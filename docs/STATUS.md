# Implementation status

As of 2026-10-20, `main` at the commit that adds this file (previous: `806ccf4`).
This is a research prototype: it is not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

Stage 1, **Milestone 1 is implemented and audited**. Milestone 2 (Mininet, Open
vSwitch, controller) has **not** been started and needs explicit approval.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, hard constraints, STL robustness, verification shield | implemented; audit fixes applied; 3 findings await design decisions |
| 2 | Mininet topology, SDN controller | not started (not yet authorized) |
| 3 | traffic, telemetry, nominal-model calibration | not started |
| 4 | fallback, heuristic candidates, selection, closed loop | not started |
| 5 | experiments, metrics, reports | not started |

## What exists (Milestone 1)

| Component | Code | Paper |
|---|---|---|
| State s_t and demand d_t, with measurement validity and freshness | `src/vgcp/state.py` | Eqs 1, 3 |
| Bounded action set A; immutable actions; vector form for learned policies | `src/vgcp/action.py` | Eq 2 |
| Hard constraints c(s, a) <= 0 (capacity, flow table, minimum budget, routing validity) | `src/vgcp/constraints.py` | Eq 16 |
| STL syntax, parser and robustness | `src/vgcp/stl/` | Eqs 5-11 |
| Analytic nominal model T-hat (uncalibrated), upper-bound demand forecast, static fallback pi_0 | `src/vgcp/models/` | Eqs 12-13 |
| Verification shield with certificates bound to the certified action | `src/vgcp/shield.py` | Eqs 14, 17-18 |
| Strict configuration loading; all thresholds in `configs/` | `src/vgcp/config.py` | - |

Details: [milestone1_design.md](milestone1_design.md) (design, decision register
D1-D17) and [traceability.md](traceability.md) (paper-to-code table).

## Tests

`scripts/run_unit_tests.sh` - **342 passed, 0 failed** on 2026-10-20 (no root,
no Mininet). Property-based tests are deterministic by default;
`HYPOTHESIS_PROFILE=explore` searches with fresh random examples.

| File | Tests | Covers |
|---|---|---|
| test_stl_robustness / _parser / _properties | 25 / 32 / 5 | hand-calculated STL cases, syntax, semantic properties |
| test_eq17 | 11 | naive Eq 8-11 oracle, hand-calculated Eq 17 instance, literal Eq 17 reference on a grid |
| test_shield | 49 | acceptance, rejection, missing/stale/non-finite inputs, internal errors |
| test_certificate_binding | 26 | action immutability, certificate binding, fail-closed `authorizes()` |
| test_config / _strict | 35 / 40 | validation, Assumption 1 horizon, unknown or misspelled keys |
| test_state / test_action / test_constraints / test_models | 30 / 25 / 15 / 9 | schemas, constraints, nominal model |
| test_unmodelled_signals | 16 | intents may not read model placeholders over the rollout |
| test_audit_low | 24 | low-severity audit fixes |

## Audit status

An independent audit of Milestone 1 reported 1 critical, 3 high, 5 medium and 8
low findings.

| Finding | Status | Commit |
|---|---|---|
| C1 non-finite timestamps passed freshness checks | fixed | `eb0d31e` |
| H2 misspelled config keys silently ignored | fixed | `eb0d31e` |
| M3 certificate not bound to the certified action | partly: binding done; enforcement needs the Milestone 4 apply step | `eb0d31e` |
| M1 Eq 17 evidence overstated | fixed | `8ff6d2f` |
| M2 out-of-distribution threshold (Def 2) misapplied | fixed | `8ff6d2f` |
| M5 intents on unmodelled signals were vacuous | fixed | `5845cb1` |
| L1-L4, L6, L7 | fixed | `2be136e` .. `806ccf4` |
| L5 utilization bound vs counter jitter | documented; revisit with real data in Milestone 3 | `806ccf4` |
| L8 exact float comparison at rho_min | documented and pinned by a test | `806ccf4` |
| **H1** capacity constraint and model ignore measured link load | **open: needs a decision** | - |
| **H3** fallback cannot satisfy intents already violated by the measured state (tension with Assumption 3) | **open: needs a decision** | - |
| **M4** robustness compared across different units | **open: needs a decision** | - |

## Decisions needed (agenda for the next session)

1. **H1 - measured link load.** Should the capacity constraint and/or the nominal
   model use measured utilization (to account for traffic outside the managed
   slices)? This determines what telemetry Milestone 2 must provide, so it should
   be settled before Milestone 2.
2. **H3 - intents and the measured state.** Options: evaluate intents from t+1,
   write recovery-style intents, or deploy pi_0 and log an Assumption 3
   violation. A research decision; needed before Milestone 4.
3. **M4 - units of robustness.** Normalize each predicate to a unitless scale so
   the paper's single rho_min works (and Eqs 27, 40 become meaningful), or keep
   per-intent margins (D2). Needed before Milestone 4.
4. **Milestone 2 go-ahead**, once H1 is decided.
5. **Research PDF.** `research/problem_formulation_corrected.pdf` stays untracked
   until its distribution rights are confirmed.

## Known limitations

* The nominal model is uncalibrated and not shown to be conservative.
* The fallback policy's recursive feasibility (Assumption 3) is not checked.
* Shield acceptance means feasibility with respect to the model and the configured
  constraints, not safety of the real network.
* Certificates are not yet enforced by any apply step (Milestone 4).
* Thresholds in `configs/` are illustrative experiment values, not 6G standards.
