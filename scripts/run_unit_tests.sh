#!/usr/bin/env bash
# Unit tests only: no Mininet, no root.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m pytest tests/unit "$@"
