"""Audit finding H2: unknown or misspelled configuration keys must be rejected, not ignored."""

import shutil

import pytest
import yaml

from factories import CONFIG_DIR, config_with, raw_config
from vgcp.config import CONFIG_FILES, build_config, load_config
from vgcp.errors import ConfigError


def _yaml_dir(tmp_path, file, old, new):
    """Copy configs/ into tmp_path, replacing `old` by `new` exactly once in `file`."""
    for name in CONFIG_FILES:
        shutil.copy(CONFIG_DIR / f"{name}.yaml", tmp_path / f"{name}.yaml")
    path = tmp_path / file
    text = path.read_text()
    assert text.count(old) == 1, f"fixture expects exactly one {old!r} in {file}"
    path.write_text(text.replace(old, new))
    return tmp_path


# ---------------------------------------------------------------- audit examples, through load_config
def test_rho_min_typo_rejected(tmp_path):
    # Global key misspelt: intents.rho_min -> rho_mn
    d = _yaml_dir(tmp_path, "intents.yaml", "\nrho_min: 0.05\n", "\nrho_mn: 0.05\n")
    with pytest.raises(ConfigError) as exc:
        load_config(d)
    msg = str(exc.value)
    assert msg.startswith("intents: ") and "'rho_mn'" in msg
    assert "did you mean 'rho_min'" in msg


def test_per_intent_key_typo_rejected(tmp_path):
    d = _yaml_dir(tmp_path, "intents.yaml", "  - name: urllc_latency\n", "  - name: urllc_latency\n    rho_mn: 0.05\n")
    with pytest.raises(ConfigError) as exc:
        load_config(d)
    assert "intents.intents[0]" in str(exc.value) and "'rho_mn'" in str(exc.value)


def test_enabled_typo_rejected(tmp_path):
    d = _yaml_dir(tmp_path, "intents.yaml", "    enabled: false\n", "    enable: false\n")
    with pytest.raises(ConfigError) as exc:
        load_config(d)
    msg = str(exc.value)
    assert "intents.intents[3]" in msg and "'enable'" in msg
    assert "did you mean 'enabled'" in msg


@pytest.mark.parametrize("file, old, new, where, key", [
    ("shield.yaml", "  calibration_status:", "  calibraton_status:", "shield.nominal_model", "calibraton_status"),
    ("network.yaml", "  power_controllable_links:", "  power_controlable_links:", "network.topology",
     "power_controlable_links"),
    ("constraints.yaml", "  max_reserved_fraction:", "  max_reserved_fracton:", "constraints.link_capacity",
     "max_reserved_fracton"),
])
def test_optional_or_nested_typo_rejected_from_yaml(tmp_path, file, old, new, where, key):
    d = _yaml_dir(tmp_path, file, old, new)
    with pytest.raises(ConfigError) as exc:
        load_config(d)
    assert where in str(exc.value) and repr(key) in str(exc.value)


# ---------------------------------------------------------------- an unknown key in every fixed-schema mapping
def _add_key(path, key="bogus_key"):
    def mutate(raw):
        node = raw
        for p in path:
            node = node[p]
        node[key] = 1
    return mutate


@pytest.mark.parametrize("path, where", [
    (("network",), "network"),
    (("network", "control"), "network.control"),
    (("network", "topology"), "network.topology"),
    (("network", "topology", "links", 0), "network.topology.links[0]"),
    (("network", "topology", "links", 6), "network.topology.links[6]"),
    (("network", "slices", "urllc"), "network.slices.urllc"),
    (("network", "slices", "mmtc"), "network.slices.mmtc"),
    (("network", "state_bounds"), "network.state_bounds"),
    (("network", "demand_bounds"), "network.demand_bounds"),
    (("constraints",), "constraints"),
    (("constraints", "link_capacity"), "constraints.link_capacity"),
    (("constraints", "flow_table"), "constraints.flow_table"),
    (("constraints", "slice_min_budget"), "constraints.slice_min_budget"),
    (("constraints", "routing_validity"), "constraints.routing_validity"),
    (("intents",), "intents"),
    (("intents", "intents", 0), "intents.intents[0]"),
    (("intents", "intents", 2), "intents.intents[2]"),
    (("shield",), "shield"),
    (("shield", "measurements"), "shield.measurements"),
    (("shield", "demand_forecast"), "shield.demand_forecast"),
    (("shield", "nominal_model"), "shield.nominal_model"),
    (("shield", "fallback_action"), "shield.fallback_action"),
])
def test_unknown_key_rejected_in_each_section(path, where):
    with pytest.raises(ConfigError) as exc:
        config_with(_add_key(path))
    msg = str(exc.value)
    assert msg.startswith(f"{where}: ") and "'bogus_key'" in msg


