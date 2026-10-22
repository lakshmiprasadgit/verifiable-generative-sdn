Calibration of the nominal model's latency safety factor k (T-hat latency = k * analytic sum).

Training: experiments/results/2026-10-22-main (seeds all, scenarios ['s1_steady', 's2_background_on_embb_path', 's3_background_on_urllc_path', 's4_telemetry_faults', 's6_actuation_delay_and_failures']), 22380 slot-slice points, commit `e46f9b1`.

* configured k = 1.5: covers 100.0 % of training points
* proposed k = 1.109 (q = 0.99): covers 99.1 %

| slice | n | ratio median | p90 | p99 | max |
|---|---|---|---|---|---|
| embb | 7380 | 1.002 | 1.067 | 1.108 | 1.129 |
| mmtc | 7500 | 0.998 | 1.062 | 1.113 | 1.148 |
| urllc | 7500 | 0.997 | 1.061 | 1.106 | 1.122 |

ratio = recorded latency / analytic latency with k = 1.

Held-out coverage (fraction of points with k * analytic >= recorded):

| campaign | scenario | n | proposed k | configured k |
|---|---|---|---|---|
| experiments/results/2026-10-22-main (simulated) | all | 4500 | 38.8 % | 64.8 % |
| | s5_model_mismatch | 4500 | 38.8 % | 64.8 % |
| experiments/results/2026-10-22-heldout (simulated) | all | 26850 | 88.5 % | 94.1 % |
| | s1_steady | 4500 | 98.3 % | 100.0 % |
| | s2_background_on_embb_path | 4433 | 98.3 % | 100.0 % |
| | s3_background_on_urllc_path | 4500 | 98.3 % | 100.0 % |
| | s4_telemetry_faults | 4500 | 98.3 % | 100.0 % |
| | s5_model_mismatch | 4500 | 39.6 % | 64.7 % |
| | s6_actuation_delay_and_failures | 4417 | 98.3 % | 100.0 % |

Limits: operating points outside the recorded ones are not covered; only k is fitted; Mininet data inherits its telemetry errors; coverage is not a safety guarantee.
