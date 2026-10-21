"""Closed-loop experiment runner (simulated backend).

One trial = one scenario x one controller mode x one seed. Per slot t it records the
controller's StepRecord and the ground truth of slot t+1, i.e. the network condition
produced by the action chosen at t. Metrics are computed from that ground truth, not
from the shield's predictions.

Controller modes (same candidate generator and preference order in all of them):
  shielded       first certified candidate, else pi_0
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
from vgcp.shield import VerificationShield, fallback_policy
from vgcp.sim import Scenario, SimulatedNetwork
from vgcp.stl import predicates

MODES = ("shielded", "unshielded", "unshielded-fitted", "fallback-only")
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


def build_controller(cfg: ProjectConfig, mode: str, backend, seed: int, n_random: int):
    shield = VerificationShield.from_config(cfg)
    gen = HeuristicCandidateGenerator(cfg, n_random=n_random, seed=seed,
                                      preference="fitted-first" if mode == "unshielded-fitted" else "greedy")
    if mode == "shielded":
        return ShieldedController(cfg, shield, gen, CertifiedApplier(backend, fallback_policy(cfg), cfg.shield.max_staleness_s))
    if mode in ("unshielded", "unshielded-fitted"):
        return UnshieldedController(cfg, gen, UncheckedApplier(backend), shadow_shield=shield)
    if mode == "fallback-only":
        return FallbackOnlyController(cfg, shield, CertifiedApplier(backend, fallback_policy(cfg), cfg.shield.max_staleness_s))
    raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")


def run_trial(cfg: ProjectConfig, scenario: Scenario, mode: str, seed: int, n_random: int = 4) -> list[dict[str, Any]]:
    backend = SimulatedNetwork(cfg, scenario, seed)
    controller = build_controller(cfg, mode, backend, seed, n_random)
    rows = []
    for _ in range(scenario.slots):
        obs = backend.observe()
        rec = controller.step(obs)
        backend.advance()
        rows.append({"step": rec.to_dict(), "truth_next": backend.ground_truth()})
    return rows


def _violations(row: dict[str, Any], cfg: ProjectConfig, bounds: dict[str, float]) -> dict[str, bool]:
    truth = row["truth_next"]
    overload = any(u > 1.0 + 1e-9 for u in truth["link_util"].values())
    reserve = any(u > cfg.constraints.max_reserved_fraction + 1e-9 for u in truth["link_util"].values()) \
        if cfg.constraints.link_capacity else False
    intent = {s: truth["latency_p99_ms"][s] > c for s, c in bounds.items()}
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
    out: dict[str, Any] = {
        "slots": n,
        "overload_slots": sum(v["overload"] for v in viol),
        "reservation_violation_slots": sum(v["reservation"] for v in viol),
        "any_violation_slots": sum(v["any"] for v in viol),
        **{f"latency_violation_slots.{s}": sum(v[f"latency.{s}"] for v in viol) for s in bounds},
        "mean_loss": {s: statistics.fmean(r["truth_next"]["loss"][s] for r in rows) for s in cfg.action_schema.slice_names},
        "max_loss": {s: max(r["truth_next"]["loss"][s] for r in rows) for s in cfg.action_schema.slice_names},
        "mean_throughput_mbps": {s: statistics.fmean(r["truth_next"]["throughput_mbps"][s] for r in rows)
                                 for s in cfg.action_schema.slice_names},
        "max_link_util": max(max(r["truth_next"]["link_util"].values()) for r in rows),
        "candidate_rejection_rate": (verified - certified) / verified if verified else None,
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
    for nested in ("mean_loss", "mean_throughput_mbps"):
        out[nested] = {sl: statistics.fmean(s[nested][sl] for s in summaries) for sl in summaries[0][nested]}
    return out


def dumps(obj: Any) -> str:
    return json.dumps(json_safe(obj), sort_keys=True)
