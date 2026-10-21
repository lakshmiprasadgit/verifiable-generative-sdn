# Implementation status

As of 2026-10-21. A research prototype: not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

**Milestone 2 in progress.** The closed control loop runs end to end against a
*simulated* network; the Mininet / Open vSwitch backend is the next increment.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, constraints, STL robustness, verification shield | done; all audit findings addressed |
| 2 | closed loop, network backends, telemetry, experiments | **in progress**: loop + simulated backend + experiments done; Mininet backend next |
| 3 | traffic, telemetry calibration of the nominal model | not started |
| 4 | Eq 42 selection, utility, closed-loop evaluation at scale | not started |
| 5 | experiment campaign and reports | started early (simulation) |

## Done in Milestone 2 (2026-10-21)

* Explicit loop boundaries: observation → candidates → shield → certificate →
  **CertifiedApplier** (the enforcement point that closes audit M3) → network →
  post-action measurement. See [ARCHITECTURE.md](ARCHITECTURE.md).
* Heuristic candidate generator (stand-in for the generative policy).
* Controllers: shielded, unshielded greedy, unshielded capacity-fitted (strong
  baseline), fallback-only.
* Simulated ground-truth network with background traffic, overload loss, telemetry
  faults, controller failures and actuation delay, deliberately different from the
  nominal model.
* Experiment runner with seeds, raw logs, manifests; six scenarios; first campaign
  and fallback ablation. See [EXPERIMENTS.md](EXPERIMENTS.md).
* State-dependent fallback π₀(s), now the default after the ablation.
  See [DECISIONS.md](DECISIONS.md).

## Headline results (simulation, 5 seeds)

* With the static π₀, a background surge made π₀ infeasible and the shield could
  certify nothing; it was no better than no shield. With π₀(s) the violation slots
  fell from 16.4 to 0.8.
* With π₀(s) the shielded controller matched, but did not beat, a good conventional
  heuristic (and in s2 the fallback alone did as well).
* With a mismatched model (s5) the shield certified actions that were unsafe in every
  slot: certification is only as good as the model.

## Tests

`scripts/run_unit_tests.sh` - **428 passed, 0 failed** (no root, no Mininet).
New in Milestone 2: test_loop 15, test_sim 16, test_experiments 10,
test_fallback_policy 8. The H3 temporal-window regression (test_recovery_intents)
is kept.

## Next engineering objective

Mininet / Open vSwitch backend behind the same `NetworkBackend` interface:
topology from `configs/network.yaml`, slice routing and per-slice rate limits,
background traffic hosts, telemetry from OVS port and flow counters (background =
port rate − managed flow rates), latency probes. Code and parsers will be built and
unit-tested without root; the real runs need **one consolidated set of root commands**
from the team.

## Known limitations

* All loop results so far are from simulation; the simulator is unvalidated.
* The nominal model is uncalibrated and not shown to be conservative (s5 shows the
  consequence).
* π₀(s) is not shown to be recursively feasible (Assumption 3); uncertified
  fallbacks are counted in every experiment.
* Selection is "first certified candidate", not Eq 42.
* Background load is held constant over the horizon and is under-measured during
  overload (post-drop counters).
* No mMTC loss intent is active (the model does not predict loss).
* Thresholds in `configs/` are illustrative, not 6G standards.
* `research/problem_formulation_corrected.pdf` stays untracked (rights unconfirmed).
