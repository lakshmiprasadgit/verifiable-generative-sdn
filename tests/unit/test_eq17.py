"""Audit finding M1: evidence for the shield's relation to the paper's Eq 17.

Eq 17:  A_Phi(s) = { a in A : rho_phi(s, a) >= rho_min for all phi in Phi,  c(s, a) <= 0 }
with rho_phi(s, a) the Eq 14 robustness of the projected trajectory (Eqs 12-13).

The shield adds documented extensions that can only remove actions: measurement
validity, the nominal model's validity domain (D12), pi_0 outputs in A, and
c <= 0 along the rollout (D3). So the expected relation is V(s, a) = 1 => a in A_Phi(s)
(soundness), with every a in A_Phi(s) that V rejects explained by one of those checks.

Evidence here, from most to least independent of the code under test:
1. the STL evaluator agrees with a naive transcription of Eqs 8-11;
2. a small instance whose accept/reject outcomes are calculated by hand;
3. a literal Eq 17 reference on a grid of A. It shares T-hat, d-bar, pi_0 and c with
   the shield, because Eq 17 is defined in terms of them; it does not share the
   shield's decision code, rollout code or STL evaluator.
"""

import itertools
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factories import NOW, action_with, config_with, nominal_demand, nominal_state
from stl_reference import rho as reference_rho
from vgcp.constraints import HardConstraints
from vgcp.models import AnalyticNominalModel, UpperBoundConstantForecast
from vgcp.shield import CheckStatus, VerificationShield
from vgcp.signals import step_signals
from vgcp.stl import Always, And, Eventually, Not, Or, Predicate, Top, Trace, Until, required_horizon, robustness

# ---------------------------------------------------------------- 1. STL evaluator vs naive Eq 8-11 oracle
LEN = 10
_values = st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False)
_preds = st.builds(Predicate, st.sampled_from(["x", "y"]), st.sampled_from(["<=", ">="]),
                   st.floats(min_value=-5, max_value=5, allow_nan=False, allow_infinity=False))
_windows = st.tuples(st.integers(0, 2), st.integers(0, 2)).map(lambda ab: (ab[0], ab[0] + ab[1]))


def _extend(children):
    return st.one_of(
        st.builds(Not, children),
        st.builds(And, children, children),
        st.builds(Or, children, children),
        st.builds(lambda w, c: Eventually(w[0], w[1], c), _windows, children),
        st.builds(lambda w, c: Always(w[0], w[1], c), _windows, children),
        st.builds(lambda w, l, r: Until(l, r, w[0], w[1]), _windows, children, children),
    )


_formulas = st.recursive(st.one_of(_preds, st.just(Top())), _extend, max_leaves=6)


@settings(max_examples=400, deadline=None)
@given(_formulas, st.lists(_values, min_size=LEN, max_size=LEN), st.lists(_values, min_size=LEN, max_size=LEN),
       st.integers(0, LEN - 1))
def test_robustness_matches_naive_eq8_to_11(phi, xs, ys, t):
    if t + required_horizon(phi) > LEN - 1:
        return
    x = {"x": xs, "y": ys}
    assert robustness(phi, Trace(x), t) == reference_rho(phi, x, t)


# ---------------------------------------------------------------- 2. hand-calculated instance
def _budget_intent_config(raw):
    # One intent on an action signal (Eq 5 allows p(s, a)); its robustness does not
    # depend on the nominal model, so the expected values below are pure arithmetic.
    raw["intents"]["intents"] = [{
        "name": "embb_budget", "formula": "G[0,10](action.rate_budget_mbps.embb >= 40.0)",
    }]
    raw["intents"]["rho_min"] = 0.5
    raw["intents"]["signal_scales"]["action.rate_budget_mbps"] = 1.0  # Mbit/s


# Fallback pi_0: urllc A @5, embb B @100, mmtc C @5; capacity limit 0.9 * C = 45 (A, C) / 180 (B).
# For k >= 1 the rollout uses pi_0, whose embb budget is 100, so rho = min(budget_0 - 40, 100 - 40).
HAND_CASES = [
    # (changes, expected rho, expected accept, working)
    ({}, 60.0, True, "rho = min(100-40, 60) = 60; c: B 100 <= 180"),
    ({"rate_budget_mbps": {"embb": 40.5}}, 0.5, True, "rho = min(0.5, 60) = 0.5 = rho_min (boundary)"),
    ({"rate_budget_mbps": {"embb": 40.25}}, 0.25, False, "rho = 0.25 < 0.5"),
    ({"path": {"embb": "A"}, "rate_budget_mbps": {"embb": 39.0}}, -1.0, False, "rho = -1; c: A 39+5 = 44 <= 45"),
    ({"path": {"embb": "A"}}, None, False, "c: A 100+5 = 105 > 45 (capacity), robustness not reached"),
    ({"path": {"urllc": "C"}}, 60.0, True, "c: C 5+5 = 10 <= 45; rho unchanged"),
]


@pytest.mark.parametrize("changes, rho_expected, accept_expected, working", HAND_CASES,
                         ids=[c[3].split(";")[0] for c in HAND_CASES])
def test_hand_calculated_eq17_instance(changes, rho_expected, accept_expected, working):
    cfg = config_with(_budget_intent_config)
    shield = VerificationShield.from_config(cfg)
    cert = shield.verify(nominal_state(cfg), nominal_demand(), action_with(cfg, **changes), NOW)
    assert cert.accepted is accept_expected, working
    if rho_expected is None:
        assert cert.check("hard_constraints_now").status is CheckStatus.FAIL
    else:
        assert cert.robustness["embb_budget"] == rho_expected


