"""Analytical nominal model T-hat, demand forecast d-bar and static fallback pi_0."""

import math

import pytest

from factories import action_with, nominal_demand, nominal_state
from vgcp.models import AnalyticNominalModel, UpperBoundConstantForecast, StaticFallbackPolicy
from vgcp.state import Demand

LN100 = math.log(100.0)


@pytest.fixture
def model(cfg):
    return AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)


def test_urllc_latency_hand_calculation(cfg, model):
    # urllc on path A (l12, l25: 50 Mbit/s, 0.1 ms each), offered 2.4 Mbit/s, budget 5:
    #   rho = 2.4 / 50 = 0.048
    #   S   = 64 B * 8 / 50e6 s = 0.01024 ms
    #   hop = 0.1 + 0.05 + ln(100) * 0.01024 / (1 - 0.048)
    #   latency = 1.5 * 2 * hop
    d = nominal_demand(**{"offered_load_mbps.urllc": 2.4})
    pred = model.predict(nominal_state(cfg), cfg.fallback_action, d)
    hop = 0.1 + 0.05 + LN100 * 0.01024 / (1 - 0.048)
    assert pred.in_domain is True
    assert pred.state.value("link_utilization.l12") == pytest.approx(0.048)
    assert pred.state.value("latency_p99_ms.urllc") == pytest.approx(1.5 * 2 * hop)
    assert pred.state.value("latency_p99_ms.urllc") == pytest.approx(0.59861, abs=1e-5)
    assert pred.state.value("throughput_mbps.urllc") == pytest.approx(2.4)
    assert pred.state.t == 1


def test_budget_and_admission_limit_load(cfg, model):
    # mmtc: 400 devices offering 8 Mbit/s, admission 100 -> 25 % admitted -> 2 Mbit/s (< budget 5)
    d = nominal_demand(**{"offered_load_mbps.mmtc": 8.0, "active_devices.mmtc": 400.0})
    a = action_with(cfg, admission_limit={"mmtc": 100})
    pred = model.predict(nominal_state(cfg), a, d)
    assert pred.state.value("throughput_mbps.mmtc") == pytest.approx(2.0)
    assert pred.state.value("active_users.mmtc") == 100.0
    # embb offered 80, budget 100 -> 80; budget 50 -> policed to 50
    pred = model.predict(nominal_state(cfg), action_with(cfg, rate_budget_mbps={"embb": 50.0}), nominal_demand())
    assert pred.state.value("throughput_mbps.embb") == 50.0


def test_shared_link_uses_largest_packet(cfg, model):
    # urllc and embb both on A: S = 1514 B frame / 50 Mbit/s = 0.24224 ms
    a = action_with(cfg, path={"embb": "A"}, rate_budget_mbps={"embb": 20.0})
    pred = model.predict(nominal_state(cfg), a, nominal_demand())
    rho = (2.0 + 20.0) / 50
    hop = 0.1 + 0.05 + LN100 * 0.24224 / (1 - rho)
    assert pred.state.value("latency_p99_ms.urllc") == pytest.approx(1.5 * 2 * hop)


def test_out_of_domain_utilization(cfg, model):
    # embb 48 + urllc 2 on A -> rho = 1.0 > 0.95
    a = action_with(cfg, path={"embb": "A"}, rate_budget_mbps={"embb": 48.0})
    pred = model.predict(nominal_state(cfg), a, nominal_demand())
    assert pred.in_domain is False
    assert math.isnan(pred.state.value("latency_p99_ms.urllc"))  # rho >= 1: no prediction
    assert any("utilization" in n for n in pred.notes)


def test_missing_demand_is_out_of_domain(cfg, model):
    d = nominal_demand(**{"offered_load_mbps.embb": None})
    pred = model.predict(nominal_state(cfg), cfg.fallback_action, d)
    assert pred.in_domain is False
    assert math.isnan(pred.state.value("throughput_mbps.embb"))


def test_load_on_powered_off_link_is_out_of_domain(cfg, model):
    pred = model.predict(nominal_state(cfg), action_with(cfg, link_power={"l46": False}), nominal_demand())
    assert pred.in_domain is False


def test_energy_proxy(cfg, model):
    # all 7 links on: 7 * 1.0 W idle + 2.0 W * sum of utilizations
    pred = model.predict(nominal_state(cfg), cfg.fallback_action, nominal_demand())
    utils = sum(pred.state.value(f"link_utilization.{l}") for l in cfg.topology.links)
    assert pred.state.value("energy_w") == pytest.approx(7.0 + 2.0 * utils)
    # unused path C switched off saves its idle power
    a = action_with(cfg, path={"mmtc": "A"}, link_power={"l14": False, "l46": False, "l65": False})
    pred_off = model.predict(nominal_state(cfg), a, nominal_demand())
    assert pred_off.state.value("energy_w") < pred.state.value("energy_w")


def test_forecast(cfg):
    fc = UpperBoundConstantForecast(cfg.demand_schema, 0.2)
    out = fc.forecast(nominal_demand(**{"active_devices.urllc": None}), 3)
    assert len(out) == 3 and all(isinstance(d, Demand) for d in out)
    assert [d.t for d in out] == [0, 1, 2]
    assert out[2].value("offered_load_mbps.embb") == pytest.approx(96.0)
    assert math.isnan(out[0].value("active_devices.urllc"))
    with pytest.raises(ValueError):
        UpperBoundConstantForecast(cfg.demand_schema, -0.1)


def test_static_fallback(cfg):
    pi0 = StaticFallbackPolicy(cfg.fallback_action)
    assert pi0.act(nominal_state(cfg)) is cfg.fallback_action
