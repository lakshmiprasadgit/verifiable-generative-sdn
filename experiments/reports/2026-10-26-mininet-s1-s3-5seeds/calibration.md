Calibration of the nominal model's latency safety factor k (T-hat latency = k * analytic sum).

Training: experiments/results/mininet-20261026T134135Z/campaign (seeds [1, 2, 3], scenarios all), 8100 slot-slice points, commit `88d5a84`.

* configured k = 1.5: covers 95.8 % of training points
* proposed k = 2.272 (q = 0.99): covers 99.0 %

| slice | n | ratio median | p90 | p99 | max |
|---|---|---|---|---|---|
| embb | 2700 | 0.934 | 1.061 | 1.627 | 3.178 |
| mmtc | 2700 | 0.980 | 1.152 | 1.505 | 2.837 |
| urllc | 2700 | 0.958 | 1.506 | 3.728 | 17.134 |

ratio = recorded latency / analytic latency with k = 1.

Held-out coverage (fraction of points with k * analytic >= recorded):

| campaign | scenario | n | proposed k | configured k |
|---|---|---|---|---|
| experiments/results/mininet-20261026T134135Z/campaign (mininet (measured)) | all | 5399 | 98.5 % | 95.3 % |
| | s1_steady | 1800 | 98.1 % | 93.5 % |
| | s2_background_on_embb_path | 1799 | 99.1 % | 97.4 % |
| | s3_background_on_urllc_path | 1800 | 98.4 % | 94.8 % |

Limits: operating points outside the recorded ones are not covered; only k is fitted; Mininet data inherits its telemetry errors; coverage is not a safety guarantee.
