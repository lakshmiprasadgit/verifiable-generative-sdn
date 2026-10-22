Emulated Mininet backend (measured values, not ground truth; overload is not observable, latency is the max of the slot's probes). Commit `dde4fe4`, seeds [1, 2, 3]. Values are mean ± std over seeds.

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 1 ± 1 | 2.33 ± 0.58 | 0.333 ± 0.58 | 0.333 ± 0.58 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 19 ± 0 | 19 ± 0 | 18.3 ± 0.58 | 19 ± 0 | 19.3 ± 0.58 |
| candidate rejection rate | 0.626 ± 0.0019 | 0.626 ± 0.0019 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.976 ± 0.0067 | 0.978 ± 0.0027 | 0.99 ± 0.00069 | 0.973 ± 0.0043 | 0.981 ± 0.00014 |
| reserved Mbit/s (mean) | 127 ± 0.019 | 96.8 ± 0.08 | 158 ± 0.0035 | 96.9 ± 0.033 | 95.9 ± 0.042 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0.333 ± 0.58 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 29.5 ± 1.1 | 29.6 ± 0.041 | 4.69 ± 0.75 | 4.36 ± 0.23 | 4.33 ± 0.28 |
| eMBB throughput Mbit/s | 77 (3/3 trials) | 77 (3/3 trials) | 82.4 (3/3 trials) | 77.1 (3/3 trials) | 77 (3/3 trials) |
| recovered trials | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
