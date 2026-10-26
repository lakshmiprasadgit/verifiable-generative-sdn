#!/usr/bin/env bash
# OVS meter diagnostic (DECISIONS 2026-10-26). Needs root; about 3 minutes.
#   sudo scripts/meter_sweep.sh
# Builds the emulated network once, sweeps fixed meter rates x datagram sizes with
# only eMBB installed, and writes experiments/results/meter-sweep-<UTC time>/
# (sweep.json, sweep.md, sweep.log), owned by the invoking user afterwards. Changes
# no configuration; runs Mininet's own cleanup (mn -c) before and after.
set -uo pipefail
cd "$(dirname "$0")/.."
if [ "$(id -u)" -ne 0 ]; then echo "run with sudo: sudo $0 $*"; exit 1; fi
OWNER="${SUDO_USER:-root}"
OUT="experiments/results/meter-sweep-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1
modprobe openvswitch
systemctl is-active --quiet openvswitch-switch || systemctl start openvswitch-switch
mn -c >/dev/null 2>&1
.venv/bin/python -m vgcp.experiments.meter_sweep --out "$OUT" 2>&1 | grep -v 'sch_htb: quantum' | tee "$OUT/sweep.log"
rc=${PIPESTATUS[0]}
mn -c >/dev/null 2>&1
chown -R "$OWNER": "$OUT"
echo "results in $OUT (exit $rc)"
exit "$rc"
