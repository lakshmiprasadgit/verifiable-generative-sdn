"""Closed-loop experiment runner (simulated backend).

One trial = one scenario x one controller mode x one seed. Per slot t it records the
controller's StepRecord and the ground truth of slot t+1, i.e. the network condition
produced by the action chosen at t. Metrics are computed from that ground truth, not
from the shield's predictions.

Controller modes (same candidate generator and preference order in all of them):
  shielded       first certified candidate, else pi_0
  shielded-utility  the certified candidate with the highest predicted return (Eq 42),
                 else pi_0
  unshielded     first candidate (greedy preference), unverified; a shadow shield
                 records what it would have decided
  unshielded-fitted  same, but the capacity-fitted heuristic is preferred first -
                 a stronger conventional baseline, so the shield is not compared
                 only against a greedy straw man
  fallback-only  always pi_0
"""

from __future__ import annotations

import json
import math
import statistics
from typing import Any

from vgcp.config import ProjectConfig
from vgcp.errors import json_safe
from vgcp.loop import (
    CertifiedApplier,
    FallbackOnlyController,
    HeuristicCandidateGenerator,
    ShieldedController,
    UncheckedApplier,
    UnshieldedController,
)
from vgcp.loop.selection import UtilityModel
from vgcp.shield import VerificationShield, fallback_policy
from vgcp.sim import Scenario, SimulatedNetwork
from vgcp.stl import predicates

MODES = ("shielded", "shielded-utility", "unshielded", "unshielded-fitted", "fallback-only")
RECOVERY_RUN = 3  # consecutive violation-free slots that count as recovered


def latency_thresholds(cfg: ProjectConfig) -> dict[str, float]:
    """Per-slice latency bound taken from the active intents (latency_p99_ms.<slice> <= c)."""
    out: dict[str, float] = {}
    for it in cfg.intents:
        for p in predicates(it.formula):
            fam, _, sl = p.signal.partition(".")
            if fam == "latency_p99_ms" and p.op == "<=":
                out[sl] = min(out.get(sl, math.inf), p.threshold)
    return out


def build_controller(cfg: ProjectConfig, mode: str, backend, seed: int, n_random: int,
                     wrap_shield=None, wrap_generator=None):
    """wrap_shield / wrap_generator (optional) receive the real shield / generator and
    return a pass-through wrapper, e.g. to record certificates for the dashboard."""
    shield = VerificationShield.from_config(cfg)
    gen = HeuristicCandidateGenerator(cfg, n_random=n_random, seed=seed,
                                      preference="fitted-first" if mode == "unshielded-fitted" else "greedy")
    if wrap_shield is not None:
        shield = wrap_shield(shield)
    if wrap_generator is not None:
        gen = wrap_generator(gen)
    if mode == "shielded":
        return ShieldedController(cfg, shield, gen, CertifiedApplier(backend, fallback_policy(cfg), cfg.shield.max_staleness_s))
    if mode == "shielded-utility":
        return ShieldedController(cfg, shield, gen, CertifiedApplier(backend, fallback_policy(cfg), cfg.shield.max_staleness_s),
                                  utility=UtilityModel(cfg), mode=mode)
    if mode in ("unshielded", "unshielded-fitted"):
        return UnshieldedController(cfg, gen, UncheckedApplier(backend), shadow_shield=shield)
    if mode == "fallback-only":
        return FallbackOnlyController(cfg, shield, CertifiedApplier(backend, fallback_policy(cfg), cfg.shield.max_staleness_s))
    raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")


def run_trial(cfg: ProjectConfig, scenario: Scenario, mode: str, seed: int, n_random: int = 4,
              make_backend=None) -> list[dict[str, Any]]:
    """make_backend(cfg, scenario, seed) -> NetworkBackend; default: the simulator.
    For an emulated network, 'truth_next' holds measurements, not ground truth."""
    backend = (make_backend or SimulatedNetwork)(cfg, scenario, seed)
    try:
        controller = build_controller(cfg, mode, backend, seed, n_random)
        rows = []
        for _ in range(scenario.slots):
            obs = backend.observe()
            rec = controller.step(obs)
            backend.advance()
            rows.append({"step": rec.to_dict(), "truth_next": backend.ground_truth()})
        return rows
    finally:
        close = getattr(backend, "close", None)
        if close is not None:
            close()


def _num(v: Any) -> float:
    """A recorded value as a float; missing (None) or non-numeric -> NaN (never 0)."""
    if v is None or isinstance(v, bool):
        return math.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def _measured(row: dict[str, Any]) -> bool:
    return row["truth_next"].get("source") == "measured"


def _violations(row: dict[str, Any], cfg: ProjectConfig, bounds: dict[str, float]) -> dict[str, bool]:
    truth = row["truth_next"]
    util = [_num(u) for u in truth["link_util"].values()]
    # A measured (emulated) link rate is post-shaping and cannot exceed capacity, so
    # overload is not observable there; it is never counted as "no overload".
    overload = False if _measured(row) else any(u > 1.0 + 1e-9 for u in util)
    reserve = any(u > cfg.constraints.max_reserved_fraction + 1e-9 for u in util) \
        if cfg.constraints.link_capacity else False
    intent = {s: _num(truth["latency_p99_ms"][s]) > c for s, c in bounds.items()}  # unknown (NaN) -> not counted here
    return {"overload": overload, "reservation": reserve, **{f"latency.{s}": v for s, v in intent.items()},
            "any": overload or any(intent.values())}


