Emulated Mininet backend (measured values, not ground truth; overload is not observable, latency is the max of the slot's probes). Commit `074e46f`, seeds [1, 2, 3]. Values are mean ± std over seeds.

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 1 ± 1 | 0.333 ± 0.58 | 1.33 ± 0.58 | 0.667 ± 0.58 | 0.333 ± 0.58 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 18.3 ± 1.2 | 18.7 ± 0.58 | 19.7 ± 0.58 | 18.7 ± 0.58 | 19 ± 0 |
| candidate rejection rate | 0.625 ± 0.0011 | 0.627 ± 0.0043 | – | – | – |
| fallback slots | 0.667 ± 1.2 | 0.333 ± 0.58 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0.667 ± 1.2 | 0.333 ± 0.58 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 22.7 ± 1.5 | 0 ± 0 | 0 ± 0 |
| max link util | 0.975 ± 0.0052 | 0.979 ± 0.0011 | 0.992 ± 0.001 | 0.977 ± 0.0065 | 0.971 ± 0.0045 |
| reserved Mbit/s (mean) | 125 ± 1.7 | 96.2 ± 0.56 | 158 ± 0.0028 | 96.7 ± 0.14 | 96 ± 0.014 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 30.7 ± 0.41 | 30.3 ± 0.47 | 3.94 ± 0.21 | 4.12 ± 0.064 | 4.22 ± 0.14 |
| eMBB throughput Mbit/s | 75.7 (3/3 trials) | 76.1 (3/3 trials) | 82 (3/3 trials) | 75.9 (3/3 trials) | 76.4 (3/3 trials) |
| recovered trials | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
