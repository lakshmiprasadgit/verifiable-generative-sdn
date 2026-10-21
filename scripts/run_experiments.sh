#!/usr/bin/env bash
# Closed-loop experiments on the simulated backend (no root needed).
# Example: scripts/run_experiments.sh --scenarios experiments/scenarios/s*.yaml --seeds 1-5
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src exec .venv/bin/python -m vgcp.experiments "$@"
