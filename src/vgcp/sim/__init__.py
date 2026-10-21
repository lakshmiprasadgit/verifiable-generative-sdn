"""Simulated ground-truth network for closed-loop experiments (no root needed)."""

from vgcp.sim.network import SimulatedNetwork
from vgcp.sim.scenario import Scenario, load_scenario, parse_scenario

__all__ = ["SimulatedNetwork", "Scenario", "load_scenario", "parse_scenario"]