def _pct(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    v = sorted(values)
    return v[min(len(v) - 1, int(math.ceil(q * len(v))) - 1)]


def summarize(cfg: ProjectConfig, scenario: Scenario, rows: list[dict[str, Any]]) -> dict[str, Any]:
    bounds = latency_thresholds(cfg)
    viol = [_violations(r, cfg, bounds) for r in rows]
    steps = [r["step"] for r in rows]
    n = len(rows)
    verified = sum(s["n_verified"] for s in steps)
    certified = sum(s["n_certified"] for s in steps)
    slices = cfg.action_schema.slice_names
    observable = not any(_measured(r) for r in rows)

    def series(fam: str, s: str) -> list[float]:
        vals = [_num(r["truth_next"][fam][s]) for r in rows]
        return [v for v in vals if not math.isnan(v)]

    out: dict[str, Any] = {
        "slots": n,
        "overload_observable": observable,
        "overload_slots": sum(v["overload"] for v in viol) if observable else None,
        "reservation_violation_slots": sum(v["reservation"] for v in viol),
        "any_violation_slots": sum(v["any"] for v in viol),
        **{f"latency_violation_slots.{s}": sum(v[f"latency.{s}"] for v in viol) for s in bounds},
        **{f"latency_unknown_slots.{s}": n - len(series("latency_p99_ms", s)) for s in bounds},
        # means and maxima over the slots that have a value; how many is reported, and a
        # missing slot is never averaged in as 0
        "mean_loss": {s: _mean(series("loss", s)) for s in slices},
        "max_loss": {s: max(series("loss", s), default=None) for s in slices},
        "mean_throughput_mbps": {s: _mean(series("throughput_mbps", s)) for s in slices},
        "valid_slots": {fam: {s: len(series(fam, s)) for s in slices} for fam in ("loss", "throughput_mbps")},
        "max_link_util": max((u for r in rows for u in map(_num, r["truth_next"]["link_util"].values())
                              if not math.isnan(u)), default=None),
        "candidate_rejection_rate": (verified - certified) / verified if verified else None,
        # bandwidth reserved by the applied actions (Eq 27's cost term); outcome metrics
        # cannot show it when every budget exceeds demand
        "mean_reserved_mbps": statistics.fmean(sum(s["action"]["rate_budget_mbps"].values()) for s in steps),
        "fallback_slots": sum(s["kind"] == "fallback" for s in steps),
        "uncertified_fallback_slots": sum(s["fallback_certified"] is False for s in steps),
        "shadow_rejected_applied_slots": sum(s["shield_would_accept"] is False for s in steps),
        "apply_failures": sum(not s["applied"] for s in steps),
        "verify_time_ms_mean": 1e3 * statistics.fmean(s["verify_time_s"] for s in steps),
        "verify_time_ms_p95": 1e3 * _pct([s["verify_time_s"] for s in steps], 0.95),
        "decision_time_ms_p95": 1e3 * _pct([s["decision_time_s"] for s in steps], 0.95),
        "rejection_reasons": _merge(s["rejection_reasons"] for s in steps),
    }
    start = scenario.disturbance_start()
    out["disturbance_start"] = start
    out["recovery_slots"] = _recovery(viol, start)
    return out


def _mean(vals: list[float]) -> float | None:
    return statistics.fmean(vals) if vals else None


def _merge(dicts) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return dict(sorted(out.items()))


def _recovery(viol: list[dict[str, bool]], start: int | None) -> int | None:
    """Slots from the disturbance start until RECOVERY_RUN consecutive violation-free slots."""
    if start is None:
        return None
    for r in range(start, len(viol) - RECOVERY_RUN + 1):
        if not any(v["any"] for v in viol[r:r + RECOVERY_RUN]):
            return r - start
    return None


def aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean and sample std over seeds for the scalar metrics."""
    out: dict[str, Any] = {"trials": len(summaries)}
    keys = [k for k, v in summaries[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for k in keys:
        vals = [s[k] for s in summaries if isinstance(s.get(k), (int, float))]
        vals = [v for v in vals if not (isinstance(v, float) and math.isnan(v))]
        if vals:
            out[k] = {"mean": statistics.fmean(vals), "std": statistics.stdev(vals) if len(vals) > 1 else 0.0}
    rec = [s["recovery_slots"] for s in summaries]
    out["recovered_trials"] = sum(r is not None for r in rec)
    for nested in ("mean_loss", "mean_throughput_mbps"):  # over the trials that have a value
        out[nested] = {sl: _mean([v for s in summaries if (v := _num(s[nested][sl])) == v])
                       for sl in summaries[0][nested]}
        out[nested + "_trials"] = {sl: sum(_num(s[nested][sl]) == _num(s[nested][sl]) for s in summaries)
                                   for sl in summaries[0][nested]}
    return out


def dumps(obj: Any) -> str:
    return json.dumps(json_safe(obj), sort_keys=True)
