"""A fake Fabric: fluid-model counters consistent with installed rules (tests only).

It enforces Open vSwitch's meter rules, so ordering bugs fail here and not first on
a real switch: a flow referencing a meter that does not exist on that switch is
rejected (OFPMMFC_INVALID_METER), as are adding an existing meter and modifying a
missing one.

Its counters behave like OVS's (first Mininet campaign, 2026-10-22): a deleted and
re-added rule starts again at 0 bytes with a new age (duration), and a slice's
ingress rule counts packets before the meter drops them.
"""

from __future__ import annotations

import re

from vgcp.emu.fabric import FabricError
from vgcp.emu.openflow import FlowCounters, PortCounters
from vgcp.emu.plan import EmulationPlan
from vgcp.emu.telemetry import Snapshot


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s


class FakeFabric:
    def __init__(self, clock: FakeClock, lose_probes: set[str] | None = None,
                 fail_on: str | None = None) -> None:
        self.clock, self.lose_probes, self.fail_on = clock, lose_probes or set(), fail_on
        self.closed = 0
        self.rules: dict[str, list] = {}
        self.meters: dict[str, dict[int, float]] = {}
        self.ports_down: set[tuple[str, int]] = set()
        self.rates: dict[str, tuple[float, int]] = {}
        self.calls: list[tuple] = []
        self._flow_bytes: dict[tuple[str, int, str], float] = {}
        self._installed: dict[tuple[str, int, str], float] = {}  # rule -> install time (for duration)
        self._tx: dict[tuple[str, int], float] = {}
        self._last = 0.0
        self._probe: list[str] = []

    def _maybe_fail(self, op):
        if self.fail_on == op:
            raise FabricError(f"injected failure in {op}")

    def setup(self, plan: EmulationPlan) -> None:
        self.plan = plan
        self.rules = {sw: [] for sw in plan.switches}
        self.calls.append(("setup",))
        self._maybe_fail("setup")

    def add_flows(self, switch, rules):
        self._maybe_fail("add_flows")
        for r in rules:
            m = re.search(r"meter:(\d+)", r.actions)
            if m and int(m.group(1)) not in self.meters.get(switch, {}):
                raise FabricError(f"ovs-ofctl add-flows {switch}: OFPMMFC_INVALID_METER ({r.text()})")
        self.rules[switch] += rules
        for r in rules:  # a new rule's counters start at zero
            self._flow_bytes[(switch, r.cookie, r.match)] = 0.0
            self._installed[(switch, r.cookie, r.match)] = self.clock()
        self.calls.append(("add_flows", switch, len(rules)))

    def del_flows(self, switch, cookie, mask):
        gone = [r for r in self.rules[switch] if (r.cookie & mask) == (cookie & mask)]
        self.rules[switch] = [r for r in self.rules[switch] if (r.cookie & mask) != (cookie & mask)]
        for r in gone:
            self._flow_bytes.pop((switch, r.cookie, r.match), None)
            self._installed.pop((switch, r.cookie, r.match), None)
        self.calls.append(("del_flows", switch, cookie))

    def set_meter(self, switch, spec, new):
        m = int(re.search(r"meter=(\d+)", spec).group(1))
        kbps = int(re.search(r"rate=(\d+)", spec).group(1))
        exists = m in self.meters.get(switch, {})
        if new and exists:
            raise FabricError(f"ovs-ofctl add-meter {switch}: OFPMMFC_METER_EXISTS")
        if not new and not exists:
            raise FabricError(f"ovs-ofctl mod-meter {switch}: OFPMMFC_UNKNOWN_METER")
        self.meters.setdefault(switch, {})[m] = kbps / 1000
        self.calls.append(("set_meter", switch, m, kbps / 1000, new))

    def set_port(self, switch, port, up):
        (self.ports_down.discard if up else self.ports_down.add)((switch, port))
        self.calls.append(("set_port", switch, port, up))

    def set_traffic(self, cls, mbps, packet_bytes):
        self.rates[cls] = (mbps, packet_bytes)

    def start_probes(self, slices, count, interval_s):
        self._probe = list(slices)

    # ---------------------------------------------------------------- counters
    def _forward(self, cls):
        """Follow the class's forward rules from the ingress: [(switch, rule, out_port)]."""
        src, dst = self.plan.senders[cls], self.plan.receivers[cls]
        sw, hops, seen = self.plan.ingress, [], set()
        while sw not in seen:
            seen.add(sw)
            rule = next((r for r in self.rules[sw] if f"nw_src={src.ip},nw_dst={dst.ip}" in r.match), None)
            if rule is None:
                return hops
            out = int(re.search(r"output:(\d+)", rule.actions).group(1))
            hops.append((sw, rule, out))
            nxt = [l for l in self.plan.links.values() if (l.a, l.port_a) == (sw, out)]
            if not nxt:
                return hops
            sw = nxt[0].b
        return hops

    def snapshot(self) -> Snapshot:
        dt = self.clock() - self._last
        self._last = self.clock()
        load = {}
        for cls, (mbps, _) in self.rates.items():
            hops = self._forward(cls)
            if not hops:
                continue
            m = re.search(r"meter:(\d+)", hops[0][1].actions)
            admitted = min(mbps, self.meters.get(hops[0][0], {}).get(int(m.group(1)), mbps)) if m else mbps
            if any((sw, out) in self.ports_down for sw, _, out in hops):
                admitted = 0.0
            load[cls] = (hops, mbps, admitted)
        for cls, (hops, offered, admitted) in load.items():
            for i, (sw, rule, out) in enumerate(hops):
                rate = offered if i == 0 else admitted
                key = (sw, rule.cookie, rule.match)
                lived = min(dt, self.clock() - self._installed.get(key, -1e9))  # rule may be younger than dt
                self._flow_bytes[key] = self._flow_bytes.get(key, 0.0) + rate * 1e6 / 8 * lived
                self._tx[(sw, out)] = self._tx.get((sw, out), 0.0) + admitted * 1e6 / 8 * dt
        ports = {sw: {} for sw in self.plan.switches}
        for (sw, port), b in self._tx.items():
            ports[sw][port] = PortCounters(0, 0, 0, int(b), 0)
        for l in self.plan.links.values():
            ports[l.a].setdefault(l.port_a, PortCounters(0, 0, 0, 0, 0))
        flows = {sw: [FlowCounters(r.cookie, r.priority, r.match, 0, int(self._flow_bytes.get((sw, r.cookie, r.match), 0)),
                                   int(re.search(r"output:(\d+)", r.actions).group(1)),
                                   self.clock() - self._installed.get((sw, r.cookie, r.match), 0.0))
                      for r in self.rules[sw]]
                 for sw in self.plan.switches}
        rtts = {}
        for s in self._probe:
            if s in self.lose_probes:
                rtts[s] = []
                continue
            hops = load.get(s, ([], 0, 0))[0]
            delay = sum(l.delay_ms for l in self.plan.links.values() for sw, _, out in hops if (l.a, l.port_a) == (sw, out))
            rtts[s] = [2 * delay + 0.1] * 8
        self._probe = []
        return Snapshot(self.clock(), ports, flows, rtts)

    def close(self):
        self.closed += 1
        self.calls.append(("close",))
