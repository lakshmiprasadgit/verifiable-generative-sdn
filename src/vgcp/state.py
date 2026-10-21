"""Network state s_t (paper Eq 1) and exogenous input d_t (paper Eq 3).

Both are represented as a set of named scalar measurements. Each measurement
carries the time it was taken so that stale data can be detected; a missing
measurement is represented explicitly (value None) and is never replaced by a
default. The ordered key list of an ObservationSchema defines the vector
embedding s_t in R^{n_s} (and d_t in R^{n_d}) used by later learned components.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from vgcp.errors import ConfigError, is_finite_real, is_real

# family -> (index set, unit). Index sets: "link", "slice", "switch", "global".
# Paper Sec 2.1 lists: link utilizations; per-slice queue occupancies; per-flow
# latency and jitter; flow-table/TCAM occupancy; radio resource block utilization;
# energy; active users per slice; packet drop rates; routing table summaries.
# Radio RB utilization is omitted (no RAN in the Mininet prototype); latency,
# jitter and loss are aggregated per slice; the routing summary is the current
# action, which the controller records separately.
STATE_FAMILIES: dict[str, tuple[str, str]] = {
    "link_utilization": ("link", "fraction of capacity"),
    # Traffic on the link outside the managed slices: link rate minus the managed
    # slices' flow rates on it (OpenFlow port and flow statistics). Audit H1.
    "background_load_mbps": ("link", "Mbit/s"),
    "latency_p99_ms": ("slice", "ms"),
    "jitter_ms": ("slice", "ms"),
    "loss_rate": ("slice", "fraction of packets"),
    "throughput_mbps": ("slice", "Mbit/s"),
    "queue_occupancy_pkts": ("slice", "packets"),
    "active_users": ("slice", "count"),
    "flow_table_occupancy": ("switch", "entries"),
    "energy_w": ("global", "W (proxy)"),
}

# Paper Sec 2.1: traffic matrices, mobility, channel conditions, demand patterns.
# Stage 1 uses per-slice offered load and device population only.
DEMAND_FAMILIES: dict[str, tuple[str, str]] = {
    "offered_load_mbps": ("slice", "Mbit/s"),
    "active_devices": ("slice", "count"),
}


@dataclass(frozen=True)
class Measurement:
    """One scalar. ``value=None`` means "not measured".

    ``timestamp_s`` is when the value was measured, on the same clock as the
    ``now_s`` argument of the shield. Predicted (model) values carry ``None``.
    """

    value: float | None
    timestamp_s: float | None = None


@dataclass(frozen=True)
class Observation:
    t: int
    metrics: Mapping[str, Measurement] = field(default_factory=dict)

    @classmethod
    def from_values(
        cls, t: int, values: Mapping[str, float | None], timestamp_s: float | None = None
    ):
        return cls(t, {k: Measurement(v, timestamp_s) for k, v in values.items()})

    def value(self, key: str) -> float:
        """The numeric value, or NaN if missing or not a real number."""
        m = self.metrics.get(key)
        if m is None or not is_real(m.value):
            return math.nan
        return float(m.value)


@dataclass(frozen=True)
class NetworkState(Observation):
    """s_t in S (paper Eq 1)."""


@dataclass(frozen=True)
class Demand(Observation):
    """d_t in D (paper Eq 3)."""


class MetricStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    NOT_NUMERIC = "not_numeric"
    NON_FINITE = "non_finite"
    OUT_OF_BOUNDS = "out_of_bounds"
    NO_TIMESTAMP = "no_timestamp"
    INVALID_TIMESTAMP = "invalid_timestamp"  # NaN or +/-inf
    FUTURE_TIMESTAMP = "future_timestamp"
    STALE = "stale"
    UNKNOWN_KEY = "unknown_key"


@dataclass(frozen=True)
class MetricSpec:
    key: str
    family: str
    unit: str
    lower: float
    upper: float


class ObservationSchema:
    """Ordered, bounded set of metric keys (the bounded sets S and D, Assumption 4)."""

    def __init__(self, specs: Sequence[MetricSpec]) -> None:
        self.specs: dict[str, MetricSpec] = {}
        for spec in specs:
            if spec.key in self.specs:
                raise ConfigError(f"duplicate metric key '{spec.key}'")
            self.specs[spec.key] = spec
        self.keys: tuple[str, ...] = tuple(self.specs)

    @classmethod
    def build(
        cls,
        families: Mapping[str, tuple[str, str]],
        index_sets: Mapping[str, Sequence[str]],
        bounds: Mapping[str, tuple[float, float]],
    ) -> "ObservationSchema":
        specs = []
        for family, (index, unit) in families.items():
            if family not in bounds:
                raise ConfigError(f"no bounds configured for metric family '{family}'")
            lo, hi = bounds[family]
            if index == "global":
                specs.append(MetricSpec(family, family, unit, lo, hi))
            else:
                for item in index_sets[index]:
                    specs.append(MetricSpec(f"{family}.{item}", family, unit, lo, hi))
        return cls(specs)

    def check(
        self,
        obs: Observation,
        keys: Sequence[str] | None = None,
        now_s: float | None = None,
        max_age_s: float | None = None,
    ) -> dict[str, MetricStatus]:
        """Status of each requested key; unexpected keys in ``obs`` are UNKNOWN_KEY.

        Freshness is checked only when ``now_s`` is given (measured states);
        predicted states have no timestamps.
        """
        statuses: dict[str, MetricStatus] = {
            k: MetricStatus.UNKNOWN_KEY for k in obs.metrics if k not in self.specs
        }
        for key in self.keys if keys is None else keys:
            spec = self.specs[key]
            m = obs.metrics.get(key)
            if m is None or m.value is None:
                status = MetricStatus.MISSING
            elif not is_real(m.value):
                status = MetricStatus.NOT_NUMERIC
            elif not is_finite_real(m.value):
                status = MetricStatus.NON_FINITE
            elif not spec.lower <= m.value <= spec.upper:
                status = MetricStatus.OUT_OF_BOUNDS
            elif now_s is None:
                status = MetricStatus.OK
            elif m.timestamp_s is None or not is_real(m.timestamp_s):
                status = MetricStatus.NO_TIMESTAMP
            elif not is_finite_real(m.timestamp_s):
                # Must precede the comparisons below: every comparison with NaN is
                # False, so a NaN timestamp would otherwise fall through to OK.
                status = MetricStatus.INVALID_TIMESTAMP
            elif m.timestamp_s > now_s:
                status = MetricStatus.FUTURE_TIMESTAMP
            elif max_age_s is not None and now_s - m.timestamp_s > max_age_s:
                status = MetricStatus.STALE
            else:
                status = MetricStatus.OK
            statuses[key] = status
        return statuses

    def to_vector(self, obs: Observation) -> list[float]:
        """Embedding in R^n with NaN for missing entries."""
        return [obs.value(k) for k in self.keys]

    def from_vector(
        self, vec: Sequence[float], t: int, timestamp_s: float | None = None, cls=NetworkState
    ) -> Observation:
        if len(vec) != len(self.keys):
            raise ValueError(f"expected {len(self.keys)} entries, got {len(vec)}")
        metrics = {}
        for key, v in zip(self.keys, vec):
            missing = v is None or (is_real(v) and math.isnan(v))
            metrics[key] = Measurement(None if missing else float(v), timestamp_s)
        return cls(t, metrics)
