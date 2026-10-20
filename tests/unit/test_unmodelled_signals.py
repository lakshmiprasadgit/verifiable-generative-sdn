"""Audit finding M5: intents must not read, over the rollout, signals the nominal model does not predict.

The analytic model's loss output is a placeholder (0 inside its validity domain) and
flow-table occupancy is carried forward unchanged. An intent that reads such a signal
at a future step would only ever test the placeholder, so it would look like a
guarantee over the horizon while checking nothing. Reading it at offset 0 (the
measured state s_t) is meaningful and allowed.
"""

import pytest

from factories import NOW, config_with, nominal_demand, nominal_state
from vgcp.errors import ConfigError
from vgcp.models import AnalyticNominalModel
from vgcp.shield import CheckStatus, VerificationShield
from vgcp.stl import parse, signal_offsets


@pytest.mark.parametrize("text, expected", [
    ("x <= 1", {"x": 0}),
    ("G[0,5](x <= 1)", {"x": 5}),
    ("F[2,3](x <= 1) & y >= 0", {"x": 3, "y": 0}),
    ("G[0,5] F[0,3] (x <= 1)", {"x": 8}),
    ("(x <= 1) U[1,4] (y >= 0)", {"x": 4, "y": 4}),
    ("true", {}),
])
def test_signal_offsets(text, expected):
    assert signal_offsets(parse(text)) == expected


def test_nominal_model_declares_placeholder_outputs(cfg):
    model = AnalyticNominalModel(cfg.topology, [s.name for s in cfg.slices], cfg.nominal_model)
    unmodelled = model.unmodelled_state_keys()
    assert {f"loss_rate.{s}" for s in ("urllc", "embb", "mmtc")} <= unmodelled
    assert {f"flow_table_occupancy.{sw}" for sw in cfg.topology.switches} <= unmodelled
    assert not any(k.startswith(("latency_p99_ms.", "link_utilization.")) for k in unmodelled)


def _with_intent(formula):
    def mutate(raw):
        raw["intents"]["intents"] = [{"name": "x", "formula": formula}]
    return mutate


@pytest.mark.parametrize("formula, signal", [
    ("G[0,10](loss_rate.mmtc <= 0.02)", "loss_rate.mmtc"),
    ("F[1,1](loss_rate.urllc <= 0.001)", "loss_rate.urllc"),
    ("G[0,10](flow_table_occupancy.s1 <= 900)", "flow_table_occupancy.s1"),
    ("G[0,10](latency_p99_ms.urllc <= 1.0) & G[0,2](loss_rate.embb <= 0.1)", "loss_rate.embb"),
])
def test_shield_rejects_intents_reading_unmodelled_signals_ahead(formula, signal):
    cfg = config_with(_with_intent(formula))
    with pytest.raises(ConfigError) as exc:
        VerificationShield.from_config(cfg)
    assert "'x'" in str(exc.value) and signal in str(exc.value)


@pytest.mark.parametrize("formula", [
    "loss_rate.mmtc <= 0.02",
    "G[0,10](latency_p99_ms.urllc <= 1.0) & (loss_rate.mmtc <= 0.02)",
    "G[0,0](flow_table_occupancy.s1 <= 900)",
])
def test_measurement_only_reads_are_allowed(formula):
    VerificationShield.from_config(config_with(_with_intent(formula)))


def test_measurement_only_loss_intent_uses_the_measured_value():
    cfg = config_with(_with_intent("loss_rate.mmtc <= 0.02"))
    shield = VerificationShield.from_config(cfg)
    ok = shield.verify(nominal_state(cfg), nominal_demand(), cfg.fallback_action, NOW)
    assert ok.accepted and ok.robustness["x"] == 0.02
    bad = shield.verify(nominal_state(cfg, **{"loss_rate.mmtc": 0.03}), nominal_demand(), cfg.fallback_action, NOW)
    assert not bad.accepted and bad.check("intent:x").status is CheckStatus.FAIL


def test_repository_intents_satisfy_the_rule(cfg):
    VerificationShield.from_config(cfg)
    mmtc = next(i for i in cfg.intents if i.name == "mmtc_loss")
    assert signal_offsets(mmtc.formula) == {"loss_rate.mmtc": 0}
