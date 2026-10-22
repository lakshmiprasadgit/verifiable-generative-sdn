"""Emulation layer without root: plan, OpenFlow rules, parsers, telemetry, backend logic."""

import math
import shutil
import subprocess

import pytest

from factories import action_with, config_with
from fake_fabric import FakeClock, FakeFabric
from test_sim import BASE
from vgcp.emu import FabricError, MininetFabric, MininetNetwork, plan_emulation
from vgcp.emu import fabric as fabric_mod
from vgcp.emu.openflow import (
    COOKIE_MASK,
    action_rules,
    all_classes,
    background_rules,
    class_cookie,
    FlowRule,
    meter_id,
    meter_spec,
    parse_dump_flows,
    parse_dump_meters,
    parse_dump_ports,
    parse_meter_features,
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
    match = f"ip,nw_src={plan.senders['embb'].ip},nw_dst={plan.receivers['embb'].ip}"
    flow = lambda b, age: FlowCounters(0x200, 100, match, 0, b, l.port_a, age)
    before = Snapshot(0.0, {"s1": {l.port_a: PortCounters(0, 0, 0, 0, 0)}}, {"s1": [flow(0, 5.0)], "s3": [flow(0, 5.0)]})
    # 1 s: port sent 150 Mbit. eMBB offered 100 Mbit at the ingress rule (before its
    # meter); 80 Mbit crossed l13 (counted on s3) -> 70 Mbit/s of background, not 50.
    after = Snapshot(1.0, {"s1": {l.port_a: PortCounters(0, 0, 0, int(150e6 / 8), 0)}},
                     {"s1": [flow(int(100e6 / 8), 6.0)], "s3": [flow(int(80e6 / 8), 6.0)]})
    m = link_measurements(plan, before, after, ck)
    assert m["background_load_mbps.l13"] == pytest.approx(70.0)
    assert m["link_utilization.l13"] == pytest.approx(150 / 200)


def test_reinstalled_rule_is_not_compared_with_its_predecessor(cfg, plan):
    """Reroute: the s5 rule is deleted and re-added; its new counter must not be
    subtracted from the old rule's counter (gave NaN or silently wrong rates)."""
    from vgcp.emu.telemetry import flow_rate_mbps
    old = FlowCounters(0x200, 100, "m", 0, int(10e6 / 8), 1, 1.0)
    same = FlowCounters(0x200, 100, "m", 0, int(30e6 / 8), 1, 2.0)
    assert flow_rate_mbps(same, old, 1.0) == pytest.approx(20.0)  # same rule, aged by 1 s
    new = FlowCounters(0x200, 100, "m", 0, int(10e6 / 8 + 1000), 1, 0.95)  # reinstalled 0.95 s ago
    assert flow_rate_mbps(new, old, 1.0) == pytest.approx((10e6 / 8 + 1000) * 8 / 0.95 / 1e6)  # own lifetime, not ~0
    young = FlowCounters(0x200, 100, "m", 0, 100, 1, 0.1)
    assert math.isnan(flow_rate_mbps(young, old, 1.0))  # too young to measure: unknown, not 0
    assert math.isnan(flow_rate_mbps(None, old, 1.0))
    no_age = FlowCounters(0x200, 100, "m", 0, 5, 1)
    assert math.isnan(flow_rate_mbps(no_age, FlowCounters(0x200, 100, "m", 0, 50, 1), 1.0))  # reset, no age known


def test_reroute_keeps_measurements_after_counter_reset(cfg):
    net, fabric, _ = _net(cfg)
    net.apply(action_with(cfg, path={"mmtc": "A"}))
    net.advance()
    st = net.observe().state
    assert st.value("throughput_mbps.mmtc") == pytest.approx(2.0)  # was 0.0 before the fix
    assert net.observe().demand.value("offered_load_mbps.mmtc") == pytest.approx(2.0)


def test_metered_slice_does_not_hide_background(cfg):
    """Budget below demand: the ingress rule counts 80, only 60 crosses l13."""
    net, _, _ = _net(cfg, background=[{"start": 0, "end": 10, "links": ["l13", "l35"], "mbps": 50.0}])
    net.apply(action_with(cfg, rate_budget_mbps={"embb": 60.0}))
    net.advance()
    net.advance()
    st = net.observe().state
    assert st.value("background_load_mbps.l13") == pytest.approx(50.0)  # pre-fix: 30
    assert st.value("throughput_mbps.embb") == pytest.approx(60.0)


def test_unknown_admitted_rate_gives_unknown_loss(cfg, plan):
    src, dst = plan.senders["embb"].ip, plan.receivers["embb"].ip
    f = lambda b: FlowCounters(0x200, 100, f"ip,nw_src={src},nw_dst={dst}", 0, b, 1)
    before = Snapshot(0.0, {}, {"s1": [f(0)], "s5": [f(0)]})  # no rule on s3: admitted unknown
    after = Snapshot(1.0, {}, {"s1": [f(100)], "s3": [f(100)], "s5": [f(100)]})
    m = slice_measurements(plan, before, after, {"embb": 0x200}, {"embb": ("s1", "s3", "s5")})
    assert math.isnan(m["loss_rate.embb"])  # pre-fix: 0.0


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



# ---------------------------------------------------------------- first Mininet run (2026-10-21) regressions
# Failure 1: s1 rejected "actions=meter:1,output:2" with OFPMMFC_INVALID_METER because the
# flows of a slice were installed before its meter. The fake fabric now rejects that too.
def test_meters_exist_before_any_flow_that_references_them(cfg):
    _, fabric, _ = _net(cfg)
    first_flow = next(i for i, c in enumerate(fabric.calls) if c[0] == "add_flows")
    meter_calls = [i for i, c in enumerate(fabric.calls) if c[0] == "set_meter"]
    assert len(meter_calls) == 3 and max(meter_calls) < first_flow
    assert fabric.meters == {"s1": {meter_id(cfg.fallback_action, s): cfg.fallback_action.rate_budget_mbps[s]
                                    for s in ("urllc", "embb", "mmtc")}}


def test_backend_refuses_flows_whose_meter_is_missing_on_that_switch(cfg):
    net, fabric, _ = _net(cfg)
    n = len(fabric.calls)
    rule = FlowRule("s2", 0x100, 100, "ip,nw_src=10.0.2.1,nw_dst=10.0.2.2", "meter:1,output:1")
    assert rule.meter == 1 and FlowRule("s2", 0x100, 100, "ip", "output:1").meter is None
    with pytest.raises(FabricError, match=r"s2 reference meters \[1\]"):
        net._add_flows("s2", [rule])  # meter 1 exists on s1 only
    assert len(fabric.calls) == n  # never sent to the switch


def test_fake_fabric_rejects_meter_misuse_like_ovs(cfg, plan):
    f = FakeFabric(FakeClock())
    f.setup(plan)
    with pytest.raises(FabricError, match="UNKNOWN_METER"):
        f.set_meter("s1", meter_spec(1, 5.0), new=False)
    f.set_meter("s1", meter_spec(1, 5.0), new=True)
    with pytest.raises(FabricError, match="METER_EXISTS"):
        f.set_meter("s1", meter_spec(1, 5.0), new=True)


# Failure 2: the failed constructor never closed its network (the test fixture had no
# reference to it), so every later setup hit "RTNETLINK answers: File exists".
@pytest.mark.parametrize("where", ["setup", "add_flows"])
def test_failed_construction_closes_the_fabric(cfg, where):
    fabric = FakeFabric(FakeClock(), fail_on=where)
    with pytest.raises(FabricError, match="injected"):
        MininetNetwork(cfg, _scenario(cfg), 1, fabric, clock=fabric.clock, sleep=fabric.clock.sleep)
    assert fabric.closed == 1


def test_a_failing_cleanup_does_not_hide_the_original_error(cfg):
    fabric = FakeFabric(FakeClock(), fail_on="add_flows")

    def broken_close():
        raise FabricError("close failed too")
    fabric.close = broken_close
    with pytest.raises(FabricError, match="injected") as exc:
        MininetNetwork(cfg, _scenario(cfg), 1, fabric, clock=fabric.clock, sleep=fabric.clock.sleep)
    assert any("close failed too" in n for n in exc.value.__notes__)


def test_plan_lists_the_switch_side_interfaces_mininet_creates(cfg, plan):
    names = plan.switch_interfaces()
    assert len(names) == len(set(names)) == 2 * len(plan.links) + 2 * len(plan.senders)
    assert "s5-eth7" in names  # bgdst's switch port: the interface that collided in the first run
    assert plan.receivers["bg"].switch == "s5" and plan.receivers["bg"].port == 7


def test_leak_check_matches_only_this_harness_processes(plan):
    ours = fabric_mod.is_emulation_process
    assert ours(["iperf3", "-s", "-p", "5201"], plan)  # what survived the first run
    assert ours(["iperf3", "-c", "10.0.2.2", "-u", "-b", "80.000M", "-l", "1400", "-t", "86400", "-p", "5202"], plan)
    assert ours(["ping", "-n", "-c", "8", "-i", "0.1", "-W", "1", "10.0.1.2"], plan)
    assert not ours(["/usr/bin/iperf3", "--server", "--interval", "0"], plan)  # the system iperf3 service
    assert not ours(["iperf3", "-s", "-p", "5300"], plan)
    assert not ours(["ping", "8.8.8.8"], plan) and not ours([], plan)


# ---------------------------------------------------------------- MininetFabric lifecycle without root
class _Proc:
    def __init__(self, alive=True, fail=False):
        self.alive, self.fail, self.pid, self.stopped = alive, fail, 4242, False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        if self.fail:
            raise OSError("terminate failed")
        self.alive, self.stopped = False, True

    def kill(self):
        self.alive = False

    def wait(self, timeout=None):
        return 0


class _Net:
    def __init__(self, fail_build=False, fail_stop=False, **kwargs):
        self.kwargs, self.fail_build, self.fail_stop, self.stopped = kwargs, fail_build, fail_stop, 0

    def build(self):
        if self.fail_build:
            raise Exception("Error creating interface pair (bgdst-eth0,s5-eth7): RTNETLINK answers: File exists")

    def start(self):
        pass

    def stop(self):
        self.stopped += 1
        if self.fail_stop:
            raise RuntimeError("stop failed")


@pytest.fixture
def bare_fabric(monkeypatch, plan):
    """A MininetFabric without the root check, with resource probing recorded, not run."""
    left, removed = [], []
    monkeypatch.setattr(fabric_mod, "leftover_resources", lambda p: list(left))
    monkeypatch.setattr(fabric_mod, "remove_resources", lambda names: (removed.extend(names), left.clear()))
    f = object.__new__(MininetFabric)
    f.net, f.plan = None, plan
    f._traffic, f._probes, f._servers = {}, {}, []
    f.stale_removed, f.forced_cleanup = [], []
    return f, left, removed


def test_close_runs_every_step_and_is_idempotent(bare_fabric):
    f, left, removed = bare_fabric
    bad, good, server = _Proc(fail=True), _Proc(), _Proc()
    net = _Net(fail_stop=True)
    f._traffic, f._servers, f.net = {"embb": (80.0, 1400, bad), "urllc": (2.0, 64, good)}, [server], net
    left.append("intf:s5-eth7")  # what a failed stop leaves behind
    with pytest.raises(FabricError, match="terminate failed.*mininet stop"):
        f.close()
    assert good.stopped and server.stopped and net.stopped == 1  # a failure did not skip later steps
    assert removed == ["intf:s5-eth7"] and f.forced_cleanup == ["intf:s5-eth7"]
    f.close()  # nothing left: a second close is a no-op
    assert net.stopped == 1


def test_setup_failure_stops_the_partial_network(bare_fabric, monkeypatch, plan):
    pytest.importorskip("mininet.net")
    f, left, removed = bare_fabric
    made = []
    monkeypatch.setattr("mininet.net.Mininet", lambda **kw: made.append(_Net(fail_build=True, **kw)) or made[-1])
    left.append("intf:s5-eth7")  # leaked by an earlier run
    with pytest.raises(Exception, match="File exists"):
        f.setup(plan)
    assert f.stale_removed == ["intf:s5-eth7"] and removed == ["intf:s5-eth7"]  # deleted before building
    assert made[0].kwargs["build"] is False and made[0].stopped == 1 and f.net is None


def test_snapshot_refuses_a_dead_traffic_generator(bare_fabric):
    f, _, _ = bare_fabric
    f._traffic = {"embb": (80.0, 1400, _Proc(alive=False))}
    with pytest.raises(FabricError, match=r"exited for \['embb'\]"):
        f.snapshot()


# ---------------------------------------------------------------- meter parsers (formats from OVS 3.3 ofp-print)
METER_FEATURES = """OFPST_METER_FEATURES reply (OF1.3) (xid=0x2):
max_meter:200000 max_bands:1 max_color:0
band_types: drop
capabilities: kbps pktps burst stats
"""

DUMP_METERS = """OFPST_METER_CONFIG reply (OF1.3) (xid=0x2):
meter=1 kbps burst bands=
type=drop rate=100000 burst_size=10000

meter=3 kbps burst bands=
type=drop rate=5000 burst_size=500
"""


def test_parse_meter_features_and_dump_meters():
    assert parse_meter_features(METER_FEATURES) == 200000
    assert parse_meter_features("max_meter:0 max_bands:0") == 0
    assert parse_meter_features("garbage") is None
    assert parse_dump_meters(DUMP_METERS) == {1: 100000, 3: 5000}
    assert parse_dump_meters("OFPST_METER_CONFIG reply (OF1.3) (xid=0x2):\n") == {}


@pytest.mark.skipif(shutil.which("ovs-ofctl") is None, reason="ovs-ofctl not installed")
def test_meter_parsers_read_what_ovs_prints():
    import struct

    def reply(mtype, body):
        payload = struct.pack("!HH4x", mtype, 0) + body
        return (struct.pack("!BBHI", 4, 19, 8 + len(payload), 2) + payload).hex()

    def meter(mid, kbps):
        band = struct.pack("!HHII4x", 1, 16, kbps, kbps // 10)
        return struct.pack("!HHI", 8 + len(band), 0b101, mid) + band

    def show(hexmsg):
        return subprocess.run(["ovs-ofctl", "ofp-print", hexmsg], capture_output=True, text=True, check=True).stdout

    assert parse_meter_features(show(reply(11, struct.pack("!IIIBB2x", 64, 2, 0xF, 1, 0)))) == 64
    assert parse_dump_meters(show(reply(10, meter(1, 100000) + meter(2, 5000)))) == {1: 100000, 2: 5000}



def test_snapshot_refreshes_rule_counters_before_reading_them(bare_fabric, monkeypatch):
    """Rule counters lag up to max-revalidator (500 ms) behind the datapath; a plain
    dump read rates at 0.5x / 1.5x (Mininet campaigns 2026-10-22)."""
    f, _, _ = bare_fabric
    calls = []

    def run(cmd, **kw):
        calls.append(cmd[:2] if cmd[0] == "ovs-appctl" else cmd[-2])
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(fabric_mod.subprocess, "run", run)
    f.snapshot()
    assert calls[0] == ["ovs-appctl", "revalidator/wait"]
    assert set(calls[1:]) == {"dump-ports", "dump-flows"}

    def failing(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, "", "unknown command")
    monkeypatch.setattr(fabric_mod.subprocess, "run", failing)
    with pytest.raises(FabricError, match="revalidator/wait"):
        f.snapshot()  # stale counters are not silently accepted
