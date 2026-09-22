# Adaptive Verification Ecology (AVE)

**Status:** experimental algorithm proposal + simulator target  
**Date:** 2026-09-22  
**Scope:** routing, verifier allocation, generation backpressure, and diversity preservation for the Verified Swarm Runner / Connector Control Plane.

## 1. Why this exists

IDKMesh already has useful nature-inspired mechanisms:

- ACO/stigmergic task routing;
- homeostatic regulation of duplication/concentration;
- Quality-Diversity / MAP-Elites as a research direction;
- bandit and diversity experiments;
- queue/backpressure and verification-scaling work;
- measured verifier-correlation evidence (E017 and follow-ups).

The missing piece is a **single closed-loop trust policy** that joins those ideas around the product's strongest question:

> How should IDKMesh allocate workers and verifiers when generation is cheap, verification is scarce, and nominal reviewer count can badly overstate independent evidence?

AVE is a proposed answer. It is deliberately not a biological simulation and not a claim that software projects are organisms or markets. Biology, ecology, economics, and physics supply candidate control mechanisms. The mechanism stays only if it beats simpler baselines under matched budgets.

## 2. High-level loop

```text
WorkUnit
  |
  v
policy/risk feasibility filter
  |
  v
niche-aware worker routing
  |     |    -- entropy/temperature preserves exploration
  |    -- family occupancy penalizes monoculture
  |    -- shadow prices penalize scarce review/compute
  v
untrusted candidate
  |
  v
danger / uncertainty estimate
  |
  v
immune-style verifier portfolio
  |     |    -- known-bad probes maintain detector memory
  |    -- correlation penalty favors independent families
  |    -- risk-adaptive quorum/fan-out
  v
VerificationResult + evidence
  |
  +--> update worker evidence
  +--> update verifier evidence
  +--> update queue shadow prices
  +--> update concentration/diversity state
  |
  v
human/governance integration remains outside AVE
```

AVE is a **recommendation and resource-allocation layer**. It does not grant permissions, decide truth without verification, or merge.

## 3. Scientific inspirations and exact IDKMesh mappings

### 3.1 Adaptive immunity -> verifier memory and anomaly response

Useful engineering inspirations:

- negative selection: detectors should be tested against known "self/non-self" examples;
- clonal selection: effective detectors can receive more sampling budget, but not unlimited authority;
- immune memory: retain evidence that a verifier catches or misses known-bad probes;
- innate/danger-style signals: increase scrutiny when risk, novelty, provenance anomalies, or disagreement rise.

IDKMesh mapping:

| Immune concept | AVE object |
| --- | --- |
| antigen | candidate artifact / known-bad probe |
| detector | verifier / validator |
| memory | verifier reliability posterior and breach history |
| immune diversity | verifier-family diversity |
| danger signal | risk + uncertainty + provenance anomaly + correlated-worker signal |
| tolerance | low-risk, well-characterized work uses minimal sufficient verification |
| immune overreaction | unnecessary verification cost / false rejection |
| immune escape | defect accepted by all selected verifiers |

Important boundary: "danger theory" is used only as an engineering analogy for combining contextual anomaly signals. It is not required as a biological claim.

### 3.2 Ecology -> niches, carrying capacity, and anti-monoculture

Ecological coexistence work emphasizes that stable diversity depends on differences in niches/resource use; biodiversity can sometimes provide resilience when components respond differently to disturbances.

IDKMesh mapping:

- task classes are **niches**;
- worker/model/tool families are **species-like strategies**;
- review capacity, compute and human attention are **limiting resources**;
- repeated same-family attempts consume the same niche and create diminishing marginal evidence;
- rare but capable worker families can receive a negative-frequency-dependence bonus;
- each task has a carrying-capacity-like useful parallelism limit.

The goal is not diversity for its own sake. Diversity is valuable only when it reduces correlated failure or covers a capability niche.

### 3.3 Economics -> shadow prices for scarce verification capacity

A verifier queue is a congestion problem.

Instead of a token or cryptocurrency, AVE uses an internal **shadow price** for scarce resources.

For resource `r`:

```text
lambda_r(t+1) =
  clip(
    lambda_r(t)
    + eta_r * (utilization_r(t) - target_r),
    0,
    lambda_max
  )
```

When review demand exceeds sustainable capacity:

- `lambda_review` rises;
- low-value/high-review-cost generation becomes less attractive;
- unnecessary fan-out shrinks;
- the router favors candidates with better expected verified value per review unit;
- high-risk policy floors still prevent under-verification.

When capacity recovers, the price falls.

This is inspired by network-utility/congestion-control work using feedback and shadow prices. It is **not money** and creates no transferable asset.

### 3.4 Statistical physics -> entropy-regularized exploration

