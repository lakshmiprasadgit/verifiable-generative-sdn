"""CLI (root): measure what an OVS meter actually lets through, to explain its overshoot.

  sudo scripts/meter_sweep.sh            (wraps: python -m vgcp.experiments.meter_sweep --out DIR)

The Mininet campaigns saw the meter deliver about 1.10x its budget at 50-70 Mbit/s
and 1.00x at 1 Mbit/s (DECISIONS 2026-10-22). This sweep fixes the meter rate and
the datagram size, offers 1.5x the budget, and measures the frames admitted past the
meter, so the cause can be told apart:
  * header or fragment accounting: the ratio depends on the datagram size;
  * a property of the meter itself: the ratio depends on the rate or the burst size;
  * the old eMBB setting (1500-byte payload) fragments into a 1514- and a 62-byte frame.

Only the eMBB slice is installed (path B, metered at the ingress); no background.
Writes sweep.json and sweep.md; changes no configuration.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

from vgcp.config import load_config
from vgcp.emu.fabric import MininetFabric
from vgcp.emu.openflow import SLICE_PRIORITY, path_rules
from vgcp.emu.plan import FRAME_OVERHEAD_BYTES, plan_emulation
from vgcp.emu.telemetry import _flow, flow_rate_mbps
from vgcp.experiments.__main__ import ROOT, _git

SLICE, PATH, METER, COOKIE = "embb", "B", 1, 0x100
IP_MTU = 1500
ETH, IP, UDP = 14, 20, 8


def frames_per_datagram(payload: int) -> list[int]:
    """Ethernet frame sizes (no FCS) one UDP datagram of this payload becomes, fragments included."""
    data = UDP + payload  # the IP payload
    per = (IP_MTU - IP) // 8 * 8  # data per fragment, a multiple of 8
    out = []
    while data > 0:
        chunk = data if data <= IP_MTU - IP else per
        out.append(ETH + IP + chunk)
        data -= chunk
    return out


def grid() -> list[dict]:
    """(budget, payload, burst) points: every size at low rates, large sizes up to 70 Mbit/s,
    and two burst sizes at 50 Mbit/s."""
    pts = []
    for payload in (22, 58, 1400, 1472, 1500):
        for budget in (1.0, 5.0, 20.0, 50.0, 70.0):
            if payload < 100 and budget > 20:
                continue  # 64-byte frames at > 30 Mbit/s exceed what iperf3 generates here
            pts.append({"budget_mbps": budget, "payload_bytes": payload, "burst_fraction": 0.1})
    pts.append({"budget_mbps": 50.0, "payload_bytes": 1472, "burst_fraction": 0.01})
    pts.append({"budget_mbps": 50.0, "payload_bytes": 1472, "burst_fraction": 1.0})
    return pts


def spec(budget_mbps: float, burst_fraction: float) -> str:
    """As openflow.meter_spec, with the burst (kbit) as a fraction of one second at the rate."""
    kbps = max(1, int(round(budget_mbps * 1000)))
    return f"meter={METER},kbps,burst,band=type=drop,rate={kbps},burst_size={max(1, int(kbps * burst_fraction))}"


def run(out: Path, warmup_s: float, window_s: float) -> dict:
    cfg = load_config(ROOT / "configs")
    plan = plan_emulation(cfg)
    nodes = cfg.topology.paths[PATH].nodes
    src, dst = plan.senders[SLICE].ip, plan.receivers[SLICE].ip
    fabric = MininetFabric()
    rows = []
    try:
        fabric.setup(plan)
        first = True
        for p in grid():
            fabric.set_meter(plan.ingress, spec(p["budget_mbps"], p["burst_fraction"]), new=first)
            if first:
                for sw in nodes:
                    fabric.add_flows(sw, [r for r in path_rules(plan, SLICE, nodes, COOKIE, SLICE_PRIORITY, METER)
                                          if r.switch == sw])
                first = False
            frames = frames_per_datagram(p["payload_bytes"])
            wire_per_payload = sum(frames) / p["payload_bytes"]
            offered_frames = 1.5 * p["budget_mbps"]
            fabric.set_traffic(SLICE, offered_frames / wire_per_payload, p["payload_bytes"])
            time.sleep(warmup_s)
            a = fabric.snapshot()
            time.sleep(window_s)
            b = fabric.snapshot()
            d = b.time_s - a.time_s

            def rate(sw):
                return flow_rate_mbps(_flow(b.flows[sw], COOKIE, src, dst), _flow(a.flows[sw], COOKIE, src, dst), d)

            def pps(sw):
                f1, f0 = _flow(b.flows[sw], COOKIE, src, dst), _flow(a.flows[sw], COOKIE, src, dst)
                return (f1.n_packets - f0.n_packets) / d if f1 and f0 else float("nan")

            offered, admitted, adm_pps = rate(nodes[0]), rate(nodes[1]), pps(nodes[1])
            b_ = p["budget_mbps"]
            rows.append({**p, "frames_per_datagram": frames, "offered_mbps": offered, "admitted_mbps": admitted,
                         "admitted_pps": adm_pps,
                         "ratio_frames": admitted / b_,
                         # what the meter would see if it counted without the Ethernet header
                         "ratio_ip": (admitted - adm_pps * ETH * 8 / 1e6) / b_,
                         "ratio_payload": admitted / wire_per_payload / b_,
                         "offered_enough": offered >= 1.2 * b_})
            print(f"budget {b_:5.1f}  payload {p['payload_bytes']:4d}  burst {p['burst_fraction']:<4}  "
                  f"offered {offered:7.2f}  admitted {admitted:7.2f}  ratio {admitted / b_:.3f}", flush=True)
    finally:
        fabric.close()
    result = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "git_commit": _git("rev-parse", "HEAD"),
              "warmup_s": warmup_s, "window_s": window_s, "frame_overhead_bytes": FRAME_OVERHEAD_BYTES, "rows": rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / "sweep.json").write_text(json.dumps(result, indent=2))
    (out / "sweep.md").write_text(report(result))
    return result


def report(result: dict) -> str:
    lines = ["# OVS meter sweep", "",
             f"Commit `{(result['git_commit'] or 'unknown')[:7]}`. eMBB alone on path B, meter at the ingress, "
             f"offered 1.5x the budget; admitted = frames counted past the meter over {result['window_s']} s. "
             "Emulated network, one machine.", "",
             "| budget Mbit/s | UDP payload B | frames per datagram | burst (s at rate) | offered | admitted | "
             "admitted / budget (frames) | (IP bytes) | (payload) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        flag = "" if r["offered_enough"] else " (offered too low)"
        lines.append(f"| {r['budget_mbps']:g} | {r['payload_bytes']} | {'+'.join(map(str, r['frames_per_datagram']))} | "
                     f"{r['burst_fraction']:g} | {r['offered_mbps']:.2f} | {r['admitted_mbps']:.2f} | "
                     f"{r['ratio_frames']:.3f}{flag} | {r['ratio_ip']:.3f} | {r['ratio_payload']:.3f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--warmup", type=float, default=2.0, help="seconds after a change before measuring")
    ap.add_argument("--window", type=float, default=4.0, help="measurement window in seconds")
    a = ap.parse_args(argv)
    run(a.out, a.warmup, a.window)


if __name__ == "__main__":
    main()
