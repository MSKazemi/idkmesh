# R4 — Verified Stigmergic Routing

**Issue:** #97  
**Status:** Synthetic mechanism and frozen reference experiment complete

## Research question

Can a local ant-colony/stigmergic memory learn task→worker affinities from **verified outcomes**, forget stale advantages, adapt after capabilities change, and still let newcomers demonstrate value?

The experiment is intentionally limited to routing. A pheromone trace is **not** contributor authority, governance power, or evidence that a result is correct.

## Reference evidence

The frozen default and lock-in traces, readable comparison, exact generation
commands, and artifact digests are published in the
[`R4 reference report`](../../results/experiments/r4/reference-summary.md). The
committed artifact hashes and cross-runtime replay invariants are checked in
`tests/test_r4_reference.py`; byte identity is bound to the recorded Python 3.12
runtime family.

The evidence is deliberately mixed: evaporation plus exploration avoids the
permanent-pheromone lock-in failure, but Thompson sampling wins the adversarial
lock-in scenario and slightly leads realized success in the default scenario.
This is mechanism evidence, not a claim that stigmergy is the preferred router.
The issue selection, failed predecessor, and clean current-`main` continuation
are preserved in the
[`issue #97 completion record`](../conversations/2026-08-29-issue-97-reference-evidence.md).

## Governing invariant

> **Activity is not pheromone. Verification is the update gate.**

The simulator sends two separate events for every selected worker:

```text
1. activity happened
2. verified outcome arrived
```

The activity event is deliberately ignored by the stigmergic policy.

Only the verified outcome can change pheromone:

```text
verified success -> positive deposit
verified failure -> optional negative penalty
unverified activity -> exactly zero positive deposit
```

The result records:

```text
unverified_activity_events
unverified_activity_pheromone_increase
verified_success_deposit_events
verified_success_deposit_total
verified_failure_penalty_events
```

The required invariant is:

```text
unverified_activity_pheromone_increase == 0
```

This distinction is essential before any future attempt to map the idea onto GitHub/community activity.

---

# 1. Pheromone rule

For task class `a` and worker `i`, R4 maintains a trace `tau[a,i]`.

At each step, existing pheromone evaporates:

```text
tau <- max(tau_min, (1-rho) * tau)
```

After **verified** feedback:

```text
success:
  tau <- tau + success_deposit

failure:
  tau <- max(tau_min, tau - failure_penalty)
```

The routing weight is approximately:

```text
weight[a,i]
  = tau[a,i]^alpha
  * newcomer_bonus(if untried)
```

and the policy samples proportionally to these weights unless the explicit exploration floor fires.

With exploration floor `epsilon`:

```text
with probability epsilon:
  choose uniformly among eligible workers
otherwise:
  sample from pheromone weights
```

This gives three independently meaningful controls:

- `rho` — forgetting/evaporation;
- `alpha` — reinforcement strength;
- `epsilon` — guaranteed exploration.

---

# 2. Policies

R4 compares six policies on the exact same replayable task/environment trace.

## `random`

Uniform random eligible worker.

## `greedy`

Choose the highest empirical verified-success posterior mean using a simple Beta(1,1) prior.

This baseline can lock onto incumbents because it does not deliberately explore once an observed worker looks better than an unseen one.

## `thompson`

Per-task-class Thompson sampling with Beta success/failure posteriors.

This is an important conventional stochastic baseline: bio-inspired stigmergy is not assumed to outperform a bandit merely because it resembles nature.

## `stigmergy-no-evap`

- pheromone reinforcement;
- no forgetting;
- no explicit uniform exploration floor.

This is intentionally vulnerable to historical lock-in.

## `stigmergy-evap`

Adds evaporation so old verified evidence gradually loses influence.

## `stigmergy-evap-explore`

Adds both:

- evaporation;
- explicit uniform exploration floor;
- extra routing weight for untried/new worker-task pairs.

This is the main candidate adaptive policy, not a presumed winner.

---

# 3. Common-random-number outcome design

Policy comparisons should not win because they happened to receive an easier random stream.

R4 therefore generates a task trace once and uses a deterministic hash-derived outcome draw for:

