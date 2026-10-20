"""Low-severity audit findings L1, L2 (shield reporting and input robustness)."""

import math

import pytest

from factories import NOW, action_with, config_with, nominal_demand, nominal_state
from vgcp.errors import ConfigError, InvalidActionError
from vgcp.shield import CheckStatus, VerificationShield
from vgcp.state import Measurement, NetworkState
from vgcp.stl import ParseError, Trace, parse

HUGE = 10**400  # a valid Python int that cannot be converted to float


# ---------------------------------------------------------------- L1: a disabled check is not a PASS
def test_disabled_rollout_constraint_check_is_not_applicable():
    cfg = config_with(lambda raw: raw["shield"].update(check_constraints_along_rollout=False))
    cert = VerificationShield.from_config(cfg).verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    check = cert.check("hard_constraints_rollout")
    assert check.status is CheckStatus.NOT_APPLICABLE
    assert cert.accepted and check not in cert.failed()
    assert cert.to_dict()["checks"][[c.name for c in cert.checks].index("hard_constraints_rollout")]["status"] == "not_applicable"


def test_enabled_rollout_constraint_check_is_a_real_check(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.check("hard_constraints_rollout").status is CheckStatus.PASS
    assert all(c.status is not CheckStatus.NOT_APPLICABLE for c in cert.checks)


# ---------------------------------------------------------------- L2: no raw exceptions from odd inputs
@pytest.mark.parametrize("mutate", [
    lambda r: r["shield"]["measurements"].update(max_staleness_s=HUGE),
    lambda r: r["shield"]["fallback_action"]["rate_budget_mbps"].update(embb=HUGE),
    lambda r: r["shield"]["nominal_model"].update(latency_safety_factor=HUGE),
    lambda r: r["shield"]["nominal_model"]["mean_packet_size_bytes"].update(embb=HUGE),
    lambda r: r["constraints"]["flow_table"].update(max_entries_per_switch=HUGE),
    lambda r: r["network"]["topology"]["links"][0].update(capacity_mbps=HUGE),
], ids=["staleness", "fallback-budget", "safety-factor", "packet-size", "flow-table", "capacity"])
def test_huge_integers_in_config_raise_config_error(mutate):
    with pytest.raises(ConfigError):
        config_with(mutate)


def test_deeply_nested_formula_raises_config_error():
    deep = "!" * 5000 + "(latency_p99_ms.urllc <= 1.0)"
    with pytest.raises(ConfigError) as exc:
        config_with(lambda r: r["intents"].update(intents=[{"name": "deep", "formula": deep}]))
    assert "too deeply nested" in str(exc.value)


@pytest.mark.parametrize("text", ["x <= 1e999", "x >= -1e999"])
def test_overflowing_threshold_is_a_parse_error(text):
    with pytest.raises(ParseError) as exc:
        parse(text)
    assert "finite" in str(exc.value)


def test_huge_integer_measurement_is_rejected_as_non_finite(cfg, shield):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(HUGE, NOW)
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("state_measurements").data["problems"] == {"latency_p99_ms.urllc": "non_finite"}


def test_huge_integer_timestamp_is_rejected(cfg, shield):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(0.5, HUGE)
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("state_measurements").data["problems"] == {"latency_p99_ms.urllc": "invalid_timestamp"}


def test_huge_integer_budget_is_an_invalid_action(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, rate_budget_mbps={"embb": HUGE}), NOW)
    assert not cert.accepted
    assert cert.check("action_valid").status is CheckStatus.FAIL
    assert all(c.name != "internal_error" for c in cert.checks)


def test_huge_integer_in_action_vector_is_rejected(cfg):
    vec = cfg.action_schema.to_vector(cfg.fallback_action)
    vec[1] = HUGE
    with pytest.raises(InvalidActionError):
        cfg.action_schema.from_vector(vec)


def test_huge_integer_trace_sample_is_invalid():
    tr = Trace({"x": [HUGE, 1.0]})
    assert ("x", 0) in tr.invalid and math.isnan(tr.value("x", 0))


# ---------------------------------------------------------------- L4: property tests are reproducible
def test_hypothesis_default_profile_is_deterministic():
    import os

    from hypothesis import settings

    if os.environ.get("HYPOTHESIS_PROFILE", "deterministic") != "deterministic":
        pytest.skip("a non-default Hypothesis profile was selected explicitly")
    assert settings.default.derandomize is True
    assert settings.default.database is None


# ---------------------------------------------------------------- L6: intent time bounds are tied to the slot length
def test_intents_declare_the_slot_duration_they_were_written_for(cfg):
    assert cfg.raw["intents"]["slot_duration_s"] == cfg.delta_t_s == 1.0


def test_changing_delta_t_without_revisiting_intents_is_rejected():
    with pytest.raises(ConfigError) as exc:
        config_with(lambda r: r["network"]["control"].update(delta_t_s=0.1))
    assert "slot_duration_s" in str(exc.value) and "delta_t_s" in str(exc.value)


def test_slot_duration_is_required():
    with pytest.raises(ConfigError) as exc:
        config_with(lambda r: r["intents"].pop("slot_duration_s", None))
    assert "slot_duration_s" in str(exc.value)


def test_consistent_change_of_both_is_accepted():
    def mutate(r):
        r["network"]["control"]["delta_t_s"] = 0.5
        r["intents"]["slot_duration_s"] = 0.5
    assert config_with(mutate).delta_t_s == 0.5


# ---------------------------------------------------------------- L7: names do not claim unestablished properties
def test_forecast_type_name_states_what_it_is(cfg):
    from vgcp.models import UpperBoundConstantForecast

    assert cfg.raw["shield"]["demand_forecast"]["type"] == "upper_bound_constant"
    assert isinstance(VerificationShield.from_config(cfg).forecast, UpperBoundConstantForecast)


def test_old_forecast_type_name_is_rejected():
    with pytest.raises(ConfigError) as exc:
        config_with(lambda r: r["shield"]["demand_forecast"].update(type="conservative_constant"))
    assert "upper_bound_constant" in str(exc.value)


# ---------------------------------------------------------------- L8: rho >= rho_min is an exact float comparison
def test_rho_min_comparison_is_exact_floating_point(cfg, shield):
    # Measured URLLC latency 0.95 ms against the 1 ms bound: rho = 1.0 - 0.95, which in
    # binary floating point is 0.050000000000000044, just above rho_min = 0.05. The
    # shield compares exactly (no tolerance), so this is accepted. Values within
    # rounding error of rho_min can fall either side; choose rho_min with that in mind.
    rho = 1.0 - 0.95
    assert rho != 0.05 and rho > 0.05
    cert = shield.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": 0.95}), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.robustness["urllc_latency"] == rho
    assert cert.accepted
