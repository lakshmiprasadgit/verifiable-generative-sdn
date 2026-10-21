# Implementation status

As of 2026-10-21. Earlier snapshot: 2026-10-20 (`8ed17b8`).
This is a research prototype: it is not formally verified, and nothing here is a
claim about the safety of a real network.

## Where we are

Stage 1, **Milestone 1 is implemented, audited, and every audit finding is
addressed** (decisions on H1, H3 and M4 taken 2026-10-21). **Milestone 2 (Mininet,
Open vSwitch, controller) is approved** to start after these changes are pushed.

| Milestone | Scope | Status |
|---|---|---|
| 1 | state/action schemas, hard constraints, STL robustness, verification shield | implemented; all audit findings addressed |
| 2 | Mininet topology, SDN controller | approved, not started |
| 3 | traffic, telemetry, nominal-model calibration | not started |
| 4 | fallback, heuristic candidates, selection, closed loop | not started |
| 5 | experiments, metrics, reports | not started |

## What exists (Milestone 1)

| Component | Code | Paper |
|---|---|---|
| State s_t and demand d_t, with measurement validity and freshness | `src/vgcp/state.py` | Eqs 1, 3 |
| Bounded action set A; immutable actions; vector form for learned policies | `src/vgcp/action.py` | Eq 2 |
| Hard constraints c(s, a) <= 0 (capacity incl. measured background load, flow table, minimum budget, routing validity) | `src/vgcp/constraints.py` | Eq 16 |
| STL syntax, parser and robustness; predicates normalized per signal family | `src/vgcp/stl/` | Eqs 5-11 |
| Analytic nominal model T-hat (uncalibrated), upper-bound demand forecast, static fallback pi_0 | `src/vgcp/models/` | Eqs 12-13 |
| Verification shield with certificates bound to the certified action | `src/vgcp/shield.py` | Eqs 14, 17-18 |
| Strict configuration loading; all thresholds in `configs/` | `src/vgcp/config.py` | - |

Details: [milestone1_design.md](milestone1_design.md) (design, decision register
D1-D19) and [traceability.md](traceability.md) (paper-to-code table).

## Tests

`scripts/run_unit_tests.sh` - **379 passed, 0 failed** on 2026-10-21 (no root,
no Mininet). Property-based tests are deterministic by default;
`HYPOTHESIS_PROFILE=explore` searches with fresh random examples.

| File | Tests | Covers |
|---|---|---|
| test_stl_robustness / _parser / _properties | 25 / 32 / 5 | hand-calculated STL cases, syntax, semantic properties |
| test_eq17 | 11 | naive Eq 8-11 oracle, hand-calculated Eq 17 instance, literal Eq 17 reference on a grid |
| test_shield | 49 | acceptance, rejection, missing/stale/non-finite inputs, internal errors |
| test_certificate_binding | 26 | action immutability, certificate binding, fail-closed `authorizes()` |
| test_config / _strict | 35 / 41 | validation, Assumption 1 horizon, unknown or misspelled keys |
| test_state / test_action / test_constraints / test_models | 30 / 25 / 15 / 9 | schemas, constraints, nominal model |
| test_unmodelled_signals | 16 | intents may not read model placeholders over the rollout |
| test_audit_low | 24 | low-severity audit fixes |
| test_background_load / test_normalization / test_recovery_intents | 9 / 18 / 9 | H1, M4, H3 |

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
| H1 capacity constraint and model ignored measured link load | fixed: per-link `background_load_mbps` (D16) | `6ed2223` |
| M4 robustness compared across different units | fixed: per-family scales, one unitless rho_min (D18; D2 retired) | `e156bd5` |
| H3 a measured violation made the fallback uncertifiable | fixed: recovery-style `G[1,10] p` intents, `measured_violations` in certificates (D19) | `f994235` |

## Decisions taken on 2026-10-21

1. **H1:** measure background load per link (link rate minus managed-slice flow
   rates). **Milestone 2 must provide it** from OpenFlow port and flow statistics.
2. **H3:** recovery-style intents. The configured form is `G[1,10] p`; the first
   proposal `F[0,2] G[0,8] p` turned out to hide the candidate's own effect (Eq 13
   applies it for one step) and was not adopted. Longer recovery windows need a
   model with recovery dynamics (Milestone 3).
3. **M4:** normalized predicates, one global unitless rho_min = 0.05. The eMBB
   latency margin is therefore 0.05 ms (was 1 ms); margins remain illustrative.
4. **Milestone 2:** approved, to start after these changes are pushed.

Still open: `research/problem_formulation_corrected.pdf` stays untracked until its
distribution rights are confirmed.

## Known limitations

* The nominal model is uncalibrated and not shown to be conservative.
* The fallback policy's recursive feasibility (Assumption 3) is not checked.
* Shield acceptance means feasibility with respect to the model and the configured
  constraints, not safety of the real network.
* Certificates are not yet enforced by any apply step (Milestone 4).
* Background load is held constant over the horizon; that is not conservative if it grows.
* No mMTC loss intent is active: the model does not predict loss yet.
* Thresholds in `configs/` are illustrative experiment values, not 6G standards.
