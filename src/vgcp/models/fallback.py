"""Static fallback policy pi_0 (paper Eq 13, Assumption 3).

Stage 1 / Milestone 1: pi_0 returns one configured action regardless of state.
Whether this action is actually intent-feasible on the reachable state space
(Assumption 3) is NOT established here; it is checked offline in Milestone 4.
"""

from __future__ import annotations

from vgcp.action import ControlAction
from vgcp.state import NetworkState


class StaticFallbackPolicy:
    def __init__(self, action: ControlAction) -> None:
        self.action = action

    def act(self, state: NetworkState) -> ControlAction:
        return self.action