def test_unknown_key_in_disabled_constraint_family_rejected():
    def mutate(raw):
        raw["constraints"]["flow_table"] = {"enabled": False, "max_entries_per_swtich": 10}
    with pytest.raises(ConfigError) as exc:
        config_with(mutate)
    assert "constraints.flow_table" in str(exc.value) and "'max_entries_per_swtich'" in str(exc.value)


def test_unknown_top_level_section_rejected():
    raw = raw_config()
    raw["intent"] = {}
    with pytest.raises(ConfigError) as exc:
        build_config(raw)
    assert "'intent'" in str(exc.value)


# ---------------------------------------------------------------- no silent coercion of structural values
@pytest.mark.parametrize("mutate, where", [
    (lambda r: r["network"]["slices"]["urllc"].update(allowed_paths="A"), "network.slices.urllc.allowed_paths"),
    (lambda r: r["network"]["topology"]["links"][0].update(id=12), "network.topology.links[0].id"),
    (lambda r: r["intents"]["intents"][0].update(description=7), "intents.intents[0].description"),
    (lambda r: r["shield"]["nominal_model"].update(calibration_status=1), "shield.nominal_model.calibration_status"),
])
def test_malformed_structural_values_rejected(mutate, where):
    with pytest.raises(ConfigError) as exc:
        config_with(mutate)
    assert str(exc.value).startswith(f"{where}: ")


# ---------------------------------------------------------------- valid configurations are unchanged
def test_repository_config_values_match_yaml():
    cfg = load_config(CONFIG_DIR)
    data = yaml.safe_load((CONFIG_DIR / "intents.yaml").read_text())
    assert cfg.rho_min == data["rho_min"] == 0.05
    # Enabled flags and rho_min as written in the file; the disabled intent is excluded.
    assert [it.get("enabled", True) for it in data["intents"]] == [True, True, True, False]
    assert {i.name: i.rho_min for i in cfg.intents} == {
        "urllc_latency": 0.05, "embb_latency": 0.05, "mmtc_loss": 0.05,
    }
    assert cfg.raw == raw_config()


def test_optional_keys_may_be_omitted():
    def mutate(raw):
        raw["intents"]["intents"] = [{"name": "x", "formula": "G[0,10](loss_rate.mmtc <= 0.02)"}]
        del raw["shield"]["nominal_model"]["calibration_status"]
        del raw["network"]["topology"]["power_controllable_links"]
        raw["shield"]["fallback_action"]["link_power"] = {}
    c = config_with(mutate)
    (it,) = c.intents
    assert (it.name, it.rho_min, it.description) == ("x", c.rho_min, "")
    assert c.nominal_model.calibration_status == "uncalibrated"
    assert c.topology.power_controllable_links == ()


def test_optional_keys_present_are_used():
    def mutate(raw):
        raw["intents"]["intents"] = [{
            "name": "x", "formula": "G[0,10](loss_rate.mmtc <= 0.02)",
            "enabled": True, "description": "d",
        }]
    (it,) = config_with(mutate).intents
    assert (it.name, it.description) == ("x", "d")


@pytest.mark.parametrize("family, section", [
    ("link_capacity", {"enabled": False}),
    ("flow_table", {"enabled": False}),
    ("slice_min_budget", {"enabled": False}),
])
def test_disabled_constraint_family_without_parameters(family, section):
    c = config_with(lambda raw: raw["constraints"].update({family: section}))
    assert getattr(c.constraints, family) is False


def test_disabled_constraint_family_keeps_documented_parameters():
    c = config_with(lambda raw: raw["constraints"]["flow_table"].update(enabled=False))
    assert c.constraints.flow_table is False
