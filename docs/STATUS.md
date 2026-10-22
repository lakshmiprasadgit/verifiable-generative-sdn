# Implementation status

As of 2026-10-22. A research prototype: not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

**Every Stage 1 milestone has its implementation in place; what remains is
validation on the emulated network and team decisions.**

* **Simulation:** the closed loop runs end to end, with first-certified and Eq 42
  selection, a calibration tool, and campaigns on main and held-out seeds.
* **Mininet:** the backend passed its 9 integration tests twice (2026-10-21). Its
  first campaign (2026-10-22) exposed telemetry errors, which are fixed in code
  (`824c8b1`).
* **Not yet re-run on Mininet**, which needs root: the integration suite and the
  s2 campaign. Until then, the Mininet results stay provisional.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, constraints, STL robustness, verification shield | **done**; all audit findings addressed |
| 2 | closed loop, network backends, telemetry, experiments | **done in code**: telemetry and metric fixes from the Mininet audit (`824c8b1`). **Open:** re-run the integration suite and s2 on Mininet (root) |
| 3 | traffic, telemetry, nominal-model calibration | **done (method and simulator evidence)**: calibration tool, held-out evaluation, provisional Mininet fit. The configured factor is deliberately unchanged. **Open:** fit and adopt on fixed Mininet data |
| 4 | fallback, candidates, selection, closed loop | **done**: π₀(s), heuristic candidates, enforced closed loop, Eq 42 utility selection (`shielded-utility`, D20). **Open:** Assumption 3 (recursive feasibility) is still not shown |
| 5 | experiments, metrics, reports | **done for simulation**: 2026-10-22 campaigns (main, held-out, calibration ablation) in `experiments/reports/`; dashboard. **Open:** a Mininet campaign after the fixes |

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

## Mininet re-run after the fixes (2026-10-22 17:09, `mininet-20261022T170942Z`)

At `074e46f`: integration suite 9/9 twice; s2 × 5 controllers × 3 seeds, all trials
complete.

**Confirmed on the emulated network:**
* no missing measurements (before: 65);
* background on l13 measured at 123.5 Mbit/s against 123.6 expected (before: 102);
* fewer uncertified fallbacks.

**Two remaining causes found:**
1. **Stale rule counters** (OVS refreshes them every 500 ms). Spurious readings
   triggered π₀(s) reroutes and the shielded runs' few violations. Fixed in code
   since (snapshots call `ovs-appctl revalidator/wait`, read-only), but **not yet
   run on Mininet**.
2. **The meter passes about 1.10× its budget,** which alone explains the 18-20
   reservation-limit slots per trial for every controller. Needs a team decision
   (DECISIONS, 2026-10-22).

Details: EXPERIMENTS.md, "Campaign 2".

## Done on 2026-10-22 (after the Mininet audit)

| Commit | What |
|---|---|
| `824c8b1` | Telemetry: reinstall-safe rule rates (by rule age), post-meter background, NaN-aware loss and summaries, overload "not observable" on measured data, generator never reads unknowns as 0 (D21). Stricter fake fabric; regressions fail on the old code |
| `7eb7e26`, `7720cde` | Eq 42 selection with an Eq 27 utility (`shielded-utility`, D20); dashboard shows predicted returns |
| `035a480` | Calibration tool (`python -m vgcp.experiments.calibrate`), `--latency-safety-factor` ablation |
| `e46f9b1` | Reserved-bandwidth metric |

Results: docs/EXPERIMENTS.md, "Results - 2026-10-22 campaign". In short:
* the fixes left the shielded results unchanged;
* Eq 42 reserves 20-32 % less bandwidth with identical outcomes;
* a simulator-calibrated factor (1.109) removes s3's 20 uncertified fallbacks on
  held-out seeds without new violations, but does not fix s5;
* the provisional Mininet fit disagrees (1.86), so the configured 1.5 is kept.

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

`scripts/run_unit_tests.sh` - **494 passed, 0 failed** (no root, no Mininet; includes test_demo, test_selection, test_calibration).
New in Milestone 2: test_loop 15, test_sim 16, test_experiments 10,
test_fallback_policy 8, test_emu 32 (13 of them regressions for the first Mininet
run). Integration tests (`tests/integration`, 9) are skipped without root; on real
Mininet: run 1 (before the fixes) 7/7 failed, run 2 9/9 passed twice. The H3 temporal-window regression (test_recovery_intents)
is kept.

## Next engineering objective

Validate the counter-refresh fix on Mininet, as root: the integration suite twice
(now 10 tests, including steady counters), then s2 with all five controllers
(about 17 minutes in total):

```bash
sudo scripts/mininet_run.sh --campaign --only s2_background_on_embb_path
```

Then:
1. Compare with `mininet-20261022T170942Z`. Expected: no 0.5×/1.5× offered-load
   readings, no spurious background jumps, and so no π₀ reroutes during the surge.
   The reservation-limit slots will remain until the meter decision.
2. Run s1-s3 (`--campaign` alone, about 52 minutes).
3. Fit the latency factor on Mininet seeds and check it on held-out Mininet seeds.

Team decisions still needed:
* rate units (payload or frames) and eMBB's packet size (1500 bytes fragments);
* probes per slot (latency is the max of 8);
* the meter's ~1.10× pass-through.

## Known limitations

* All loop results so far are from simulation; the simulator is unvalidated. The
  Mininet integration tests validate the emulation's plumbing, not the controller.
* The nominal model's factor is calibrated only on the simulator, and on Mininet only
  provisionally; the configured 1.5 is kept (DECISIONS). s5 shows that calibration
  cannot fix a structurally wrong model.
* π₀(s) is not shown to be recursively feasible (Assumption 3); uncertified
  fallbacks are counted in every experiment.
* Eq 42 (`shielded-utility`) uses illustrative weights and the nominal model's
  predictions; `shielded` keeps first-certified.
* The Mininet telemetry fixes are unit-tested against a stricter fake fabric only,
  until the root re-run.
* Background load is held constant over the horizon and is under-measured during
  overload (post-drop counters).
* No mMTC loss intent is active (the model does not predict loss).
* Thresholds in `configs/` are illustrative, not 6G standards.
* `research/problem_formulation_corrected.pdf` stays untracked (rights unconfirmed).
