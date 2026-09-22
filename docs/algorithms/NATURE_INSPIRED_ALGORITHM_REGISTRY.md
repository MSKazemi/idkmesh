# Nature-, Economy-, and Physics-Inspired Algorithm Registry

**Status:** current research registry  
**Date:** 2026-09-22  
**Purpose:** keep cross-disciplinary mechanisms attached to concrete IDKMesh problems, evidence, and promotion gates.

## Core rule

IDKMesh borrows **mechanisms**, not prestige or metaphors.

A proposal belongs in the architecture only when it has:

1. a concrete IDKMesh state variable;
2. an explicit mechanism/equation;
3. a simpler baseline;
4. a falsifiable prediction;
5. resource and human-attention accounting;
6. a clear authority boundary;
7. retained negative as well as positive evidence.

Nature-inspired policy never overrides constitutional constraints such as:

- WorkUnit scope and permissions;
- resource/compute admission;
- the repository project-spend ceiling;
- evaluator sovereignty and validator coverage;
- independent verification;
- explicit human/governance integration authority.

## Maturity scale

| Level | Meaning |
| --- | --- |
| **N0 — inspiration** | idea documented; no executable mechanism |
| **N1 — executable synthetic** | deterministic simulator/tests exist |
| **N2 — retained synthetic evidence** | comparative result retained with limitations |
| **N3 — real dry-run** | observes or recommends against real project data but cannot actuate |
| **N4 — bounded live cohort** | limited actuation behind existing policy/permission gates |
| **N5 — production-eligible** | repeated evidence, rollback, monitoring, and governance support promotion |

No mechanism should skip levels merely because its scientific source is well established. A mechanism can be valid in biology/economics/physics and still be wrong for IDKMesh.

## Active mechanisms

| Mechanism | Inspiration | IDKMesh subsystem | Maturity | Current evidence / artifact | Promotion question |
| --- | --- | --- | --- | --- | --- |
| Verified stigmergy / ACO | ant-colony pheromone trails | task / WorkUnit routing | **N2** | `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md`, E014 | does verified trace memory beat simpler routing after charging for diversity and review? |
| Homeostatic stigmergy | density-dependent biological regulation + feedback control | task routing / duplication control | **N2** | `docs/algorithms/HOMEOSTATIC_STIGMERGY_ROUTING.md` + simulator/tests | does adaptive diversity pressure improve the Pareto frontier over fixed ACO/capability routing? |
| Quality-Diversity / MAP-Elites | evolution/ecological niches | architecture / worker-policy archive | **N0/N1** | issue #22 and research design | can multiple verified specialists be preserved without keeping inferior variants for diversity alone? |
| Adaptive Verification Ecology (AVE) | immunity + ecology + congestion economics + entropy | worker/verifier allocation and generation backpressure | **N1/N2 research branch** | PR #622, issues #621, AVE-0/1/2 | which smallest subset reduces correlated/high-risk escape under matched review budgets? |
| Verifier-family diversity | ecological niche separation / portfolio diversification | verifier selection | **N1/N2 research branch** | AVE ablations + E017 motivation | does family diversity add independent evidence rather than nominal variety? |
| Known-bad verifier probes | artificial immunity / adversarial testing | gate audit and verifier diagnostics | **N2 diagnostic; not trust authority** | gate-audit direction, AVE probe tests | do probe results predict live verifier failures on representative tasks? |
| Review shadow price | congestion pricing / network utility | verification queue and optional fan-out | **N1/N2** | AVE + verification-debt/backpressure work | does a scarcity signal control verification debt without starving important work? |
| Entropy / temperature exploration | statistical mechanics / entropy regularization | routing exploration | **N1** | AVE and scientific foundations | does adaptive exploration improve recovery from shift enough to pay its cost? |
| Physarum conductance routing | slime-mold adaptive transport networks | admitted multi-node compute/federation paths | **N1/N2 research branch** | PR #631, issue #630, PHY-0/1 | does adaptive conductance outperform strong change-aware/failover baselines across varied failure regimes? |
| Replicator-mutator policy weights | evolutionary dynamics | ACE community-growth strategy controller | **N1 offline** | issue #57 / ACE controller design | do strategy weights improve verified descendants per reviewer/maintainer attention? |
| Carrying-capacity governor | population ecology / logistic regulation | community/reviewer growth | **N1** | ACE design | does growth stop before reviewer load becomes the bottleneck? |
| Verification backpressure | queueing/control theory | generation vs verification capacity | **N2** | roadmap, ADR-0007 and verification-scaling research | can verification debt be bounded while preserving high-value throughput? |

## Diagnostic/research mechanisms not yet promoted

