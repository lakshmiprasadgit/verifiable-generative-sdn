# Verifiable Generative Control Plane for 6G SDN - Stage 1 prototype

The specification is the research paper `research/problem_formulation_corrected.pdf`.
The paper is not included in this repository (its distribution rights are not yet
confirmed); obtain it from the authors.

Stage 1 builds the paper's shielded control loop on a Mininet / Open vSwitch
prototype, using conventional heuristics and an analytical nominal model in place
of the generative policy and learned world model.

This is a research prototype. It is not formally verified and makes no
production-readiness or real-network safety claims.

## Status

| Milestone | Content | Status |
|---|---|---|
| 1 | state/action schemas, hard constraints, STL robustness, verification shield | done; all audit findings addressed (see below) |
| 2 | closed loop, simulated and Mininet backends, experiments | in progress (see docs/STATUS.md) |
| 3 | traffic, telemetry, nominal-model calibration | not started |
| 4 | fallback, heuristic candidates, selection, closed loop | not started |
| 5 | experiments, metrics, reports | not started |

## Layout

```
research/   the paper (specification; kept locally, not tracked)
docs/       design notes and research-to-code traceability
configs/    network, constraints, intents (STL), shield settings - all thresholds live here
src/vgcp/   package: state, action, constraints, stl/, models/, shield, config,
            loop/, sim/, emu/ (Mininet), experiments/, demo/ (dashboard)
tests/unit/ unit tests (no Mininet, no root)
scripts/    environment setup, test runners, run_dashboard.sh
experiments/ (Milestone 5)
```

## Prerequisites

* Linux (developed on Ubuntu 24.04 under WSL2) with the system Python 3.12
  (`/usr/bin/python3`) and PyYAML (`python3-yaml`).
* A `pip` to install the test dependencies into the virtual environment (see
  `scripts/setup_venv.sh`; it falls back to an external pip if `python3.12-venv`
  is not installed).
* Unit tests need no root, Mininet or Open vSwitch. Those are needed from
  Milestone 2 onward.

## Setup and tests

```bash
scripts/setup_venv.sh
```
```bash
scripts/run_unit_tests.sh
```

Property-based tests (Hypothesis) are deterministic by default, so every run uses
the same examples. To search with fresh random examples instead:

```bash
HYPOTHESIS_PROFILE=explore scripts/run_unit_tests.sh
```

Current status: [docs/STATUS.md](docs/STATUS.md). Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Decisions: [docs/DECISIONS.md](docs/DECISIONS.md). Experiments and results: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

Closed-loop experiments (simulated network, no root):

```bash
scripts/run_experiments.sh --scenarios experiments/scenarios/s*.yaml --seeds 1-5
```

Read first: [docs/milestone1_design.md](docs/milestone1_design.md) and
[docs/traceability.md](docs/traceability.md).

## Control-loop dashboard

A browser dashboard that runs the real controller, shield and simulated network one
control slot at a time (`src/vgcp/demo/`, Python standard library only, no root).

```bash
scripts/run_dashboard.sh
```

Then open <http://127.0.0.1:8765/> (from Windows with WSL2, the same URL works).
Use `--port N` for another port; stop the server with Ctrl+C.

**Controls.** Pick a scenario, controller and seed, then *Start new run*. *Step*
runs one slot; *Play* / *Pause* runs at the chosen speed (ms per slot); *Reset*
restarts the same configuration. Click a candidate row to see its certificate
checks. *Saved campaigns* shows earlier campaign summaries, labelled as historical.
A link such as `/?scenario=s3_background_on_urllc_path&controller=shielded&steps=25`
starts a run and steps it automatically.

**What it shows.** Topology from `configs/network.yaml` with each slice's installed
path. The seven loop stages per slot. Every candidate with its verification result
and failed check, and the decision: CERTIFIED ACTION, CERTIFIED FALLBACK,
**UNCERTIFIED FALLBACK**, UNVERIFIED (baseline) or NOT APPLIED. Outcome metrics,
the observation the controller actually used, an event timeline and an end-of-run
summary computed by the experiment runner's own `summarize()`. A dashboard run
produces the same records as `run_trial` with the same settings (tested).

**Limitations.**
* Live runs use the simulated network. Its outcome values are the simulator's
  ground truth, not real-network measurements.
* The Mininet backend is offered only when the server runs as root. The dashboard
  never calls `sudo`; use `sudo scripts/mininet_run.sh` for Mininet runs.
* Mininet campaign data in *Saved campaigns* is provisional (see
  docs/EXPERIMENTS.md):
  * overload is not observable;
  * latency is the max of 8 probes;
  * counter-derived throughput, loss and background have known errors.
* Missing values are shown as unavailable and never as zero.
* Nothing shown establishes real-network safety.

## Known limitations and open audit findings

An independent audit of Milestone 1 found issues; all are addressed:

* **C1 (fixed)** - non-finite measurement timestamps no longer pass freshness checks.
* **H2 (fixed)** - unknown or misspelled configuration keys and non-string
  identifiers are rejected at load time.
* **M3 (partially addressed)** - actions are immutable after construction and each
  certificate records the certified action (with a canonical fingerprint) and
  fingerprints of its inputs; `Certificate.authorizes()` fails closed. No
  production apply step consumes certificates yet, so authorization is not
  enforced until the closed loop exists (Milestone 4). The input context is
  recorded but not checked.
* **M1 (fixed)** - the evidence for Eq 17 is now a hand-calculated instance, a
  naive independent transcription of the STL robustness equations, and a literal
  Eq 17 reference that checks the shield is sound (accepts only Eq 17 actions),
  with every difference attributed to a documented extension.
* **M2 (fixed)** - the paper's out-of-distribution threshold (Def 2) is no longer
  misapplied to the nominal model. The nominal model reports an explicit validity
  flag (extension D12); Def 2 awaits a learned world model.
* **H1 (fixed)** - traffic outside the managed slices is measured per link
  (`background_load_mbps`) and counted by the capacity constraint and the nominal
  model. Milestone 2 must provide it (port rate minus managed flow rates).
* **H3 (fixed)** - intents are recovery-style (`G[1,10] p`): the measured slot is
  excused, so the fallback can be certified while recovering from a measured
  violation, and the candidate's effect is still checked. Certificates list
  measured violations. The measurement-only loss intent is disabled.
* **M4 (fixed)** - predicates are normalized by a declared scale per signal
  family, so robustness is unitless and one global rho_min applies, as in Eq 17.
  Per-intent margins are retired.
* **M5 (fixed)** - an intent may not read, over the rollout, a signal the nominal
  model does not predict (loss, flow-table occupancy); the shield refuses such
  configurations. The mMTC loss intent is now a current-measurement check.
* **Low-severity findings L1-L8** - addressed: disabled checks are reported as
  not applicable (L1); oversized numbers and deeply nested formulas give clear
  errors (L2); the traceability table and decision register are complete (L3);
  property tests are deterministic (L4); intents declare the slot length they
  were written for (L6); names no longer claim "conservative" (L7). L5 (the
  utilization bound versus real counter jitter) and L8 (exact floating-point
  comparison at rho_min) are documented; L5 is revisited with real data in
  Milestone 3.

No audit finding remains open; M3's enforcement waits for the Milestone 4 apply step.

Other limitations: the nominal model is uncalibrated and not shown to be
conservative; the fallback policy's recursive feasibility is not checked; shield
acceptance means feasibility with respect to the model and configured
constraints, not safety of the real network.
