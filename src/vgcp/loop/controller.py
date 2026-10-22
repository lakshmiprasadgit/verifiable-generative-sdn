"""Controllers for one control slot (paper Sec 3).

ShieldedController   - verifies every candidate; applies the first certified one in the
                       generator's order of preference (Milestone 2 rule), or, given a
                       UtilityModel, the certified one with the highest predicted return
                       (paper Eq 42, Milestone 4); otherwise applies pi_0 (Remark 1) and
                       records whether pi_0 itself was certified.
UnshieldedController - baseline: applies the generator's first candidate unverified. It
                       can optionally ask the shield, without acting on the answer
                       ("shadow" verification), so we can count how often it applied
                       something the shield would have rejected.
FallbackOnlyController - baseline: always applies pi_0.

All three use the same generator and record the same fields, so the comparison
isolates the effect of the shield.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from vgcp.config import ProjectConfig
from vgcp.loop.applier import ApplyRecord, CertifiedApplier, UncheckedApplier
from vgcp.loop.interfaces import CandidateGenerator, Observation
from vgcp.shield import Certificate, CheckStatus, VerificationShield


@dataclass
class StepRecord:
    t: int
    mode: str
    chosen: str  # candidate label, or "fallback"
    kind: str  # "certified" | "fallback" | "unchecked"
    applied: bool
    n_candidates: int = 0
    n_verified: int = 0  # candidates actually checked by the shield before deciding
    n_certified: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    fallback_certified: bool | None = None  # pi_0 checked in this state (Assumption 3 monitor)
    shield_would_accept: bool | None = None  # unshielded mode with shadow verification
    measured_violations: list[str] = field(default_factory=list)
    verify_time_s: float = 0.0
    decision_time_s: float = 0.0
    action: dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    selection: str | None = None  # "first-certified" | "max-utility" (shielded modes only)
    predicted_returns: dict[str, float] = field(default_factory=dict)  # Eq 42 objective per certified candidate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def primary_failures(cert: Certificate) -> list[str]:
    """Failed checks, excluding those only skipped because an earlier one failed."""
    return [c.name.split(":")[0] for c in cert.failed()
            if not (c.status is CheckStatus.UNKNOWN and c.detail.startswith("skipped"))]


def _record(t, mode, label, rec: ApplyRecord, **kw) -> StepRecord:
    return StepRecord(t=t, mode=mode, chosen=label, kind=rec.kind, applied=rec.applied,
                      action=rec.action.to_dict(), detail=rec.detail, **kw)


class ShieldedController:
    mode = "shielded"

    def __init__(self, cfg: ProjectConfig, shield: VerificationShield,
                 generator: CandidateGenerator, applier: CertifiedApplier, utility=None,
                 mode: str | None = None) -> None:
        self.cfg, self.shield, self.generator, self.applier = cfg, shield, generator, applier
        self.utility = utility  # vgcp.loop.selection.UtilityModel -> Eq 42; None -> first certified
        if mode is not None:
            self.mode = mode

    def step(self, obs: Observation) -> StepRecord:
        t0 = time.perf_counter()
        candidates = self.generator.propose(obs)
        reasons: Counter[str] = Counter()
        certified, verify = [], 0.0
        for cand in candidates:
            v0 = time.perf_counter()
            cert = self.shield.verify(obs.state, obs.demand, cand.action, obs.now_s)
            verify += time.perf_counter() - v0
            if cert.accepted:
                certified.append((cand, cert))
            else:
                reasons.update(primary_failures(cert))
        chosen, returns = (certified[0] if certified else None), {}
        if certified and self.utility is not None:
            from vgcp.loop.selection import select_max_utility
            chosen, returns = select_max_utility(self.utility, self.shield, obs, certified)
        common = dict(n_candidates=len(candidates), n_verified=len(candidates), n_certified=len(certified),
                      rejection_reasons=dict(reasons),
                      selection="max-utility" if self.utility is not None else "first-certified",
                      predicted_returns=returns)
        if chosen is not None:
            cand, cert = chosen
            rec = self.applier.apply_certified(cand.action, cert, obs)
            return _record(obs.t, self.mode, cand.label, rec, measured_violations=list(cert.measured_violations),
                           verify_time_s=verify, decision_time_s=time.perf_counter() - t0, **common)
        v0 = time.perf_counter()
        fb_cert = self.shield.verify(obs.state, obs.demand, self.applier.fallback_action(obs), obs.now_s)
        verify += time.perf_counter() - v0
        rec = self.applier.apply_fallback(obs, "no candidate certified")
        return _record(obs.t, self.mode, "fallback", rec, fallback_certified=fb_cert.accepted,
                       measured_violations=list(fb_cert.measured_violations),
                       verify_time_s=verify, decision_time_s=time.perf_counter() - t0, **common)


class UnshieldedController:
    mode = "unshielded"

    def __init__(self, cfg: ProjectConfig, generator: CandidateGenerator, applier: UncheckedApplier,
                 shadow_shield: VerificationShield | None = None) -> None:
        self.cfg, self.generator, self.applier, self.shadow = cfg, generator, applier, shadow_shield

    def step(self, obs: Observation) -> StepRecord:
        t0 = time.perf_counter()
        candidates = self.generator.propose(obs)
        top = candidates[0]
        would, verify = None, 0.0
        if self.shadow is not None:  # observation only; never changes the decision
            v0 = time.perf_counter()
            would = self.shadow.verify(obs.state, obs.demand, top.action, obs.now_s).accepted
            verify = time.perf_counter() - v0
        rec = self.applier.apply_unchecked(top.action)
        return _record(obs.t, self.mode, top.label, rec, n_candidates=len(candidates),
                       shield_would_accept=would, verify_time_s=verify, decision_time_s=time.perf_counter() - t0)


class FallbackOnlyController:
    mode = "fallback-only"

    def __init__(self, cfg: ProjectConfig, shield: VerificationShield, applier: CertifiedApplier) -> None:
        self.cfg, self.shield, self.applier = cfg, shield, applier

    def step(self, obs: Observation) -> StepRecord:
        t0 = time.perf_counter()
        cert = self.shield.verify(obs.state, obs.demand, self.applier.fallback_action(obs), obs.now_s)
        verify = time.perf_counter() - t0
        rec = self.applier.apply_fallback(obs, "fallback-only baseline")
        return _record(obs.t, self.mode, "fallback", rec, fallback_certified=cert.accepted,
                       measured_violations=list(cert.measured_violations),
                       verify_time_s=verify, decision_time_s=time.perf_counter() - t0)
