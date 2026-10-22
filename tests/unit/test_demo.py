"""Dashboard backend: it must show the real run, unchanged, and never dress up missing data."""

import json
import math
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from factories import CONFIG_DIR
from vgcp.config import load_config
from vgcp.demo.server import App, make_handler
from vgcp.demo.session import DemoRun, _num
from vgcp.experiments.runner import dumps, run_trial, summarize
from vgcp.sim import load_scenario

ROOT = CONFIG_DIR.parent
TIMING = ("verify_time_s", "decision_time_s")


@pytest.fixture(scope="module")
def cfg():
    return load_config(CONFIG_DIR)


def _sc(cfg, name):
    return load_scenario(ROOT / "experiments" / "scenarios" / f"{name}.yaml", {s.name for s in cfg.slices},
                         set(cfg.topology.links))


def _strip(rows):
    out = []
    for r in rows:
        r = json.loads(dumps(r))
        for k in TIMING:
            r["step"].pop(k)
        out.append(r)
    return out


def _run(cfg, name, mode, seed=1):
    run = DemoRun(cfg, _sc(cfg, name), mode, seed)
    steps = []
    while not run.done:
        steps.append(run.step())
    return run, steps


@pytest.mark.parametrize("name,mode", [("s3_background_on_urllc_path", "shielded"),
                                       ("s2_background_on_embb_path", "unshielded")])
def test_demo_run_is_the_experiment_trial(cfg, name, mode):
    run, _ = _run(cfg, name, mode)
    assert _strip(run.rows) == _strip(run_trial(cfg, _sc(cfg, name), mode, 1))  # same records, timing aside


def test_uncertified_fallback_is_labelled_as_such(cfg):
    run, steps = _run(cfg, "s3_background_on_urllc_path", "shielded")
    for s, r in zip(steps, run.rows):
        d = s["decision"]
        if r["step"]["kind"] == "fallback" and r["step"]["fallback_certified"] is False:
            assert d["badge"] == "UNCERTIFIED FALLBACK" and not d["fallback_certificate"]["accepted"]
            assert any(e["kind"] == "uncertified" for e in s["events"])
        elif r["step"]["kind"] == "certified":
            assert d["badge"] == "CERTIFIED ACTION"
            sel = [c for c in s["candidates"] if c["role"] == "selected"]
            assert len(sel) == 1 and sel[0]["certificate"]["accepted"] and sel[0]["action"] == d["action"]
    assert sum(s["decision"]["badge"] == "UNCERTIFIED FALLBACK" for s in steps) == run.summary()["demo"]["fallback_uncertified_steps"] > 0


def test_candidates_match_the_controllers_counts(cfg):
    _, steps = _run(cfg, "s2_background_on_embb_path", "shielded")
    for s in steps:
        d, c = s["decision"], s["candidates"]
        assert len(c) == d["n_candidates"] == d["n_verified"]
        assert sum(x["certificate"]["accepted"] for x in c) == d["n_certified"]


def test_missing_telemetry_stays_missing(cfg):
    _, steps = _run(cfg, "s4_telemetry_faults", "shielded")
    s = steps[41]  # background counters missing in slots 40-45
    bg = {k: m for k, m in s["observation"]["state"].items() if k.startswith("background_load_mbps.")}
    assert bg and all(m["value"] is None and m["status"] == "missing" for m in bg.values())
    assert any(e["kind"] == "missing" for e in s["events"])
    assert _num(math.nan) is None and _num(math.inf) is None and _num(None) is None and _num(0.0) == 0.0


def test_summary_is_the_runners_summary(cfg):
    run, _ = _run(cfg, "s3_background_on_urllc_path", "fallback-only")
    got = run.summary()["runner"]
    want = json.loads(dumps(summarize(cfg, run.sc, run.rows)))
    assert got == want


def test_http_api_end_to_end(cfg):
    app = App(CONFIG_DIR)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        meta = call("/api/meta")
        assert set(meta["topology"]["paths"]) == {"A", "B", "C"} and meta["backends"]["sim"]["available"]
        r = call("/api/run", {"scenario": "s1_steady", "controller": "shielded", "seed": 2})
        n = 0
        while True:
            s = call("/api/step", {"run_id": r["run_id"]})
            n += 1
            if s["done"]:
                break
        assert n == r["slots"] == 60
        summ = call(f"/api/summary?run_id={r['run_id']}")
        assert summ["runner"]["slots"] == 60 and summ["demo"]["certified_steps"] + summ["runner"]["fallback_slots"] == 60
        with pytest.raises(urllib.error.HTTPError) as e:
            call("/api/history/item?id=../../etc")
        assert e.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as e:
            call("/api/run", {"scenario": "../configs/network", "controller": "shielded"})
        assert e.value.code == 400
    finally:
        httpd.shutdown()
        if app.run is not None:
            app.run.close()
