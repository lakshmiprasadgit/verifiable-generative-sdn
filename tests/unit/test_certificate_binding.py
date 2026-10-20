"""Audit finding M3: a certificate must be bound to the exact action (and inputs) it certified."""

import dataclasses
import json
import math

import pytest

from factories import NOW, action_with, nominal_demand, nominal_state
from vgcp.action import ControlAction
from vgcp.state import Measurement, NetworkState


@pytest.fixture
def certified(cfg, shield):
    a = action_with(cfg)
    cert = shield.verify(nominal_state(cfg), nominal_demand(), a, NOW)
    assert cert.accepted
    return a, cert


# ---------------------------------------------------------------- 1. post-certification mutation
@pytest.mark.parametrize("field, key, value", [
    ("path", "embb", "A"),
    ("rate_budget_mbps", "embb", 150.0),
    ("admission_limit", "mmtc", 1),
    ("link_power", "l14", False),
])
def test_certified_action_cannot_be_mutated(certified, field, key, value):
    a, cert = certified
    with pytest.raises(TypeError):
        getattr(a, field)[key] = value
    with pytest.raises(TypeError):
        del getattr(a, field)[key]
    assert cert.authorizes(a)


def test_caller_dict_does_not_alias_action(cfg, shield):
    path = {"urllc": "A", "embb": "B", "mmtc": "C"}
    fb = cfg.fallback_action
    a = ControlAction(path, dict(fb.rate_budget_mbps), dict(fb.admission_limit), dict(fb.link_power))
    cert = shield.verify(nominal_state(cfg), nominal_demand(), a, NOW)
    path["urllc"] = "B"  # edit the dict the action was built from
    assert a.path["urllc"] == "A"
    assert cert.accepted and cert.authorizes(a)


def test_fields_cannot_be_reassigned(certified):
    a, cert = certified
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.path = {"urllc": "B", "embb": "B", "mmtc": "B"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        cert.action_fingerprint = "forged"


# ---------------------------------------------------------------- 2. action substitution
@pytest.mark.parametrize("changes", [
    {"path": {"embb": "A"}},
    {"rate_budget_mbps": {"embb": 99.0}},
    {"admission_limit": {"mmtc": 499}},
    {"link_power": {"l14": False}},
])
def test_certificate_does_not_authorize_a_different_action(cfg, certified, changes):
    _, cert = certified
    assert not cert.authorizes(action_with(cfg, **changes))


def test_certificate_records_the_certified_action(certified):
    a, cert = certified
    assert cert.action == a
    assert isinstance(cert.action_fingerprint, str) and len(cert.action_fingerprint) == 64


@pytest.mark.parametrize("other", [None, "action", {"path": {}}, 42])
def test_authorizes_fails_closed_on_non_actions(certified, other):
    _, cert = certified
    assert not cert.authorizes(other)


def test_rejected_certificate_authorizes_nothing(cfg, shield):
    a = action_with(cfg, path={"embb": "A"})  # violates link capacity
    cert = shield.verify(nominal_state(cfg), nominal_demand(), a, NOW)
    assert not cert.accepted
    assert not cert.authorizes(a)


def test_certificate_for_invalid_action_has_no_binding(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), "not an action", NOW)
    assert not cert.accepted and cert.action is None and cert.action_fingerprint is None
    assert not cert.authorizes("not an action")


# ---------------------------------------------------------------- 3. input context is recorded
def test_certificate_records_input_context(cfg, shield):
    s, d = nominal_state(cfg), nominal_demand()
    cert = shield.verify(s, d, cfg.fallback_action, NOW)
    assert cert.now_s == NOW and cert.t == s.t and cert.config_hash == cfg.config_hash
    # a changed state or demand yields a different recorded fingerprint
    s2 = nominal_state(cfg, **{"latency_p99_ms.urllc": 0.6})
    d2 = nominal_demand(**{"offered_load_mbps.embb": 81.0})
    cert_s2 = shield.verify(s2, d, cfg.fallback_action, NOW)
    cert_d2 = shield.verify(s, d2, cfg.fallback_action, NOW)
    assert cert_s2.accepted and cert_d2.accepted
    assert cert_s2.state_fingerprint != cert.state_fingerprint
    assert cert_s2.demand_fingerprint == cert.demand_fingerprint
    assert cert_d2.demand_fingerprint != cert.demand_fingerprint
    # a changed timestamp is a changed input
    s3 = nominal_state(cfg, now=NOW - 1.0)
    assert shield.verify(s3, d, cfg.fallback_action, NOW).state_fingerprint != cert.state_fingerprint
    # same inputs -> same fingerprints (deterministic)
    again = shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert (again.state_fingerprint, again.demand_fingerprint) == (cert.state_fingerprint, cert.demand_fingerprint)


def test_input_fingerprint_is_order_independent(cfg, shield):
    s = nominal_state(cfg)
    reordered = NetworkState(s.t, dict(reversed(list(s.metrics.items()))))
    a = shield.verify(s, nominal_demand(), cfg.fallback_action, NOW)
    b = shield.verify(reordered, nominal_demand(), cfg.fallback_action, NOW)
    assert a.state_fingerprint == b.state_fingerprint


# ---------------------------------------------------------------- 4. unmodified control
def test_unmodified_action_is_authorized(certified):
    a, cert = certified
    assert cert.authorizes(a)


# ---------------------------------------------------------------- 5. copy / serialization paths
def test_equivalent_reconstructions_are_authorized(cfg, certified):
    a, cert = certified
    assert cert.authorizes(ControlAction.from_dict(a.to_dict()))
    assert cert.authorizes(cfg.action_schema.from_vector(cfg.action_schema.to_vector(a)))
    assert cert.authorizes(ControlAction.from_dict(json.loads(json.dumps(a.to_dict()))))


def test_int_and_float_budgets_are_the_same_action(cfg, shield):
    a_int = action_with(cfg, rate_budget_mbps={"embb": 100})
    a_float = action_with(cfg, rate_budget_mbps={"embb": 100.0})
    cert = shield.verify(nominal_state(cfg), nominal_demand(), a_int, NOW)
    assert cert.authorizes(a_float)


def test_float_admission_limit_is_not_the_certified_integer(cfg, certified):
    # 50.0 is not a valid admission limit (A requires an int), so it must not be authorized
    _, cert = certified
    d = cfg.fallback_action.to_dict()
    d["admission_limit"]["urllc"] = 50.0
    assert not cert.authorizes(ControlAction.from_dict(d))


def test_to_dict_carries_the_binding(certified):
    a, cert = certified
    out = cert.to_dict()
    json.dumps(out, allow_nan=False)
    assert out["action"] == a.to_dict()
    assert out["action_fingerprint"] == cert.action_fingerprint
    assert out["now_s"] == NOW
    assert out["state_fingerprint"] == cert.state_fingerprint


def test_non_finite_budget_has_no_fingerprint(cfg, certified):
    _, cert = certified
    d = cfg.fallback_action.to_dict()
    d["rate_budget_mbps"]["embb"] = math.nan
    assert not cert.authorizes(ControlAction.from_dict(d))


def test_unusable_measurement_values_still_fingerprint(cfg, shield):
    # a rejected certificate for odd inputs must still be constructible (no crash)
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urllc"] = Measurement(math.nan, math.nan)
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted and isinstance(cert.state_fingerprint, str)
