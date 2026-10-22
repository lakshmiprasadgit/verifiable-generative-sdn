"""Dashboard server (Python standard library only; no root needed for simulation runs).

  GET  /                      the dashboard (static/index.html)
  GET  /api/meta              topology, slices, intents, scenarios, controllers, backend status
  POST /api/run               {scenario, controller, seed, backend} -> new run (replaces the old one)
  POST /api/step              {run_id} -> one control slot of the current run
  GET  /api/summary?run_id=   end-of-run summary (runner.summarize + demo counts)
  GET  /api/history           saved campaigns (historical, read-only)
  GET  /api/history/item?id=  one saved campaign's summary and manifest

One run at a time; a lock serializes steps. Saved campaigns are only read.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from vgcp.config import load_config
from vgcp.demo.session import DemoRun
from vgcp.errors import json_safe
from vgcp.experiments.runner import MODES, latency_thresholds
from vgcp.sim import load_scenario

ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parent / "static"
SCENARIOS = ROOT / "experiments" / "scenarios"


def mininet_status() -> dict:
    if os.geteuid() != 0:
        return {"available": False, "reason": "needs root. The dashboard does not use sudo; Mininet runs are "
                "launched from a terminal with: sudo scripts/mininet_run.sh"}
    try:
        import mininet.net  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "Mininet is not importable"}
    if not Path("/var/run/openvswitch/db.sock").exists():
        return {"available": False, "reason": "Open vSwitch is not running"}
    for tool in ("ovs-ofctl", "iperf3", "ping"):
        if shutil.which(tool) is None:
            return {"available": False, "reason": f"{tool} not found"}
    return {"available": True, "reason": "running as root; each slot takes 1 s of real time"}


class App:
    def __init__(self, config_dir: Path) -> None:
        self.cfg = load_config(config_dir)
        self.slice_names = {s.name for s in self.cfg.slices}
        self.lock = threading.Lock()
        self.run: DemoRun | None = None
        self.run_id: str | None = None

    def scenario(self, name: str):
        path = SCENARIOS / f"{name}.yaml"
        if path.parent != SCENARIOS or not path.is_file():
            raise ValueError(f"unknown scenario {name!r}")
        return load_scenario(path, self.slice_names, set(self.cfg.topology.links))

    def meta(self) -> dict:
        cfg, topo = self.cfg, self.cfg.topology
        scen = []
        for p in sorted(SCENARIOS.glob("*.yaml")):
            sc = load_scenario(p, self.slice_names, set(topo.links))
            scen.append({"name": sc.name, "slots": sc.slots, "description": sc.description})
        return json_safe({
            "topology": {
                "switches": list(topo.switches), "ingress": topo.ingress, "egress": topo.egress,
                "links": {lid: {"a": l.a, "b": l.b, "capacity_mbps": l.capacity_mbps, "delay_ms": l.prop_delay_ms}
                          for lid, l in topo.links.items()},
                "paths": {pid: {"nodes": list(p.nodes), "links": list(p.links)} for pid, p in topo.paths.items()},
                "power_controllable_links": list(topo.power_controllable_links),
            },
            "slices": [{"name": s.name, "allowed_paths": list(s.allowed_paths),
                        "rate_budget_mbps": list(s.rate_budget_mbps)} for s in cfg.slices],
            "intents": [{"name": it.name, "formula": it.text, "rho_min": it.rho_min, "description": it.description} for it in cfg.intents],
            "latency_bounds_ms": latency_thresholds(cfg),
            "max_reserved_fraction": cfg.constraints.max_reserved_fraction,
            "fallback_policy": cfg.shield.fallback_policy,
            "horizon_H": cfg.horizon_H,
            "scenarios": scen, "controllers": list(MODES),
            "backends": {"sim": {"available": True, "reason": "simulated network (ground truth model)"},
                         "mininet": mininet_status()},
        })

    def start(self, body: dict) -> dict:
        mode = body.get("controller", "shielded")
        if mode not in MODES:
            raise ValueError(f"unknown controller {mode!r}")
        backend = body.get("backend", "sim")
        if backend == "mininet" and not mininet_status()["available"]:
            raise ValueError("Mininet backend unavailable: " + mininet_status()["reason"])
        seed = int(body.get("seed", 1))
        sc = self.scenario(str(body.get("scenario", "")))
        with self.lock:
            if self.run is not None:
                self.run.close()
            self.run = None
            self.run = DemoRun(self.cfg, sc, mode, seed, backend=backend)
            self.run_id = uuid.uuid4().hex[:8]
            return json_safe({"run_id": self.run_id, "scenario": sc.name, "description": sc.description,
                              "slots": sc.slots, "controller": mode, "seed": seed, "backend": backend,
                              "initial": self.run.initial})

    def _current(self, run_id: str) -> DemoRun:
        if self.run is None or run_id != self.run_id:
            raise LookupError("no such run (it was reset or replaced)")
        return self.run

    def step(self, body: dict) -> dict:
        with self.lock:
            run = self._current(str(body.get("run_id")))
            if run.done:
                return {"done": True}
            out = run.step()
            out["done"] = run.done
            out["slot"] = len(run.rows)
            return out

    def summary(self, run_id: str) -> dict:
        with self.lock:
            return self._current(run_id).summary()

    # ---------------------------------------------------------------- saved campaigns (read-only)
    def _campaign_dirs(self) -> list[Path]:
        dirs = sorted((ROOT / "experiments" / "reports").glob("*/summary.json"))
        dirs += sorted((ROOT / "experiments" / "results").glob("mininet-*/campaign/summary.json"))
        return [p.parent for p in dirs]

    def history(self) -> list[dict]:
        out = []
        for d in self._campaign_dirs():
            man = json.loads((d / "manifest.json").read_text()) if (d / "manifest.json").exists() else {}
            out.append({"id": str(d.relative_to(ROOT)), "backend": man.get("backend", "unknown"),
                        "commit": (man.get("git_commit") or "unknown")[:7], "dirty": man.get("git_dirty"),
                        "started_utc": man.get("started_utc"), "seeds": man.get("seeds"),
                        "fallback_policy": man.get("fallback_policy"),
                        "scenarios": list(man.get("scenarios", {}))})
        return out

    def history_item(self, ident: str) -> dict:
        allowed = {str(d.relative_to(ROOT)): d for d in self._campaign_dirs()}
        if ident not in allowed:
            raise LookupError("unknown campaign")
        d = allowed[ident]
        man = json.loads((d / "manifest.json").read_text()) if (d / "manifest.json").exists() else {}
        return {"id": ident, "manifest": man, "summary": json.loads((d / "summary.json").read_text())}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quieter console
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(json_safe(obj), allow_nan=False).encode(), "application/json")

        def _guard(self, fn):
            try:
                self._json(fn())
            except LookupError as e:
                self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
            except ValueError as e:
                self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            except Exception as e:  # report, never crash the server
                self._json({"error": f"{type(e).__name__}: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/meta":
                return self._guard(app.meta)
            if u.path == "/api/summary":
                return self._guard(lambda: app.summary(q.get("run_id", [""])[0]))
            if u.path == "/api/history":
                return self._guard(app.history)
            if u.path == "/api/history/item":
                return self._guard(lambda: app.history_item(q.get("id", [""])[0]))
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "invalid JSON"}, HTTPStatus.BAD_REQUEST)
            if u.path == "/api/run":
                return self._guard(lambda: app.start(body))
            if u.path == "/api/step":
                return self._guard(lambda: app.step(body))
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    return Handler


def serve(host: str, port: int, config_dir: Path) -> None:
    app = App(config_dir)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"VGCP dashboard: http://{host}:{port}/   (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if app.run is not None:
            app.run.close()
        httpd.server_close()
