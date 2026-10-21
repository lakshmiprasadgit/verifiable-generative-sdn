"""STL abstract syntax (paper Eq 7).

Only the paper's core operators are node types:

    phi ::= T | p_i >= 0 | not phi | phi1 and phi2 | phi1 U[a,b] phi2

Derived operators are *constructor functions* that expand to the core form
exactly as defined in paper Sec 2.2, so the evaluator never needs separate
semantics for them:

    F[a,b] phi  = T U[a,b] phi
    G[a,b] phi  = not F[a,b] not phi
    phi1 or phi2 = not (not phi1 and not phi2)      (standard De Morgan)
    false        = not T

Time bounds a, b are non-negative integers counted in control slots.
"""

from __future__ import annotations

from dataclasses import dataclass

from vgcp.errors import is_finite_real


class Formula:
    """Base class of STL formulas."""


@dataclass(frozen=True)
class Top(Formula):
    """The constant true formula T."""


@dataclass(frozen=True)
class Predicate(Formula):
    """Atomic predicate written ``signal <= c`` or ``signal >= c``.

    Its real-valued function (paper Eq 5) is
        p(x) = (c - x) / scale   for  x <= c      (cf. Eq 6: L_max - latency)
        p(x) = (x - c) / scale   for  x >= c
    and the predicate holds iff p(x) >= 0. ``scale`` > 0 is the signal family's
    declared unit (configs/intents.yaml signal_scales), which makes robustness
    unitless (audit M4, D18); it never changes whether the predicate holds.
    The parser produces scale 1; config loading applies the declared scales.
    Strict comparisons are not provided: robustness cannot distinguish
    ``x < c`` from ``x <= c``.
    """

    signal: str
    op: str
    threshold: float
    scale: float = 1.0

    def __post_init__(self) -> None:
        if self.op not in ("<=", ">="):
            raise ValueError(f"predicate operator must be '<=' or '>=', got {self.op!r}")
        if not is_finite_real(self.threshold):
            raise ValueError(f"predicate threshold must be a finite number, got {self.threshold!r}")
        if not isinstance(self.signal, str) or not self.signal:
            raise ValueError("predicate signal name must be a non-empty string")
        if not is_finite_real(self.scale) or self.scale <= 0:
            raise ValueError(f"predicate scale must be a finite number > 0, got {self.scale!r}")

    def value(self, x: float) -> float:
        margin = self.threshold - x if self.op == "<=" else x - self.threshold
        return margin / self.scale


@dataclass(frozen=True)
class Not(Formula):
    child: Formula


