# Mininet s1-s3, 5 seeds - 2026-10-26 13:41 UTC

Copied from `experiments/results/mininet-20261026T134135Z/` (raw `steps.jsonl` and logs
stay local). Commit `88d5a84` (frame-rate units, p99 of 100 probes), clean tree.
Integration 11/11 in both passes, no leftovers. Then s1-s3 × 5 controllers × seeds 1-5.

Emulated-network measurements, not ground truth and not real-network validation.

* s2 still had about 20 reservation-limit slots per trial in every mode: the meter's
  0.1 s burst, refilled on every modification (found afterwards, see
  `2026-10-26-meter-sweep`; fixed in `2026-10-26-mininet-s2-meter-fix`).
* URLLC p99 above 1 ms in 43 slots of s1 and 124 of s3, up to 18.8 ms on path A
  (0.2 ms propagation), in every controller and clustered by run. Not queueing; not
  the counter reads (idle-path test). Cause open, so latency violations on lightly
  loaded paths here are not attributable to the controller.
* The latency-factor fit on seeds 1-3 (k = 2.272) covered 98.5 % of held-out slots on
  seeds 4-5, below the 99 % rule: k stays 1.5 (`calibration.md`).
