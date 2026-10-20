"""Hand-calculated STL robustness cases (paper Eqs 8-11).

Every expected value below was computed by hand from the equations; the
working is shown in the comments.
"""

import math

import pytest

from vgcp.stl import (
    Always, And, Eventually, Not, Or, Predicate, Top, Trace, TraceTooShortError, UnknownSignalError,
    Until, Verdict, evaluate, false, max_temporal_bound, parse, required_horizon, robustness, satisfied,
)

# x:      3   1  -2   4   0
X = Trace({"x": [3.0, 1.0, -2.0, 4.0, 0.0]})
x_ge_0 = Predicate("x", ">=", 0.0)  # p = x - 0


# ---------------------------------------------------------------- atomic, Eq 8
def test_predicate_ge():
    assert robustness(x_ge_0, X, 0) == 3.0
    assert robustness(x_ge_0, X, 2) == -2.0


def test_predicate_le_matches_eq6():
    # Eq 6: p = L_max - latency, L_max = 1 ms, latency 0.6 ms -> 0.4
    tr = Trace({"lat": [0.6]})
    assert robustness(Predicate("lat", "<=", 1.0), tr) == pytest.approx(0.4)


# ---------------------------------------------------------------- negation / conjunction
def test_negation_eq9():
    assert robustness(Not(x_ge_0), X, 0) == -3.0


def test_conjunction_eq10():
    # min(x - 0, 2 - x) at t=0: min(3, -1) = -1
    phi = And(x_ge_0, Predicate("x", "<=", 2.0))
    assert robustness(phi, X, 0) == -1.0
    # at t=1: min(1, 1) = 1
    assert robustness(phi, X, 1) == 1.0


def test_disjunction_derived():
    # Or = not(not a and not b) = max(a, b): t=0 -> max(3, -1) = 3
    assert robustness(Or(x_ge_0, Predicate("x", "<=", 2.0)), X, 0) == 3.0


# ---------------------------------------------------------------- temporal
def test_always_violated():
    # G[0,2](x>=0) at 0 = min(3, 1, -2) = -2
    r = evaluate(Always(0, 2, x_ge_0), X, 0)
    assert r.robustness == -2.0 and r.verdict is Verdict.VIOLATED and r.satisfied is False


def test_always_satisfied():
    # G[0,1](x>=0) at 0 = min(3, 1) = 1
    r = evaluate(Always(0, 1, x_ge_0), X, 0)
    assert r.robustness == 1.0 and r.verdict is Verdict.SATISFIED and r.satisfied is True


def test_always_boundary_zero():
    # G[0,1](x>=0) at 3 = min(4, 0) = 0 -> boundary; qualitatively 0 >= 0 holds
    r = evaluate(Always(0, 1, x_ge_0), X, 3)
    assert r.robustness == 0.0 and r.verdict is Verdict.BOUNDARY and r.satisfied is True


def test_eventually_windows():
    assert robustness(Eventually(0, 2, x_ge_0), X, 0) == 3.0  # max(3, 1, -2)
    assert robustness(Eventually(1, 2, x_ge_0), X, 0) == 1.0  # max(1, -2)
    assert robustness(Eventually(2, 2, x_ge_0), X, 0) == -2.0  # only tau = 2
    assert robustness(Eventually(0, 0, x_ge_0), X, 4) == 0.0  # point window at the last sample


def test_eventually_violated():
    # F[0,2](x >= 5) at 0 = max(-2, -4, -7) = -2
    r = evaluate(Eventually(0, 2, Predicate("x", ">=", 5.0)), X, 0)
    assert r.robustness == -2.0 and r.verdict is Verdict.VIOLATED


def test_until_eq11():
    # y = [5, 2, 1, -1, 3]  phi1 = y >= 0 -> rho1 = [5, 2, 1, -1, 3]
    # x = [0, 1, 3, 6, 2]   phi2 = x >= 2 -> rho2 = [-2, -1, 1, 4, 0]
    # phi1 U[0,3] phi2 at t=0:
    #   tau=0: min(-2, min(5))          = -2
    #   tau=1: min(-1, min(5,2))        = -1
    #   tau=2: min( 1, min(5,2,1))      =  1
    #   tau=3: min( 4, min(5,2,1,-1))   = -1
    #   max = 1
    tr = Trace({"y": [5, 2, 1, -1, 3], "x": [0, 1, 3, 6, 2]})
    phi = Until(Predicate("y", ">=", 0), Predicate("x", ">=", 2), 0, 3)
    r = evaluate(phi, tr, 0)
    assert r.robustness == 1.0 and r.satisfied is True
    # U[3,3] at 0: only tau=3 -> -1 (phi1 fails at u=3)
    assert robustness(Until(phi.left, phi.right, 3, 3), tr, 0) == -1.0


