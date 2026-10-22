Simulated backend (ground truth). Commit `e46f9b1`, seeds [1, 2, 3, 4, 5]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.503 ± 0.0091 | 0.503 ± 0.0091 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.029 | 105 ± 0.98 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – | – |
| verify ms p95 | 22.8 ± 3.1 | 22.3 ± 1.4 | 2.94 ± 0.23 | 3.92 ± 0.49 | 3.21 ± 0.54 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0.8 ± 0.45 | 0.8 ± 0.45 | 16.4 ± 1.1 | 0.8 ± 0.45 | 0.8 ± 0.45 |
| overload slots | 0 ± 0 | 0 ± 0 | 11.2 ± 1.1 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 5.8 ± 1.9 | 5.8 ± 1.9 | 20 ± 0 | 5.8 ± 1.9 | 5.8 ± 1.9 |
| candidate rejection rate | 0.628 ± 0.01 | 0.628 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.988 ± 0.014 | 0.988 ± 0.014 | 1.04 ± 0.011 | 0.988 ± 0.014 | 0.988 ± 0.014 |
| reserved Mbit/s (mean) | 125 ± 0.095 | 91.2 ± 1.1 | 155 ± 0.029 | 91.3 ± 1.2 | 96.2 ± 0.081 |
| recovery slots | 0 ± 0 | 0 ± 0 | 19 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 22.1 ± 0.74 | 22.6 ± 2.2 | 3.16 ± 0.35 | 2.99 ± 0.14 | 3.18 ± 0.25 |
| eMBB throughput Mbit/s | 73 (5/5 trials) | 73 (5/5 trials) | 79.8 (5/5 trials) | 73 (5/5 trials) | 73 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s3_background_on_urllc_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 0.744 ± 0.00093 | 0.744 ± 0.00093 | 0.744 ± 0.00093 | 0.744 ± 0.00093 | 0.744 ± 0.00093 |
| reserved Mbit/s (mean) | 140 ± 0.024 | 107 ± 1 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 23.6 ± 0.78 | 22.5 ± 0.39 | 2.89 ± 0.19 | 3.16 ± 0.4 | 3.47 ± 0.4 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s4_telemetry_faults

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.611 ± 0.0073 | 0.611 ± 0.0073 | – | – | – |
| fallback slots | 13 ± 0 | 13 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 13 ± 0 | 13 ± 0 | 0 ± 0 | 0 ± 0 | 13 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 13 ± 0 | 13 ± 0 | 0 ± 0 |
| max link util | 0.653 ± 0.019 | 0.653 ± 0.02 | 0.662 ± 0.017 | 0.662 ± 0.017 | 0.5 ± 0 |
| reserved Mbit/s (mean) | 145 ± 0.021 | 116 ± 0.95 | 155 ± 0.033 | 112 ± 2 | 110 ± 0 |
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 20.5 ± 1.2 | 21.2 ± 1.8 | 3.06 ± 0.16 | 3.48 ± 0.28 | 2.94 ± 0.44 |
| eMBB throughput Mbit/s | 91 (5/5 trials) | 90.6 (5/5 trials) | 93.7 (5/5 trials) | 86.7 (5/5 trials) | 86.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

### s5_model_mismatch

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 60 ± 0 | 60 ± 0 | 60 ± 0 | 60 ± 0 | 60 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.503 ± 0.0091 | 0.503 ± 0.0091 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 | 0.445 ± 0.011 |
| reserved Mbit/s (mean) | 155 ± 0.029 | 105 ± 0.98 | 155 ± 0.029 | 105 ± 1 | 110 ± 0 |
| recovery slots | – | – | – | – | – |
| verify ms p95 | 21.8 ± 1.4 | 22 ± 0.27 | 3.15 ± 0.24 | 2.95 ± 0.31 | 3.04 ± 0.16 |
| eMBB throughput Mbit/s | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) | 80.3 (5/5 trials) |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 1.6 ± 0.55 | 1.6 ± 0.55 | 16.4 ± 1.1 | 1.6 ± 0.55 | 1.6 ± 0.55 |
| overload slots | 0.4 ± 0.55 | 0.4 ± 0.55 | 11.2 ± 1.1 | 0.4 ± 0.55 | 0.4 ± 0.55 |
| reservation-limit slots | 6.8 ± 1.9 | 6.8 ± 1.9 | 20 ± 0 | 6.8 ± 1.9 | 6.8 ± 1.9 |
| candidate rejection rate | 0.628 ± 0.01 | 0.628 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 1 ± 0.012 | 1 ± 0.012 | 1.04 ± 0.011 | 1 ± 0.012 | 1 ± 0.012 |
| reserved Mbit/s (mean) | 125 ± 0.098 | 91.2 ± 1.1 | 155 ± 0.029 | 91.3 ± 1.2 | 96.2 ± 0.088 |
| recovery slots | 0.8 ± 0.45 | 0.8 ± 0.45 | 19 ± 0 | 0.8 ± 0.45 | 0.8 ± 0.45 |
| verify ms p95 | 22.5 ± 1.2 | 22 ± 1.9 | 3.12 ± 0.37 | 3.1 ± 0.31 | 3.43 ± 0.72 |
| eMBB throughput Mbit/s | 72.9 (5/5 trials) | 72.9 (5/5 trials) | 79.8 (5/5 trials) | 72.9 (5/5 trials) | 72.9 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
