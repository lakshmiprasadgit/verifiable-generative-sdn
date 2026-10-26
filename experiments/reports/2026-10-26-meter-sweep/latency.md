# OVS meter sweep

Commit `6e2c3e9`. eMBB alone on path B, meter at the ingress, offered 1.5x the budget; admitted = frames counted past the meter over 4.0 s. Emulated network, one machine.

| budget Mbit/s | UDP payload B | frames per datagram | burst (s at rate) | offered | admitted | admitted / budget (frames) | (IP bytes) | (payload) |
|---|---|---|---|---|---|---|---|---|

## Idle-path latency (path A, no traffic, 100 pings per slot)

| counter reads each slot | median slot p99 ms | max slot p99 ms | slots over 1 ms (of 20) |
|---|---|---|---|
| no | 0.494 | 0.980 | 0 |
| yes | 0.495 | 0.785 | 0 |
