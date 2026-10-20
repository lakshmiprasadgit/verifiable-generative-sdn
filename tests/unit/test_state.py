"""State s_t / demand d_t schemas: validation, missing and stale telemetry, vector form."""

import math

import pytest

from factories import NOW, nominal_state
from vgcp.state import Demand, Measurement, MetricStatus, NetworkState


def test_schema_has_expected_keys(cfg):
    keys = cfg.state_schema.keys
    assert "link_utilization.l12" in keys
    assert "latency_p99_ms.urllc" in keys
    assert "flow_table_occupancy.s6" in keys
    assert "energy_w" in keys
    # 7 links + 6 per-slice families x 3 slices + 6 switches + energy
    assert len(keys) == 7 + 6 * 3 + 6 + 1


def test_nominal_state_all_ok(cfg):
    statuses = cfg.state_schema.check(nominal_state(cfg), now_s=NOW, max_age_s=2.0)
    assert set(statuses.values()) == {MetricStatus.OK}


@pytest.mark.parametrize(
    "measurement, expected",
    [
        (None, MetricStatus.MISSING),
        (Measurement(None, NOW), MetricStatus.MISSING),
        (Measurement("0.5", NOW), MetricStatus.NOT_NUMERIC),
        (Measurement(True, NOW), MetricStatus.NOT_NUMERIC),
        (Measurement(math.nan, NOW), MetricStatus.NON_FINITE),
        (Measurement(math.inf, NOW), MetricStatus.NON_FINITE),
        (Measurement(-0.1, NOW), MetricStatus.OUT_OF_BOUNDS),
        (Measurement(10001.0, NOW), MetricStatus.OUT_OF_BOUNDS),
        (Measurement(0.5, None), MetricStatus.NO_TIMESTAMP),
        (Measurement(0.5, NOW + 0.001), MetricStatus.FUTURE_TIMESTAMP),
        (Measurement(0.5, NOW - 2.001), MetricStatus.STALE),
        # boundaries: exactly at the bound / exactly max age are accepted
        (Measurement(0.0, NOW), MetricStatus.OK),
        (Measurement(10000.0, NOW), MetricStatus.OK),
        (Measurement(0.5, NOW - 2.0), MetricStatus.OK),
    ],
)
def test_metric_status(cfg, measurement, expected):
    base = nominal_state(cfg)
    metrics = dict(base.metrics)
    key = "latency_p99_ms.urllc"
    if measurement is None:
        del metrics[key]
    else:
        metrics[key] = measurement
    statuses = cfg.state_schema.check(NetworkState(0, metrics), [key], now_s=NOW, max_age_s=2.0)
    assert statuses[key] is expected


# Audit finding C1: a timestamp must be finite before any freshness comparison.
@pytest.mark.parametrize(
    "timestamp, expected",
    [
        (math.nan, "invalid_timestamp"),
        (math.inf, "invalid_timestamp"),
        (-math.inf, "invalid_timestamp"),
        (NOW - 1.0, "ok"),
        (NOW - 2.5, "stale"),
        (NOW + 0.5, "future_timestamp"),
    ],
    ids=["nan", "+inf", "-inf", "valid", "stale", "future"],
)
def test_timestamp_validation(cfg, timestamp, expected):
    key = "latency_p99_ms.urllc"
    metrics = dict(nominal_state(cfg).metrics)
    metrics[key] = Measurement(0.5, timestamp)
    statuses = cfg.state_schema.check(NetworkState(0, metrics), [key], now_s=NOW, max_age_s=2.0)
    assert statuses[key] is MetricStatus(expected)


@pytest.mark.parametrize("timestamp", [math.nan, math.inf, -math.inf], ids=["nan", "+inf", "-inf"])
def test_non_finite_timestamp_rejected_without_max_age(cfg, timestamp):
    # With no staleness limit there is no age comparison to fail, so NaN and -inf
    # previously fell through to OK.
    key = "latency_p99_ms.urllc"
    s = NetworkState(0, {key: Measurement(0.5, timestamp)})
    assert cfg.state_schema.check(s, [key], now_s=NOW)[key] is MetricStatus("invalid_timestamp")


def test_unknown_key_reported(cfg):
    metrics = dict(nominal_state(cfg).metrics)
    metrics["latency_p99_ms.urlc"] = Measurement(0.5, NOW)  # typo
    statuses = cfg.state_schema.check(NetworkState(0, metrics), now_s=NOW, max_age_s=2.0)
    assert statuses["latency_p99_ms.urlc"] is MetricStatus.UNKNOWN_KEY


def test_without_now_freshness_is_not_checked(cfg):
    s = NetworkState.from_values(0, {"latency_p99_ms.urllc": 0.5}, timestamp_s=None)
    assert cfg.state_schema.check(s, ["latency_p99_ms.urllc"])["latency_p99_ms.urllc"] is MetricStatus.OK


def test_value_returns_nan_for_missing(cfg):
    s = NetworkState.from_values(0, {"energy_w": None})
    assert math.isnan(s.value("energy_w"))
    assert math.isnan(s.value("not_there"))


def test_vector_roundtrip_with_missing(cfg):
    s = nominal_state(cfg)
    metrics = dict(s.metrics)
    metrics["jitter_ms.embb"] = Measurement(None, NOW)
    s = NetworkState(0, metrics)
    vec = cfg.state_schema.to_vector(s)
    assert len(vec) == len(cfg.state_schema.keys)
    assert math.isnan(vec[cfg.state_schema.keys.index("jitter_ms.embb")])
    back = cfg.state_schema.from_vector(vec, t=0, timestamp_s=NOW)
    assert cfg.state_schema.to_vector(back)[:5] == vec[:5]
    assert back.metrics["jitter_ms.embb"].value is None
    with pytest.raises(ValueError):
        cfg.state_schema.from_vector(vec[:-1], t=0)


def test_demand_schema(cfg):
    assert set(cfg.demand_schema.keys) == {
        f"{f}.{s}" for f in ("offered_load_mbps", "active_devices") for s in ("urllc", "embb", "mmtc")
    }
    d = cfg.demand_schema.from_vector([1, 2, 3, 4, 5, 6], t=0, cls=Demand)
    assert isinstance(d, Demand)
