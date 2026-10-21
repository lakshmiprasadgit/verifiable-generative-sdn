"""Emulated network backend: Mininet + Open vSwitch (OpenFlow 1.3), iperf3, ping.

Only `fabric.MininetFabric` needs root; the plan, rules, parsers, telemetry and the
backend logic are pure and unit-tested without it.
"""

from vgcp.emu.backend import MininetNetwork
from vgcp.emu.fabric import Fabric, FabricError, MininetFabric
from vgcp.emu.plan import EmulationPlan, plan_emulation

__all__ = ["MininetNetwork", "Fabric", "FabricError", "MininetFabric", "EmulationPlan", "plan_emulation"]