A fixed exploration rate is brittle. AVE uses a temperature-controlled distribution.

For eligible worker `a` and task `j`, define an adjusted utility `U(a,j)`.

```text
P(a -> j) =
  exp(U(a,j) / T)
  -----------------------------
  sum_k exp(U(a,k) / T)
```

Interpretation:

- high `T`: uncertainty is high -> broaden exploration;
- low `T`: evidence is mature or verification is congested -> exploit stronger routes;
- `T` is bounded; it never disables policy constraints.

A first feedback rule can be:

```text
T(t) = clip(
  T_base
  + k_u * mean_route_uncertainty
  + k_s * stagnation_signal
  - k_q * lambda_review,
  T_min,
  T_max
)
```

This is a practical use of the "free-energy" idea already discussed in `SCIENTIFIC_FOUNDATIONS.md`: quality pressure plus a controlled diversity/entropy term.

### 3.5 Bayesian/bandit learning -> learn task-family fit without freezing newcomers out

For each worker family `f` and task class `c`, maintain a posterior over verified success.

A simple Beta-Bernoulli starting point:

```text
theta_(f,c) ~ Beta(alpha_(f,c), beta_(f,c))
```

A router can sample `theta` (Thompson-style) or use posterior mean + uncertainty.

Updates must use retained verification/outcome evidence, not raw activity volume.

This makes the routing question:

> Which worker family should be tried for this task class, given observed verified outcomes and uncertainty?

rather than:

> Which provider has the biggest model?

### 3.6 Quality-Diversity -> preserve proven specialists, not one global winner

MAP-Elites is useful as a model for an archive indexed by meaningful behavioral descriptors.

A future AVE archive can index candidate worker/verifier strategies by dimensions such as:

- task class;
- risk class;
- latency band;
- cost band;
- local vs hosted execution;
- model/agent family;
- verifier-family composition;
- network/no-network execution;
- context size.

Each cell retains one or a few high-performing **verified** configurations.

This prevents a globally strong provider from erasing specialized combinations that are better for a minority of tasks.

## 4. Core AVE state

### 4.1 WorkUnit state

For WorkUnit `w`:

- task class;
- risk/security class;
- expected impact;
- information gain;
- deadline/latency tolerance;
- review cost estimate;
- compute estimate;
- source novelty / out-of-distribution signal;
- useful parallelism limit;
- required capabilities;
- required verifier classes;
- minimum human checkpoint policy.

### 4.2 Worker state

For worker/agent `a`:

- connector/driver;
- family labels (model, agent, toolchain, operator where policy permits);
- task capabilities;
- task-family posterior;
- recent load;
- cost/latency distribution;
- evidence freshness;
- failure/correlation fingerprint;
- permissions and execution boundary.

### 4.3 Verifier state

For verifier `v`:

- verifier family;
- supported validator classes;
- known-bad probe history;
- sensitivity/specificity or task-appropriate reliability estimates;
- pairwise/group error correlation;
- review/resource cost;
- queue load;
- evidence freshness;
- independence constraints.

### 4.4 Global control state

- review shadow price;
- compute shadow price;
- optional human-attention shadow price;
- task/family occupancy;
- exploration temperature;
- recent defect escape rate;
- recent false-reject rate;
- queue utilization;
- coverage/stagnation indicators.

## 5. Routing objective

After the hard policy/permission filter, a first worker-task utility is:

```text
U_worker(a,w) =
    Value(w)
  * Capability(a,w)
  * SampledReliability(a, class(w))
  * IndependenceBonus(a,w)
  * NicheBonus(a,w)
  / (
      1
      + lambda_review * ExpectedReviewCost(a,w)
      + lambda_compute * ExpectedComputeCost(a,w)
      + RiskFriction(a,w)
    )
```

Terms:

- `Value`: impact + information gain;
- `Capability`: declared/observed task fit;
- `SampledReliability`: posterior sample/estimate, preserving uncertainty;
- `IndependenceBonus`: higher for workers whose failures differ from active attempts;
- `NicheBonus`: negative-frequency dependence / anti-monoculture;
- shadow prices: adaptive scarcity pressure.

The final choice is entropy-regularized, not deterministic greedy selection.

## 6. Ecological occupancy rule

Let `n_(f,c)` be active attempts by worker family `f` in task class `c`.

A simple negative-frequency term is:

```text
NicheBonus(f,c) =
  1 / (1 + n_(f,c))^gamma
```

Add a global family-share cap:

```text
share_f <= K_f(risk_class)
```

unless no feasible alternative exists.

For high-risk work, the allowed concentration can be stricter.

This is not a fairness score or contributor worth score. It is a correlated-failure control.