@dataclass(frozen=True)
class And(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Until(Formula):
    """phi1 U[a,b] phi2 with integer slot bounds 0 <= a <= b."""

    left: Formula
    right: Formula
    a: int
    b: int

    def __post_init__(self) -> None:
        for name in ("a", "b"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError(f"time bound {name} must be an integer number of slots, got {v!r}")
        if not 0 <= self.a <= self.b:
            raise ValueError(f"time interval [{self.a},{self.b}] must satisfy 0 <= a <= b")


def Or(left: Formula, right: Formula) -> Formula:
    return Not(And(Not(left), Not(right)))


def Eventually(a: int, b: int, child: Formula) -> Formula:
    return Until(Top(), child, a, b)


def Always(a: int, b: int, child: Formula) -> Formula:
    return Not(Eventually(a, b, Not(child)))


def false() -> Formula:
    return Not(Top())


def predicates(phi: Formula):
    """All atomic predicates of phi, in order of appearance."""
    if isinstance(phi, Predicate):
        yield phi
    elif isinstance(phi, Not):
        yield from predicates(phi.child)
    elif isinstance(phi, (And, Until)):
        yield from predicates(phi.left)
        yield from predicates(phi.right)
    elif not isinstance(phi, Top):
        raise TypeError(f"not an STL formula: {phi!r}")


def signals(phi: Formula) -> frozenset[str]:
    if isinstance(phi, Predicate):
        return frozenset({phi.signal})
    if isinstance(phi, Top):
        return frozenset()
    if isinstance(phi, Not):
        return signals(phi.child)
    if isinstance(phi, (And, Until)):
        return signals(phi.left) | signals(phi.right)
    raise TypeError(f"not an STL formula: {phi!r}")


def max_temporal_bound(phi: Formula) -> int:
    """b_phi of paper Assumption 1: largest right endpoint of any U[a,b] (0 if none)."""
    if isinstance(phi, (Top, Predicate)):
        return 0
    if isinstance(phi, Not):
        return max_temporal_bound(phi.child)
    if isinstance(phi, And):
        return max(max_temporal_bound(phi.left), max_temporal_bound(phi.right))
    if isinstance(phi, Until):
        return max(phi.b, max_temporal_bound(phi.left), max_temporal_bound(phi.right))
    raise TypeError(f"not an STL formula: {phi!r}")


def required_horizon(phi: Formula) -> int:
    """Number of steps after t whose samples rho_phi(., t) may read.

    hrz(p) = 0, hrz(not phi) = hrz(phi), hrz(phi1 and phi2) = max,
    hrz(phi1 U[a,b] phi2) = b + max(hrz(phi1), hrz(phi2)).
    For nested temporal operators this exceeds b_phi; see docs (Assumption 1).
    """
    if isinstance(phi, (Top, Predicate)):
        return 0
    if isinstance(phi, Not):
        return required_horizon(phi.child)
    if isinstance(phi, And):
        return max(required_horizon(phi.left), required_horizon(phi.right))
    if isinstance(phi, Until):
        return phi.b + max(required_horizon(phi.left), required_horizon(phi.right))
    raise TypeError(f"not an STL formula: {phi!r}")


def with_scales(phi: Formula, scale_of) -> Formula:
    """Copy of phi with each predicate's scale set to scale_of(signal)."""
    if isinstance(phi, Top):
        return phi
    if isinstance(phi, Predicate):
        return Predicate(phi.signal, phi.op, phi.threshold, scale_of(phi.signal))
    if isinstance(phi, Not):
        return Not(with_scales(phi.child, scale_of))
    if isinstance(phi, And):
        return And(with_scales(phi.left, scale_of), with_scales(phi.right, scale_of))
    if isinstance(phi, Until):
        return Until(with_scales(phi.left, scale_of), with_scales(phi.right, scale_of), phi.a, phi.b)
    raise TypeError(f"not an STL formula: {phi!r}")


def signal_offsets(phi: Formula) -> dict[str, int]:
    """For each signal, the largest number of steps after the evaluation time at
    which rho_phi reads it (0 = only the current sample)."""
    if isinstance(phi, Top):
        return {}
    if isinstance(phi, Predicate):
        return {phi.signal: 0}
    if isinstance(phi, Not):
        return signal_offsets(phi.child)
    if isinstance(phi, (And, Until)):
        shift = phi.b if isinstance(phi, Until) else 0
        out: dict[str, int] = {}
        for child in (phi.left, phi.right):
            for sig, k in signal_offsets(child).items():
                out[sig] = max(out.get(sig, 0), k + shift)
        return out
    raise TypeError(f"not an STL formula: {phi!r}")


def to_text(phi: Formula) -> str:
    """Core-form text (derived operators appear expanded)."""
    if isinstance(phi, Top):
        return "true"
    if isinstance(phi, Predicate):
        scale = "" if phi.scale == 1.0 else f" /{phi.scale!r}"
        return f"({phi.signal} {phi.op} {phi.threshold!r}{scale})"
    if isinstance(phi, Not):
        return f"!{to_text(phi.child)}"
    if isinstance(phi, And):
        return f"({to_text(phi.left)} & {to_text(phi.right)})"
    if isinstance(phi, Until):
        return f"({to_text(phi.left)} U[{phi.a},{phi.b}] {to_text(phi.right)})"
    raise TypeError(f"not an STL formula: {phi!r}")
