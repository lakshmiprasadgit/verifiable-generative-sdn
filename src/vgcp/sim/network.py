"""Simulated network backend: a ground truth for closed-loop experiments without root.

This is NOT the shield's nominal model. It has its own dynamics, configured per
scenario, so that the shield's predictions can be wrong:

* true packet sizes and multiplicative latency noise may differ from the model;
* overload is physical: a link whose offered load exceeds capacity delivers only
  its capacity, drops the rest (loss) and adds a full buffer of delay;
* background traffic (outside the managed slices) follows scheduled events;
* telemetry is noisy and can be delayed, frozen (stale) or missing;
* the controller can fail to install actions, and installation can be delayed.

Background load is measured as the link's delivered rate minus the managed slices'
delivered rates on it - the same definition the Mininet backend uses (port counters
minus flow counters). During overload this under-measures the *offered* background,
because both counters see post-drop rates; that is a real failure mode, kept on purpose.

Results from this backend are simulation results, not measurements of a real network.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any

from vgcp.action import ControlAction
from vgcp.config import ProjectConfig
from vgcp.loop.interfaces import ControllerFailure, Observation
from vgcp.sim.scenario import Scenario
from vgcp.state import Demand, Measurement, NetworkState

P99 = math.log(100.0)
BASE_FLOW_ENTRIES = 10.0  # non-slice rules per switch (table-miss, ARP, ...)


class SimulatedNetwork:
    def __init__(self, cfg: ProjectConfig, scenario: Scenario, seed: int) -> None:
        self.cfg, self.sc, self.seed = cfg, scenario, seed
        self.rng = random.Random(f"sim:{seed}")
        self.topo = cfg.topology
        self.slices = [s.name for s in cfg.slices]
        self.dt = cfg.delta_t_s
        self.t = 0
        self.installed: ControlAction = cfg.fallback_action  # network starts under pi_0
        self._pending: deque[tuple[int, ControlAction]] = deque()
        self._truth: list[dict[str, Any]] = []
        self._meas: list[tuple[dict[str, float], dict[str, float]]] = []  # (state values, demand values)
        self._last_fresh: tuple[int, dict, dict] | None = None
        self._step_truth()  # slot 0 under pi_0

    # ---------------------------------------------------------------- backend interface
    def observe(self) -> Observation:
        t = self.t
        now = t * self.dt
        src = max(0, t - self.sc.measurement_delay_slots)
        st_vals, dm_vals = self._meas[src]
        ts = src * self.dt
        if any(w.active(t) for w in self.sc.stale_telemetry) and self._last_fresh is not None:
            src_ts, st_vals, dm_vals = self._last_fresh  # collector stuck: re-sends old values
            ts = src_ts
        else:
            self._last_fresh = (ts, st_vals, dm_vals)
        hidden = [p for m in self.sc.missing_telemetry if m.window.active(t) for p in m.prefixes]

        def measure(vals: dict[str, float]) -> dict[str, Measurement]:
            return {k: Measurement(None if any(k.startswith(p) for p in hidden) else v, ts) for k, v in vals.items()}

        return Observation(t, NetworkState(t, measure(st_vals)), Demand(t, measure(dm_vals)), now)

    def apply(self, action: ControlAction) -> None:
        if any(w.active(self.t) for w in self.sc.controller_failures):
            raise ControllerFailure(f"switches unreachable at slot {self.t}")
        self._pending.append((self.t + self.sc.actuation_delay_slots, action))

    def advance(self) -> None:
        self.t += 1
        while self._pending and self._pending[0][0] < self.t:
            self.installed = self._pending.popleft()[1]
        self._step_truth()

    def ground_truth(self) -> dict[str, Any]:
        return self._truth[self.t]

    # ---------------------------------------------------------------- dynamics
    def _noise(self, rel: float) -> float:
        return max(0.0, 1.0 + rel * self.rng.gauss(0.0, 1.0))

    def _step_truth(self) -> None:
        t, sc, a, topo = self.t, self.sc, self.installed, self.topo
        offered, devices = {}, {}
        for s in self.slices:
            f = math.prod(e.factor for e in sc.demand_events if e.slice == s and e.window.active(t))
            offered[s] = sc.demand_mbps[s] * f * self._noise(sc.demand_noise)
            devices[s] = sc.devices[s]
        background = {lid: sum(e.mbps for e in sc.background if lid in e.links and e.window.active(t))
                      for lid in topo.links}
        route = {s: topo.paths[a.path[s]].links for s in self.slices}
        dead = {s for s in self.slices if any(not a.link_power.get(l, True) for l in route[s])}
        load = {}
        for s in self.slices:
            frac = 1.0 if devices[s] <= 0 else min(1.0, a.admission_limit[s] / devices[s])
            load[s] = 0.0 if s in dead else min(offered[s] * frac, float(a.rate_budget_mbps[s]))  # meters police
        util, deliv, link_lat = {}, {}, {}
        for lid, link in topo.links.items():
            users = [s for s in self.slices if lid in route[s] and s not in dead]
            total = sum(load[s] for s in users) + background[lid]
            util[lid] = total / link.capacity_mbps
            deliv[lid] = 1.0 if total <= link.capacity_mbps else link.capacity_mbps / total
            pkt_ms = max((sc.truth.packet_size_bytes[s] for s in users), default=1500.0) * 8 / (link.capacity_mbps * 1e3)
            queue = sc.truth.buffer_ms if util[lid] >= 1.0 else min(sc.truth.buffer_ms, P99 * pkt_ms / (1.0 - util[lid]))
            link_lat[lid] = link.prop_delay_ms + sc.truth.processing_delay_ms_per_hop + queue
        truth: dict[str, Any] = {"t": t, "link_util": util, "background_mbps": background,
                                 "installed": a.to_dict(), "offered_mbps": offered}
        lat, loss, thr = {}, {}, {}
        for s in self.slices:
            delivered = math.prod(deliv[l] for l in route[s])
            loss[s] = 1.0 if s in dead else 1.0 - delivered
            thr[s] = load[s] * delivered
            lat[s] = math.inf if s in dead else sum(link_lat[l] for l in route[s]) * self._noise(sc.truth.latency_noise)
        truth.update(latency_p99_ms=lat, loss=loss, throughput_mbps=thr)
        self._truth.append(truth)

        # ---- telemetry as a controller would see it (noisy, post-drop counters)
        n = sc.truth.measurement_noise
        st: dict[str, float] = {}
        for lid, link in topo.links.items():
            users = [s for s in self.slices if lid in route[s] and s not in dead]
            link_rate = min(util[lid], 1.0) * link.capacity_mbps  # port counter: delivered bits
            managed = sum(load[s] for s in users) * deliv[lid]  # flow counters of slice rules
            st[f"link_utilization.{lid}"] = min(1.0, max(0.0, min(util[lid], 1.0) * self._noise(n)))
            st[f"background_load_mbps.{lid}"] = max(0.0, (link_rate - managed) * self._noise(n))
        for s in self.slices:
            st[f"latency_p99_ms.{s}"] = min(10000.0, lat[s] * self._noise(n)) if math.isfinite(lat[s]) else 10000.0
            st[f"jitter_ms.{s}"] = 0.2 * st[f"latency_p99_ms.{s}"]
            st[f"loss_rate.{s}"] = min(1.0, max(0.0, loss[s] * self._noise(n)))
            st[f"throughput_mbps.{s}"] = thr[s] * self._noise(n)
            st[f"queue_occupancy_pkts.{s}"] = sum(min(1e6, u / max(1e-9, 1 - u)) if u < 1 else 1e6
                                                  for u in (util[l] for l in route[s]))
            st[f"active_users.{s}"] = min(devices[s], float(a.admission_limit[s]))
        for sw in topo.switches:
            n_slices = sum(1 for s in self.slices if sw in topo.paths[a.path[s]].nodes)
            st[f"flow_table_occupancy.{sw}"] = BASE_FLOW_ENTRIES + 2 * n_slices
        st["energy_w"] = sum(1.0 + 2.0 * min(util[l], 1.0) for l in topo.links if a.link_power.get(l, True))
        dm = {}
        for s in self.slices:
            dm[f"offered_load_mbps.{s}"] = offered[s] * self._noise(n)
            dm[f"active_devices.{s}"] = devices[s]
        self._meas.append((st, dm))