```text
outcome_seed
+ step
+ worker id
+ task class
```

If two policies choose the same worker on the same task/step, they observe the same synthetic verified outcome.

The task/environment trace is hashed with SHA-256 and every policy result records the same trace digest.

This makes the experiment reproducible while allowing policies to route differently.

---

# 4. Default environment: specialization, shift, newcomers, churn

The default environment has three task classes:

```text
code
test
security
```

and several workers with different specialties.

Before the change point:

- `code-specialist` is strongest on code;
- `test-specialist` is strongest on tests;
- `security-specialist` is strongest on security;
- `generalist` is moderate across classes.

At `shift_step`, affinities change:

- the old code/test specialists effectively swap strengths;
- the security specialist degrades;
- the generalist remains stable.

Later, two newcomers appear:

- `newcomer-strong` — genuinely useful, especially for security;
- `newcomer-weak` — low quality.

The generalist also has a temporary unavailable window to introduce simple churn.

This makes the routing algorithm solve several problems at once:

```text
learn specialization
+ forget stale specialization
+ survive temporary absence
+ give newcomers trials
+ distinguish strong vs weak newcomer
```

The default environment is a descriptive stress scenario, not a causal one-factor experiment.

---

# 5. Deliberate lock-in trap

`lockin` is a separate synthetic scenario designed specifically to produce a harmful reinforcement regime.

Workers:

```text
early-incumbent
steady-backup
late-expert
```

Before the shift:

```text
early-incumbent success ~= 1.00
steady-backup    success ~= 0.55
late-expert      unavailable
```

After the shift:

```text
early-incumbent success ~= 0.05
steady-backup    success ~= 0.55
late-expert      success ~= 0.95 and becomes available
```

A no-evaporation pheromone policy can carry a large historical advantage for the now-bad incumbent, while evaporation + explicit exploration should have a mechanism to discover the late expert and forget the old route.

The test suite requires this fixture to expose harm from no-evaporation stigmergy rather than allowing the bio-inspired mechanism to be reported only in favorable regimes.

---

# 6. Metrics

Every policy reports raw machine-readable routing metrics.

## Verified outcome

- verified successes;
- overall verified-success rate;
- pre-shift verified-success rate;
- post-shift verified-success rate.

## Regret / specialization

For every step the simulator knows the synthetic success probability of every eligible worker.

It records:

```text
oracle success probability
selected worker success probability
expected regret = oracle - selected
```

Aggregate metrics include:

- cumulative expected regret;
- mean expected regret;
- optimal-assignment rate.

The oracle is for measurement only; routing policies do not get to use it.

## Adaptation

`adaptation_recovery_steps` searches the post-shift trace for the first 25-step window whose mean selected/oracle expected-quality ratio reaches at least 90%.

If no such window occurs, recovery is `null`.

This is a descriptive diagnostic rather than a formal optimal stopping criterion.

## Stale-route persistence

For task classes whose best worker changes across the shift, R4 measures the fraction of early post-shift assignments that still go to the old best route.

This helps expose historical lock-in directly.

## Concentration

- assignment entropy;
- assignment Herfindahl-Hirschman concentration (`assignment_hhi`);
- assignment counts;
- longest same-worker streak;
- longest failed same-worker lock-in streak.

High concentration can represent useful specialization or dangerous lock-in; it must be interpreted with success/regret together.

## Newcomers

- first assignment step per newcomer;
- newcomer assignment share;
- newcomer assignment count;
- newcomer availability opportunities.

A good policy should not maximize newcomer share blindly. It should provide enough opportunity to discover a strong newcomer without permanently subsidizing a weak newcomer.

## Pheromone integrity

For stigmergic policies:

- verified success deposit events/total;
- verified failure penalty events/total;
- unverified activity events;
- unverified activity pheromone increase;
- periodic full pheromone snapshots.

---

# 7. Pheromone snapshots

R4 stores full machine-readable pheromone state periodically, including at important transition steps:

- start;
- capability shift;
- newcomer arrival;
- end;
- configured snapshot interval.

This allows a contributor to audit whether a route strengthened because of verified success or remained strong only because evidence decayed too slowly.

The raw event trace separately stores per-step routing diagnostics before and after verification when event retention is enabled.

