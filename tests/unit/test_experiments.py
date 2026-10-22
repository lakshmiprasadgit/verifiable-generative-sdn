"""Experiment runner: trials, metrics, reproducibility, CLI outputs."""

import json
from pathlib import Path

import pytest

from factories import CONFIG_DIR
from test_sim import BASE, scenario
from vgcp.experiments.__main__ import main
from vgcp.experiments.runner import MODES, aggregate, latency_thresholds, run_trial, summarize

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "experiments" / "scenarios"


def test_latency_thresholds_come_from_intents(cfg):
    assert latency_thresholds(cfg) == {"urllc": 1.0, "embb": 40.0, "mmtc": 20.0}


@pytest.mark.parametrize("mode", MODES)
def test_trial_runs_and_metrics_are_consistent(cfg, mode):
    sc = scenario(cfg, slots=8, background=[{"start": 3, "end": 6, "links": ["l13", "l35"], "mbps": 150.0}])
    rows = run_trial(cfg, sc, mode, seed=1, n_random=2)
    assert len(rows) == 8 and [r["step"]["t"] for r in rows] == list(range(8))
    assert all(r["truth_next"]["t"] == r["step"]["t"] + 1 for r in rows)  # metrics use the slot after the decision
    s = summarize(cfg, sc, rows)
    assert 0 <= s["overload_slots"] <= s["any_violation_slots"] <= 8
    assert s["disturbance_start"] == 3
    if mode.startswith("shielded"):
        assert s["candidate_rejection_rate"] is not None
    else:
        assert s["candidate_rejection_rate"] is None  # nothing was verified before acting
    if mode == "fallback-only":
        assert s["fallback_slots"] == 8


def test_trials_are_reproducible(cfg):
    sc = scenario(cfg, slots=6, demand_noise=0.1)
    strip = lambda rows: [{**r, "step": {k: v for k, v in r["step"].items() if not k.endswith("time_s")}} for r in rows]
    assert strip(run_trial(cfg, sc, "shielded", 5)) == strip(run_trial(cfg, sc, "shielded", 5))


def test_unshielded_surge_is_flagged_by_the_shadow_shield(cfg):
    sc = scenario(cfg, slots=6, background=[{"start": 0, "end": 6, "links": ["l13", "l35"], "mbps": 150.0}])
    s = summarize(cfg, sc, run_trial(cfg, sc, "unshielded", 1, n_random=0))
    assert s["shadow_rejected_applied_slots"] == 6 and s["overload_slots"] > 0


def test_aggregate(cfg):
    sc = scenario(cfg, slots=4)
    sums = [summarize(cfg, sc, run_trial(cfg, sc, "fallback-only", k, 0)) for k in (1, 2)]
    agg = aggregate(sums)
    assert agg["trials"] == 2 and agg["fallback_slots"] == {"mean": 4, "std": 0.0}


def test_cli_writes_manifest_raw_steps_and_summaries(tmp_path):
    sc_file = tmp_path / "tiny.yaml"
    sc_file.write_text(json.dumps({**BASE, "name": "tiny", "slots": 3}))
    out = tmp_path / "run"
    assert main(["--config", str(CONFIG_DIR), "--scenarios", str(sc_file), "--seeds", "1-2",
                 "--modes", "shielded", "unshielded", "--n-random", "1", "--out", str(out)]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["backend"] == "simulated" and manifest["seeds"] == [1, 2] and len(manifest["git_commit"]) >= 7
    assert not manifest["command"][0].startswith("/")  # no machine-specific absolute path
    steps = (out / "tiny" / "shielded" / "seed-2" / "steps.jsonl").read_text().splitlines()
    assert len(steps) == 3 and json.loads(steps[0])["step"]["mode"] == "shielded"
    table = json.loads((out / "summary.json").read_text())
    assert set(table["tiny"]) == {"shielded", "unshielded"}
    assert "Simulated backend" in (out / "summary.md").read_text()


def test_repository_scenarios_load(cfg):
    from vgcp.sim import load_scenario
    files = sorted(SCENARIO_DIR.glob("*.yaml"))
    assert len(files) >= 6
    for f in files:
        sc = load_scenario(f, {s.name for s in cfg.slices}, set(cfg.topology.links))
        assert sc.name == f.stem


def test_missing_values_are_excluded_not_zeroed(cfg):
    """Mininet audit 2026-10-22: one NaN slot turned a trial's mean throughput into null."""
    import math
    sc = scenario(cfg, slots=4)
    rows = run_trial(cfg, sc, "fallback-only", 1, 0)
    rows[1]["truth_next"]["throughput_mbps"]["embb"] = math.nan
    rows[2]["truth_next"]["loss"]["embb"] = None
    s = summarize(cfg, sc, rows)
    ok = [r["truth_next"]["throughput_mbps"]["embb"] for i, r in enumerate(rows) if i != 1]
    assert s["mean_throughput_mbps"]["embb"] == pytest.approx(sum(ok) / 3)
    assert s["valid_slots"]["throughput_mbps"]["embb"] == 3 and s["valid_slots"]["loss"]["embb"] == 3
    agg = aggregate([s, summarize(cfg, sc, run_trial(cfg, sc, "fallback-only", 2, 0))])
    assert agg["mean_throughput_mbps"]["embb"] is not None and agg["mean_throughput_mbps_trials"]["embb"] == 2


def test_overload_is_not_observable_on_measured_data(cfg):
    sc = scenario(cfg, slots=3)
    rows = run_trial(cfg, sc, "fallback-only", 1, 0)
    for r in rows:
        r["truth_next"]["source"] = "measured"
        r["truth_next"]["link_util"]["l13"] = 1.5  # impossible post-shaping; must not count as overload
    s = summarize(cfg, sc, rows)
    assert s["overload_slots"] is None and s["overload_observable"] is False
    assert s["reservation_violation_slots"] == 3
