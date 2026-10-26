"""The measured meter overshoot (DECISIONS 2026-10-26) is counted wherever budgets meet capacity."""

import pytest

from factories import CONFIG_DIR, action_with, config_with, nominal_demand, nominal_state
from vgcp.config import load_config
from vgcp.constraints import HardConstraints
from vgcp.errors import ConfigError
from vgcp.models.fallback import CapacityAwareFallbackPolicy
from vgcp.models.nominal import AnalyticNominalModel
from vgcp.shield import VerificationShield


def _eps(e):
    return config_with(lambda r: r["network"]["control"].update(meter_overshoot=e))


def test_configured_overshoot_is_the_measured_one():
    assert load_config(CONFIG_DIR).meter_overshoot == 0.01


@pytest.mark.parametrize("bad", [-0.1, 1.0, "x"])
def test_overshoot_must_be_a_fraction(bad):
    with pytest.raises(ConfigError, match="meter_overshoot"):
        _eps(bad)


def test_capacity_constraint_counts_budget_times_one_plus_epsilon():
    for e in (0.0, 0.1):
        cfg = _eps(e)
        c = HardConstraints(cfg.constraints, cfg.topology, cfg.slices, cfg.meter_overshoot)
        vec = c.evaluate(nominal_state(cfg), action_with(cfg, path={"embb": "A"}))
        l12 = next(v for v in vec.values if v.name == "link_capacity.l12")
        assert l12.value == pytest.approx(105 * (1 + e) - 45)


def test_nominal_model_lets_a_policed_slice_pass_its_overshoot():
    cfg = _eps(0.1)
    m = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model, cfg.meter_overshoot)
    pred = m.predict(nominal_state(cfg), action_with(cfg, rate_budget_mbps={"embb": 50.0}), nominal_demand())
    assert pred.state.value("throughput_mbps.embb") == pytest.approx(55.0)  # offered 80, budget 50 * 1.1


def test_fallback_leaves_room_for_the_overshoot():
    cfg = _eps(0.2)
    state = nominal_state(cfg, **{"background_load_mbps.l13": 120.0, "background_load_mbps.l35": 120.0})
    pi0 = CapacityAwareFallbackPolicy(cfg.fallback_action, cfg.topology, cfg.slices,
                                      cfg.constraints.max_reserved_fraction, meter_overshoot=cfg.meter_overshoot)
    a = pi0.act(state)
    assert a.path["embb"] == "B" and a.rate_budget_mbps["embb"] == pytest.approx(60.0 / 1.2)


def test_shield_wires_the_overshoot_into_model_constraints_and_fallback():
    cfg = _eps(0.05)
    sh = VerificationShield.from_config(cfg)
    assert sh.model.meter_overshoot == sh.constraints.meter_overshoot == 0.05
    assert sh.fallback.k == pytest.approx(1.05)
