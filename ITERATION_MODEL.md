# IDKMesh Iteration Model

**Status:** Canonical vocabulary and integration protocol. Individual mechanisms remain experimental until their stated evidence gates pass.

IDKMesh should not define an iteration as "a commit". A commit is only an event. An **iteration** is a measurable state transition in which repository activity changes one or more dimensions of project fitness and produces evidence that can guide the next transition.

## 0. What IDKMesh is

IDKMesh is one layered system with five roles:

1. a **coordination framework and protocol set** for goals, bounded work, evidence, provenance, scheduling, and governance;
2. a **reference application**, initially the Git-native Verified Swarm Runner;
3. a **research program** testing collective-intelligence mechanisms;
4. an **open community** that supplies goals, work, criticism, review, and stewardship;
5. a **self-hosting experiment** in which IDKMesh is the first project coordinated by IDKMesh.

The current repository is an early GitHub-native laboratory for that system, not yet a general intelligent entity or production distributed platform. “Learning” currently means explicit, inspectable updates to graphs, evidence, beliefs, and policy parameters. It does not mean that the repository silently trains a foundation model from every interaction.

```text
human constitution and governance
              | constrains
              v
goals/evidence graph -> evolution controller -> Action Contract
       ^                                      |
       |                                      v
outcome memory <- decision <- verification <- Work Units
       |                                      |
       +------ policy learning <--- humans + agents + compute
```

The graph supplies meaning and memory; the controller chooses bounded experiments; the runner coordinates execution; verification supplies evidence; governance alone grants canonical authority.

This document defines the shared lifecycle; specialized documents define each mechanism:

| Responsibility | Detailed contract |
| --- | --- |
| constitutional and human-value limits | [`CONSTITUTION.md`](CONSTITUTION.md), [`GOVERNANCE.md`](GOVERNANCE.md) |
| semantic goal/task/evidence state | [`docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`](docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md) |
| repository restructuring | [`docs/architecture/SELF_EVOLVING_REPOSITORY.md`](docs/architecture/SELF_EVOLVING_REPOSITORY.md) |
| mathematical primitives and live control | [`docs/architecture/MATHEMATICAL_EVOLUTION_KERNEL.md`](docs/architecture/MATHEMATICAL_EVOLUTION_KERNEL.md), [`docs/architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md`](docs/architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md) |
| algorithm/evidence signal composition and authority ceilings | [`docs/architecture/ALGORITHM_COLLABORATION_FABRIC.md`](docs/architecture/ALGORITHM_COLLABORATION_FABRIC.md), [`docs/architecture/EVIDENCE_AGGREGATION_FABRIC.md`](docs/architecture/EVIDENCE_AGGREGATION_FABRIC.md) |
| community reproduction and capacity | [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md), [`docs/community/ACE_ACTIVITY_METABOLISM.md`](docs/community/ACE_ACTIVITY_METABOLISM.md) |
| compute admission and execution | [`docs/architecture/FREE_RESOURCE_MESH_COMPUTE_BRIDGE.md`](docs/architecture/FREE_RESOURCE_MESH_COMPUTE_BRIDGE.md), [`EVOLUTION.md`](EVOLUTION.md) |
| canonical Git integration | [`docs/planning/BRANCH_CONVERGENCE_POLICY.md`](docs/planning/BRANCH_CONVERGENCE_POLICY.md) |

## 1. Repository state

The complete observable state at time `t` is:

```text
Z_t = (K_t, D_t, W_t, N_t, X_t, B_t, Pi_t, L_t)
```

where:

- `K` = typed goals, questions, hypotheses, evidence, decisions, and provenance;
- `D` = canonical code, documentation, schemas, and artifacts;
- `W` = open Work Units, dependencies, candidates, and verification queues;
- `N` = participant capability, independence, attention, and community capacity;
- `X` = admitted compute/resources, cost, availability, and execution risk;
- `B` = uncertain beliefs and measured health indicators;
- `Pi` = versioned operational policies under constitutional constraints;
- `L` = append-only event, experiment, decision, and outcome lineage.

The existing health vector is a projection of `Z_t`, not the repository's full state:

```text
S_t = [G_t, Q_t, C_t, V_t, M_t, H_t, R_t]
```

where:

- `G` = goal clarity and goal-graph quality;
- `Q` = implementation/product quality;
- `C` = community health and contributor capacity;
- `V` = verification strength and reproducibility;
- `M` = modularity/maintainability of the repository structure;
- `H` = useful hypothesis diversity / exploration capacity;
- `R` = accumulated risk, complexity, coordination cost, and unresolved debt.