---

# 8. Why evaporation matters beyond routing

R4 is partly testing a broader IDKMesh principle:

> **Useful memory should usually have a half-life unless the environment is truly stationary.**

Permanent historical advantage can create:

- stale worker routing;
- incumbent contributor lock-in;
- outdated verifier trust;
- obsolete topology links;
- architecture choices that survive long after evidence changes.

But too much evaporation wastes durable evidence and causes repeated rediscovery.

The interesting question is not "should history exist?" It is:

```text
what evidence should persist
for how long
under which change signal
with what exploration floor?
```

R4 begins with the lowest-risk version of that question: synthetic task routing.

---

# 9. Why this is not yet a reputation system

Do **not** directly convert R4 pheromone into contributor authority, merge rights, voting power, resource ownership, or governance weight.

Routing and governance have different threat models.

Community/reputation deployment needs separate experiments for:

- Sybil attacks;
- collusion;
- reciprocal reinforcement;
- spam/activity gaming;
- identity resets;
- incumbent capture;
- newcomer fairness;
- appeals/correction;
- strategic withholding;
- malicious verification;
- transparency/privacy.

R4's strongest community lesson, if supported, may be architectural rather than numerical:

```text
reward verified durable outcomes
+ decay stale evidence
+ preserve newcomer exploration
```

not "use this exact pheromone score for people."

---

# 10. Run

Default specialization/change/newcomer scenario:

```bash
python -m randomness_lab.r4 \
  --scenario default \
  --steps 800 \
  --shift-step 400 \
  --task-seed 42 \
  --outcome-seed 4242 \
  --policy-seed 1337 \
  --output results/r4-default.json
```

Deliberate lock-in trap:

```bash
python -m randomness_lab.r4 \
  --scenario lockin \
  --steps 500 \
  --shift-step 100 \
  --task-seed 11 \
  --outcome-seed 1111 \
  --policy-seed 77 \
  --output results/r4-lockin.json
```

For smaller result files, omit per-step events while retaining aggregate metrics and pheromone snapshots:

```bash
python -m randomness_lab.r4 --scenario default --no-events --output results/r4-summary.json
```

---

# 11. Acceptance criteria mapping for #97

The initial implementation targets:

- interchangeable routing policies;
- random/greedy/Thompson baselines;
- no-evaporation stigmergy;
- evaporation stigmergy;
- evaporation + explicit exploration/newcomer bonus;
- reproducible non-stationary environment;
- reproducible newcomer arrival;
- verified-outcome-only pheromone deposits;
- raw routing diagnostics and pheromone snapshots;
- harmful lock-in fixture;
- tests proving activity cannot increase pheromone.

---

# 12. Next experiments after the first reference run

## Factor-isolate evaporation

Sweep:

```text
rho = 0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10
```

under identical capability-shift traces.

This can estimate the exploration-memory trade-off rather than comparing only two hand-picked settings.

## Factor-isolate exploration

Sweep explicit exploration floor separately from evaporation.

Measure:

- newcomer time-to-discovery;
- weak-newcomer wasted assignments;
- regret;
- routing concentration.

## Reinforcement strength

Sweep `alpha`, success-deposit size, and failure penalty.

Aggressive positive feedback may learn specialization quickly but amplify misleading early success.

## Task→verifier routing

Apply the same mechanism to choosing independent verifier bundles by failure class, but only after task→worker routing is understood.

## Community path simulation

Create an abstract contributor/task graph with Sybil/collusion attackers before any real community scoring is considered.

---

# 13. Evidence standard

A useful result is not:

> "Ant colony algorithms work in nature, therefore IDKMesh should use them."

A useful result is a map like:

```text
stationary specialization:
  stigmergy learns quickly

capability shift:
  no evaporation locks in
  moderate evaporation recovers

newcomer arrival:
  zero exploration delays discovery
  small exploration discovers strong newcomer
  excessive exploration wastes work on weak newcomer

high noise / misleading early success:
  Thompson may beat stigmergy
```

If the conventional bandit wins, that is a successful R4 finding.

The biological analogy proposes a local rule. Reproducible evidence decides whether the rule belongs in IDKMesh.
