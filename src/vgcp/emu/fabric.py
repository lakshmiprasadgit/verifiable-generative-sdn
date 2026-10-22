"""The privileged side of the emulation, behind one small interface.

MininetFabric runs Mininet, Open vSwitch (OpenFlow 1.3 via ovs-ofctl), iperf3 and
ping, and therefore needs root. Everything above it (MininetNetwork) only calls the
Fabric methods, so its logic is unit-tested with a fake fabric.

Controller choice (docs/DECISIONS.md): the control loop programs the switches
directly with ovs-ofctl instead of running a separate controller process (OS-Ken
installs and imports on this Python, but would add inter-process calls whose latency
and failures are not what this research studies). Routing is proactive, so no
packet-in handling is needed; the Fabric boundary keeps a controller a drop-in.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Protocol

from vgcp.emu.openflow import FlowRule, parse_dump_flows, parse_dump_meters, parse_dump_ports, parse_meter_features
from vgcp.emu.plan import EmulationPlan
from vgcp.emu.telemetry import Snapshot, parse_ping


class Fabric(Protocol):
    def setup(self, plan: EmulationPlan) -> None: ...
    def add_flows(self, switch: str, rules: list[FlowRule]) -> None: ...
    def del_flows(self, switch: str, cookie: int, mask: int) -> None: ...
    def set_meter(self, switch: str, spec: str, new: bool) -> None: ...
    def set_port(self, switch: str, port: int, up: bool) -> None: ...
    def set_traffic(self, cls: str, mbps: float, packet_bytes: int) -> None: ...
    def start_probes(self, slices: list[str], count: int, interval_s: float) -> None: ...
    def snapshot(self) -> Snapshot: ...
    def close(self) -> None: ...


class FabricError(RuntimeError):
    pass


log = logging.getLogger(__name__)


def is_emulation_process(argv: list[str], plan: EmulationPlan) -> bool:
    """A traffic generator, iperf3 server or probe this fabric starts for the plan
    (matched by program and the plan's receiver ports or addresses)."""
    if not argv:
        return False
    prog, args = os.path.basename(argv[0]), set(argv[1:])
    ports = {str(5201 + i) for i in range(len(plan.receivers))}
    ips = {h.ip for h in plan.receivers.values()}
    if prog == "iperf3":
        return bool(ports & args) and ("-s" in args or bool(ips & args))
    return prog == "ping" and bool(ips & args)


def _emulation_processes(plan: EmulationPlan) -> list[int]:
    """Live emulation processes outside the root network namespace (Mininet hosts).
    mnexec execs the command, so `mn -c` (which kills mnexec) does not catch them, and
    they keep a host's namespace alive after the network is gone (first run)."""
    try:
        root_ns = os.readlink("/proc/1/ns/net")
    except OSError:
        return []  # not root: cannot see other namespaces
    pids = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            argv = [a.decode(errors="replace") for a in Path(f"/proc/{d}/cmdline").read_bytes().split(b"\0") if a]
            ns = os.readlink(f"/proc/{d}/ns/net")
        except OSError:
            continue  # exited meanwhile
        if ns != root_ns and is_emulation_process(argv, plan):
            pids.append(int(d))
    return sorted(pids)


def leftover_resources(plan: EmulationPlan) -> list[str]:
    """This plan's switch-side interfaces, OVS bridges and host processes that still
    exist (root only). Only what this plan creates is looked at; nothing else on the
    host is touched (an iperf3 service in the root namespace, for example)."""
    left = [f"intf:{n}" for n in plan.switch_interfaces() if os.path.exists(f"/sys/class/net/{n}")]
    for sw in plan.switches:
        if subprocess.run(["ovs-vsctl", "br-exists", sw], capture_output=True).returncode == 0:
            left.append(f"bridge:{sw}")
    left += [f"proc:{pid}" for pid in _emulation_processes(plan)]
    return left


def remove_resources(names: list[str]) -> None:
    """Delete resources named as leftover_resources() reports them."""
    for item in names:
        kind, name = item.split(":", 1)
        if kind == "proc":
            try:
                os.kill(int(name), signal.SIGKILL)
            except ProcessLookupError:
                pass
            continue
        cmd = ["ip", "link", "del", name] if kind == "intf" else ["ovs-vsctl", "--if-exists", "del-br", name]
        subprocess.run(cmd, capture_output=True)


def _stop_process(proc) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


class MininetFabric:
    """Real network: requires root, Mininet, Open vSwitch with the openvswitch kernel module, iperf3."""

    def __init__(self) -> None:
        if os.geteuid() != 0:
            raise FabricError("the Mininet backend needs root: run it with sudo (see scripts/mininet_run.sh)")
        for tool in ("ovs-ofctl", "ovs-vsctl", "ovs-appctl", "iperf3", "ping"):
            if shutil.which(tool) is None:
                raise FabricError(f"{tool} not found")
        self.net = None
        self.plan: EmulationPlan | None = None
        self._traffic: dict[str, tuple[float, int, object]] = {}
        self._probes: dict[str, object] = {}
        self._servers: list[object] = []
        self.stale_removed: list[str] = []  # leftovers of an earlier run, deleted before setup
        self.forced_cleanup: list[str] = []  # what Mininet's own stop() left behind and close() deleted

    # ---------------------------------------------------------------- topology
    def setup(self, plan: EmulationPlan) -> None:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch
        from mininet.topo import Topo

        class _Topo(Topo):
            def build(self_inner) -> None:
                for sw in plan.switches:
                    self_inner.addSwitch(sw, dpid=plan.dpid(sw), protocols="OpenFlow13", failMode="secure")
                for link in plan.links.values():
                    self_inner.addLink(link.a, link.b, port1=link.port_a, port2=link.port_b,
                                       bw=link.capacity_mbps, delay=f"{link.delay_ms}ms")  # HTB rate + netem delay
                for h in list(plan.senders.values()) + list(plan.receivers.values()):
                    self_inner.addHost(h.name, ip=f"{h.ip}/16")
                    self_inner.addLink(h.name, h.switch, port2=h.port, bw=1000)

        self.plan = plan
        # a crashed earlier run (or the pre-fix code) can leave this plan's interfaces
        # behind; Mininet does not delete them and fails with "RTNETLINK answers: File exists"
        self.stale_removed = leftover_resources(plan)
        if self.stale_removed:
            log.warning("removing leftovers of an earlier run: %s", self.stale_removed)
            remove_resources(self.stale_removed)
        # build=False so that self.net exists, and can be stopped, if building fails half way
        self.net = Mininet(topo=_Topo(), switch=OVSSwitch, link=TCLink, controller=None, build=False,
                           autoSetMacs=True, autoStaticArp=True, waitConnected=False)
        try:
            self.net.build()
            self.net.start()
            features = self._ofctl("meter-features", plan.ingress)
            if not parse_meter_features(features):
                raise FabricError(f"{plan.ingress} reports no OpenFlow meter support, so slice budgets cannot be "
                                  f"policed:\n{features}")
            for i, h in enumerate(plan.receivers.values()):
                self._servers.append(self.net.get(h.name).popen(
                    ["iperf3", "-s", "-p", str(5201 + i)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            time.sleep(0.5)
        except BaseException as e:
            try:
                self.close()
            except Exception as ce:
                e.add_note(f"cleanup after the failed setup also failed: {ce}")
            raise

    # ---------------------------------------------------------------- OpenFlow
    def _ofctl(self, *args: str) -> str:
        r = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "--no-names", *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise FabricError(f"ovs-ofctl {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout

    def add_flows(self, switch: str, rules: list[FlowRule]) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".flows", delete=False) as f:
            f.write("".join(r.text() + "\n" for r in rules))
            path = f.name
        try:
            self._ofctl("add-flows", switch, path)
        finally:
            os.unlink(path)

    def del_flows(self, switch: str, cookie: int, mask: int) -> None:
        self._ofctl("del-flows", switch, f"cookie={cookie:#x}/{mask:#x}")

    def set_meter(self, switch: str, spec: str, new: bool) -> None:
        self._ofctl("add-meter" if new else "mod-meter", switch, spec)

    def set_port(self, switch: str, port: int, up: bool) -> None:
        self._ofctl("mod-port", switch, str(port), "up" if up else "down")

    def meters(self, switch: str) -> dict[int, int | None]:
        """Meters that exist on a switch -> drop rate in kbps (for tests and diagnostics)."""
        return parse_dump_meters(self._ofctl("dump-meters", switch))

    # ---------------------------------------------------------------- traffic and probes
    def set_traffic(self, cls: str, mbps: float, packet_bytes: int) -> None:
        old = self._traffic.get(cls)
        if old and abs(old[0] - mbps) <= 0.01 * max(mbps, 1e-9) and old[1] == packet_bytes:
            return
        if old:
            old[2].terminate()
            old[2].wait(timeout=5)
            del self._traffic[cls]
        if mbps <= 0:
            return
        assert self.plan is not None and self.net is not None
        src, dst = self.plan.senders[cls], self.plan.receivers[cls]
        port = 5201 + list(self.plan.receivers).index(cls)
        proc = self.net.get(src.name).popen(
            ["iperf3", "-c", dst.ip, "-u", "-b", f"{mbps:.3f}M", "-l", str(packet_bytes), "-t", "86400", "-p", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._traffic[cls] = (mbps, packet_bytes, proc)

    def start_probes(self, slices: list[str], count: int, interval_s: float) -> None:
        assert self.plan is not None and self.net is not None
        for s in slices:
            src, dst = self.plan.senders[s], self.plan.receivers[s]
            self._probes[s] = self.net.get(src.name).popen(
                ["ping", "-n", "-c", str(count), "-i", f"{interval_s}", "-W", "1", dst.ip],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    def _collect_probes(self) -> dict[str, list[float]]:
        out = {}
        for s, proc in self._probes.items():
            try:
                text, _ = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                text, _ = proc.communicate()
            out[s] = parse_ping(text or "")
        self._probes = {}
        return out

    def snapshot(self) -> Snapshot:
        assert self.plan is not None
        dead = sorted(cls for cls, (_, _, proc) in self._traffic.items() if proc.poll() is not None)
        if dead:  # otherwise the slot would be measured with less traffic than was set
            raise FabricError(f"traffic generator (iperf3 client) exited for {dead}")
        rtts = self._collect_probes()
        self._refresh_flow_stats()
        t = time.monotonic()  # the counters read below are current as of now
        ports = {sw: parse_dump_ports(self._ofctl("dump-ports", sw)) for sw in self.plan.switches}
        flows = {sw: parse_dump_flows(self._ofctl("dump-flows", sw)) for sw in self.plan.switches}
        return Snapshot(t, ports, flows, rtts)

    def _refresh_flow_stats(self) -> None:
        """Make the OpenFlow rule counters current before reading them.

        OVS copies rule counters from the kernel datapath in revalidation cycles,
        every max-revalidator ms (default 500, see ovs-vswitchd.conf.db(5)). A plain
        dump can therefore be up to half a slot old, and per-slot rates read about
        0.5x or 1.5x their value (Mininet campaigns 2026-10-22: offered load 42 / 126
        instead of 84 Mbit/s, and spurious background jumps that triggered reroutes).
        `ovs-appctl revalidator/wait` returns after a full cycle has completed. It is
        read-only and changes no configuration. Port counters are read directly from
        the network device and need no refresh.
        """
        r = subprocess.run(["ovs-appctl", "revalidator/wait"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise FabricError(f"ovs-appctl revalidator/wait failed: {r.stderr.strip() or r.returncode}")

    def close(self) -> None:
        """Release everything, also after a partial setup. Idempotent; every step runs even
        if an earlier one fails, and the failures are raised together at the end."""
        errors = []
        procs = [proc for _, _, proc in self._traffic.values()] + list(self._probes.values()) + self._servers
        self._traffic, self._probes, self._servers = {}, {}, []
        for proc in procs:
            try:
                _stop_process(proc)
            except Exception as e:
                errors.append(f"stopping pid {getattr(proc, 'pid', '?')}: {e!r}")
        net, self.net = self.net, None
        if net is not None:
            try:
                net.stop()
            except Exception as e:
                errors.append(f"mininet stop: {e!r}")
        if self.plan is not None:
            left = leftover_resources(self.plan)
            if left:
                log.warning("Mininet stop left %s behind; deleting", left)
                self.forced_cleanup += left
                remove_resources(left)
                still = leftover_resources(self.plan)
                if still:
                    errors.append(f"could not delete {still}")
        if errors:
            raise FabricError("; ".join(errors))
