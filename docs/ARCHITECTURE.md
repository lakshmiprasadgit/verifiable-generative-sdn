# Architecture

A research prototype of the paper's verifiable control loop (Sec 3). Stage 1 uses
conventional components where the paper has learned ones: heuristics instead of the
generative policy G_θ, an analytic model T̂ instead of the world model W_ψ.

## Control loop, one slot

```
             ┌──────────────────────── NetworkBackend ────────────────────────┐
             │  SimulatedNetwork (no root)        MininetNetwork (needs root)  │
             └──┬─────────────────────────────────────────────▲──────────────┘
     observe()  │ Observation(t, s_t, d_t, now)                │ apply(a)  (only via the applier)
                ▼                                              │
     ┌──────────────────────┐   candidates (ranked)   ┌────────┴────────────┐
     │ CandidateGenerator   │ ──────────────────────▶ │  Controller         │
     │ heuristics (≈ G_θ)   │                         │  shielded / baselines│
     └──────────────────────┘                         └──┬──────────▲───────┘
                                       verify(s,d,a,now) │          │ Certificate
                                                         ▼          │
                                          ┌─────────────────────────┴──┐
                                          │ VerificationShield (V)     │
                                          │ measurement validity       │
                                          │ c(s,a) ≤ 0                 │
                                          │ rollout: T̂, d̄, π₀(s) (Eq 12-13)
                                          │ STL robustness ≥ ρ_min (Eq 14,17)
                                          └────────────────────────────┘
                                                         │ first certified candidate
                                                         ▼   (else π₀(s_t), Remark 1)
                                          ┌────────────────────────────┐
                                          │ CertifiedApplier           │  the only shielded
                                          │ authorizes(a)? same obs?   │  path to the network
                                          │ certificate fresh?         │
                                          └────────────────────────────┘
```

After `apply`, the backend advances one slot; the next `observe()` is the
post-action measurement. Experiments score the ground truth of that next slot.

## Components

| Component | Code | Role | Paper |
|---|---|---|---|
| State, demand, action | `vgcp/state.py`, `vgcp/action.py` | named, bounded measurements with timestamps; immutable actions | Eqs 1-3 |
| Configuration | `vgcp/config.py`, `configs/` | strict YAML; every threshold lives here | – |
| Hard constraints | `vgcp/constraints.py` | c(s,a): capacity incl. measured background load, flow table, minimum budgets, routing validity | Eq 16 |
| STL | `vgcp/stl/` | parser, robustness, normalized predicates | Eqs 5-11 |
| Nominal model, forecast, fallback | `vgcp/models/` | T̂ (analytic, uncalibrated), upper-bound d̄, π₀ static or capacity-aware | Eqs 12-13 |
| Verification shield | `vgcp/shield.py` | V, certificates bound to action and inputs | Eqs 14, 17-18 |
| Loop | `vgcp/loop/` | interfaces, candidate generator, controllers, enforcing applier | Sec 3 |
| Simulated network | `vgcp/sim/` | ground truth for experiments; deliberately differs from T̂ | – |
| Emulated network | `vgcp/emu/` | Mininet + Open vSwitch: plan, OpenFlow 1.3 rules and meters, counter telemetry, traffic and probes; only `MininetFabric` needs root | – |
| Experiments | `vgcp/experiments/`, `experiments/` | scenarios × controllers × seeds, raw logs, summaries | – |

## Boundaries that keep claims honest

* **Observation → state.** Telemetry becomes timestamped measurements. Missing or
  frozen telemetry stays missing or old; the shield rejects it rather than guessing.
* **Shield → certificate.** A certificate states which action, which observation and
  which time it certifies. It is evidence, not enforcement.
* **Certificate → network.** `CertifiedApplier` is the enforcement point: it applies
  an action only if the certificate authorizes exactly that action for the
  observation being acted on, within the staleness limit. Only π₀(s_t), computed by
  the applier itself, may bypass certification (Remark 1), and whether π₀ was
  itself certifiable is recorded every time.
* **Model vs world.** The shield predicts with T̂; the simulator (and later Mininet)
  is the world. They are separate code with separate parameters, so a certificate
  can be wrong, and the experiments measure how often it is.

## Timing assumption

Eq 13 applies the candidate action at k = 0 and π₀ from k = 1. Intents are written
`G[1,10] p`, so the candidate's predicted effect (first visible at k = 1) is inside
the checked window. If the network applies actions late (actuation delay), the real
effect falls outside what was checked; scenario s6 measures this.

## Emulated network (vgcp/emu)

```
EmulationPlan (pure)  ──▶ MininetFabric (root): Mininet topology, ovs-ofctl, iperf3, ping
      │                        ▲
      ▼                        │ Fabric interface (unit-tested with a fake)
OpenFlow rules / meters ──▶ MininetNetwork (NetworkBackend): one real-time slot per advance()
counter parsers         ──▶ telemetry: counters → measured state (background = port − flows)
```

Per traffic class (each slice, plus background), proactive forward and reverse rules
on every switch of its path; slices are metered at the ingress switch. Link power
actions bring both ends of a link down with `mod-port`.
