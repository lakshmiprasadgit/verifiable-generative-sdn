#!/usr/bin/env bash
# Milestone 2 Mininet runs. Needs root.
#   sudo scripts/mininet_run.sh              integration tests only, twice (default)
#   sudo scripts/mininet_run.sh --campaign   the same, then the closed-loop campaign
#                                            (about 40 minutes), only if every pass is green
# The integration file runs PASSES times (default 2) without any cleanup in between,
# so a leaked interface, bridge or process from one pass fails the next.
# Everything is written to experiments/results/mininet-<UTC time>/ and owned by the
# invoking user afterwards. No files outside the repository are changed except
# Mininet's own cleanup (mn -c, once before the tests and after the campaign) and
# starting the Open vSwitch service if stopped.
set -uo pipefail
cd "$(dirname "$0")/.."
if [ "$(id -u)" -ne 0 ]; then echo "run with sudo: sudo $0 $*"; exit 1; fi
CAMPAIGN=0
for arg in "$@"; do
  case "$arg" in
    --campaign) CAMPAIGN=1 ;;
    *) echo "unknown argument: $arg (use --campaign or nothing)"; exit 2 ;;
  esac
done
PASSES="${PASSES:-2}"
OWNER="${SUDO_USER:-root}"
OUT="experiments/results/mininet-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1   # no root-owned caches in the repository
{
  echo "== environment"; uname -r; mn --version; ovs-vsctl --version | head -1; iperf3 --version | head -1
  echo "git $(git rev-parse --short HEAD) $(git status --porcelain -- src tests configs scripts | wc -l) changed files"
  modprobe openvswitch && echo "openvswitch module loaded"
  systemctl is-active --quiet openvswitch-switch || systemctl start openvswitch-switch
  systemctl is-active openvswitch-switch
  mn -c >/dev/null 2>&1; echo "mininet cleaned (before the first pass only)"
} 2>&1 | tee "$OUT/environment.log"

IT=0
for pass in $(seq 1 "$PASSES"); do
  echo "== integration tests, pass $pass of $PASSES" | tee "$OUT/integration-pass$pass.log"
  .venv/bin/python -m pytest tests/integration -m mininet -v -p no:cacheprovider 2>&1 | tee -a "$OUT/integration-pass$pass.log"
  rc=${PIPESTATUS[0]}
  echo "pass $pass exit $rc" | tee -a "$OUT/integration-summary.log"
  [ "$rc" -ne 0 ] && IT=$rc
done
echo "after the last pass: $(ip -o link show | grep -cE ' s[0-9]+-eth[0-9]+') switch interfaces, $(pgrep -fc '^iperf3 -[sc] ') harness iperf3 processes" \
  | tee -a "$OUT/integration-summary.log"

if [ "$IT" -ne 0 ]; then
  echo "integration tests failed (exit $IT): campaign not run" | tee "$OUT/campaign.log"
elif [ "$CAMPAIGN" -eq 1 ]; then
  echo "== campaign" | tee "$OUT/campaign.log"
  .venv/bin/python -m vgcp.experiments --backend mininet \
      --scenarios experiments/scenarios/s1_steady.yaml experiments/scenarios/s2_background_on_embb_path.yaml \
                  experiments/scenarios/s3_background_on_urllc_path.yaml \
      --seeds 1-3 --out "$OUT/campaign" 2>&1 | tee -a "$OUT/campaign.log"
  mn -c >/dev/null 2>&1
else
  echo "integration tests passed; campaign not requested (add --campaign)" | tee "$OUT/campaign.log"
fi
chown -R "$OWNER": "$OUT"
echo "results in $OUT"
exit "$IT"
