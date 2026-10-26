"""CLI (root): measure what an OVS meter actually lets through, to explain its overshoot.

  sudo scripts/meter_sweep.sh [--part grid|modify|latency|all]
                                         (wraps: python -m vgcp.experiments.meter_sweep --out DIR)

The Mininet campaigns saw the meter deliver about 1.10x its budget at 50-70 Mbit/s
and 1.00x at 1 Mbit/s (DECISIONS 2026-10-22). This sweep fixes the meter rate and
the datagram size, offers 1.5x the budget, and measures the frames admitted past the
meter, so the cause can be told apart:
  * header or fragment accounting: the ratio depends on the datagram size;
  * a property of the meter itself: the ratio depends on the rate or the burst size;
  * the old eMBB setting (1500-byte payload) fragments into a 1514- and a 62-byte frame.

Only the eMBB slice is installed (path B, metered at the ingress); no background.

The grid (2026-10-26) found the meter exact in steady state at every rate, size and
burst, while the campaign's metered slots, all of which modified the meter, ran
1.07x (up to 1.12x). Two further parts test the remaining explanations:
  * modify: the same meter, offered 1.5x, measured per 1 s slot, either modified
    every slot by +-0.1 % (as the controller does) or left alone; per burst size.
  * latency: 100 pings per slot on idle path A (URLLC route, no traffic), either
    alone or with the backend's per-slot counter reads (revalidator/wait and
    dumps); the campaign saw URLLC p99 up to 19 ms on this 0.2 ms path.

Writes sweep.json and sweep.md; changes no configuration.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import time
from pathlib import Path

from vgcp.config import load_config
from vgcp.emu.fabric import MininetFabric
from vgcp.emu.openflow import SLICE_PRIORITY, path_rules
from vgcp.emu.plan import FRAME_OVERHEAD_BYTES, plan_emulation
from vgcp.emu.telemetry import _flow, flow_rate_mbps
from vgcp.experiments.__main__ import ROOT, _git

SLICE, PATH, METER, COOKIE = "embb", "B", 1, 0x100
PROBE_SLICE, PROBE_PATH, PROBE_METER, PROBE_COOKIE = "urllc", "A", 2, 0x200
SLOT_S, SLOTS = 1.0, 6
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


def modify_points() -> list[dict]:
    return [{"budget_mbps": b, "payload_bytes": 1472, "burst_fraction": f, "modify": m}
            for b in (20.0, 50.0) for f in (0.01, 0.1, 1.0) for m in (False, True)]


def percentile(values: list[float], q: float) -> float:
    """Nearest rank, as the backend computes a slot's p99."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def run(out: Path, warmup_s: float, window_s: float, part: str = "all") -> dict:
    cfg = load_config(ROOT / "configs")
    plan = plan_emulation(cfg)
    nodes = cfg.topology.paths[PATH].nodes
    src, dst = plan.senders[SLICE].ip, plan.receivers[SLICE].ip
    fabric = MininetFabric()
    rows, mod_rows, lat_rows = [], [], []
    try:
        fabric.setup(plan)
        fabric.set_meter(plan.ingress, spec(1.0, 0.1), new=True)
        for sw in nodes:
            fabric.add_flows(sw, [r for r in path_rules(plan, SLICE, nodes, COOKIE, SLICE_PRIORITY, METER)
                                  if r.switch == sw])
        for p in grid() if part in ("grid", "all") else []:
            fabric.set_meter(plan.ingress, spec(p["budget_mbps"], p["burst_fraction"]), new=False)
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

        for p in modify_points() if part in ("modify", "all") else []:
            b_ = p["budget_mbps"]
            fabric.set_meter(plan.ingress, spec(b_, p["burst_fraction"]), new=False)
            fabric.set_traffic(SLICE, 1.5 * b_ * 1472 / 1514, 1472)
            time.sleep(warmup_s)
            ratios = []
            prev = fabric.snapshot()
            for k in range(SLOTS):
                if p["modify"]:  # what the controller does when a budget moves slightly
                    fabric.set_meter(plan.ingress, spec(b_ * (1.001 if k % 2 == 0 else 0.999), p["burst_fraction"]), new=False)
                time.sleep(SLOT_S)
                cur = fabric.snapshot()
                d = cur.time_s - prev.time_s
                ratios.append(flow_rate_mbps(_flow(cur.flows[nodes[1]], COOKIE, src, dst),
                                             _flow(prev.flows[nodes[1]], COOKIE, src, dst), d) / b_)
                prev = cur
            fabric.set_meter(plan.ingress, spec(b_, p["burst_fraction"]), new=False)  # back to the exact budget
            mod_rows.append({**p, "ratios": ratios, "mean": sum(ratios) / len(ratios), "max": max(ratios)})
            print(f"budget {b_:5.1f}  burst {p['burst_fraction']:<4}  modified every slot {str(p['modify']):5}  "
                  f"admitted/budget mean {mod_rows[-1]['mean']:.3f} max {mod_rows[-1]['max']:.3f}", flush=True)

        if part in ("latency", "all"):
            fabric.set_traffic(SLICE, 0.0, 1472)
            pnodes = cfg.topology.paths[PROBE_PATH].nodes
            for sw in pnodes:
                fabric.add_flows(sw, [r for r in path_rules(plan, PROBE_SLICE, pnodes, PROBE_COOKIE, SLICE_PRIORITY, None)
                                      if r.switch == sw])
            for with_reads in (False, True):
                p99s = []
                for _ in range(20):
                    fabric.start_probes([PROBE_SLICE], 100, 0.9 * SLOT_S / 100)
                    time.sleep(SLOT_S)
                    if with_reads:
                        rtts = fabric.snapshot().rtts_ms.get(PROBE_SLICE, [])
                    else:
                        rtts = fabric._collect_probes().get(PROBE_SLICE, [])
                    p99s.append(percentile(rtts, 0.99) / 2)
                lat_rows.append({"counter_reads": with_reads, "slot_p99_ms": p99s,
                                 "median": percentile(p99s, 0.5), "max": max(p99s),
                                 "slots_over_1ms": sum(1 for v in p99s if v > 1.0)})
                print(f"idle path A, counter reads {str(with_reads):5}: slot p99 median {lat_rows[-1]['median']:.3f} ms, "
                      f"max {lat_rows[-1]['max']:.3f} ms, {lat_rows[-1]['slots_over_1ms']} of 20 slots over 1 ms", flush=True)
    finally:
        fabric.close()
    result = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "git_commit": _git("rev-parse", "HEAD"),
              "warmup_s": warmup_s, "window_s": window_s, "frame_overhead_bytes": FRAME_OVERHEAD_BYTES, "rows": rows,
              "modify_rows": mod_rows, "latency_rows": lat_rows}
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
    if result.get("modify_rows"):
        lines += ["", "## Meter modified every slot vs left alone", "",
                  "Offered 1.5x the budget, 1472-byte payload; admitted / budget per 1 s slot.", "",
                  "| budget Mbit/s | burst (s at rate) | modified every slot | mean | max | per slot |", "|---|---|---|---|---|---|"]
        for r in result["modify_rows"]:
            lines.append(f"| {r['budget_mbps']:g} | {r['burst_fraction']:g} | {'yes' if r['modify'] else 'no'} | "
                         f"{r['mean']:.3f} | {r['max']:.3f} | {' '.join(f'{v:.3f}' for v in r['ratios'])} |")
    if result.get("latency_rows"):
        lines += ["", "## Idle-path latency (path A, no traffic, 100 pings per slot)", "",
                  "| counter reads each slot | median slot p99 ms | max slot p99 ms | slots over 1 ms (of 20) |", "|---|---|---|---|"]
        for r in result["latency_rows"]:
            lines.append(f"| {'yes' if r['counter_reads'] else 'no'} | {r['median']:.3f} | {r['max']:.3f} | {r['slots_over_1ms']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--warmup", type=float, default=2.0, help="seconds after a change before measuring")
    ap.add_argument("--window", type=float, default=4.0, help="measurement window in seconds")
    ap.add_argument("--part", choices=["grid", "modify", "latency", "all"], default="all")
    a = ap.parse_args(argv)
    run(a.out, a.warmup, a.window, a.part)


if __name__ == "__main__":
    main()
