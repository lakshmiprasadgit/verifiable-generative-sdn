"""Emulation layer without root: plan, OpenFlow rules, parsers, telemetry, backend logic."""

import math
import shutil
import subprocess

import pytest

from factories import action_with, config_with
from fake_fabric import FakeClock, FakeFabric
from test_sim import BASE
from vgcp.emu import MininetNetwork, plan_emulation
from vgcp.emu.openflow import (
    COOKIE_MASK,
    action_rules,
    all_classes,
    background_rules,
    class_cookie,
    meter_spec,
    parse_dump_flows,
    parse_dump_ports,
)
from vgcp.emu.telemetry import Snapshot, link_measurements, parse_ping, slice_measurements
from vgcp.emu.openflow import FlowCounters, PortCounters
from vgcp.errors import ConfigError
from vgcp.experiments.runner import run_trial, summarize
from vgcp.loop import ControllerFailure
from vgcp.shield import VerificationShield
from vgcp.sim import parse_scenario


@pytest.fixture
def plan(cfg):
    return plan_emulation(cfg)


def _paths(cfg):
    return {pid: p.nodes for pid, p in cfg.topology.paths.items()}


# ---------------------------------------------------------------- plan
def test_plan_ports_are_unique_and_consistent(cfg, plan):
    used = {}
    for link in plan.links.values():
        for sw, port in ((link.a, link.port_a), (link.b, link.port_b)):
            assert (sw, port) not in used
            used[(sw, port)] = link.id
    for h in list(plan.senders.values()) + list(plan.receivers.values()):
        assert (h.switch, h.port) not in used
        used[(h.switch, h.port)] = h.name
    assert plan.port_towards("s1", "s2") == plan.links["l12"].port_a
    assert plan.port_towards("s2", "s1") == plan.links["l12"].port_b
    assert set(plan.senders) == {"urllc", "embb", "mmtc", "bg"}
    assert all(len(h.name) <= 10 for h in plan.senders.values())  # interface names stay < 16 chars
    assert plan.dpid("s1") == "0000000000000001"


def test_plan_rejects_paths_against_link_direction():
    def mutate(raw):
        raw["network"]["topology"]["links"][0].update(a="s2", b="s1")  # l12 now s2 -> s1
    with pytest.raises(ConfigError, match="against its configured direction"):
        plan_emulation(config_with(mutate))


# ---------------------------------------------------------------- OpenFlow rules
def test_rules_follow_the_path_and_meter_at_ingress(cfg, plan):
    rules = action_rules(plan, _paths(cfg), cfg.fallback_action)
    embb = [r for r in rules if r.cookie == class_cookie(all_classes(cfg.fallback_action), "embb")]
    assert sorted({r.switch for r in embb}) == ["s1", "s3", "s5"]  # path B
    fwd = [r for r in embb if r.match.startswith(f"ip,nw_src={plan.senders['embb'].ip}")]
    assert [r.switch for r in fwd] == ["s1", "s3", "s5"]
    assert fwd[0].actions.startswith("meter:") and not fwd[1].actions.startswith("meter:")
    assert fwd[-1].actions == f"output:{plan.receivers['embb'].port}"
    assert len(embb) == 6  # forward + reverse on 3 switches


def test_cookies_separate_classes(cfg):
    classes = all_classes(cfg.fallback_action)
    cookies = {c: class_cookie(classes, c) for c in classes}
    assert len(set(cookies.values())) == len(classes)
    assert all(ck & COOKIE_MASK == ck for ck in cookies.values())


def test_meter_spec():
    assert meter_spec(2, 5.0) == "meter=2,kbps,burst,band=type=drop,rate=5000,burst_size=500"


@pytest.mark.skipif(shutil.which("ovs-ofctl") is None, reason="ovs-ofctl not installed")
def test_every_rule_is_accepted_by_ovs_ofctl(cfg, plan):
    rules = action_rules(plan, _paths(cfg), cfg.fallback_action)
    rules += background_rules(plan, _paths(cfg)["B"], all_classes(cfg.fallback_action))
    for r in rules:
        res = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "parse-flow", r.text()], capture_output=True, text=True)
        assert res.returncode == 0 and "OFPT_FLOW_MOD" in res.stdout, (r.text(), res.stderr)


# ---------------------------------------------------------------- parsers
DUMP_PORTS = """OFPST_PORT reply (OF1.3) (xid=0x2): 3 ports
  port LOCAL: rx pkts=0, bytes=0, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=0, bytes=0, drop=0, errs=0, coll=0
           duration=101.402s
  port  1: rx pkts=1200, bytes=1756800, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=2400, bytes=3513600, drop=3, errs=0, coll=0
           duration=101.399s
  port  4: rx pkts=?, bytes=?, drop=?, errs=?, frame=?, over=?, crc=?
           tx pkts=10, bytes=980, drop=0, errs=0, coll=0
           duration=101.399s
"""

