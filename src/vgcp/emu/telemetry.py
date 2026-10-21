"""Turn two counter snapshots into measured state (pure functions).

Definitions (one control slot between snapshots, dt seconds):

  link rate l = (a -> b)   delta tx_bytes of switch a's port toward b
                           (links carry forward traffic in config order a -> b)
  managed rate on l        delta n_bytes of the slices' forward rules on switch a that
                           output to that port
  background load on l     link rate - managed rate      (audit H1; counters see
                           delivered, post-drop traffic, so overload under-measures it)
  offered load of a slice  delta bytes of its forward rule on the ingress switch
                           (counted before the meter drops anything)
  admitted                 delta bytes of its forward rule on the next switch (after
                           the meter: meter drops are budget enforcement, not loss)
  delivered (throughput)   delta bytes of its forward rule on the egress switch
  loss                     1 - delivered / admitted
  p99 latency              RTT p99 of the slot's ping probes / 2 (symmetric links)
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


def _flow_bytes(flows: list[FlowCounters], cookie: int, src_ip: str, dst_ip: str) -> int | None:
    for f in flows:
        if f.cookie == cookie and f"nw_src={src_ip}" in f.match and f"nw_dst={dst_ip}" in f.match:
            return f.n_bytes
    return None


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
                f0 = next((f for f in before.flows.get(link.a, []) if f.cookie == f1.cookie and f.match == f1.match), None)
                managed += _mbps(_delta(f1.n_bytes, f0.n_bytes if f0 else 0), dt)
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
            return _mbps(_delta(_flow_bytes(after.flows.get(sw, []), ck, src, dst),
                                _flow_bytes(before.flows.get(sw, []), ck, src, dst)), dt)

        offered, admitted, delivered = rate(nodes[0]), rate(nodes[1]), rate(nodes[-1])
        out[f"offered_load_mbps.{s}"] = offered
        out[f"throughput_mbps.{s}"] = delivered
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
