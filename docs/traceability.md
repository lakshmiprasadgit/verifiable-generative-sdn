# Research-to-code traceability (Milestone 1)

Paper: `research/problem_formulation_corrected.pdf`. Status column:
**Impl** = implemented as written; **Impl\*** = implemented with a documented
deviation or extension (see [milestone1_design.md §6](milestone1_design.md));
**Iface** = interface or placeholder only; **Later** = later milestone.

| Paper item | Statement | Code | Tests | Status |
|---|---|---|---|---|
| Sec 2.1 | slotted time t ∈ {0..T} | `control.delta_t_s` (configs/network.yaml); slot index `Observation.t`; STL slots | test_stl_robustness | Impl (D9) |
| Eq 1 | s_t ∈ S ⊆ R^{n_s} | `vgcp.state.NetworkState`, `ObservationSchema.to_vector/from_vector` | test_state | Impl |
| Eq 2 | a_t ∈ A ⊆ R^{n_a}, bounded, mixed discrete/continuous | `vgcp.action.ControlAction`, `ActionSchema.validate/to_vector/from_vector/vector_bounds` | test_action | Impl (subset of components, §2) |
| Eq 3 | d_t ∈ D ⊆ R^{n_d} | `vgcp.state.Demand`, demand schema | test_state | Impl (load and devices only) |
| Eq 4 | s_{t+1} = T(s_t, a_t, d_t, ε_t), unknown | real network (Milestone 2) | – | Later |
| Eq 5 | predicates p_i : S × A → R | `stl.ast.Predicate`; signals from s and a in `vgcp.signals.step_signals` | test_stl_robustness, test_shield | Impl\* (subset: single-signal comparisons `x <= c` / `x >= c`, D8, D17) |
| Eq 6 | p₁ = L_max − latency | `Predicate(op="<=").value` = c − x | `test_predicate_le_matches_eq6` | Impl |
| Eq 7 | STL syntax ⊤, p ≥ 0, ¬, ∧, U[a,b]; ◇, □ derived | `stl.ast` (core nodes + `Eventually`, `Always`, `Or`, `false` constructors), `stl.parser` | test_stl_parser, `test_derived_operators_expand_to_core` | Impl |
| Eq 8 | ρ_p = p_i(s_t, a_t) | `stl.robustness._rho` (Predicate) | hand cases | Impl |
| Eq 9 | ρ_¬φ = −ρ_φ | `_rho` (Not) | `test_negation_eq9`, property tests | Impl |
| Eq 10 | ρ_∧ = min | `_rho` (And) | `test_conjunction_eq10` | Impl |
| Eq 11 | ρ_U = max_τ min(ρ₂(τ), min_{u∈[t,τ]} ρ₁(u)) | `_rho` (Until), closed [t, τ] | `test_until_eq11`, `test_until_uses_closed_interval_t_tau`; Eqs 8–11 vs naive oracle `stl_reference.py`: `test_robustness_matches_naive_eq8_to_11` | Impl |
| Sec 2.2 | ρ > 0 satisfied, ρ < 0 violated | `stl.robustness.evaluate` → `Verdict` | sign-agreement property test | Impl\* (D5, D6, D7) |
| Eq 12 | ŝ_{t+k+1} = T̂(ŝ_{t+k}, a_{t+k}, d̄_{t+k}) | `VerificationShield.rollout`; T̂ = `models.nominal.AnalyticNominalModel`; d̄ = `models.forecast.UpperBoundConstantForecast` | test_models, test_shield | Impl\* (T̂ uncalibrated; D10) |
| Eq 13 | a_{t+k} = a_t (k=0), π₀(ŝ_{t+k}) (k≥1) | `VerificationShield.rollout`; π₀ = `models.fallback.StaticFallbackPolicy` | `test_invalid_fallback_continuation_rejects` | Impl |
| Eq 14 | ρ_φ(s_t, a_t) = ρ_φ(ŝ_{t:t+H}, â_{t:t+H}, t) | `VerificationShield._run_checks` (intent checks) | `test_accepts_fallback_in_nominal_conditions` (hand-checked ρ); intents may not read unmodelled outputs beyond offset 0: `test_unmodelled_signals.py` | Impl\* (D11, D13) |
| Assumption 1 | H ≥ max_φ b_φ | `stl.ast.max_temporal_bound`, `required_horizon`; enforced in `config.build_config` | test_config (`test_assumption1_*`, `test_nested_horizon_*`) | Impl\* (D1) |
| Sec 2.2 | Φ ≠ ∅, else Φ = {⊤} | `config.build_config` | `test_empty_intent_set_becomes_top`, `test_top_intent_set` | Impl |
| Eq 16 | hard constraints c(s, a) ≤ 0 | `vgcp.constraints.HardConstraints`, configs/constraints.yaml | test_constraints | Impl\* (interpretation: reserved budgets plus measured background load, D16; audit H1, `test_background_load.py`) |
| Eq 17 | A_Φ(s) = {a ∈ A : ρ_φ ≥ ρ_min ∀φ, c ≤ 0} | shield checks 1, 4, 8; extensions 2, 3, 5, 6, 7 only remove actions | test_eq17: hand-calculated instance, literal Eq 17 reference on a 648-action grid (soundness; gaps attributed to extensions), `test_d3_*`, `test_d12_*` | Impl\* (D2, D3, D12) |
| Eq 18 | V : S × A × Φ → {0, 1} | `VerificationShield.verify` → `Certificate.accepted` | test_shield | Impl\* (D4) |
| Assumption 2 | V = 1 ⇒ a ∈ A_Φ(s) | holds by construction **relative to T̂, d̄, π₀, c**; not for the real network | `test_shield_is_sound_wrt_literal_eq17_on_grid`, `test_acceptance_implies_every_check_passed` | Impl (model-relative only) |
| Assumption 3 | π₀ recursively feasible | π₀ checked to be in A at load and along the rollout only | `fallback_continuation` check | Later (Milestone 4) |
| Sec 2.4, Eq 21 | generative policy G_θ | – | – | Not in Stage 1 |
| Sec 2.5, Eqs 22–23 | world model W_ψ, uncertainty u_ψ | not implemented; Stage 1 has no learned model. W_ψ is not the shield's `TransitionModel` (that is T̂) | – | Later |
| Def 2 | OOD trigger u_ψ > η ⇒ fallback | not implemented: needs W_ψ (no η setting). Separate extension D12: shield check `nominal_model_domain` rejects rollouts outside T̂'s validity domain | `test_out_of_domain_rollout_rejects`, `test_d12_removes_actions_that_eq17_admits` (D12) | Later (D12 is an extension, not Def 2) |
| Sec 3, step 6 | deploy π₀ if no candidate is verified | – | – | Later (Milestone 4) |
| Eq 27 | utility U | – | – | Later (Milestone 4) |
| Eqs 28–29, 31, 33 | objectives J, δ, ε | – | – | Later (Milestone 5 metrics) |
| Constraint 1 | c(s_t, a_t) ≤ 0 a.s. | not claimed; needs Assumptions 2 and 3 on the real system | – | Later (empirical) |
| Constraint 3 | a_t = π₀ if u_ψ > η | not implemented: needs W_ψ and the closed loop (Milestone 4) | – | Later |
| Eq 42 | selection rule σ | – | – | Later (Milestone 4) |
