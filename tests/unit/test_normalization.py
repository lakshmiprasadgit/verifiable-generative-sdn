"""Audit finding M4: robustness is unitless, so one rho_min (Eq 17) and minima over
intents (Eqs 27, 40) compare like with like.

Each signal family has a declared scale (configs/intents.yaml signal_scales) and a
predicate's value is p = (c - x) / scale for 'x <= c' and (x - c) / scale for 'x >= c'.
Positive scaling never changes whether a predicate holds, only the size of the margin.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factories import NOW, config_with, nominal_demand, nominal_state
from vgcp.errors import ConfigError
from vgcp.shield import VerificationShield
from vgcp.stl import Predicate, Trace, parse, robustness, satisfied


def test_scaled_predicate_value():
    assert Predicate("x", "<=", 1.0, 0.5).value(0.6) == pytest.approx(0.8)  # (1.0 - 0.6) / 0.5
    assert Predicate("x", ">=", 10.0, 4.0).value(12.0) == 0.5  # (12 - 10) / 4
    assert Predicate("x", "<=", 1.0).scale == 1.0  # parsed predicates start unscaled


@pytest.mark.parametrize("scale", [0, -1.0, float("nan"), float("inf"), True])
def test_scale_must_be_positive_and_finite(scale):
    with pytest.raises(ValueError):
        Predicate("x", "<=", 1.0, scale)


@settings(max_examples=200, deadline=None)
@given(st.floats(-100, 100), st.floats(-100, 100), st.floats(0.001, 1000), st.sampled_from(["<=", ">="]))
def test_scaling_never_changes_satisfaction(x, c, scale, op):
    tr = Trace({"x": [x]})
    assert satisfied(Predicate("x", op, c, scale), tr) == satisfied(Predicate("x", op, c), tr)


def test_configured_scales_are_applied(cfg):
    scales = cfg.raw["intents"]["signal_scales"]
    assert scales == {"latency_p99_ms": 1.0, "loss_rate": 0.01}
    urllc = next(i for i in cfg.intents if i.name == "urllc_latency")
    preds = {p.signal: p.scale for p in _predicates(urllc.formula)}
    assert preds == {"latency_p99_ms.urllc": 1.0}


def _predicates(phi):
    if isinstance(phi, Predicate):
        yield phi
    for child in ("child", "left", "right"):
        if hasattr(phi, child):
            yield from _predicates(getattr(phi, child))


def _intents(*items, scales=None):
    def mutate(raw):
        raw["intents"]["intents"] = [dict(i) for i in items]
        if scales is not None:
            raw["intents"]["signal_scales"] = scales
    return mutate


def test_mixed_units_compare_on_one_scale():
    # latency 0.5 ms against 1 ms (scale 1 ms) -> 0.5; loss 0.019 against 0.02 (scale 0.01) -> 0.1.
    # Without normalization the minimum would be the raw loss margin 0.001.
    cfg = config_with(_intents({"name": "x", "formula": "(latency_p99_ms.urllc <= 1.0) & (loss_rate.mmtc <= 0.02)"}))
    cert = VerificationShield.from_config(cfg).verify(
        nominal_state(cfg, **{"loss_rate.mmtc": 0.019}), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.robustness["x"] == pytest.approx(0.1)


def test_single_global_rho_min_applies_to_every_intent(cfg):
    assert {i.rho_min for i in cfg.intents} == {cfg.rho_min}


def test_per_intent_rho_min_is_rejected():
    with pytest.raises(ConfigError) as exc:
        config_with(_intents({"name": "x", "formula": "latency_p99_ms.urllc <= 1.0", "rho_min": 0.5}))
    assert "'rho_min'" in str(exc.value)


def test_every_used_signal_family_needs_a_scale():
    with pytest.raises(ConfigError) as exc:
        config_with(_intents({"name": "x", "formula": "G[0,10](jitter_ms.urllc <= 2.0)"}))
    assert "jitter_ms" in str(exc.value) and "signal_scales" in str(exc.value)


def test_action_signal_families_can_be_scaled():
    cfg = config_with(_intents({"name": "x", "formula": "action.rate_budget_mbps.embb >= 40"},
                               scales={"latency_p99_ms": 1.0, "action.rate_budget_mbps": 10.0}))
    cert = VerificationShield.from_config(cfg).verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.robustness["x"] == pytest.approx(6.0)  # (100 - 40) / 10


@pytest.mark.parametrize("scales, fragment", [
    ({"latency_p99_ms": 0.0, "loss_rate": 0.01}, "must be >"),
    ({"latency_p99_ms": -1.0, "loss_rate": 0.01}, "must be >"),
    ({"latency_p99_ms": "1 ms", "loss_rate": 0.01}, "finite number"),
    ({"latency_p99_ms": 1.0, "loss_rate": 0.01, "latncy_p99_ms": 1.0}, "unknown signal family"),
])
def test_invalid_scales_are_rejected(scales, fragment):
    with pytest.raises(ConfigError) as exc:
        config_with(lambda raw: raw["intents"].update(signal_scales=scales))
    assert fragment in str(exc.value)


def test_parse_is_unaffected():
    assert parse("x <= 1") == Predicate("x", "<=", 1.0)
