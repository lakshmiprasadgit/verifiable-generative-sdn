# Experiments

All results below come from the **simulated backend** (`vgcp.sim`), a ground-truth
model that deliberately differs from the shield's nominal model. They are not
measurements of a real network and do not establish real-network safety. The
Mininet integration tests pass, and one Mininet campaign has run, but its results
are **provisional** because of telemetry errors (see "Emulated network runs" below).

## Research questions

| RQ | Question | Scenario |
|---|---|---|
| RQ0 | What does the shield cost when nothing goes wrong? | s1 |
| RQ1 | Does accounting for measured background load (H1) prevent overload? What happens when nothing - not even π₀ - fits? | s2 |
| RQ2 | Does the shield protect the 1 ms URLLC intent when its path is loaded, and how often can it certify nothing? | s3 |
| RQ3 | Does the shield refuse to act on stale or missing telemetry, and what does acting blind cost? | s4 |
| RQ4 | How often is an action the shield certified actually unsafe when the model is wrong? | s5 |
| RQ5 | What breaks when actions take effect late, or are lost? | s6 |
| RQ6 | Does a state-dependent fallback π₀(s) change the answers (ablation)? | all, static vs capacity-aware π₀ |
| RQ7 | What does utility-based selection (Eq 42) change, and does a calibrated model reduce over-conservatism? | all, 2026-10-22 campaign |

## Controllers (same candidate generator and preference order in all)

* **shielded** - first certified candidate, otherwise π₀(s_t) (Remark 1).
* **unshielded** - the generator's first choice (greedy eMBB), unverified.
* **unshielded-fitted** - unverified, but prefers the capacity-fitted heuristic: a
  strong conventional baseline, so the shield is not compared with a straw man.
* **fallback-only** - always π₀(s_t).

Unshielded controllers also ask the shield in shadow mode (no effect on the action),
which counts actions applied that the shield would have rejected.

## Scenarios

Six scenarios in `experiments/scenarios/`, 60 slots of 1 s each, base demand URLLC
2, eMBB 80, mMTC 2 Mbit/s with 5 % noise. Parameters were chosen from the topology
(e.g. a background surge that fills path B) before any results existed.

