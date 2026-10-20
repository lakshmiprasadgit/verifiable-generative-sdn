"""Verification shield V (paper Eq 18, Assumption 2): acceptance, rejection, unknowns."""

import itertools
import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factories import CONFIG_DIR, NOW, action_with, config_with, nominal_demand, nominal_state
from vgcp.action import ControlAction
from vgcp.config import load_config
from vgcp.constraints import HardConstraints
from vgcp.models import AnalyticNominalModel, ConservativeConstantForecast, StaticFallbackPolicy
from vgcp.shield import CheckStatus, VerificationShield
from vgcp.signals import step_signals
from vgcp.state import Demand, Measurement, NetworkState
from vgcp.stl import Trace, robustness

# Module-level instances for the hypothesis test (function-scoped fixtures are not reset between examples).
_CFG = load_config(CONFIG_DIR)
_SHIELD = VerificationShield.from_config(_CFG)

LATER_CHECKS = ["hard_constraints_now", "nominal_model_domain", "fallback_continuation",
                "hard_constraints_rollout", "intent:urllc_latency", "intent:embb_latency", "intent:mmtc_loss"]


def status(cert, name):
    return cert.check(name).status


# ---------------------------------------------------------------- acceptance
def test_accepts_fallback_in_nominal_conditions(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.accepted, [(c.name, c.detail) for c in cert.failed()]
    assert all(c.status is CheckStatus.PASS for c in cert.checks)
    assert [c.name for c in cert.checks] == ["action_valid", "state_measurements", "demand_measurements", *LATER_CHECKS]
    # urllc: measured 0.5 ms at k=0 (rho 0.5); predicted 0.59861 ms for k>=1 (rho 0.40139) -> min
    assert cert.robustness["urllc_latency"] == pytest.approx(1.0 - 0.598604, abs=1e-5)
    # mmtc: measured and predicted loss 0 -> rho = 0.02 - 0 = 0.02
    assert cert.robustness["mmtc_loss"] == pytest.approx(0.02)
    assert cert.horizon_H == 10 and cert.config_hash == cfg.config_hash


def test_certificate_is_json_serializable(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, path={"embb": "A"}), NOW)
    json.dumps(cert.to_dict(), allow_nan=False)


# ---------------------------------------------------------------- invalid actions
@pytest.mark.parametrize("action", [
    "not an action",
    None,
    ControlAction({"urllc": "Z", "embb": "B", "mmtc": "C"}, {"urllc": 5.0, "embb": 100.0, "mmtc": 5.0},
                  {"urllc": 50, "embb": 20, "mmtc": 500}, {"l14": True, "l46": True, "l65": True}),
])
def test_rejects_invalid_action(cfg, shield, action):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action, NOW)
    assert not cert.accepted
    assert status(cert, "action_valid") is CheckStatus.FAIL
    for name in LATER_CHECKS:
        assert status(cert, name) is CheckStatus.UNKNOWN  # never PASS when a prerequisite failed


def test_rejects_out_of_bounds_budget(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, rate_budget_mbps={"urllc": 10.5}), NOW)
    assert not cert.accepted and status(cert, "action_valid") is CheckStatus.FAIL


# ---------------------------------------------------------------- hard constraints
def test_rejects_capacity_violation(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, path={"embb": "A"}), NOW)
    assert not cert.accepted
    assert status(cert, "hard_constraints_now") is CheckStatus.FAIL
    assert cert.constraints_now["link_capacity.l12"] == pytest.approx(60.0)


def test_rejects_route_over_powered_off_link(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, link_power={"l14": False}), NOW)
    assert not cert.accepted and status(cert, "hard_constraints_now") is CheckStatus.FAIL


def test_rejects_full_flow_table(cfg, shield):
    s = nominal_state(cfg, **{"flow_table_occupancy.s1": 999.0})
    cert = shield.verify(s, nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted and status(cert, "hard_constraints_now") is CheckStatus.FAIL


# ---------------------------------------------------------------- missing / stale telemetry
@pytest.mark.parametrize("key", ["latency_p99_ms.urllc", "loss_rate.mmtc", "flow_table_occupancy.s4"])
def test_missing_required_state_metric_rejects(cfg, shield, key):
    metrics = dict(nominal_state(cfg).metrics)
    del metrics[key]
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    c = cert.check("state_measurements")
    assert c.status is CheckStatus.UNKNOWN and c.data["problems"] == {key: "missing"}
    for name in LATER_CHECKS:
        assert status(cert, name) is CheckStatus.UNKNOWN


def test_missing_unrequired_metric_does_not_block(cfg, shield):
    # jitter is not read by any configured check
    metrics = dict(nominal_state(cfg).metrics)
    del metrics["jitter_ms.embb"]
    assert shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW).accepted


