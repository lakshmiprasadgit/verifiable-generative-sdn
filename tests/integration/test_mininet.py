"""Mininet / Open vSwitch integration tests. Need root: run via scripts/mininet_run.sh.

Without root (or without Mininet, OVS or iperf3) every test is skipped, never passed.
Tolerances are deliberately loose: these tests check that the emulation does what
the telemetry and constraints assume (routes, policing, background accounting,
probe latency), not precise performance.

Every test ends with a leak check: none of the plan's switch interfaces or bridges may
remain, and Mininet's own stop() must have removed them (no forced cleanup). The
first privileged run failed because a failed setup leaked its network into every
later test; scripts/mininet_run.sh runs this file twice to catch leaks across runs.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))  # factories, test_sim fixtures

from factories import CONFIG_DIR, action_with  # noqa: E402
from vgcp.config import load_config  # noqa: E402
from vgcp.sim import parse_scenario  # noqa: E402


def _why_not() -> str | None:
    if os.geteuid() != 0:
        return "needs root (sudo scripts/mininet_run.sh)"
    try:
        import mininet.net  # noqa: F401
    except ImportError:
        return "Mininet not importable"
    if not Path("/var/run/openvswitch/db.sock").exists():
        return "Open vSwitch is not running"
    for tool in ("ovs-ofctl", "iperf3", "ping"):
        if shutil.which(tool) is None:
            return f"{tool} not found"
    return None


pytestmark = [pytest.mark.mininet, pytest.mark.skipif(_why_not() is not None, reason=_why_not() or "")]

BASE = {
    "name": "it", "slots": 20,
    "demand_mbps": {"urllc": 2.0, "embb": 80.0, "mmtc": 2.0},
    "devices": {"urllc": 10, "embb": 5, "mmtc": 200},
    "ground_truth": {"packet_size_bytes": {"urllc": 64, "embb": 1400, "mmtc": 100},
                     "processing_delay_ms_per_hop": 0.05, "latency_noise": 0.0,
                     "measurement_noise": 0.0, "buffer_ms": 50.0},
}


@pytest.fixture(scope="module")
def cfg():
    return load_config(CONFIG_DIR)


@pytest.fixture
def plan(cfg):
    from vgcp.emu import plan_emulation
    return plan_emulation(cfg)


def _assert_no_leftovers(plan, fabrics):
    from vgcp.emu.fabric import leftover_resources
    assert leftover_resources(plan) == [], "network resources leaked"
    assert [f.forced_cleanup for f in fabrics if f.forced_cleanup] == [], "Mininet stop() left resources behind"


@pytest.fixture
def make_net(cfg, plan):
    from vgcp.emu import MininetFabric, MininetNetwork
    made, fabrics = [], []

    def make(fabric=None, **extra):
        sc = parse_scenario({**BASE, **extra}, {s.name for s in cfg.slices}, set(cfg.topology.links))
        fabric = fabric or MininetFabric()
        fabrics.append(fabric)  # registered before construction: a failed setup is checked too
        net = MininetNetwork(cfg, sc, 1, fabric)
        made.append(net)
        return net

    yield make
    errors = []
    for net in made:
        try:
            net.close()
        except Exception as e:  # close every network, then report
            errors.append(e)
    assert not errors, errors
    _assert_no_leftovers(plan, fabrics)


def _settle(net, slots=2):
    for _ in range(slots):
        net.advance()
    return net.observe()


def test_every_slice_reaches_its_receiver(make_net, cfg):
    obs = _settle(make_net())
    for s in ("urllc", "embb", "mmtc"):
        lat = obs.state.value(f"latency_p99_ms.{s}")
        assert lat == lat and lat > 0, f"{s}: no probe replies"


def test_routes_follow_the_installed_path(make_net, cfg):
    net = make_net()
    _settle(net)
    m = net.ground_truth()
    # pi_0: eMBB on B (l13, l35), not on A or C
    assert m["link_util"]["l13"] > 0.2 and m["link_util"]["l12"] < 0.1


def test_meter_polices_the_budget(make_net, cfg):
    net = make_net()
    net.apply(action_with(cfg, rate_budget_mbps={"embb": 20.0}))
    obs = _settle(net, 3)
    assert obs.state.value("throughput_mbps.embb") == pytest.approx(20.0, rel=0.2)
    assert obs.demand.value("offered_load_mbps.embb") == pytest.approx(80.0, rel=0.2)  # counted before the meter


def test_background_is_measured_and_slices_excluded(make_net, cfg):
    net = make_net(background=[{"start": 0, "end": 20, "links": ["l13", "l35"], "mbps": 50.0}])
    obs = _settle(net, 3)
    assert obs.state.value("background_load_mbps.l13") == pytest.approx(50.0, rel=0.15)
    assert obs.state.value("background_load_mbps.l12") < 2.0


def test_probe_latency_matches_link_delays(make_net, cfg):
    obs = _settle(make_net())
    # path B: 2 x 5 ms one way; probes add queueing and host overhead, never less
    assert 10.0 <= obs.state.value("latency_p99_ms.embb") <= 15.0
    assert obs.state.value("latency_p99_ms.urllc") < 2.0  # path A: 2 x 0.1 ms


def test_reroute_takes_effect_within_one_slot(make_net, cfg):
    net = make_net()
    _settle(net)
    net.apply(action_with(cfg, path={"embb": "C"}, rate_budget_mbps={"embb": 30.0}))
    net.advance()
    m = net.ground_truth()
    assert m["installed"]["path"]["embb"] == "C"
    assert m["link_util"]["l14"] > 0.4 and m["link_util"]["l13"] < 0.1


def test_shielded_closed_loop_smoke(cfg, plan):
    from vgcp.emu import MininetFabric, MininetNetwork
    from vgcp.experiments.runner import run_trial, summarize
    sc = parse_scenario({**BASE, "slots": 8}, {s.name for s in cfg.slices}, set(cfg.topology.links))
    fabric = MininetFabric()
    rows = run_trial(cfg, sc, "shielded", 1, n_random=2,
                     make_backend=lambda c, s, seed: MininetNetwork(c, s, seed, fabric))
    _assert_no_leftovers(plan, [fabric])  # run_trial closed the backend
    summary = summarize(cfg, sc, rows)
    assert summary["apply_failures"] == 0
    assert all(r["truth_next"]["source"] == "measured" for r in rows)


def test_meters_exist_on_the_ingress_only(make_net, cfg, plan):
    from vgcp.emu.openflow import meter_id
    net = make_net()
    a = cfg.fallback_action
    assert net.fabric.meters(plan.ingress) == {meter_id(a, s): round(a.rate_budget_mbps[s] * 1000) for s in a.path}
    assert all(net.fabric.meters(sw) == {} for sw in plan.switches if sw != plan.ingress)


def test_failed_setup_leaves_nothing_behind(make_net, cfg, plan):
    from vgcp.emu import FabricError, MininetFabric
    from vgcp.emu.fabric import leftover_resources

    class FailsInstalling(MininetFabric):
        def add_flows(self, switch, rules):
            raise FabricError("injected after the topology was built")

    with pytest.raises(FabricError, match="injected"):
        make_net(fabric=FailsInstalling())
    assert leftover_resources(plan) == []
    obs = _settle(make_net(), 1)  # the same names can be built again straight away
    assert obs.state.value("throughput_mbps.embb") > 0
