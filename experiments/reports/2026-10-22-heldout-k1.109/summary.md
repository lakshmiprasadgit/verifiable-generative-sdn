Simulated backend (ground truth). Commit `e46f9b1`, seeds [6, 7, 8, 9, 10]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.504 ± 0.01 | 0.504 ± 0.01 | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – |
| verify ms p95 | 23.8 ± 0.67 | 22.7 ± 3.8 | 3.08 ± 0.2 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 0.8 ± 0.45 | 0.8 ± 0.45 | 0.8 ± 0.45 |
| overload slots | 0.6 ± 0.55 | 0.6 ± 0.55 | 0.6 ± 0.55 |
| reservation-limit slots | 6.2 ± 1.3 | 6.2 ± 1.3 | 6.2 ± 1.3 |
| candidate rejection rate | 0.624 ± 0.0089 | 0.624 ± 0.0089 | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.996 ± 0.022 | 0.996 ± 0.022 | 0.996 ± 0.022 |
| reserved Mbit/s (mean) | 124 ± 0.12 | 91.2 ± 0.69 | 96.2 ± 0.094 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 21.8 ± 0.89 | 21.2 ± 1.4 | 3.06 ± 0.53 |
| eMBB throughput Mbit/s | 72.9 (5/5 trials) | 72.9 (5/5 trials) | 72.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 |

### s3_background_on_urllc_path

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.509 ± 0.0079 | 0.509 ± 0.0079 | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.744 ± 0.00026 | 0.744 ± 0.00048 | 0.744 ± 0.00026 |
| reserved Mbit/s (mean) | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 21.2 ± 1.4 | 23.2 ± 2.4 | 2.94 ± 0.53 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 |

### s4_telemetry_faults

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.613 ± 0.0097 | 0.613 ± 0.0097 | – |
| fallback slots | 13 ± 0 | 13 ± 0 | 60 ± 0 |
| uncertified fallback | 13 ± 0 | 13 ± 0 | 13 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.65 ± 0.017 | 0.65 ± 0.017 | 0.5 ± 0 |
| reserved Mbit/s (mean) | 145 ± 0.026 | 116 ± 0.67 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 21.3 ± 1.4 | 20.9 ± 0.54 | 3.12 ± 0.14 |
| eMBB throughput Mbit/s | 90.9 (5/5 trials) | 90.5 (5/5 trials) | 86.8 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 |

### s5_model_mismatch

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 60 ± 0 | 60 ± 0 | 60 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.504 ± 0.01 | 0.504 ± 0.01 | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.446 ± 0.011 | 0.445 ± 0.0096 | 0.446 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – |
| verify ms p95 | 20.5 ± 0.85 | 22.1 ± 1.1 | 3.42 ± 0.24 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | shielded-utility | fallback-only |
|---|---|---|---|
| violation slots | 1.8 ± 0.45 | 1.8 ± 0.45 | 1.8 ± 0.45 |
| overload slots | 1.4 ± 0.89 | 1.4 ± 0.89 | 1.4 ± 0.89 |
| reservation-limit slots | 7.2 ± 1.3 | 7.2 ± 1.3 | 7.2 ± 1.3 |
| candidate rejection rate | 0.624 ± 0.0089 | 0.624 ± 0.0089 | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 1.01 ± 0.017 | 1.01 ± 0.017 | 1.01 ± 0.017 |
| reserved Mbit/s (mean) | 125 ± 0.12 | 91.2 ± 0.66 | 96.2 ± 0.095 |
| recovery slots | 1 ± 0 | 1 ± 0 | 1 ± 0 |
| verify ms p95 | 23.7 ± 2.8 | 22.4 ± 1.7 | 3.41 ± 0.2 |
| eMBB throughput Mbit/s | 72.9 (5/5 trials) | 72.9 (5/5 trials) | 72.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 |
