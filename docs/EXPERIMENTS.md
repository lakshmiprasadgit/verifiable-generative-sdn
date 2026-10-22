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

## Limitations of these results

* Simulation only; the simulator's fidelity is unvalidated until the Mininet runs.
* One topology, one demand mix, five seeds; standard deviations are across seeds only.
* The selection rule is "first certified", not the paper's Eq 42.
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

Differences from the simulator, by design of the emulation:
* values are **measurements**, not ground truth (counters, ping probes);
* offered load is constant within a demand window (no per-slot demand noise);
* admission control is emulated by scaling the sender's rate;
* background traffic follows one path at a time;
* telemetry faults (s4) and controller faults (s6) are injected by the backend, as
  in the simulator; model mismatch (s5) arises from the configured packet sizes.