DUMP_FLOWS = """ cookie=0x200, duration=12.345s, table=0, n_packets=5000, n_bytes=7500000, priority=100,ip,nw_src=10.0.2.1,nw_dst=10.0.2.2 actions=meter:2,output:3
 cookie=0x200, duration=12.345s, table=0, n_packets=40, n_bytes=3920, priority=100,ip,nw_src=10.0.2.2,nw_dst=10.0.2.1 actions=output:8
 cookie=0x400, duration=2.001s, table=0, n_packets=0, n_bytes=0, priority=50,ip,nw_src=10.0.4.1,nw_dst=10.0.4.2 actions=output:3
"""


def test_parse_dump_ports():
    p = parse_dump_ports(DUMP_PORTS)
    assert set(p) == {1, 4}  # LOCAL skipped
    assert p[1] == PortCounters(1200, 1756800, 2400, 3513600, 3)
    assert p[4].rx_bytes is None and p[4].tx_bytes == 980  # '?' = unsupported counter


def test_parse_dump_flows():
    f = parse_dump_flows(DUMP_FLOWS)
    assert [(x.cookie, x.priority, x.n_bytes, x.out_port) for x in f] == [
        (0x200, 100, 7500000, 3), (0x200, 100, 3920, 8), (0x400, 50, 0, 3)]
    assert f[0].match == "ip,nw_src=10.0.2.1,nw_dst=10.0.2.2"


def test_parse_ping():
    text = "64 bytes from 10.0.1.2: icmp_seq=1 ttl=64 time=0.412 ms\n64 bytes from 10.0.1.2: icmp_seq=3 ttl=64 time=0.398 ms\n"
    assert parse_ping(text) == [0.412, 0.398]


# ---------------------------------------------------------------- telemetry arithmetic
def test_background_is_link_rate_minus_managed_flow_rate(cfg, plan):
    l = plan.links["l13"]
    ck = {"embb": 0x200}
    flow = lambda b: FlowCounters(0x200, 100, f"ip,nw_src={plan.senders['embb'].ip},nw_dst={plan.receivers['embb'].ip}", 0, b, l.port_a)
    before = Snapshot(0.0, {"s1": {l.port_a: PortCounters(0, 0, 0, 0, 0)}}, {"s1": [flow(0)]})
    # 1 s: port sent 150 Mbit, the eMBB rule 80 Mbit -> 70 Mbit/s of background
    after = Snapshot(1.0, {"s1": {l.port_a: PortCounters(0, 0, 0, int(150e6 / 8), 0)}}, {"s1": [flow(int(80e6 / 8))]})
    m = link_measurements(plan, before, after, ck)
    assert m["background_load_mbps.l13"] == pytest.approx(70.0)
    assert m["link_utilization.l13"] == pytest.approx(150 / 200)


def test_counter_reset_is_unknown_not_zero(cfg, plan):
    l = plan.links["l13"]
    before = Snapshot(0.0, {"s1": {l.port_a: PortCounters(0, 0, 0, 1000, 0)}}, {})
    after = Snapshot(1.0, {"s1": {l.port_a: PortCounters(0, 0, 0, 10, 0)}}, {})
    assert math.isnan(link_measurements(plan, before, after, {})["background_load_mbps.l13"])


def test_meter_drops_are_not_counted_as_loss(cfg, plan):
    src, dst = plan.senders["embb"].ip, plan.receivers["embb"].ip
    f = lambda b: FlowCounters(0x200, 100, f"ip,nw_src={src},nw_dst={dst}", 0, b, 1)
    mb = lambda x: int(x * 1e6 / 8)
    before = Snapshot(0.0, {}, {sw: [f(0)] for sw in ("s1", "s3", "s5")})
    # offered 120 at s1, meter passes 100 to s3, 95 arrive at s5
    after = Snapshot(1.0, {}, {"s1": [f(mb(120))], "s3": [f(mb(100))], "s5": [f(mb(95))]}, {"embb": [20.0, 22.0]})
    m = slice_measurements(plan, before, after, {"embb": 0x200}, {"embb": ("s1", "s3", "s5")})
    assert m["offered_load_mbps.embb"] == pytest.approx(120)
    assert m["throughput_mbps.embb"] == pytest.approx(95)
    assert m["loss_rate.embb"] == pytest.approx(0.05)  # 1 - 95/100, not 1 - 95/120
    assert m["latency_p99_ms.embb"] == pytest.approx(11.0)  # RTT p99 / 2


# ---------------------------------------------------------------- backend logic with a fake fabric
def _scenario(cfg, **extra):
    return parse_scenario({**BASE, **extra}, {s.name for s in cfg.slices}, set(cfg.topology.links))


