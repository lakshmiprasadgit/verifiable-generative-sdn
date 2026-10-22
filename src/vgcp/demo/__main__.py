"""python -m vgcp.demo [--host 127.0.0.1] [--port 8765] [--config configs]"""

from __future__ import annotations

import argparse
from pathlib import Path

from vgcp.demo.server import ROOT, serve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m vgcp.demo", description="VGCP control-loop dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--config", default=str(ROOT / "configs"))
    args = ap.parse_args(argv)
    serve(args.host, args.port, Path(args.config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
