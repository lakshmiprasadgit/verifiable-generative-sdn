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
| 1 | state/action schemas, hard constraints, STL robustness, verification shield | implemented with unit tests; audit findings open (see below) |
| 2 | Mininet topology, SDN controller | not started |
| 3 | traffic, telemetry, nominal-model calibration | not started |
| 4 | fallback, heuristic candidates, selection, closed loop | not started |
| 5 | experiments, metrics, reports | not started |

## Layout

```
research/   the paper (specification; kept locally, not tracked)
docs/       design notes and research-to-code traceability
configs/    network, constraints, intents (STL), shield settings - all thresholds live here
src/vgcp/   package: state, action, constraints, stl/, models/, shield, config
tests/unit/ unit tests (no Mininet, no root)
scripts/    environment setup and test runners
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

Read first: [docs/milestone1_design.md](docs/milestone1_design.md) and
[docs/traceability.md](docs/traceability.md).

## Known limitations and open audit findings

An independent audit of Milestone 1 found issues; three are fixed:

* **C1 (fixed)** - non-finite measurement timestamps no longer pass freshness checks.
* **H2 (fixed)** - unknown or misspelled configuration keys and non-string
  identifiers are rejected at load time.
* **M3 (partially addressed)** - actions are immutable after construction and each
  certificate records the certified action (with a canonical fingerprint) and
  fingerprints of its inputs; `Certificate.authorizes()` fails closed. No
  production apply step consumes certificates yet, so authorization is not
  enforced until the closed loop exists (Milestone 4). The input context is
  recorded but not checked.

Unresolved:

* **H1** - the capacity constraint and nominal model ignore measured link load
  (a saturated link can still be certified).
* **H3** - with intents evaluated from the measured state, the fallback policy is
  rejected whenever the current measurement already violates an intent, so the
  paper's recursive-feasibility assumption cannot hold in such states.
* **M1** - the Eq 17 grid test reuses the shield's own components and checks the
  extended feasible set, not an independent restatement of Eq 17.
* **M2** - the out-of-distribution threshold is applied to the nominal model's
  validity flag, not to the learned world model's uncertainty (paper Def 2).
* **M4** - robustness values in different units are compared through one
  minimum; per-intent margins do not fix this for the paper's utility terms.
* **M5** - intents on signals the nominal model does not predict (e.g. loss)
  are vacuous over the rollout.

Other limitations: the nominal model is uncalibrated and not shown to be
conservative; the fallback policy's recursive feasibility is not checked; shield
acceptance means feasibility with respect to the model and configured
constraints, not safety of the real network.
