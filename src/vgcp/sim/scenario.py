"""Experiment scenarios (experiments/scenarios/*.yaml), loaded strictly.

A scenario fixes everything about the simulated environment that is not a property
of the controller: demand, background traffic, faults, and the ground-truth network
parameters (which may deliberately differ from the nominal model's).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from vgcp.errors import ConfigError, is_finite_real


@dataclass(frozen=True)
class Window:
    start: int  # first slot (inclusive)
    end: int  # last slot (exclusive)

    def active(self, t: int) -> bool:
        return self.start <= t < self.end


@dataclass(frozen=True)
class BackgroundEvent:
    window: Window
    links: tuple[str, ...]
    mbps: float


@dataclass(frozen=True)
class DemandEvent:
    window: Window
    slice: str
    factor: float  # multiplies the base offered load


@dataclass(frozen=True)
class MissingTelemetry:
    window: Window
    prefixes: tuple[str, ...]  # metric keys starting with any of these are not reported


@dataclass(frozen=True)
class GroundTruth:
    packet_size_bytes: Mapping[str, float]  # true mean Ethernet frame sizes (may differ from the model)
    processing_delay_ms_per_hop: float
    latency_noise: float  # relative std of multiplicative latency noise
    measurement_noise: float  # relative std of telemetry noise
    buffer_ms: float  # max queueing delay per hop when a link is overloaded


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    slots: int
    demand_mbps: Mapping[str, float]
    devices: Mapping[str, float]
    demand_noise: float
    background: tuple[BackgroundEvent, ...]
    demand_events: tuple[DemandEvent, ...]
    stale_telemetry: tuple[Window, ...]  # telemetry frozen (last values re-sent with old timestamps)
    missing_telemetry: tuple[MissingTelemetry, ...]
    measurement_delay_slots: int
    controller_failures: tuple[Window, ...]  # apply() fails during these slots
    actuation_delay_slots: int
    truth: GroundTruth
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.raw, sort_keys=True, default=str).encode()).hexdigest()

    def disturbance_start(self) -> int | None:
        starts = [e.window.start for e in self.background] + [e.window.start for e in self.demand_events]
        starts += [w.start for w in self.stale_telemetry] + [m.window.start for m in self.missing_telemetry]
        starts += [w.start for w in self.controller_failures]
        return min(starts) if starts else None


_TOP = {"name", "description", "slots", "demand_mbps", "devices", "demand_noise", "background",
        "demand_events", "stale_telemetry", "missing_telemetry", "measurement_delay_slots",
        "controller_failures", "actuation_delay_slots", "ground_truth"}
_TRUTH = {"packet_size_bytes", "processing_delay_ms_per_hop", "latency_noise", "measurement_noise", "buffer_ms"}


def _keys(m: Any, allowed: set[str], required: set[str], ctx: str) -> Mapping[str, Any]:
    if not isinstance(m, Mapping):
        raise ConfigError(f"{ctx}: expected a mapping")
    unknown = sorted(set(m) - allowed)
    if unknown:
        raise ConfigError(f"{ctx}: unknown keys {unknown}")
    missing = sorted(required - set(m))
    if missing:
        raise ConfigError(f"{ctx}: missing keys {missing}")
    return m


def _num(x: Any, ctx: str, lo: float = 0.0) -> float:
    if not is_finite_real(x) or x < lo:
        raise ConfigError(f"{ctx}: expected a finite number >= {lo}, got {x!r}")
    return float(x)


def _int(x: Any, ctx: str, lo: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool) or x < lo:
        raise ConfigError(f"{ctx}: expected an integer >= {lo}, got {x!r}")
    return x


def _window(m: Any, ctx: str, slots: int, extra: frozenset = frozenset()) -> Window:
    m = _keys(m, {"start", "end"} | set(extra), {"start", "end"}, ctx)
    w = Window(_int(m["start"], f"{ctx}.start"), _int(m["end"], f"{ctx}.end"))
    if not w.start < w.end <= slots:
        raise ConfigError(f"{ctx}: need start < end <= slots ({slots})")
    return w


def _slice_map(m: Any, slices: set[str], ctx: str) -> dict[str, float]:
    if not isinstance(m, Mapping) or set(m) != slices:
        raise ConfigError(f"{ctx}: must give a value for exactly {sorted(slices)}")
    return {s: _num(m[s], f"{ctx}.{s}") for s in slices}


def parse_scenario(raw: Mapping[str, Any], slices: set[str], links: set[str]) -> Scenario:
    raw = _keys(raw, _TOP, {"name", "slots", "demand_mbps", "devices", "ground_truth"}, "scenario")
    slots = _int(raw["slots"], "scenario.slots", lo=1)
    bgs = []
    for i, e in enumerate(raw.get("background", [])):
        ctx = f"scenario.background[{i}]"
        e = _keys(e, {"start", "end", "links", "mbps"}, {"start", "end", "links", "mbps"}, ctx)
        bad = sorted(set(e["links"]) - links)
        if bad:
            raise ConfigError(f"{ctx}: unknown links {bad}")
        bgs.append(BackgroundEvent(_window(e, ctx, slots, frozenset(e) - {"start", "end"}), tuple(e["links"]), _num(e["mbps"], f"{ctx}.mbps")))
    des = []
    for i, e in enumerate(raw.get("demand_events", [])):
        ctx = f"scenario.demand_events[{i}]"
        e = _keys(e, {"start", "end", "slice", "factor"}, {"start", "end", "slice", "factor"}, ctx)
        if e["slice"] not in slices:
            raise ConfigError(f"{ctx}: unknown slice {e['slice']!r}")
        des.append(DemandEvent(_window(e, ctx, slots, frozenset(e) - {"start", "end"}), e["slice"], _num(e["factor"], f"{ctx}.factor")))
    missing = []
    for i, e in enumerate(raw.get("missing_telemetry", [])):
        ctx = f"scenario.missing_telemetry[{i}]"
        e = _keys(e, {"start", "end", "prefixes"}, {"start", "end", "prefixes"}, ctx)
        missing.append(MissingTelemetry(_window(e, ctx, slots, frozenset(e) - {"start", "end"}), tuple(str(p) for p in e["prefixes"])))
    truth = _keys(raw["ground_truth"], _TRUTH, _TRUTH, "scenario.ground_truth")
    gt = GroundTruth(
        packet_size_bytes=_slice_map(truth["packet_size_bytes"], slices, "ground_truth.packet_size_bytes"),
        processing_delay_ms_per_hop=_num(truth["processing_delay_ms_per_hop"], "ground_truth.processing_delay_ms_per_hop"),
        latency_noise=_num(truth["latency_noise"], "ground_truth.latency_noise"),
        measurement_noise=_num(truth["measurement_noise"], "ground_truth.measurement_noise"),
        buffer_ms=_num(truth["buffer_ms"], "ground_truth.buffer_ms"),
    )
    return Scenario(
        name=str(raw["name"]), description=str(raw.get("description", "")), slots=slots,
        demand_mbps=_slice_map(raw["demand_mbps"], slices, "scenario.demand_mbps"),
        devices=_slice_map(raw["devices"], slices, "scenario.devices"),
        demand_noise=_num(raw.get("demand_noise", 0.0), "scenario.demand_noise"),
        background=tuple(bgs), demand_events=tuple(des),
        stale_telemetry=tuple(_window(w, f"scenario.stale_telemetry[{i}]", slots)
                              for i, w in enumerate(raw.get("stale_telemetry", []))),
        missing_telemetry=tuple(missing),
        measurement_delay_slots=_int(raw.get("measurement_delay_slots", 0), "scenario.measurement_delay_slots"),
        controller_failures=tuple(_window(w, f"scenario.controller_failures[{i}]", slots)
                                  for i, w in enumerate(raw.get("controller_failures", []))),
        actuation_delay_slots=_int(raw.get("actuation_delay_slots", 0), "scenario.actuation_delay_slots"),
        truth=gt, raw=dict(raw),
    )


def load_scenario(path: str | Path, slices: set[str], links: set[str]) -> Scenario:
    with Path(path).open() as f:
        data = yaml.safe_load(f)
    return parse_scenario(data, slices, links)
