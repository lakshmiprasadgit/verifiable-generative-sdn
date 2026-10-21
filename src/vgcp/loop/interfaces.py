"""Boundaries of the closed control loop (paper Sec 3, steps 1-7).

    NetworkBackend.observe()  ->  Observation (s_t, d_t, controller clock)       step 1
    CandidateGenerator.propose(Observation) -> ranked candidates                 step 2
    VerificationShield.verify(...) -> Certificate per candidate                  step 3-4
    controller selects (Milestone 2: first certified candidate in rank order)    step 5
    CertifiedApplier.apply_*  -> NetworkBackend.apply(action)                    step 6-7
    NetworkBackend.advance()  -> one control slot elapses; next observe() is the
                                 post-action measurement

Each boundary is a Protocol so the simulated and the Mininet backends, and later a
generative candidate generator (G_theta), plug in without changing the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vgcp.action import ControlAction
from vgcp.state import Demand, NetworkState


@dataclass(frozen=True)
class Observation:
    """What the controller knows at decision time t."""

    t: int
    state: NetworkState
    demand: Demand
    now_s: float  # controller clock when the observation was assembled


class ControllerFailure(RuntimeError):
    """The network did not accept an action (controller or switch failure)."""


class NetworkBackend(Protocol):
    def observe(self) -> Observation:
        """Assemble s_t and d_t from telemetry. Missing or late data must appear as
        missing or old measurements, never as made-up values."""
        ...

    def apply(self, action: ControlAction) -> None:
        """Install an action. Raises ControllerFailure if the network rejects it.
        Only CertifiedApplier / UncheckedApplier may call this."""
        ...

    def advance(self) -> None:
        """Let one control slot elapse."""
        ...

    def ground_truth(self) -> dict[str, Any] | None:
        """For simulation only: the true network condition of the slot that just
        elapsed. Real backends return None (only measurements exist)."""
        ...


@dataclass(frozen=True)
class Candidate:
    label: str  # which heuristic produced it, e.g. "greedy-embb"
    action: ControlAction


class CandidateGenerator(Protocol):
    def propose(self, obs: Observation) -> list[Candidate]:
        """Candidates in the controller's order of preference (best first)."""
        ...
