"""Configuration loading and validation, including Assumption 1 (horizon sufficiency)."""

import pytest

from factories import CONFIG_DIR, config_with, raw_config
from vgcp.config import build_config, config_hash, load_config
from vgcp.errors import ConfigError
from vgcp.stl import Top


def test_repository_config_loads(cfg):
    assert cfg.horizon_H == 10
    assert cfg.delta_t_s == 1.0
    assert [i.name for i in cfg.intents] == ["urllc_latency", "embb_latency", "mmtc_loss"]  # disabled one excluded
    assert {i.name: i.rho_min for i in cfg.intents} == {"urllc_latency": 0.05, "embb_latency": 1.0, "mmtc_loss": 0.005}
    assert set(cfg.topology.paths) == {"A", "B", "C"}
    assert cfg.topology.paths["C"].links == ("l14", "l46", "l65")
    assert cfg.nominal_model.calibration_status == "uncalibrated"


def test_config_hash_is_stable_and_sensitive():
    assert config_hash(raw_config()) == config_hash(raw_config()) == load_config(CONFIG_DIR).config_hash
    raw = raw_config()
    raw["intents"]["rho_min"] = 0.006
    assert config_hash(raw) != config_hash(raw_config())


def _intent(formula, **extra):
    def mutate(raw):
        raw["intents"]["intents"] = [{"name": "x", "formula": formula, **extra}]
    return mutate


def test_assumption1_horizon_exactly_sufficient():
    c = config_with(_intent("G[0,10](latency_p99_ms.urllc <= 1.0)"))
    assert c.intents[0].name == "x"


def test_assumption1_horizon_too_short():
    with pytest.raises(ConfigError) as exc:
        config_with(_intent("G[0,11](latency_p99_ms.urllc <= 1.0)"))
    assert "H=10 is too short" in str(exc.value)


def test_nested_horizon_is_enforced_beyond_paper_b_phi():
    # b_phi = 8 <= H = 10, but the formula reads 8 + 3 = 11 steps ahead
    with pytest.raises(ConfigError) as exc:
        config_with(_intent("G[0,8] F[0,3] (latency_p99_ms.urllc <= 1.0)"))
    assert "b_phi = 8" in str(exc.value) and "H >= 11" in str(exc.value)


def test_empty_intent_set_becomes_top():
    c = config_with(lambda raw: raw["intents"].update(intents=[]))
    assert len(c.intents) == 1 and c.intents[0].formula == Top()


def test_all_disabled_becomes_top():
    def mutate(raw):
        for it in raw["intents"]["intents"]:
            it["enabled"] = False
    assert config_with(mutate).intents[0].formula == Top()


def test_action_signal_in_intent():
    c = config_with(_intent("G[0,10](action.rate_budget_mbps.embb >= 50)"))
    assert c.intents[0].rho_min == c.rho_min


@pytest.mark.parametrize("mutate, fragment", [
    (_intent("G[0,10](latency_p99_ms.nope <= 1)"), "unknown signals"),
    (_intent("G[0,10](latency_p99_ms.urllc < 1)"), "cannot parse"),
    (_intent("G[0,10](latency_p99_ms.urllc <= 1)", rho_min=0), "must be > 0"),
    (lambda r: r["intents"].update(rho_min=0.0), "must be > 0"),
    (lambda r: r["intents"].update(rho_min=-1), "must be > 0"),
    (lambda r: r["intents"].update(horizon_H=0), "must be >= 1"),
    (lambda r: r["intents"].update(horizon_H=10.0), "integer"),
    (lambda r: r["intents"]["intents"].append(dict(r["intents"]["intents"][0])), "duplicate"),
    (lambda r: r["network"]["topology"]["paths"].update(D=["s1", "s2", "s1", "s3", "s5"]), "loop-free"),
    (lambda r: r["network"]["topology"]["paths"].update(D=["s1", "s6", "s5"]), "no link"),
    (lambda r: r["network"]["topology"]["paths"].update(D=["s2", "s5"]), "not ingress"),
    (lambda r: r["network"]["topology"]["links"][0].update(capacity_mbps=0), "must be >"),
    (lambda r: r["network"]["topology"]["links"].append({"id": "l99", "a": "s1", "b": "s2", "capacity_mbps": 1, "prop_delay_ms": 0}), "parallel"),
    (lambda r: r["network"]["slices"]["urllc"].update(allowed_paths=["Q"]), "allowed_paths"),
    (lambda r: r["network"]["slices"]["urllc"].update(rate_budget_mbps=[5, 1]), "exceeds"),
    (lambda r: r["network"]["state_bounds"].pop("energy_w"), "exactly"),
    (lambda r: r["network"]["control"].update(delta_t_s=0), "must be >"),
    (lambda r: r["shield"]["fallback_action"]["path"].update(urllc="Z"), "not in the action set A"),
    (lambda r: r["shield"]["fallback_action"].pop("link_power"), "exactly the fields"),
    (lambda r: r["shield"]["measurements"].update(max_staleness_s=0), "must be >"),
    # eta (paper Def 2) applies to the learned world model, which Stage 1 does not have (M2)
    (lambda r: r["shield"].update(ood_threshold_eta=0.5), "unknown key 'ood_threshold_eta'"),
    (lambda r: r["shield"]["demand_forecast"].update(type="arima"), "only 'upper_bound_constant'"),
    (lambda r: r["shield"]["nominal_model"].update(max_valid_utilization=1.0), "max_valid_utilization"),
    (lambda r: r["shield"]["nominal_model"].update(latency_safety_factor=0.5), "latency_safety_factor"),
    (lambda r: r["shield"]["nominal_model"]["mean_packet_size_bytes"].pop("embb"), "mean_packet_size_bytes"),
])
def test_invalid_configs_rejected(mutate, fragment):
    with pytest.raises(ConfigError) as exc:
        config_with(mutate)
    assert fragment in str(exc.value)


def test_missing_section():
    raw = raw_config()
    del raw["shield"]
    with pytest.raises(ConfigError):
        build_config(raw)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path)
