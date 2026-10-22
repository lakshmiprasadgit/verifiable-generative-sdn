# Milestone 1 - Design: state, actions, constraints, STL, verification shield

Specification: `research/problem_formulation_corrected.pdf` (SHA-256 `8d81ddff…2fbeb76`).
Code: `src/vgcp/`. Configuration: `configs/`. Tests: `tests/unit/`.
Equation-to-code mapping: [traceability.md](traceability.md).

Stage 1 replaces the generative policy G_θ and learned world model W_ψ with
conventional components. Neither is implemented in Milestone 1; their
interfaces (`TransitionModel`, `FallbackPolicy`, `DemandForecast`, the vector
embeddings of s, a, d) are in place.

---

## 1. State s_t and exogenous input d_t (paper Eqs 1, 3)

* A state is a set of named scalar **measurements** (`NetworkState`), each with
  a value and the timestamp at which it was measured. `value=None` means
  "not measured"; nothing is ever imputed.
* Metric keys are `<family>.<index>` (e.g. `latency_p99_ms.urllc`,
  `link_utilization.l12`, `flow_table_occupancy.s3`, `energy_w`). The families
  and units are listed in `src/vgcp/state.py`.
* `ObservationSchema` fixes the key order (vector embedding in R^{n_s}, NaN for
  missing) and per-family bounds from `configs/network.yaml` (bounded S, D;
  Assumption 4).
* Paper state components **not** represented: radio resource-block
  utilization (no RAN in the prototype); per-flow latency is aggregated per
  slice; the "routing table summary" is the current action, which later
  milestones log alongside the state.
* d_t (`Demand`) holds per-slice offered load and active device count.

**Measurement validity** (`ObservationSchema.check`). A value is usable only
if it is present, numeric (not bool), finite, inside its configured bounds,
timestamped, not in the future, and no older than `max_staleness_s`
(`configs/shield.yaml`; both bounds are inclusive). Anything else yields a
specific status (`missing`, `stale`, `out_of_bounds`, …). Out-of-bounds values
are rejected, never clipped. Measured link utilization is bounded by [0, 1];
real port counters can read slightly above 1 because of sampling jitter, which
would make the shield reject (fail safe, but costs availability). The bound will
be revisited with real counter data in Milestone 3 (audit L5). Unexpected metric keys are reported as
`unknown_key`.

## 2. Control action a_t and the action set A (paper Eq 2)

| Component | Type | Bounds |
|---|---|---|
| `path[slice]` | discrete | `allowed_paths` of the slice |
| `rate_budget_mbps[slice]` | continuous | `[lo, hi]` per slice |
| `admission_limit[slice]` | integer | `[lo, hi]` per slice |
| `link_power[link]` | binary | power-controllable links only |

`ActionSchema.validate` returns every reason an action is outside A: wrong
type, missing or extra entries, unknown or disallowed path, non-finite or
out-of-range budget, non-integer (or bool) limit, non-bool power state. Bounds
are inclusive. `to_vector`/`from_vector` give a fixed-order embedding in
R^{n_a}. Decoding a vector never rounds: a non-integral path index or limit is
rejected, so malformed output from a future generator cannot be silently repaired.

Not modelled yet (paper Sec 2.1): P4 table entries, O-RAN RIC parameters,
queue scheduling weights.

## 3. Hard constraints c(s, a) ≤ 0 (paper Eq 16)

Configured in `configs/constraints.yaml`; every family can be disabled. Each
component is a real number: ≤ 0 satisfied (0 is satisfied), > 0 is the amount
of violation. Boolean invariants use 0/1.

