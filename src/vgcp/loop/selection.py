"""Selection rule sigma of paper Eq 42 with the utility of Eq 27 (Milestone 4).

    sigma(s_t) = argmax_{a in A_Phi(s_t)}  sum_{k=0..H} gamma^k U(s^_{t+k}, a^_{t+k}, Phi)       (42)
    U(s, a, Phi) = a1 Q(s, a) + a2 E(s, a) + a3 min_phi rho_phi(s, a) - a4 C(s, a)          (27)

with s^_t = s_t, a^_t = a, a^_{t+k} = pi_0(s^_{t+k}) for k >= 1 - exactly the projected
rollout the shield already builds for Eq 14 (VerificationShield.rollout). Stage 1
replaces the world model q_psi by the deterministic nominal model T-hat, so the
expectation in Eq 42 is a single rollout.

Stage 1 instantiation of the terms (extension D20; weights and scales in
configs/shield.yaml, illustrative, not tuned):
  Q  quality of service   sum of slice throughput in s (Mbit/s) / qos_scale
  E  energy efficiency    - energy_w in s / energy_scale  (less power is better; throughput
                          is already rewarded by Q)
  rho                     min over intents and their predicates of the normalized
                          predicate value p(s, a) at this step (Eq 8, D18)
  C  operational cost     sum of reserved rate budgets of a (Mbit/s) / cost_scale
A term whose input is missing contributes 0 at that step. This can only happen at
k = 0, where s is the measured state, the same for every candidate; certified
candidates have in-domain predictions at k >= 1.

Only certified candidates are ranked, so selection never weakens verification; ties
keep the generator's order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from vgcp.action import ControlAction
from vgcp.config import ProjectConfig
from vgcp.errors import ConfigError, is_finite_real
from vgcp.signals import step_signals
from vgcp.state import Demand, NetworkState
from vgcp.stl import predicates

DEFAULTS = {
    "discount_gamma": 0.9,
    "weights": {"qos": 1.0, "energy": 0.1, "robustness": 1.0, "cost": 0.5},
    "scales": {"qos_mbps": 100.0, "energy_w": 10.0, "cost_mbps": 100.0},
}


@dataclass(frozen=True)
class SelectionSettings:
    discount_gamma: float
    weights: Mapping[str, float]
    scales: Mapping[str, float]

    @classmethod
    def from_config(cls, cfg: ProjectConfig) -> "SelectionSettings":
        raw = (cfg.raw.get("shield") or {}).get("selection") or {}
        gamma = raw.get("discount_gamma", DEFAULTS["discount_gamma"])
        if not (is_finite_real(gamma) and 0.0 < gamma <= 1.0):
            raise ConfigError(f"shield.selection.discount_gamma: {gamma!r} not in (0, 1]")

        def block(name: str, positive: bool) -> dict[str, float]:
            given = raw.get(name) or {}
            unknown = set(given) - set(DEFAULTS[name])
            if unknown:
                raise ConfigError(f"shield.selection.{name}: unknown keys {sorted(unknown)}")
            out = {**DEFAULTS[name], **given}
            for k, v in out.items():
                if not (is_finite_real(v) and (v > 0 if positive else v >= 0)):
                    raise ConfigError(f"shield.selection.{name}.{k}: invalid value {v!r}")
            return {k: float(v) for k, v in out.items()}

        return cls(float(gamma), block("weights", positive=False), block("scales", positive=True))


def _zero_if_nan(v: float) -> float:
    return 0.0 if v != v else v


class UtilityModel:
    def __init__(self, cfg: ProjectConfig, settings: SelectionSettings | None = None) -> None:
        self.cfg = cfg
        self.settings = settings or SelectionSettings.from_config(cfg)
        self.slices = cfg.action_schema.slice_names
        self.preds = [p for it in cfg.intents for p in predicates(it.formula)]

    def terms(self, state: NetworkState, action: ControlAction) -> dict[str, float]:
        """Q, E, rho, C of Eq 27 for one (state, action) pair."""
        sc = self.settings.scales
        q = sum(_zero_if_nan(state.value(f"throughput_mbps.{s}")) for s in self.slices) / sc["qos_mbps"]
        e = -_zero_if_nan(state.value("energy_w")) / sc["energy_w"]
        if self.preds:
            sig = step_signals(self.cfg.state_schema, self.cfg.action_schema, state, action)
            vals = [p.value(sig[p.signal]) for p in self.preds if sig.get(p.signal, math.nan) == sig.get(p.signal)]
            rho = min(vals) if vals else 0.0
        else:
            rho = 0.0
        c = sum(float(action.rate_budget_mbps[s]) for s in self.slices) / sc["cost_mbps"]
        return {"qos": q, "energy": e, "robustness": rho, "cost": c}

    def utility(self, state: NetworkState, action: ControlAction) -> float:
        w, t = self.settings.weights, self.terms(state, action)
        return w["qos"] * t["qos"] + w["energy"] * t["energy"] + w["robustness"] * t["robustness"] - w["cost"] * t["cost"]

    def predicted_return(self, shield, state: NetworkState, demand: Demand, action: ControlAction) -> float:
        """Eq 42's objective for one candidate, over the shield's own projected rollout."""
        roll = shield.rollout(state, action, demand)
        g = self.settings.discount_gamma
        return sum(g ** k * self.utility(s, a) for k, (s, a) in enumerate(zip(roll.states, roll.actions)))


def select_max_utility(model: UtilityModel, shield, obs, certified: list[tuple[Any, Any]]):
    """certified: [(candidate, certificate)] in the generator's order. Returns
    ((candidate, certificate), {label: predicted return})."""
    scores = {cand.label: model.predicted_return(shield, obs.state, obs.demand, cand.action)
              for cand, _ in certified}
    best = max(certified, key=lambda cc: scores[cc[0].label])  # max() keeps the first of equal scores
    return best, scores
