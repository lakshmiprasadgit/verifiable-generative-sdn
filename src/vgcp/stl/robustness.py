"""Quantitative robustness (paper Eqs 8-11) and qualitative satisfaction of STL.

Robustness, at integer slot t of a finite trace:

    rho_T(t)                = +inf                                        (not in paper; standard)
    rho_p(t)                = p(x_t)                                      (Eq 8)
    rho_{not phi}(t)        = -rho_phi(t)                                 (Eq 9)
    rho_{phi1 and phi2}(t)  = min(rho_phi1(t), rho_phi2(t))               (Eq 10)
    rho_{phi1 U[a,b] phi2}(t) = max_{tau in [t+a, t+b]}
                                min(rho_phi2(tau), min_{u in [t, tau]} rho_phi1(u))   (Eq 11)

Note the paper's window for phi1 is the closed interval [t, tau] (it includes
tau); this is implemented exactly as written.

Satisfaction: the paper states rho > 0 means satisfied and rho < 0 violated.
rho == 0 is reported as BOUNDARY, with the qualitative (Boolean) semantics -
predicate true iff p >= 0 - deciding the Boolean value.

Missing data: any NaN sample that the evaluation reads makes the result
UNKNOWN (robustness NaN / satisfied None). There is no imputation, and a
known value elsewhere in a window does not override an unknown one.

Evaluation that would read beyond the end of the trace raises
TraceTooShortError (the robustness is undefined, cf. Assumption 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from vgcp.stl.ast import And, Formula, Not, Predicate, Top, Until, required_horizon
from vgcp.stl.signal import Trace


class TraceTooShortError(ValueError):
    pass


class Verdict(str, Enum):
    SATISFIED = "satisfied"  # rho > 0
    VIOLATED = "violated"  # rho < 0
    BOUNDARY = "boundary"  # rho == 0
    UNKNOWN = "unknown"  # a required sample is missing or invalid


@dataclass(frozen=True)
class StlResult:
    robustness: float | None  # None when unknown
    verdict: Verdict
    satisfied: bool | None  # qualitative semantics; None when unknown


def _min(values) -> float:
    values = list(values)
    return math.nan if any(math.isnan(v) for v in values) else min(values)


def _max(values) -> float:
    values = list(values)
    return math.nan if any(math.isnan(v) for v in values) else max(values)


def _check_horizon(phi: Formula, trace: Trace, t: int) -> None:
    if not isinstance(t, int) or t < 0:
        raise ValueError(f"evaluation time must be a non-negative integer, got {t!r}")
    needed = t + required_horizon(phi)
    if needed > trace.length - 1:
        raise TraceTooShortError(
            f"evaluating at t={t} needs samples up to index {needed}, "
            f"but the trace has length {trace.length}"
        )


def robustness(phi: Formula, trace: Trace, t: int = 0) -> float:
    """rho_phi(trace, t); NaN when a required sample is missing."""
    _check_horizon(phi, trace, t)
    return _rho(phi, trace, t, {})


def _rho(phi: Formula, trace: Trace, t: int, memo: dict) -> float:
    key = (id(phi), t)
    if key in memo:
        return memo[key]
    if isinstance(phi, Top):
        r = math.inf
    elif isinstance(phi, Predicate):
        x = trace.value(phi.signal, t)
        r = math.nan if math.isnan(x) else phi.value(x)
    elif isinstance(phi, Not):
        r = -_rho(phi.child, trace, t, memo)
    elif isinstance(phi, And):
        r = _min([_rho(phi.left, trace, t, memo), _rho(phi.right, trace, t, memo)])
    elif isinstance(phi, Until):
        candidates = []
        left_min = math.inf  # running min of rho_phi1(u) over u in [t, tau]
        for tau in range(t, t + phi.b + 1):
            left_min = _min([left_min, _rho(phi.left, trace, tau, memo)])
            if tau >= t + phi.a:
                candidates.append(_min([_rho(phi.right, trace, tau, memo), left_min]))
        r = _max(candidates)
    else:
        raise TypeError(f"not an STL formula: {phi!r}")
    memo[key] = r
    return r


def satisfied(phi: Formula, trace: Trace, t: int = 0) -> bool | None:
    """Qualitative (Boolean) semantics; None when a required sample is missing."""
    _check_horizon(phi, trace, t)
    return _sat(phi, trace, t, {})


def _all_known(values) -> bool:
    return all(v is not None for v in values)


def _sat(phi: Formula, trace: Trace, t: int, memo: dict) -> bool | None:
    key = (id(phi), t)
    if key in memo:
        return memo[key]
    if isinstance(phi, Top):
        r: bool | None = True
    elif isinstance(phi, Predicate):
        x = trace.value(phi.signal, t)
        r = None if math.isnan(x) else phi.value(x) >= 0
    elif isinstance(phi, Not):
        c = _sat(phi.child, trace, t, memo)
        r = None if c is None else not c
    elif isinstance(phi, And):
        vals = [_sat(phi.left, trace, t, memo), _sat(phi.right, trace, t, memo)]
        r = all(vals) if _all_known(vals) else None
    elif isinstance(phi, Until):
        lefts = [_sat(phi.left, trace, u, memo) for u in range(t, t + phi.b + 1)]
        rights = [_sat(phi.right, trace, tau, memo) for tau in range(t + phi.a, t + phi.b + 1)]
        if not (_all_known(lefts) and _all_known(rights)):
            r = None
        else:
            r = any(
                rights[tau - t - phi.a] and all(lefts[: tau - t + 1])
                for tau in range(t + phi.a, t + phi.b + 1)
            )
    else:
        raise TypeError(f"not an STL formula: {phi!r}")
    memo[key] = r
    return r


def evaluate(phi: Formula, trace: Trace, t: int = 0) -> StlResult:
    rho = robustness(phi, trace, t)
    sat = satisfied(phi, trace, t)
    if math.isnan(rho) or sat is None:
        return StlResult(None, Verdict.UNKNOWN, None)
    if rho > 0:
        verdict = Verdict.SATISFIED
    elif rho < 0:
        verdict = Verdict.VIOLATED
    else:
        verdict = Verdict.BOUNDARY
    return StlResult(rho, verdict, sat)
