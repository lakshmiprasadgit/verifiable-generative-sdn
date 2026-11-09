Simulated backend (ground truth). Commit `296d117`, seeds [6, 7, 8, 9, 10]. Values are mean ± std over seeds.

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
| verify ms p95 | 25 ± 2.3 | 24.6 ± 1.7 | 3.28 ± 0.58 | 3.04 ± 0.43 | 3.22 ± 0.52 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0.8 ± 0.45 | 0.8 ± 0.45 | 16.4 ± 2.1 | 0.8 ± 0.45 | 0.8 ± 0.45 |
| overload slots | 0.6 ± 0.55 | 0.6 ± 0.55 | 11 ± 3.1 | 0.6 ± 0.55 | 0.6 ± 0.55 |
| reservation-limit slots | 4.2 ± 0.84 | 4.2 ± 0.84 | 20 ± 0 | 4.2 ± 0.84 | 4.2 ± 0.84 |
| candidate rejection rate | 0.626 ± 0.009 | 0.626 ± 0.009 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.996 ± 0.022 | 0.996 ± 0.022 | 1.04 ± 0.018 | 0.996 ± 0.022 | 0.996 ± 0.022 |
| reserved Mbit/s (mean) | 124 ± 0.12 | 90.9 ± 0.66 | 155 ± 0.032 | 91 ± 0.69 | 96 ± 0.093 |
| recovery slots | 0 ± 0 | 0 ± 0 | 15 ± 7.3 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 27 ± 1.1 | 23.6 ± 1 | 3.1 ± 0.53 | 4.06 ± 0.38 | 4.41 ± 0.99 |
| eMBB throughput Mbit/s | 72.7 (5/5 trials) | 72.7 (5/5 trials) | 79.7 (5/5 trials) | 72.7 (5/5 trials) | 72.7 (5/5 trials) |
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
| reserved Mbit/s (mean) | 140 ± 0.017 | 107 ± 0.67 | 155 ± 0.032 | 105 ± 1 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 26.9 ± 2.3 | 24.7 ± 2 | 3.29 ± 0.4 | 3.69 ± 0.4 | 3.3 ± 0.4 |
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
| reserved Mbit/s (mean) | 145 ± 0.026 | 116 ± 0.68 | 155 ± 0.024 | 113 ± 0.72 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 23.5 ± 1.2 | 22.4 ± 1.4 | 2.56 ± 0.3 | 3.25 ± 0.7 | 3.75 ± 0.91 |
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
| verify ms p95 | 24.8 ± 2.6 | 22.5 ± 0.98 | 4.24 ± 1.5 | 3.34 ± 0.41 | 2.65 ± 0.44 |
| eMBB throughput Mbit/s | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) | 80.2 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 1.8 ± 0.45 | 1.8 ± 0.45 | 16.4 ± 2.1 | 1.8 ± 0.45 | 1.8 ± 0.45 |
| overload slots | 1.4 ± 0.89 | 1.4 ± 0.89 | 11 ± 3.1 | 1.4 ± 0.89 | 1.4 ± 0.89 |
| reservation-limit slots | 5.2 ± 0.84 | 5.2 ± 0.84 | 20 ± 0 | 5.2 ± 0.84 | 5.2 ± 0.84 |
| candidate rejection rate | 0.626 ± 0.009 | 0.626 ± 0.009 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 1.01 ± 0.017 | 1.01 ± 0.017 | 1.04 ± 0.018 | 1.01 ± 0.017 | 1.01 ± 0.017 |
| reserved Mbit/s (mean) | 124 ± 0.12 | 91 ± 0.63 | 155 ± 0.032 | 91 ± 0.66 | 96 ± 0.094 |
| recovery slots | 1 ± 0 | 1 ± 0 | 15 ± 7.3 | 1 ± 0 | 1 ± 0 |
| verify ms p95 | 25.4 ± 2.8 | 22.6 ± 1.2 | 3.62 ± 0.86 | 3.95 ± 1.6 | 4.14 ± 0.73 |
| eMBB throughput Mbit/s | 72.7 (5/5 trials) | 72.7 (5/5 trials) | 79.7 (5/5 trials) | 72.7 (5/5 trials) | 72.7 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
