# Mathematical Evolution Kernel

**Status:** executable v0.1 architecture  
**Date:** 2026-08-28  
**Authority:** observational / experimental; no merge or approval authority

## 1. Purpose

IDKMesh already has a rich architectural vocabulary: IDKGraph, Work Units, quality-diversity simulation, independent verification, a guarded self-evolution loop, Free Resource Mesh, and zero-cost compute routing. The weak point was the mathematical center of the live evolution observer: repository events were previously translated into small additive hand-authored score deltas.

That is useful for a first prototype, but it has three problems:

1. repeated events can push a score by construction rather than by accumulated evidence;
2. uncertainty is not represented explicitly;
3. the workflow state was normally rebuilt from the checked-in seed on a fresh Actions runner, so the observer did not truly learn across iterations.

The Mathematical Evolution Kernel turns the most useful formulas already proposed in the project into deterministic, machine-tested primitives and connects them to GitHub Actions without increasing integration authority.

The governing idea is:

```text
observe -> update uncertain beliefs -> preserve diversity -> allocate experiments
       -> compare Pareto alternatives -> test homeostasis/invariants
       -> retain evidence -> human/governance integration decision
```

No scalar score is allowed to become merge authority.

---

## 2. Bayesian evidence instead of additive declarations

For each repository-health dimension `d`, maintain a Beta belief

```text
p_d ~ Beta(alpha_d, beta_d)
```

with posterior mean

```text
mu_d = alpha_d / (alpha_d + beta_d).
```

A normalized repository event contributes signed soft evidence `e in [-1,1]` with strength `s`:

```text
alpha' = alpha + s * max(e, 0)
beta'  = beta  + s * max(-e, 0).
```

This is deliberately weaker than saying “a merged PR improved product quality by 0.012.” A merge is only evidence whose calibration must eventually be learned from downstream outcomes.

Posterior variance is

```text
Var[p] = alpha beta / ((alpha+beta)^2 (alpha+beta+1)).
```

The observer also emits conservative approximate confidence bounds. Positive dimensions use the lower bound as the cautious signal; `risk_debt` uses the upper bound.

### Why Beta beliefs

They are appropriate for a v0 kernel because they are:

- bounded in `[0,1]`;
- interpretable;
- dependency-free;
- easy to update from soft evidence;
- explicit about uncertainty;
- compatible with later Bernoulli/binomial outcome calibration.

They are not claimed to be the final model for every metric. Continuous/ordinal outcomes can later use richer distributions.

---

## 3. Reliability-weighted Bayesian/log-odds verification

Nominal verifier count is not independent evidence count. For a binary vote `v_i` from a verifier with reliability `r_i`, the information contribution is modeled as log odds

```text
ell_i = log(r_i / (1-r_i)).
```

A positive vote adds `ell_i`; a negative vote subtracts it.

If a group of size `n` has approximate within-group error correlation `rho`, use the equicorrelation effective sample size

```text
n_eff = n / (1 + (n-1) rho).
```

Each member of that group receives weight

```text
w = 1 / (1 + (n-1) rho),
```

so the group's total information weight is `n_eff` rather than `n`.

The posterior log odds become

```text
logit P(correct | votes)
  = logit P(correct)
  + sum_i w_i * sign(v_i) * log(r_i/(1-r_i)).
```

This extends the existing correlated-verifier experiments into a reusable aggregation primitive. It is still a model: group labels and `rho` are hypotheses and must be estimated/validated rather than treated as truth.

---

## 4. Pareto / NSGA-style multi-objective selection

High-level task and architecture selection should not collapse immediately to one utility number.

For candidate `i`, use a vector such as

```text
z_i = (
  impact,
  information_gain,
  unlock,
  diversity,
  -risk,
  -cost,
  -review_burden
).
```

Candidate `a` dominates candidate `b` iff `a` is no worse in every objective and strictly better in at least one.

The kernel implements:

1. fast non-dominated sorting into Pareto fronts;
2. NSGA-II-style crowding distance inside each front.

The first mechanism prevents a policy weight from hiding important trade-offs. The second prevents the frontier from collapsing around one region of objective space.

