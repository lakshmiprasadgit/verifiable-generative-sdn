"""Deterministic fallback policies pi_0 (paper Eq 13, Remark 1, Assumption 3).

StaticFallbackPolicy        one configured action regardless of state.
CapacityAwareFallbackPolicy pi_0(s): the static action, except that eMBB - the
                            elastic slice - is moved to the allowed path with the
                            most reservable room left after the measured background
                            load and the other slices' reservations, and its budget
                            is shrunk to fit. URLLC and mMTC keep their (small)
                            reservations. Without a background measurement it
                            returns the static action (nothing to adapt to).

Eq 13 uses pi_0(s-hat) along the rollout, so a state-dependent pi_0 also changes
which candidates can be certified. Neither policy is shown to be recursively
feasible (Assumption 3); the controllers record, per slot, whether pi_0 itself is
certified, so failures of Assumption 3 are measured rather than assumed away.
"""

from __future__ import annotations

import math
from typing import Sequence

from vgcp.action import ControlAction, SliceSpec
from vgcp.state import NetworkState
from vgcp.topology import Topology

POLICIES = ("static", "capacity_aware")


class StaticFallbackPolicy:
    def __init__(self, action: ControlAction) -> None:
        self.action = action

    def act(self, state: NetworkState) -> ControlAction:
        return self.action


class CapacityAwareFallbackPolicy:
    def __init__(self, base: ControlAction, topology: Topology, slices: Sequence[SliceSpec],
                 max_reserved_fraction: float, elastic_slice: str = "embb") -> None:
        self.base, self.topo, self.frac = base, topology, max_reserved_fraction
        self.slices = {s.name: s for s in slices}
        if elastic_slice not in self.slices:
            raise ValueError(f"unknown elastic slice {elastic_slice!r}")
        self.elastic = elastic_slice

    def act(self, state: NetworkState) -> ControlAction:
        bg = {lid: state.value(f"background_load_mbps.{lid}") for lid in self.topo.links}
        if any(math.isnan(v) for v in bg.values()):
            return self.base
        fixed = {s: float(self.base.rate_budget_mbps[s]) for s in self.slices if s != self.elastic}

        def room(pid: str) -> float:
            return min(
                self.frac * self.topo.links[lid].capacity_mbps - bg[lid]
                - sum(b for s, b in fixed.items() if lid in self.topo.paths[self.base.path[s]].links)
                for lid in self.topo.paths[pid].links
            )

        want = float(self.base.rate_budget_mbps[self.elastic])
        if room(self.base.path[self.elastic]) >= want:
            return self.base  # the static choice still fits: unchanged
        rooms = {pid: room(pid) for pid in self.slices[self.elastic].allowed_paths}
        best_path = max(rooms, key=lambda p: (rooms[p], -self.slices[self.elastic].allowed_paths.index(p)))
        lo, hi = self.slices[self.elastic].rate_budget_mbps
        budget = min(want, rooms[best_path])
        d = self.base.to_dict()
        d["path"][self.elastic] = best_path
        d["rate_budget_mbps"][self.elastic] = min(max(budget, lo), hi)
        return ControlAction.from_dict(d)
