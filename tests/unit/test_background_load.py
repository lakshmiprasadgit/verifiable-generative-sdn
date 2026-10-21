"""Audit finding H1: traffic outside the managed slices must count against link capacity.

The state carries per-link background_load_mbps: the link's measured rate minus the
rates of the managed slices' flows on it (both available from OpenFlow port and flow
statistics in Milestone 2). The capacity constraint becomes
    sum of reserved budgets on l + background_l - f_max * C_l <= 0
and the nominal model adds the background to each link's load.
"""

import math

import pytest

from factories import NOW, action_with, nominal_demand, nominal_state
from vgcp.constraints import HardConstraints
from vgcp.models import AnalyticNominalModel
from vgcp.shield import CheckStatus
from vgcp.state import NetworkState

BG = "background_load_mbps"


def test_state_schema_has_background_load_per_link(cfg):
    assert {f"{BG}.{lid}" for lid in cfg.topology.links} <= set(cfg.state_schema.keys)
    assert cfg.state_schema.specs[f"{BG}.l12"].unit == "Mbit/s"


@pytest.fixture
def hc(cfg):
    return HardConstraints(cfg.constraints, cfg.topology, cfg.slices)


def test_capacity_constraint_counts_background(cfg, hc):
    # path A: urllc budget 5 + background 41 = 46 > 0.9 * 50 = 45
    c = hc.evaluate(nominal_state(cfg, **{f"{BG}.l12": 41.0}), cfg.fallback_action).as_dict()
    assert c["link_capacity.l12"] == pytest.approx(1.0)
    # exactly at the limit is satisfied: 5 + 40 - 45 = 0
    c = hc.evaluate(nominal_state(cfg, **{f"{BG}.l12": 40.0}), cfg.fallback_action).as_dict()
    assert c["link_capacity.l12"] == 0.0


def test_missing_background_makes_capacity_unknown(cfg, hc):
    vec = hc.evaluate(nominal_state(cfg, **{f"{BG}.l13": None}), cfg.fallback_action)
    assert vec.status == "unknown"
    assert "link_capacity.l13" in [v.name for v in vec.unknown()]


def test_background_is_a_required_measurement(cfg, shield):
    assert f"{BG}.l25" in shield.required_state_keys
    metrics = dict(nominal_state(cfg).metrics)
    del metrics[f"{BG}.l25"]
    cert = shield.verify(NetworkState(0, metrics), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("state_measurements").data["problems"] == {f"{BG}.l25": "missing"}


def test_link_saturated_by_background_is_not_certified(cfg, shield):
    # Audit probe P8: path A carried by unmanaged traffic. Before H1 this was accepted.
    s = nominal_state(cfg, **{f"{BG}.l12": 48.0, f"{BG}.l25": 48.0})
    cert = shield.verify(s, nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted
    assert cert.check("hard_constraints_now").status is CheckStatus.FAIL


def test_nominal_model_adds_background_to_utilization(cfg):
    model = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)
    s = nominal_state(cfg, **{f"{BG}.l12": 10.0})
    pred = model.predict(s, cfg.fallback_action, nominal_demand(**{"offered_load_mbps.urllc": 2.4}))
    # (2.4 urllc + 10 background) / 50
    assert pred.state.value("link_utilization.l12") == pytest.approx(12.4 / 50)
    assert pred.state.value(f"{BG}.l12") == 10.0  # carried forward
    # urllc latency rises with the background on l12 only (rho 0.248); l25 stays at 0.048
    def hop(rho):
        return 0.1 + 0.05 + math.log(100) * 0.01024 / (1 - rho)
    assert pred.state.value("latency_p99_ms.urllc") == pytest.approx(1.5 * (hop(0.248) + hop(0.048)))


def test_background_can_push_the_model_out_of_domain(cfg):
    model = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)
    pred = model.predict(nominal_state(cfg, **{f"{BG}.l12": 46.0}), cfg.fallback_action, nominal_demand())
    assert pred.in_domain is False


def test_background_is_declared_unmodelled(cfg):
    # The model carries it forward unchanged, so intents may not read it ahead (M5 rule).
    model = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)
    assert {f"{BG}.{lid}" for lid in cfg.topology.links} <= model.unmodelled_state_keys()


def test_background_on_unused_link_does_not_block(cfg, shield):
    # path C carries mmtc at 5 Mbit/s: 5 + 39 = 44 <= 45
    s = nominal_state(cfg, **{f"{BG}.l14": 39.0, f"{BG}.l46": 39.0, f"{BG}.l65": 39.0})
    assert shield.verify(s, nominal_demand(), cfg.fallback_action, NOW).accepted
    assert not shield.verify(s, nominal_demand(), action_with(cfg, rate_budget_mbps={"mmtc": 7.0}), NOW).accepted
