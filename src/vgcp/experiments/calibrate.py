"""CLI: calibrate the nominal model's latency safety factor from recorded runs.

  python -m vgcp.experiments.calibrate --campaign DIR [--test-campaign DIR ...]
         [--train-seeds 1-5] [--train-scenarios s1_steady,...] [--quantile 0.99] --out DIR

Fits k on the training runs (see vgcp.models.calibration) and reports its coverage
on every test campaign, next to the coverage of the configured k. Writes
calibration.json and calibration.md; never edits configs/ (adopting a factor is a
decision, recorded in docs/DECISIONS.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from vgcp.config import load_config
from vgcp.experiments.__main__ import ROOT, _git, _seeds
from vgcp.models.calibration import calibrate, coverage, points_from_campaign
from vgcp.sim import load_scenario


def _devices(cfg, campaign: Path) -> dict[str, dict[str, float]]:
    man = json.loads((campaign / "manifest.json").read_text())
    out = {}
    for name, info in man["scenarios"].items():
        path = Path(info["file"])
        sc = load_scenario(path if path.is_absolute() else ROOT / path, {s.name for s in cfg.slices},
                           set(cfg.topology.links))
        out[name] = dict(sc.devices)
    return out


def _seed_of(run: str) -> int:
    return int(run.rsplit("seed-", 1)[1])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m vgcp.experiments.calibrate")
    ap.add_argument("--config", default=str(ROOT / "configs"))
    ap.add_argument("--campaign", required=True, help="training campaign directory")
    ap.add_argument("--train-seeds", default=None, help="e.g. 1-5 (default: all)")
    ap.add_argument("--train-scenarios", default=None, help="comma-separated (default: all)")
    ap.add_argument("--test-campaign", nargs="*", default=[], help="held-out campaign directories")
    ap.add_argument("--quantile", type=float, default=0.99)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    camp = Path(args.campaign)
    seeds = set(_seeds(args.train_seeds)) if args.train_seeds else None
    scen = set(args.train_scenarios.split(",")) if args.train_scenarios else None

    def train(run: str) -> bool:
        return (seeds is None or _seed_of(run) in seeds) and (scen is None or run.split("/")[0] in scen)

    pts = points_from_campaign(cfg, camp, _devices(cfg, camp), train)
    if not pts:
        raise SystemExit("no usable calibration points in the training runs")
    fit = calibrate(pts, args.quantile)
    k_new, k_cfg = fit["proposed_latency_safety_factor"], cfg.nominal_model.latency_safety_factor
    fit["configured_latency_safety_factor"] = k_cfg
    fit["train_coverage_configured"] = coverage(pts, k_cfg)
    tests = {}
    for tc in [camp, *map(Path, args.test_campaign)]:
        heldout = (lambda run: not train(run)) if tc == camp else (lambda run: True)
        tp = points_from_campaign(cfg, tc, _devices(cfg, tc), heldout)
        by_sc: dict[str, list] = {}
        for p in tp:
            by_sc.setdefault(p.run.split("/")[0], []).append(p)
        tests[str(tc)] = {
            "backend": json.loads((tc / "manifest.json").read_text()).get("backend"),
            "n_points": len(tp), "coverage_proposed": coverage(tp, k_new), "coverage_configured": coverage(tp, k_cfg),
            "by_scenario": {s: {"n": len(v), "coverage_proposed": coverage(v, k_new),
                                "coverage_configured": coverage(v, k_cfg)} for s, v in sorted(by_sc.items())},
        }
    report = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "git_commit": _git("rev-parse", "HEAD"),
              "config_hash": cfg.config_hash, "training": {"campaign": str(camp), "seeds": sorted(seeds) if seeds else "all",
                                                         "scenarios": sorted(scen) if scen else "all"},
              "fit": fit, "held_out": tests}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "calibration.json").write_text(json.dumps(report, indent=1))
    (out / "calibration.md").write_text(render(report))
    print(render(report))
    return 0


def _pct(v) -> str:
    return "–" if v is None else f"{100 * v:.1f} %"


def render(r: dict) -> str:
    f = r["fit"]
    lines = [
        "Calibration of the nominal model's latency safety factor k (T-hat latency = k * analytic sum).",
        "",
        f"Training: {r['training']['campaign']} (seeds {r['training']['seeds']}, scenarios {r['training']['scenarios']}), "
        f"{f['n_points']} slot-slice points, commit `{r['git_commit'][:7]}`.",
        "",
        f"* configured k = {f['configured_latency_safety_factor']:g}: covers {_pct(f['train_coverage_configured'])} of training points",
        f"* proposed k = {f['proposed_latency_safety_factor']:.3f} (q = {f['quantile']}): covers {_pct(f['train_coverage'])}",
        "",
        "| slice | n | ratio median | p90 | p99 | max |", "|---|---|---|---|---|---|",
    ]
    for s, v in f["ratio_by_slice"].items():
        lines.append(f"| {s} | {v['n']} | {v['median']:.3f} | {v['p90']:.3f} | {v['p99']:.3f} | {v['max']:.3f} |")
    lines += ["", "ratio = recorded latency / analytic latency with k = 1.", "", "Held-out coverage (fraction of points with k * analytic >= recorded):", "",
              "| campaign | scenario | n | proposed k | configured k |", "|---|---|---|---|---|"]
    for c, t in r["held_out"].items():
        lines.append(f"| {c} ({t['backend']}) | all | {t['n_points']} | {_pct(t['coverage_proposed'])} | {_pct(t['coverage_configured'])} |")
        for s, v in t["by_scenario"].items():
            lines.append(f"| | {s} | {v['n']} | {_pct(v['coverage_proposed'])} | {_pct(v['coverage_configured'])} |")
    lines += ["", "Limits: operating points outside the recorded ones are not covered; only k is fitted; "
              "Mininet data inherits its telemetry errors; coverage is not a safety guarantee."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
