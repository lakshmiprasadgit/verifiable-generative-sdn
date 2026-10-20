"""Constant upper-bound demand forecast d-bar (paper Eq 12).

d-bar_{t+k} = (1 + margin) * d_t for every demand metric and k = 0..H-1.

This is conservative for load-driven quantities (utilization, queueing,
latency), but NOT for lower-bound intents on throughput, where a higher demand
forecast is optimistic. See docs/milestone1_design.md.
"""

from __future__ import annotations

import math

from vgcp.state import Demand, Measurement, ObservationSchema


class UpperBoundConstantForecast:
    def __init__(self, demand_schema: ObservationSchema, margin: float) -> None:
        if not (math.isfinite(margin) and margin >= 0):
            raise ValueError("forecast margin must be a finite number >= 0")
        self.schema = demand_schema
        self.margin = margin

    def required_demand_keys(self) -> frozenset[str]:
        return frozenset(self.schema.keys)

    def forecast(self, demand: Demand, horizon: int) -> list[Demand]:
        metrics = {}
        for key in self.schema.keys:
            v = demand.value(key)
            metrics[key] = Measurement(None if math.isnan(v) else v * (1.0 + self.margin), None)
        return [Demand(demand.t + k, dict(metrics)) for k in range(horizon)]
