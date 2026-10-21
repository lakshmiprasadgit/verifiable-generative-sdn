"""OpenFlow 1.3 rules, meters and counter parsing for ovs-ofctl (pure functions).

Routing is proactive. For a traffic class (a slice, or background) routed over a
path s_0 .. s_k:
  forward  rule on every s_i: ip, src -> dst      -> output toward s_{i+1} (receiver at s_k)
  reverse  rule on every s_i: ip, dst -> src      -> output toward s_{i-1} (sender at s_0)
Slices are rate-limited by an OpenFlow meter on the ingress forward rule (the
slice's rate budget, the "meters police each slice" assumption of D16). Background
traffic has its own cookie and is never metered. Table-miss drops everything else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vgcp.action import ControlAction
from vgcp.emu.plan import BACKGROUND, EmulationPlan

SLICE_PRIORITY = 100
BACKGROUND_PRIORITY = 50
COOKIE_MASK = 0xFF00


def class_cookie(classes: list[str], cls: str) -> int:
    return (classes.index(cls) + 1) << 8


@dataclass(frozen=True)
class FlowRule:
    switch: str
    cookie: int
    priority: int
    match: str
    actions: str

    def text(self) -> str:
        return f"cookie={self.cookie:#x},priority={self.priority},{self.match},actions={self.actions}"

    @property
    def meter(self) -> int | None:
        m = re.match(r"meter:(\d+)", self.actions)
        return int(m.group(1)) if m else None


def path_rules(plan: EmulationPlan, cls: str, nodes: tuple[str, ...], cookie: int, priority: int,
               meter_id: int | None) -> list[FlowRule]:
    src, dst = plan.senders[cls], plan.receivers[cls]
    rules = []
    for i, sw in enumerate(nodes):
        out = plan.port_towards(sw, nodes[i + 1]) if i < len(nodes) - 1 else dst.port
        act = f"meter:{meter_id},output:{out}" if (i == 0 and meter_id is not None) else f"output:{out}"
        rules.append(FlowRule(sw, cookie, priority, f"ip,nw_src={src.ip},nw_dst={dst.ip}", act))
        back = plan.port_towards(sw, nodes[i - 1]) if i > 0 else src.port
        rules.append(FlowRule(sw, cookie, priority, f"ip,nw_src={dst.ip},nw_dst={src.ip}", f"output:{back}"))
    return rules


def slice_classes(action: ControlAction) -> list[str]:
    return sorted(action.path)


def all_classes(action: ControlAction) -> list[str]:
    return slice_classes(action) + [BACKGROUND]


def meter_id(action: ControlAction, slice_name: str) -> int:
    return slice_classes(action).index(slice_name) + 1


def action_rules(plan: EmulationPlan, paths: dict[str, tuple[str, ...]], action: ControlAction) -> list[FlowRule]:
    """Slice rules for an action; paths maps path id -> switch sequence."""
    classes = all_classes(action)
    rules = []
    for s in slice_classes(action):
        rules += path_rules(plan, s, paths[action.path[s]], class_cookie(classes, s), SLICE_PRIORITY,
                            meter_id(action, s))
    return rules


def background_rules(plan: EmulationPlan, nodes: tuple[str, ...], classes: list[str]) -> list[FlowRule]:
    return path_rules(plan, BACKGROUND, nodes, class_cookie(classes, BACKGROUND), BACKGROUND_PRIORITY, None)


def meter_spec(meter: int, mbps: float) -> str:
    kbps = max(1, int(round(mbps * 1000)))
    return f"meter={meter},kbps,burst,band=type=drop,rate={kbps},burst_size={max(1, kbps // 10)}"


# ---------------------------------------------------------------- counter parsing
@dataclass(frozen=True)
class PortCounters:
    rx_packets: int | None
    rx_bytes: int | None
    tx_packets: int | None
    tx_bytes: int | None
    tx_dropped: int | None


@dataclass(frozen=True)
class FlowCounters:
    cookie: int
    priority: int
    match: str
    n_packets: int
    n_bytes: int
    out_port: int | None


def _int_or_none(s: str) -> int | None:
    return int(s) if s.isdigit() else None


_PORT = re.compile(r"^\s*port\s+(\S+?):\s*rx pkts=(\S+?), bytes=(\S+?), drop=(\S+?),")
_TX = re.compile(r"^\s*tx pkts=(\S+?), bytes=(\S+?), drop=(\S+?),")


def parse_dump_ports(text: str) -> dict[int, PortCounters]:
    """`ovs-ofctl -O OpenFlow13 --no-names dump-ports SWITCH` -> counters per port number."""
    out: dict[int, PortCounters] = {}
    current: tuple[int, int | None, int | None] | None = None
    for line in text.splitlines():
        m = _PORT.match(line)
        if m:
            port = m.group(1).strip('"')
            current = (int(port), _int_or_none(m.group(2)), _int_or_none(m.group(3))) if port.isdigit() else None
            continue
        m = _TX.match(line)
        if m and current is not None:
            out[current[0]] = PortCounters(current[1], current[2], _int_or_none(m.group(1)),
                                           _int_or_none(m.group(2)), _int_or_none(m.group(3)))
            current = None
    return out


_FIELD = re.compile(r"(\w+)=([^,\s]+)")


def parse_dump_flows(text: str) -> list[FlowCounters]:
    """`ovs-ofctl -O OpenFlow13 --no-names dump-flows SWITCH` -> one entry per flow."""
    flows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("cookie=") or " actions=" not in line:
            continue
        head, actions = line.split(" actions=", 1)
        fields = dict(_FIELD.findall(head))
        match = head.split(", ")[-1].strip()
        # the last comma-separated group holds priority and the match
        match = re.sub(r"^.*?priority=\d+,?", "", match)
        out = re.search(r"output:(\d+)", actions)
        flows.append(FlowCounters(
            cookie=int(fields.get("cookie", "0"), 16),
            priority=int(fields.get("priority", "32768")),
            match=match,
            n_packets=int(fields.get("n_packets", "0")),
            n_bytes=int(fields.get("n_bytes", "0")),
            out_port=int(out.group(1)) if out else None,
        ))
    return flows


_METER = re.compile(r"meter=(\d+)(.*?)(?=meter=\d+|\Z)", re.S)


def parse_dump_meters(text: str) -> dict[int, int | None]:
    """`ovs-ofctl -O OpenFlow13 dump-meters SWITCH` -> drop-band rate (kbps) per meter id."""
    out: dict[int, int | None] = {}
    for m in _METER.finditer(text):
        rate = re.search(r"rate=(\d+)", m.group(2))
        out[int(m.group(1))] = int(rate.group(1)) if rate else None
    return out


def parse_meter_features(text: str) -> int | None:
    """`ovs-ofctl -O OpenFlow13 meter-features SWITCH` -> max_meter (0 = no meter support)."""
    m = re.search(r"max_meter:(\d+)", text)
    return int(m.group(1)) if m else None