def _net(cfg, **extra):
    clock = FakeClock()
    lose = extra.pop("lose", None)
    fabric = FakeFabric(clock, lose)
    return MininetNetwork(cfg, _scenario(cfg, **extra), 1, fabric, clock=clock, sleep=clock.sleep), fabric, clock


def test_backend_installs_fallback_and_measures_slot0(cfg):
    net, fabric, clock = _net(cfg, background=[{"start": 0, "end": 10, "links": ["l13", "l35"], "mbps": 50.0}])
    assert clock.now == pytest.approx(1.0)  # slot 0 took one real slot
    assert {c[1] for c in fabric.calls if c[0] == "set_meter"} == {"s1"} and len(fabric.meters["s1"]) == 3
    obs = net.observe()
    assert obs.t == 0 and obs.now_s == 0.0
    assert obs.state.value("background_load_mbps.l13") == pytest.approx(50.0)  # eMBB excluded as managed
    assert obs.state.value("link_utilization.l13") == pytest.approx((80 + 50) / 200)
    assert obs.state.value("throughput_mbps.embb") == pytest.approx(80.0)
    assert obs.state.value("latency_p99_ms.embb") == pytest.approx((2 * 10 + 0.1) / 2)


def test_backend_measurements_pass_the_shield(cfg):
    net, _, _ = _net(cfg)
    obs = net.observe()
    cert = VerificationShield.from_config(cfg).verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    assert cert.check("state_measurements").status.value == "pass", cert.check("state_measurements").data


def test_backend_reroutes_rebudgets_and_powers_links(cfg):
    net, fabric, _ = _net(cfg)
    fabric.calls.clear()
    net.apply(action_with(cfg, path={"mmtc": "A"}, rate_budget_mbps={"embb": 60.0},
                          link_power={"l14": False, "l46": False, "l65": False}))
    net.advance()
    kinds = [c[0] for c in fabric.calls]
    assert kinds.count("del_flows") == len(cfg.topology.switches)  # mMTC rules removed everywhere
    assert ("set_meter", "s1", 1, 60.0, False) in fabric.calls  # eMBB is meter 1 (slices sorted: embb, mmtc, urllc)
    assert sum(1 for c in fabric.calls if c[0] == "set_port" and c[3] is False) == 6  # 3 links x 2 ends
    assert net.ground_truth()["installed"]["path"]["mmtc"] == "A"
    assert net.observe().state.value("throughput_mbps.mmtc") == pytest.approx(2.0)


def test_backend_controller_failure_and_actuation_delay(cfg):
    net, _, _ = _net(cfg, controller_failures=[{"start": 0, "end": 1}], actuation_delay_slots=1)
    with pytest.raises(ControllerFailure):
        net.apply(action_with(cfg, path={"embb": "C"}, rate_budget_mbps={"embb": 30.0}))
    net.advance()
    net.apply(action_with(cfg, path={"embb": "C"}, rate_budget_mbps={"embb": 30.0}))
    net.advance()
    assert net.ground_truth()["installed"]["path"]["embb"] == "B"  # delayed one slot
    net.advance()
    assert net.ground_truth()["installed"]["path"]["embb"] == "C"


def test_lost_probes_are_unknown_to_the_shield_and_infinite_in_scoring(cfg):
    net, _, _ = _net(cfg, lose={"urllc"})
    obs = net.observe()
    assert obs.state.metrics["latency_p99_ms.urllc"].value is None
    assert math.isinf(net.ground_truth()["latency_p99_ms"]["urllc"])
    cert = VerificationShield.from_config(cfg).verify(obs.state, obs.demand, cfg.fallback_action, obs.now_s)
    assert not cert.accepted and "latency_p99_ms.urllc" in cert.check("state_measurements").data["problems"]


def test_backend_rejects_background_on_two_paths(cfg):
    with pytest.raises(ConfigError, match="more than one path"):
        _net(cfg, background=[{"start": 0, "end": 5, "links": ["l13"], "mbps": 1.0},
                              {"start": 0, "end": 5, "links": ["l12"], "mbps": 1.0}])


def test_closed_loop_trial_runs_on_the_emulation_backend(cfg):
    clock = FakeClock()
    make = lambda c, sc, seed: MininetNetwork(c, sc, seed, FakeFabric(clock), clock=clock, sleep=clock.sleep)
    sc = _scenario(cfg, slots=6, background=[{"start": 2, "end": 5, "links": ["l13", "l35"], "mbps": 120.0}])
    rows = run_trial(cfg, sc, "shielded", 1, n_random=2, make_backend=make)
    assert len(rows) == 6 and all(r["truth_next"]["source"] == "measured" for r in rows)
    s = summarize(cfg, sc, rows)
    assert s["slots"] == 6 and s["apply_failures"] == 0
