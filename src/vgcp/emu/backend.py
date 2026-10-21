"""MininetNetwork: the NetworkBackend for an emulated network (paper Sec 3, steps 1 and 7).

One control slot is real time (delta_t_s). Per slot:
  advance(): install due actions (OpenFlow rules, meters, port states), set traffic
             generator rates for the slot, start latency probes, wait until the slot
             ends, read all counters -> measured state of the slot.
  observe(): the latest measurement as an Observation, with the scenario's telemetry
             faults applied (frozen, missing, delayed) exactly as in the simulator.
  apply():   queue an action (actuation delay) or fail (controller-failure windows).

There is no ground truth in a real network: ground_truth() returns the *measured*
condition of the slot that just elapsed, marked source="measured". A slice whose
probes all got lost is scored with infinite latency (unknown is never "fast").

Emulation limits (documented in docs/EXPERIMENTS.md): offered load is generated at
constant rate per slot (no per-slot demand noise); admission control is emulated by
scaling the sender's rate; background traffic follows one path at a time.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Callable

from vgcp.action import ControlAction
from vgcp.config import ProjectConfig
from vgcp.emu.fabric import Fabric, FabricError
from vgcp.emu.openflow import (
    COOKIE_MASK,
    FlowRule,
    action_rules,
    all_classes,
    background_rules,
    class_cookie,
    meter_id,
    meter_spec,
    slice_classes,
)
from vgcp.emu.plan import BACKGROUND, plan_emulation
from vgcp.emu.telemetry import Snapshot, link_measurements, slice_measurements
from vgcp.errors import ConfigError
from vgcp.loop.interfaces import ControllerFailure, Observation
from vgcp.sim.scenario import Scenario
from vgcp.state import Demand, Measurement, NetworkState

PROBES_PER_SLOT = 8


class MininetNetwork:
    def __init__(self, cfg: ProjectConfig, scenario: Scenario, seed: int, fabric: Fabric,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.cfg, self.sc, self.seed, self.fabric = cfg, scenario, seed, fabric
        self.clock, self.sleep = clock, sleep
        self.topo, self.dt = cfg.topology, cfg.delta_t_s
        self.plan = plan_emulation(cfg)
        self.paths = {pid: p.nodes for pid, p in self.topo.paths.items()}
        self.slices = [s.name for s in cfg.slices]
        self.bg_path = self._background_path()
        self.installed: ControlAction | None = None
        self._pending: deque[tuple[int, ControlAction]] = deque()
        self._meas: list[tuple[dict[str, float], dict[str, float], dict[str, Any]]] = []
        self._last_fresh = None
        self._meters: dict[str, set[int]] = {}  # meters created on each switch (flows may reference only these)
        self.t = 0
        try:
            self.fabric.setup(self.plan)
            classes = all_classes(cfg.fallback_action)
            if self.bg_path is not None:
                for sw in self.paths[self.bg_path]:
                    self._add_flows(sw, [r for r in background_rules(self.plan, self.paths[self.bg_path], classes)
                                         if r.switch == sw])
            self._install(cfg.fallback_action, first=True)
            self._start = self.clock()
            self._snap = self.fabric.snapshot()
            self._run_slot()  # slot 0 under pi_0
        except BaseException as e:
            # nobody else holds a reference yet: release a partially built network here,
            # or its interfaces and processes outlive the failure (first Mininet run)
            try:
                self.fabric.close()
            except Exception as ce:
                e.add_note(f"cleanup after the failed construction also failed: {ce}")
            raise

    # ---------------------------------------------------------------- backend interface
    def observe(self) -> Observation:
        t, now = self.t, self.t * self.dt
        src = max(0, t - self.sc.measurement_delay_slots)
        st, dm, _ = self._meas[src]
        ts = src * self.dt
        if any(w.active(t) for w in self.sc.stale_telemetry) and self._last_fresh is not None:
            ts, st, dm = self._last_fresh
        else:
            self._last_fresh = (ts, st, dm)
        hidden = [p for m in self.sc.missing_telemetry if m.window.active(t) for p in m.prefixes]

        def measure(vals):
            return {k: Measurement(None if (any(k.startswith(p) for p in hidden) or v != v) else v, ts)
                    for k, v in vals.items()}

        return Observation(t, NetworkState(t, measure(st)), Demand(t, measure(dm)), now)

    def apply(self, action: ControlAction) -> None:
        if any(w.active(self.t) for w in self.sc.controller_failures):
            raise ControllerFailure(f"switches unreachable at slot {self.t}")
        self._pending.append((self.t + self.sc.actuation_delay_slots, action))

    def advance(self) -> None:
        self.t += 1
        while self._pending and self._pending[0][0] < self.t:
            self._install(self._pending.popleft()[1])
        self._run_slot()

    def ground_truth(self) -> dict[str, Any]:
        return self._meas[self.t][2]

    def close(self) -> None:
        self.fabric.close()

    # ---------------------------------------------------------------- internals
    def _background_path(self) -> str | None:
        paths = set()
        for e in self.sc.background:
            match = [pid for pid, p in self.topo.paths.items() if set(e.links) <= set(p.links)]
            if not match:
                raise ConfigError(f"Mininet backend: background links {list(e.links)} do not lie on one path")
            paths.add(match[0])
        if len(paths) > 1:
            raise ConfigError("Mininet backend: background events on more than one path are not supported")
        return paths.pop() if paths else None

    def _add_flows(self, switch: str, rules: list[FlowRule]) -> None:
        """Install rules, refusing any that references a meter not yet created on that switch."""
        missing = {m for r in rules if (m := r.meter) is not None} - self._meters.get(switch, set())
        if missing:
            raise FabricError(f"flows on {switch} reference meters {sorted(missing)} that do not exist there")
        self.fabric.add_flows(switch, rules)

    def _install(self, action: ControlAction, first: bool = False) -> None:
        old = self.installed
        classes = all_classes(action)
        rules = action_rules(self.plan, self.paths, action)
        # meters first: an OpenFlow switch rejects a flow whose meter does not exist yet
        for s in slice_classes(action):
            if first or old.rate_budget_mbps[s] != action.rate_budget_mbps[s]:
                m = meter_id(action, s)
                self.fabric.set_meter(self.topo.ingress, meter_spec(m, action.rate_budget_mbps[s]), new=first)
                self._meters.setdefault(self.topo.ingress, set()).add(m)
        for s in slice_classes(action):
            if first or old.path[s] != action.path[s]:
                ck = class_cookie(classes, s)
                for sw in self.topo.switches:
                    if not first:
                        self.fabric.del_flows(sw, ck, COOKIE_MASK)
                    mine = [r for r in rules if r.switch == sw and r.cookie == ck]
                    if mine:
                        self._add_flows(sw, mine)
        for lid in self.topo.power_controllable_links:
            if first or old.link_power[lid] != action.link_power[lid]:
                for sw, port in self.plan.link_ports(lid):
                    self.fabric.set_port(sw, port, action.link_power[lid])
        self.installed = action

    def _offered(self, s: str, t: int) -> float:
        f = math.prod(e.factor for e in self.sc.demand_events if e.slice == s and e.window.active(t))
        frac = min(1.0, self.installed.admission_limit[s] / self.sc.devices[s]) if self.sc.devices[s] > 0 else 1.0
        return self.sc.demand_mbps[s] * f * frac

    def _run_slot(self) -> None:
        t, a = self.t, self.installed
        for s in self.slices:
            self.fabric.set_traffic(s, self._offered(s, t), int(self.sc.truth.packet_size_bytes[s]))
        bg = sum(e.mbps for e in self.sc.background if e.window.active(t))
        self.fabric.set_traffic(BACKGROUND, bg, 1400)
        self.fabric.start_probes(self.slices, PROBES_PER_SLOT, self.dt / (PROBES_PER_SLOT + 2))
        deadline = self._start + (t + 1) * self.dt
        self.sleep(max(0.0, deadline - self.clock()))
        before, after = self._snap, self.fabric.snapshot()
        self._snap = after
        self._meas.append(self._measure(before, after, a, t))

    def _measure(self, before: Snapshot, after: Snapshot, a: ControlAction, t: int):
        classes = all_classes(a)
        cookies = {s: class_cookie(classes, s) for s in slice_classes(a)}
        st = link_measurements(self.plan, before, after, cookies)
        sl = slice_measurements(self.plan, before, after, cookies, {s: self.paths[a.path[s]] for s in self.slices})
        for s in self.slices:
            for fam in ("latency_p99_ms", "jitter_ms", "loss_rate", "throughput_mbps"):
                st[f"{fam}.{s}"] = sl[f"{fam}.{s}"]
            st[f"active_users.{s}"] = min(self.sc.devices[s], float(a.admission_limit[s]))
        for sw in self.topo.switches:
            st[f"flow_table_occupancy.{sw}"] = float(len(after.flows.get(sw, [])))
        st["energy_w"] = sum(1.0 + 2.0 * min(st[f"link_utilization.{l}"], 1.0) for l in self.topo.links
                             if a.link_power.get(l, True) and st[f"link_utilization.{l}"] == st[f"link_utilization.{l}"])
        dm = {}
        for s in self.slices:
            dm[f"offered_load_mbps.{s}"] = sl[f"offered_load_mbps.{s}"]
            dm[f"active_devices.{s}"] = float(self.sc.devices[s])
        lat = {s: (st[f"latency_p99_ms.{s}"] if st[f"latency_p99_ms.{s}"] == st[f"latency_p99_ms.{s}"] else math.inf)
               for s in self.slices}
        measured = {
            "t": t, "source": "measured", "installed": a.to_dict(),
            "link_util": {l: st[f"link_utilization.{l}"] for l in self.topo.links},
            "background_mbps": {l: st[f"background_load_mbps.{l}"] for l in self.topo.links},
            "offered_mbps": {s: dm[f"offered_load_mbps.{s}"] for s in self.slices},
            "latency_p99_ms": lat,
            "loss": {s: st[f"loss_rate.{s}"] for s in self.slices},
            "throughput_mbps": {s: st[f"throughput_mbps.{s}"] for s in self.slices},
        }
        # keep state values inside the schema bounds the shield validates against (L5)
        for k, v in list(st.items()):
            if k.startswith("latency_p99_ms.") or k.startswith("jitter_ms."):
                st[k] = min(v, 10000.0) if v == v else v
        return st, dm, measured
