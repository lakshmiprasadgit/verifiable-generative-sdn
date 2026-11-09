Simulated backend (ground truth). Commit `296d117`, seeds [1, 2, 3, 4, 5]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.503 ± 0.0091 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.029 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – |
| verify ms p95 | 26 ± 1.8 | 3.07 ± 0.22 | 2.85 ± 0.14 | 2.73 ± 0.45 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 16.4 ± 1.1 | 16.4 ± 1.1 | 0.8 ± 0.45 | 16.4 ± 1.1 |
| overload slots | 11.2 ± 1.1 | 11.2 ± 1.1 | 0 ± 0 | 11.2 ± 1.1 |
| reservation-limit slots | 20 ± 0 | 20 ± 0 | 4.4 ± 1.5 | 20 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 1.04 ± 0.011 | 1.04 ± 0.011 | 0.988 ± 0.014 | 1.04 ± 0.011 |
| reserved Mbit/s (mean) | 140 ± 0.024 | 155 ± 0.029 | 91.1 ± 1.2 | 110 ± 0 |
| recovery slots | 19 ± 0 | 19 ± 0 | 0 ± 0 | 19 ± 0 |
| verify ms p95 | 24.5 ± 4 | 3.58 ± 0.28 | 3.08 ± 0.52 | 3.44 ± 0.44 |
| eMBB throughput Mbit/s | 79.8 (5/5 trials) | 79.8 (5/5 trials) | 72.8 (5/5 trials) | 79.8 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 |

### s3_background_on_urllc_path

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 0.744 ± 0.00093 | 0.744 ± 0.00093 | 0.744 ± 0.00093 | 0.744 ± 0.00093 |
| reserved Mbit/s (mean) | 140 ± 0.024 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 26.5 ± 2.6 | 3.3 ± 0.55 | 3.07 ± 0.69 | 3.45 ± 0.54 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 |

### s4_telemetry_faults

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.611 ± 0.0073 | – | – | – |
| fallback slots | 13 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 13 ± 0 | 0 ± 0 | 0 ± 0 | 13 ± 0 |
| applied but shield-rejected | 0 ± 0 | 13 ± 0 | 13 ± 0 | 0 ± 0 |
| max link util | 0.653 ± 0.019 | 0.662 ± 0.017 | 0.662 ± 0.017 | 0.5 ± 0 |
| reserved Mbit/s (mean) | 145 ± 0.021 | 155 ± 0.033 | 112 ± 2 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 22.1 ± 2.5 | 2.76 ± 0.66 | 2.95 ± 0.58 | 2.58 ± 0.62 |
| eMBB throughput Mbit/s | 91 (5/5 trials) | 93.7 (5/5 trials) | 86.7 (5/5 trials) | 86.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 |

### s5_model_mismatch

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 60 ± 0 | 60 ± 0 | 60 ± 0 | 60 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.503 ± 0.0091 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.029 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – |
| verify ms p95 | 27.2 ± 3.5 | 3.01 ± 0.58 | 2.59 ± 0.31 | 2.74 ± 0.31 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 16.4 ± 1.1 | 16.4 ± 1.1 | 1.6 ± 0.55 | 16.4 ± 1.1 |
| overload slots | 11.2 ± 1.1 | 11.2 ± 1.1 | 0.4 ± 0.55 | 11.2 ± 1.1 |
| reservation-limit slots | 20 ± 0 | 20 ± 0 | 5.4 ± 1.5 | 20 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 1.04 ± 0.011 | 1.04 ± 0.011 | 1 ± 0.012 | 1.04 ± 0.011 |
| reserved Mbit/s (mean) | 140 ± 0.024 | 155 ± 0.029 | 91.1 ± 1.2 | 110 ± 0 |
| recovery slots | 19 ± 0 | 19 ± 0 | 0.8 ± 0.45 | 19 ± 0 |
| verify ms p95 | 22.6 ± 1.5 | 3.17 ± 0.5 | 2.84 ± 0.31 | 2.71 ± 0.32 |
| eMBB throughput Mbit/s | 79.8 (5/5 trials) | 79.8 (5/5 trials) | 72.8 (5/5 trials) | 79.8 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 |