| Mechanism | Potential use | Current decision |
| --- | --- | --- |
| Percolation thresholds | predict fragmentation under node/provider loss | **N0** — simulation/observability candidate for multi-machine stage |
| Spectral connectivity / graph Laplacian | detect weak links, partitions, slow information mixing | **N0** — use as diagnostics before allowing it to influence scheduling |
| Epidemic/contagion models | malware/bad-evidence propagation and containment | **N0** — security simulation only |
| Simulated annealing | task partitioning, test portfolio, architecture search | **N0** — compare to MILP/bandit/evolutionary baselines first |
| Free-energy objective | explicit quality/cost vs useful-diversity trade-off | **N0/N1 research concept** — never replace the underlying metric vector with one permanent scalar |
| Reaction-diffusion / morphogenesis | decentralized specialization of cells/agents | **HOLD** — no demonstrated gap that requires it yet |
| Predator-prey dynamics | generation-verification balance | **HOLD** — current queue/backpressure/AVE mechanisms already address this; add only if they fail in a measurable regime |
| Neural/homeostatic plasticity | adaptive routing weights | **HOLD** — likely overlaps bandit/controller machinery |
| Genetic/evolutionary mutation | generate architectures/policies | **proposal-only** — randomness may propose; independent verification still decides acceptance |
| Blockchain/token economics | cross-org settlement / incentives | **not a trust mechanism** — existing project decisions require a concrete demonstrated settlement need first |
| Quantum-inspired optimization | constrained routing/partitioning | **optional research** — conventional baselines remain mandatory |

## Separation of concerns

Use different mechanisms for different layers.

```text
goal / task selection
  -> Quality-Diversity, bandits, stigmergy, homeostasis

worker + verifier allocation
  -> AVE, measured error correlation, backpressure

compute admission
  -> hard repository policy, authorization, capability/trust filters

compute path routing after admission
  -> Physarum candidate, conventional network-routing baselines

community strategy
  -> ACE carrying capacity, replicator-mutator controller

integration
  -> evidence + independent verification + human/governance authority
```

Do **not** combine these into one "bio-inspired score."

A single opaque score would make attribution, debugging, and falsification harder.

## Required experiment template

Every new mechanism should add a record containing:

```text
problem:
mechanism:
source_domain:
state_variables:
hard_constraints:
baseline_1:
baseline_2:
strong_baseline:
hypothesis:
matched_budget:
metrics:
known_failure_modes:
falsification_rule:
authority_boundary:
real_data_gate:
rollback_or_disable_path:
```

## Promotion rules

### N0 -> N1

Requires:

- deterministic executable model;
- unit tests for invariants;
- at least one deliberately adverse fixture;
- no production authority.

### N1 -> N2

Requires:

- multiple seeds/cases;
- strong baseline, not only a strawman;
- retained raw/summary evidence;
- explicit negative trade-offs;
- no claim beyond the simulated environment.

### N2 -> N3

Requires real project data or a controlled real node/candidate corpus.

The policy remains advisory/dry-run.

Use the common shadow-evidence protocol introduced by PR #637 / issue #636:

- freeze a pre-outcome `adaptive-policy-plan-v0.1` against an exact revision/input digest;
- keep all hard gates outside adaptive authority;
- name the existing baseline beside the shadow recommendation;
- join the later real-process result with `adaptive-policy-outcome-v0.1`;
- never rewrite the frozen plan after the outcome is known;
- summarize cohorts descriptively with the adaptive-policy cohort evaluator;
- keep `shadow_counterfactual_observed=false` and `causal_effect_estimate=null`.

N3 should answer whether a policy makes useful, measurable, materially different recommendations on real state. It does not establish that an unexecuted recommendation would have caused a better result.

### N3 -> N4

Requires:

- independently reviewed evidence;
- bounded cohort;
- resource/risk limits;
- rollback/disable switch;
- explanations for policy decisions;
- no expansion of existing permissions.

### N4 -> N5

Requires repeated operation across relevant workload regimes, observed failure handling, and a governance decision.

## Anti-patterns

Reject these patterns:

### Metaphor-first architecture

> "Ants/slime molds/immune systems are robust, therefore IDKMesh should copy them."

Invalid. The IDKMesh mechanism must independently earn its place.

### Complexity stacking

> "ACO + immune memory + markets + thermodynamics must be stronger together."

Not necessarily. AVE ablation exists specifically to remove components that do not contribute enough value.

### Popularity as evidence

High use, many comments, model fame, or route frequency do not prove correctness or independence.

### Family labels as independence proof

Different model/provider/agent names are only hypotheses about independence. Measured error behavior is stronger evidence.

### Economic language as financial authority

A "price", "budget", or "market" inside an algorithm does not grant permission to spend real money.

### Self-verification

No learning/routing algorithm may let a worker satisfy the verifier independence and EvaluatorPlan ownership boundaries for its own result.

## Current priorities

1. Complete AVE matched-budget/adversarial ablations (#621).
2. Complete Physarum stationary/failure/attribution stress matrix (#630).
3. Move neither mechanism into live routing until it earns **N3 real dry-run** evidence through the common shadow contract (#636 / PR #637).
4. Treat a low shadow-vs-baseline disagreement rate as evidence that a new mechanism may not justify its complexity.
5. Prefer removing unnecessary mechanisms over adding new ones.
5. At the 3-10 node stage, evaluate spectral/percolation diagnostics before inventing another scheduler.
