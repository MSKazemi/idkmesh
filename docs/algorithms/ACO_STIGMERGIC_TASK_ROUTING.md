# ACO Stigmergic Task Routing for IDKMesh

**Status:** Experimental algorithm proposal.

## Why this biological algorithm

If IDKMesh adds one biology-inspired algorithm as an executable coordination primitive, a strong candidate is **Ant Colony Optimization (ACO)**.

Ant colonies coordinate without a central planner by leaving local environmental traces (pheromones). Useful routes become easier to rediscover; unused traces decay. IDKMesh has a natural equivalent: issues, Work Units, evidence, pull requests, reproductions, reviews, benchmarks, and verified descendants are public traces that future humans/agents can observe.

The engineering hypothesis is:

> Verified useful work should leave a decaying stigmergic signal that increases the probability that compatible future contributors discover and select related high-value work, while congestion, review load, risk, and herding reduce that probability.

This is an experiment, not a claim that open-source communities literally behave like ants.

---

## 1. Core state

For each currently selectable task or Work Unit `j`, maintain a pheromone-like scalar:

`tau_j(t) >= 0`

`tau_j` is **not reputation and not priority by fiat**. It is a decaying public signal representing accumulated evidence that useful descendants have recently emerged from that work path.

For each worker/agent `a` and task `j`, compute a local heuristic desirability:

`eta_(a,j)(t)`.

The worker can then probabilistically select among feasible tasks rather than always choosing the globally highest score.

---

## 2. Data required

### Task / Work Unit data

Each candidate task `j` should expose or estimate:

- `impact_j` — expected project/community value if completed;
- `information_gain_j` — how much uncertainty the work may reduce;
- `risk_j` — security/integration/governance risk;
- `review_cost_j` — expected scarce reviewer effort;
- `queue_load_j` — current number of active attempts/reviews;
- `freshness_j` — time relevance or decay-adjusted urgency;
- `parallel_limit_j` — useful maximum number of simultaneous attempts;
- `required_capabilities_j` — skills/tools/resources needed;
- `dependencies_j` — blocking Work Units or evidence;
- `community_accessibility_j` — newcomer legibility / boundedness.

### Worker / agent data

For candidate worker `a`:

- `capabilities_a`;
- `current_load_a`;
- `reliability_uncertainty_a` (preferably a posterior/interval, not one opaque score);
- `independence_profile_a` — model family, method, organization, toolchain, or other correlation signals where relevant;
- `permissions_a` / security boundary.

Worker identity is not required for the mathematics; privacy-preserving or pseudonymous capability descriptors can be used where appropriate.

### Evidence data

After work is attempted:

- parent task / Work Unit;
- descendant artifact or PR;
- verification status;
- verifier independence/diversity;
- quality/evidence score;
- reviewer minutes;
- compute/resource cost;
- post-integration defects/regressions where observable;
- durability / retention signal after a time window;
- whether the result created another independently useful Work Unit or contribution opportunity.

Only evidence-backed outcomes should create strong positive pheromone deposits.

---

## 3. Local desirability formula

For worker `a` and feasible task `j`, define a bounded heuristic:

`eta_(a,j) = (I_j * G_j * S_(a,j) * D_(a,j) * F_j * A_j) / ((1 + H_j) * (1 + L_j) * (1 + X_j))`

where:

- `I_j` = normalized impact;
- `G_j` = expected information gain;
- `S_(a,j)` = worker-task capability match;
- `D_(a,j)` = diversity / independence bonus relative to current attempts;
- `F_j` = freshness;
- `A_j` = accessibility / boundedness;
- `H_j` = expected human review cost;
- `L_j` = congestion / current queue load;
- `X_j` = risk / execution friction.

All positive components should be normalized to stable ranges (for example `[epsilon, 1]`) before multiplication.

The important IDKMesh-specific term is `D_(a,j)`: ten nearly identical agents should not look ten times more desirable than one independent approach.

---

## 4. Stigmergic task-selection probability

For a worker `a`, let `F_a(t)` be the set of tasks currently feasible under dependencies, permissions, resource limits, and policy.

Choose task `j` with probability:

`P(a -> j | t) = [tau_j(t)^alpha * eta_(a,j)(t)^beta] / sum_(k in F_a(t)) [tau_k(t)^alpha * eta_(a,k)(t)^beta]`

Parameters:

- `alpha >= 0` — strength of collective historical evidence;
- `beta >= 0` — strength of current local fit;
- low `alpha` preserves exploration;
- high `alpha` creates stronger social proof / path reinforcement;
- high `beta` makes selection more capability- and context-driven.

For IDKMesh bootstrap experiments, prefer moderate `beta` and conservative `alpha` to avoid early lock-in from tiny samples.

A minimum exploration floor should ensure that low-pheromone tasks remain discoverable:

`tau_j := max(tau_min, tau_j)`.

---

## 5. Pheromone update

The basic biological ACO update becomes:

`tau_j(t+1) = clip((1-rho) * tau_j(t) + Deposit_j(t) - Penalty_j(t), tau_min, tau_max)`

where:

- `rho in (0,1)` is evaporation;
- `tau_min` prevents permanent starvation;
- `tau_max` prevents runaway positive feedback.

### Verified-evidence deposit

For each verified descendant `e` of task `j`:

`DeltaTau_(e,j) = (Q_e * V_e * D_e * U_e) / (1 + H_e + C_e)`

where:

- `Q_e` = independently verified quality/usefulness;
- `V_e` = verification strength / reproducibility;
- `D_e` = diversity / independent-information contribution;
- `U_e` = durability or descendant-creation value;
- `H_e` = human review cost;
- `C_e` = compute/resource cost after normalization.

Then:

`Deposit_j(t) = sum_e DeltaTau_(e,j)`.

This means an inexpensive, independently verified contribution that creates useful follow-up work deposits more signal than a high-volume but weakly verified artifact.

### Congestion / failure penalty

A simple bounded penalty can be:

`Penalty_j = kappa_1 * Overload_j + kappa_2 * Defect_j + kappa_3 * Correlation_j`

where:

- `Overload_j` rises when active attempts or review backlog exceed useful capacity;
- `Defect_j` reflects verified regressions/failures;
- `Correlation_j` reflects redundant, highly correlated attempts.

A failed experiment should not necessarily receive a large penalty if it produced valuable information. Information gain belongs in the evidence evaluation.

---

## 6. Anti-herding rule

Classic ACO can converge too strongly on one path. IDKMesh needs persistent diversity.

Use at least three controls:

1. pheromone evaporation (`rho`);
2. lower/upper pheromone bounds (`tau_min`, `tau_max`);
3. a diversity/congestion term in `eta_(a,j)`.

A useful congestion multiplier is:

`C_j = 1 / (1 + n_j)^gamma`

where `n_j` is the number of currently active correlated attempts.

Then replace:

`eta_(a,j) <- eta_(a,j) * C_j`.

This naturally pushes later workers toward neglected tasks or independent approaches when one path becomes crowded.

---

## 7. GitHub-native mapping

A first GitHub implementation does not need a separate distributed database.

| Biological ACO concept | IDKMesh/GitHub equivalent |
| --- | --- |
| ant | human or AI worker |
| path | task / Work Unit / evidence route |
| pheromone | decaying evidence-backed task signal |
| food found | verified useful artifact/descendant |
| pheromone deposit | verified outcome score |
| evaporation | time decay |
| crowded trail | too many active/correlated attempts |
| colony exploration | probabilistic assignment / discovery |
| environmental constraint | permissions, dependencies, review capacity, risk |

Possible storage for an early prototype:

- a machine-readable JSON/YAML state artifact committed/generated from repository metadata; or
- one GitHub issue/status artifact maintained by a metadata-only workflow.

The pheromone value should be reproducible from public evidence wherever possible.

---

## 8. Minimal algorithm

For each routing epoch:

```text
1. Read feasible tasks and current evidence state.
2. Evaporate all pheromone values.
3. For newly verified descendants, deposit evidence-weighted pheromone.
4. Apply bounded penalties for overload, regressions, and correlated duplication.
5. For each available worker:
      a. filter tasks by dependency, permission, risk, and resource constraints;
      b. compute worker-task heuristic eta;
      c. compute probabilistic ACO selection P(a -> j);
      d. sample or recommend a task;
      e. preserve a non-zero exploration probability.
6. Do not treat selection as authorization to merge or bypass verification.
7. Record outcome/evidence for the next epoch.
```

The algorithm can recommend work; canonical acceptance remains governed by IDKMesh verification and human/policy gates.

---

## 9. First falsifiable experiment

Compare four task-routing strategies on the same bounded task pool:

1. random feasible routing;
2. greedy highest estimated value;
3. capability-only matching;
4. ACO stigmergic routing with evaporation + diversity/congestion penalty.

Use a mixture of humans/agents or a simulator with heterogeneous workers.

Measure:

- verified useful artifacts per unit of compute;
- verified useful artifacts per reviewer minute;
- task completion latency;
- review queue size;
- abandoned work;
- duplicate/correlated attempts;
- diversity of successful approaches;
- number of neglected but valuable tasks;
- escaped defects;
- newcomer task-selection success where applicable.

### Falsification criterion

Do **not** adopt ACO merely because it sounds biologically elegant.

ACO should be considered useful only if, across repeated runs, it improves a predeclared multi-objective outcome such as:

`VerifiedUtility / (HumanAttention + ComputeCost)`

without materially worsening defects, concentration, accessibility, or review backlog compared with simpler baselines.

---

## 10. Safety and governance constraints

- Pheromone is a routing signal, not truth.
- Popularity, stars, reactions, or raw comments must not directly create strong deposits.
- A worker must not gain permissions from pheromone.
- ACO must not bypass independent verification.
- Security/governance changes should remain outside autonomous routing until separately authorized.
- Contributions from many correlated agents should receive diminishing diversity credit.
- Parameters (`alpha`, `beta`, `rho`, bounds, penalty weights) should be versioned and changed through evidence, not hidden tuning.
- Keep an explicit random/exploration component so minority hypotheses and novel approaches remain reachable.

---

## 11. Why this is particularly suitable for IDKMesh

ACO operationalizes several existing IDKMesh principles in one small mechanism:

- **stigmergy:** useful work leaves public coordination traces;
- **decentralization:** no global planner must assign every task;
- **memory with forgetting:** evidence persists but decays;
- **diversity:** congestion/correlation can push workers toward alternative paths;
- **verification-first selection:** only evidence-backed outcomes strongly reinforce routes;
- **bounded self-evolution:** routing behavior adapts from observed outcomes without automatically changing constitutional rules;
- **community accessibility:** bounded, legible tasks can receive an explicit accessibility advantage.

The most important idea is not "copy ants." It is:

> Convert verified outcomes into decaying public coordination signals, then let many independent actors probabilistically follow or challenge those signals under explicit capacity and diversity constraints.