GitHub objects are observations and actuators over this state. The typed IDKGraph is the intended semantic model; Git, GitHub, and evidence artifacts are the current storage and control surfaces.

## 2. Event, action, iteration, generation, and learning

These terms are not interchangeable:

- An **event** is an observed occurrence, such as a review, workflow result, commit, failure, or issue. It may be noise and grants no authority.
- An **action** is a deliberately authorized, bounded intervention expected to change state or reduce uncertainty.
- A **candidate** is an action result awaiting verification or decision; it is not canonical state.
- An **iteration** is a closed evidence cycle from a baseline snapshot through an action or deliberate no-op to an outcome record and state/belief update.
- A **generation** is a capacity-bounded set of related iterations after which allocation or catalyst-strategy weights may be updated.
- **Learning** is a versioned update justified by linked outcome evidence. Merely counting an event is observation, not learning.

Every action must have an inspectable contract:

```yaml
id: EA-...
kind: observe|research|implement|verify|integrate|repair|govern|onboard
target: stable goal/task/artifact IDs
hypothesis: expected change and why
baseline: immutable snapshot/evidence references
preconditions: dependencies and authority gates
budget: compute, time, reviewer attention, write scope
risk_class: R0|R1|R2|R3
outputs: expected artifacts and provenance
verification: independent methods and acceptance criteria
outcome_window: when realized effects will be measured
rollback: reversal or containment procedure
```

An iteration is:

```text
I_t = (baseline, trigger, action_contract, execution,
       verification, decision, outcome_observation, state_update)
```

or more compactly:

```text
Z_(t+1) = F(Z_t, action_t, evidence_t)
```

An observation-only iteration may choose `action = no-op`; this is preferable to manufacturing work. A rejected PR or failed experiment can complete a useful iteration by reducing uncertainty, but it must not be mislabeled as a product improvement.

## 3. Definition and decision rule for improvement

Improvement is a vector of evidence-backed changes, including capability, correctness, goal clarity, verification, maintainability, community capacity, information gained, cost, and risk. Hard constraints and minimum floors are evaluated before optimization:

```text
Admissible(a) = constitutional_invariants
             AND authority_valid
             AND dependencies_satisfied
             AND budget_within_limits
             AND verification_sufficient_for_risk
             AND rollback_or_containment_ready
```

A result is an **improvement candidate** only when it is admissible and either:

```text
1. Pareto-acceptable: it improves at least one objective without crossing a
   protected floor on another; or
2. Informative experiment: it produces enough expected information gain to
   justify its bounded, reversible cost even if capability does not increase.
```

Merge or acceptance records a verified candidate transition. **Realized improvement** is established only after the declared outcome window checks durability, regressions, maintenance/review cost, reuse, and community effects. The record may later be revised by new evidence.

The existing scalar `Phi` and `DeltaPhi > epsilon` remain diagnostic summaries. They may rank already-admissible candidates, but a favorable weighted sum cannot compensate for failed security, governance, evidence, human-value, or resource constraints. Raw commits, stars, issue counts, or lines of code are never improvement evidence by themselves.

Every completed action receives exactly one outcome class:

- `realized-improvement` — the expected benefit survived its outcome window;
- `informative-negative` — the hypothesis failed but uncertainty decreased;
- `risk-revealing` — the action exposed a defect, threat, or invalid assumption;
- `null` — no supported benefit or material information gain;
- `adverse-rolled-back` — a protected floor regressed and containment ran.

This is the enforceable meaning of “every action helps the next action”: every action must leave an auditable receipt and update future decisions. It is neither possible nor safe to promise that every action directly increases project fitness.

A closed Iteration Receipt records at least:

```yaml
iteration_id: EI-...
action_id: EA-...
baseline: immutable state and policy digests
artifacts: produced candidates and provenance
verification: checks, reviewers, independence, and exact versions
decision: accept|reject|revise|inconclusive
outcome: class, observed delta vector, confidence, observation window
actual_cost: compute, energy, latency, human/reviewer attention
policy_effect: unchanged or separately reviewed policy transition
next_state: state digest and follow-up hypotheses/tasks
```

Missing outcome evidence leaves the iteration `open` or `inconclusive`; it must not default to success.

## 4. Four coupled evolutionary loops

IDKMesh should evolve through four simultaneous loops.

### A. Goal loop

Trigger: new question, disagreement, failed experiment, changed assumptions.

