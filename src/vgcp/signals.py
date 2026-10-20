"""Signals seen by STL predicates p_i(s, a) (paper Eq 5).

At every time step the signal valuation is the union of
* each state metric key, e.g. ``latency_p99_ms.urllc``, and
* each numeric action component prefixed with ``action.``, e.g.
  ``action.rate_budget_mbps.embb`` (link power states as 1.0 / 0.0).

The categorical routing choice ``path[slice]`` is not exposed as a signal.
"""

from __future__ import annotations

from vgcp.action import ActionSchema, ControlAction
from vgcp.state import NetworkState, ObservationSchema

ACTION_PREFIX = "action."


def action_signal_names(schema: ActionSchema) -> tuple[str, ...]:
    names = []
    for s in schema.slice_names:
        names += [f"{ACTION_PREFIX}rate_budget_mbps.{s}", f"{ACTION_PREFIX}admission_limit.{s}"]
    names += [f"{ACTION_PREFIX}link_power.{link}" for link in schema.power_links]
    return tuple(names)


def step_signals(
    state_schema: ObservationSchema,
    action_schema: ActionSchema,
    state: NetworkState,
    action: ControlAction,
) -> dict[str, float]:
    """Signal valuation at one step; missing state metrics map to NaN. ``action`` must be valid."""
    sig = {key: state.value(key) for key in state_schema.keys}
    for s in action_schema.slice_names:
        sig[f"{ACTION_PREFIX}rate_budget_mbps.{s}"] = float(action.rate_budget_mbps[s])
        sig[f"{ACTION_PREFIX}admission_limit.{s}"] = float(action.admission_limit[s])
    for link in action_schema.power_links:
        sig[f"{ACTION_PREFIX}link_power.{link}"] = 1.0 if action.link_power[link] else 0.0
    return sig
