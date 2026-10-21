Simulated backend. Commit `4ce9616`, seeds [1, 2, 3, 4, 5]. Values are mean ± std over seeds.

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
| recovery slots | – | – | – | – |
| verify ms p95 | 19.8 ± 0.92 | 3.05 ± 0.51 | 2.75 ± 0.47 | 3.77 ± 0.26 |
| eMBB throughput Mbit/s | 80.3 | 80.3 | 80.3 | 80.3 |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 |

### s2_background_on_embb_path

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 16.4 ± 1.1 | 16.4 ± 1.1 | 0.8 ± 0.45 | 16.4 ± 1.1 |
| overload slots | 11.2 ± 1.1 | 11.2 ± 1.1 | 0 ± 0 | 11.2 ± 1.1 |
| reservation-limit slots | 20 ± 0 | 20 ± 0 | 5.8 ± 1.9 | 20 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 1.04 ± 0.011 | 1.04 ± 0.011 | 0.988 ± 0.014 | 1.04 ± 0.011 |
| recovery slots | 19 ± 0 | 19 ± 0 | 0 ± 0 | 19 ± 0 |
| verify ms p95 | 20.9 ± 2.3 | 2.87 ± 0.27 | 3 ± 0.47 | 2.73 ± 0.37 |
| eMBB throughput Mbit/s | 79.8 | 79.8 | 73 | 79.8 |
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
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 22.1 ± 1.9 | 2.87 ± 0.33 | 3 ± 0.093 | 3.14 ± 0.29 |
| eMBB throughput Mbit/s | 80.3 | 80.3 | 80.3 | 80.3 |
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
| recovery slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 20.1 ± 0.96 | 3.08 ± 0.91 | 2.6 ± 0.29 | 2.87 ± 0.23 |
| eMBB throughput Mbit/s | 91 | 93.7 | 93.3 | 86.9 |
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
| recovery slots | – | – | – | – |
| verify ms p95 | 22.4 ± 2.1 | 3.83 ± 1 | 3.05 ± 0.37 | 3.46 ± 0.73 |
| eMBB throughput Mbit/s | 80.3 | 80.3 | 80.3 | 80.3 |
| recovered trials | 0/5 | 0/5 | 0/5 | 0/5 |

### s6_actuation_delay_and_failures

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 16.4 ± 1.1 | 16.4 ± 1.1 | 1.6 ± 0.55 | 16.4 ± 1.1 |
| overload slots | 11.2 ± 1.1 | 11.2 ± 1.1 | 0.4 ± 0.55 | 11.2 ± 1.1 |
| reservation-limit slots | 20 ± 0 | 20 ± 0 | 6.8 ± 1.9 | 20 ± 0 |
| candidate rejection rate | 0.671 ± 0.0087 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20 ± 0 | 20 ± 0 | 0 ± 0 |
| max link util | 1.04 ± 0.011 | 1.04 ± 0.011 | 1 ± 0.012 | 1.04 ± 0.011 |
| recovery slots | 19 ± 0 | 19 ± 0 | 0.8 ± 0.45 | 19 ± 0 |
| verify ms p95 | 21.1 ± 2.4 | 4.06 ± 1.2 | 3.22 ± 0.2 | 2.96 ± 0.15 |
| eMBB throughput Mbit/s | 79.8 | 79.8 | 72.9 | 79.8 |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 |
