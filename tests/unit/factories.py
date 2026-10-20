"""Shared builders for unit tests (no Mininet, no root)."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from vgcp.action import ControlAction
from vgcp.config import CONFIG_FILES, ProjectConfig, build_config
from vgcp.state import Demand, NetworkState

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
NOW = 1000.0


def raw_config() -> dict:
    """A fresh, mutable copy of the repository configuration."""
    return {n: yaml.safe_load((CONFIG_DIR / f"{n}.yaml").read_text()) for n in CONFIG_FILES}


def config_with(mutate=None) -> ProjectConfig:
    raw = raw_config()
    if mutate:
        mutate(raw)
    return build_config(copy.deepcopy(raw))


def nominal_state_values(cfg: ProjectConfig) -> dict[str, float]:
    vals = {k: 0.0 for k in cfg.state_schema.keys}
    vals.update({
        "latency_p99_ms.urllc": 0.5,
        "latency_p99_ms.embb": 12.0,
        "latency_p99_ms.mmtc": 8.0,
        "throughput_mbps.embb": 80.0,
        "energy_w": 10.0,
    })
    for sw in cfg.topology.switches:
        vals[f"flow_table_occupancy.{sw}"] = 10.0
    return vals


def nominal_state(cfg: ProjectConfig, now: float = NOW, **overrides) -> NetworkState:
    vals = nominal_state_values(cfg)
    vals.update(overrides)
    return NetworkState.from_values(0, vals, now)


def nominal_demand(now: float = NOW, **overrides) -> Demand:
    vals = {
        "offered_load_mbps.urllc": 2.0,
        "offered_load_mbps.embb": 80.0,
        "offered_load_mbps.mmtc": 2.0,
        "active_devices.urllc": 10.0,
        "active_devices.embb": 5.0,
        "active_devices.mmtc": 200.0,
    }
    vals.update(overrides)
    return Demand.from_values(0, vals, now)


def action_with(cfg: ProjectConfig, **changes) -> ControlAction:
    """Copy of the fallback action with e.g. path={'embb': 'A'} merged in."""
    d = cfg.fallback_action.to_dict()
    for field, updates in changes.items():
        d[field].update(updates)
    return ControlAction.from_dict(d)
