"""State-dependent fallback pi_0(s) (paper Eq 13) and its effect on certification."""

import pytest

from factories import NOW, action_with, config_with, nominal_demand, nominal_state
from vgcp.errors import ConfigError
from vgcp.models import CapacityAwareFallbackPolicy
from vgcp.shield import VerificationShield, fallback_policy

BG = "background_load_mbps"


def _policy(cfg):
    return CapacityAwareFallbackPolicy(cfg.fallback_action, cfg.topology, cfg.slices,
                                       cfg.constraints.max_reserved_fraction)


def _bg_on_b(cfg, mbps):
    return nominal_state(cfg, **{f"{BG}.l13": mbps, f"{BG}.l35": mbps})


def test_unchanged_when_the_static_action_fits(cfg):
    assert _policy(cfg).act(nominal_state(cfg)) == cfg.fallback_action


def test_shrinks_embb_on_its_path_when_that_still_has_the_most_room(cfg):
    # B: 0.9*200 - 120 = 60 Mbit/s room; C: 0.9*50 - 5 (mMTC) = 40; A: 45 - 5 (URLLC) = 40
    a = _policy(cfg).act(_bg_on_b(cfg, 120.0))
    assert a.path["embb"] == "B" and a.rate_budget_mbps["embb"] == pytest.approx(60.0)
    assert {s: a.path[s] for s in ("urllc", "mmtc")} == {"urllc": "A", "mmtc": "C"}  # others untouched


def test_moves_embb_when_another_path_has_more_room(cfg):
    a = _policy(cfg).act(_bg_on_b(cfg, 175.0))  # B room 5; A and C have 40
    assert a.path["embb"] in ("A", "C") and a.rate_budget_mbps["embb"] == pytest.approx(40.0)


def test_budget_never_leaves_A(cfg):
    # No path has room: B 0.9*200 - 190 = -10; A and C 0.9*50 - 49 - 5 = -9.
    bg = {f"{BG}.{l}": 49.0 for l in cfg.topology.links} | {f"{BG}.l13": 190.0, f"{BG}.l35": 190.0}
    a = _policy(cfg).act(nominal_state(cfg, **bg))
    assert cfg.action_schema.is_valid(a)
    assert a.rate_budget_mbps["embb"] == cfg.slices[1].rate_budget_mbps[0]  # clipped to the lower bound


def test_without_background_measurement_it_is_static(cfg):
    assert _policy(cfg).act(nominal_state(cfg, **{f"{BG}.l13": None})) == cfg.fallback_action


def test_shipped_default_is_capacity_aware(cfg):
    # chosen on the 2026-10-21 ablation (docs/EXPERIMENTS.md, docs/DECISIONS.md)
    assert cfg.shield.fallback_policy == "capacity_aware"


def test_config_selects_the_policy():
    c = config_with(lambda r: r["shield"].update(fallback_policy="capacity_aware"))
    assert isinstance(fallback_policy(c), CapacityAwareFallbackPolicy)
    with pytest.raises(ConfigError, match="fallback_policy"):
        config_with(lambda r: r["shield"].update(fallback_policy="smart"))


def test_capacity_aware_continuation_makes_a_fitting_candidate_certifiable():
    # Under 120 Mbit/s background on B, the static pi_0 (eMBB 100 on B) breaks capacity
    # along the rollout, so no candidate can be certified. With pi_0(s) the continuation
    # fits, and a candidate that fits is certified.
    fitted = lambda c: action_with(c, rate_budget_mbps={"embb": 60.0})
    static = config_with(lambda r: r["shield"].update(fallback_policy="static"))
    aware = config_with(lambda r: r["shield"].update(fallback_policy="capacity_aware"))
    for c, expected in ((static, False), (aware, True)):
        s = _bg_on_b(c, 120.0)
        cert = VerificationShield.from_config(c).verify(s, nominal_demand(), fitted(c), NOW)
        assert cert.accepted is expected
