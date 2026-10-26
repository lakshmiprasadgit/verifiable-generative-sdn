"""Hard constraints c(s, a) <= 0 (paper Eq 16).

Each enabled constraint family contributes one or more named components of the
vector c(s, a). Component values are real numbers: <= 0 means satisfied and
> 0 is the amount of violation in the component's own unit. Boolean protocol
invariants use 0 (holds) / 1 (violated). A component whose inputs are missing
evaluates to None (unknown) - never to "satisfied".

Families (all configured in configs/constraints.yaml):

link_capacity.<link>   sum of rate budgets of slices routed over the link, each times
                       (1 + meter_overshoot): what a metered slice can actually pass
                       + measured background load on the link (traffic outside
                       the managed slices, audit H1)
                       - max_reserved_fraction * capacity                     [Mbit/s]
flow_table.<switch>    current occupancy + rules_per_slice_per_switch * (slices
                       routed through the switch) - max_entries_per_switch    [entries]
slice_min_budget.<s>   min_rate_budget_mbps[s] - rate_budget_mbps[s]         [Mbit/s]
routing_validity.<s>   0 if the slice's path is allowed, loop-free, connects
                       ingress to egress and uses only powered-on links, else 1

``evaluate`` expects an action that is already in A (the shield checks this first).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from vgcp.action import ControlAction, SliceSpec
from vgcp.errors import ConfigError, is_finite_real
from vgcp.state import NetworkState
from vgcp.topology import Topology


@dataclass(frozen=True)
class ConstraintValue:
    name: str
    value: float | None
    detail: str = ""

    @property
    def satisfied(self) -> bool | None:
        return None if self.value is None else self.value <= 0


@dataclass(frozen=True)
class ConstraintVector:
    values: tuple[ConstraintValue, ...]

    @property
    def status(self) -> str:
        """'violated' if any component > 0, else 'unknown' if any is None, else 'satisfied'."""
        if any(v.satisfied is False for v in self.values):
            return "violated"
        if any(v.satisfied is None for v in self.values):
            return "unknown"
        return "satisfied"

    def violated(self) -> list[ConstraintValue]:
        return [v for v in self.values if v.satisfied is False]

    def unknown(self) -> list[ConstraintValue]:
        return [v for v in self.values if v.satisfied is None]

    def as_dict(self) -> dict[str, float | None]:
        return {v.name: v.value for v in self.values}


def _get(m: Mapping[str, Any], key: str, ctx: str) -> Any:
    if not isinstance(m, Mapping) or key not in m:
        raise ConfigError(f"{ctx}: missing '{key}'")
    return m[key]


def _num(x: Any, ctx: str, lo: float | None = None, hi: float | None = None) -> float:
    if not is_finite_real(x):
        raise ConfigError(f"{ctx}: expected a finite number, got {x!r}")
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ConfigError(f"{ctx}: {x} outside [{lo}, {hi}]")
    return float(x)


def _enabled(section: Mapping[str, Any], ctx: str) -> bool:
    v = _get(section, "enabled", ctx)
    if not isinstance(v, bool):
        raise ConfigError(f"{ctx}.enabled must be true or false")
    return v


@dataclass(frozen=True)
class ConstraintConfig:
    link_capacity: bool
    max_reserved_fraction: float
    flow_table: bool
    max_entries_per_switch: float
    rules_per_slice_per_switch: float
    slice_min_budget: bool
    min_rate_budget_mbps: Mapping[str, float] = field(default_factory=dict)
    routing_validity: bool = True

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], slice_names: Sequence[str]) -> "ConstraintConfig":
        ctx = "constraints"
        cap = _get(raw, "link_capacity", ctx)
        ft = _get(raw, "flow_table", ctx)
        smb = _get(raw, "slice_min_budget", ctx)
        rv = _get(raw, "routing_validity", ctx)
        unknown = set(raw) - {"link_capacity", "flow_table", "slice_min_budget", "routing_validity"}
        if unknown:
            raise ConfigError(f"{ctx}: unknown constraint families {sorted(unknown)}")

        cap_on = _enabled(cap, f"{ctx}.link_capacity")
        frac = _num(_get(cap, "max_reserved_fraction", f"{ctx}.link_capacity"),
                    f"{ctx}.link_capacity.max_reserved_fraction", 0.0, 1.0) if cap_on else 1.0
        ft_on = _enabled(ft, f"{ctx}.flow_table")
        max_entries = rules = 0.0
        if ft_on:
            max_entries = _num(_get(ft, "max_entries_per_switch", f"{ctx}.flow_table"),
                               f"{ctx}.flow_table.max_entries_per_switch", 0.0)
            rules = _num(_get(ft, "rules_per_slice_per_switch", f"{ctx}.flow_table"),
                         f"{ctx}.flow_table.rules_per_slice_per_switch", 0.0)
        smb_on = _enabled(smb, f"{ctx}.slice_min_budget")
        mins: dict[str, float] = {}
        if smb_on:
            table = _get(smb, "min_rate_budget_mbps", f"{ctx}.slice_min_budget")
            if not isinstance(table, Mapping) or set(table) != set(slice_names):
                raise ConfigError(
                    f"{ctx}.slice_min_budget.min_rate_budget_mbps must list exactly {list(slice_names)}"
                )
            mins = {s: _num(table[s], f"{ctx}.slice_min_budget.{s}", 0.0) for s in slice_names}
        return cls(cap_on, frac, ft_on, max_entries, rules, smb_on, mins, _enabled(rv, f"{ctx}.routing_validity"))


class HardConstraints:
    def __init__(self, cfg: ConstraintConfig, topology: Topology, slices: Sequence[SliceSpec],
                 meter_overshoot: float = 0.0) -> None:
        self.cfg = cfg
        self.meter_overshoot = meter_overshoot
        self.topology = topology
        self.slices = {s.name: s for s in slices}

    def required_state_keys(self) -> frozenset[str]:
        keys: set[str] = set()
        if self.cfg.flow_table:
            keys |= {f"flow_table_occupancy.{sw}" for sw in self.topology.switches}
        if self.cfg.link_capacity:
            keys |= {f"background_load_mbps.{lid}" for lid in self.topology.links}
        return frozenset(keys)

    def evaluate(self, state: NetworkState, action: ControlAction) -> ConstraintVector:
        values: list[ConstraintValue] = []
        topo = self.topology
        route_links = {s: topo.paths[action.path[s]].links for s in self.slices}
        route_nodes = {s: topo.paths[action.path[s]].nodes for s in self.slices}

        if self.cfg.routing_validity:
            for s, spec in self.slices.items():
                pid = action.path[s]
                problems = []
                if pid not in spec.allowed_paths:
                    problems.append(f"path {pid} not allowed")
                problems += topo.path_problems(route_nodes[s])
                off = [
                    lid for lid in route_links[s]
                    if lid in action.link_power and not action.link_power[lid]
                ]
                if off:
                    problems.append(f"uses powered-off links {off}")
                values.append(ConstraintValue(
                    f"routing_validity.{s}", 1.0 if problems else 0.0, "; ".join(problems)
                ))

        if self.cfg.link_capacity:
            for lid, link in topo.links.items():
                users = [s for s in self.slices if lid in route_links[s]]
                reserved = sum(float(action.rate_budget_mbps[s]) for s in users) * (1.0 + self.meter_overshoot)
                background = state.value(f"background_load_mbps.{lid}")
                limit = self.cfg.max_reserved_fraction * link.capacity_mbps
                if math.isnan(background):
                    values.append(ConstraintValue(f"link_capacity.{lid}", None, "background load not measured"))
                    continue
                values.append(ConstraintValue(
                    f"link_capacity.{lid}", reserved + background - limit,
                    f"reserved {reserved:g} Mbit/s by {users} + background {background:g} Mbit/s "
                    f"vs limit {limit:g} Mbit/s",
                ))

        if self.cfg.flow_table:
            for sw in topo.switches:
                occ = state.value(f"flow_table_occupancy.{sw}")
                n = sum(1 for s in self.slices if sw in route_nodes[s])
                if math.isnan(occ):
                    values.append(ConstraintValue(f"flow_table.{sw}", None, "occupancy not measured"))
                    continue
                needed = occ + self.cfg.rules_per_slice_per_switch * n
                values.append(ConstraintValue(
                    f"flow_table.{sw}", needed - self.cfg.max_entries_per_switch,
                    f"{occ:g} installed + {self.cfg.rules_per_slice_per_switch:g}x{n} new "
                    f"vs limit {self.cfg.max_entries_per_switch:g}",
                ))

        if self.cfg.slice_min_budget:
            for s in self.slices:
                need = self.cfg.min_rate_budget_mbps[s]
                have = float(action.rate_budget_mbps[s])
                values.append(ConstraintValue(
                    f"slice_min_budget.{s}", need - have, f"budget {have:g} vs minimum {need:g} Mbit/s"
                ))
        return ConstraintVector(tuple(values))
