# OVS meter and idle-latency diagnostics - 2026-10-26

From `experiments/results/meter-sweep-20261026T{132641,171710,171934}Z/`
(`sudo scripts/meter_sweep.sh [--part ...]`). Emulated network on one machine.

* `grid.md`: unmodified meters pass 0.997-1.000x their budget at 1-70 Mbit/s, 64-1514
  byte frames (and the old fragmenting payload) and 0.01-1 s bursts. Meters count
  Ethernet frames.
* `modify.md`: modified every slot, the meter passes about one burst extra per
  modification: 1.005x (0.01 s), 1.066x (0.1 s), 1.50x (1 s, capped by the offered
  1.5x). Unmodified controls: 0.998-1.000x.
* `latency.md`: idle path A, 100 pings per slot: slot p99 median 0.49 ms, max
  0.98 ms, with or without the per-slot counter reads.

Decision: docs/DECISIONS.md, 2026-10-26.