@pytest.mark.parametrize("measurement, problem", [
    (Measurement(0.5, NOW - 2.5), "stale"),
    (Measurement(0.5, NOW + 1.0), "future_timestamp"),
    (Measurement(0.5, None), "no_timestamp"),
    (Measurement(math.nan, NOW), "non_finite"),
    (Measurement(-1.0, NOW), "out_of_bounds"),
])
def test_unusable_measurement_rejects(cfg, shield, measurement, problem):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = measurement
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("state_measurements").data["problems"] == {"latency_p99_ms.urllc": problem}


def test_staleness_boundary_accepts(cfg, shield):
    s = nominal_state(cfg, now=NOW - 2.0)  # exactly max_staleness_s old
    assert shield.verify(s, nominal_demand(), cfg.fallback_action, NOW).accepted


# Audit finding C1: non-finite timestamps must never lead to acceptance.
NON_FINITE = pytest.mark.parametrize("timestamp", [math.nan, math.inf, -math.inf], ids=["nan", "+inf", "-inf"])


@NON_FINITE
def test_non_finite_state_timestamp_never_accepted(cfg, shield, timestamp):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(0.5, timestamp)
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    c = cert.check("state_measurements")
    assert c.status is CheckStatus.UNKNOWN
    assert c.data["problems"] == {"latency_p99_ms.urllc": "invalid_timestamp"}
    for name in LATER_CHECKS:
        assert status(cert, name) is CheckStatus.UNKNOWN


@NON_FINITE
def test_non_finite_demand_timestamp_never_accepted(cfg, shield, timestamp):
    metrics = dict(nominal_demand().metrics)
    metrics["offered_load_mbps.embb"] = Measurement(80.0, timestamp)
    cert = shield.verify(nominal_state(cfg), Demand(0, metrics), cfg.fallback_action, NOW)
    assert not cert.accepted
    c = cert.check("demand_measurements")
    assert c.status is CheckStatus.UNKNOWN
    assert c.data["problems"] == {"offered_load_mbps.embb": "invalid_timestamp"}


@NON_FINITE
def test_all_timestamps_non_finite_never_accepted(cfg, shield, timestamp):
    # Audit probe P1b: every state and demand timestamp non-finite.
    s = NetworkState(0, {k: Measurement(m.value, timestamp) for k, m in nominal_state(cfg).metrics.items()})
    d = Demand(0, {k: Measurement(m.value, timestamp) for k, m in nominal_demand().metrics.items()})
    cert = shield.verify(s, d, cfg.fallback_action, NOW)
    assert not cert.accepted
    assert set(cert.check("state_measurements").data["problems"].values()) == {"invalid_timestamp"}
    assert set(cert.check("demand_measurements").data["problems"].values()) == {"invalid_timestamp"}


def test_finite_timestamps_still_accepted(cfg, shield):
    # Control for the C1 tests: same inputs with an ordinary, fresh timestamp.
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(0.5, NOW - 1.0)
    assert shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW).accepted


@settings(max_examples=300, deadline=None)
@given(st.floats(allow_nan=True, allow_infinity=True))
def test_acceptance_requires_finite_fresh_timestamp(timestamp):
    metrics = dict(nominal_state(_CFG).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(0.5, timestamp)
    cert = _SHIELD.verify(NetworkState(0, metrics), nominal_demand(), _CFG.fallback_action, NOW)
    if cert.accepted:
        assert math.isfinite(timestamp)
        assert NOW - _CFG.shield.max_staleness_s <= timestamp <= NOW


def test_unknown_metric_key_rejects(cfg, shield):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.video"] = Measurement(1.0, NOW)
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("state_measurements").data["problems"] == {"latency_p99_ms.video": "unknown_key"}


def test_missing_demand_rejects(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(**{"active_devices.embb": None}), cfg.fallback_action, NOW)
    assert not cert.accepted and status(cert, "demand_measurements") is CheckStatus.UNKNOWN


@pytest.mark.parametrize("now", [math.nan, math.inf, None, "1000"])
def test_invalid_clock_rejects(cfg, shield, now):
    assert not shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, now).accepted


def test_wrong_input_types_reject(cfg, shield):
    assert not shield.verify({"t": 0}, nominal_demand(), cfg.fallback_action, NOW).accepted
    assert not shield.verify(nominal_state(cfg), nominal_state(cfg), cfg.fallback_action, NOW).accepted


# ---------------------------------------------------------------- STL intents
def test_current_measured_violation_rejects(cfg, shield):
    # Eq 14 evaluates from s-hat_t = s_t: a measured 1.2 ms already violates G[0,10](lat <= 1)
    cert = shield.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": 1.2}), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert status(cert, "intent:urllc_latency") is CheckStatus.FAIL
    assert cert.robustness["urllc_latency"] == pytest.approx(-0.2)


