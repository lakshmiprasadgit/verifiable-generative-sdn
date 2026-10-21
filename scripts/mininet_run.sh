#!/usr/bin/env bash
# Milestone 2 Mininet runs. Needs root:   sudo scripts/mininet_run.sh
# 1. integration tests (routes, meters, background accounting, probes, loop smoke)
# 2. a closed-loop campaign on the emulated network (about 40 minutes)
# Everything is written to experiments/results/mininet-<UTC time>/ and owned by the
# invoking user afterwards. No files outside the repository are changed except
# Mininet's own cleanup (mn -c) and starting the Open vSwitch service if stopped.
set -uo pipefail
cd "$(dirname "$0")/.."
if [ "$(id -u)" -ne 0 ]; then echo "run with sudo: sudo $0"; exit 1; fi
OWNER="${SUDO_USER:-root}"
OUT="experiments/results/mininet-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1   # no root-owned caches in the repository
{
  echo "== environment"; uname -r; mn --version; ovs-vsctl --version | head -1; iperf3 --version | head -1
  modprobe openvswitch && echo "openvswitch module loaded"
  systemctl is-active --quiet openvswitch-switch || systemctl start openvswitch-switch
  systemctl is-active openvswitch-switch
  mn -c >/dev/null 2>&1; echo "mininet cleaned"
} 2>&1 | tee "$OUT/environment.log"

echo "== integration tests" | tee "$OUT/integration.log"
.venv/bin/python -m pytest tests/integration -m mininet -v -p no:cacheprovider 2>&1 | tee -a "$OUT/integration.log"
IT=${PIPESTATUS[0]}
mn -c >/dev/null 2>&1

if [ "$IT" -eq 0 ]; then
  echo "== campaign" | tee "$OUT/campaign.log"
  .venv/bin/python -m vgcp.experiments --backend mininet \
      --scenarios experiments/scenarios/s1_steady.yaml experiments/scenarios/s2_background_on_embb_path.yaml \
                  experiments/scenarios/s3_background_on_urllc_path.yaml \
      --seeds 1-3 --out "$OUT/campaign" 2>&1 | tee -a "$OUT/campaign.log"
  mn -c >/dev/null 2>&1
else
  echo "integration tests failed (exit $IT): campaign skipped" | tee "$OUT/campaign.log"
fi
chown -R "$OWNER": "$OUT"
echo "results in $OUT"