| Component | Definition | Unit |
|---|---|---|
| `link_capacity.<l>` | Σ budgets of slices routed on l + background_l − f_max·C_l | Mbit/s |
| `flow_table.<sw>` | occupancy(sw) + r·(#slices through sw) − N_max | entries |
| `slice_min_budget.<s>` | min_s − budget_s | Mbit/s |
| `routing_validity.<s>` | 0 if path allowed, loop-free, ingress→egress, all links powered; else 1 | – |

Missing inputs (e.g. no flow-table measurement) make a component **unknown**
(`None`), never satisfied. The vector's status is `violated` if any
component > 0, else `unknown` if any is unknown, else `satisfied`.

Assumptions under which these are meaningful:
* `link_capacity` counts reserved budgets plus the measured background load
  (traffic outside the managed slices, audit H1). It bounds real load only if the
  data plane polices each slice to its budget (meters, Milestone 2) and the
  background measurement is accurate; a missing background measurement makes the
  component unknown, so the action is rejected.
* `flow_table` counts old and new rules together (make-before-break), so it is
  conservative for the update itself.

## 4. STL specifications (paper Sec 2.2, Eq 7)

**Syntax.** Core node types are exactly those of Eq 7: `Top`, `Predicate`,
`Not`, `And`, `Until[a,b]`. Derived operators are constructor functions that
expand to the paper's definitions:
`F[a,b]φ = ⊤ U[a,b] φ`, `G[a,b]φ = ¬F[a,b]¬φ`, `φ∨ψ = ¬(¬φ∧¬ψ)`,
`false = ¬⊤`. Formulas are written as text in `configs/intents.yaml`
(grammar in `src/vgcp/stl/parser.py`).

**Predicates** (Eq 5). `x <= c` has p = (c − x)/σ and `x >= c` has p = (x − c)/σ,
where σ > 0 is the declared scale of the signal's family (D18; σ = 1 recovers Eq 6)
(this matches Eq 6, p₁ = L_max − latency). The predicate holds iff p ≥ 0.
Strict `<`, `>` are rejected because robustness cannot distinguish them.
Signals are state metric keys and numeric action components prefixed with
`action.`, so predicates may depend on both s and a, as in Eq 5.

**Signal representation.** `Trace`: for each signal name, a sequence of floats
indexed by slot k = 0..N−1. Missing samples are NaN. ±inf samples are treated
as invalid measurements and stored as NaN. Non-numeric samples raise TypeError.

**Temporal sampling convention.** Discrete time: slot k corresponds to time
t₀ + k·Δt, with Δt = `control.delta_t_s` (1 s). `intents.yaml` states the slot length its bounds
were written for (`slot_duration_s`); loading fails unless it equals Δt, so
changing Δt cannot silently rescale every intent (audit L6). The paper calls STL
"dense-time" but defines everything on slotted time (Sec 2.1); this
implementation uses discrete-time semantics.

**Time windows.** `[a, b]` are integer slot offsets, 0 ≤ a ≤ b, **closed at
both ends**. For `φ₁ U[a,b] φ₂` at t, τ ranges over {t+a, …, t+b} and φ₁ is
required over u ∈ [t, τ] **including τ**, exactly as in Eq 11. Some literature
uses [t, τ); `test_until_uses_closed_interval_t_tau` pins the paper's choice.

**Robustness** (Eqs 8–11). ρ_⊤ = +∞ (the paper does not define it; this is
the standard choice), ρ_p = p, ρ_¬ = −ρ, ρ_∧ = min, ρ_U as in Eq 11.

**Satisfaction.** ρ > 0 → `SATISFIED`; ρ < 0 → `VIOLATED` (paper Sec 2.2).
ρ = 0 is not classified by the paper and is reported as `BOUNDARY`, with
the Boolean value from qualitative semantics (predicate true iff p ≥ 0). A
property-based test checks that the sign of ρ agrees with the Boolean
semantics whenever ρ ≠ 0.

**Missing or invalid measurements.** If any sample the evaluation reads is
NaN, the result is `UNKNOWN` (robustness `None`). No partial evaluation is
attempted, so even `F` with one known satisfying sample is `UNKNOWN`. This is
deliberately conservative. Samples outside the evaluated windows do not affect
the result.

**Horizon.** If evaluation at t would read past the end of the trace,
`TraceTooShortError` is raised; the value is undefined, not guessed.

## 5. Verification shield V (paper Eqs 12–19)

`VerificationShield.verify(state, demand, action, now_s) → Certificate`.
Checks, in order, each `PASS` / `FAIL` / `UNKNOWN`:

1. `action_valid` – a ∈ A.
2. `state_measurements` – every state metric read by the constraints, the
   nominal model or an intent is usable (§1).
3. `demand_measurements` – same for d_t.
4. `hard_constraints_now` – c(s_t, a_t) ≤ 0.
5. `nominal_model_domain` – every predicted step of the projected trajectory
   (Eqs 12–13) is inside the nominal model's validity domain (extension D12;
   this is not the paper's Def 2, see below).
6. `fallback_continuation` – π₀'s actions along the rollout are in A.
7. `hard_constraints_rollout` – c(ŝ_{t+k}, â_{t+k}) ≤ 0 for k = 1..H
   (configurable; stricter than Eq 17).
8. `intent:<name>` – ρ_φ(s_t, a_t) ≥ ρ_min for each φ ∈ Φ, where ρ_φ is
   Eq 14 evaluated on the projected trajectory (ŝ_t = s_t, â_t = a_t,
   â_{t+k} = π₀(ŝ_{t+k})).

**Decision.** The action is accepted iff every check is `PASS`, except that a check disabled by configuration (only `hard_constraints_rollout`, D3) is reported as `NOT_APPLICABLE` rather than `PASS` (audit L1). If a
prerequisite (1–3) fails, the later checks are recorded as `UNKNOWN`
("skipped"), never `PASS`. Any exception inside the shield is recorded as
`internal_error: UNKNOWN`, so an exception is a rejection. The `Certificate`
records every check with detail, per-intent ρ, the c(s_t, a_t) vector, whether
the nominal model stayed in its validity domain, H, ρ_min and the configuration
hash, and it serialises to strict JSON.

The comparison ρ ≥ ρ_min is exact on floating-point values, with no tolerance
(as in Eq 17). A ρ within rounding error of ρ_min can land on either side; for
example 1.0 − 0.95 evaluates to 0.050000000000000044 and passes ρ_min = 0.05.
ρ_min is the safety margin and should be chosen well above rounding error
(audit L8, pinned by `test_rho_min_comparison_is_exact_floating_point`).

**Binding (audit M3).** `ControlAction` copies its four mappings into read-only
views at construction, so an action cannot change after it is verified. The
certificate records the certified action, a canonical SHA-256 `action_fingerprint`
(sorted keys; budgets as floats so 100 ≡ 100.0; limits as ints; anything
non-canonical has no fingerprint), `now_s`, and fingerprints of the measured state
and demand. `Certificate.authorizes(action)` is true only for an accepted
certificate and an action with the same fingerprint; it fails closed otherwise.
It does **not** check the input context. Whether a certificate may be used at a
later state or slot is a closed-loop decision for Milestone 4. No code in
`src/` consumes certificates yet, so the apply step (Milestone 4) must call
`authorizes()` for the binding to be enforced.

**Rollout components (Stage 1).**
* T̂ – `AnalyticNominalModel`: fluid load and M/M/1 queueing approximation,
  formulas in `src/vgcp/models/nominal.py`. **Uncalibrated.** Each prediction
  carries `in_domain`, which is false when utilization exceeds
  `max_valid_utilization`, load is routed over a powered-off link, or an input
  is unknown (D12). It carries no uncertainty value.
* The paper's out-of-distribution trigger (Def 2, Constraint 3: u_ψ > η ⇒ π₀)
  concerns the learned world model W_ψ used for candidate selection (Eq 42), not
  T̂ in the certificate (Eq 14). Stage 1 has no W_ψ, so Def 2 is not implemented
  and there is no η setting (audit finding M2).
* Placeholder outputs (audit M5): T̂ reports loss as 0 inside its validity domain
  and carries flow-table occupancy forward; it declares these keys in
  `unmodelled_state_keys()`. The shield refuses to be constructed if an intent
  reads such a signal beyond offset 0 (`stl.signal_offsets`), because over the
  rollout it would only test the placeholder (D13). The shipped `mmtc_loss`
  intent is therefore a current-measurement check, `loss_rate.mmtc <= 0.02`.
* d̄ – `UpperBoundConstantForecast`: d̄_{t+k} = (1+margin)·d_t.
* π₀ – `StaticFallbackPolicy`: one configured action (must be in A; checked at load).

### What an acceptance does and does not mean

**Established by the implementation.** V = 1 ⇒ a ∈ A_Φ(s_t) as defined by
Eq 17, *where ρ_φ is computed with the configured T̂, d̄ and π₀ and c is the
configured constraint set*. This is Assumption 2 (soundness) **relative to
the model**. The shield evaluates Eq 17 and then applies extensions (measurement
validity, D3, D12, π₀ outputs in A) that can only remove actions, so the accepted
set is a subset of Eq 17's; it is not claimed to equal it.

Evidence (`tests/unit/test_eq17.py`, audit finding M1):
* the STL evaluator matches a naive, separately written transcription of
  Eqs 8–11 (`tests/unit/stl_reference.py`) on random formulas and traces;
* a small instance with an action-signal intent whose accept/reject outcomes and
  ρ values are calculated by hand, with no shield code involved;
* a literal Eq 17 reference (c at k = 0 only, no domain check, ρ from the naive
  oracle) on a 648-action grid. It shares T̂, d̄, π₀ and c with the shield because
  Eq 17 is defined in terms of them, but not the shield's decision, rollout or STL
  code. Every accepted action is in Eq 17's set; on this grid the two sets
  coincide (75 accepted, 573 rejected) both with D3 off (Eq 17 as written) and on,
  and any Eq 17 action the shield rejects must be explained by an extension check;
* targeted cases where D3 and D12 each remove an action that Eq 17 admits.

`test_shield_matches_extended_feasible_set_on_action_grid` (in `test_shield.py`)
compares the shield with a restatement of its *extended* set built from the same
components; it is a regression check, not independent evidence.

**Not established.**
* That the real (emulated) network behaves as T̂ predicts. T̂ is
  uncalibrated and its conservativeness is unproven. Summing per-hop p99
  values is a heuristic, not a bound. This is measured in Milestone 3.
* Assumption 3 (π₀ is recursively feasible on the reachable state space).
  This is not checked; Milestone 4 checks π₀ offline over the demand box D.
* The "99.999 % reliability" part of the paper's example intent. A
  single-trajectory STL formula cannot express it; it will be estimated
  empirically.
* Any almost-sure guarantee (Constraint 1) about the real network. It
  requires Assumptions 2 and 3 to hold for the real system, which Stage 1 can
  only test empirically.

## 6. Design choices that need approval (deviations or extensions)

| # | Topic | Paper | Implementation | Why |
|---|---|---|---|---|
| D1 | Horizon (Assumption 1) | H ≥ b_φ = largest right endpoint | Also requires H ≥ hrz(φ), the nested horizon (e.g. `G[0,5]F[0,3]` needs 8) | With nested operators, H ≥ b_φ does not make ρ well-defined, contrary to the paper's claim |
| D2 | ρ_min | single global ρ_min | **retired (audit M4)**: was a per-intent override; replaced by normalized predicates (D18) and one global ρ_min | per-intent overrides are now rejected as unknown keys |
| D3 | Constraints along rollout | Eq 17 checks c only at (s_t, a_t) | Also checks k = 1..H (configurable, on by default) | Stricter; detects a π₀ continuation that violates c |
| D4 | Shield inputs | V : S × A × Φ | also takes d_t and the current time | d̄ in Eq 12 needs measured demand; staleness needs a clock |
| D5 | ρ of ⊤ | not stated | +∞ | standard; makes F = ⊤U behave as max |
| D6 | ρ = 0 | not classified | `BOUNDARY` + Boolean semantics | the shield never accepts it because ρ_min > 0 |
| D7 | Missing samples | not discussed | any missing sample read → UNKNOWN → reject | conservative; no imputation |
| D8 | Strict predicates | not discussed | `<`, `>` rejected | robustness cannot distinguish them |
| D9 | Time domain | "dense-time" STL | discrete slots of Δt | the paper's own model is slotted |
| D10 | d̄ conservativeness | "conservative demand forecast" | one upper-bound forecast | conservative for load and latency, **optimistic** for lower bounds on throughput; no throughput lower-bound intents configured |
| D11 | Trajectory start | ŝ_t = s_t (Eq 12) | as written | intents are partly decided by the current measurement, independently of a_t; resolved for the configured intents by D19 (audit H3) |
| D12 | Nominal-model validity domain | T̂ is assumed conservative; no validity domain | shield rejects (UNKNOWN) if any rollout step is outside T̂'s validity domain (`nominal_model_domain`) | an analytic queueing model's formulas break down near saturation; using them there would certify on meaningless numbers. Not the paper's Def 2 (which concerns W_ψ) |
| D13 | Intents on unmodelled signals | not discussed | an intent may read a signal the nominal model does not predict (loss, flow-table occupancy) only at the current step; otherwise the shield refuses to start | over the rollout such a signal is a placeholder, so the intent would be vacuous (audit M5) |
| D14 | Measurement validity | the state s_t is given | the shield rejects (UNKNOWN) if any state or demand metric it reads is missing, non-finite, out of bounds, stale or badly timestamped | the paper assumes s_t is known; a real controller's telemetry is not always usable |
| D15 | Fallback outputs along the rollout | π₀ is assumed well defined | each π₀ output along the rollout must be in A (`fallback_continuation`), otherwise reject | detects a broken π₀ instead of crashing or using an invalid action |
| D16 | Link-capacity constraint | "physical link capacities" | Σ reserved rate budgets on a link + measured background load ≤ f_max · capacity | slice traffic is bounded by its budget (meters, Milestone 2); traffic outside the slices is measured as `background_load_mbps` = link rate − managed flow rates (audit H1). T̂ adds the background to utilization and holds it constant over the horizon, which is not conservative if it grows |
| D17 | Predicate functions | any real-valued p_i(s, a) (Eq 5) | single-signal comparisons `x <= c` (p = c − x) and `x >= c` (p = x − c) | covers Eq 6 and the configured intents; sums or maxima of signals are not expressible yet |
| D18 | Predicate normalization | p₁ = L_max − latency (Eq 6), in the signal's unit | p = (c − x)/scale with a declared scale per signal family (`intents.signal_scales`), so robustness is unitless | one ρ_min (Eq 17) and minima over intents (Eqs 27, 40) then compare like with like; positive scaling never changes satisfaction (audit M4) |
| D19 | Recovery-style intents | intents over [0, b] with ŝ_t = s_t | configured intents are `G[1,10] p`: the measured slot k = 0 is excused; the certificate lists `measured_violations` | with `G[0,10] p` a violation already in s_t rejects every action including π₀, contradicting Assumption 3. Wider windows (e.g. `F[0,2] G[0,8] p`) are unsafe because Eq 13 applies the candidate for one step, so its effect appears only at k = 1 (pinned by a test). Eq 14 is unchanged (audit H3) |
| D20 | Selection rule σ and utility U (Eqs 27, 42) | argmax over A_Φ(s_t) of E_qψ[Σ γ^k U] | mode `shielded-utility`: one deterministic rollout with T̂ (no q_ψ); Q = total throughput, E = −power, ρ = tightest normalized predicate, C = reserved budgets; weights in `shield.selection` | Stage 1 has no world model; the terms are the simplest readings of Eq 27's definitions. `shielded` keeps first-certified for comparison (Milestone 4) |

## 7. Illustrative parameters

All numeric thresholds in `configs/` (1 ms / 40 ms latency, 2 % loss, link
capacities, delays, margins) are experiment parameters for a scaled-down
software emulation. The 1 ms URLLC bound mirrors the paper's example intent.
None of them is presented as a 6G standard value.

## 8. Configuration validation

`config.build_config` (also used by `load_config`) first checks the raw
configuration against an explicit key schema (`_SCHEMA` in `src/vgcp/config.py`).
Any key that is not listed for its mapping is rejected with a `ConfigError` that
names the section path, the key, the closest allowed key and the full allowed set,
e.g. `intents.intents[0]: unknown key 'rho_mn' (did you mean 'rho_min'?)`.
This applies at every level, including the top-level sections, list items
(`links[i]`, `intents[i]`) and per-slice entries, and also to constraint families
that are disabled. Identifier and label fields must be strings, and list fields must
be lists; they are no longer converted with `str()`.

Optional keys and their defaults (unchanged):

| Key | Default |
|---|---|
| `intents[].rho_min` | global `rho_min` (D2) |
| `intents[].enabled` | `true` |
| `intents[].description` | `""` |
| `network.topology.power_controllable_links` | `[]` |
| `shield.nominal_model.calibration_status` | `"uncalibrated"` |

Parameters of a constraint family are required only while the family is enabled.
All other keys are required. Value checks (types, ranges, exact name sets) are
unchanged.
