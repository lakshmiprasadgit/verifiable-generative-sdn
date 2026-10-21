"""Audit finding H3: a measured violation must not make the fallback uncertifiable.

Eq 14 evaluates intents on the trajectory starting at the measured state (s-hat_t = s_t).
With intents of the form G[0,H] p, a violation already present in s_t makes every
action, including pi_0, fail, contradicting Assumption 3. The configured intents are
therefore recovery-style, G[1,H] p: only the measured slot k = 0 is excused. Eq 14 is
unchanged. Wider windows such as F[0,2] G[0,8] p are unsafe here: Eq 13 applies the
candidate for one step, so its effect appears only at k = 1, and a window starting
at k = 2 would never see it. The certificate records which intents the measured
state currently violates, so the closed loop can log it.
"""

import pytest

from factories import NOW, action_with, config_with, nominal_demand, nominal_state
from vgcp.shield import CheckStatus, VerificationShield
from vgcp.stl import Trace, parse, robustness

FG = "F[0,2] G[0,8] (x <= 1.0)"


def test_recovery_formula_hand_calculated():
    # x: 1.2 at k=0, then 0.6 for k=1..10.  p = 1 - x: -0.2, then 0.4.
    # tau=0: min over k=0..8 = -0.2;  tau=1: min over k=1..9 = 0.4;  tau=2: 0.4  -> rho = 0.4
    tr = Trace({"x": [1.2] + [0.6] * 10})
    assert robustness(parse(FG), tr, 0) == pytest.approx(0.4)
    # Same trace under G[0,10]: the measured violation decides it.
    assert robustness(parse("G[0,10](x <= 1.0)"), tr, 0) == pytest.approx(-0.2)


def test_recovery_too_late_is_violated():
    # Still above 1 at k=0..2, so no tau in [0, 2] starts a satisfied 8-slot window.
    tr = Trace({"x": [1.2, 1.1, 1.05] + [0.6] * 8})
    assert robustness(parse(FG), tr, 0) == pytest.approx(-0.05)


def test_configured_latency_intents_are_recovery_style(cfg):
    formulas = {i.name: i.text for i in cfg.intents}
    assert formulas == {
        "urllc_latency": "G[1,10](latency_p99_ms.urllc <= 1.0)",
        "embb_latency": "G[1,10](latency_p99_ms.embb <= 40.0)",
        "mmtc_latency": "G[1,10](latency_p99_ms.mmtc <= 20.0)",
    }


def test_measurement_only_loss_intent_is_disabled(cfg):
    raw = {i["name"]: i for i in cfg.raw["intents"]["intents"]}
    assert raw["mmtc_loss"]["enabled"] is False
    assert "mmtc_loss" not in {i.name for i in cfg.intents}


def test_fallback_is_certifiable_during_a_measured_violation(cfg, shield):
    # Measured URLLC latency 1.2 ms; pi_0 keeps URLLC on path A, predicted 0.5986 ms.
    cert = shield.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": 1.2}), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.accepted
    assert cert.robustness["urllc_latency"] == pytest.approx(1.0 - 0.598604, abs=1e-5)
    assert cert.measured_violations == ("urllc_latency: latency_p99_ms.urllc",)
    assert cert.to_dict()["measured_violations"] == ["urllc_latency: latency_p99_ms.urllc"]


def test_no_measured_violation_is_recorded_normally(cfg, shield):
    cert = shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert cert.accepted and cert.measured_violations == ()


def test_persistent_predicted_violation_is_still_rejected(cfg, shield):
    # URLLC moved onto the high-delay path B: it never recovers.
    cert = shield.verify(nominal_state(cfg, **{"latency_p99_ms.urllc": 1.2}), nominal_demand(),
                         action_with(cfg, path={"urllc": "B"}), NOW)
    assert not cert.accepted
    assert cert.check("intent:urllc_latency").status is CheckStatus.FAIL


def test_wider_recovery_window_would_hide_the_candidates_effect():
    # Why the configured intents use G[1,10] and not F[0,2] G[0,8]: URLLC moved onto the
    # 10 ms path B violates at k = 1 only (pi_0 moves it back from k = 1 on), and a
    # window starting at k = 2 never sees it - the shield would certify the bad action.
    def fg(raw):
        raw["intents"]["intents"] = [{"name": "u", "formula": "F[0,2] G[0,8] (latency_p99_ms.urllc <= 1.0)"}]
    cfg = config_with(fg)
    bad = action_with(cfg, path={"urllc": "B"})
    assert VerificationShield.from_config(cfg).verify(nominal_state(cfg), nominal_demand(), bad, NOW).accepted
    def g1(raw):
        raw["intents"]["intents"] = [{"name": "u", "formula": "G[1,10](latency_p99_ms.urllc <= 1.0)"}]
    cfg = config_with(g1)
    assert not VerificationShield.from_config(cfg).verify(nominal_state(cfg), nominal_demand(), bad, NOW).accepted


def test_hold_only_intent_keeps_eq14_semantics():
    # An explicit G[0,10] intent is still decided by the measured state (Eq 14 unchanged).
    cfg = config_with(lambda r: r["intents"].update(
        intents=[{"name": "hold", "formula": "G[0,10](latency_p99_ms.urllc <= 1.0)"}]))
    cert = VerificationShield.from_config(cfg).verify(
        nominal_state(cfg, **{"latency_p99_ms.urllc": 1.2}), nominal_demand(), cfg.fallback_action, NOW)
    assert not cert.accepted and cert.robustness["hold"] == pytest.approx(-0.2)
    assert cert.measured_violations == ("hold: latency_p99_ms.urllc",)