## 7. Immune-style verifier allocation

### 7.1 Known-bad probes

IDKMesh already has seeded known-bad candidate logic in the gate-audit direction.

AVE makes this an online control input.

For verifier `v`:

```text
probe_reliability_v ~ Beta(a_v, b_v)
```

On a known-bad probe:

- correctly reject -> `a_v += 1`;
- incorrectly accept -> `b_v += 1`.

A verifier that repeatedly accepts known-bad probes is not silently trusted because of nominal status.

### 7.2 Danger score

A first bounded score:

```text
D(w,candidate) =
    q_r * Risk(w)
  + q_u * RouteUncertainty(worker, w)
  + q_n * Novelty(w, candidate)
  + q_p * ProvenanceAnomaly(candidate)
  + q_c * CorrelatedWorkerPressure(w)
  + q_h * HistoricalEscapeRate(task_class)
```

`D` maps to a minimum verifier budget.

Example policy:

```text
D < 0.30       -> minimum 1 verifier
0.30 <= D<0.65 -> minimum 2 verifier families
D >= 0.65      -> minimum 3 verifier families + human checkpoint if policy requires
```

The exact thresholds are experimental.

### 7.3 Verifier portfolio selection

Select verifiers greedily or through a small combinatorial optimizer to maximize:

```text
VerifierValue(S) =
    ExpectedDetection(S)
  + Diversity(S)
  + Coverage(S)
  - lambda_review * Cost(S)
  - CorrelationPenalty(S)
```

subject to:

- required validator IDs;
- worker/verifier identity separation;
- risk-class minimums;
- queue/capacity limits;
- provider/operator separation where policy demands it.

This is the component most directly tied to E017: **N verifiers are useful only if their joint evidence is stronger than one verifier's evidence.**

## 8. Risk-adaptive quorum

Do not use one permanent majority rule.

For a verifier portfolio `S`, the aggregation rule should depend on:

- sidedness of errors;
- measured false-accept vs false-reject costs;
- correlation;
- task risk;
- known unanimity/common-mode floor.

E017 showed that for the measured one-sided partial-test panel, majority was a poor rule and unanimity-to-accept substantially reduced errors. That result must not be generalized to arbitrary two-sided verifiers.

AVE therefore treats quorum as a policy selected from evidence, not a constant.

## 9. Economic generation backpressure

Generation should slow when verification cannot keep up.

Let:

```text
rho_verify =
  arriving_verification_work /
  effective_verification_capacity
```

When `rho_verify > 1` persistently:

- raise `lambda_review`;
- reduce optional generation fan-out;
- stop redundant same-family attempts first;
- preserve high-risk minimum verification;
- increase human escalation only for high information-value decisions;
- surface "verification debt" in the GUI.

This is preferable to producing an ever-growing queue of untrusted candidates.

## 10. Product integration points

### Connector Control Plane

Add optional policy hooks, not vendor-specific logic:

```text
route(work_unit, eligible_connectors, evidence_state) -> RouteDecision
select_verifiers(candidate, evaluator_requirements, evidence_state) -> VerificationPlan
update(outcome) -> EvidenceStateDelta
```

The connector kernel still owns:

- connector registry;
- capabilities;
- health;
- secret refs;
- run state.

AVE consumes normalized connector metadata and produces recommendations.

### WorkUnit

Use existing fields where possible. Do not add new schema fields until an implementation proves they are necessary.

Potential future fields/extensions:

- task_class;
- uncertainty/novelty hints;
- expected human-review budget;
- minimum verifier-family diversity;
- optional useful parallelism cap.

### EvaluatorPlan

AVE should generate or help select an EvaluatorPlan, but the plan remains verifier-owned and content-bound.

A router must not weaken:

- exact WorkUnit binding;
- source revision binding;
- required validator coverage;
- worker/verifier identity separation.

### gate-audit

The current gate-audit surface can become the first measurement input for AVE:

```text
gate-audit output
 -> measured verifier correlation
 -> effective panel size / breach evidence
 -> AVE verifier-family state
 -> future verifier allocation
```

This creates a clean product progression from today's tool to the future control plane.

### GUI

Show the control state directly:

- nominal vs effective verifier count;
- current review shadow price;
- verification queue utilization;
- worker-family concentration;
- verifier-family concentration;
- exploration temperature;
- known-bad probe breach rate;
- why a worker/verifier was selected;
- what policy floor prevented cheaper routing;
- where no independent verifier is currently available.

## 11. First synthetic experiment

Compare under equal workloads and seeds:

1. **capability-static**
   - greedy capability routing;
   - one fixed verifier;
   - no memory;
   - no backpressure.

2. **diversity-static**
   - same workload;
   - family-concentration penalty;
   - fixed two-family verifier allocation;
   - no learning/backpressure.

