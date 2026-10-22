Simulated backend (ground truth). Commit `e46f9b1`, seeds [6, 7, 8, 9, 10]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.506 ± 0.01 | 0.506 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.032 | 105 ± 1 | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – | – |
| verify ms p95 | 21.5 ± 1.4 | 24.8 ± 2.7 | 2.98 ± 0.25 | 3.3 ± 0.17 | 3.08 ± 0.47 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0.8 ± 0.45 | 0.8 ± 0.45 | 16.4 ± 2.1 | 0.8 ± 0.45 | 0.8 ± 0.45 |
| overload slots | 0.6 ± 0.55 | 0.6 ± 0.55 | 11 ± 3.1 | 0.6 ± 0.55 | 0.6 ± 0.55 |
| reservation-limit slots | 6.2 ± 1.3 | 6.2 ± 1.3 | 20 ± 0 | 6.2 ± 1.3 | 6.2 ± 1.3 |
| candidate rejection rate | 0.626 ± 0.009 | 0.626 ± 0.009 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.996 ± 0.022 | 0.996 ± 0.022 | 1.04 ± 0.018 | 0.996 ± 0.022 | 0.996 ± 0.022 |
| reserved Mbit/s (mean) | 124 ± 0.12 | 91.2 ± 0.69 | 155 ± 0.032 | 91.2 ± 0.69 | 96.2 ± 0.094 |
| recovery slots | 0 ± 0 | 0 ± 0 | 15 ± 7.3 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 25.2 ± 4.4 | 24.4 ± 1.7 | 3.02 ± 0.56 | 3.03 ± 0.28 | 2.89 ± 0.35 |
| eMBB throughput Mbit/s | 72.9 (5/5 trials) | 72.9 (5/5 trials) | 79.7 (5/5 trials) | 72.9 (5/5 trials) | 72.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s3_background_on_urllc_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.67 ± 0.0075 | 0.67 ± 0.0075 | – | – | – |
| fallback slots | 20 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 0.744 ± 0.00026 | 0.744 ± 0.00026 | 0.744 ± 0.00026 | 0.744 ± 0.00026 | 0.744 ± 0.00026 |
| reserved Mbit/s (mean) | 140 ± 0.017 | 107 ± 0.69 | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 23.7 ± 2.1 | 24.6 ± 2 | 3.31 ± 0.43 | 3.45 ± 0.64 | 3.06 ± 0.27 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s4_telemetry_faults

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.614 ± 0.0097 | 0.614 ± 0.0097 | – | – | – |
| fallback slots | 13 ± 0 | 13 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 13 ± 0 | 13 ± 0 | 0 ± 0 | 0 ± 0 | 13 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 13 ± 0 | 13 ± 0 | 0 ± 0 |
| max link util | 0.65 ± 0.017 | 0.65 ± 0.017 | 0.66 ± 0.026 | 0.66 ± 0.026 | 0.5 ± 0 |
| reserved Mbit/s (mean) | 145 ± 0.026 | 116 ± 0.67 | 155 ± 0.024 | 113 ± 0.72 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 23.1 ± 2.1 | 21.7 ± 0.99 | 2.9 ± 0.37 | 2.89 ± 0.26 | 2.93 ± 0.57 |
| eMBB throughput Mbit/s | 90.9 (5/5 trials) | 90.5 (5/5 trials) | 93.5 (5/5 trials) | 86.7 (5/5 trials) | 86.8 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s5_model_mismatch

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 60 ± 0 | 60 ± 0 | 60 ± 0 | 60 ± 0 | 60 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.506 ± 0.01 | 0.506 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.032 | 105 ± 1 | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – | – |
| verify ms p95 | 22.2 ± 0.66 | 26.1 ± 4.4 | 3.09 ± 0.4 | 3.13 ± 0.51 | 3.16 ± 0.3 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 1.8 ± 0.45 | 1.8 ± 0.45 | 16.4 ± 2.1 | 1.8 ± 0.45 | 1.8 ± 0.45 |
| overload slots | 1.4 ± 0.89 | 1.4 ± 0.89 | 11 ± 3.1 | 1.4 ± 0.89 | 1.4 ± 0.89 |
| reservation-limit slots | 7.2 ± 1.3 | 7.2 ± 1.3 | 20 ± 0 | 7.2 ± 1.3 | 7.2 ± 1.3 |
| candidate rejection rate | 0.626 ± 0.009 | 0.626 ± 0.009 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 1.01 ± 0.017 | 1.01 ± 0.017 | 1.04 ± 0.018 | 1.01 ± 0.017 | 1.01 ± 0.017 |
| reserved Mbit/s (mean) | 125 ± 0.12 | 91.2 ± 0.66 | 155 ± 0.032 | 91.2 ± 0.66 | 96.2 ± 0.095 |
| recovery slots | 1 ± 0 | 1 ± 0 | 15 ± 7.3 | 1 ± 0 | 1 ± 0 |
| verify ms p95 | 25.1 ± 3.6 | 23.9 ± 2.4 | 2.71 ± 0.31 | 3.21 ± 0.55 | 3.22 ± 0.18 |
| eMBB throughput Mbit/s | 72.9 (5/5 trials) | 72.9 (5/5 trials) | 79.7 (5/5 trials) | 72.9 (5/5 trials) | 72.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
