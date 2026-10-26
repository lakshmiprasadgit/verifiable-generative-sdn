Emulated Mininet backend (measured values, not ground truth; overload is not observable, latency is the max of the slot's probes). Commit `88d5a84`, seeds [1, 2, 3, 4, 5]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 4.6 ± 6.7 | 1.6 ± 1.8 | 0.4 ± 0.55 | 0.8 ± 0.84 | 1.2 ± 1.8 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.503 ± 0.0091 | 0.503 ± 0.0091 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.404 ± 0.0048 | 0.404 ± 0.0033 | 0.402 ± 0.00089 | 0.402 ± 0.0012 | 0.402 ± 0.00032 |
| reserved Mbit/s (mean) | 155 ± 0.0014 | 105 ± 0.069 | 155 ± 0.00031 | 105 ± 0.0088 | 110 ± 0 |
| recovery slots | – | – | – | – | – |
| verify ms p95 | 44.4 ± 15 | 31.1 ± 3.2 | 3.88 ± 0.25 | 3.92 ± 0.073 | 4.08 ± 0.19 |
| eMBB throughput Mbit/s | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0.8 ± 0.84 | 1.2 ± 0.84 | 3 ± 1 | 1.2 ± 0.84 | 1 ± 0.71 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 19.8 ± 0.45 | 19.8 ± 0.45 | 20 ± 0 | 20 ± 0 | 19.4 ± 0.55 |
| candidate rejection rate | 0.627 ± 0.01 | 0.627 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.987 ± 0.004 | 0.988 ± 0.0029 | 0.993 ± 0.0025 | 0.988 ± 0.0043 | 0.982 ± 0.008 |
| reserved Mbit/s (mean) | 125 ± 0.036 | 91.9 ± 0.079 | 155 ± 0.00028 | 91.9 ± 0.0073 | 96.9 ± 0.039 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0.4 ± 0.89 | 0.2 ± 0.45 | 0.2 ± 0.45 |
| verify ms p95 | 29.4 ± 0.64 | 28.9 ± 1.2 | 3.83 ± 0.087 | 4.1 ± 0.25 | 4.4 ± 0.37 |
| eMBB throughput Mbit/s | 74.9 (5/5 trials) | 74.9 (5/5 trials) | 79.8 (5/5 trials) | 74.9 (5/5 trials) | 74.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s3_background_on_urllc_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 4.8 ± 2.7 | 4.4 ± 1.3 | 4.6 ± 2.6 | 5 ± 1.2 | 6.2 ± 1.3 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.663 ± 0.0088 | 0.663 ± 0.0088 | – | – | – |
| fallback slots | 19 ± 0 | 19 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 19 ± 0 | 19 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 19.8 ± 0.45 | 19.8 ± 0.45 | 0 ± 0 |
| max link util | 0.742 ± 0.00033 | 0.743 ± 0.00054 | 0.742 ± 0.00034 | 0.742 ± 0.00038 | 0.742 ± 0.00061 |
| reserved Mbit/s (mean) | 141 ± 0.0007 | 107 ± 0.064 | 155 ± 0.00066 | 105 ± 0.016 | 110 ± 0 |
| recovery slots | 2.8 ± 4.8 | 1.2 ± 2.7 | 0 ± 0 | 4 ± 3 | 2.8 ± 3.1 |
| verify ms p95 | 30.1 ± 1.3 | 29.8 ± 1 | 3.9 ± 0.18 | 3.96 ± 0.12 | 4.05 ± 0.25 |
| eMBB throughput Mbit/s | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) | 80.1 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