| | Disturbance |
|---|---|
| s1 | none (control case) |
| s2 | 120 Mbit/s unmanaged traffic on path B (eMBB's path, 200 Mbit/s), slots 20-40 |
| s3 | 35 Mbit/s unmanaged traffic on path A (URLLC's path, 50 Mbit/s), slots 20-40 |
| s4 | eMBB demand +50 % (15-35); telemetry frozen (20-30); background counters missing (40-45) |
| s5 | model mismatch: URLLC packets 1500 B (model: 64 B), mMTC 500 B (model: 100 B), 20 % latency noise |
| s6 | s2's surge plus a one-slot actuation delay throughout and a controller outage (45-50) |

## Metrics (from the ground truth of the slot after each decision)

* **violation slots** - slots with link overload (offered > capacity) or a slice's
  true p99 latency above its intent bound (URLLC 1 ms, eMBB 40 ms, mMTC 20 ms).
* **overload slots**; reservation-limit slots (true load > 0.9 · capacity).
* **fallback slots**, **uncertified fallback** (π₀ applied although π₀ itself failed
  the shield: Assumption 3 failed in that state).
* **candidate rejection rate** (shielded only); **verify ms p95** (shield time per slot).
* eMBB throughput delivered; recovery slots after the first disturbance.

## Reproducing

```bash
scripts/run_experiments.sh --scenarios experiments/scenarios/s*.yaml --seeds 1-5 --fallback-policy capacity_aware
```
```bash
scripts/run_experiments.sh --scenarios experiments/scenarios/s*.yaml --seeds 1-5 --fallback-policy static
```

Each run writes `manifest.json` (commit, dirty flag, config hash, scenario digests,
seeds, command), raw per-slot `steps.jsonl` and summaries. Raw results stay under
the gitignored `experiments/results/`; summaries and manifests of the runs reported
here are in `experiments/reports/2026-10-21-{static,capacity_aware}/` (commit
`4ce9616`, clean tree). Re-running at that commit reproduces the same outcomes
(checked); only timing fields differ.

## Results - 2026-10-21 campaign (5 seeds, mean ± std)

Rows are with the capacity-aware π₀(s) (the default); the last row of each table is
the shielded controller with the static π₀, for the ablation.

#### s1_steady

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 0.0 ± 0.0 | 0.0 ± 0.0 | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 3.0 ± 0.3 | 80.3 |
| shielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.50 ± 0.01 | 21.6 ± 2.0 | 80.3 |
| unshielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 2.7 ± 0.2 | 80.3 |
| unshielded-fitted | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 3.3 ± 0.4 | 80.3 |
| *shielded, static π₀* | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.50 ± 0.01 | 19.8 ± 0.9 | 80.3 |

#### s2_background_on_embb_path

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 0.8 ± 0.4 | 0.0 ± 0.0 | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 2.9 ± 0.2 | 73.0 |
| shielded | 0.8 ± 0.4 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.63 ± 0.01 | 23.6 ± 2.0 | 73.0 |
| unshielded | 16.4 ± 1.1 | 11.2 ± 1.1 | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | – | 2.9 ± 0.6 | 79.8 |
| unshielded-fitted | 0.8 ± 0.4 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 3.0 ± 0.3 | 73.0 |
| *shielded, static π₀* | 16.4 ± 1.1 | 11.2 ± 1.1 | 20.0 ± 0.0 | 20.0 ± 0.0 | 0.0 ± 0.0 | 0.67 ± 0.01 | 20.9 ± 2.3 | 79.8 |

#### s3_background_on_urllc_path

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 0.0 ± 0.0 | 0.0 ± 0.0 | 60.0 ± 0.0 | 20.0 ± 0.0 | 0.0 ± 0.0 | – | 3.0 ± 0.3 | 80.3 |
| shielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | 20.0 ± 0.0 | 0.0 ± 0.0 | 0.67 ± 0.01 | 22.7 ± 0.8 | 80.3 |
| unshielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | – | 3.4 ± 0.8 | 80.3 |
| unshielded-fitted | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | – | 3.5 ± 0.6 | 80.3 |
| *shielded, static π₀* | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | 20.0 ± 0.0 | 0.0 ± 0.0 | 0.67 ± 0.01 | 22.1 ± 1.9 | 80.3 |

#### s4_telemetry_faults

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 0.0 ± 0.0 | 0.0 ± 0.0 | 60.0 ± 0.0 | 13.0 ± 0.0 | 0.0 ± 0.0 | – | 2.6 ± 0.2 | 86.9 |
| shielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.0 ± 0.0 | 13.0 ± 0.0 | 0.0 ± 0.0 | 0.61 ± 0.01 | 20.6 ± 2.1 | 91.0 |
| unshielded | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.0 ± 0.0 | – | 2.7 ± 0.5 | 93.7 |
| unshielded-fitted | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.0 ± 0.0 | – | 2.7 ± 0.4 | 93.3 |
| *shielded, static π₀* | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.0 ± 0.0 | 13.0 ± 0.0 | 0.0 ± 0.0 | 0.61 ± 0.01 | 20.1 ± 1.0 | 91.0 |

#### s5_model_mismatch

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 60.0 ± 0.0 | 0.0 ± 0.0 | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 2.6 ± 0.2 | 80.3 |
| shielded | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.50 ± 0.01 | 20.9 ± 3.9 | 80.3 |
| unshielded | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 4.3 ± 4.0 | 80.3 |
| unshielded-fitted | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 2.6 ± 0.3 | 80.3 |
| *shielded, static π₀* | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.50 ± 0.01 | 22.4 ± 2.1 | 80.3 |

#### s6_actuation_delay_and_failures

| controller | violation slots | overload slots | fallback slots | uncertified fallback | applied, shield would reject | candidate rejection rate | verify ms p95 | eMBB Mbit/s |
|---|---|---|---|---|---|---|---|---|
| fallback-only | 1.6 ± 0.5 | 0.4 ± 0.5 | 60.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 3.5 ± 0.6 | 72.9 |
| shielded | 1.6 ± 0.5 | 0.4 ± 0.5 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.63 ± 0.01 | 21.9 ± 1.9 | 72.9 |
| unshielded | 16.4 ± 1.1 | 11.2 ± 1.1 | 0.0 ± 0.0 | 0.0 ± 0.0 | 20.0 ± 0.0 | – | 3.6 ± 0.4 | 79.8 |
| unshielded-fitted | 1.6 ± 0.5 | 0.4 ± 0.5 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | – | 3.2 ± 0.6 | 72.9 |
| *shielded, static π₀* | 16.4 ± 1.1 | 11.2 ± 1.1 | 20.0 ± 0.0 | 20.0 ± 0.0 | 0.0 ± 0.0 | 0.67 ± 0.01 | 21.1 ± 2.4 | 79.8 |

## Findings

1. **RQ0 - cost.** In steady conditions all controllers behave identically. The shield
   rejects about half of the candidates (mostly naive or random ones) and needs
   about 20 ms (p95) per slot to verify ~9 candidates, against a 1 s slot.
2. **RQ1/RQ6 - background surge.** With the static π₀, the shielded controller was no
   better than no shield (16.4 violation slots): π₀ itself was infeasible, so no
   candidate could be certified and the infeasible π₀ was applied in all 20 surge
   slots. With π₀(s) it dropped to 0.8, with no uncertified fallbacks.
3. **The shield did not beat a good heuristic.** With π₀(s), the shielded controller
   performed exactly like the unshielded capacity-fitted controller in every
   scenario - and in s2 so did fallback-only with π₀(s) (0.8 violation slots each).
   The safety gain comes from the capacity-aware decision rule; the shield matched it
   but added nothing measurable on top. Its value here is that it made the greedy
   generator's proposals as safe as a well-designed heuristic, which is the paper's
   premise; these experiments show no advantage over such a heuristic. The price is
   eMBB throughput (73.0 vs 79.8 Mbit/s for the unshielded greedy controller, which
   in exchange overloaded the link in 11 slots).
4. **Reaction lag.** The remaining ~1 violation slot in s2 is the surge's first slot,
   decided before the surge was observable. Any reactive controller pays it.
5. **RQ2 - over-conservatism.** In s3 no controller violated anything, yet the shield
   fell back in 20 slots and π₀ was uncertifiable: the nominal model (safety factor
   1.5) predicts URLLC above 1 ms while the simulated truth stays below.
6. **RQ3 - stale data.** In s4 the shield refused to act for 13 slots of frozen or
   missing telemetry. Nothing was violated in any mode; the refusal cost about 3 %
   eMBB throughput.
7. **RQ4 - model mismatch.** In s5 every controller violated the URLLC intent in all 60
   slots, and the shield certified those actions: **"certified" did not mean safe**
   when the model was wrong. Calibration (Milestone 3) or runtime monitoring is needed.
8. **RQ5 - delay and outage.** One slot of actuation delay added about one violation
   slot per surge; with π₀(s) the shield again matched the strong baseline.

## Results - 2026-10-22 campaign (after the telemetry and metric fixes)

**Setup.**
* Commit `e46f9b1`, clean tree; simulated backend.
* 6 scenarios × 5 controllers: the four above plus `shielded-utility` (paper Eq 42,
  D20).
* Seeds 1-5 (`experiments/reports/2026-10-22-main/`) and held-out seeds 6-10
  (`2026-10-22-heldout/`).
* Ablation on the held-out seeds with the calibrated latency safety factor
  (`2026-10-22-heldout-k1.109/`) for the shielded, shielded-utility and
  fallback-only controllers.

Seeds 1-5, mean over seeds (std as in the reports). "reserved" is the mean total
rate budget of the applied actions (new metric).

| scenario | controller | violation slots | uncertified fallback | reserved Mbit/s | eMBB Mbit/s |
|---|---|---|---|---|---|
| s1 | shielded / shielded-utility | 0 / 0 | 0 / 0 | 155 / 105 | 80.3 / 80.3 |
| s1 | unshielded / unshielded-fitted / fallback-only | 0 / 0 / 0 | 0 / 0 / 0 | 155 / 105 / 110 | 80.3 |
| s2 | shielded / shielded-utility | 0.8 / 0.8 | 0 / 0 | 125 / 91.2 | 73.0 / 73.0 |
| s2 | unshielded / unshielded-fitted / fallback-only | 16.4 / 0.8 / 0.8 | 0 / 0 / 0 | 155 / 91.3 / 96.2 | 79.8 / 73.0 / 73.0 |
| s3 | shielded / shielded-utility | 0 / 0 | 20 / 20 | 140 / 107 | 80.3 |
| s3 | unshielded / unshielded-fitted / fallback-only | 0 / 0 / 0 | 0 / 0 / 20 | 155 / 105 / 110 | 80.3 |
| s4 | shielded / shielded-utility | 0 / 0 | 13 / 13 | 145 / 116 | 91.0 / 90.6 |
| s4 | unshielded / unshielded-fitted / fallback-only | 0 / 0 / 0 | 0 / 0 / 13 | 155 / 112 / 110 | 93.7 / 86.7 / 86.9 |
| s5 | all five | 60 | 0 | 105-155 | 80.3 |
| s6 | shielded / shielded-utility | 1.6 / 1.6 | 0 / 0 | 125 / 91.2 | 72.9 |
| s6 | unshielded / unshielded-fitted / fallback-only | 16.4 / 1.6 / 1.6 | 0 / 0 / 0 | 155 / 91.3 / 96.2 | 79.8 / 72.9 / 72.9 |

**Findings.**
1. **The fixes did not change the shielded results.** Violation, fallback and
   rejection figures of the shielded, unshielded and fallback-only controllers equal
   the 2026-10-21 campaign. One baseline changed: in s4 `unshielded-fitted` now
   delivers 86.7 instead of 93.3 Mbit/s eMBB, with no violation either way. Its
   generator no longer reads frozen or missing demand and background as 0 (D21 in
   DECISIONS: unknown demand keeps π₀'s budget).
2. **Eq 42 selection (RQ7).** In every scenario `shielded-utility` had exactly the
   same violations, fallbacks and delivered throughput as first-certified, but
   reserved 20-32 % less bandwidth: e.g. s1 155 → 105 and s2 125 → 91.2 Mbit/s.
   It picks `demand-matched` where first-certified takes `greedy-embb`. In this
   simulator a budget above demand does not change the outcome, so the gain is
   only the reservation. The weights are illustrative, so the choice among
   certified candidates depends on them.
3. **Calibration (Milestone 3, simulator).**
   * The recorded/analytic latency ratio has median 1.00 and p99 1.11 for every
     slice in the nominal scenarios, so the configured factor 1.5 is about 35 %
     over-conservative there.
   * k = 1.109, fitted on seeds 1-5 of s1-s4 and s6, covers 98.3 % of the held-out
     points in each of those scenarios (target 99 %).
   * On the held-out seeds it removed all 20 uncertified fallbacks in s3, with no
     new violation, and changed nothing else (`2026-10-22-heldout-k1.109`).
   * It does **not** fix s5: coverage 40 % (configured 1.5: 65 %). A structural
     model error is not a scale error.
4. **Calibration (Mininet, provisional).** On the 2026-10-22 Mininet campaign the
   ratio's median is below 1 (URLLC 0.76) but its tail is heavy (URLLC p99 2.9,
   max 19), so 99 % coverage would need k = 1.86. That data carries known telemetry
   errors and latency is the max of 8 pings
   (`experiments/reports/2026-10-22-calibration-mininet-provisional/`).
   The simulator and the emulator disagree, so **the configured k = 1.5 is kept**
   (DECISIONS, 2026-10-22).

## Limitations of these results

* Simulation only, except the provisional Mininet campaign. The simulator's
  fidelity is unvalidated.
* One topology, one demand mix, five seeds per campaign; standard deviations are
  across seeds only.
* Eq 42 uses illustrative weights and the uncalibrated T̂; a higher predicted return
  is not a measured benefit.
* The sim calibration is fitted to this project's own simulator; it shows the
  method and its held-out check, not the right factor for a real network.
* Thresholds and scales are illustrative, not 6G requirements.

## Emulated network runs (Mininet) - integration green, first campaign provisional

`sudo scripts/mininet_run.sh` runs the root-only integration tests twice (connectivity,
routes, meter placement and policing, background accounting, probe latency, reroute
timing, cleanup after a failed setup, a closed-loop smoke test; each followed by a
leak check). `sudo scripts/mininet_run.sh --campaign` then adds, only if every pass
is green, a campaign of s1-s3 × 4 controllers × 3 seeds (about 40 minutes). Output
goes to `experiments/results/mininet-<UTC>/`.

**Run 1, 2026-10-21 17:10 UTC (`mininet-20261021T171037Z`): 7 of 7 integration tests
failed; no campaign.** Environment: WSL2 kernel 6.6.87.2, Mininet 2.3.0, OVS 3.3.9,
iperf3 3.16. The first test failed with `OFPMMFC_INVALID_METER` (flows installed
before their meter). The other six failed with `RTNETLINK answers: File exists`,
because the first test's half-built network was never closed. The many
`sch_htb: quantum of class 50001 is big` lines are a benign tc warning (HTB quantum
at ≥16 Mbit/s rates with the default r2q), not a failure. Root causes and fixes:
[DECISIONS.md](DECISIONS.md), "Install order and lifecycle of the emulated network".
These runs measure nothing about the controller; they only show the emulation was
not yet usable.

**Run 2, 2026-10-21 17:22 UTC (`mininet-20261021T172242Z`), commit `692ba3b`,
clean tree, same environment: 9 of 9 integration tests passed in both passes**
(69.73 s and 69.44 s, no cleanup in between): every slice reaches its receiver,
routes follow the installed path, meters police the budget, background is measured
and slices excluded, probe latency matches link delays, reroute within one slot,
meters exist on the ingress only, a failed setup leaves nothing behind, and a
shielded closed-loop smoke test (8 slots). After the last pass, 0 switch interfaces
and 0 harness iperf3 processes remained. Campaign not requested; **no campaign
results exist**. The tests' tolerances are loose (e.g. ±20 % on policing, ±15 % on
background), so this validates the plumbing, not measurement precision.

**Campaign 1, 2026-10-22 11:08 UTC (`mininet-20261022T110546Z/campaign`), commit
`b78e247`, clean tree:** s1-s3 × 4 controllers × 3 seeds, all 36 trials complete. Its
summary is **not reported as a result**. A read-only audit found telemetry errors:
* reroute counter resets (NaN or wrong deltas; eMBB throughput `null` in s2);
* background under-measured behind the ingress meter (about 101 vs about 124 Mbit/s
  on l13, which explains the s2 reservation-limit slots for every controller);
* stepwise flow-counter updates (most per-slot loss values are artifacts);
* the meter passing about 1.10× its budget;
* payload versus frame units.

Latency is the maximum of 8 pings and `overload_slots` cannot see overload here.
Details and slot IDs: docs/STATUS.md. The dashboard's *Saved campaigns* tab shows it
with these caveats.

**Campaign 2, 2026-10-22 17:09 UTC (`mininet-20261022T170942Z`), commit `074e46f`
(telemetry fixes), clean tree.**
* Integration suite 9/9 twice, no leftovers.
* s2 × 5 controllers × seeds 1-3, all 15 trials complete.
* Summary: `experiments/reports/2026-10-22-mininet-s2-after-fixes/`.

**What it validated:**
* **No missing values** (provisional campaign: 65). Measured background on l13
  during the surge has median 123.5 Mbit/s against 123.6 expected (before: 102).
  The reinstall-safe rates and the post-meter background work on the real switch.
* **Fewer shielded fallbacks:** uncertified fallbacks fell to 0.67 / 0.33 per trial
  for shielded / shielded-utility (before: 2 per trial). Mean eMBB throughput is
  available for every trial (75.7-82.0 Mbit/s).

**What it showed is still wrong:**
* **Reservation-limit slots stay at 18-20 for every controller.** Cause: the
  capacity-fitted budgets fill l13 to exactly 0.900, but the OVS meter delivers a
  median 1.10× its budget (191 metered slots, range 1.08-1.20). The link therefore
  runs at 0.928. Background accounting is no longer involved.
* **Stale rule counters.** OVS copies rule counters from the datapath every
  max-revalidator = 500 ms, so a dump can be half a slot old. Offered load read
  about 0.5×/1.5× in 47 slots, and background jumped (151.7 Mbit/s at t=37 in
  shielded seed 1 while the link rate was unchanged). Acting on such readings,
  π₀(s) moved eMBB onto path C (mMTC 32.7 ms) and then path A (URLLC 27.6 ms).
  These are the shielded runs' violations. Fixed afterwards: snapshots call
  `ovs-appctl revalidator/wait` first. That is not yet run on Mininet.
* **Unshielded:** 22.7 applied actions per trial were ones the shield would have
  rejected; 1.33 violation slots.

These are emulated measurements; the violation counts (0.33-1.33 per trial) are
too few to rank controllers.

**Campaign 3, 2026-10-22 17:47 UTC (`mininet-20261022T174731Z`), commit `dde4fe4`
(current rule counters), clean tree.**
* Integration suite 10/10 twice, including the new steady-counter test.
* s2 × 5 controllers × seeds 1-3, all 15 trials complete.
* Summary: `experiments/reports/2026-10-22-mininet-s2-counter-refresh/`.

**What changed:**
* eMBB offered-load misreadings 47 → 0;
* spurious eMBB reroutes 6 → 0;
* uncertified fallbacks 3 → 0;
* missing values stay 0;
* l13 background median 123.5 Mbit/s (expected 123.6).

| s2, mean over 3 seeds | shielded | shielded-utility | unshielded | unshielded-fitted | fallback-only |
|---|---|---|---|---|---|
| violation slots | 0 | 1.0 | 2.3 | 0.33 | 0.33 |
| applied, shield would reject | 0 | 0 | 20 | 0 | 0 |
| reservation-limit slots | 19 | 19 | 18.3 | 19 | 19.3 |
| reserved Mbit/s (mean) | 127 | 96.8 | 158 | 96.9 | 95.9 |
| eMBB delivered Mbit/s (frames) | 77.0 | 77.0 | 82.4 | 77.1 | 77.0 |

**Reading:**
* The shielded modes' remaining violations are isolated one-slot URLLC spikes on an
  idle path A, consistent with ping noise (max of 8 probes).
* The unshielded controller, as in simulation, applied 20 actions per trial that the
  shield would have rejected, and drove path B to 0.87-0.98 utilization (eMBB up to
  50 ms).
* Eq 42 again reserved about 24 % less bandwidth than first-certified at equal
  outcomes.
* Reservation-limit slots remain for every controller because of the meter's ~1.10×
  overshoot (decision pending).
* Overload is not observable here. Three seeds per controller are too few to rank
  the controllers that rarely violate.

Differences from the simulator, by design of the emulation:
* values are **measurements**, not ground truth (counters, ping probes);
* offered load is constant within a demand window (no per-slot demand noise);
* admission control is emulated by scaling the sender's rate;
* background traffic follows one path at a time;
* telemetry faults (s4) and controller faults (s6) are injected by the backend, as
  in the simulator; model mismatch (s5) arises from the configured packet sizes.
