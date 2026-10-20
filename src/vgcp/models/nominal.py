"""Analytical nominal transition model T-hat (paper Eq 12) - UNCALIBRATED in Milestone 1.

A fluid / queueing approximation of the transport network:

* admitted fraction    f_s = min(1, admission_limit_s / active_devices_s)  (1 if no devices)
* slice load           x_s = min(f_s * offered_load_s, rate_budget_s)       (budgets are policed)
* link utilization     rho_l = (sum of x_s over slices routed on l) / C_l
* service time         S_l = max packet size of slices on l / C_l
* per-hop p99 delay    prop_l + proc + ln(100) * S_l / (1 - rho_l)          (M/M/1 sojourn p99)
* slice p99 latency    k_safety * sum of per-hop p99 delays along the path
* slice jitter         k_safety * sum of S_l / (1 - rho_l)
* queue occupancy      sum of rho_l / (1 - rho_l) along the path            (M/M/1 mean)
* loss                 0 inside the validity domain - a placeholder, not a prediction
* energy proxy         sum over powered-on links of (P_idle + P_dyn * rho_l)
* flow-table occupancy carried forward unchanged from the current state
  (loss and flow-table occupancy are reported by unmodelled_state_keys(); see M5)

Validity domain: all inputs known and every link utilization <= max_valid_utilization,
with no load on a powered-off link. Outside it the predicted state may contain
missing values and the prediction is flagged ``in_domain=False`` (D12; this is not
the learned world model's uncertainty of paper Def 2).

Summing per-hop p99 values is a heuristic, not a proven bound on the end-to-end
p99. The model is NOT shown to be conservative with respect to the real
(emulated) network; that is established empirically by calibration in Milestone 3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from vgcp.action import ControlAction
from vgcp.errors import ConfigError, is_real
from vgcp.models.interfaces import Prediction
from vgcp.state import Demand, Measurement, NetworkState
from vgcp.topology import Topology

P99_FACTOR = math.log(100.0)  # p99 of an exponential sojourn time = ln(100) * mean


@dataclass(frozen=True)
class NominalModelParams:
    calibration_status: str
    mean_packet_size_bytes: Mapping[str, float]
    processing_delay_ms_per_hop: float
    latency_safety_factor: float
    max_valid_utilization: float
    link_idle_power_w: float
    link_dynamic_power_w: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], slice_names: Sequence[str]) -> "NominalModelParams":
        ctx = "shield.nominal_model"

        def num(key: str, lo: float, hi: float = math.inf, lo_open: bool = False) -> float:
            if key not in raw:
                raise ConfigError(f"{ctx}: missing '{key}'")
            v = raw[key]
            ok = is_real(v) and math.isfinite(v) and v <= hi and (v > lo if lo_open else v >= lo)
            if not ok:
                raise ConfigError(f"{ctx}.{key}: invalid value {v!r}")
            return float(v)

        sizes = raw.get("mean_packet_size_bytes")
        if not isinstance(sizes, Mapping) or set(sizes) != set(slice_names):
            raise ConfigError(f"{ctx}.mean_packet_size_bytes must list exactly {list(slice_names)}")
        for s, v in sizes.items():
            if not (is_real(v) and math.isfinite(v) and v > 0):
                raise ConfigError(f"{ctx}.mean_packet_size_bytes.{s}: must be > 0")
        max_u = num("max_valid_utilization", 0.0, 1.0, lo_open=True)
        if max_u >= 1.0:
            raise ConfigError(f"{ctx}.max_valid_utilization must be < 1")
        return cls(
            calibration_status=str(raw.get("calibration_status", "uncalibrated")),
            mean_packet_size_bytes={s: float(v) for s, v in sizes.items()},
            processing_delay_ms_per_hop=num("processing_delay_ms_per_hop", 0.0),
            latency_safety_factor=num("latency_safety_factor", 1.0),
            max_valid_utilization=max_u,
            link_idle_power_w=num("link_idle_power_w", 0.0),
            link_dynamic_power_w=num("link_dynamic_power_w", 0.0),
        )


class AnalyticNominalModel:
    def __init__(self, topology: Topology, slice_names: Sequence[str], params: NominalModelParams) -> None:
        self.topology = topology
        self.slices = tuple(slice_names)
        self.params = params

    def required_state_keys(self) -> frozenset[str]:
        return frozenset(f"flow_table_occupancy.{sw}" for sw in self.topology.switches)

    def unmodelled_state_keys(self) -> frozenset[str]:
        return frozenset(
            [f"loss_rate.{s}" for s in self.slices]
            + [f"flow_table_occupancy.{sw}" for sw in self.topology.switches]
        )

    def required_demand_keys(self) -> frozenset[str]:
        keys = set()
        for s in self.slices:
            keys |= {f"offered_load_mbps.{s}", f"active_devices.{s}"}
        return frozenset(keys)

    def predict(self, state: NetworkState, action: ControlAction, demand: Demand) -> Prediction:
        p, topo = self.params, self.topology
        notes: list[str] = []

        load: dict[str, float] = {}
        for s in self.slices:
            offered = demand.value(f"offered_load_mbps.{s}")
            devices = demand.value(f"active_devices.{s}")
            if math.isnan(offered) or math.isnan(devices):
                notes.append(f"demand for slice {s} unknown")
                load[s] = math.nan
                continue
            frac = 1.0 if devices <= 0 else min(1.0, action.admission_limit[s] / devices)
            load[s] = min(frac * offered, float(action.rate_budget_mbps[s]))

        route = {s: topo.paths[action.path[s]].links for s in self.slices}
        util: dict[str, float] = {}
        service_ms: dict[str, float] = {}
        for lid, link in topo.links.items():
            users = [s for s in self.slices if lid in route[s]]
            total = sum(load[s] for s in users) if users else 0.0
            util[lid] = total / link.capacity_mbps
            pkt_bits = max((p.mean_packet_size_bytes[s] for s in users), default=0.0) * 8.0
            service_ms[lid] = pkt_bits / (link.capacity_mbps * 1e6) * 1e3
            powered = action.link_power.get(lid, True)
            if not powered and users:
                notes.append(f"load routed over powered-off link {lid}")
            if math.isnan(util[lid]):
                continue
            if util[lid] > p.max_valid_utilization:
                notes.append(f"link {lid} utilization {util[lid]:.3f} > {p.max_valid_utilization}")

        def per_link(lid: str, f) -> float:
            r = util[lid]
            if math.isnan(r) or r >= 1.0:
                return math.nan
            return f(lid, r)

        values: dict[str, float] = {}
        for lid in topo.links:
            values[f"link_utilization.{lid}"] = util[lid]
        for s in self.slices:
            hops = route[s]
            lat = sum(per_link(l, lambda l, r: topo.links[l].prop_delay_ms
                               + p.processing_delay_ms_per_hop
                               + P99_FACTOR * service_ms[l] / (1.0 - r)) for l in hops)
            jit = sum(per_link(l, lambda l, r: service_ms[l] / (1.0 - r)) for l in hops)
            q = sum(per_link(l, lambda l, r: r / (1.0 - r)) for l in hops)
            values[f"latency_p99_ms.{s}"] = p.latency_safety_factor * lat
            values[f"jitter_ms.{s}"] = p.latency_safety_factor * jit
            values[f"queue_occupancy_pkts.{s}"] = q
            values[f"loss_rate.{s}"] = 0.0 if not math.isnan(lat) else math.nan
            values[f"throughput_mbps.{s}"] = load[s]
            devices = demand.value(f"active_devices.{s}")
            values[f"active_users.{s}"] = min(devices, float(action.admission_limit[s]))
        values["energy_w"] = sum(
            p.link_idle_power_w + p.link_dynamic_power_w * util[lid]
            for lid in topo.links if action.link_power.get(lid, True)
        )
        for sw in topo.switches:
            key = f"flow_table_occupancy.{sw}"
            values[key] = state.value(key)
            if math.isnan(values[key]):
                notes.append(f"{key} unknown")

        metrics = {
            k: Measurement(None if math.isnan(v) else v, None) for k, v in values.items()
        }
        return Prediction(NetworkState(state.t + 1, metrics), not notes, tuple(notes))