def test_until_uses_closed_interval_t_tau():
    # Paper Eq 11 takes min over u in [t, tau] INCLUDING tau.
    # rho1 = [1, 1, -1], rho2 = [-1, -1, 5]; phi1 U[2,2] phi2 at 0:
    #   closed [0,2]:   min(5, min(1, 1, -1)) = -1   <- paper
    #   half-open [0,2): min(5, min(1, 1))    =  1   (other literature)
    tr = Trace({"a": [1, 1, -1], "b": [-1, -1, 5]})
    phi = Until(Predicate("a", ">=", 0), Predicate("b", ">=", 0), 2, 2)
    assert robustness(phi, tr, 0) == -1.0
    assert satisfied(phi, tr, 0) is False


def test_derived_operators_expand_to_core():
    p = x_ge_0
    assert Eventually(1, 3, p) == Until(Top(), p, 1, 3)
    assert Always(1, 3, p) == Not(Until(Top(), Not(p), 1, 3))
    assert Or(p, p) == Not(And(Not(p), Not(p)))


def test_top_and_false():
    assert robustness(Top(), X, 0) == math.inf
    assert robustness(false(), X, 0) == -math.inf
    assert robustness(Eventually(0, 2, Top()), X, 0) == math.inf
    assert evaluate(Top(), X, 0).verdict is Verdict.SATISFIED


def test_nested_temporal_operator():
    # G[0,1] F[0,1] (x>=0) at 0:
    #   F[0,1] at 0 = max(3, 1) = 3 ; at 1 = max(1, -2) = 1 ; G = min(3, 1) = 1
    assert robustness(Always(0, 1, Eventually(0, 1, x_ge_0)), X, 0) == 1.0


# ---------------------------------------------------------------- missing data
def test_missing_sample_outside_window_is_ignored():
    tr = Trace({"x": [3.0, None, 2.0]})
    assert robustness(x_ge_0, tr, 0) == 3.0


def test_missing_sample_inside_window_is_unknown():
    tr = Trace({"x": [3.0, None, 2.0]})
    for phi in (Always(0, 2, x_ge_0), Eventually(0, 2, x_ge_0)):
        r = evaluate(phi, tr, 0)
        # even F, which a known 3.0 would satisfy, is UNKNOWN: no partial evaluation
        assert r.verdict is Verdict.UNKNOWN and r.robustness is None and r.satisfied is None


def test_infinite_sample_is_invalid():
    tr = Trace({"x": [math.inf, 1.0]})
    assert ("x", 0) in tr.invalid
    assert evaluate(x_ge_0, tr, 0).verdict is Verdict.UNKNOWN


def test_non_numeric_sample_rejected():
    with pytest.raises(TypeError):
        Trace({"x": [1.0, "2"]})


def test_unknown_signal_raises():
    with pytest.raises(UnknownSignalError):
        robustness(Predicate("nope", ">=", 0), X, 0)


def test_from_steps_absent_name_is_missing():
    tr = Trace.from_steps([{"x": 1.0, "y": 2.0}, {"x": 1.0}])
    assert math.isnan(tr.value("y", 1))


# ---------------------------------------------------------------- horizons
def test_horizons():
    phi = Always(0, 5, Eventually(0, 3, x_ge_0))
    assert max_temporal_bound(phi) == 5  # paper's b_phi
    assert required_horizon(phi) == 8  # samples actually read: 5 + 3
    assert required_horizon(Until(x_ge_0, x_ge_0, 2, 4)) == 4


def test_trace_too_short():
    with pytest.raises(TraceTooShortError):
        robustness(Always(0, 2, x_ge_0), X, 3)  # needs index 5, trace has 0..4
    # exactly long enough is fine
    assert robustness(Always(0, 1, x_ge_0), X, 3) == 0.0


def test_bad_inputs():
    with pytest.raises(ValueError):
        Until(Top(), Top(), 3, 2)
    with pytest.raises(ValueError):
        Until(Top(), Top(), -1, 2)
    with pytest.raises(ValueError):
        Until(Top(), Top(), 0, 1.5)
    with pytest.raises(ValueError):
        Predicate("x", "<", 1.0)
    with pytest.raises(ValueError):
        Predicate("x", "<=", math.nan)
    with pytest.raises(ValueError):
        robustness(x_ge_0, X, -1)
    with pytest.raises(ValueError):
        Trace({"x": [1.0], "y": [1.0, 2.0]})


def test_parsed_formula_evaluates_like_constructed():
    assert robustness(parse("G[0,2](x >= 0)"), X, 0) == robustness(Always(0, 2, x_ge_0), X, 0)
