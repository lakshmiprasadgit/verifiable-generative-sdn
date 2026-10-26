"""Emulation plan: a pure function of the configuration (no Mininet import).

Fixes host names, IP addresses and OpenFlow port numbers so that the Mininet
topology builder and the OpenFlow rule builder cannot disagree about wiring.

* Every link of configs/network.yaml becomes a Mininet link with its capacity
  (HTB rate) and propagation delay (netem), port numbers assigned in config order.
* Each slice gets a sender on the ingress switch and a receiver on the egress
  switch; one extra host pair carries background (unmanaged) traffic.
* All hosts share 10.0.0.0/16 and use static ARP, so no flooding rules are needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from vgcp.config import ProjectConfig
from vgcp.errors import ConfigError

BACKGROUND = "bg"

# Rate units (DECISIONS 2026-10-26): every rate in the project (scenario demand and
# background, budgets, link capacity, telemetry) is a wire rate of Ethernet frames
# without FCS, which is what OVS rule and port counters, OVS meters and the HTB link
# shaper all count. Packet sizes are frame sizes. Only iperf3 works in UDP payload,
# so the traffic generator converts with these constants.
FRAME_OVERHEAD_BYTES = 42  # Ethernet header 14 + IPv4 20 + UDP 8
MAX_FRAME_BYTES = 1514  # 1500-byte IP MTU: a larger datagram would fragment into two frames
MIN_FRAME_BYTES = FRAME_OVERHEAD_BYTES + 16  # iperf3 needs 16 bytes of UDP payload for its own header


def udp_payload_bytes(frame_bytes: int) -> int:
    if not MIN_FRAME_BYTES <= frame_bytes <= MAX_FRAME_BYTES:
        raise ConfigError(f"frame size {frame_bytes} B outside [{MIN_FRAME_BYTES}, {MAX_FRAME_BYTES}] "
                          "(one unfragmented UDP datagram per frame)")
    return frame_bytes - FRAME_OVERHEAD_BYTES


def payload_mbps(frame_mbps: float, frame_bytes: int) -> float:
    """The iperf3 (UDP payload) rate that puts frame_mbps of frames on the wire."""
    return frame_mbps * udp_payload_bytes(frame_bytes) / frame_bytes


@dataclass(frozen=True)
class HostPlan:
    name: str
    ip: str
    switch: str
    port: int  # switch-side port number


@dataclass(frozen=True)
class LinkPlan:
    id: str
    a: str
    b: str
    port_a: int
    port_b: int
    capacity_mbps: float
    delay_ms: float


@dataclass(frozen=True)
class EmulationPlan:
    switches: tuple[str, ...]
    links: dict[str, LinkPlan]
    senders: dict[str, HostPlan]  # traffic class ("urllc", ..., "bg") -> source host
    receivers: dict[str, HostPlan]
    ingress: str
    egress: str

    def port_towards(self, switch: str, neighbour: str) -> int:
        for link in self.links.values():
            if (link.a, link.b) == (switch, neighbour):
                return link.port_a
            if (link.b, link.a) == (switch, neighbour):
                return link.port_b
        raise KeyError(f"no link between {switch} and {neighbour}")

    def link_ports(self, link_id: str) -> tuple[tuple[str, int], tuple[str, int]]:
        link = self.links[link_id]
        return (link.a, link.port_a), (link.b, link.port_b)

    def dpid(self, switch: str) -> str:
        return f"{self.switches.index(switch) + 1:016x}"

    def switch_interfaces(self) -> list[str]:
        """Root-namespace interface names Mininet creates for this plan ({switch}-eth{port}).
        Host-side interfaces live in the hosts' namespaces and vanish with their peers."""
        names = [f"{l.a}-eth{l.port_a}" for l in self.links.values()] + [f"{l.b}-eth{l.port_b}" for l in self.links.values()]
        names += [f"{h.switch}-eth{h.port}" for h in list(self.senders.values()) + list(self.receivers.values())]
        return sorted(names)


def plan_emulation(cfg: ProjectConfig) -> EmulationPlan:
    topo = cfg.topology
    next_port = {sw: 1 for sw in topo.switches}

    def take(sw: str) -> int:
        p = next_port[sw]
        next_port[sw] += 1
        return p

    # Telemetry reads each link's forward rate on its "a" side, so every path must use
    # its links in the configured a -> b direction (ingress towards egress).
    for pid, path in topo.paths.items():
        for u, v, lid in zip(path.nodes, path.nodes[1:], path.links):
            if (topo.links[lid].a, topo.links[lid].b) != (u, v):
                raise ConfigError(f"path {pid} uses link {lid} from {u} to {v}, against its configured direction "
                                  f"{topo.links[lid].a} -> {topo.links[lid].b}")
    links = {}
    for lid, link in topo.links.items():
        links[lid] = LinkPlan(lid, link.a, link.b, take(link.a), take(link.b), link.capacity_mbps, link.prop_delay_ms)
    classes = [s.name for s in cfg.slices] + [BACKGROUND]
    senders, receivers = {}, {}
    for i, c in enumerate(classes, start=1):
        senders[c] = HostPlan(f"{c}src", f"10.0.{i}.1", topo.ingress, take(topo.ingress))
        receivers[c] = HostPlan(f"{c}dst", f"10.0.{i}.2", topo.egress, take(topo.egress))
    return EmulationPlan(topo.switches, links, senders, receivers, topo.ingress, topo.egress)
