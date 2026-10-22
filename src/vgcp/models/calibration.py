"""Calibration of the nominal model's latency map (Milestone 3).

T-hat predicts a slice's p99 latency as  k * L0(load, path, background), where L0 is
the analytic per-hop sum (models/nominal.py) and k = latency_safety_factor. Whether
k makes T-hat conservative is an empirical question, answered here from recorded
runs:

  for every recorded slot (one row of steps.jsonl, field truth_next):
      L0_s   = T-hat with k = 1, fed the slot's own installed action, offered load,
               background and the scenario's device counts
      L_s    = the latency recorded for that slot (simulator ground truth, or the
               Mininet measurement)
      r_s    = L_s / L0_s
  proposed k = the q-quantile of r over the training slots (q = 0.99 by default):
               the smallest k with k * L0 >= L on a fraction q of the training slots.

Coverage of a factor = the fraction of slots with k * L0 >= L. A proposal is only
evidence if its coverage holds on runs it was not fitted on (held-out seeds and
scenarios), which is why calibrate() and coverage() are separate.

Limits, stated in every report:
* this calibrates the latency map at observed operating points only; it says
  nothing about loads never seen;
* it calibrates k only; packet sizes and processing delay stay as configured;
* data recorded with faulty telemetry (Mininet campaign 2026-10-22) calibrates
  the faults too.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from vgcp.action import ControlAction
from vgcp.config import ProjectConfig
from vgcp.models.nominal import AnalyticNominalModel
from vgcp.state import Demand, Measurement, NetworkState


@dataclass(frozen=True)
class LatencyPoint:
    run: str  # e.g. "s1_steady/shielded/seed-1"
    t: int
    slice: str
    observed_ms: float
    base_ms: float  # T-hat latency with safety factor 1

    @property
    def ratio(self) -> float:
        return self.observed_ms / self.base_ms


def _num(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return math.nan
    return f


def base_model(cfg: ProjectConfig) -> AnalyticNominalModel:
    params = dataclasses.replace(cfg.nominal_model, latency_safety_factor=1.0)
    return AnalyticNominalModel(cfg.topology, cfg.action_schema.slice_names, params)


def points_from_rows(cfg: ProjectConfig, rows: Iterable[dict[str, Any]], devices: dict[str, float],
                     run: str = "") -> list[LatencyPoint]:
    """Pairs (observed, base prediction) for every slot and slice with usable values."""
    model, topo = base_model(cfg), cfg.topology
    out = []
    for row in rows:
        tr = row["truth_next"]
        bg = {l: _num(tr["background_mbps"].get(l)) for l in topo.links}
        offered = {s: _num(tr["offered_mbps"].get(s)) for s in cfg.action_schema.slice_names}
        if any(math.isnan(v) for v in list(bg.values()) + list(offered.values())):
            continue  # an unknown input gives no calibration point (never filled with 0)
        state = NetworkState(tr["t"], {
            **{f"background_load_mbps.{l}": Measurement(v, None) for l, v in bg.items()},
            **{f"flow_table_occupancy.{sw}": Measurement(0.0, None) for sw in topo.switches},
        })
        demand = Demand(tr["t"], {
            **{f"offered_load_mbps.{s}": Measurement(v, None) for s, v in offered.items()},
            **{f"active_devices.{s}": Measurement(float(devices[s]), None) for s in offered},
        })
        pred = model.predict(state, ControlAction.from_dict(tr["installed"]), demand)
        for s in cfg.action_schema.slice_names:
            obs, base = _num(tr["latency_p99_ms"].get(s)), pred.state.value(f"latency_p99_ms.{s}")
            if math.isfinite(obs) and math.isfinite(base) and base > 0:
                out.append(LatencyPoint(run, tr["t"], s, obs, base))
    return out


def points_from_campaign(cfg: ProjectConfig, campaign: Path, scenario_devices: dict[str, dict[str, float]],
                         select=lambda run: True) -> list[LatencyPoint]:
    """All points of a campaign directory (<scenario>/<mode>/seed-<k>/steps.jsonl)."""
    pts = []
    for f in sorted(Path(campaign).glob("*/*/seed-*/steps.jsonl")):
        run = str(f.parent.relative_to(campaign))
        sc = run.split("/")[0]
        if sc not in scenario_devices or not select(run):
            continue
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        pts += points_from_rows(cfg, rows, scenario_devices[sc], run)
    return pts


def quantile(values: list[float], q: float) -> float:
    """Upper empirical quantile (nearest rank): the smallest v with F(v) >= q."""
    if not values:
        return math.nan
    v = sorted(values)
    return v[min(len(v) - 1, max(0, math.ceil(q * len(v)) - 1))]


def coverage(points: list[LatencyPoint], k: float) -> float | None:
    """Fraction of points with k * base >= observed (None if there are no points)."""
    if not points:
        return None
    return sum(k * p.base_ms >= p.observed_ms for p in points) / len(points)


def calibrate(points: list[LatencyPoint], q: float = 0.99) -> dict[str, Any]:
    if not 0.0 < q <= 1.0:
        raise ValueError("q must be in (0, 1]")
    ratios = [p.ratio for p in points]
    per_slice = {}
    for s in sorted({p.slice for p in points}):
        r = [p.ratio for p in points if p.slice == s]
        per_slice[s] = {"n": len(r), "median": quantile(r, 0.5), "p90": quantile(r, 0.9),
                        "p99": quantile(r, 0.99), "max": max(r)}
    k = quantile(ratios, q)
    return {"quantile": q, "n_points": len(points), "proposed_latency_safety_factor": k,
            "train_coverage": coverage(points, k), "ratio_by_slice": per_slice}
