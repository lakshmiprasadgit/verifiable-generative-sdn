"""One demonstration run, stepped one control slot at a time.

Nothing here decides anything: the run uses the experiment runner's own
build_controller, backends and summarize(). Two pass-through recorders sit around
the real shield and candidate generator, so the dashboard can show the exact
candidates and certificates the controller used in each slot.

Per step:  observe() -> controller.step(obs) -> advance() -> ground_truth()
which is the loop of runner.run_trial, so a demo run and an experiment trial with
the same scenario, controller and seed produce the same records.
"""

from __future__ import annotations

import math
import time
from typing import Any

from vgcp.config import ProjectConfig
from vgcp.errors import json_safe
from vgcp.experiments.runner import _violations, build_controller, latency_thresholds, summarize
from vgcp.loop.controller import primary_failures
from vgcp.shield import CheckStatus
from vgcp.sim import Scenario, SimulatedNetwork
from vgcp.state import MetricStatus

REASON_LABELS = {
    "action_valid": "action outside the action set",
    "state_measurements": "state measurement missing or stale",
    "demand_measurements": "demand measurement missing or stale",
    "hard_constraints_now": "hard constraint violated now (capacity, flow table, budgets, routing)",
    "nominal_model_domain": "nominal model outside its validity domain",
    "fallback_continuation": "fallback continuation invalid",
    "hard_constraints_rollout": "hard constraint violated along the predicted rollout",
    "intent": "temporal-logic intent not satisfied with margin",
    "internal_error": "internal error (fails closed)",
}


class RecordingShield:
    """Pass-through: returns the real shield's certificate and keeps a copy."""

    def __init__(self, shield) -> None:
        self.inner, self.log = shield, []

    def verify(self, state, demand, action, now_s):
        cert = self.inner.verify(state, demand, action, now_s)
        self.log.append(cert)
        return cert


class RecordingGenerator:
    """Pass-through: returns the real generator's candidates and keeps them."""

    def __init__(self, gen) -> None:
        self.inner, self.last = gen, None

    def propose(self, obs):
        self.last = self.inner.propose(obs)
        return self.last


