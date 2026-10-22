Emulated Mininet backend (measured values, not ground truth). Commit `b78e247`, seeds [1, 2, 3]. Values are mean ± std over seeds.

### s1_steady

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 0 ± 0 | 1 ± 1.7 | 2 ± 1 | 0 ± 0 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.504 ± 0.0011 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 3 ± 1 | 0 ± 0 | 0 ± 0 |
| max link util | 0.421 ± 0.00051 | 0.422 ± 0.00043 | 0.428 ± 0.0073 | 0.423 ± 0.0014 |
| recovery slots | – | – | – | – |
| verify ms p95 | 27.9 ± 0.31 | 4.18 ± 0.16 | 4.61 ± 0.94 | 4.17 ± 0.036 |
| eMBB throughput Mbit/s | 83 | 83.5 | 82.8 | 83.5 |
| recovered trials | 0/3 | 0/3 | 0/3 | 0/3 |

### s2_background_on_embb_path

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 2 ± 1.7 | 0.667 ± 0.58 | 2.67 ± 1.5 | 1.67 ± 1.2 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 17.7 ± 0.58 | 19.7 ± 0.58 | 15.7 ± 1.2 | 19 ± 0 |
| candidate rejection rate | 0.631 ± 0.0019 | – | – | – |
| fallback slots | 2 ± 1.7 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 2 ± 1.7 | 0 ± 0 | 0 ± 0 | 3 ± 0 |
| applied but shield-rejected | 0 ± 0 | 21 ± 1 | 7 ± 3.5 | 0 ± 0 |
| max link util | 0.992 ± 0.003 | 0.994 ± 0.0012 | 0.979 ± 0.0042 | 0.991 ± 0.0021 |
| recovery slots | 0.667 ± 1.2 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| verify ms p95 | 31.3 ± 2.2 | 3.99 ± 0.14 | 4.22 ± 0.43 | 4.34 ± 0.19 |
| eMBB throughput Mbit/s | nan | 82.2 | nan | nan |
| recovered trials | 3/3 | 3/3 | 3/3 | 3/3 |

### s3_background_on_urllc_path

| metric | shielded | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|
| violation slots | 1.33 ± 0.58 | 1.33 ± 0.58 | 2 ± 1 | 1.33 ± 1.2 |
| overload slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| reservation-limit slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| candidate rejection rate | 0.672 ± 0.0075 | – | – | – |
| fallback slots | 20 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 20 ± 0 | 0 ± 0 | 0 ± 0 | 20 ± 0 |
| applied but shield-rejected | 0 ± 0 | 20.7 ± 0.58 | 20 ± 0 | 0 ± 0 |
| max link util | 0.789 ± 0.00054 | 0.788 ± 0.00091 | 0.788 ± 0.00023 | 0.79 ± 0.0029 |
| recovery slots | 1 ± 1.7 | 0 ± 0 | 0 ± 0 | 1.67 ± 1.5 |
| verify ms p95 | 31.8 ± 0.37 | 3.94 ± 0.11 | 3.83 ± 0.26 | 3.79 ± 0.19 |
| eMBB throughput Mbit/s | 83.5 | 83.5 | 83 | 83.5 |
| recovered trials | 3/3 | 3/3 | 3/3 | 3/3 |
