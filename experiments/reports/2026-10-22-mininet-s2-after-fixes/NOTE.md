# Mininet s2 after the telemetry fixes - 2026-10-22 17:09 UTC

Copied from `experiments/results/mininet-20261022T170942Z/` (raw `steps.jsonl` and
logs stay local). Commit `074e46f`, clean tree. Integration suite 9/9 in both passes,
no leftovers. Then s2 × 5 controllers × seeds 1-3; all 15 trials are complete.

Emulated-network measurements, not ground truth and not real-network validation.

**Validated by this run** (compared with the provisional campaign `mininet-20261022T110546Z`):
* **Missing values:** 0 (before: 65; eMBB throughput is no longer `null`).
* **Background on l13 during the surge:** median 123.5 Mbit/s against 123.6
  expected (120 Mbit/s payload as frames). Before: 102.

**Still wrong in this run** (fixes or decisions pending):
* **Reservation-limit slots (18-20 for every controller) come from the meter.** The
  certified budgets fill l13 to exactly 0.900 of capacity, but the OVS meter
  delivers 1.10× the budget (median, 191 metered slots), so the link runs at
  0.928.
* **Rule counters were read stale** (up to 500 ms; OVS max-revalidator). Offered
  load read about 0.5×/1.5× in 47 slots, and background jumped (e.g. 151.7 at t=37
  in shielded seed 1). π₀(s) then rerouted eMBB onto path C or A, causing the
  shielded runs' violations (mMTC 32.7 ms, URLLC 27.6 ms) and their uncertified
  fallbacks. Fixed afterwards: the snapshot calls `ovs-appctl revalidator/wait`
  before reading counters. That fix is not yet run on Mininet.
* **Latency is the max of 8 pings**, and `overload_slots` is not observable here
  (shown as "–").
