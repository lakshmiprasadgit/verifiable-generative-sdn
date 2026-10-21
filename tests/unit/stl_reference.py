"""Deliberately naive transcription of paper Eqs 8-11, used only as a test oracle.

It shares no evaluation code with vgcp.stl.robustness: no memoisation, no running
minimum, no Predicate.value(). Only the AST node types are imported. Signals are
plain lists of finite floats; missing-data handling (D7) is not part of the paper
and is not modelled here.
"""

import math

from vgcp.stl.ast import And, Not, Predicate, Top, Until


def rho(phi, x, t):
    if isinstance(phi, Top):
        return math.inf
    if isinstance(phi, Predicate):  # Eq 8, p = (c - x)/scale for '<=', (x - c)/scale for '>=' (Eq 6, D18)
        v = x[phi.signal][t]
        return (phi.threshold - v) / phi.scale if phi.op == "<=" else (v - phi.threshold) / phi.scale
    if isinstance(phi, Not):  # Eq 9
        return -rho(phi.child, x, t)
    if isinstance(phi, And):  # Eq 10
        return min(rho(phi.left, x, t), rho(phi.right, x, t))
    if isinstance(phi, Until):  # Eq 11, window for phi1 is the closed interval [t, tau]
        return max(
            min(rho(phi.right, x, tau), min(rho(phi.left, x, u) for u in range(t, tau + 1)))
            for tau in range(t + phi.a, t + phi.b + 1)
        )
    raise TypeError(phi)
