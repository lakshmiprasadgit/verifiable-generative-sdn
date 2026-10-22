Calibration of the nominal model's latency safety factor k (T-hat latency = k * analytic sum).

Training: experiments/results/mininet-20261022T110546Z/campaign (seeds all, scenarios all), 6354 slot-slice points, commit `e46f9b1`.

* configured k = 1.5: covers 98.0 % of training points
* proposed k = 1.858 (q = 0.99): covers 99.0 %

| slice | n | ratio median | p90 | p99 | max |
|---|---|---|---|---|---|
| embb | 2080 | 0.923 | 1.023 | 1.886 | 3.070 |
| mmtc | 2137 | 0.955 | 1.002 | 1.308 | 2.240 |
| urllc | 2137 | 0.761 | 0.985 | 2.901 | 19.450 |

ratio = recorded latency / analytic latency with k = 1.

Held-out coverage (fraction of points with k * analytic >= recorded):

| campaign | scenario | n | proposed k | configured k |
|---|---|---|---|---|
| experiments/results/mininet-20261022T110546Z/campaign (mininet (measured)) | all | 0 | – | – |

Limits: operating points outside the recorded ones are not covered; only k is fitted; Mininet data inherits its telemetry errors; coverage is not a safety guarantee.
