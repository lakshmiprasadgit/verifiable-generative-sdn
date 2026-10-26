"""Verification shield V : S x A x Phi -> {0, 1} (paper Eq 18, Assumption 2).

For a measured state s_t, measured demand d_t and candidate action a_t, the
shield runs explicit checks and accepts only if every check PASSES:

  action_valid            a_t in A (bounds, types, allowed paths)          Sec 2.1
  state_measurements      every state metric the checks read is present,
                          finite, within S's bounds and fresh               Sec 2.1
  demand_measurements     same for the demand metrics d_t                   Sec 2.1
  hard_constraints_now    c(s_t, a_t) <= 0                                  Eqs 16-17
  nominal_model_domain    every step of the projected trajectory (Eqs 12-13)
                          is inside the nominal model's validity domain     extension (D12)
  fallback_continuation   pi_0 outputs along the rollout are in A           Eq 13
  hard_constraints_rollout c(s-hat_{t+k}, a-hat_{t+k}) <= 0, k = 1..H
                          (stricter than Eq 17; configurable)
  intent:<name>           rho_phi(s_t, a_t) >= rho_min for each phi in Phi  Eqs 14, 17

Each check is PASS, FAIL, UNKNOWN, or NOT_APPLICABLE (only for a check that the
configuration disables, so a certificate never reports it as passed). UNKNOWN (missing/stale data, skipped
because a prerequisite failed, model out of domain, internal error) is never
treated as safe: the action is rejected.

What acceptance means: V = 1 implies a_t is in A_Phi(s_t) as defined by
Eq 17, where rho_phi is computed with *this* nominal model, demand forecast,
fallback policy and configured constraints. It is a statement about the model,
not a guarantee about the real network; see docs/milestone1_design.md.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from vgcp.action import ControlAction, action_fingerprint
from vgcp.config import Intent, ProjectConfig
from vgcp.constraints import ConstraintVector, HardConstraints
from vgcp.errors import ConfigError, is_finite_real, is_real, json_safe
from vgcp.models import (
    AnalyticNominalModel,
    CapacityAwareFallbackPolicy,
    UpperBoundConstantForecast,
    DemandForecast,
    FallbackPolicy,
    StaticFallbackPolicy,
    TransitionModel,
)
from vgcp.signals import ACTION_PREFIX, step_signals
from vgcp.state import Demand, MetricStatus, NetworkState, Observation, ObservationSchema
from vgcp.stl import Trace, evaluate, predicates, signal_offsets, signals


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"  # check disabled by configuration; never emitted otherwise


_ACCEPTABLE = (CheckStatus.PASS, CheckStatus.NOT_APPLICABLE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Certificate:
    """Record of one shield decision."""

    accepted: bool
    t: int
    checks: tuple[CheckResult, ...]
    robustness: dict[str, float | None]  # rho_phi(s_t, a_t) per intent (Eq 14)
    constraints_now: dict[str, float | None]  # c(s_t, a_t) (Eq 16)
    rho_min: dict[str, float]
    horizon_H: int
    nominal_model_in_domain: bool | None  # None if the rollout was not run
    config_hash: str
    # Binding to what was certified (audit M3). The action is immutable (ControlAction
    # freezes its fields); the inputs are identified by fingerprints.
    action: ControlAction | None = None
    action_fingerprint: str | None = None
    now_s: float | None = None
    state_fingerprint: str | None = None
    demand_fingerprint: str | None = None
    # "intent: signal" for each predicate the measured state s_t already violates
    # (audit H3). Informational: recovery-style intents can still be certified.
    measured_violations: tuple[str, ...] = ()

    def authorizes(self, action: Any) -> bool:
        """True only if this certificate accepted exactly ``action``; fails closed.

        Compares canonical action fingerprints. The input context (state, demand,
        now_s, config) is recorded but not checked here: whether a certificate may be
        used at a later state or slot is a closed-loop decision (Milestone 4).
        """
        if self.accepted is not True or self.action_fingerprint is None:
            return False
        return action_fingerprint(action) == self.action_fingerprint

    def check(self, name: str) -> CheckResult:
        for c in self.checks:
            if c.name == name:
                return c
        raise KeyError(name)

    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status not in _ACCEPTABLE]

    def to_dict(self) -> dict[str, Any]:
        return json_safe({
            "accepted": self.accepted,
            "t": self.t,
            "checks": [
                {"name": c.name, "status": c.status.value, "detail": c.detail, "data": c.data}
                for c in self.checks
            ],
            "robustness": self.robustness,
            "constraints_now": self.constraints_now,
            "rho_min": self.rho_min,
            "horizon_H": self.horizon_H,
            "nominal_model_in_domain": self.nominal_model_in_domain,
            "config_hash": self.config_hash,
            "action": self.action.to_dict() if self.action is not None else None,
            "action_fingerprint": self.action_fingerprint,
            "now_s": self.now_s,
            "state_fingerprint": self.state_fingerprint,
            "demand_fingerprint": self.demand_fingerprint,
            "measured_violations": list(self.measured_violations),
        })


def fallback_policy(config: ProjectConfig) -> FallbackPolicy:
    if config.shield.fallback_policy == "capacity_aware":
        return CapacityAwareFallbackPolicy(config.fallback_action, config.topology, config.slices,
                                           config.constraints.max_reserved_fraction,
                                           meter_overshoot=config.meter_overshoot)
    return StaticFallbackPolicy(config.fallback_action)


def observation_fingerprint(obs: Any) -> str | None:
    """SHA-256 identifying a measured state or demand exactly: type, slot, and every
    metric's key, value and timestamp (via repr, so floats are exact and 0 != 0.0).
    Independent of metric order. None if ``obs`` is not an Observation. Never raises."""
    try:
        if not isinstance(obs, Observation):
            return None
        items = sorted((str(k), repr(m.value), repr(m.timestamp_s)) for k, m in obs.metrics.items())
        return hashlib.sha256(repr((type(obs).__name__, obs.t, items)).encode()).hexdigest()
    except Exception:
        return None


@dataclass(frozen=True)
class Rollout:
    """Projected trajectory of paper Eqs 12-13: states and actions for k = 0..H."""

    states: tuple[NetworkState, ...]
    actions: tuple[ControlAction, ...]
    in_domain: tuple[bool, ...]  # one flag per predicted step
    notes: tuple[str, ...]
    # Non-empty if pi_0 returned an action outside A; the rollout stops at that step.
    invalid_fallback: tuple[str, ...] = ()


class VerificationShield:
    def __init__(
        self,
        config: ProjectConfig,
        model: TransitionModel,
        fallback: FallbackPolicy,
        forecast: DemandForecast,
        constraints: HardConstraints,
    ) -> None:
        self.cfg = config
        self.model = model
        self.fallback = fallback
        self.forecast = forecast
        self.constraints = constraints
        self.intents: tuple[Intent, ...] = config.intents
        # Audit M5: a placeholder output of the model must not be read over the rollout.
        unmodelled = model.unmodelled_state_keys()
        ahead = [
            f"intent '{it.name}' reads {sig} up to {k} step(s) ahead"
            for it in self.intents for sig, k in sorted(signal_offsets(it.formula).items())
            if k > 0 and sig in unmodelled
        ]
        if ahead:
            raise ConfigError(
                "intents read signals the nominal model does not predict: " + "; ".join(ahead)
                + ". Such signals can only be checked on the current measurement (no temporal operator)."
            )
        intent_state_keys = {
            sig for it in self.intents for sig in signals(it.formula)
            if not sig.startswith(ACTION_PREFIX)
        }
        self.required_state_keys = tuple(sorted(
            intent_state_keys | constraints.required_state_keys() | model.required_state_keys()
        ))
        self.required_demand_keys = tuple(sorted(
            forecast.required_demand_keys() | model.required_demand_keys()
        ))

    @classmethod
    def from_config(cls, config: ProjectConfig) -> "VerificationShield":
        names = [s.name for s in config.slices]
        return cls(
            config,
            AnalyticNominalModel(config.topology, names, config.nominal_model, config.meter_overshoot),
            fallback_policy(config),
            UpperBoundConstantForecast(config.demand_schema, config.shield.forecast_margin),
            HardConstraints(config.constraints, config.topology, config.slices, config.meter_overshoot),
        )

    # ---------------------------------------------------------------- public
    def verify(self, state: NetworkState, demand: Demand, action: Any, now_s: float) -> Certificate:
        checks: list[CheckResult] = []
        robustness: dict[str, float | None] = {}
        violations: list[str] = []
        c_now: dict[str, float | None] = {}
        in_domain: bool | None = None
        t = state.t if isinstance(state, NetworkState) else -1
        # Identify the certified action and inputs before any check reads them.
        bound_action = action if isinstance(action, ControlAction) else None
        bound_fp = action_fingerprint(action)
        state_fp, demand_fp = observation_fingerprint(state), observation_fingerprint(demand)
        try:
            bound_now = float(now_s) if is_real(now_s) else None
        except OverflowError:
            bound_now = None
        try:
            in_domain = self._run_checks(state, demand, action, now_s, checks, robustness, c_now, violations)
        except Exception as exc:  # an exception must never turn into acceptance
            checks.append(CheckResult("internal_error", CheckStatus.UNKNOWN, repr(exc)))
        accepted = bool(checks) and all(c.status in _ACCEPTABLE for c in checks)
        return Certificate(
            accepted=accepted, t=t, checks=tuple(checks), robustness=robustness,
            constraints_now=c_now, rho_min={it.name: it.rho_min for it in self.intents},
            horizon_H=self.cfg.horizon_H, nominal_model_in_domain=in_domain, config_hash=self.cfg.config_hash,
            action=bound_action, action_fingerprint=bound_fp,
            now_s=bound_now,
            state_fingerprint=state_fp, demand_fingerprint=demand_fp,
            measured_violations=tuple(dict.fromkeys(violations)),
        )

    def rollout(self, state: NetworkState, action: ControlAction, demand: Demand) -> Rollout:
        """Eqs 12-13: s-hat_t = s_t, a-hat_t = a_t, a-hat_{t+k} = pi_0(s-hat_{t+k}) for k >= 1."""
        H = self.cfg.horizon_H
        d_bar = self.forecast.forecast(demand, H)
        states, actions, flags, notes = [state], [action], [], []
        for k in range(H):
            pred = self.model.predict(states[k], actions[k], d_bar[k])
            states.append(pred.state)
            flags.append(pred.in_domain)
            notes += [f"k={k}: {n}" for n in pred.notes]
            next_action = self.fallback.act(pred.state)
            errors = self.cfg.action_schema.validate(next_action)
            if errors:
                bad = (f"k={k + 1}: " + "; ".join(errors),)
                return Rollout(tuple(states), tuple(actions), tuple(flags), tuple(notes), bad)
            actions.append(next_action)
        return Rollout(tuple(states), tuple(actions), tuple(flags), tuple(notes))

    # ---------------------------------------------------------------- checks
    def _run_checks(self, state, demand, action, now_s, checks, robustness, c_now, violations) -> bool | None:
        intent_names = [f"intent:{it.name}" for it in self.intents]
        later = ["hard_constraints_now", "nominal_model_domain", "fallback_continuation",
                 "hard_constraints_rollout", *intent_names]

        errors = self.cfg.action_schema.validate(action)
        checks.append(CheckResult(
            "action_valid", CheckStatus.FAIL if errors else CheckStatus.PASS,
            "; ".join(errors) or "action is in A",
        ))
        checks.append(self._measurements("state_measurements", NetworkState, state,
                                         self.cfg.state_schema, self.required_state_keys, now_s))
        checks.append(self._measurements("demand_measurements", Demand, demand,
                                         self.cfg.demand_schema, self.required_demand_keys, now_s))
        if any(c.status is not CheckStatus.PASS for c in checks):
            reason = "skipped: " + ", ".join(c.name for c in checks if c.status is not CheckStatus.PASS) + " did not pass"
            checks += [CheckResult(n, CheckStatus.UNKNOWN, reason) for n in later]
            return None

        vec = self.constraints.evaluate(state, action)
        c_now.update(vec.as_dict())
        checks.append(self._constraint_check("hard_constraints_now", [vec]))

        roll = self.rollout(state, action, demand)
        # Only an explicit True counts as in-domain (fail closed on anything else).
        in_domain = all(flag is True for flag in roll.in_domain)
        checks.append(CheckResult(
            "nominal_model_domain", CheckStatus.PASS if in_domain else CheckStatus.UNKNOWN,
            "every predicted step is inside the nominal model's validity domain" if in_domain
            else "nominal model outside its validity domain: " + "; ".join(roll.notes),
            {"steps_out_of_domain": [k for k, f in enumerate(roll.in_domain) if f is not True]},
        ))

        bad_fallback = list(roll.invalid_fallback)
        checks.append(CheckResult(
            "fallback_continuation", CheckStatus.FAIL if bad_fallback else CheckStatus.PASS,
            "; ".join(bad_fallback) or "pi_0 actions along the rollout are in A",
        ))

        if not self.cfg.shield.check_constraints_along_rollout:
            checks.append(CheckResult("hard_constraints_rollout", CheckStatus.NOT_APPLICABLE,
                                      "disabled in configuration (paper Eq 17 checks k = 0 only)"))
        elif bad_fallback:
            checks.append(CheckResult("hard_constraints_rollout", CheckStatus.UNKNOWN,
                                      "skipped: invalid fallback actions"))
        else:
            vecs = [self.constraints.evaluate(s, a) for s, a in zip(roll.states[1:], roll.actions[1:])]
            checks.append(self._constraint_check("hard_constraints_rollout", vecs))

        if not in_domain or bad_fallback:
            reason = "skipped: projected trajectory not trustworthy (model domain or fallback)"
            checks += [CheckResult(n, CheckStatus.UNKNOWN, reason) for n in intent_names]
            for it in self.intents:
                robustness[it.name] = None
            return in_domain

        trace = Trace.from_steps([
            step_signals(self.cfg.state_schema, self.cfg.action_schema, s, a)
            for s, a in zip(roll.states, roll.actions)
        ])
        for it in self.intents:
            for p in predicates(it.formula):
                x = trace.value(p.signal, 0)  # the measured state s_t (and a_t)
                if x == x and p.value(x) < 0:  # x == x excludes NaN
                    violations.append(f"{it.name}: {p.signal}")
            res = evaluate(it.formula, trace, 0)
            robustness[it.name] = res.robustness
            if res.robustness is None:
                status, detail = CheckStatus.UNKNOWN, "robustness unknown (missing samples)"
            elif res.robustness >= it.rho_min:
                status, detail = CheckStatus.PASS, f"rho={res.robustness:.6g} >= rho_min={it.rho_min:g}"
            else:
                status, detail = CheckStatus.FAIL, f"rho={res.robustness:.6g} < rho_min={it.rho_min:g}"
            checks.append(CheckResult(f"intent:{it.name}", status, detail,
                                      {"robustness": res.robustness, "verdict": res.verdict.value}))
        return in_domain

    def _measurements(self, name: str, cls: type, obs: Any, schema: ObservationSchema,
                      keys: Sequence[str], now_s: float) -> CheckResult:
        if not isinstance(obs, cls):
            return CheckResult(name, CheckStatus.UNKNOWN, f"expected {cls.__name__}, got {type(obs).__name__}")
        if not is_finite_real(now_s):
            return CheckResult(name, CheckStatus.UNKNOWN, f"invalid current time {now_s!r}")
        statuses = schema.check(obs, keys, now_s=now_s, max_age_s=self.cfg.shield.max_staleness_s)
        bad = {k: s.value for k, s in statuses.items() if s is not MetricStatus.OK}
        if bad:
            return CheckResult(name, CheckStatus.UNKNOWN, f"{len(bad)} metric(s) not usable", {"problems": bad})
        return CheckResult(name, CheckStatus.PASS, f"{len(keys)} required metrics present and fresh")

    @staticmethod
    def _constraint_check(name: str, vecs: Sequence[ConstraintVector]) -> CheckResult:
        violated = [f"{v.name}={v.value:g} ({v.detail})" for vec in vecs for v in vec.violated()]
        unknown = [f"{v.name} ({v.detail})" for vec in vecs for v in vec.unknown()]
        if violated:
            return CheckResult(name, CheckStatus.FAIL, "; ".join(violated[:10]))
        if unknown:
            return CheckResult(name, CheckStatus.UNKNOWN, "; ".join(unknown[:10]))
        n = sum(len(vec.values) for vec in vecs)
        return CheckResult(name, CheckStatus.PASS, f"all {n} constraint components <= 0")
