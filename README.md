# Verifiable Generative Control Plane for 6G SDN - Stage 1 prototype

A research prototype of a **shielded SDN control loop**. A controller proposes
network actions (routing, rate budgets, admission limits, link power). A
**verification shield** checks each proposal against hard constraints and
temporal-logic (STL) intents over a predicted horizon. Only certified actions
reach the network; otherwise a fallback policy is applied.

* **Specification:** the research paper `research/problem_formulation_corrected.pdf`.
  It is **not in this repository** (distribution rights unconfirmed); ask the
  authors for it.
* **Stage 1 stand-ins:** conventional heuristics replace the paper's generative
  policy G_θ, and an analytic model T̂ replaces its learned world model W_ψ.
* **Not a safety claim:** this is not formally verified, not production-ready,
  and makes no real-network safety claim. A certificate means "acceptable under
  the nominal model and the configured constraints", nothing more.

This README has two audiences: **[Part A](#part-a---for-team-members)** for people
on the team, **[Part B](#part-b---for-ai-agents-and-automation)** for coding agents
and automation. Both share the status table and the quick start.

## Status (2026-10-22)

| Milestone | Content | Status |
|---|---|---|
| 1 | state/action schemas, hard constraints, STL robustness, verification shield | **done** - all audit findings addressed; certificates are enforced by `CertifiedApplier` |
| 2 | closed loop, simulated and Mininet backends, experiments | **done in code** - loop, simulator, Mininet backend (integration 9/9 twice), telemetry fixes from the Mininet audit. **Open:** re-run on Mininet (root) |
| 3 | traffic, telemetry, nominal-model calibration | **done (method and simulator evidence)** - calibration tool with held-out evaluation. **Open:** fit on fixed Mininet data; the configured factor is unchanged until then |
| 4 | fallback, heuristic candidates, selection, closed loop | **done** - π₀(s), heuristic candidates, enforced loop, Eq 42 utility selection (`shielded-utility`). **Open:** recursive feasibility (Assumption 3) is not shown |
| 5 | experiments, metrics, reports | **done for simulation** - 2026-10-22 campaigns (5 controllers, main and held-out seeds, calibration ablation) in `experiments/reports/`; dashboard. **Open:** Mininet campaign after the fixes |

Details and evidence: [docs/STATUS.md](docs/STATUS.md). Work happens on the branch
`feat/m2-mininet-backend`, which is not yet merged into `main`.

## Quick start (no root needed)

```bash
scripts/setup_venv.sh
```
```bash
scripts/run_unit_tests.sh
```
```bash
scripts/run_dashboard.sh
```

Then open <http://127.0.0.1:8765/>. From Windows with WSL2, the same URL works.

---

## Part A - For team members

### The idea in one minute

Each control slot (1 s) the loop does:

1. **Observe** - read telemetry into a state s_t: per-slice latency and throughput,
   link utilization, background traffic, offered demand.
2. **Propose** - a candidate generator suggests several actions. Today these are
   heuristics, e.g. "give eMBB the most bandwidth" or "fit eMBB into free capacity".
3. **Verify** - for each candidate, the shield checks:
   * the measurements are present and fresh;
   * the hard constraints hold now (capacity incl. background, flow tables, budgets, routing);
   * a 10-step prediction with the nominal model stays within constraints and
     satisfies the STL intents with margin ρ_min.
4. **Certify** - a passing candidate gets a certificate bound to that exact action
   and observation.
5. **Select** - apply the first certified candidate. If none is certified, apply the
   fallback π₀(s) (paper Remark 1).
6. **Apply** - only through `CertifiedApplier`, which refuses any action whose
   certificate does not match.
7. **Measure** - the next slot shows what actually happened.

### Words you will meet

| Term | Meaning here |
|---|---|
| Slice | URLLC (1 ms latency bound), eMBB (40 ms, high throughput), mMTC (20 ms, many devices) |
| Path A / B / C | A: 2 hops, 50 Mb/s, 0.1 ms per link. B: 2 hops, 200 Mb/s, 5 ms per link. C: 3 hops, 50 Mb/s, 2 ms per link (`configs/network.yaml`) |
| Intent | An STL formula, e.g. `G[1,10](latency_p99_ms.urllc <= 1.0)`: "for each of the next 10 slots, URLLC p99 latency ≤ 1 ms" |
| Robustness ρ | How much margin a prediction has to an intent (normalized); a candidate needs ρ ≥ 0.05 |
| Certificate | The shield's record: which checks passed, for which action and which observation |
| Fallback π₀(s) | The conservative action used when nothing is certified; it resizes eMBB to fit measured background |
| Uncertified fallback | π₀(s) was applied but the shield could not certify it either. **Not shown to be safe** |
| Nominal model T̂ | The shield's simple prediction model (uncalibrated) |
| Simulator | A separate "world" with its own physics, so the shield can be wrong; used for experiments without root |
| Mininet backend | A real emulated network (Open vSwitch, real queues and traffic); needs root |
| Eq 42 / utility | Among certified candidates, prefer the one with the best predicted mix of throughput, energy, margin and reserved bandwidth over the next 10 slots (`shielded-utility`) |
| Calibration | Fitting the model's latency safety factor to recorded latency, then checking it on runs it was not fitted on |

### Try it: the dashboard

Run `scripts/run_dashboard.sh` and open <http://127.0.0.1:8765/>.

1. Choose scenario `s3_background_on_urllc_path`, controller `shielded`, seed 1, then
   **Start new run** and **Play**. A full run takes about 35 s.
2. In slots 0-19 you will see certified actions, with some candidates rejected.
3. From slot 20, background traffic loads path A. Nothing can be certified, and the
   decision panel shows **UNCERTIFIED FALLBACK**. Open the π₀(s) certificate: the
   URLLC latency intent fails with too little margin.
4. Try `s4_telemetry_faults` around slots 40-45: missing telemetry is shown as
   *missing* (never 0), and the shield refuses to certify.
5. Switch the controller to `unshielded` to see actions applied without
   verification, and what the shield would have said.

**Controls.**
* *Step* runs one slot; *Play* / *Pause* run continuously at the chosen ms per slot;
  *Reset* restarts the same configuration.
* Click a candidate row to see its checks.
* *Saved campaigns* shows earlier results, labelled as historical.
* A link like `/?scenario=s3_background_on_urllc_path&controller=shielded&steps=25`
  starts a run and steps it automatically.

Live runs use the **simulated** network. The Mininet backend appears only if the
dashboard server itself runs as root; the dashboard never calls `sudo`.

### Running experiments

Simulated network, no root (writes to `experiments/results/<UTC>/`):

```bash
scripts/run_experiments.sh --scenarios experiments/scenarios/s*.yaml --seeds 1-5
```

Emulated network, needs root. It runs the 9 integration tests twice. With
`--campaign` it also runs s1-s3 × 5 controllers × 3 seeds (about 52 minutes); add
`--only s2_background_on_embb_path` for one scenario (about 17 minutes):

```bash
sudo scripts/mininet_run.sh
```

Calibrate the nominal model's latency factor from a campaign (no root). This fits on
seeds 1-5 and reports coverage on a held-out campaign:

```bash
PYTHONPATH=src .venv/bin/python -m vgcp.experiments.calibrate --campaign experiments/results/<main> --train-seeds 1-5 --test-campaign experiments/results/<heldout> --out experiments/reports/<name>
```

Controllers: `shielded` (first certified candidate), `shielded-utility` (paper
Eq 42: the certified candidate with the highest predicted utility), `unshielded`,
`unshielded-fitted` (strong heuristic baseline), `fallback-only`.

### What the results do and do not say

* **Simulation:**
  * With π₀(s), the shield matched, but did not beat, a good conventional heuristic.
  * Eq 42 selection kept the same outcomes while reserving 20-32 % less bandwidth.
  * The configured model is over-conservative (s3). A simulator-calibrated factor
    removed s3's uncertified fallbacks on held-out seeds.
  * A wrong model (s5) defeated every controller, and calibration did not help.
* **Mininet integration:** the plumbing works (routes, meters, probes, cleanup).
* **Mininet campaign (2026-10-22):** provisional. An audit found measurement
  errors:
  * flow counters reset on reroute;
  * background is under-measured when the ingress meter drops traffic;
  * counter steps distort offered load and loss;
  * latency is the maximum of only 8 pings;
  * overload cannot be observed after shaping.

  The first two and the metric handling were fixed and confirmed by a Mininet
  re-run of s2. That re-run isolated two remaining causes: stale counters (fixed in
  code since) and the meter overshoot (open). Do not quote either campaign's
  violation counts as results.
* **Nothing here** establishes real-network safety.

### Where to read more

| Document | What it gives you |
|---|---|
| [docs/STATUS.md](docs/STATUS.md) | current state, test evidence, next step |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | components and the boundaries between them |
| [docs/DECISIONS.md](docs/DECISIONS.md) | each design decision: problem, alternatives, choice, uncertainty |
| [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) | scenarios, metrics, results and their limits |
| [docs/milestone1_design.md](docs/milestone1_design.md), [docs/traceability.md](docs/traceability.md) | paper equations → code, decision register D1-D19 |

### Contributing

* Work on a feature branch, run `scripts/run_unit_tests.sh` before you push, and
  open a pull request. `main` only gets reviewed, validated branches.
* All thresholds live in `configs/`. Change them there, deliberately, and record why
  in docs/DECISIONS.md.
* Never commit the paper or anything else under `research/`.

---

## Part B - For AI agents and automation

Read this section completely before changing anything.

### Hard rules

1. **Never commit `research/`**, including `research/problem_formulation_corrected.pdf`.
   Stage files explicitly; never `git add .` or `git add -A`.
2. **No force-push, no history rewriting, no merge into `main`** without an explicit
   review request from the maintainer. Use feature branches. Commits use the
   repository's local git identity and carry no AI co-author trailers unless the
   maintainer asks for them.
3. **Root:**
   * Never use `sudo` yourself; never store, request or log passwords.
   * Never configure passwordless sudo.
   * For root-only steps (Mininet, OVS), finish all non-root work first, then give
     the maintainer one consolidated command.
4. **Do not weaken verification to make something pass:**
   * no relaxed constraints, thresholds, ρ_min or intents;
   * no skipped checks;
   * no deleted or loosened tests;
   * no changed scenario definitions or fallback policy without an explicit decision
     recorded in docs/DECISIONS.md.
5. **Report honestly.** Say exactly which tests ran and their result. Distinguish:
   * simulated ground truth;
   * emulated measurements;
   * model predictions;
   * assumptions.

   Never invent results. Never present an uncertified action as safe.
6. Do not modify saved results (`experiments/results/`, `experiments/reports/`). Do
   not start long campaigns (the Mininet campaign takes about 52 minutes) unless asked.

### Invariants the code relies on

| Invariant | Where | Guarded by |
|---|---|---|
| `CertifiedApplier` is the only shielded path to `backend.apply()`; π₀ is computed by the applier itself | `src/vgcp/loop/applier.py` | `tests/unit/test_loop.py` |
| Missing or non-finite measurements stay missing (`None`/NaN → UNKNOWN), never 0 | `vgcp/state.py`, `vgcp/shield.py`, `vgcp/demo/session.py` | `test_audit_low`, `test_demo` |
| The shield fails closed: any exception or unknown → not accepted | `vgcp/shield.py` | `test_shield`, `test_certificate_binding` |
| Intents are `G[1,10] p` (H3); `F[0,2] G[0,8]` hid the candidate's effect | `configs/intents.yaml` | `tests/unit/test_recovery_intents.py` |
| Capacity counts measured background (H1) | `vgcp/constraints.py`, `vgcp/models/nominal.py` | `test_background_load` |
| The simulator is not the nominal model (separate code and parameters) | `vgcp/sim/` vs `vgcp/models/` | `test_sim` |
| Meters before flows; a failed setup releases everything | `vgcp/emu/backend.py`, `vgcp/emu/fabric.py` | `test_emu`, `tests/integration/` |
| Dashboard runs equal `run_trial` records (timing aside) | `vgcp/demo/session.py` | `test_demo` |
| Eq 42 ranks only certified candidates; ties keep the generator's order | `vgcp/loop/selection.py` | `test_selection` |
| Flow rates never compare two different rules' counters (rule age); unknown stays unknown | `vgcp/emu/telemetry.py` | `test_emu` (strict fake fabric) |
| Summaries skip missing slots and report counts; overload is `None` on measured data | `vgcp/experiments/runner.py` | `test_experiments` |
| Calibration never edits `configs/`; a factor is adopted only by a recorded decision | `vgcp/experiments/calibrate.py` | `test_calibration` |

### Environment facts

* **Platform:** Ubuntu 24.04 on WSL2; Mininet 2.3.0, Open vSwitch 3.3.9, iperf3 3.16.
* **Virtual environment:** `.venv` is built from `/usr/bin/python3` 3.12 with
  `--system-site-packages` and without pip. `python3.12-venv` is not installed, so
  packages are added with an external pip using `--python .venv/bin/python`.
* **Imports:** run modules with `PYTHONPATH=src`; the scripts already set it.
* **Hypothesis** is deterministic by default; `HYPOTHESIS_PROFILE=explore` for random
  examples.
* **Pushing** (SSH, passphrase-protected key): if no agent is loaded in your shell,
  ask the maintainer to run `ssh-add`. Do not try to bypass it.

### Map of the code

| Path | Contents | Entry point |
|---|---|---|
| `configs/` | topology, constraints, intents, shield settings (strict schema) | `vgcp.config.load_config` |
| `src/vgcp/state.py`, `action.py` | measurements with timestamps, immutable actions, schemas | – |
| `src/vgcp/constraints.py`, `stl/` | c(s,a); STL parser and robustness (Eqs 5-11) | – |
| `src/vgcp/models/` | nominal model T̂, upper-bound forecast, fallback policies, calibration | `vgcp.models.calibration` |
| `src/vgcp/shield.py` | `VerificationShield.verify` → `Certificate` | `VerificationShield.from_config` |
| `src/vgcp/loop/` | candidate generator, controllers, `CertifiedApplier`, Eq 42 selection | `ShieldedController.step(obs)` |
| `src/vgcp/sim/` | simulated network + scenario parser | `SimulatedNetwork` |
| `src/vgcp/emu/` | Mininet/OVS backend; only `MininetFabric` needs root | `MininetNetwork` |
| `src/vgcp/experiments/` | `run_trial`, `summarize`, campaign CLI, calibration CLI | `python -m vgcp.experiments`, `python -m vgcp.experiments.calibrate` |
| `src/vgcp/demo/` | dashboard server, session, static page | `python -m vgcp.demo` |
| `experiments/scenarios/` | s1-s6 scenario YAML | – |
| `tests/unit/`, `tests/integration/` | unit tests (no root); Mininet tests (root, skipped otherwise) | `scripts/run_unit_tests.sh` |

### How to validate a change

* Any code change: `scripts/run_unit_tests.sh` (~25 s; currently 494 passed).
* `vgcp/emu/` changes: the unit tests, then hand the maintainer
  `sudo scripts/mininet_run.sh` (integration suite twice). Never run it yourself.
* Dashboard changes: `.venv/bin/python -m pytest tests/unit/test_demo.py`, then start
  `scripts/run_dashboard.sh` and load a deep link. Windows Chrome can render it
  headlessly from WSL.
* Update docs/STATUS.md (and DECISIONS / EXPERIMENTS when relevant) in the same branch.

### Known open issues (do not "fix" by relabelling)

* **Mininet telemetry** (2026-10-22 audit):
  * **Fixed and confirmed on Mininet** (`824c8b1`, re-run `mininet-20261022T170942Z`):
    reroute counter resets (rule identity by age), pre-meter ingress counting
    (managed rate read downstream), NaN handling in loss and summaries, overload
    on measured data.
  * **Fixed in code, not yet run on Mininet:** stale rule counters. OVS refreshes
    them every 500 ms; snapshots now call `ovs-appctl revalidator/wait` first.
  * **Still open:**
    * the meter passes ~1.10× the budget at 50-70 Mb/s (cause unknown), which
      alone explains s2's reservation-limit slots on Mininet (team decision,
      DECISIONS 2026-10-22);
    * scenarios give payload rates while counters count frames;
    * eMBB's 1500-byte payload fragments;
    * latency is the max of 8 probes.
* **Research gaps:**
  * The latency factor is calibrated on the simulator only; the configured 1.5 is
    kept.
  * Eq 42 weights are illustrative.
  * π₀(s) recursive feasibility (Assumption 3) is not shown.
  * s5 shows that a structurally wrong model defeats the shield.

---

## Layout

```
research/      the paper (local only, never tracked)
docs/          status, architecture, decisions, experiments, design, traceability
configs/       network, constraints, intents (STL), shield settings - all thresholds
src/vgcp/      state, action, constraints, stl/, models/, shield, loop/, sim/, emu/,
               experiments/, demo/
tests/         unit/ (no root), integration/ (Mininet, root)
scripts/       setup_venv, run_unit_tests, run_experiments, run_dashboard, mininet_run
experiments/   scenarios/ (tracked), reports/ (tracked summaries), results/ (local, ignored)
```

## Prerequisites

* Linux with the system Python 3.12 (`/usr/bin/python3`) and PyYAML (`python3-yaml`).
* A `pip` to install the test dependencies into the virtual environment (see
  `scripts/setup_venv.sh`).
* Unit tests, simulation experiments and the dashboard need no root. Mininet, Open
  vSwitch and iperf3 are needed only for the emulated network, which runs as root.

Property-based tests (Hypothesis) are deterministic by default. For fresh random
examples:

```bash
HYPOTHESIS_PROFILE=explore scripts/run_unit_tests.sh
```

## Audit history (Milestone 1)

An independent audit of Milestone 1 found issues; all are addressed:

* **C1** - non-finite measurement timestamps no longer pass freshness checks.
* **H2** - unknown or misspelled configuration keys are rejected at load time.
* **M3** - actions are immutable and certificates are bound to the action and its
  input fingerprints. `CertifiedApplier` enforces this before anything reaches the
  network (Milestone 2).
* **M1** - Eq 17 is checked against a hand calculation, an independent naive STL
  implementation and a literal Eq 17 reference.
* **M2** - the out-of-distribution threshold (Def 2) is no longer misapplied; the
  nominal model reports an explicit validity flag (D12).
* **H1** - measured background traffic per link counts in capacity and in the model.
* **H3** - intents are recovery-style (`G[1,10] p`); certificates list measured
  violations.
* **M4** - predicates are normalized per signal family, with one global ρ_min.
* **M5** - intents may not read, over the rollout, signals the model does not predict.
* **L1-L8** - addressed or documented (L5 and L8 are documented limitations).

Details: [docs/milestone1_design.md](docs/milestone1_design.md) and
[docs/DECISIONS.md](docs/DECISIONS.md).
