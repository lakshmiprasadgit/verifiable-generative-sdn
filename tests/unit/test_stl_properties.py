"""Property-based checks of STL semantics on random formulas and traces."""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from vgcp.stl import (
    Always, And, Eventually, Not, Or, Predicate, Top, Trace, Until, Verdict, evaluate,
    required_horizon, robustness, satisfied,
)

LEN = 12
values = st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False)
traces = st.builds(
    lambda xs, ys: Trace({"x": xs, "y": ys}),
    st.lists(values, min_size=LEN, max_size=LEN),
    st.lists(values, min_size=LEN, max_size=LEN),
)
preds = st.builds(Predicate, st.sampled_from(["x", "y"]), st.sampled_from(["<=", ">="]),
                  st.integers(-5, 5).map(float))
windows = st.tuples(st.integers(0, 2), st.integers(0, 2)).map(lambda ab: (ab[0], ab[0] + ab[1]))


def _extend(children):
    return st.one_of(
        st.builds(Not, children),
        st.builds(And, children, children),
        st.builds(Or, children, children),
        st.builds(lambda w, c: Eventually(w[0], w[1], c), windows, children),
        st.builds(lambda w, c: Always(w[0], w[1], c), windows, children),
        st.builds(lambda w, l, r: Until(l, r, w[0], w[1]), windows, children, children),
    )


formulas = st.recursive(st.one_of(preds, st.just(Top())), _extend, max_leaves=5).filter(
    lambda f: required_horizon(f) < LEN
)


@settings(max_examples=300, deadline=None)
@given(formulas, traces)
def test_robustness_sign_agrees_with_boolean_semantics(phi, tr):
    rho, sat = robustness(phi, tr), satisfied(phi, tr)
    if rho > 0:
        assert sat is True
    if rho < 0:
        assert sat is False


@settings(max_examples=200, deadline=None)
@given(formulas, traces)
def test_double_negation(phi, tr):
    assert robustness(Not(Not(phi)), tr) == robustness(phi, tr)


@settings(max_examples=200, deadline=None)
@given(preds, windows, traces)
def test_always_eventually_are_window_min_max(p, w, tr):
    a, b = w
    vals = [robustness(p, tr, k) for k in range(a, b + 1)]
    assert robustness(Always(a, b, p), tr) == min(vals)
    assert robustness(Eventually(a, b, p), tr) == max(vals)


@settings(max_examples=200, deadline=None)
@given(formulas, formulas, traces)
def test_and_or_commutative(f, g, tr):
    if required_horizon(And(f, g)) < LEN:
        assert robustness(And(f, g), tr) == robustness(And(g, f), tr)
        assert robustness(Or(f, g), tr) == robustness(Or(g, f), tr)


@settings(max_examples=200, deadline=None)
@given(formulas, traces)
def test_evaluate_is_consistent(phi, tr):
    r = evaluate(phi, tr)
    assert r.verdict is not Verdict.UNKNOWN
    assert r.robustness == robustness(phi, tr)
    if r.verdict is Verdict.BOUNDARY:
        assert r.robustness == 0 and r.satisfied is not None
    assert not math.isnan(r.robustness)
