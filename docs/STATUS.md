# Implementation status

As of 2026-10-22. A research prototype: not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

**Milestone 2 in progress.** The closed control loop runs end to end against a
*simulated* network. The Mininet / Open vSwitch backend is implemented and
unit-tested without root. Its first privileged run failed all 7 integration tests;
after the fixes (below, commit `692ba3b`) the **9 integration tests passed on real
Mininet in two consecutive passes** (2026-10-21 17:22 UTC). The first Mininet
campaign ran on 2026-10-22 (36 trials, complete), but an audit found measurement
errors in its telemetry, so its results are **provisional** and not yet reported
(below). A dashboard now shows the loop live on the simulated network.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, constraints, STL robustness, verification shield | done; all audit findings addressed |
| 2 | closed loop, network backends, telemetry, experiments | **mostly done**: loop, simulated backend, experiments, Mininet backend (integration green twice), first Mininet campaign (provisional). Open: telemetry fixes, re-run, write-up, review and merge |
| 3 | traffic, telemetry calibration of the nominal model | not started; telemetry problems identified by the 2026-10-22 audit |
| 4 | fallback, candidates, Eq 42 selection, closed loop | partly done early: π₀(s), heuristic candidates and the enforced closed loop exist; Eq 42 selection not started |
| 5 | experiment campaign and reports | started: simulation campaigns reported; one provisional Mininet campaign; dashboard |

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
* Control-loop dashboard (`scripts/run_dashboard.sh`, no root): steps the real loop on
  the simulated network and shows candidates, certificates, fallbacks, outcomes and
  saved campaigns. See the README.

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
   removed the interfaces but not 8 iperf3 servers in orphaned namespaces (removed
   since; see run 2). Fixed:
   construction and `MininetFabric.setup` release a partial network on any failure;
   `close()` is idempotent and runs every step even if one fails; setup removes this
   plan's leftovers first; every integration test ends with a leak check
   (interfaces, bridges, processes); the script runs the suite twice.

See [DECISIONS.md](DECISIONS.md) and [EXPERIMENTS.md](EXPERIMENTS.md) for details.

## Second Mininet run (2026-10-21, `experiments/results/mininet-20261021T172242Z/`)

At commit `692ba3b`, clean tree. **9/9 integration tests passed in both passes**
(69.73 s, 69.44 s), with no cleanup in between. After the last pass: 0 switch
interfaces and 0 harness iperf3 processes left. The 8 orphaned iperf3 servers from run 1
are gone as well (checked afterwards with `pgrep`). This shows the emulation does what the telemetry
and constraints assume, within the tests' loose tolerances; it says nothing about the
controller's performance or the safety of a real network.

## Mininet campaign (2026-10-22, `experiments/results/mininet-20261022T110546Z/`) - provisional

s1-s3 × 4 controllers × 3 seeds at commit `b78e247`, clean tree: all 36 trials
complete (60 step records and a summary each), no probe lost. A read-only audit
traced the anomalies to the emulation's telemetry, not to the controller:

* **Reroutes reset flow counters.** Rules are deleted and re-added, so the next
  delta is NaN (65 missing values, all in s2, all at reroute slots) or silently
  wrong. This turned eMBB mean throughput into `null` and fed missing data to the
  controllers.
* **Background under-measured** by about 22 Mbit/s when the ingress meter drops
  traffic: the ingress rule counts packets before the meter. Budgets certified on
  that basis overfilled path B, which is why all controllers show s2
  reservation-limit slots.
* **Flow counters update in steps** (offered load reads 0.5× then 1.5×); this
  makes most of the per-slot loss values artifacts.
* **The meter passes about 1.10× its budget** at 50-70 Mbit/s (cause unknown).
* **Units differ:** scenario rates are payloads, while counters count frames.
* **s3:** 20 uncertified fallbacks per shielded seed. The nominal model predicts
  URLLC about 1.16 ms (bound 1 ms) where about 0.45 ms was measured. Measured URLLC
  exceeded 1 ms in 2 of those 60 fallback slots.
* **Metric limits:** latency is the max of 8 pings; `overload_slots` cannot detect
  overload on Mininet (post-shaping utilization).

These numbers are not to be quoted as results until the telemetry is fixed and s2
re-run.

## Dashboard (2026-10-22)

`scripts/run_dashboard.sh` (no root) steps the real loop on the simulated network
and shows candidates, certificates, fallbacks (including UNCERTIFIED FALLBACK),
outcomes, the observation used, a timeline and a summary. Saved campaigns are
labelled as historical. Its records equal `run_trial`'s (tested in `test_demo`).

## Headline results (simulation, 5 seeds)

* With the static π₀, a background surge made π₀ infeasible and the shield could
  certify nothing; it was no better than no shield. With π₀(s) the violation slots
  fell from 16.4 to 0.8.
* With π₀(s) the shielded controller matched, but did not beat, a good conventional
  heuristic (and in s2 the fallback alone did as well).
* With a mismatched model (s5) the shield certified actions that were unsafe in every
  slot: certification is only as good as the model.

## Tests

`scripts/run_unit_tests.sh` - **467 passed, 0 failed** (no root, no Mininet; includes test_demo 7).
New in Milestone 2: test_loop 15, test_sim 16, test_experiments 10,
test_fallback_policy 8, test_emu 32 (13 of them regressions for the first Mininet
run). Integration tests (`tests/integration`, 9) are skipped without root; on real
Mininet: run 1 (before the fixes) 7/7 failed, run 2 9/9 passed twice. The H3 temporal-window regression (test_recovery_intents)
is kept.

## Next engineering objective

Fix the Mininet telemetry found by the 2026-10-22 audit:
1. make the fake fabric strict (counter resets, pre-meter ingress counters);
2. fix reroute counter handling and meter-aware background;
3. use NaN-aware metrics with valid-slot counts.

Then run the integration suite twice and re-run s2 on Mininet (12 trials, about
14 minutes) before s1-s3. Decisions needed from the team: rate units (payload or
frames, eMBB packet size), probes per slot, and an overload definition on Mininet.
After that, record the results in EXPERIMENTS.md, then review
`feat/m2-mininet-backend` and decide on merging it into `main` (not merged).

## Known limitations

* All loop results so far are from simulation; the simulator is unvalidated. The
  Mininet integration tests validate the emulation's plumbing, not the controller.
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
