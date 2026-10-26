"""The meter sweep's pure parts (the sweep itself needs root and Mininet)."""

from vgcp.experiments.meter_sweep import frames_per_datagram, grid, report, spec


def test_frames_per_datagram_counts_headers_and_fragments():
    assert frames_per_datagram(1472) == [1514]  # the new eMBB size: one full frame
    assert frames_per_datagram(1500) == [1514, 62]  # the old one: a second, 28-byte fragment
    assert frames_per_datagram(22) == [64]


def test_grid_keeps_small_frames_at_rates_iperf3_can_generate():
    pts = grid()
    assert all(p["budget_mbps"] <= 20 for p in pts if p["payload_bytes"] < 100)
    assert {p["burst_fraction"] for p in pts} == {0.01, 0.1, 1.0}


def test_spec_matches_the_backend_meter_at_the_default_burst():
    from vgcp.emu.openflow import meter_spec
    assert spec(50.0, 0.1) == meter_spec(1, 50.0)


def test_report_marks_points_where_the_offered_load_did_not_exceed_the_budget():
    row = {"budget_mbps": 50.0, "payload_bytes": 1472, "burst_fraction": 0.1, "frames_per_datagram": [1514],
           "offered_mbps": 55.0, "admitted_mbps": 54.9, "admitted_pps": 4500.0, "ratio_frames": 1.098,
           "ratio_ip": 1.088, "ratio_payload": 1.067, "offered_enough": False}
    text = report({"git_commit": "abcdef1234", "window_s": 4.0, "rows": [row]})
    assert "| 50 | 1472 | 1514 | 0.1 | 55.00 | 54.90 | 1.098 (offered too low) |" in text
