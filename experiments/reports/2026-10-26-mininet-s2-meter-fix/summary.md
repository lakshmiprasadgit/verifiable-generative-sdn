Emulated Mininet backend (measured values, not ground truth; overload is not observable, latency is the p99 of the slot's ping probes, RTT/2). Commit `c831a00`, seeds [1, 2, 3, 4, 5]. Values are mean ± std over seeds.

### s2_background_on_embb_path

| metric | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0.6 ± 0.89 | 0.8 ± 1.3 | 4.2 ± 1.5 | 1.2 ± 1.8 | 1.2 ± 0.45 |
| overload slots | – | – | – | – | – |
| reservation-limit slots | 4 ± 0.71 | 4.6 ± 1.1 | 20 ± 0 | 3.8 ± 1.1 | 3.4 ± 0.89 |
| candidate rejection rate | 0.627 ± 0.01 | 0.627 ± 0.01 | – | – | – |
| fallback slots | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 60 ± 0 |
| uncertified fallback | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 |
| applied but shield-rejected | 0 ± 0 | 0 ± 0 | 20 ± 0 | 0 ± 0 | 0 ± 0 |
| max link util | 0.982 ± 0.0028 | 0.982 ± 0.0056 | 0.991 ± 0.0026 | 0.971 ± 0.0089 | 0.974 ± 0.0083 |
| reserved Mbit/s (mean) | 125 ± 0.027 | 91.7 ± 0.074 | 155 ± 0.00028 | 91.7 ± 0.07 | 96.6 ± 0.0092 |
| recovery slots | 0 ± 0 | 0.6 ± 1.3 | 1.6 ± 1.1 | 0.6 ± 1.3 | 0 ± 0 |
| verify ms p95 | 30.1 ± 1.3 | 31.7 ± 0.85 | 4.11 ± 0.15 | 4.5 ± 0.67 | 4.6 ± 0.5 |
| eMBB throughput Mbit/s | 73.5 (5/5 trials) | 73.5 (5/5 trials) | 79.7 (5/5 trials) | 73.5 (5/5 trials) | 73.4 (5/5 trials) |
| recovered trials | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
