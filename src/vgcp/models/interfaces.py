"""Interfaces for the components the shield's rollout depends on (paper Eqs 12-14).

Stage 1 provides an analytical nominal model, a static fallback policy and a
constant upper-bound demand forecast.

The certificate (Eq 14) is computed with the nominal model T-hat. The learned
world model W_psi, its uncertainty u_psi (Eqs 22-23) and the out-of-distribution
trigger u_psi > eta (Def 2, Constraint 3) belong to candidate selection in the
closed loop (Eq 42; Sec 3, step 6), not to the shield. Stage 1 has no learned
model, so W_psi will get its own interface when one exists; it is deliberately
not modelled as a TransitionModel here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vgcp.action import ControlAction
from vgcp.state import Demand, NetworkState


@dataclass(frozen=True)
class Prediction:
    state: NetworkState
    # False if the inputs fall outside the region where the model's formulas are
    # meant to apply (implementation extension D12). Not the paper's u_psi.
    in_domain: bool
    notes: tuple[str, ...] = ()


class TransitionModel(Protocol):
    """Nominal transition model T-hat (paper Eq 12).

    The paper requires T-hat to be conservative. That is not established for the
    Stage 1 analytic model (it is uncalibrated); see docs/milestone1_design.md.
    """

    def predict(self, state: NetworkState, action: ControlAction, demand: Demand) -> Prediction: ...

    def required_state_keys(self) -> frozenset[str]: ...

    def required_demand_keys(self) -> frozenset[str]: ...

    def unmodelled_state_keys(self) -> frozenset[str]:
        """State keys whose predicted values are placeholders (constant or carried
        forward), not predictions. Intents may read them only at the current step."""
        ...


class FallbackPolicy(Protocol):
    """Pre-computed safe fallback pi_0 (paper Eq 13, Assumption 3)."""

    def act(self, state: NetworkState) -> ControlAction: ...


class DemandForecast(Protocol):
    """Demand forecast d-bar_{t+k}, k = 0..H-1 (paper Eq 12 asks for a conservative one;
    an upper bound is conservative for load and latency only, see D10)."""

    def forecast(self, demand: Demand, horizon: int) -> list[Demand]: ...

    def required_demand_keys(self) -> frozenset[str]: ...
