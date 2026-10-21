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

import os
import shutil
import subprocess
import tempfile
import time
from typing import Protocol

from vgcp.emu.openflow import FlowRule, parse_dump_flows, parse_dump_ports
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


class MininetFabric:
    """Real network: requires root, Mininet, Open vSwitch with the openvswitch kernel module, iperf3."""

    def __init__(self) -> None:
        if os.geteuid() != 0:
            raise FabricError("the Mininet backend needs root: run it with sudo (see scripts/mininet_run.sh)")
        for tool in ("ovs-ofctl", "ovs-vsctl", "iperf3", "ping"):
            if shutil.which(tool) is None:
                raise FabricError(f"{tool} not found")
        self.net = None
        self.plan: EmulationPlan | None = None
        self._traffic: dict[str, tuple[float, int, object]] = {}
        self._probes: dict[str, object] = {}
        self._servers: list[object] = []

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
        self.net = Mininet(topo=_Topo(), switch=OVSSwitch, link=TCLink, controller=None,
                           autoSetMacs=True, autoStaticArp=True, waitConnected=False)
        self.net.start()
        for i, h in enumerate(plan.receivers.values()):
            self._servers.append(self.net.get(h.name).popen(
                ["iperf3", "-s", "-p", str(5201 + i)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(0.5)

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
        rtts = self._collect_probes()
        t = time.monotonic()
        ports = {sw: parse_dump_ports(self._ofctl("dump-ports", sw)) for sw in self.plan.switches}
        flows = {sw: parse_dump_flows(self._ofctl("dump-flows", sw)) for sw in self.plan.switches}
        return Snapshot(t, ports, flows, rtts)

    def close(self) -> None:
        for _, _, proc in self._traffic.values():
            proc.terminate()
        for proc in list(self._probes.values()) + self._servers:
            proc.terminate()
        if self.net is not None:
            self.net.stop()
