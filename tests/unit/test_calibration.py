"""Nominal-model latency calibration (Milestone 3)."""

import json
import math

import pytest

from factories import CONFIG_DIR
from test_sim import BASE, scenario
from vgcp.experiments.__main__ import main as run_campaign
from vgcp.experiments.calibrate import main as run_calibration
from vgcp.experiments.runner import run_trial
from vgcp.models.calibration import LatencyPoint, calibrate, coverage, points_from_rows, quantile


def test_model_matching_ground_truth_calibrates_to_one(cfg):
    """BASE's ground truth uses the model's packet sizes and no noise: ratio is 1."""
    sc = scenario(cfg, slots=6, background=[{"start": 2, "end": 5, "links": ["l13", "l35"], "mbps": 60.0}])
    rows = run_trial(cfg, sc, "fallback-only", 1, 0)
    pts = points_from_rows(cfg, rows, dict(sc.devices))
    assert len(pts) == 6 * 3
    assert all(p.ratio == pytest.approx(1.0) for p in pts)
    assert calibrate(pts)["proposed_latency_safety_factor"] == pytest.approx(1.0)


def test_mismatched_ground_truth_is_detected(cfg):
    big = {**BASE["ground_truth"], "packet_size_bytes": {"urllc": 1500, "embb": 1500, "mmtc": 500}}
    sc = scenario(cfg, slots=4, ground_truth=big)
    pts = points_from_rows(cfg, run_trial(cfg, sc, "fallback-only", 1, 0), dict(sc.devices))
    fit = calibrate(pts)
    assert fit["ratio_by_slice"]["urllc"]["median"] > 1.0  # bigger packets than the model assumes
    assert coverage(pts, 1.0) < 1.0 and coverage(pts, fit["proposed_latency_safety_factor"]) == 1.0


def test_unknown_inputs_give_no_point(cfg):
    sc = scenario(cfg, slots=2)
    rows = run_trial(cfg, sc, "fallback-only", 1, 0)
    rows[0]["truth_next"]["background_mbps"]["l13"] = None
    rows[1]["truth_next"]["latency_p99_ms"]["urllc"] = math.inf  # lost probes on Mininet
    pts = points_from_rows(cfg, rows, dict(sc.devices))
    assert {p.t for p in pts} == {rows[1]["truth_next"]["t"]} and len(pts) == 2


def test_quantile_and_coverage_by_hand():
    assert quantile([1, 2, 3, 4], 0.5) == 2 and quantile([1, 2, 3, 4], 0.99) == 4 and math.isnan(quantile([], 0.5))
    pts = [LatencyPoint("r", 0, "urllc", obs, 1.0) for obs in (0.5, 1.0, 1.5, 2.0)]
    assert coverage(pts, 1.0) == 0.5 and coverage(pts, 2.0) == 1.0 and coverage([], 1.0) is None
    assert calibrate(pts, 0.75)["proposed_latency_safety_factor"] == 1.5
    with pytest.raises(ValueError):
        calibrate(pts, 0.0)


def test_cli_fits_on_training_seeds_and_reports_held_out_coverage(tmp_path):
    sc_file = tmp_path / "tiny.yaml"
    sc_file.write_text(json.dumps({**BASE, "name": "tiny", "slots": 3}))
    camp = tmp_path / "camp"
    assert run_campaign(["--config", str(CONFIG_DIR), "--scenarios", str(sc_file), "--seeds", "1-2",
                         "--modes", "fallback-only", "--out", str(camp)]) == 0
    out = tmp_path / "cal"
    assert run_calibration(["--config", str(CONFIG_DIR), "--campaign", str(camp), "--train-seeds", "1",
                            "--out", str(out)]) == 0
    rep = json.loads((out / "calibration.json").read_text())
    assert rep["fit"]["n_points"] == 3 * 3 and rep["training"]["seeds"] == [1]
    held = rep["held_out"][str(camp)]
    assert held["n_points"] == 3 * 3  # seed 2 only
    assert (out / "calibration.md").read_text().startswith("Calibration of the nominal model")


def test_campaign_records_the_safety_factor_override(tmp_path):
    sc_file = tmp_path / "tiny.yaml"
    sc_file.write_text(json.dumps({**BASE, "name": "tiny", "slots": 2}))
    out = tmp_path / "run"
    assert run_campaign(["--config", str(CONFIG_DIR), "--scenarios", str(sc_file), "--seeds", "1",
                         "--modes", "shielded", "--latency-safety-factor", "1.1", "--out", str(out)]) == 0
    man = json.loads((out / "manifest.json").read_text())
    assert man["latency_safety_factor"] == 1.1 and man["config_overrides"] == {"latency_safety_factor": 1.1}
