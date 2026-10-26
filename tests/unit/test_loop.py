"""Closed loop: enforcement at the applier (M3), controllers, candidate generator."""

import dataclasses

import pytest

from factories import NOW, action_with, config_with, nominal_demand, nominal_state
from vgcp.loop import (
    CertifiedApplier,
    ControllerFailure,
    FallbackOnlyController,
    HeuristicCandidateGenerator,
    Observation,
    ShieldedController,
    UnauthorizedActionError,
    UncheckedApplier,
    UnshieldedController,
)
from vgcp.models import StaticFallbackPolicy
from vgcp.state import Measurement, NetworkState


class RecordingBackend:
    def __init__(self, fail=False):
        self.applied, self.fail = [], fail

    def apply(self, action):
        if self.fail:
            raise ControllerFailure("down")
        self.applied.append(action)


def _obs(cfg, t=0, now=NOW, **state):
    return Observation(t, nominal_state(cfg, now=now, **state), nominal_demand(now=now), now)


@pytest.fixture
def backend():
    return RecordingBackend()


@pytest.fixture
def applier(cfg, backend):
    return CertifiedApplier(backend, StaticFallbackPolicy(cfg.fallback_action), max_age_s=cfg.shield.max_staleness_s)


# ---------------------------------------------------------------- enforcement point
def test_certified_action_is_applied(cfg, shield, backend, applier):
    obs = _obs(cfg)
    cert = shield.verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    rec = applier.apply_certified(cfg.fallback_action, cert, obs)
    assert rec.applied and rec.kind == "certified" and backend.applied == [cfg.fallback_action]


def test_rejected_certificate_is_refused(cfg, shield, backend, applier):
    obs = _obs(cfg)
    bad = action_with(cfg, path={"embb": "A"})
    cert = shield.verify(obs.state, obs.demand, bad, obs.now_s)
    with pytest.raises(UnauthorizedActionError):
        applier.apply_certified(bad, cert, obs)
    assert backend.applied == []


def test_substituted_action_is_refused(cfg, shield, backend, applier):
    obs = _obs(cfg)
    cert = shield.verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    with pytest.raises(UnauthorizedActionError, match="does not authorize"):
        applier.apply_certified(action_with(cfg, rate_budget_mbps={"embb": 120.0}), cert, obs)
    assert backend.applied == []


def test_certificate_for_another_observation_is_refused(cfg, shield, backend, applier):
    old = _obs(cfg)
    cert = shield.verify(old.state, old.demand, cfg.fallback_action, old.now_s)
    new = _obs(cfg, **{"latency_p99_ms.urllc": 0.6})
    with pytest.raises(UnauthorizedActionError, match="different observation"):
        applier.apply_certified(cfg.fallback_action, cert, new)


def test_stale_certificate_is_refused(cfg, shield, backend, applier):
    obs = _obs(cfg)
    cert = shield.verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    later = dataclasses.replace(obs, now_s=obs.now_s + cfg.shield.max_staleness_s + 0.5)
    with pytest.raises(UnauthorizedActionError, match="age"):
        applier.apply_certified(cfg.fallback_action, cert, later)


def test_fallback_is_computed_by_the_applier_not_passed_in(cfg, backend, applier):
    # apply_fallback takes the observation, not an action: pi_0(s_t) cannot be substituted.
    rec = applier.apply_fallback(_obs(cfg), "test")
    assert rec.kind == "fallback" and backend.applied == [cfg.fallback_action]


def test_controller_failure_is_recorded_not_raised(cfg, shield):
    applier = CertifiedApplier(RecordingBackend(fail=True), StaticFallbackPolicy(cfg.fallback_action), 2.0)
    obs = _obs(cfg)
    cert = shield.verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    rec = applier.apply_certified(cfg.fallback_action, cert, obs)
    assert not rec.applied and "controller failure" in rec.detail


def test_unchecked_applier_is_only_for_baselines(cfg, backend):
    rec = UncheckedApplier(backend).apply_unchecked(action_with(cfg, path={"embb": "A"}))
    assert rec.kind == "unchecked" and rec.applied


# ---------------------------------------------------------------- controllers
def test_shielded_controller_applies_first_certified_candidate(cfg, shield, backend, applier):
    gen = HeuristicCandidateGenerator(cfg, n_random=2, seed=1)
    obs = _obs(cfg)
    rec = ShieldedController(cfg, shield, gen, applier).step(obs)
    labels = [c.label for c in gen.propose(obs)]
    first_ok = next(c for c in gen.propose(obs) if shield.verify(obs.state, obs.demand, c.action, obs.now_s).accepted)
    assert rec.kind == "certified" and rec.chosen == first_ok.label
    assert rec.n_verified == rec.n_candidates == len(labels) and 0 < rec.n_certified <= len(labels)
    assert backend.applied == [first_ok.action]