def test_rejects_predicted_intent_violation(cfg, shield):
    # urllc moved onto B with embb: ~16 ms latency > 1 ms; constraints still hold
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, path={"urllc": "B"}), NOW)
    assert not cert.accepted
    assert status(cert, "hard_constraints_now") is CheckStatus.PASS
    assert status(cert, "intent:urllc_latency") is CheckStatus.FAIL
    assert status(cert, "intent:embb_latency") is CheckStatus.PASS


def test_robustness_below_margin_rejects_even_if_satisfied(cfg, shield):
    # measured 0.97 ms: satisfied (rho = 0.03 > 0) but rho < rho_min = 0.05
    cert = shield.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": 0.97}), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.robustness["urllc_latency"] == pytest.approx(0.03)
    assert not cert.accepted and status(cert, "intent:urllc_latency") is CheckStatus.FAIL


def _shield_with_budget_intent(threshold):
    def mutate(raw):
        raw["intents"]["intents"] = [{
            "name": "embb_budget", "formula": f"G[0,10](action.rate_budget_mbps.embb >= {threshold})",
            "rho_min": 0.5,
        }]
    return VerificationShield.from_config(config_with(mutate))


def test_rho_exactly_rho_min_is_accepted(cfg):
    # 100.0 - 99.5 = 0.5 exactly (binary-exact numbers), rho >= rho_min holds
    sh = _shield_with_budget_intent(99.5)
    cert = sh.verify(nominal_state(sh.cfg), nominal_demand(), sh.cfg.fallback_action, NOW)
    assert cert.robustness["embb_budget"] == 0.5 and cert.accepted


def test_rho_just_below_rho_min_is_rejected(cfg):
    sh = _shield_with_budget_intent(99.75)
    cert = sh.verify(nominal_state(sh.cfg), nominal_demand(), sh.cfg.fallback_action, NOW)
    assert cert.robustness["embb_budget"] == 0.25 and not cert.accepted


def test_top_intent_set(cfg):
    sh = VerificationShield.from_config(config_with(lambda r: r["intents"].update(intents=[])))
    cert = sh.verify(nominal_state(sh.cfg), nominal_demand(), sh.cfg.fallback_action, NOW)
    assert cert.accepted and cert.robustness == {"true": math.inf}


# ---------------------------------------------------------------- rollout / model domain
def test_out_of_domain_rollout_rejects():
    # with capacity checks off, embb 48 + urllc 2.4 on A pushes utilization > 0.95
    def mutate(raw):
        raw["constraints"]["link_capacity"]["enabled"] = False
    sh = VerificationShield.from_config(config_with(mutate))
    a = action_with(sh.cfg, path={"embb": "A"}, rate_budget_mbps={"embb": 48.0})
    cert = sh.verify(nominal_state(sh.cfg), nominal_demand(), a, NOW)
    assert not cert.accepted
    assert status(cert, "hard_constraints_now") is CheckStatus.PASS
    assert status(cert, "nominal_model_domain") is CheckStatus.UNKNOWN
    assert cert.nominal_model_in_domain is False
    assert status(cert, "intent:urllc_latency") is CheckStatus.UNKNOWN


def test_constraints_checked_along_rollout(cfg):
    # The candidate satisfies c at k=0, but the pi_0 continuation (embb budget 5 < minimum 10)
    # violates c at k >= 1. Paper Eq 17 checks k=0 only; the configurable rollout check catches it.
    def mutate(raw):
        raw["shield"]["fallback_action"]["rate_budget_mbps"]["embb"] = 5.0  # < min budget 10
    c = config_with(mutate)
    sh = VerificationShield.from_config(c)
    candidate = action_with(c, rate_budget_mbps={"embb": 100.0})
    cert = sh.verify(nominal_state(c), nominal_demand(), candidate, NOW)
    assert status(cert, "hard_constraints_now") is CheckStatus.PASS
    assert status(cert, "hard_constraints_rollout") is CheckStatus.FAIL
    assert not cert.accepted

    def mutate_off(raw):
        mutate(raw)
        raw["shield"]["check_constraints_along_rollout"] = False
    c2 = config_with(mutate_off)
    sh2 = VerificationShield.from_config(c2)
    assert sh2.verify(nominal_state(c2), nominal_demand(), action_with(c2, rate_budget_mbps={"embb": 100.0}), NOW).accepted


def test_invalid_fallback_continuation_rejects(cfg):
    class BrokenFallback:
        def act(self, state):
            return "garbage"
    names = [s.name for s in cfg.slices]
    sh = VerificationShield(
        cfg, AnalyticNominalModel(cfg.topology, names, cfg.nominal_model), BrokenFallback(),
        ConservativeConstantForecast(cfg.demand_schema, 0.2),
        HardConstraints(cfg.constraints, cfg.topology, cfg.slices),
    )
    cert = sh.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted and status(cert, "fallback_continuation") is CheckStatus.FAIL


