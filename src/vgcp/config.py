"""Load and validate configs/*.yaml into a ProjectConfig.

All thresholds, bounds and limits live in the YAML files; nothing safety-relevant
is hard-coded. Validation fails loudly (ConfigError) rather than substituting
defaults for safety-relevant values. Every mapping with a fixed set of keys is
checked against _SCHEMA first, so a misspelt optional key cannot silently fall
back to its default.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from vgcp.action import ActionSchema, ControlAction, SliceSpec
from vgcp.constraints import ConstraintConfig
from vgcp.errors import ConfigError, InvalidActionError, is_finite_real
from vgcp.models.nominal import NominalModelParams
from vgcp.signals import action_signal_names
from vgcp.state import DEMAND_FAMILIES, STATE_FAMILIES, ObservationSchema
from vgcp.stl import Formula, ParseError, Top, max_temporal_bound, parse, required_horizon, signals
from vgcp.topology import Link, Topology

CONFIG_FILES = ("network", "constraints", "intents", "shield")


@dataclass(frozen=True)
class Intent:
    """One operator intent phi in Phi, compiled to STL (paper Sec 2.2)."""

    name: str
    text: str
    formula: Formula
    rho_min: float
    description: str = ""


@dataclass(frozen=True)
class ShieldSettings:
    max_staleness_s: float
    check_constraints_along_rollout: bool
    forecast_margin: float


@dataclass(frozen=True)
class ProjectConfig:
    source: str
    config_hash: str
    delta_t_s: float
    topology: Topology
    slices: tuple[SliceSpec, ...]
    state_schema: ObservationSchema
    demand_schema: ObservationSchema
    action_schema: ActionSchema
    constraints: ConstraintConfig
    horizon_H: int
    rho_min: float
    intents: tuple[Intent, ...]
    shield: ShieldSettings
    nominal_model: NominalModelParams
    fallback_action: ControlAction
    raw: Mapping[str, Any]


def load_config(config_dir: str | Path) -> ProjectConfig:
    config_dir = Path(config_dir)
    raw: dict[str, Any] = {}
    for name in CONFIG_FILES:
        path = config_dir / f"{name}.yaml"
        if not path.is_file():
            raise ConfigError(f"missing configuration file: {path}")
        with path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ConfigError(f"{path}: top level must be a mapping")
        raw[name] = data
    return build_config(raw, source=str(config_dir))


def config_hash(raw: Mapping[str, Any]) -> str:
    blob = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------- helpers
def _get(m: Any, key: str, ctx: str) -> Any:
    if not isinstance(m, Mapping) or key not in m:
        raise ConfigError(f"{ctx}: missing '{key}'")
    return m[key]


def _num(x: Any, ctx: str, *, lo: float | None = None, lo_open: bool = False) -> float:
    if not is_finite_real(x):
        raise ConfigError(f"{ctx}: expected a finite number, got {x!r}")
    if lo is not None and (x <= lo if lo_open else x < lo):
        raise ConfigError(f"{ctx}: must be {'>' if lo_open else '>='} {lo}, got {x}")
    return float(x)


def _int(x: Any, ctx: str, *, lo: int | None = None) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ConfigError(f"{ctx}: expected an integer, got {x!r}")
    if lo is not None and x < lo:
        raise ConfigError(f"{ctx}: must be >= {lo}, got {x}")
    return x


def _pair(x: Any, ctx: str, conv) -> tuple:
    if not isinstance(x, (list, tuple)) or len(x) != 2:
        raise ConfigError(f"{ctx}: expected [lower, upper]")
    lo, hi = conv(x[0], f"{ctx}[0]"), conv(x[1], f"{ctx}[1]")
    if lo > hi:
        raise ConfigError(f"{ctx}: lower bound {lo} exceeds upper bound {hi}")
    return lo, hi


def _bool(x: Any, ctx: str) -> bool:
    if not isinstance(x, bool):
        raise ConfigError(f"{ctx}: expected true or false, got {x!r}")
    return x


def _bounds(section: Any, families: Mapping[str, Any], ctx: str) -> dict[str, tuple[float, float]]:
    if not isinstance(section, Mapping) or set(section) != set(families):
        raise ConfigError(f"{ctx}: must give [lower, upper] for exactly {sorted(families)}")
    return {f: _pair(section[f], f"{ctx}.{f}", _num) for f in families}


# ---------------------------------------------------------------- key schema
# Structural schema of the configuration: which keys each fixed-schema mapping may
# contain, and which values must be lists, name-keyed mappings or strings.
# A field value of None is a leaf whose value build_config validates. Required keys
# and all value checks stay in build_config; this pass only rejects what build_config
# would otherwise ignore or coerce.
@dataclass(frozen=True)
class _Obj:
    """Mapping with a fixed key set; each key maps to the schema of its value."""

    fields: Mapping[str, Any]
    label: str = "key"


@dataclass(frozen=True)
class _ListOf:
    item: Any


@dataclass(frozen=True)
class _MapOf:
    """Mapping keyed by user-chosen names (slices, paths)."""

    value: Any


_STR = "string"  # leaf that must be a string (identifiers, labels)

_SCHEMA = _Obj({
    "network": _Obj({
        "control": _Obj({"delta_t_s": None}),
        "topology": _Obj({
            "ingress": _STR,
            "egress": _STR,
            "switches": _ListOf(_STR),
            "links": _ListOf(_Obj({
                "id": _STR, "a": _STR, "b": _STR, "capacity_mbps": None, "prop_delay_ms": None,
            })),
            "paths": _MapOf(_ListOf(_STR)),
            "power_controllable_links": _ListOf(_STR),  # optional, default []
        }),
        "slices": _MapOf(_Obj({
            "allowed_paths": _ListOf(_STR), "rate_budget_mbps": None, "admission_limit": None,
        })),
        "state_bounds": _Obj({f: None for f in STATE_FAMILIES}, label="metric family"),
        "demand_bounds": _Obj({f: None for f in DEMAND_FAMILIES}, label="metric family"),
    }),
    "constraints": _Obj({
        # Family parameters are required only while the family is enabled.
        "link_capacity": _Obj({"enabled": None, "max_reserved_fraction": None}),
        "flow_table": _Obj({
            "enabled": None, "max_entries_per_switch": None, "rules_per_slice_per_switch": None,
        }),
        "slice_min_budget": _Obj({"enabled": None, "min_rate_budget_mbps": None}),
        "routing_validity": _Obj({"enabled": None}),
    }, label="constraint family"),
    "intents": _Obj({
        "slot_duration_s": None,
        "horizon_H": None,
        "rho_min": None,
        "intents": _ListOf(_Obj({
            "name": _STR,
            "formula": _STR,
            "rho_min": None,  # optional, default: global rho_min (D2)
            "enabled": None,  # optional, default true
            "description": _STR,  # optional, default ""
        })),
    }),
    "shield": _Obj({
        "measurements": _Obj({"max_staleness_s": None}),
        "check_constraints_along_rollout": None,
        "demand_forecast": _Obj({"type": _STR, "margin": None}),
        "nominal_model": _Obj({
            "calibration_status": _STR,  # optional, default "uncalibrated"
            "mean_packet_size_bytes": None,
            "processing_delay_ms_per_hop": None,
            "latency_safety_factor": None,
            "max_valid_utilization": None,
            "link_idle_power_w": None,
            "link_dynamic_power_w": None,
        }),
        "fallback_action": _Obj({
            "path": None, "rate_budget_mbps": None, "admission_limit": None, "link_power": None,
        }),
    }),
}, label="section")


def _check_schema(node: Any, schema: Any, ctx: str) -> None:
    where = ctx or "configuration"
    if schema is None:
        return
    if schema is _STR:
        if not isinstance(node, str):
            raise ConfigError(f"{where}: expected a string, got {node!r}")
    elif isinstance(schema, _ListOf):
        if not isinstance(node, list):
            raise ConfigError(f"{where}: expected a list, got {node!r}")
        for i, item in enumerate(node):
            _check_schema(item, schema.item, f"{ctx}[{i}]")
    elif isinstance(schema, _MapOf):
        if not isinstance(node, Mapping):
            raise ConfigError(f"{where}: expected a mapping, got {node!r}")
        for name, value in node.items():
            if not isinstance(name, str):
                raise ConfigError(f"{where}: name {name!r} must be a string")
            _check_schema(value, schema.value, f"{ctx}.{name}")
    else:
        if not isinstance(node, Mapping):
            raise ConfigError(f"{where}: expected a mapping, got {node!r}")
        for key in node:
            if key not in schema.fields:
                close = difflib.get_close_matches(key, schema.fields, n=1) if isinstance(key, str) else []
                hint = f" (did you mean {close[0]!r}?)" if close else ""
                raise ConfigError(
                    f"{where}: unknown {schema.label} {key!r}{hint}; "
                    f"allowed: {', '.join(sorted(schema.fields))}"
                )
        for key, value in node.items():
            _check_schema(value, schema.fields[key], f"{ctx}.{key}" if ctx else key)


# ---------------------------------------------------------------- builder
def build_config(raw: Mapping[str, Any], source: str = "<memory>") -> ProjectConfig:
    for name in CONFIG_FILES:
        if not isinstance(raw.get(name), Mapping):
            raise ConfigError(f"configuration section '{name}' missing")
    _check_schema(raw, _SCHEMA, "")
    net, cons, intents_raw, shield_raw = (raw[n] for n in CONFIG_FILES)

    delta_t = _num(_get(_get(net, "control", "network"), "delta_t_s", "network.control"),
                   "network.control.delta_t_s", lo=0.0, lo_open=True)

    # --- topology
    traw = _get(net, "topology", "network")
    links = []
    for i, l in enumerate(_get(traw, "links", "network.topology")):
        ctx = f"network.topology.links[{i}]"
        links.append(Link(
            id=str(_get(l, "id", ctx)), a=str(_get(l, "a", ctx)), b=str(_get(l, "b", ctx)),
            capacity_mbps=_num(_get(l, "capacity_mbps", ctx), f"{ctx}.capacity_mbps", lo=0.0, lo_open=True),
            prop_delay_ms=_num(_get(l, "prop_delay_ms", ctx), f"{ctx}.prop_delay_ms", lo=0.0),
        ))
    paths = _get(traw, "paths", "network.topology")
    if not isinstance(paths, Mapping):
        raise ConfigError("network.topology.paths must map path id -> list of switches")
    topology = Topology(
        switches=[str(s) for s in _get(traw, "switches", "network.topology")],
        links=links,
        paths={str(k): [str(n) for n in v] for k, v in paths.items()},
        ingress=str(_get(traw, "ingress", "network.topology")),
        egress=str(_get(traw, "egress", "network.topology")),
        power_controllable_links=[str(x) for x in traw.get("power_controllable_links", [])],
    )

    # --- slices and action set A
    sraw = _get(net, "slices", "network")
    if not isinstance(sraw, Mapping) or not sraw:
        raise ConfigError("network.slices must be a non-empty mapping")
    slices = []
    for name, s in sraw.items():
        ctx = f"network.slices.{name}"
        allowed = tuple(str(p) for p in _get(s, "allowed_paths", ctx))
        unknown = [p for p in allowed if p not in topology.paths]
        if not allowed or unknown:
            raise ConfigError(f"{ctx}.allowed_paths: must be non-empty and known (unknown: {unknown})")
        budget = _pair(_get(s, "rate_budget_mbps", ctx), f"{ctx}.rate_budget_mbps",
                       lambda x, c: _num(x, c, lo=0.0))
        limit = _pair(_get(s, "admission_limit", ctx), f"{ctx}.admission_limit",
                      lambda x, c: _int(x, c, lo=0))
        slices.append(SliceSpec(str(name), allowed, budget, limit))
    slice_names = [s.name for s in slices]
    action_schema = ActionSchema(slices, list(topology.paths), topology.power_controllable_links)

    # --- state and demand schemas (bounded S and D)
    index_sets = {"link": list(topology.links), "slice": slice_names, "switch": list(topology.switches)}
    state_schema = ObservationSchema.build(
        STATE_FAMILIES, index_sets, _bounds(_get(net, "state_bounds", "network"), STATE_FAMILIES, "network.state_bounds"))
    demand_schema = ObservationSchema.build(
        DEMAND_FAMILIES, index_sets, _bounds(_get(net, "demand_bounds", "network"), DEMAND_FAMILIES, "network.demand_bounds"))

    # --- hard constraints
    constraints = ConstraintConfig.from_mapping(cons, slice_names)

    # --- intents Phi
    # Time bounds in formulas count slots; changing the slot length must not silently
    # change what every intent means (audit L6).
    slot = _num(_get(intents_raw, "slot_duration_s", "intents"), "intents.slot_duration_s", lo=0.0, lo_open=True)
    if slot != delta_t:
        raise ConfigError(
            f"intents.slot_duration_s = {slot} s but network.control.delta_t_s = {delta_t} s: "
            "intent time bounds are counted in slots, so review every intent before changing "
            "the slot length, then update slot_duration_s"
        )
    H = _int(_get(intents_raw, "horizon_H", "intents"), "intents.horizon_H", lo=1)
    rho_min = _num(_get(intents_raw, "rho_min", "intents"), "intents.rho_min", lo=0.0, lo_open=True)
    known_signals = set(state_schema.keys) | set(action_signal_names(action_schema))
    intents: list[Intent] = []
    seen = set()
    items = _get(intents_raw, "intents", "intents")
    if not isinstance(items, list):
        raise ConfigError("intents.intents must be a list")
    for i, item in enumerate(items):
        ctx = f"intents.intents[{i}]"
        name = str(_get(item, "name", ctx))
        if name in seen:
            raise ConfigError(f"{ctx}: duplicate intent name '{name}'")
        seen.add(name)
        text = _get(item, "formula", ctx)
        try:
            phi = parse(text)
        except (ParseError, ValueError) as e:
            raise ConfigError(f"intent '{name}': cannot parse formula: {e}") from e
        unknown = sorted(signals(phi) - known_signals)
        if unknown:
            raise ConfigError(f"intent '{name}': unknown signals {unknown}")
        need, b_phi = required_horizon(phi), max_temporal_bound(phi)
        if need > H:
            raise ConfigError(
                f"intent '{name}': rollout horizon H={H} is too short. The formula reads "
                f"{need} steps ahead (paper Assumption 1 asks H >= b_phi = {b_phi}; nested "
                f"temporal operators need H >= {need}, see docs/milestone1_design.md)"
            )
        own_rho = item.get("rho_min", rho_min)
        own_rho = _num(own_rho, f"{ctx}.rho_min", lo=0.0, lo_open=True)
        if _bool(item.get("enabled", True), f"{ctx}.enabled"):
            intents.append(Intent(name, text, phi, own_rho, str(item.get("description", ""))))
    if not intents:
        # Paper Sec 2.2: "if no intents are active, Phi may be taken as {T}".
        intents.append(Intent("true", "true", Top(), rho_min, "Phi = {T}: no active intents"))

    # --- shield settings
    meas = _get(shield_raw, "measurements", "shield")
    fc = _get(shield_raw, "demand_forecast", "shield")
    if _get(fc, "type", "shield.demand_forecast") != "upper_bound_constant":
        raise ConfigError("shield.demand_forecast.type: only 'upper_bound_constant' is implemented")
    settings = ShieldSettings(
        max_staleness_s=_num(_get(meas, "max_staleness_s", "shield.measurements"),
                             "shield.measurements.max_staleness_s", lo=0.0, lo_open=True),
        check_constraints_along_rollout=_bool(
            _get(shield_raw, "check_constraints_along_rollout", "shield"),
            "shield.check_constraints_along_rollout"),
        forecast_margin=_num(_get(fc, "margin", "shield.demand_forecast"),
                             "shield.demand_forecast.margin", lo=0.0),
    )
    nominal = NominalModelParams.from_mapping(_get(shield_raw, "nominal_model", "shield"), slice_names)

    # --- fallback action pi_0 (must be in A; Assumption 3 is checked in Milestone 4)
    try:
        fallback = ControlAction.from_dict(_get(shield_raw, "fallback_action", "shield"))
    except InvalidActionError as e:
        raise ConfigError(f"shield.fallback_action: {e}") from e
    errors = action_schema.validate(fallback)
    if errors:
        raise ConfigError("shield.fallback_action is not in the action set A: " + "; ".join(errors))

    return ProjectConfig(
        source=source, config_hash=config_hash(raw), delta_t_s=delta_t, topology=topology,
        slices=tuple(slices), state_schema=state_schema, demand_schema=demand_schema,
        action_schema=action_schema, constraints=constraints, horizon_H=H, rho_min=rho_min,
        intents=tuple(intents), shield=settings, nominal_model=nominal,
        fallback_action=fallback, raw=raw,
    )