3. **AVE**
   - posterior routing;
   - niche penalty;
   - entropy temperature;
   - known-bad probe memory;
   - correlation-aware verifier portfolio;
   - shadow-price backpressure;
   - risk-adaptive verification.

### Environment controls

Sweep:

- worker-family correlation;
- verifier-family correlation;
- task risk mix;
- reviewer capacity;
- provider outages;
- task distribution shift;
- quality gap between dominant and minority worker families;
- known-bad probe frequency;
- human-review cost.

### Metrics

Report a Pareto vector, not one permanent score:

- true verified utility;
- escaped defects;
- false rejects;
- review cost;
- compute cost;
- human-attention proxy;
- review queue utilization;
- task coverage;
- worker-family concentration;
- verifier-family concentration;
- effective verifier count;
- probe breach rate;
- routing regret;
- recovery after distribution shift.

## 12. Falsification criteria

AVE should be rejected or simplified if, under matched budgets:

- it does not reduce escaped defects;
- it only improves safety by spending much more review;
- static capability routing dominates it on utility, defects, and cost;
- diversity pressure preserves weak workers without reducing correlated failure;
- shadow prices create starvation or unacceptable latency;
- known-bad probes fail to predict real verifier failures;
- entropy exploration adds cost without improving adaptation;
- the combined controller is worse than one simpler component alone.

A successful result is a reproducible **Pareto improvement**, not merely a more complex algorithm.

## 13. Development slices

### AVE-0 — simulator and ablations

- standard-library-only simulator under `sim/`;
- deterministic seeds;
- static capability / static diversity / AVE baselines;
- unit tests;
- JSON report;
- no production routing change.

### AVE-1 — measurement adapters

- define a normalized evidence record from:
  - gate-audit;
  - VerificationResult;
  - ResultManifest;
  - post-integration outcome;
- no autonomy.

### AVE-2 — dry-run router

- integrate with Connector Control Plane routing as a dry-run explanation;
- no dispatch authority;
- compare proposed route against current deterministic router.

### AVE-3 — verifier-plan recommender

- propose verifier families and minimum fan-out;
- produce explanation and expected review cost;
- human/policy still approves the EvaluatorPlan.

### AVE-4 — bounded live cohort

- 10-30 real WorkUnits;
- at least two materially different worker families;
- at least two verifier families;
- retain all candidates and negative outcomes;
- compare against frozen baseline policy.

### AVE-5 — feedback activation

Only after the cohort shows benefit:

- allow evidence to update routing posteriors;
- allow review shadow price to reduce optional fan-out;
- keep risk floors and merge authority unchanged.

## 14. Safety and governance boundaries

AVE MUST NOT:

- convert popularity into trust;
- treat provider/model identity as proof of independence;
- use hidden personal attributes;
- infer contributor worth;
- lower a WorkUnit's mandatory validator set;
- let a worker select or modify its own hidden evaluator;
- silently change routing policy;
- automatically merge;
- introduce a token/economic reward system;
- claim biological optimality.

Every policy update must be inspectable and replayable.

## 15. Research references

Primary external inspirations:

- Mouret, J.-B. and Clune, J. (2015), **Illuminating search spaces by mapping elites**: https://arxiv.org/abs/1504.04909
- Kelly, F. P., Maulloo, A. K., and Tan, D. K. H. (1998), **Rate control for communication networks: shadow prices, proportional fairness and stability**: https://www.statslab.cam.ac.uk/~fpk1/rate.html
- Greensmith, J., Aickelin, U., and Cayzer, S., immune-inspired anomaly/dendritic-cell algorithm work, summarized in Springer proceedings: https://link.springer.com/book/10.1007/11536444
- artificial immune-system literature on negative selection and immune-inspired anomaly detection: https://link.springer.com/book/10.1007/978-3-642-33757-4
- Nature overview of biodiversity and stability / insurance mechanisms: https://www.nature.com/scitable/knowledge/library/biodiversity-and-ecosystem-stability-17059965/
- Levine, J. M. and HilleRisLambers, J. (2009), **The importance of niches for the maintenance of species diversity**: https://www.nature.com/articles/nature08251

Repository evidence and foundations:

- `SCIENTIFIC_FOUNDATIONS.md`
- `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md`
- `docs/algorithms/HOMEOSTATIC_STIGMERGY_ROUTING.md`
- `experiments/E017-item-difficulty-and-quorum.md`
- `docs/research/EVALUATOR_PLAN_BINDING.md`
- `docs/architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md`
- issue #22 — coherent systems from vague goals
- issue #30 — stochastic diversity / correlated errors
- issue #97 — stigmergic verified-outcome routing
