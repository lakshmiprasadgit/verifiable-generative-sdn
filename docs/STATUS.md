# Implementation status

As of 2026-10-21. A research prototype: not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

**Milestone 2 in progress.** The closed control loop runs end to end against a
*simulated* network. The Mininet / Open vSwitch backend is implemented and
unit-tested without root. Its **first privileged run (2026-10-21 17:10 UTC) failed
all 7 integration tests**; both causes are found and fixed (below), but the fixes
have **not yet been confirmed on a real Mininet network**. No Mininet results exist.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, constraints, STL robustness, verification shield | done; all audit findings addressed |
| 2 | closed loop, network backends, telemetry, experiments | **in progress**: loop, simulated backend, experiments done; Mininet backend: first root run failed, fixes awaiting a second root run |
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

## First Mininet run (2026-10-21, `experiments/results/mininet-20261021T171037Z/`)

All 7 integration tests failed; the campaign was correctly not started.

1. **`OFPMMFC_INVALID_METER` on s1** for `actions=meter:1,output:2`. Root cause: the
   backend installed each slice's flows *before* creating its meter, and an OpenFlow
   switch rejects a flow whose meter does not exist yet. The unit tests missed it
   because the fake fabric accepted such flows. Fixed: meters are created before
   any flow, the backend refuses to send a flow whose meter it has not created on
   that switch, and the fake fabric now rejects what OVS rejects.
2. **`RTNETLINK answers: File exists` (bgdst-eth0 / s5-eth7)** in the other 6 tests.
   Root cause: the failing constructor never closed its half-built network (the test
   fixture never received a reference to it), so its interfaces and processes
   outlived the test and every later build collided with them. `mn -c` afterwards
   removed the interfaces but not 8 iperf3 servers, which are still running in
   orphaned namespaces (they will be removed by the next run's setup). Fixed:
   construction and `MininetFabric.setup` release a partial network on any failure;
   `close()` is idempotent and runs every step even if one fails; setup removes this
   plan's leftovers first; every integration test ends with a leak check
   (interfaces, bridges, processes); the script runs the suite twice.

See [DECISIONS.md](DECISIONS.md) and [EXPERIMENTS.md](EXPERIMENTS.md) for details.

## Headline results (simulation, 5 seeds)

* With the static π₀, a background surge made π₀ infeasible and the shield could
  certify nothing; it was no better than no shield. With π₀(s) the violation slots
  fell from 16.4 to 0.8.
* With π₀(s) the shielded controller matched, but did not beat, a good conventional
  heuristic (and in s2 the fallback alone did as well).
* With a mismatched model (s5) the shield certified actions that were unsafe in every
  slot: certification is only as good as the model.

## Tests

`scripts/run_unit_tests.sh` - **460 passed, 0 failed** (no root, no Mininet).
New in Milestone 2: test_loop 15, test_sim 16, test_experiments 10,
test_fallback_policy 8, test_emu 32 (13 of them regressions for the first Mininet
run). Integration tests (`tests/integration`, now 9) are skipped without root; on
real Mininet they have run once, before the fixes, and all failed. The H3 temporal-window regression (test_recovery_intents)
is kept.

## Next engineering objective

Re-run the integration suite on real Mininet, as root:

```bash
sudo scripts/mininet_run.sh
```

By default it runs only the 9 integration tests, twice and without cleanup in
between, so that leaks fail the second pass (a few minutes). The 40-minute s1-s3
campaign runs only with `--campaign`, and only after every pass is green; it is not
to be started until the suite passes reliably. Then: fix whatever the real network
still contradicts (e.g. counter precision, slot timing), run the campaign, and
compare the measured results with the simulation. `feat/m2-mininet-backend` is
merged into `main` only after that.

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