GitHub representation: issue / IDKIP / discussion -> competing hypotheses -> experiment -> decision -> GOALS/DECISIONS update.

Improvement means reduced ambiguity where convergence is justified, or better explicit branching where uncertainty remains.

### B. Product/structure loop

Trigger: bug, feature request, architecture friction, repeated contributor confusion, dependency bottleneck.

GitHub representation: issue -> PR -> checks/review -> merge/reject -> architecture/doc updates.

Improvement means verified capability increases without disproportionate structural entropy or maintenance burden.

### C. Community loop

Trigger: issue/PR/review/comment from a person or agent, newcomer arrival, stalled task, repeated maintainer bottleneck.

GitHub representation: labels, assignments, starter issues, review requests, acknowledgements, contributor ownership, community docs.

Improvement means lower onboarding friction, more independent ownership, better review capacity, higher recurrence, and lower concentration of work in one maintainer.

### D. Meta-evolution loop

Trigger: evidence that the evolution process itself is inefficient.

GitHub representation: changes to workflows, templates, labels, scoring rules, governance, automation, or iteration metrics through normal PR review.

Improvement means future iterations become safer, cheaper, faster, more informative, or more community-generating.

This loop is how the repository can restructure how it restructures itself.

## 5. GitHub-native triggers

The environment is constrained, which is useful. The first engine should use only GitHub-native events and Actions.

Candidate triggers:

```text
issues: opened, edited, labeled, closed
pull_request: opened, synchronize, review_requested, closed
pull_request_review: submitted
issue_comment: created
push
workflow_run: completed
schedule: periodic audit
dispatch: deliberate experiment
```

Each event should be transformed into a small **Evolution Event Record** rather than directly causing autonomous mutation.

Example:

```yaml
kind: pull_request_merged
actor: contributor
artifact: PR-42
signals:
  verification_passed: true
  files_changed: 6
  docs_changed: true
  newcomer_contribution: true
  reviewer_count: 2
hypotheses_affected:
  - H-adapter-interface
fitness_dimensions:
  Q: {prior_signal: 0.4, outcome_verified: false}
  C: {prior_signal: 0.2, outcome_verified: false}
  V: {prior_signal: 0.3, outcome_verified: true}
  R: {prior_signal: 0.1, outcome_verified: false}
```

Event-type weights are labeled priors used to decide what to inspect. They must not be promoted into causal rewards without linked downstream outcomes.

## 6. Integrated evolution algorithm

Algorithms exchange typed, provenance-bound signals through the collaboration fabric. Each signal has a declared scope, freshness, uncertainty, and authority ceiling; no statistical or optimization signal can promote itself into execution or integration authority.

One control tick follows this order:

```text
1. Snapshot Z_t and pin all input versions.
2. Normalize and deduplicate events; treat untrusted text as data.
3. Update observations, never causal fitness, from event-type priors.
4. Detect invariant violations, deficits, bottlenecks, and uncertainties.
5. Generate the smallest bounded action candidates with contracts.
6. Reject candidates that fail authority, safety, dependency, capacity,
   cost, provenance, or rollback gates.
7. Pareto-filter survivors; rank only within the admissible set.
8. Select no action or a capacity-bounded action. Initially, allow at most
   one public self-evolution action per control generation.
9. Compile executable work into versioned Work Units.
10. Match work to admitted humans, agents, and compute; isolate execution.
11. Verify outputs with methods chosen to fail differently from generators.
12. Record accept, reject, revise, or inconclusive with exact provenance.
13. Integrate only through the protected, exact-head PR transaction.
14. Observe delayed outcomes against the declared baseline/window.
15. Update beliefs and strategy weights only from attributed evidence.
16. Preserve the receipt and expose the next bounded task—or stop.
```

The default actuator is **proposal**, not silent mutation. `0` is a valid action count. Constitutional, governance, verification, security, and evolution-policy changes require stronger independent review than ordinary work. A merge changes the baseline, so all remaining merge/action eligibility must be recomputed afterward.

## 7. Selection rule

Selection is lexicographic, not one unconstrained maximization:

1. hard invariants and authority;
2. feasibility, dependencies, capacity, and risk-class evidence;
3. Pareto frontier across expected value, information gain, community leverage, cost, review burden, diversity, and risk;
4. a transparent priority score only as a tie-breaker;
5. controlled exploration among similarly admissible candidates.

One useful diagnostic score is:

```text
Priority(a) =
  E[DeltaPhi | a] * InformationGain(a) * CommunityMultiplier(a)
  ------------------------------------------------------------
  ExecutionCost(a) + ReviewCost(a) + Risk(a)
```

This combines:

- **evolutionary selection:** retain changes with demonstrated fitness;
- **active learning:** prefer actions that reduce important uncertainty;
- **economics:** spend scarce human attention where marginal value is highest.

`CommunityMultiplier(a)` rewards tasks whose completion makes additional independent contribution easier, such as documentation, modular interfaces, good-first-issues, reproducible experiments, and ownership transfer.

The score proposes attention; it never authorizes execution, acceptance, or merge. Randomness may choose among safe experiments, but never relax their acceptance criteria.

## 8. Community reproduction number

For community growth, define a repository reproduction number analogous to epidemiology:

```text
R_repo = p_discover * p_engage * p_contribute * p_return * k_enable
```

where `k_enable` is the expected number of additional contributors enabled by one successful contribution through documentation, examples, mentorship, modularity, issue creation, or reusable infrastructure.

Interpretation:

- `R_repo < 1`: the contributor population tends to decay without maintainer effort;
- `R_repo ~= 1`: the community replaces itself;
- `R_repo > 1`: each cohort creates conditions for a larger next cohort.

The engine should optimize the components, not merely stars. A PR that creates three clearly bounded follow-up tasks may have a larger community effect than a larger monolithic PR.

## 9. Structural entropy

Repository growth creates entropy. Track a rough structural entropy score from signals such as:

- duplicated concepts across docs;
- files with unclear ownership;
- large modules with many unrelated responsibilities;
- orphan issues/docs;
- broken internal links;
- cyclic or excessive dependencies;
- stale contradictory decisions;
- repeated onboarding questions.

Periodic Actions can scan deterministic signals and open consolidation issues. The goal is not minimum complexity; it is **maximum useful complexity per unit of coordination burden**.

## 10. Exploration vs exploitation

The project begins with uncertain goals, so it must not converge too early.

Use an adaptive exploration budget:

```text
exploration_rate ~= uncertainty * reversibility / risk
```

High uncertainty + reversible experiments -> allow competing branches and prototypes.

High risk + irreversible architectural/governance changes -> demand stronger evidence and review.

As evidence accumulates, the engine can move from hypothesis generation toward consolidation.

## 11. Current minimal implementation inside GitHub

The repository currently has these five seed artifacts:

1. `state/evolution-state.json` — compact latest metric/state snapshot.
2. `state/evolution-events.jsonl` — append-only derived event/evidence records.
3. `scripts/evolution_score.py` — deterministic scoring and opportunity detection.
4. `.github/workflows/evolution-loop.yml` — runs on selected GitHub events and on a schedule.
5. `EVOLUTION_REPORT.md` or a recurring GitHub issue — human-readable state, regressions, opportunities, and proposed next actions.

The workflow has conservative read authority and cannot merge its own code. The checked-in state is still a bootstrap seed, while cross-run Bayesian history is restored from expiring GitHub Actions artifacts. This is useful operational memory, but it is not yet durable causal learning. Important validated outcomes must be promoted into versioned repository evidence and decisions.

## 12. First measurable dimensions

Do not start with dozens of metrics. Begin with:

```text
Goal:
- unresolved high-level contradictions
- hypotheses with explicit tests/evidence

Product:
- verification pass rate
- reproducible examples / benchmark tasks

Community:
- unique active contributors
- first contribution -> second contribution conversion
- review distribution / maintainer concentration
- number of independently owned surfaces

Structure:
- stale/orphan issue count
- documentation consistency checks
- dependency/interface violations

Risk:
- failing workflows
- unreviewed high-impact changes
- unresolved security/verification debt
```

Metrics must remain inspectable and easy for contributors to challenge through PRs.

## 13. Example iteration

A newcomer opens an issue describing difficulty implementing a verifier.

```text
1. issue_opened -> signal: onboarding/API friction
2. engine links it to verifier-interface hypothesis
3. similar issues increase expected value of interface/documentation work
4. engine proposes a bounded issue: "extract verifier adapter + add 10-minute tutorial"
5. contributor submits PR
6. CI passes and an independent reviewer approves
7. another newcomer successfully implements a verifier using the new interface
8. the declared outcome window measures reuse, defects, and attention cost
9. only supported dimensions of C, Q, M, and V are updated
10. the successful pattern becomes a reusable issue/template rule
```

That entire causal cycle is an iteration. The individual commits are merely events inside it.

