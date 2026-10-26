# Mininet s2 after the meter fix - 2026-10-26 17:33 UTC

Copied from `experiments/results/mininet-20261026T173343Z/` (raw data stays local).
Commit `c831a00` (0.01 s meter burst, meter overshoot ε = 0.01 modelled), clean tree.
Integration 11/11 in both passes, no leftovers. s2 × 5 controllers × seeds 1-5.

Emulated-network measurements, not ground truth and not real-network validation.

| reservation-limit slots per trial | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| before (`2026-10-26-mininet-s1-s3-5seeds`) | 19.8 | 19.8 | 20 | 20 | 19.4 |
| after | 4.0 | 4.6 | 20 | 3.8 | 3.4 |

Of the shielded controller's 20 remaining slots (5 trials), 13 fall in the surge's
first three slots (t = 20-22), while the controller is still reacting to it. The
others exceed the 0.9 limit by 0.01-2.6 %, consistent with measurement noise in
the background estimate. The unshielded controller keeps 20 (it never adapts).

Violation slots: shielded 0.6 ± 0.9, shielded-utility 0.8 ± 1.3, unshielded
4.2 ± 1.5; the shield would have rejected 20 of the unshielded controller's applied
actions per trial.
