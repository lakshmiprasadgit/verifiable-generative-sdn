"""Turn two counter snapshots into measured state (pure functions).

Definitions (one control slot between snapshots, dt seconds):

  link rate l = (a -> b)   delta tx_bytes of switch a's port toward b
                           (links carry forward traffic in config order a -> b)
  managed rate on l        the slices whose forward rule on a outputs to that port,
                           counted by the same rule on switch b, i.e. what arrived
                           over l. (Counting on a was wrong at the ingress: a slice's
                           ingress rule counts packets before its meter drops them,
                           which under-measured background; Mininet audit 2026-10-22.)
  background load on l     link rate - managed rate      (audit H1; counters see
                           delivered, post-drop traffic, so overload under-measures it)
  offered load of a slice  delta bytes of its forward rule on the ingress switch
                           (counted before the meter drops anything)
  admitted                 delta bytes of its forward rule on the next switch (after
                           the meter: meter drops are budget enforcement, not loss)
  delivered (throughput)   delta bytes of its forward rule on the egress switch
  loss                     1 - delivered / admitted
  p99 latency              RTT p99 of the slot's ping probes / 2 (symmetric links);
                           nearest rank, so with 100 probes the 99th smallest

All rates are Ethernet frame rates (without FCS), as OVS counts them; see plan.py.

Rule counters across a reinstall (reroutes delete and re-add rules): a rule is the
same rule as in the previous snapshot only if its age (OVS "duration") grew by the
interval. Otherwise its counter restarted, and its rate is its bytes over its own
age when that covers most of the slot, else unknown. Comparing counters of two
different rules gave NaN or silently wrong values (Mininet audit 2026-10-22).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from vgcp.emu.openflow import FlowCounters, PortCounters
from vgcp.emu.plan import EmulationPlan


@dataclass(frozen=True)
class Snapshot:
    time_s: float
    ports: dict[str, dict[int, PortCounters]]
    flows: dict[str, list[FlowCounters]]
    rtts_ms: dict[str, list[float]] = field(default_factory=dict)  # per slice, probes of the slot


def _mbps(delta_bytes: float, dt: float) -> float:
    return delta_bytes * 8 / dt / 1e6


REINSTALL_TOLERANCE_S = 0.25  # slack when comparing rule ages with the snapshot interval
MIN_RULE_AGE_S = 0.25  # a reinstalled rule younger than this gives no usable rate


def _find(flows: list[FlowCounters], cookie: int, match: str) -> FlowCounters | None:
    return next((f for f in flows if f.cookie == cookie and f.match == match), None)


def _flow(flows: list[FlowCounters], cookie: int, src_ip: str, dst_ip: str) -> FlowCounters | None:
    for f in flows:
        if f.cookie == cookie and f"nw_src={src_ip}" in f.match and f"nw_dst={dst_ip}" in f.match:
            return f
    return None


def flow_rate_mbps(new: FlowCounters | None, old: FlowCounters | None, dt: float) -> float:
    """Rate of one rule over the interval; NaN (unknown) when it cannot be measured."""
    if new is None:
        return math.nan
    same_rule = old is not None and new.n_bytes >= old.n_bytes and (
        new.duration_s is None or old.duration_s is None
        or new.duration_s >= old.duration_s + dt - REINSTALL_TOLERANCE_S)
    if same_rule:
        return _mbps(float(new.n_bytes - old.n_bytes), dt)
    # The counter restarted (rule reinstalled, or reset): use the rule's own life, if it
    # spans most of this interval and nothing older.
    age = new.duration_s
    if age is not None and MIN_RULE_AGE_S <= age <= dt + REINSTALL_TOLERANCE_S:
        return _mbps(float(new.n_bytes), age)
    return math.nan


def _delta(new: int | None, old: int | None) -> float:
    if new is None or old is None or new < old:  # counter missing, or reset (rule re-installed)
        return math.nan
    return float(new - old)


def link_measurements(plan: EmulationPlan, before: Snapshot, after: Snapshot,
                      slice_cookies: dict[str, int]) -> dict[str, float]:
    dt = after.time_s - before.time_s
    out: dict[str, float] = {}
    managed_cookies = set(slice_cookies.values())
    for lid, link in plan.links.items():
        p0 = before.ports.get(link.a, {}).get(link.port_a)
        p1 = after.ports.get(link.a, {}).get(link.port_a)
        rate = _mbps(_delta(p1.tx_bytes if p1 else None, p0.tx_bytes if p0 else None), dt)
        managed = 0.0
        for f1 in after.flows.get(link.a, []):
            if f1.cookie in managed_cookies and f1.out_port == link.port_a:
                # what crossed l is counted on b (after the ingress meter and l's queue)
                managed += flow_rate_mbps(_find(after.flows.get(link.b, []), f1.cookie, f1.match),
                                          _find(before.flows.get(link.b, []), f1.cookie, f1.match), dt)
        out[f"link_utilization.{lid}"] = rate / link.capacity_mbps
        out[f"background_load_mbps.{lid}"] = max(0.0, rate - managed) if not math.isnan(rate + managed) else math.nan
    return out


def slice_measurements(plan: EmulationPlan, before: Snapshot, after: Snapshot, slice_cookies: dict[str, int],
                       paths: dict[str, tuple[str, ...]]) -> dict[str, float]:
    """paths: slice -> switch sequence it was routed over during the slot."""
    dt = after.time_s - before.time_s
    out: dict[str, float] = {}
    for s, nodes in paths.items():
        src, dst, ck = plan.senders[s].ip, plan.receivers[s].ip, slice_cookies[s]

        def rate(sw: str) -> float:
            return flow_rate_mbps(_flow(after.flows.get(sw, []), ck, src, dst),
                                  _flow(before.flows.get(sw, []), ck, src, dst), dt)

        offered, admitted, delivered = rate(nodes[0]), rate(nodes[1]), rate(nodes[-1])
        out[f"offered_load_mbps.{s}"] = offered
        out[f"throughput_mbps.{s}"] = delivered
        if math.isnan(admitted) or math.isnan(delivered):
            out[f"loss_rate.{s}"] = math.nan  # unknown, never 0
        else:
            out[f"loss_rate.{s}"] = min(1.0, max(0.0, 1.0 - delivered / admitted)) if admitted > 0 else 0.0
        rtts = after.rtts_ms.get(s, [])
        if rtts:
            ordered = sorted(rtts)
            out[f"latency_p99_ms.{s}"] = ordered[min(len(ordered) - 1, math.ceil(0.99 * len(ordered)) - 1)] / 2
            mean = sum(rtts) / len(rtts)
            out[f"jitter_ms.{s}"] = math.sqrt(sum((r - mean) ** 2 for r in rtts) / len(rtts)) / 2
        else:
            out[f"latency_p99_ms.{s}"] = math.nan  # no probe reply: unknown, never "fast"
            out[f"jitter_ms.{s}"] = math.nan
    return out


_PING = re.compile(r"time=([\d.]+) ms")


def parse_ping(text: str) -> list[float]:
    """RTTs in ms from `ping` output (lost probes simply have no line)."""
    return [float(m) for m in _PING.findall(text)]
