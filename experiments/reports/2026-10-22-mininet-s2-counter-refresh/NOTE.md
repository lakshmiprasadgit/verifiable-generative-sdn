# Mininet s2 with current rule counters - 2026-10-22 17:47 UTC

Copied from `experiments/results/mininet-20261022T174731Z/` (raw `steps.jsonl` and
logs stay local). Commit `dde4fe4`, clean tree. Integration suite 10/10 in both
passes (including the new steady-counter test), no leftovers. Then s2 × 5
controllers × seeds 1-3; all 15 trials are complete.

Emulated-network measurements, not ground truth and not real-network validation.

Compared with the previous two runs (provisional 11:05 → fixes 17:09 → this run):

| | provisional | fixes | counter refresh |
|---|---|---|---|
| missing values | 65 | 0 | 0 |
| eMBB offered load off by > 15 % | 15 | 47 | **0** |
| eMBB reroutes | 24 | 6 | **0** |
| l13 background off by > 10 Mbit/s during the surge | 157 / 186 | 3 / 254 | 2 / 255 |
| uncertified fallbacks | 15 | 3 | **0** |
| reservation-limit slots | 216 | 283 | 284 |

**Remaining violations.**
* **Shielded modes (shielded 0, shielded-utility 3 slots):** isolated one-slot URLLC
  spikes (1.0-1.8 ms) on path A at 7 % utilization, with neighbours around 0.3 ms.
  This is consistent with ping noise, since the statistic is the max of 8 probes.
* **Unshielded (7 slots):** besides such spikes, eMBB latency of 42.7 and 50 ms with
  path B at 0.87-0.98 utilization. The shield would have rejected 20 of its
  actions per trial.

**Reservation-limit slots are due to the meter alone.** Certified budgets fill l13
to 0.900, and the meter delivers about 1.10× its budget. Team decision pending
(docs/DECISIONS.md).
