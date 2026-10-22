#!/usr/bin/env bash
# Start the control-loop dashboard (simulation mode needs no root):
#   scripts/run_dashboard.sh            -> http://127.0.0.1:8765/
#   scripts/run_dashboard.sh --port 9000
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1
exec .venv/bin/python -m vgcp.demo "$@"