def test_shielded_controller_falls_back_on_stale_telemetry(cfg, shield, backend, applier):
    stale = Observation(0, nominal_state(cfg, now=NOW - 10), nominal_demand(now=NOW - 10), NOW)
    rec = ShieldedController(cfg, shield, HeuristicCandidateGenerator(cfg, n_random=1), applier).step(stale)
    assert rec.kind == "fallback" and rec.n_certified == 0
    assert rec.fallback_certified is False  # pi_0 cannot be certified on stale data either
    assert rec.rejection_reasons["state_measurements"] == rec.n_candidates
    assert backend.applied == [cfg.fallback_action]


def test_unshielded_controller_applies_top_candidate_and_records_shadow_verdict(cfg, shield, backend):
    gen = HeuristicCandidateGenerator(cfg, n_random=0)
    obs = _obs(cfg, **{"background_load_mbps.l13": 150.0, "background_load_mbps.l35": 150.0})
    rec = UnshieldedController(cfg, gen, UncheckedApplier(backend), shadow_shield=shield).step(obs)
    assert rec.chosen == "greedy-embb" and rec.kind == "unchecked" and rec.n_verified == 0
    assert rec.shield_would_accept is False  # greedy eMBB on a path full of background traffic
    assert backend.applied == [gen.propose(obs)[0].action]


def test_fallback_only_controller(cfg, shield, backend, applier):
    rec = FallbackOnlyController(cfg, shield, applier).step(_obs(cfg))
    assert rec.kind == "fallback" and rec.fallback_certified is True and backend.applied == [cfg.fallback_action]


# ---------------------------------------------------------------- candidate generator
def test_candidates_are_in_A_and_deterministic(cfg):
    obs = _obs(cfg)
    a = HeuristicCandidateGenerator(cfg, n_random=5, seed=7).propose(obs)
    b = HeuristicCandidateGenerator(cfg, n_random=5, seed=7).propose(obs)
    assert [c.label for c in a] == ["greedy-embb", "demand-matched", "capacity-fitted", "least-loaded-embb",
                                    "shortest-delay", "random-0", "random-1", "random-2", "random-3", "random-4"]
    assert [c.action for c in a] == [c.action for c in b]
    assert all(cfg.action_schema.is_valid(c.action) for c in a)
    c = HeuristicCandidateGenerator(cfg, n_random=5, seed=8).propose(obs)
    assert [x.action for x in a[5:]] != [x.action for x in c[5:]]


def test_capacity_fitted_shrinks_embb_to_measured_headroom(cfg):
    # 120 Mbit/s background on path B: 0.9 * 200 - 120 = 60 Mbit/s left for eMBB there,
    # path C has 0.9 * 50 - mMTC budget left; the larger room wins. The budget leaves room
    # for the meter overshoot: budget * (1 + 0.01) = 60.
    obs = _obs(cfg, **{"background_load_mbps.l13": 120.0, "background_load_mbps.l35": 120.0})
    fitted = next(c for c in HeuristicCandidateGenerator(cfg, n_random=0).propose(obs) if c.label == "capacity-fitted")
    assert fitted.action.path["embb"] == "B"
    assert fitted.action.rate_budget_mbps["embb"] == pytest.approx(60.0 / (1 + cfg.meter_overshoot))


def test_fitted_first_preference(cfg):
    gen = HeuristicCandidateGenerator(cfg, n_random=1, preference="fitted-first")
    assert [c.label for c in gen.propose(_obs(cfg))][:2] == ["capacity-fitted", "greedy-embb"]
    with pytest.raises(ValueError):
        HeuristicCandidateGenerator(cfg, preference="best")


def test_missing_measurements_are_not_read_as_zero_by_the_generator(cfg):
    """Unknown demand keeps pi_0's budget; unknown background is never 'free room'."""
    obs = _obs(cfg, **{"background_load_mbps.l13": None})
    dm = obs.demand.metrics
    obs = Observation(obs.t, obs.state, type(obs.demand)(obs.demand.t, {**dm, "offered_load_mbps.embb": Measurement(None, NOW)}),
                      obs.now_s)
    cands = {c.label: c.action for c in HeuristicCandidateGenerator(cfg, n_random=0).propose(obs)}
    assert cands["demand-matched"].rate_budget_mbps["embb"] == cfg.fallback_action.rate_budget_mbps["embb"]  # not the minimum
    assert cands["capacity-fitted"].path["embb"] != "B" and cands["least-loaded-embb"].path["embb"] != "B"
    assert all(cfg.action_schema.is_valid(a) for a in cands.values())
