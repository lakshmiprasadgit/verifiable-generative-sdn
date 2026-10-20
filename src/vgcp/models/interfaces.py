"""Interfaces for the components the shield's rollout depends on (paper Eqs 12-14).

Stage 1 provides an analytical nominal model, a static fallback policy and a
constant upper-bound demand forecast. A learned world model W_psi (paper Sec
2.5) can later implement TransitionModel and report its uncertainty u_psi
through ``Prediction.uncertainty``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vgcp.action import ControlAction
from vgcp.state import Demand, NetworkState


@dataclass(frozen=True)
class Prediction:
    state: NetworkState
    # u >= 0. The analytical model reports 0 inside its validity domain and
    # +inf outside it; it is NOT a calibrated uncertainty (paper Eq 23).
    uncertainty: float
    notes: tuple[str, ...] = ()


class TransitionModel(Protocol):
    """Conservative nominal transition T-hat (paper Eq 12)."""

    def predict(self, state: NetworkState, action: ControlAction, demand: Demand) -> Prediction: ...

    def required_state_keys(self) -> frozenset[str]: ...

    def required_demand_keys(self) -> frozenset[str]: ...


class FallbackPolicy(Protocol):
    """Pre-computed safe fallback pi_0 (paper Eq 13, Assumption 3)."""

    def act(self, state: NetworkState) -> ControlAction: ...


class DemandForecast(Protocol):
    """Conservative demand forecast d-bar_{t+k}, k = 0..H-1 (paper Eq 12)."""

    def forecast(self, demand: Demand, horizon: int) -> list[Demand]: ...

    def required_demand_keys(self) -> frozenset[str]: ...