## 14. Constitutional constraints

Self-evolution should be bounded by rules that automation cannot silently override:

- no autonomous merge to `main` for changes to goals, governance, security policy, verification rules, or the evolution algorithm itself;
- every automated recommendation must expose its evidence and score components;
- raw activity is never accepted as proof of improvement;
- reversible experiments are preferred before permanent structural changes;
- negative results are retained as evidence;
- community health and human attention are treated as system resources;
- any metric can be challenged and changed through normal project governance.

## 15. North-star outcome

For this repository, improvement should mean:

> **The repository becomes more capable of producing verified useful outcomes, discovering and refining its goals, attracting and enabling independent contributors, and improving its own coordination process—while keeping complexity, risk, and human bottlenecks under control.**

The objective is therefore not a self-modifying repository. It is a **self-observing, self-proposing, evidence-selecting repository** whose GitHub activity continuously produces better conditions for the next activity.

## 16. What learning means operationally

The memory hierarchy is:

```text
raw event -> normalized observation -> evidence -> decision
          -> delayed outcome -> belief update -> policy proposal
```

Each link must retain stable IDs, timestamps, actor/tool identity, input and output hashes, policy version, and confidence. Event frequency can update workload or attention estimates, but only linked outcomes may update claims about which actions work. Policy updates use Bayesian posteriors, causal comparisons where feasible, and replicator/bandit updates over repeated strategy outcomes. A policy change is itself a high-risk action: test it against an incumbent, run it in shadow/canary mode, preserve exploration, and require independent review and rollback.

Git history stores content; IDKGraph should store semantic relationships; append-only receipts store temporal lineage; decisions summarize durable conclusions. Expiring CI artifacts are checkpoints, not the sole long-term memory.

## 17. Role of cross-disciplinary ideas

Use each field only where it supplies a testable mechanism:

| Source | Appropriate IDKMesh role | Boundary |
| --- | --- | --- |
| Control theory | observability, feedback, backpressure, stability, rollback | proxies are not the true state |
| Bayesian statistics and causal inference | uncertainty, evidence updates, experiment comparison | correlation and event counts do not prove causes |
| Evolution/genetic algorithms | variation, selection, retention, mutation of policy candidates | never mutate or promote production policy without gates |
| Ecology and stigmergy | carrying capacity, niches, local environmental signals | popularity cannot become fitness |
| Fractals and cellular automata | repeated node/cell/federation interfaces and local-rule simulations | scale invariance and emergence must be measured |
| Statistical physics/gases | aggregate congestion, phase transitions, percolation, annealing | strategic heterogeneous agents are not particles |
| Economics | scarce-attention allocation, incentives, externalities, mechanism tests | markets do not determine truth or human values |
| Political science | polycentric governance, separation of proposal/verification/integration powers | current bootstrap authority is not the target state |
| Psychology | autonomy, competence, belonging, onboarding and retention hypotheses | measure consent and experience; do not manipulate people |
| DNA/chemical computing | later experiments in massive parallel search or reaction-like workflows | no demonstrated present engineering need |
| Quantum-inspired methods | optional benchmarked optimization formulations | classical nodes are not a quantum computer |

These are a library of hypotheses, not one grand analogy. A mechanism enters the architecture only with variables, a baseline, a falsifiable prediction, a budget, and an exit criterion.

## 18. Current maturity and next proof

The repository already implements bounded schemas, deterministic simulators, repository observatories, advisory mathematical portfolios, provenance checks, community-capacity controls, and parts of a local generation/verification pipeline. It does **not** yet demonstrate a generally self-improving entity. Current gaps include:

- no machine-readable Action Contract and closed Iteration Receipt joining all subsystems;
- incomplete durable causal linkage from action through delayed outcome;
- largely hand-authored coefficients and proxy metrics;
- no production distributed execution/federation layer;
- no protected `main` enforcement and still-concentrated integration authority;
- insufficient real evidence that community actions reproduce independent contributors;
- no evidence that the full loop beats a simpler baseline over repeated iterations.

The next decisive experiment is one complete self-hosted loop: freeze a repository deficit and baseline; emit one Action Contract; execute bounded competing Work Units; verify independently; integrate through an exact-head reviewed PR; measure the declared later outcome; emit an Iteration Receipt; and update one policy only if repeated evidence supports it. Compare its verified value, information gain, attention, compute, latency, and regressions against a human-selected baseline. Until that closes repeatedly, IDKMesh is a promising framework and research program—not yet the smart entity it intends to become.