def test_internal_error_is_never_accepted(cfg):
    class ExplodingModel:
        def predict(self, *a):
            raise RuntimeError("boom")
        def required_state_keys(self):
            return frozenset()
        def required_demand_keys(self):
            return frozenset()
        def unmodelled_state_keys(self):
            return frozenset()
    sh = VerificationShield(
        cfg, ExplodingModel(), StaticFallbackPolicy(cfg.fallback_action),
        ConservativeConstantForecast(cfg.demand_schema, 0.2),
        HardConstraints(cfg.constraints, cfg.topology, cfg.slices),
    )
    cert = sh.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert status(cert, "internal_error") is CheckStatus.UNKNOWN and "boom" in cert.check("internal_error").detail


# ---------------------------------------------------------------- Eq 17 consistency
def _in_feasible_set(cfg, state, demand, action):
    """The shield's *extended* feasible set: Eq 17 plus the domain check (D12) and,
    if enabled, c along the rollout (D3). Built from the same T-hat, c, forecast and
    STL evaluator as the shield, so this is a regression/consistency check, not
    independent evidence; see test_eq17.py for the comparison with Eq 17 itself."""
    if cfg.action_schema.validate(action):
        return False
    names = [s.name for s in cfg.slices]
    model = AnalyticNominalModel(cfg.topology, names, cfg.nominal_model)
    hc = HardConstraints(cfg.constraints, cfg.topology, cfg.slices)
    if hc.evaluate(state, action).status != "satisfied":
        return False
    d_bar = [demand_k for demand_k in ConservativeConstantForecast(cfg.demand_schema, cfg.shield.forecast_margin).forecast(demand, cfg.horizon_H)]
    states, actions = [state], [action]
    for k in range(cfg.horizon_H):
        pred = model.predict(states[-1], actions[-1], d_bar[k])
        if not pred.in_domain:
            return False
        states.append(pred.state)
        actions.append(cfg.fallback_action)
        if cfg.shield.check_constraints_along_rollout and hc.evaluate(pred.state, cfg.fallback_action).status != "satisfied":
            return False
    trace = Trace.from_steps([step_signals(cfg.state_schema, cfg.action_schema, s, a) for s, a in zip(states, actions)])
    for it in cfg.intents:
        rho = robustness(it.formula, trace, 0)
        if math.isnan(rho) or rho < it.rho_min:
            return False
    return True


def test_shield_matches_extended_feasible_set_on_action_grid(cfg, shield):
    """V = 1 iff a is in the extended feasible set (see _in_feasible_set) on a grid of A."""
    s, d = nominal_state(cfg), nominal_demand()
    paths = cfg.topology.paths
    accepted = rejected = 0
    for pu, pe, pm in itertools.product(paths, repeat=3):
        for bu, be in itertools.product([1.0, 5.0, 10.0], [10.0, 40.0, 100.0, 150.0]):
            for off in (False, True):
                a = action_with(cfg, path={"urllc": pu, "embb": pe, "mmtc": pm},
                                rate_budget_mbps={"urllc": bu, "embb": be},
                                link_power={"l14": not off, "l46": not off, "l65": not off})
                v = shield.verify(s, d, a, NOW).accepted
                assert v == _in_feasible_set(cfg, s, d, a), a
                accepted += v
                rejected += not v
    assert accepted > 0 and rejected > 0  # the grid exercises both outcomes


@settings(max_examples=150, deadline=None)
@given(
    st.sampled_from(["A", "B", "C"]), st.sampled_from(["A", "B", "C"]), st.sampled_from(["A", "B", "C"]),
    st.floats(0.0, 12.0), st.floats(0.0, 200.0), st.floats(0.0, 12.0),
    st.integers(0, 600), st.booleans(), st.floats(0.0, 1.2),
)
def test_acceptance_implies_every_check_passed(path_u, path_e, path_m, bu, be, bm, adm, power, lat):
    """Property: accepted => all checks PASS, every rho >= rho_min, every c <= 0."""
    cfg = _CFG
    a = ControlAction({"urllc": path_u, "embb": path_e, "mmtc": path_m},
                      {"urllc": bu, "embb": be, "mmtc": bm},
                      {"urllc": 50, "embb": 20, "mmtc": adm},
                      {"l14": power, "l46": True, "l65": True})
    cert = _SHIELD.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": lat}), nominal_demand(), a, NOW)
    if cert.accepted:
        assert all(c.status is CheckStatus.PASS for c in cert.checks)
        assert all(v is not None and v <= 0 for v in cert.constraints_now.values())
        for it in cfg.intents:
            assert cert.robustness[it.name] >= it.rho_min
        assert cfg.action_schema.is_valid(a)
    else:
        assert any(c.status is not CheckStatus.PASS for c in cert.checks)
