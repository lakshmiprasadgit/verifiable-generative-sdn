"""Heuristic candidate generator - Stage 1 stand-in for the generative policy G_theta.

Produces a fixed, labelled list of conventional heuristics followed by seeded random
variations, in the nominal controller's order of preference. Every candidate is
constructed inside the action set A (values clipped to the configured bounds). The
heuristics are deliberately ordinary - a greedy throughput maximizer, demand
matching, a background-aware balancer, a naive shortest-delay rule - so that the
shielded and unshielded controllers face realistic, sometimes unsafe proposals.
"""

from __future__ import annotations

import math
import random

from vgcp.action import ControlAction
from vgcp.config import ProjectConfig
from vgcp.loop.interfaces import Candidate, Observation


class HeuristicCandidateGenerator:
    PREFERENCES = ("greedy", "fitted-first")

    def __init__(self, cfg: ProjectConfig, n_random: int = 4, seed: int = 0, headroom: float = 1.25,
                 preference: str = "greedy") -> None:
        if n_random < 0:
            raise ValueError("n_random must be >= 0")
        if preference not in self.PREFERENCES:
            raise ValueError(f"preference must be one of {self.PREFERENCES}")
        self.preference = preference
        self.cfg = cfg
        self.n_random = n_random
        self.seed = seed
        self.headroom = headroom  # budget = offered load * headroom (demand matching)
        self.slices = {s.name: s for s in cfg.slices}
        self.fallback = cfg.fallback_action

    # ---------------------------------------------------------------- helpers
    def _clip_budget(self, s: str, v: float) -> float:
        lo, hi = self.slices[s].rate_budget_mbps
        return float(min(max(v, lo), hi))

    def _offered(self, obs: Observation, s: str) -> float:
        return obs.demand.value(f"offered_load_mbps.{s}")  # NaN if unmeasured

    def _make(self, path, budget) -> ControlAction:
        fb = self.fallback
        return ControlAction(
            path={s: path.get(s, fb.path[s]) for s in self.slices},
            rate_budget_mbps={s: self._clip_budget(s, budget.get(s, fb.rate_budget_mbps[s])) for s in self.slices},
            admission_limit={s: self.slices[s].admission_limit[1] for s in self.slices},
            link_power={lid: True for lid in self.cfg.topology.power_controllable_links},
        )

    def _demand_matched(self, obs: Observation) -> dict[str, float]:
        # Unmeasured demand keeps pi_0's budget. (It used to count as 0, which shrank
        # budgets to the minimum whenever a counter was unavailable; Mininet audit.)
        out = {}
        for s in self.slices:
            v = self._offered(obs, s)
            out[s] = self.fallback.rate_budget_mbps[s] if v != v else v * self.headroom
        return out

    # ---------------------------------------------------------------- heuristics
    def propose(self, obs: Observation) -> list[Candidate]:
        topo = self.cfg.topology
        matched = self._demand_matched(obs)
        out = [
            # Maximize eMBB: highest budget on the high-capacity path.
            Candidate("greedy-embb", self._make({}, {**matched, "embb": self.slices["embb"].rate_budget_mbps[1]})),
            # Budgets follow measured demand, routing as pi_0.
            Candidate("demand-matched", self._make({}, matched)),
        ]
        # Capacity-fitted: put eMBB on the allowed path with the most remaining reservable
        # capacity (f_max * C - measured background - other slices' budgets) and shrink
        # its budget to fit - a conventional congestion response.
        frac, k = self.cfg.constraints.max_reserved_fraction, 1.0 + self.cfg.meter_overshoot
        others = {s: matched[s] for s in self.slices if s != "embb"}
        fit_path, fit_room = self.fallback.path["embb"], -float("inf")
        for pid in self.slices["embb"].allowed_paths:
            room = min(
                frac * topo.links[lid].capacity_mbps
                - _unknown_full(obs.state.value(f"background_load_mbps.{lid}"))
                - k * sum(b for s, b in others.items() if lid in topo.paths[self.fallback.path[s]].links)
                for lid in topo.paths[pid].links
            )
            if room > fit_room:
                fit_path, fit_room = pid, room
        out.append(Candidate("capacity-fitted", self._make(
            {"embb": fit_path}, {**matched, "embb": min(matched["embb"], fit_room / k)})))  # -inf room clips to the minimum
        # Background-aware: move eMBB to the allowed path with the most measured headroom.
        best_path, best_room = self.fallback.path["embb"], -float("inf")
        for pid in self.slices["embb"].allowed_paths:
            room = min(
                topo.links[lid].capacity_mbps - _unknown_full(obs.state.value(f"background_load_mbps.{lid}"))
                for lid in topo.paths[pid].links
            )
            if room > best_room:
                best_path, best_room = pid, room
        out.append(Candidate("least-loaded-embb", self._make({"embb": best_path}, matched)))
        # Naive: everything on the lowest-delay path.
        lowest = min(topo.paths, key=lambda p: sum(topo.links[l].prop_delay_ms for l in topo.paths[p].links))
        out.append(Candidate("shortest-delay", self._make({s: lowest for s in self.slices}, matched)))
        # Seeded random variations within A.
        rng = random.Random(f"{self.seed}:{obs.t}")
        for i in range(self.n_random):
            path = {s: rng.choice(self.slices[s].allowed_paths) for s in self.slices}
            budget = {s: rng.uniform(*self.slices[s].rate_budget_mbps) for s in self.slices}
            out.append(Candidate(f"random-{i}", self._make(path, budget)))
        if self.preference == "fitted-first":
            out.sort(key=lambda c: c.label != "capacity-fitted")  # stable: rest keeps its order
        return out


def _unknown_full(v: float) -> float:
    """Background load for a room computation: unknown counts as no room, never as idle."""
    return math.inf if v != v else v