# ---------------------------------------------------------------- 3. literal Eq 17 reference
def in_eq17(cfg, state, demand, action, rho_min_of):
    """a in A_Phi(s) per Eq 17, with rho from Eqs 12-14 evaluated by the naive oracle.

    Only c(s, a) at k = 0 (Eq 17 as written), no model-domain check (not in the paper).
    If T-hat yields no value for a signal an intent needs, rho is undefined and the
    action is not in A_Phi(s).
    """
    if cfg.action_schema.validate(action):
        return False
    hc = HardConstraints(cfg.constraints, cfg.topology, cfg.slices)
    if hc.evaluate(state, action).status != "satisfied":
        return False
    model = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)
    d_bar = UpperBoundConstantForecast(cfg.demand_schema, cfg.shield.forecast_margin).forecast(demand, cfg.horizon_H)
    states, actions = [state], [action]
    for k in range(cfg.horizon_H):  # Eqs 12-13
        states.append(model.predict(states[k], actions[k], d_bar[k]).state)
        actions.append(cfg.fallback_action)  # pi_0 is static in Stage 1
    steps = [step_signals(cfg.state_schema, cfg.action_schema, s, a) for s, a in zip(states, actions)]
    x = {name: [step[name] for step in steps] for name in steps[0]}
    for it in cfg.intents:
        used = {p.signal for p in _predicates(it.formula)}
        if any(math.isnan(v) for name in used for v in x[name]):
            return False
        if reference_rho(it.formula, x, 0) < rho_min_of(it):
            return False
    return True


def _predicates(phi):
    if isinstance(phi, Predicate):
        yield phi
    for child in ("child", "left", "right"):
        if hasattr(phi, child):
            yield from _predicates(getattr(phi, child))


def _grid(cfg):
    for pu, pe, pm in itertools.product(cfg.topology.paths, repeat=3):
        for bu, be in itertools.product([1.0, 5.0, 10.0], [10.0, 40.0, 100.0, 150.0]):
            for off in (False, True):
                yield action_with(cfg, path={"urllc": pu, "embb": pe, "mmtc": pm},
                                  rate_budget_mbps={"urllc": bu, "embb": be},
                                  link_power={"l14": not off, "l46": not off, "l65": not off})


EXTENSION_CHECKS = {"nominal_model_domain", "fallback_continuation", "hard_constraints_rollout"}


def primary_failures(cert):
    """Failed checks, excluding those only skipped because an earlier check failed."""
    return {c.name for c in cert.failed()
            if not (c.status is CheckStatus.UNKNOWN and c.detail.startswith("skipped"))}


@pytest.mark.parametrize("rollout_constraints", [False, True], ids=["eq17-as-written", "with-D3"])
def test_shield_is_sound_wrt_literal_eq17_on_grid(rollout_constraints):
    cfg = config_with(lambda raw: raw["shield"].update(check_constraints_along_rollout=rollout_constraints))
    shield = VerificationShield.from_config(cfg)
    s, d = nominal_state(cfg), nominal_demand()
    counts = {"both": 0, "neither": 0, "eq17_only": 0}
    for a in _grid(cfg):
        cert = shield.verify(s, d, a, NOW)
        # One global rho_min, as in the paper's Eq 17 (per-intent margins retired, M4).
        ref = in_eq17(cfg, s, d, a, rho_min_of=lambda it: cfg.rho_min)
        if cert.accepted:
            assert ref, a  # soundness: V = 1 => a in A_Phi(s)
            counts["both"] += 1
        elif ref:
            failed = primary_failures(cert)
            assert failed and failed <= EXTENSION_CHECKS, (a, failed)  # gap explained by an extension
            counts["eq17_only"] += 1
        else:
            counts["neither"] += 1
    assert counts["both"] > 0 and counts["neither"] > 0
    if not rollout_constraints:
        # With D3 off, nothing on this grid is removed by an extension: V coincides with Eq 17.
        assert counts["eq17_only"] == 0, counts


def test_d3_removes_actions_that_eq17_admits():
    # pi_0 violates the minimum-budget constraint, so the continuation breaks c at k >= 1.
    # Eq 17 (c at k = 0 only) admits the candidate; D3 rejects it.
    cfg = config_with(lambda raw: raw["shield"]["fallback_action"]["rate_budget_mbps"].update(embb=5.0))
    a = action_with(cfg, rate_budget_mbps={"embb": 100.0})
    s, d = nominal_state(cfg), nominal_demand()
    assert in_eq17(cfg, s, d, a, rho_min_of=lambda it: it.rho_min)
    cert = VerificationShield.from_config(cfg).verify(s, d, a, NOW)
    assert not cert.accepted
    assert primary_failures(cert) == {"hard_constraints_rollout"}


def test_d12_removes_actions_that_eq17_admits():
    # Without the capacity constraint, embb 47.5 + urllc 2.4 on path A gives
    # utilization 0.998: T-hat still returns numbers (rho < 1) but is outside its
    # validity domain (> 0.95). Eq 17 with an mMTC latency intent (path C, unaffected)
    # admits the action.
    def mutate(raw):
        raw["constraints"]["link_capacity"]["enabled"] = False
        raw["intents"]["intents"] = [{"name": "mmtc_latency", "formula": "G[0,10](latency_p99_ms.mmtc <= 20.0)"}]
    cfg = config_with(mutate)
    a = action_with(cfg, path={"embb": "A"}, rate_budget_mbps={"embb": 47.5})
    s, d = nominal_state(cfg), nominal_demand()
    assert in_eq17(cfg, s, d, a, rho_min_of=lambda it: it.rho_min)
    cert = VerificationShield.from_config(cfg).verify(s, d, a, NOW)
    assert not cert.accepted and cert.nominal_model_in_domain is False
    assert primary_failures(cert) == {"nominal_model_domain"}
