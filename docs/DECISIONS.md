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

---

## 2026-10-21 · SDN control channel for the Mininet backend

**Problem.** The loop must install routes and rate limits on Open vSwitch and read
counters once per 1 s slot.

**Alternatives.** (a) An OS-Ken controller application, with the loop talking to it
over REST or RPC. (b) The loop programs the switches directly with OpenFlow 1.3 via
`ovs-ofctl`, behind a small `Fabric` interface.

**Chosen.** (b). OS-Ken 4.2.2 was checked and installs and imports on this Python
3.12, so (a) remains possible.

**Why.** Routing is proactive (no packet-in handling needed), and (a) would add a
second process whose event loop, RPC latency and failures are not what this research
studies. (b) is synchronous and deterministic per slot. The `Fabric` boundary keeps
a controller a drop-in replacement.

**Consequences.** No reactive behaviour (e.g. topology discovery); the topology comes
from `configs/network.yaml`. Each `ovs-ofctl` call costs a process start, which is
counted in the measured decision and slot timing.

**Uncertainty.** Whether 1 s slots leave enough time for rule updates, counter reads
and probes on this machine is measured by the integration tests and campaign.

---

## 2026-10-21 · What the emulated network measures

**Chosen definitions** (`vgcp/emu/telemetry.py`): link rate from the upstream port's
tx counter; managed rate from the slices' forward-rule counters on that switch;
background = link rate − managed rate; offered load from the ingress rule (before the
meter); loss from the first switch after the meter to the egress (meter drops are
budget enforcement, not loss); p99 latency = p99 of 8 ping RTTs per slot / 2.

**Consequences.** A slot whose probes are all lost has unknown latency: the shield
rejects (UNKNOWN), and the experiment scores it as an infinite-latency violation.
There is no ground truth in an emulated network; Mininet results are measurements.

**Uncertainty.** Ping shares the slice's queues but is ICMP, not the slice's own
packets; RTT/2 assumes symmetric paths (true for these links).

---

## 2026-10-21 · Install order and lifecycle of the emulated network (first-run fixes)

**Problem.** The first privileged run failed all 7 integration tests
(`experiments/results/mininet-20261021T171037Z/integration.log`): s1 rejected the
first slice flow with `OFPMMFC_INVALID_METER` (`actions=meter:1,output:2`), and every
later test failed building the topology with `RTNETLINK answers: File exists` for
`bgdst-eth0`/`s5-eth7`.

**Root causes.** (1) `MininetNetwork._install` added a slice's flows and only then
its meter. An OpenFlow 1.3 switch validates the meter reference when the flow is
added. Meter *support* was not the problem: the error is "invalid meter", not "out of
meters". (2) The exception escaped `MininetNetwork.__init__` after the topology was
up. The fixture appended the network to its cleanup list only after construction
returned, and `run_trial` likewise only gets a backend after construction, so
nothing ever closed it. Mininet 2.3 creates veth pairs without deleting old ones of
the same name, so the next build collided. The first collision is the bgdst link
because Mininet builds links in sorted order. iperf3 servers started with `mnexec`
kept the dead hosts' namespaces alive and were not removed by `mn -c`. (3) The
fake fabric, the only thing the unit tests ran against, accepted flows with missing
meters, so the order bug could not show up without root.

**Alternatives.** For (1): bundle meters and flows in one OpenFlow bundle, or create
meters first. For (2): clean up only in the test fixture, or make every layer
release what it built.

**Chosen.**
* Meters are created first. The backend keeps a per-switch ledger of the meters it
  created and refuses (`FabricError`) to send a flow that references a meter missing
  on *that* switch.
* Setup checks `meter-features` on the ingress and fails clearly if the datapath has
  no meters.
* `MininetNetwork.__init__` and `MininetFabric.setup` (building with `build=False` so
  a half-built network is reachable) release everything on any failure.
* `close()` is idempotent, stops every process (terminate, then kill), stops
  Mininet, verifies nothing of the plan is left and deletes what is, collecting
  errors instead of stopping at the first one.
* Setup first deletes this plan's own leftovers: its `{switch}-eth{port}`
  interfaces, its bridges, and its iperf3/ping processes in non-root namespaces.
  These are matched by the plan's ports and addresses, so the system iperf3 service
  and anything else are untouched.
