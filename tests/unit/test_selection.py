"""Eq 42 selection with the Eq 27 utility (Milestone 4)."""

import pytest

from factories import config_with, nominal_demand, nominal_state
from test_loop import RecordingBackend, _obs
from vgcp.errors import ConfigError
from vgcp.loop import CertifiedApplier, HeuristicCandidateGenerator, ShieldedController
from vgcp.loop.selection import SelectionSettings, UtilityModel, select_max_utility
from vgcp.models import StaticFallbackPolicy


@pytest.fixture
def model(cfg):
    return UtilityModel(cfg)


def test_utility_terms_by_hand(cfg, model):
    st = nominal_state(cfg)
    a = cfg.fallback_action  # budgets 5 + 100 + 5
    t = model.terms(st, a)
    thr = sum(st.value(f"throughput_mbps.{s}") for s in ("urllc", "embb", "mmtc"))
    assert t["qos"] == pytest.approx(thr / 100.0)
    assert t["energy"] == pytest.approx(-st.value("energy_w") / 10.0)
    assert t["cost"] == pytest.approx(110.0 / 100.0)
    # rho: the tightest normalized predicate, here URLLC 1 ms bound vs measured latency
    lat = {s: st.value(f"latency_p99_ms.{s}") for s in ("urllc", "embb", "mmtc")}
    assert t["robustness"] == pytest.approx(min(1.0 - lat["urllc"], 40.0 - lat["embb"], 20.0 - lat["mmtc"]))
    u = 1.0 * t["qos"] + 0.1 * t["energy"] + 1.0 * t["robustness"] - 0.5 * t["cost"]
    assert model.utility(st, a) == pytest.approx(u)


def test_predicted_return_is_eq42_over_the_shields_rollout(cfg, shield, model):
    st, dm, a = nominal_state(cfg), nominal_demand(), cfg.fallback_action
    roll = shield.rollout(st, a, dm)
    assert len(roll.states) == len(roll.actions) == cfg.horizon_H + 1  # k = 0..H
    want = sum(0.9 ** k * model.utility(s, x) for k, (s, x) in enumerate(zip(roll.states, roll.actions)))
    assert model.predicted_return(shield, st, dm, a) == pytest.approx(want)


def test_selection_ranks_only_certified_candidates_and_keeps_order_on_ties(cfg, shield, model):
    obs = _obs(cfg)
    cands = HeuristicCandidateGenerator(cfg, n_random=4, seed=3).propose(obs)
    certs = [(c, shield.verify(obs.state, obs.demand, c.action, obs.now_s)) for c in cands]
    certified = [(c, cert) for c, cert in certs if cert.accepted]
    assert certified and len(certified) < len(certs)  # this state has rejected candidates too
    (best, best_cert), scores = select_max_utility(model, shield, obs, certified)
    assert best_cert.accepted and set(scores) == {c.label for c, _ in certified}
    assert scores[best.label] == max(scores.values())
    twin = [certified[0], certified[0]]  # equal scores: the first in generator order wins
    assert select_max_utility(model, shield, obs, twin)[0] is twin[0]


def test_utility_controller_applies_a_certified_highest_return_candidate(cfg, shield):
    backend = RecordingBackend()
    applier = CertifiedApplier(backend, StaticFallbackPolicy(cfg.fallback_action), cfg.shield.max_staleness_s)
    ctl = ShieldedController(cfg, shield, HeuristicCandidateGenerator(cfg, n_random=4), applier,
                             utility=UtilityModel(cfg), mode="shielded-utility")
    rec = ctl.step(_obs(cfg))
    assert rec.kind == "certified" and rec.selection == "max-utility"
    assert rec.predicted_returns[rec.chosen] == max(rec.predicted_returns.values())
    assert backend.applied and backend.applied[-1].to_dict() == rec.action
    # the greedy 150 Mbit/s eMBB reservation buys no predicted throughput here, only cost
    assert rec.chosen != "greedy-embb"


def test_first_certified_rule_is_unchanged(cfg, shield):
    applier = CertifiedApplier(RecordingBackend(), StaticFallbackPolicy(cfg.fallback_action), cfg.shield.max_staleness_s)
    rec = ShieldedController(cfg, shield, HeuristicCandidateGenerator(cfg, n_random=4), applier).step(_obs(cfg))
    assert rec.selection == "first-certified" and rec.predicted_returns == {}


@pytest.mark.parametrize("bad", [{"discount_gamma": 0.0}, {"discount_gamma": 1.5}, {"weights": {"speed": 1.0}},
                                 {"weights": {"qos": -1.0}}, {"scales": {"qos_mbps": 0.0}}])
def test_selection_settings_are_validated(bad):
    cfg = config_with(lambda raw: raw["shield"].update({"selection": bad}))
    with pytest.raises(ConfigError):
        SelectionSettings.from_config(cfg)


def test_unknown_selection_key_is_rejected_at_load():
    with pytest.raises(ConfigError):
        config_with(lambda raw: raw["shield"].update({"selection": {"gama": 0.9}}))
