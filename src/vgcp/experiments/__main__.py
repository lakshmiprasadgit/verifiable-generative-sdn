"""CLI: python -m vgcp.experiments --scenarios experiments/scenarios/*.yaml --seeds 1-5

Writes, under --out:
  manifest.json                     code version, config hash, scenarios, seeds, command
  <scenario>/<mode>/seed-<k>/steps.jsonl   raw per-slot records (decision + ground truth)
  <scenario>/<mode>/seed-<k>/summary.json  per-trial metrics
  summary.json, summary.md          per (scenario, mode) aggregates over seeds
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
from pathlib import Path

import copy

from vgcp.config import build_config, load_config
from vgcp.experiments.runner import MODES, aggregate, dumps, run_trial, summarize
from vgcp.sim import load_scenario

ROOT = Path(__file__).resolve().parents[3]


def _seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _rel(path: str) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return Path(path).name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m vgcp.experiments")
    ap.add_argument("--config", default=str(ROOT / "configs"))
    ap.add_argument("--scenarios", nargs="+", required=True)
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES)
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--n-random", type=int, default=4)
    ap.add_argument("--backend", choices=("sim", "mininet"), default="sim",
                    help="sim: simulated ground truth (no root); mininet: emulated network (needs root)")
    ap.add_argument("--fallback-policy", choices=("static", "capacity_aware"),
                    help="override shield.fallback_policy from the configuration")
    ap.add_argument("--latency-safety-factor", type=float,
                    help="override shield.nominal_model.latency_safety_factor (calibration ablation)")
    ap.add_argument("--out", default=str(ROOT / "experiments" / "results" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    overrides = {}
    if args.fallback_policy:
        overrides["fallback_policy"] = args.fallback_policy
    if args.latency_safety_factor is not None:
        overrides["latency_safety_factor"] = args.latency_safety_factor
    if overrides:
        raw = copy.deepcopy(dict(cfg.raw))
        if "fallback_policy" in overrides:
            raw["shield"]["fallback_policy"] = overrides["fallback_policy"]
        if "latency_safety_factor" in overrides:
            raw["shield"]["nominal_model"]["latency_safety_factor"] = overrides["latency_safety_factor"]
        cfg = build_config(raw, source=f"{args.config} (overrides {overrides})")
    slices = {s.name for s in cfg.slices}
    scenarios = [load_scenario(p, slices, set(cfg.topology.links)) for p in args.scenarios]
    seeds = _seeds(args.seeds)
    make_backend = None
    if args.backend == "mininet":
        from vgcp.emu import MininetFabric, MininetNetwork

        MininetFabric()  # fails fast without root or tools, before any output is written

        def make_backend(c, sc, seed):
            return MininetNetwork(c, sc, seed, MininetFabric())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {
        # paths relative to the repository, so manifests carry no machine-specific prefix
        "command": [_rel(sys.executable), "-m", "vgcp.experiments", *(argv if argv is not None else sys.argv[1:])],
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        # dirty if any code, configuration or scenario differs from the commit, untracked files included
        "git_dirty": bool(_git("status", "--porcelain", "--", "src", "configs", "experiments/scenarios")),
        "python": platform.python_version(),
        "backend": "simulated" if args.backend == "sim" else "mininet (measured)",
        "config_hash": cfg.config_hash,
        "fallback_policy": cfg.shield.fallback_policy,
        "latency_safety_factor": cfg.nominal_model.latency_safety_factor,
        "config_overrides": overrides,
        "scenarios": {s.name: {"file": str(p), "digest": s.digest} for s, p in zip(scenarios, args.scenarios)},
        "modes": args.modes, "seeds": seeds, "n_random": args.n_random,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    table: dict[str, dict[str, dict]] = {}
    for sc in scenarios:
        for mode in args.modes:
            sums = []
            for seed in seeds:
                rows = run_trial(cfg, sc, mode, seed, args.n_random, make_backend)
                d = out / sc.name / mode / f"seed-{seed}"
                d.mkdir(parents=True)
                (d / "steps.jsonl").write_text("".join(dumps(r) + "\n" for r in rows))
                s = summarize(cfg, sc, rows)
                (d / "summary.json").write_text(dumps(s))
                sums.append(s)
            table.setdefault(sc.name, {})[mode] = aggregate(sums)
            print(f"{sc.name:28s} {mode:14s} done ({len(seeds)} seeds)", flush=True)
    (out / "summary.json").write_text(dumps(table))
    (out / "summary.md").write_text(render_markdown(table, manifest))
    print(f"results: {out}")
    return 0


COLUMNS = [
    ("any_violation_slots", "violation slots"),
    ("overload_slots", "overload slots"),
    ("reservation_violation_slots", "reservation-limit slots"),
    ("candidate_rejection_rate", "candidate rejection rate"),
    ("fallback_slots", "fallback slots"),
    ("uncertified_fallback_slots", "uncertified fallback"),
    ("shadow_rejected_applied_slots", "applied but shield-rejected"),
    ("max_link_util", "max link util"),
    ("recovery_slots", "recovery slots"),
    ("verify_time_ms_p95", "verify ms p95"),
]


def render_markdown(table: dict, manifest: dict) -> str:
    kind = ("Simulated backend (ground truth)" if manifest["backend"] == "simulated"
            else "Emulated Mininet backend (measured values, not ground truth; overload is not observable, "
                 "latency is the max of the slot's probes)")
    lines = [f"{kind}. Commit `{manifest['git_commit'][:7]}`"
             f"{' (dirty)' if manifest['git_dirty'] else ''}, seeds {manifest['seeds']}. "
             "Values are mean ± std over seeds.", ""]
    for sc, modes in table.items():
        lines += [f"### {sc}", "", "| metric | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
        for key, label in COLUMNS:
            cells = []
            for m in modes.values():
                v = m.get(key)
                cells.append("–" if not isinstance(v, dict) else f"{v['mean']:.3g} ± {v['std']:.2g}")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append("| eMBB throughput Mbit/s | " + " | ".join(
            "unavailable" if m["mean_throughput_mbps"]["embb"] is None
            else f"{m['mean_throughput_mbps']['embb']:.3g} ({m['mean_throughput_mbps_trials']['embb']}/{m['trials']} trials)"
            for m in modes.values()) + " |")
        lines.append("| recovered trials | " + " | ".join(f"{m['recovered_trials']}/{m['trials']}" for m in modes.values()) + " |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