This is a natural bridge between IDKGraph task value and the existing quality-diversity simulation.

---

## 5. Graph unlock value

A small Work Unit may be valuable because it unlocks many downstream tasks.

For directed task graph distance `d(i,j)`, define

```text
Unlock(i) = sum_{j in Desc(i)} value_j * exp(-lambda * d(i,j)).
```

The kernel computes this using shortest directed distance. This gives upstream bridge tasks a measurable value without pretending graph centrality is correctness evidence.

Future IDKGraph projections can feed this directly into the Pareto vector.

---

## 6. UCB exploration for experiment-budget allocation

When several experimental strategies/agents/adapters are available, always choosing the current empirical best causes premature convergence.

The kernel implements UCB1-style allocation:

```text
UCB_i = mean_reward_i
        + c * sqrt(log(total_pulls + 1) / pulls_i).
```

An unseen arm receives infinite exploration priority.

Good uses include allocating a bounded experiment budget among:

- worker adapters;
- task-decomposition thresholds;
- maintenance policies;
- Free Resource providers;
- verification aggregation strategies;
- documentation restructuring operators.

UCB chooses what to test next. It does not grant authority to integrate the result.

---

## 7. Multiplicative weights / discrete replicator dynamics

For longer-horizon policy mixtures, use exponentiated-gradient / multiplicative weights:

```text
w_i' proportional to w_i * exp(eta * reward_i).
```

After normalization, add an exploration floor `epsilon`:

```text
x_i' = (1-epsilon) * normalized(w_i') + epsilon/K.
```

For small `eta`, this is closely related to discrete replicator dynamics: policies doing better than the population average gain mass, while the exploration floor prevents extinction from finite early evidence.

The intended use is **experimental budget share**, not constitutional authority.

---

## 8. Diversity: entropy and Jensen-Shannon divergence

### Activity entropy

For activity shares `p_i`, normalized Shannon entropy is

```text
H_norm = -sum_i p_i log2 p_i / log2 K.
```

`H_norm = 0` means observed activity is concentrated in one category. `H_norm = 1` means the observed support is uniform.

The live evolution observer tracks:

- event-type entropy;
- actor entropy.

Low entropy is a signal for possible over-concentration, not an instruction to create artificial activity.

### Behavioral diversity

For two empirical behavior/outcome distributions `P` and `Q`, use Jensen-Shannon divergence

```text
JSD(P,Q) = 1/2 KL(P || M) + 1/2 KL(Q || M),
M = (P+Q)/2.
```

With base-2 logs, `JSD in [0,1]`.

This is useful for the heterogeneous-worker milestone: two adapters are valuable when they provide different evidence/failure modes, not merely different names.

---

## 9. Homeostasis and Lyapunov-style safety

A repository should not maximize every variable. It should remain inside healthy operating ranges.

For state dimension `x_j`, target `t_j`, scale `s_j`, and importance `q_j`, define

```text
V(R) = sum_j q_j * ((x_j - t_j) / s_j)^2.
```

`V` is a Lyapunov-style diagnostic potential: lower means the measured state is closer to configured healthy target bands.

For bounded low-risk automation, a conservative condition is

```text
V_after <= V_before + tolerance
```

**in addition to** hard invariants, tests, and governance rules.

The live observer reports this condition, but does not auto-merge based on it.

This prevents a weighted scalar fitness increase from being called “improvement” when the system moves farther from important safety/homeostatic targets.

---

## 10. Persistent learning under GitHub Actions

A GitHub-hosted runner is ephemeral. Updating `state/evolution-state.json` during a run does not persist by itself.

The evolution workflow therefore uses a read-only checkpoint protocol:

```text
trusted main run N
  -> upload evolution-checkpoint-v2-N artifact

trusted main run N+1
  -> GitHub Actions API finds latest successful run from an allowlisted trusted event
  -> exact run-bound artifact + SHA-256 manifest are verified
  -> state/ledger schema and lineage invariants are verified
  -> first-party actions/download-artifact restores checkpoint-N
  -> Bayesian update
  -> upload evolution-checkpoint-v2-(N+1)
```