* If an iperf3 client dies, the snapshot fails instead of measuring a slot with
  less traffic than intended.
* The fake fabric rejects what OVS rejects (missing meter on flow add, adding an
  existing meter, modifying a missing one).

**Consequences.** A failure now surfaces as the first real error instead of a
cascade of collisions. Integration tests end with a leak check and fail if Mininet's
own `stop()` left anything (a forced cleanup is reported, not hidden).
`scripts/mininet_run.sh` runs the suite twice without cleanup in between, and runs
the campaign only on request.

**Uncertainty.** Verified on real Mininet on 2026-10-21 (`mininet-20261021T172242Z`):
9/9 integration tests in two consecutive passes, nothing left behind. Still
untested: an iperf3 client restart racing its server (it would now fail loudly). The
leftover removal assumes only one emulation runs at a time on the host, which is
already required because the interface names are fixed.

---

## 2026-10-22 · Telemetry and metric fixes after the first Mininet campaign

**Problem.** The audit of `mininet-20261022T110546Z` found that the measurements, not
the controller, explained most anomalies:
1. A reroute deletes and re-adds rules, and the next delta compared two different
   rules' counters: NaN, or a plausible wrong value. Example: throughput 0.0 instead
   of 2.0, reproduced by the stricter fake fabric.
2. Background = link rate − managed rate, with the managed rate counted on the
   upstream switch. At the ingress that is before the meter, so background was
   under-measured by the metered-away amount (about 22 Mbit/s in s2).
3. One NaN slot made a trial's mean `null`.
4. Loss turned NaN into 0 when the admitted rate was unknown.
5. Measured overload was reported as 0 although it cannot be observed after
   shaping.
6. The candidate generator read unknown demand and unknown background as 0.

**Chosen.**
1. Rule identity by age: OVS's per-rule `duration` must grow by the interval,
   otherwise the rule was reinstalled and its rate is its bytes over its own age
   (≥ 0.25 s), else unknown.
2. The managed rate on a→b is counted by the same rule on b, i.e. what arrived
   over the link.
3. Means skip missing slots and report `valid_slots`; aggregates report how many
   trials contributed.
4. Loss is NaN when an input is.
5. `overload_slots` is `None` with `overload_observable: false` on measured data.
6. Unknown demand keeps π₀'s budget; a link with unknown background has no room.

The fake fabric now resets counters on reinstall and reports rule ages.

**Not changed (team decisions pending).**
* Probes per slot: latency is still the max of 8.
* Rate units: scenarios give payload rates while counters count frames.
* eMBB's 1500-byte payload fragments.
* The meter passes about 1.10× its budget (cause unknown).
* Stepwise flow-counter updates (seen as 0.5×/1.5× readings).

**Uncertainty.** Verified with unit tests against the stricter fake fabric only. The
privileged integration suite and an s2 re-run on Mininet are still needed.

---

## 2026-10-22 · Eq 42 selection with an Eq 27 utility (Milestone 4, extension D20)

**Problem.** The shielded controller applied the first certified candidate in the
generator's order. Paper Eq 42 instead selects the certified candidate with the
highest discounted cumulative utility (Eq 27) over the H-step rollout.

**Chosen.**
* A new controller mode `shielded-utility` implements Eq 42 over the shield's own
  projected rollout (`VerificationShield.rollout`, Eqs 12-13).
* The world model q_ψ is replaced by the deterministic nominal model T̂, so the
  expectation is a single rollout.
* Eq 27's terms in Stage 1:
  * Q = total slice throughput;
  * E = −power, since throughput is already in Q;
  * ρ = the tightest normalized intent predicate at that step;
  * C = total reserved rate budget.
* Weights and scales live in `configs/shield.yaml` (`selection`), are validated, and
  are illustrative.
* Only certified candidates are ranked, so selection cannot weaken verification.
  Ties keep the generator's order.
* `shielded` keeps the first-certified rule, so earlier results remain reproducible
  and the two rules can be compared.

**Consequences.** Steps record `selection` and each certified candidate's predicted
return. The rollout is recomputed per certified candidate, which costs about one
extra rollout each.

**Uncertainty.**
* The weights change which certified action is chosen; they are not tuned and not
  grounded in operator preferences.
* Utility is predicted with the uncalibrated T̂, so a high predicted return is not a
  measured benefit.
