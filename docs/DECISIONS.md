# Technical decisions

Milestone 1 interpretation choices (D1-D19: paper deviations, extensions and
resolved audit findings) are in the decision register of
[milestone1_design.md](milestone1_design.md) §6. This file records the decisions
taken while building the closed loop (Milestone 2), with dates.

---

## 2026-10-21 · Context binding and the enforcement point (closes audit M3)

**Problem.** Certificates recorded the certified action and inputs, but nothing that
changes the network checked them, so a certificate could be ignored or reused.

**Alternatives.** (a) Check `authorizes(action)` only. (b) Also require the
certificate to be for the observation being acted on, and fresh. (c) Cryptographically
sign certificates.

**Chosen.** (b), in one class, `CertifiedApplier`, which is the only shielded path to
`NetworkBackend.apply`. The fallback is computed by the applier from the observation.

**Why.** (a) allows acting on a certificate computed for an older state. (c) only
matters across trust boundaries, which the prototype does not have yet.

**Consequences.** Every certified action is applied within `max_staleness_s` (2 s) of
the observation it was verified on, to that same observation.

**Uncertainty.** In-process code can still bypass the applier by calling the backend
directly; only the unshielded baselines do so, and they are named accordingly.

---

## 2026-10-21 · Selection rule for Milestone 2

**Problem.** Eq 42 selects by predicted utility, which needs the utility model of
Milestone 4.

**Alternatives.** (a) Implement Eq 42 now with a provisional utility. (b) Apply the
first certified candidate in the generator's preference order.

**Chosen.** (b).

**Why.** It isolates the effect of the shield: the shielded and unshielded controllers
share the same candidates and preferences and differ only in verification.

**Consequences.** Performance (e.g. throughput) is not optimized by the shield.

**Uncertainty.** Results may change once Eq 42 is implemented.

---

## 2026-10-21 · A simulated ground-truth backend before Mininet

**Problem.** Mininet needs root, which the development environment does not have, and
the experiment harness, metrics and controllers had to be built and tested first.

**Alternatives.** (a) Wait for Mininet. (b) Evaluate against the nominal model itself.
(c) A separate simulator with its own, deliberately different dynamics.

**Chosen.** (c), `vgcp.sim.SimulatedNetwork`.

**Why.** (b) would make every certified action look safe by construction. (c) can be
wrong in the ways real networks are: overload loss and buffers, different packet
sizes, noise, stale or missing telemetry, controller failures, actuation delay.

**Consequences.** All current results are labelled simulation; they do not establish
real-network behaviour.

**Uncertainty.** The simulator's own fidelity is unvalidated until Mininet runs.

---

## 2026-10-21 · Baselines

**Problem.** Comparing the shield only with a naive controller would flatter it.

**Chosen.** Four controllers sharing one candidate generator: shielded; unshielded
greedy (the generator's own preference); **unshielded-fitted**, whose first choice is a
conventional capacity-fitting heuristic (a strong baseline); fallback-only.

**Why.** The strong baseline tests whether the shield adds anything beyond a good
heuristic. The unshielded controllers also ask the shield in "shadow" mode (without
acting on it) so we can count unsafe actions they applied.

**Consequences / uncertainty.** Other strong baselines (e.g. a tuned admission
controller) may exist; the current results only cover these four.

---

## 2026-10-21 · How background load is measured

**Problem.** H1 needs the load of traffic outside the managed slices.

**Chosen.** Background = link's measured rate − managed slices' measured rates on that
link (port counters minus flow counters), in the simulator and in the planned
Mininet backend alike.

**Consequences.** During overload both counters see delivered (post-drop) traffic, so
the offered background is under-measured. Kept on purpose and pinned by a test.

**Uncertainty.** Whether OVS counters are precise enough at 1 s intervals is unknown
until the Mininet runs.

---

## 2026-10-21 · State-dependent fallback π₀(s), and making it the default

**Problem.** The first experiments (static π₀) showed that a background surge on the
eMBB path made π₀ itself infeasible. Because Eq 13 continues every rollout with π₀,
**no candidate could then be certified**, even one that fit; the shield deployed the
infeasible π₀ (Remark 1) for all 20 surge slots and did no better than no shield.

**Alternatives.** (a) Keep the static π₀ and report the failure. (b) Drop the π₀
continuation (deviates from Eq 13). (c) A state-dependent π₀(s), which Eq 13 allows.

**Chosen.** (c): `CapacityAwareFallbackPolicy` keeps the static action when it fits,
otherwise moves and shrinks the eMBB reservation to fit measured background. Static
stays selectable (`shield.fallback_policy`); after the ablation the default became
`capacity_aware`.

**Why.** Measured: with π₀(s) the shielded controller had 0.8 instead of 16.4
violation slots in s2 and no uncertified fallbacks; identical results elsewhere
(docs/EXPERIMENTS.md).

**Consequences.** The shield's usefulness depends strongly on the fallback design.

**Uncertainty.** π₀(s) is still **not shown to be recursively feasible**
(Assumption 3); in s3 it was uncertifiable for 20 slots.