Security boundary:

- workflow permission remains `contents: read` + `actions: read`;
- ordinary PR runs may generate evidence artifacts but their event type is explicitly excluded from checkpoint selection;
- exact artifact names, run/head/event provenance, parent run, file sizes, and SHA-256 digests are bound in a manifest;
- a selected checkpoint that is missing, unavailable, malformed, or inconsistent fails the run rather than resetting history to seed;
- no repository file is autonomously committed;
- no issue/PR is autonomously approved or merged;
- the checked-in state remains a deterministic recovery seed;
- the bounded JSONL ledger is retained in checkpoint artifacts.

The `v2` artifact namespace is a deliberate trust-epoch boundary: legacy
checkpoints without provenance manifests are not candidates. The first v2 run
starts from the checked-in deterministic seed; later v2 runs preserve that
validated lineage.

This is real cross-iteration memory without bypassing issue #35's branch-protection gate.

---

## 11. GitHub-native control surface

### `Mathematical Evolution Kernel` workflow

On relevant pushes, PRs, manual dispatch, and a weekly schedule it:

1. compiles the kernel/scorer;
2. runs mathematical invariant tests on Python 3.11 and 3.13;
3. validates the versioned policy/state JSON;
4. executes a deterministic demonstration covering every algorithm family;
5. smoke-tests the Bayesian evolution scorer;
6. uploads replayable artifacts for 30 days;
7. publishes a GitHub job summary.

### `IDKMesh Evolution Loop`

It now:

1. observes repository events;
2. restores only allowlisted trusted-event checkpoint state whose exact artifact, manifest, and semantic invariants verify;
3. converts the event to signed soft evidence;
4. updates Bayesian beliefs;
5. computes confidence bounds, entropy, scalar diagnostic fitness, and homeostatic potential;
6. retains a bounded evidence ledger;
7. uploads the next checkpoint artifact;
8. remains read-only toward repository integration.

---

## 12. What each algorithm controls

| Layer | Algorithm | Purpose | Authority ceiling |
| --- | --- | --- | --- |
| health belief | Beta Bayesian update | accumulate uncertain evidence | observation only |
| verifier evidence | reliability log odds + effective sample size | discount correlated evidence | evidence only |
| task/architecture candidates | Pareto fronts + crowding | preserve trade-offs | recommendation |
| task graph | discounted unlock value | value prerequisite bridges | recommendation |
| experiment allocation | UCB | explore under uncertainty | bounded experiment choice |
| policy mixture | multiplicative weights | adapt budget shares | experiment budget only |
| diversity | entropy + JSD | detect concentration / heterogeneity | diagnostic |
| self-maintenance | homeostatic potential | prevent unstable metric chasing | additional gate, never sole authority |

---

## 13. Invariants

1. Mathematical scores never override schema/test/security failures.
2. A posterior is evidence, not causality.
3. Correlation metadata is not proof of independence.
4. Pareto rank is not correctness.
5. UCB/replicator weights allocate experiments, not merge rights.
6. Diversity is useful only when candidates remain viable and verifiable.
7. A Lyapunov decrease is necessary only where policy says so and is never sufficient by itself.
8. Untrusted PR state cannot become the trusted persistent evolution checkpoint.
9. Policy coefficients are versioned and reviewable.
10. No autonomous actor may propose and solely authorize the same protected change.

---

## 14. Calibration roadmap

The remaining scientific task is to replace more hand-authored evidence strength with observed outcome relationships.

A future calibration dataset should link event/action classes to delayed outcomes such as:

- regression frequency;
- verifier disagreement;
- rollback/revert rate;
- benchmark movement;
- issue re-open rate;
- reviewer burden;
- newcomer completion rate;
- time-to-verified-useful-work;
- security findings;
- correlated worker failures.

Then compare alternative models by held-out predictive performance and calibration rather than by narrative plausibility.

The target evolution is:

```text
hand-authored soft priors
 -> measured posteriors
 -> calibrated predictive models
 -> bounded policy experiments
 -> independently reviewed policy updates
```

That gives IDKMesh a mathematical learning loop without confusing optimization with governance.
