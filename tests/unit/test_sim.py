"""Simulated ground-truth network and scenario loading."""

import math

import pytest

from factories import action_with
from vgcp.errors import ConfigError
from vgcp.loop import ControllerFailure
from vgcp.sim import SimulatedNetwork, parse_scenario
from vgcp.state import MetricStatus

BASE = {
    "name": "t", "slots": 10,
    "demand_mbps": {"urllc": 2.0, "embb": 80.0, "mmtc": 2.0},
    "devices": {"urllc": 10, "embb": 5, "mmtc": 200},
    "ground_truth": {"packet_size_bytes": {"urllc": 64, "embb": 1514, "mmtc": 100},
                     "processing_delay_ms_per_hop": 0.05, "latency_noise": 0.0,
                     "measurement_noise": 0.0, "buffer_ms": 50.0},
}


def scenario(cfg, **extra):
    return parse_scenario({**BASE, **extra}, {s.name for s in cfg.slices}, set(cfg.topology.links))


def test_same_seed_same_trajectory(cfg):
    sc = scenario(cfg, demand_noise=0.1)
    a, b = SimulatedNetwork(cfg, sc, 3), SimulatedNetwork(cfg, sc, 3)
    for _ in range(5):
        a.advance(); b.advance()
    assert a.ground_truth() == b.ground_truth()
    c = SimulatedNetwork(cfg, sc, 4)
    for _ in range(5):
        c.advance()
    assert c.ground_truth()["offered_mbps"] != a.ground_truth()["offered_mbps"]


def test_measured_background_equals_true_background_without_overload(cfg):
    sc = scenario(cfg, background=[{"start": 0, "end": 10, "links": ["l13", "l35"], "mbps": 50.0}])
    net = SimulatedNetwork(cfg, sc, 1)
    obs = net.observe()
    assert obs.state.value("background_load_mbps.l13") == pytest.approx(50.0)
    assert obs.state.value("background_load_mbps.l12") == pytest.approx(0.0)
    assert net.ground_truth()["link_util"]["l13"] == pytest.approx((80.0 + 50.0) / 200)


def test_overload_drops_traffic_and_background_is_under_measured(cfg):
    # eMBB 80 + background 160 on path B (200 Mbit/s): 20 % of the offered load is dropped.
    sc = scenario(cfg, background=[{"start": 0, "end": 10, "links": ["l13", "l35"], "mbps": 160.0}])
    net = SimulatedNetwork(cfg, sc, 1)
    truth = net.ground_truth()
    assert truth["link_util"]["l13"] == pytest.approx(1.2)
    assert truth["loss"]["embb"] == pytest.approx(1 - (200 / 240) ** 2)  # dropped on both hops
    assert truth["latency_p99_ms"]["embb"] == pytest.approx(2 * (5.0 + 0.05 + 50.0))  # full buffers
    # Counters see delivered traffic only: background measured as 160 * 200/240 < 160.
    assert net.observe().state.value("background_load_mbps.l13") == pytest.approx(160 * 200 / 240)


def test_powered_off_route_blackholes_the_slice(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg), 1)
    net.apply(action_with(cfg, link_power={"l46": False}))  # mMTC routes over C
    net.advance()
    truth = net.ground_truth()
    assert truth["loss"]["mmtc"] == 1.0 and math.isinf(truth["latency_p99_ms"]["mmtc"])


def test_stale_telemetry_repeats_old_values_with_old_timestamps(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg, stale_telemetry=[{"start": 2, "end": 6}]), 1)
    net.advance()
    fresh = net.observe()  # slot 1
    for _ in range(4):
        net.advance()
    obs = net.observe()  # slot 5, frozen since slot 1
    assert obs.now_s == 5.0
    assert obs.state.metrics["latency_p99_ms.urllc"].timestamp_s == fresh.state.metrics["latency_p99_ms.urllc"].timestamp_s == 1.0
    statuses = cfg.state_schema.check(obs.state, ["latency_p99_ms.urllc"], now_s=obs.now_s, max_age_s=2.0)
    assert statuses["latency_p99_ms.urllc"] is MetricStatus.STALE


def test_missing_telemetry_is_reported_as_missing(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg, missing_telemetry=[{"start": 0, "end": 3, "prefixes": ["background_load_mbps."]}]), 1)
    obs = net.observe()
    assert obs.state.metrics["background_load_mbps.l13"].value is None
    assert obs.state.metrics["latency_p99_ms.urllc"].value is not None


def test_measurement_delay_ages_the_observation(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg, measurement_delay_slots=3), 1)
    for _ in range(5):
        net.advance()
    obs = net.observe()
    assert obs.now_s == 5.0 and obs.state.metrics["energy_w"].timestamp_s == 2.0


def test_controller_failure_keeps_the_installed_action(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg, controller_failures=[{"start": 0, "end": 2}]), 1)
    with pytest.raises(ControllerFailure):
        net.apply(action_with(cfg, path={"embb": "C"}))
    net.advance()
    assert net.ground_truth()["installed"]["path"]["embb"] == "B"


def test_actuation_delay(cfg):
    net = SimulatedNetwork(cfg, scenario(cfg, actuation_delay_slots=1), 1)
    net.apply(action_with(cfg, path={"embb": "C"}, rate_budget_mbps={"embb": 30.0}))
    net.advance()
    assert net.ground_truth()["installed"]["path"]["embb"] == "B"  # not yet
    net.advance()
    assert net.ground_truth()["installed"]["path"]["embb"] == "C"


@pytest.mark.parametrize("extra, fragment", [
    ({"slots": 0}, "slots"),
    ({"bogus": 1}, "unknown keys"),
    ({"background": [{"start": 5, "end": 3, "links": ["l13"], "mbps": 1}]}, "start < end"),
    ({"background": [{"start": 0, "end": 3, "links": ["l99"], "mbps": 1}]}, "unknown links"),
    ({"stale_telemetry": [{"start": 0, "end": 3, "links": ["l13"]}]}, "unknown keys"),
    ({"demand_events": [{"start": 0, "end": 3, "slice": "video", "factor": 2}]}, "unknown slice"),
    ({"demand_mbps": {"urllc": 1}}, "exactly"),
])
def test_scenario_validation(cfg, extra, fragment):
    with pytest.raises(ConfigError) as exc:
        scenario(cfg, **extra)
    assert fragment in str(exc.value)
