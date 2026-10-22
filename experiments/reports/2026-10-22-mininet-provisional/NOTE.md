# Mininet campaign 2026-10-22 - provisional, not a result

Copied unchanged from `experiments/results/mininet-20261022T110546Z/campaign/`
(raw `steps.jsonl` stay local). Emulated network, commit `b78e247`, s1-s3 × 4
controllers × 3 seeds, all 36 trials complete.

Do not quote these numbers as results. The measurements were taken with telemetry
errors that were fixed afterwards (commit `824c8b1`, not yet re-run on Mininet):

* **Reroutes reset flow counters:** NaN or wrong rates. This is why eMBB throughput
  is `null` in s2.
* **Background under-measured** behind the ingress meter. This explains the s2
  reservation-limit slots for every controller.
* **Stepwise flow-counter updates:** most per-slot loss values are artifacts.
* **Meter passes about 1.10× its budget;** rates are counted as frames, not payload.
* **Latency is the maximum of 8 pings;** `overload_slots` cannot see overload after
  shaping.

The summaries here were computed by the summarizer of that commit, before the
NaN-aware metrics. See docs/EXPERIMENTS.md and docs/STATUS.md.
