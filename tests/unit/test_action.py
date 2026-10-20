"""Action a_t and the bounded action set A: validation and vector embedding."""

import math

import pytest

from factories import action_with
from vgcp.action import ControlAction
from vgcp.errors import InvalidActionError


def test_fallback_is_valid(cfg):
    assert cfg.action_schema.validate(cfg.fallback_action) == []


@pytest.mark.parametrize(
    "changes, fragment",
    [
        ({"path": {"urllc": "Z"}}, "unknown path"),
        ({"path": {"urllc": 3}}, "unknown path"),
        ({"rate_budget_mbps": {"embb": 150.01}}, "outside"),
        ({"rate_budget_mbps": {"embb": 0.99}}, "outside"),
        ({"rate_budget_mbps": {"embb": math.nan}}, "not a finite number"),
        ({"rate_budget_mbps": {"embb": math.inf}}, "not a finite number"),
        ({"rate_budget_mbps": {"embb": True}}, "not a finite number"),
        ({"rate_budget_mbps": {"embb": "100"}}, "not a finite number"),
        ({"admission_limit": {"mmtc": 501}}, "outside"),
        ({"admission_limit": {"mmtc": 0}}, "outside"),
        ({"admission_limit": {"mmtc": 10.0}}, "not an integer"),
        ({"admission_limit": {"mmtc": False}}, "not an integer"),
        ({"link_power": {"l14": 1}}, "not a boolean"),
    ],
)
def test_invalid_components_rejected(cfg, changes, fragment):
    errors = cfg.action_schema.validate(action_with(cfg, **changes))
    assert errors and any(fragment in e for e in errors), errors


@pytest.mark.parametrize("field, value", [("rate_budget_mbps", {"embb": 150.0}), ("rate_budget_mbps", {"embb": 1.0}),
                                          ("admission_limit", {"mmtc": 500}), ("admission_limit", {"mmtc": 1})])
def test_bounds_are_inclusive(cfg, field, value):
    assert cfg.action_schema.validate(action_with(cfg, **{field: value})) == []


def test_path_not_allowed_for_slice(cfg):
    from factories import config_with

    def restrict(raw):
        raw["network"]["slices"]["urllc"]["allowed_paths"] = ["A"]
    c = config_with(restrict)
    errors = c.action_schema.validate(action_with(c, path={"urllc": "B"}))
    assert any("not allowed" in e for e in errors)


def test_missing_and_extra_entries(cfg):
    d = cfg.fallback_action.to_dict()
    del d["path"]["mmtc"]
    d["rate_budget_mbps"]["video"] = 1.0
    errors = cfg.action_schema.validate(ControlAction.from_dict(d))
    assert any("missing entries ['mmtc']" in e for e in errors)
    assert any("unexpected entries ['video']" in e for e in errors)


def test_non_action_rejected(cfg):
    assert cfg.action_schema.validate({"path": {}}) != []
    assert cfg.action_schema.validate(None) != []


def test_from_dict_requires_exact_fields():
    with pytest.raises(InvalidActionError):
        ControlAction.from_dict({"path": {}})
    with pytest.raises(InvalidActionError):
        ControlAction.from_dict({"path": [], "rate_budget_mbps": {}, "admission_limit": {}, "link_power": {}})


def test_vector_roundtrip(cfg):
    a = action_with(cfg, path={"embb": "C"}, link_power={"l46": False})
    vec = cfg.action_schema.to_vector(a)
    assert len(vec) == len(cfg.action_schema.component_names()) == len(cfg.action_schema.vector_bounds())
    assert cfg.action_schema.from_vector(vec) == a
    for v, (lo, hi) in zip(vec, cfg.action_schema.vector_bounds()):
        assert lo <= v <= hi


def test_from_vector_rejects_malformed(cfg):
    vec = cfg.action_schema.to_vector(cfg.fallback_action)
    bad_cases = []
    v = list(vec); v[0] = 0.5; bad_cases.append(v)           # non-integral path index
    v = list(vec); v[0] = 7.0; bad_cases.append(v)           # path index out of range
    v = list(vec); v[2] = 10.5; bad_cases.append(v)          # non-integral admission
    v = list(vec); v[-1] = 2.0; bad_cases.append(v)          # power not 0/1
    v = list(vec); v[1] = math.nan; bad_cases.append(v)      # non-finite
    v = list(vec); v[1] = 1e9; bad_cases.append(v)           # out of bounds
    bad_cases.append(vec[:-1])                               # wrong length
    for bad in bad_cases:
        with pytest.raises(InvalidActionError):
            cfg.action_schema.from_vector(bad)


def test_to_vector_rejects_invalid(cfg):
    with pytest.raises(InvalidActionError):
        cfg.action_schema.to_vector(action_with(cfg, path={"urllc": "Z"}))