def _num(v: Any) -> float | None:
    """A measurement as JSON: None when missing or not a finite number (never 0)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _cert(cert) -> dict[str, Any]:
    return {
        "accepted": cert.accepted,
        "primary_failures": primary_failures(cert),
        "checks": [{"name": c.name, "status": c.status.value, "detail": c.detail} for c in cert.checks
                   if not (c.status is CheckStatus.UNKNOWN and c.detail.startswith("skipped"))],
        "skipped": [c.name for c in cert.checks if c.status is CheckStatus.UNKNOWN and c.detail.startswith("skipped")],
        "robustness": json_safe(cert.robustness),
        "rho_min": cert.rho_min,
        "nominal_model_in_domain": cert.nominal_model_in_domain,
        "measured_violations": list(cert.measured_violations),
        "action_fingerprint": cert.action_fingerprint[:12] if cert.action_fingerprint else None,
    }


def _changes(old: dict, new: dict) -> list[str]:
    out = []
    for s in new["path"]:
        if old["path"][s] != new["path"][s]:
            out.append(f"{s} path {old['path'][s]}→{new['path'][s]}")
    for s in new["rate_budget_mbps"]:
        a, b = old["rate_budget_mbps"][s], new["rate_budget_mbps"][s]
        if abs(a - b) > 1e-6 * max(1.0, abs(a)):
            out.append(f"{s} budget {a:.1f}→{b:.1f} Mbit/s")
    for s in new["admission_limit"]:
        if old["admission_limit"][s] != new["admission_limit"][s]:
            out.append(f"{s} admission {old['admission_limit'][s]}→{new['admission_limit'][s]}")
    for l in new["link_power"]:
        if old["link_power"][l] != new["link_power"][l]:
            out.append(f"link {l} {'on' if new['link_power'][l] else 'off'}")
    return out


class DemoRun:
    def __init__(self, cfg: ProjectConfig, scenario: Scenario, mode: str, seed: int, n_random: int = 4,
                 backend: str = "sim") -> None:
        self.cfg, self.sc, self.mode, self.seed, self.n_random = cfg, scenario, mode, seed, n_random
        self.backend_name = backend
        if backend == "sim":
            self.backend = SimulatedNetwork(cfg, scenario, seed)
        elif backend == "mininet":  # needs root; the server only offers it when running as root
            from vgcp.emu import MininetFabric, MininetNetwork
            self.backend = MininetNetwork(cfg, scenario, seed, MininetFabric())
        else:
            raise ValueError(f"unknown backend {backend!r}")
        self.shield: RecordingShield | None = None
        self.gen: RecordingGenerator | None = None

        def ws(s):
            self.shield = RecordingShield(s)
            return self.shield

        def wg(g):
            self.gen = RecordingGenerator(g)
            return self.gen

        self.controller = build_controller(cfg, mode, self.backend, seed, n_random, wrap_shield=ws, wrap_generator=wg)
        self.bounds = latency_thresholds(cfg)
        self.rows: list[dict[str, Any]] = []
        self.steps: list[dict[str, Any]] = []
        self.initial = json_safe(self.backend.ground_truth())
        self.closed = False

    @property
    def done(self) -> bool:
        return len(self.rows) >= self.sc.slots

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            close = getattr(self.backend, "close", None)
            if close is not None:
                close()

    # ---------------------------------------------------------------- one slot
    def step(self) -> dict[str, Any]:
        if self.done:
            raise RuntimeError("run finished")
        before = self.backend.ground_truth()
        obs = self.backend.observe()
        self.shield.log.clear()
        self.gen.last = None
        w0 = time.perf_counter()
        rec = self.controller.step(obs)
        self.backend.advance()
        wall = time.perf_counter() - w0
        truth = self.backend.ground_truth()
        row = {"step": rec.to_dict(), "truth_next": truth}
        self.rows.append(row)
        out = json_safe({
            "t": obs.t,
            "observation": self._observation(obs),
            "candidates": self._candidates(rec),
            "decision": self._decision(rec, before["installed"]),
            "result": self._result(truth),
            "events": [],
            "wall_time_s": wall,
        })
        out["events"] = self._events(out, before, truth)
        if self.done:
            self.close()
        self.steps.append(out)
        return out

    def _observation(self, obs) -> dict[str, Any]:
        cfg, inner = self.cfg, self.shield.inner
        st = cfg.state_schema.check(obs.state, list(obs.state.metrics), now_s=obs.now_s,
                                    max_age_s=cfg.shield.max_staleness_s)
        dm = cfg.demand_schema.check(obs.demand, list(obs.demand.metrics), now_s=obs.now_s,
                                     max_age_s=cfg.shield.max_staleness_s)

        def pack(metrics, statuses):
            res = {}
            for k, m in metrics.items():
                ts = m.timestamp_s
                res[k] = {"value": _num(m.value), "age_s": None if ts is None else obs.now_s - ts,
                          "status": statuses.get(k, MetricStatus.OK).value}
            return res
        return {"now_s": obs.now_s, "state": pack(obs.state.metrics, st), "demand": pack(obs.demand.metrics, dm),
                "required_state": list(inner.required_state_keys), "required_demand": list(inner.required_demand_keys)}

    def _candidates(self, rec) -> list[dict[str, Any]]:
        certs = list(self.shield.log)
        cands = self.gen.last or []
        out = []
        if self.mode == "shielded":
            chosen_seen = False
            for c, cert in zip(cands, certs):
                if cert.accepted and not chosen_seen and rec.kind == "certified":
                    role, chosen_seen = "selected", True
                elif cert.accepted:
                    role = "certified, not selected"
                else:
                    role = "rejected"
                out.append({"label": c.label, "action": c.action.to_dict(), "role": role, "certificate": _cert(cert)})
        elif self.mode in ("unshielded", "unshielded-fitted"):
            for i, c in enumerate(cands):
                entry = {"label": c.label, "action": c.action.to_dict(),
                         "role": "applied without verification" if i == 0 else "not considered"}
                if i == 0 and certs:
                    entry["certificate"] = _cert(certs[0])
                    entry["shadow"] = True  # shield asked for the record only; it did not decide
                out.append(entry)
        return out

    def _decision(self, rec, installed_before: dict) -> dict[str, Any]:
        certs = list(self.shield.log)
        fb_cert = certs[-1] if rec.kind == "fallback" and certs else None
        if not rec.applied:
            badge = "NOT APPLIED"
        elif rec.kind == "certified":
            badge = "CERTIFIED ACTION"
        elif rec.kind == "fallback":
            badge = "CERTIFIED FALLBACK" if rec.fallback_certified else "UNCERTIFIED FALLBACK"
        else:
            badge = "UNVERIFIED (baseline)"
        return {
            "badge": badge, "kind": rec.kind, "chosen": rec.chosen, "applied": rec.applied, "detail": rec.detail,
            "action": rec.action, "changes": _changes(installed_before, rec.action),
            "fallback_certified": rec.fallback_certified, "shield_would_accept": rec.shield_would_accept,
            "fallback_certificate": _cert(fb_cert) if fb_cert is not None else None,
            "n_candidates": rec.n_candidates, "n_verified": rec.n_verified, "n_certified": rec.n_certified,
            "rejection_reasons": rec.rejection_reasons, "verify_time_s": rec.verify_time_s,
            "decision_time_s": rec.decision_time_s, "measured_violations": rec.measured_violations,
        }

    def _result(self, truth: dict) -> dict[str, Any]:
        viol = _violations({"truth_next": truth}, self.cfg, self.bounds)
        return {"truth": truth, "violations": viol,
                "source": truth.get("source", "simulated ground truth")}

    def _events(self, s: dict, before: dict, truth: dict) -> list[dict[str, str]]:
        """Derived only from this step's real records."""
        ev, t, d = [], s["t"], s["decision"]
        obs = s["observation"]
        bad = [k for part in ("state", "demand") for k, m in obs[part].items() if m["status"] != "ok"]
        ev.append({"kind": "observe", "text": f"Observation at t={t}: {sum(len(obs[p]) for p in ('state', 'demand'))} metrics"
                   + (f", {len(bad)} unusable" if bad else "")})
        if bad:
            ev.append({"kind": "missing", "text": "Measurement unavailable/stale: " + ", ".join(sorted(bad)[:6])
                       + (" …" if len(bad) > 6 else "")})
        if d["n_verified"]:
            reasons = ", ".join(f"{k} ×{v}" for k, v in sorted(d["rejection_reasons"].items()))
            ev.append({"kind": "verify", "text": f"{d['n_candidates']} candidates verified: {d['n_certified']} certified, "
                       f"{d['n_verified'] - d['n_certified']} rejected" + (f" ({reasons})" if reasons else "")})
        if d["kind"] == "certified":
            ev.append({"kind": "certified", "text": f"Applied certified candidate '{d['chosen']}'"})
        elif d["kind"] == "fallback":
            ev.append({"kind": "fallback" if d["fallback_certified"] else "uncertified",
                       "text": f"Fallback π₀(s) activated ({d['detail']}) — "
                       + ("fallback certified" if d["fallback_certified"] else "UNCERTIFIED FALLBACK")})
        else:
            sw = d["shield_would_accept"]
            ev.append({"kind": "unchecked", "text": f"Applied '{d['chosen']}' without verification"
                       + ("" if sw is None else f" (shadow shield would {'accept' if sw else 'REJECT'})")})
        if not d["applied"]:
            ev.append({"kind": "failure", "text": f"Action not applied: {d['detail']}"})
        for c in _changes(before["installed"], truth["installed"]):
            ev.append({"kind": "change", "text": f"Installed in network: {c}"})
        if d["applied"] and truth["installed"] != d["action"]:
            ev.append({"kind": "pending", "text": "Applied action not yet in effect (actuation delay)"})
        v = s["result"]["violations"]
        for k, hit in v.items():
            if hit and k != "any":
                ev.append({"kind": "violation", "text": f"Outcome at t={truth['t']}: {k} violated"})
        return ev

    # ---------------------------------------------------------------- end of run
    def summary(self) -> dict[str, Any]:
        rows = self.rows
        if not rows:
            return {"steps": 0}
        s = summarize(self.cfg, self.sc, rows)  # the experiment runner's own metrics
        steps = [r["step"] for r in rows]
        thr: dict[str, Any] = {}
        for sl in self.cfg.action_schema.slice_names:
            vals = [_num(r["truth_next"]["throughput_mbps"][sl]) for r in rows]
            ok = [v for v in vals if v is not None]
            thr[sl] = {"mean_valid": sum(ok) / len(ok) if ok else None, "valid_slots": len(ok), "slots": len(vals)}
        lat: dict[str, Any] = {}
        for sl in self.bounds:
            vals = [_num(r["truth_next"]["latency_p99_ms"][sl]) for r in rows]
            ok = [v for v in vals if v is not None]
            lat[sl] = {"max_valid": max(ok) if ok else None, "valid_slots": len(ok), "slots": len(vals),
                       "bound_ms": self.bounds[sl]}
        extra = {
            "scenario": self.sc.name, "description": self.sc.description, "controller": self.mode,
            "seed": self.seed, "backend": self.backend_name,
            "certified_steps": sum(x["kind"] == "certified" for x in steps),
            "fallback_certified_steps": sum(x["kind"] == "fallback" and x["fallback_certified"] is True for x in steps),
            "fallback_uncertified_steps": sum(x["kind"] == "fallback" and x["fallback_certified"] is False for x in steps),
            "unverified_steps": sum(x["kind"] == "unchecked" for x in steps),
            "rejected_candidates": sum(x["n_verified"] - x["n_certified"] for x in steps),
            "verified_candidates": sum(x["n_verified"] for x in steps),
            "throughput": thr, "latency": lat,
        }
        return json_safe({"runner": s, "demo": extra})
