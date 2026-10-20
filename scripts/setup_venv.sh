#!/usr/bin/env bash
# Create .venv from the system Python 3.12, which can import the apt-installed Mininet.
# Needs no sudo. python3.12-venv (ensurepip) is not installed on this machine, so the
# venv is created without pip and packages are installed with an external pip via --python.
set -euo pipefail
cd "$(dirname "$0")/.."

SYS_PY=/usr/bin/python3
if [ ! -x .venv/bin/python ]; then
    "$SYS_PY" -m venv --without-pip --system-site-packages .venv
fi

if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m pip install "pytest==8.3.4" "hypothesis==6.122.3"
else
    PIP_PY=$(command -v python3)
    if [ "$PIP_PY" = "$SYS_PY" ] || ! "$PIP_PY" -m pip --version >/dev/null 2>&1; then
        echo "No pip available. Install python3.12-venv (needs sudo) or a user-level python with pip." >&2
        exit 1
    fi
    "$PIP_PY" -m pip --python .venv/bin/python install "pytest==8.3.4" "hypothesis==6.122.3"
fi
.venv/bin/python -c "import sys, yaml, pytest, hypothesis; print('python', sys.version.split()[0], 'pyyaml', yaml.__version__, 'pytest', pytest.__version__, 'hypothesis', hypothesis.__version__)"
