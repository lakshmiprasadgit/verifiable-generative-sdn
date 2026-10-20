"""Transport topology: switches, links, and the candidate ingress-to-egress paths.

The topology is the structure over which the state s_t (link utilizations,
flow-table occupancy) and the routing part of the action a_t are defined
(paper Sec 2.1). It is instantiated in Mininet in Milestone 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from vgcp.errors import ConfigError


@dataclass(frozen=True)
class Link:
    """Undirected, full-duplex link. Capacity applies independently per direction."""

    id: str
    a: str
    b: str
    capacity_mbps: float
    prop_delay_ms: float


@dataclass(frozen=True)
class Path:
    id: str
    nodes: tuple[str, ...]
    links: tuple[str, ...]


class Topology:
    def __init__(
        self,
        switches: Sequence[str],
        links: Sequence[Link],
        paths: Mapping[str, Sequence[str]],
        ingress: str,
        egress: str,
        power_controllable_links: Sequence[str] = (),
    ) -> None:
        self.switches: tuple[str, ...] = tuple(switches)
        if not self.switches:
            raise ConfigError("topology: no switches")
        if len(set(self.switches)) != len(self.switches):
            raise ConfigError("topology: duplicate switch names")
        for name, node in (("ingress", ingress), ("egress", egress)):
            if node not in self.switches:
                raise ConfigError(f"topology: {name} '{node}' is not a switch")
        if ingress == egress:
            raise ConfigError("topology: ingress and egress must differ")
        self.ingress = ingress
        self.egress = egress

        self.links: dict[str, Link] = {}
        self._by_endpoints: dict[frozenset[str], Link] = {}
        for link in links:
            if link.id in self.links:
                raise ConfigError(f"topology: duplicate link id '{link.id}'")
            if link.a not in self.switches or link.b not in self.switches:
                raise ConfigError(f"topology: link '{link.id}' references an unknown switch")
            if link.a == link.b:
                raise ConfigError(f"topology: link '{link.id}' is a self-loop")
            key = frozenset((link.a, link.b))
            if key in self._by_endpoints:
                raise ConfigError(
                    f"topology: parallel links between {link.a} and {link.b} are not supported"
                )
            if not (math.isfinite(link.capacity_mbps) and link.capacity_mbps > 0):
                raise ConfigError(f"topology: link '{link.id}' needs a positive finite capacity")
            if not (math.isfinite(link.prop_delay_ms) and link.prop_delay_ms >= 0):
                raise ConfigError(f"topology: link '{link.id}' needs a non-negative delay")
            self.links[link.id] = link
            self._by_endpoints[key] = link

        self.paths: dict[str, Path] = {}
        for pid, nodes in paths.items():
            problems = self.path_problems(nodes)
            if problems:
                raise ConfigError(f"topology: path '{pid}': " + "; ".join(problems))
            hops = zip(nodes, list(nodes)[1:])
            link_ids = tuple(self._by_endpoints[frozenset(hop)].id for hop in hops)
            self.paths[str(pid)] = Path(str(pid), tuple(nodes), link_ids)
        if not self.paths:
            raise ConfigError("topology: no paths")

        unknown = [lid for lid in power_controllable_links if lid not in self.links]
        if unknown:
            raise ConfigError(f"topology: unknown power-controllable links {unknown}")
        self.power_controllable_links: tuple[str, ...] = tuple(power_controllable_links)

    def path_problems(self, nodes: Sequence[str]) -> list[str]:
        """Protocol invariants for a route: known switches, ingress->egress, loop-free, contiguous."""
        nodes = list(nodes)
        if len(nodes) < 2:
            return ["a path needs at least two switches"]
        problems = []
        unknown = [n for n in nodes if n not in self.switches]
        if unknown:
            problems.append(f"unknown switches {unknown}")
        if nodes[0] != self.ingress:
            problems.append(f"starts at {nodes[0]}, not ingress {self.ingress}")
        if nodes[-1] != self.egress:
            problems.append(f"ends at {nodes[-1]}, not egress {self.egress}")
        if len(set(nodes)) != len(nodes):
            problems.append("revisits a switch (not loop-free)")
        for u, v in zip(nodes, nodes[1:]):
            if frozenset((u, v)) not in self._by_endpoints:
                problems.append(f"no link between {u} and {v}")
        return problems
