"""Hard constraints c(s, a) <= 0 (paper Eq 16)."""

import pytest

from factories import action_with, config_with, nominal_state
from vgcp.constraints import ConstraintConfig, HardConstraints
from vgcp.errors import ConfigError
from vgcp.state import NetworkState


@pytest.fixture
def hc(cfg):
    return HardConstraints(cfg.constraints, cfg.topology, cfg.slices)


def test_fallback_satisfies_all(cfg, hc):
    vec = hc.evaluate(nominal_state(cfg), cfg.fallback_action)
    assert vec.status == "satisfied"
    # 3 routing + 7 links + 6 switches + 3 slices
    assert len(vec.values) == 19


def test_link_capacity_values(cfg, hc):
    # fallback: urllc 5 on A (l12, l25), embb 100 on B (l13, l35), mmtc 5 on C
    c = hc.evaluate(nominal_state(cfg), cfg.fallback_action).as_dict()
    assert c["link_capacity.l12"] == pytest.approx(5 - 0.9 * 50)  # -40
    assert c["link_capacity.l13"] == pytest.approx(100 - 0.9 * 200)  # -80


def test_link_capacity_violation_when_sharing(cfg, hc):
    # embb (100) moved onto A with urllc (5): 105 - 45 = 60 > 0
    a = action_with(cfg, path={"embb": "A"})
    vec = hc.evaluate(nominal_state(cfg), a)
    assert vec.status == "violated"
    assert vec.as_dict()["link_capacity.l12"] == pytest.approx(60.0)


def test_link_capacity_exact_boundary_is_satisfied(cfg, hc):
    # urllc 5 + mmtc 10 + embb 30 on A = 45 = 0.9 * 50 -> c = 0 -> satisfied (c <= 0)
    a = action_with(cfg, path={"embb": "A", "mmtc": "A"},
                    rate_budget_mbps={"embb": 30.0, "mmtc": 10.0})
    c = hc.evaluate(nominal_state(cfg), a)
    assert c.as_dict()["link_capacity.l12"] == 0.0
    assert next(v for v in c.values if v.name == "link_capacity.l12").satisfied is True


def test_flow_table(cfg, hc):
    # s1 is on every path: 3 slices x 2 rules = 6 new entries
    s = nominal_state(cfg, **{"flow_table_occupancy.s1": 994.0})
    assert hc.evaluate(s, cfg.fallback_action).as_dict()["flow_table.s1"] == 0.0  # boundary
    s = nominal_state(cfg, **{"flow_table_occupancy.s1": 995.0})
    vec = hc.evaluate(s, cfg.fallback_action)
    assert vec.status == "violated" and vec.as_dict()["flow_table.s1"] == 1.0


def test_flow_table_missing_measurement_is_unknown(cfg, hc):
    s = nominal_state(cfg, **{"flow_table_occupancy.s2": None})
    vec = hc.evaluate(s, cfg.fallback_action)
    assert vec.status == "unknown"
    assert [v.name for v in vec.unknown()] == ["flow_table.s2"]


def test_violation_dominates_unknown(cfg, hc):
    s = nominal_state(cfg, **{"flow_table_occupancy.s2": None})
    vec = hc.evaluate(s, action_with(cfg, path={"embb": "A"}))
    assert vec.status == "violated"


def test_slice_min_budget(cfg, hc):
    vec = hc.evaluate(nominal_state(cfg), action_with(cfg, rate_budget_mbps={"embb": 9.5}))
    assert vec.as_dict()["slice_min_budget.embb"] == pytest.approx(0.5)
    vec = hc.evaluate(nominal_state(cfg), action_with(cfg, rate_budget_mbps={"embb": 10.0}))
    assert vec.as_dict()["slice_min_budget.embb"] == 0.0


def test_routing_through_powered_off_link(cfg, hc):
    vec = hc.evaluate(nominal_state(cfg), action_with(cfg, link_power={"l46": False}))
    assert vec.as_dict()["routing_validity.mmtc"] == 1.0
    assert "powered-off" in next(v.detail for v in vec.values if v.name == "routing_validity.mmtc")
    # powering off a link no slice uses is fine
    vec = hc.evaluate(nominal_state(cfg), action_with(cfg, path={"mmtc": "A"}, link_power={"l46": False}))
    assert vec.as_dict()["routing_validity.mmtc"] == 0.0


def test_disabled_families_are_omitted(cfg):
    def off(raw):
        for fam in ("link_capacity", "flow_table", "slice_min_budget", "routing_validity"):
            raw["constraints"][fam]["enabled"] = False
    c = config_with(off)
    hc = HardConstraints(c.constraints, c.topology, c.slices)
    vec = hc.evaluate(NetworkState(0, {}), c.fallback_action)
    assert vec.values == () and vec.status == "satisfied"
    assert hc.required_state_keys() == frozenset()


@pytest.mark.parametrize("mutate, fragment", [
    (lambda r: r["constraints"]["link_capacity"].update(max_reserved_fraction=1.5), "outside"),
    (lambda r: r["constraints"]["flow_table"].pop("max_entries_per_switch"), "missing"),
    (lambda r: r["constraints"]["slice_min_budget"]["min_rate_budget_mbps"].pop("mmtc"), "exactly"),
    (lambda r: r["constraints"].update(bogus={"enabled": True}), "unknown constraint"),
    (lambda r: r["constraints"]["routing_validity"].update(enabled="yes"), "true or false"),
])
def test_constraint_config_errors(mutate, fragment):
    with pytest.raises(ConfigError) as exc:
        config_with(mutate)
    assert fragment in str(exc.value)
