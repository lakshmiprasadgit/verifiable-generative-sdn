# OVS meter sweep

Commit `6e2c3e9`. eMBB alone on path B, meter at the ingress, offered 1.5x the budget; admitted = frames counted past the meter over 4.0 s. Emulated network, one machine.

| budget Mbit/s | UDP payload B | frames per datagram | burst (s at rate) | offered | admitted | admitted / budget (frames) | (IP bytes) | (payload) |
|---|---|---|---|---|---|---|---|---|

## Meter modified every slot vs left alone

Offered 1.5x the budget, 1472-byte payload; admitted / budget per 1 s slot.

| budget Mbit/s | burst (s at rate) | modified every slot | mean | max | per slot |
|---|---|---|---|---|---|
| 20 | 0.01 | no | 0.998 | 1.000 | 0.994 1.000 1.000 0.999 1.000 0.996 |
| 20 | 0.01 | yes | 1.005 | 1.007 | 1.006 1.004 1.007 1.005 1.004 1.006 |
| 20 | 0.1 | no | 1.000 | 1.001 | 1.000 1.000 1.000 1.000 1.001 1.000 |
| 20 | 0.1 | yes | 1.066 | 1.067 | 1.067 1.065 1.067 1.065 1.067 1.064 |
| 20 | 1 | no | 1.000 | 1.001 | 1.000 1.000 1.000 1.001 1.000 1.000 |
| 20 | 1 | yes | 1.495 | 1.500 | 1.474 1.500 1.500 1.500 1.500 1.496 |
| 50 | 0.01 | no | 0.999 | 1.001 | 1.001 1.000 1.000 0.991 1.000 1.000 |
| 50 | 0.01 | yes | 1.006 | 1.008 | 1.007 1.005 1.005 1.004 1.008 1.005 |
| 50 | 0.1 | no | 1.000 | 1.000 | 1.000 1.000 1.000 1.000 1.000 1.000 |
| 50 | 0.1 | yes | 1.066 | 1.067 | 1.066 1.065 1.067 1.065 1.067 1.065 |
| 50 | 1 | no | 1.000 | 1.000 | 1.000 1.000 1.000 1.000 1.000 0.999 |
| 50 | 1 | yes | 1.497 | 1.501 | 1.483 1.500 1.501 1.500 1.500 1.499 |
