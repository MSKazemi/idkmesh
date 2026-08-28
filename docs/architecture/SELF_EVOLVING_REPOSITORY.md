# Guarded Self-Evolving Repository Architecture

Date: 2026-08-28
Status: architecture hypothesis / implementation plan

## Goal

Make IDKMesh progressively better at maintaining and reorganizing itself without creating an uncontrolled self-modifying repository.

“Self-evolving” should mean:

> the repository can observe its own structure and outcomes, detect weaknesses, propose bounded graph transformations, test alternative structures, learn which transformations improve project health, and eventually automate a carefully limited subset of low-risk changes.

It must **not** mean:

> an AI agent can rewrite policy, architecture, permissions, tests, and documentation simultaneously and then approve its own change.

The central design is a closed feedback loop over the **IDKGraph** project representation.

---

## 1. Repository as a dynamical system

Let repository state at iteration `t` be

`R_t = (G_t, C_t, M_t, P_t, H_t)`

where:

- `G_t` = semantic IDKGraph: goals, tasks, evidence, documents, concepts, decisions, artifacts, contributors;
- `C_t` = repository contents/code/documentation;
- `M_t` = measured health metrics;
- `P_t` = current policies and rewrite rules;
- `H_t` = provenance/event history.

Evolution is a controlled transition

`R_(t+1) = F(R_t, a_t, e_t)`

where `a_t` is a proposed action/rewrite and `e_t` represents external evidence, contributor activity, tests, and new research.

The project should learn policies for selecting `a_t`, but the allowed action space is constrained by invariants.

---

## 2. MAPE-K-inspired control loop

A practical baseline is a Monitor–Analyze–Plan–Execute loop around shared Knowledge.

### Monitor

Continuously derive repository observables:

- broken links;
- orphan documents;
- duplicate concepts/content;
- contradictory canonical claims;
- stale references;
- missing provenance;
- dependency cycles;
- oversized documents;
- unreachable starter tasks;
- issue/PR/review backlog;
- architecture/code mismatch;
- decisions not reflected in current documentation;
- concepts with inconsistent terminology;
- unverified generated artifacts;
- community fragmentation and maintainer load.

### Analyze

Convert observations into candidate diagnoses:

- this document is an orphan;
- these three sections encode one duplicated concept;
- this architecture decision is cited by obsolete text;
- this task cluster should become a separate module/cell;
- these files have high coupling but no explicit boundary artifact;
- this contributor path has excessive activation cost.

The analysis must retain confidence and evidence rather than pretending every diagnosis is true.

### Plan

Generate one or more bounded rewrite plans.

Examples:

- add missing cross-link;
- create index page;
- split oversized document;
- merge duplicate sections;
- promote repeated concept into a canonical specification;
- archive superseded material;
- generate an ADR candidate;
- split a WorkUnit;
- add a verification task;
- reorganize a directory;
- update generated navigation;
- propose new policy parameters.

### Execute

Execute only in a sandbox branch/worktree/PR, then run invariant checks, documentation checks, tests, and review.

### Knowledge

Record:

- initial health state;
- diagnosis;
- rewrite rule;
- generated diff;
- validation result;
- reviewer decision;
- post-merge health effect;
- later regressions or reverts.

This turns repository maintenance into a dataset from which future policy can learn.

---

## 3. Repository health vector

Never define “better repository” with a single vanity metric.

Define a health vector

`h(R) = (`
`  correctness,`
`  consistency,`
`  provenance_coverage,`
`  navigation_quality,`
`  modularity,`
`  discoverability,`
`  testability,`
`  newcomer_accessibility,`
`  uncertainty_reduction,`
`  reviewability,`
`  security,`
`  maintainer_leverage`
`)`.

A diagnostic energy/potential can be used for controllers:

`V_repo =`
`  w_b * BrokenLinks`
`+ w_o * OrphanNodes`
`+ w_c * Contradictions`
`+ w_d * Duplication`
`+ w_s * Staleness`
`+ w_p * MissingProvenance`
`+ w_x * UnresolvedDependencyCycles`
`+ w_r * ReviewBacklog`
`+ w_n * NavigationCost`
`+ w_k * UnsafeCoupling`
`+ w_u * UnverifiedVolume`.

Lower is generally better, but a rewrite cannot be accepted merely because this scalar decreases. Hard invariants and Pareto trade-offs come first.

---

## 4. Documentation graph

Construct `G_doc` from:

### Nodes

- Markdown/document files;
- headings/sections;
- canonical concepts;
- equations;
- decisions;
- tasks;
- schemas;
- external references.

### Edges

- links_to;
- defines;
- explains;
- depends_on;
- contradicts;
- supersedes;
- duplicates;
- derives_from;
- implements_decision;
- generated_from.

Then derive structural metrics.

### Orphan ratio

`O = number_of_unintentionally_orphan_nodes / number_of_document_nodes`.

### Broken-link ratio

`B = broken_internal_links / internal_links`.

### Navigation distance

Let `S` be newcomer entry points and `K` important canonical documents.

`NavCost = average_(s in S,k in K) shortest_path(s,k)`

with unreachable nodes assigned a large penalty.

### Concept duplication

For canonical concept `c`, let `D_c` count incompatible or unnecessarily duplicated definitions. Prefer one canonical definition plus contextual explanations.

### Decision-document consistency

For each accepted Decision node, require paths to affected architecture/specification nodes. Missing paths are consistency defects.

### Spectral fragmentation

Use graph Laplacian algebraic connectivity `lambda_2` to detect weakly linked islands. A low value does not automatically justify adding links; links must be semantically meaningful.

---

## 5. Minimum Description Length for restructuring

Repository structure faces a compression trade-off:

- too little structure -> duplication and inconsistency;
- too much abstraction -> indirection and comprehension cost.

Minimum Description Length suggests an objective of the form

`L_total = L(structure) + L(content | structure)`.

For IDKMesh, an experimental approximation is

`MDL_repo = complexity_of_taxonomy_and_crosslinks + residual_duplication + exceptions + repeated_explanations`.

Use MDL thinking when deciding whether to:

- create a new canonical concept/document;
- merge several files;
- split a monolithic file;
- introduce another abstraction layer.

Do not minimize raw token count. Human comprehension, onboarding, and auditability are part of the cost model.

---

## 6. Graph modularity and restructuring

A repository should be **modular but connected**.

For a weighted concept/dependency graph, community detection/modularity can suggest candidate modules. Spectral partitioning and graph cuts can identify clusters with dense internal coupling and sparse external interfaces.

For a partition `P`, a restructuring objective can be

`J_partition = InternalCohesion - alpha*CrossBoundaryCoupling - beta*InterfaceComplexity - gamma*MoveCost`.

Candidate boundaries should then be checked against semantic ownership and architectural invariants.

This can discover when:

- a document should split;
- a package should become a module;
- a task cluster should become a Fractal Autonomous Cell;
- multiple research threads need a shared boundary specification.

Automated clustering generates **proposals**, not authoritative architecture.

---

## 7. Typed graph-rewrite system

Represent self-evolution actions as explicit rewrite rules rather than arbitrary edits.

A rule has

`r = (Pattern, Preconditions, Transformation, Postconditions, RiskClass)`.

Candidate rewrite library:

### `AddMissingLink`

Preconditions:

- strong semantic relation detected;
- target canonical node exists;
- no duplicate link.

Postcondition:

- navigation/relation becomes explicit.

### `SplitDocument`

Preconditions:

- coherent subgraphs exist;
- document exceeds complexity threshold;
- stable section identifiers can be preserved or redirected.

Postconditions:

- canonical concepts remain reachable;
- inbound references remain valid;
- no information loss.

### `MergeDuplicateConcepts`

Preconditions:

- definitions are semantically compatible;
- one canonical identity can be chosen;
- provenance preserved.

Postcondition:

- references redirect to canonical node;
- conflicting differences are retained as evidence/alternatives rather than silently erased.

### `ArchiveSuperseded`

Preconditions:

- explicit `superseded_by` relation;
- no active dependency requires the old document as canonical.

Postcondition:

- history remains accessible;
- current navigation points to successor.

### `PromoteRepeatedFinding`

Preconditions:

- finding appears repeatedly;
- sufficient evidence/provenance;
- not already canonical.

Transformation:

- create specification/decision/research node;
- replace repeated copies with references where appropriate.

### `TaskDecomposition`

Split a WorkUnit when size, uncertainty, reviewability, or actor-capability mismatch exceeds thresholds.

### `CreateBridge`

Create a boundary artifact/task linking disconnected disciplines/modules when measured cross-cluster dependency exists.

Formal graph-transformation theory such as the double-pushout family is relevant because it provides disciplined conditions for deleting/gluing graph structure. IDKMesh does not need to implement full category-theoretic machinery in P0, but its precondition/transformation/postcondition discipline is valuable.

---

## 8. Evolutionary search over repository structures

Some restructuring problems have no obvious locally optimal rewrite.

Maintain candidate repository structures or rewrite sequences:

`Population_t = {R_t^1, R_t^2, ..., R_t^m}`

and apply

`variation -> validation -> evaluation -> selection`.

Mutation operators are the typed graph rewrites above.

Candidate fitness dimensions:

- broken-link reduction;
- contradiction reduction;
- duplicate-content reduction;
- faster navigation;
- improved modularity;
- lower reviewer effort;
- lower change size;
- improved contributor task discovery;
- preserved provenance;
- test/benchmark success.

Use **multi-objective selection** such as Pareto ranking rather than one fitness number.

A MAP-Elites / quality-diversity style experiment is also attractive: keep good candidate structures in different niches such as “fewest files,” “best newcomer navigation,” “lowest coupling,” and “lowest migration cost” instead of prematurely choosing one global best.

Only one approved structure enters the canonical repository. Alternative candidates remain experiment artifacts.

---

## 9. Simulated annealing for non-monotonic restructuring

Some beneficial restructures temporarily make metrics worse. Moving documents may temporarily increase redirect complexity before duplication is removed.

For sandbox candidates, a simulated-annealing acceptance rule can explore such moves:

`P_accept = min(1, exp(-DeltaE/T))`.

Use this only inside search/simulation. The main branch still requires explicit acceptance conditions and verification.

High `T` early in a restructuring experiment preserves alternatives. Lower `T` later increases convergence.

---

## 10. Replicator dynamics / bandits for maintenance policies

Let policy `i` be one approach to maintaining the repository:

- link checker only;
- deterministic rule-based restructuring;
- agent-proposed restructuring;
- different decomposition thresholds;
- different documentation architectures.

Track policy performance `f_i`. A replicator-style model

`dx_i/dt = x_i * (f_i - f_bar)`

or a multi-armed bandit can allocate more experiment budget to policies that perform well while retaining exploration.

Fitness should include long-term regressions and reviewer burden, not merely immediate metric improvements.

---

## 11. Homeostasis: biology-inspired target ranges

Biological systems often regulate variables around viable ranges rather than maximize them.

IDKMesh should similarly maintain homeostatic bands:

- documentation size per module;
- review backlog;
- starter-task supply;
- verification/generation ratio;
- number of canonical concepts;
- cross-module coupling;
- stale artifact fraction.

Example error signal:

`e_t = target_review_latency - observed_review_latency`.

A PID/adaptive controller could tune task-generation rate or agent fan-out. P0 can use simple threshold/rate-limited controllers before introducing complex control.

---

## 12. Immune-system analogy for self-protection

Use biological immunity only as a disciplined analogy.

Repository “immune” functions include:

- anomaly detection;
- sandbox/quarantine;
- independent verification;
- signatures/provenance;
- remembered bad patterns;
- rate limiting;
- rollback.

A new autonomous rewrite first enters a **quarantine branch**, not `main`.

Previously observed failure patterns become reusable detectors/tests, analogous to memory but implemented concretely as regression tests, policies, or signatures.

---

## 13. Self-evolution safety invariants

1. **No self-authorization** — the same autonomous actor cannot propose and solely authorize a protected change.
2. **Immutable audit trail** — every evolution proposal retains provenance and outcome.
3. **Test independence** — an agent cannot simply rewrite a failing acceptance test to make its own change pass without a separately reviewed test-change justification.
4. **Policy protection** — safety/governance invariants require stronger approval than ordinary documentation restructuring.
5. **Reversibility** — automated changes must be revertible unless an explicitly reviewed migration says otherwise.
6. **Bounded change** — autonomous proposals have limits on files, graph nodes, permissions, and semantic domains affected.
7. **Risk classes** — low-risk generated navigation differs from security policy or architecture protocol changes.
8. **No hidden deletion** — contradictory or negative evidence must be superseded/archived with provenance, not silently removed.
9. **Metric gaming checks** — improving one metric must not bypass harder quality/invariant checks.
10. **Generation/verification balance** — autonomous generation rate is feedback-controlled by verification capacity.

---

## 14. Autonomy ladder

### Level 0 — Observe

Tools compute health metrics and generate reports only.

### Level 1 — Recommend

System opens issues or suggestions for human selection.

### Level 2 — Propose

System opens bounded pull requests in low/medium-risk areas; humans review/merge.

### Level 3 — Auto-merge deterministic maintenance

Only highly constrained operations such as generated indexes, formatting, or dependency metadata may self-merge after deterministic checks and branch-protection rules.

### Level 4 — Guarded structural evolution

System may generate and compare repository/document/task-graph restructures, but semantic structural changes still require independent approval.

### Level 5 — Policy evolution

System experiments with coordination/maintenance policies and recommends new policies from measured evidence. Fundamental safety/governance constraints remain constitutionally protected and require explicit governance approval.

The project should earn each level empirically rather than declaring itself autonomous.

---

## 15. Proposed self-evolution algorithm

```text
repeat every evolution epoch:
    G <- build_IDKGraph(repository, issues, decisions, evidence)
    H <- measure_health(G, repository, community_metrics)

    anomalies <- detect_defects_and_opportunities(G, H)
    candidates <- []

    for anomaly in highest_value(anomalies):
        plans <- apply_allowed_rewrite_rules(G, anomaly)
        for plan in plans:
            G2 <- simulate(plan, G)
            if violates_hard_invariant(G2):
                reject(plan)
                continue

            metrics2 <- estimate_health(G2)
            candidates.append(plan, metrics2, uncertainty)

    frontier <- pareto_rank(candidates)
    selected <- choose_by_risk_information_gain_and_budget(frontier)

    for plan in selected:
        execute_in_branch(plan)
        run_deterministic_validation()
        run_independent_critic()
        run_tests_and_doc_checks()

        if policy_allows_auto_merge(plan.risk) and all_checks_pass:
            merge_with_provenance()
        else:
            request_independent_review()

    after_observation_window:
        record_actual_effect_of_accepted_changes()
        update_rewrite_policy_statistics()
```

The loop optimizes **evidence-backed improvement**, not edit frequency.

---

## 16. First implementation milestones

### P0 — repository observatory

Build a tool that exports:

- internal link graph;
- orphan files/sections;
- heading/concept IDs;
- broken links;
- file sizes and change frequency;
- decision-to-document references;
- WorkUnit/task graph;
- basic provenance coverage.

Output a machine-readable graph plus Markdown report.

### P1 — invariant checker

Implement graph/document invariants and fail CI on deterministic violations.

### P2 — rewrite recommender

Implement `AddMissingLink`, `GenerateIndex`, `ArchiveSuperseded`, and `TaskDecomposition` as proposal-only transformations.

### P3 — guarded PR agent

Allow a local/open agent to create a branch and PR for approved low-risk rewrite types. Require independent review.

### P4 — experiment with competing restructures

Run multi-objective/evolutionary search in simulation and compare candidate repository structures.

### P5 — controlled policy learning

Use outcome history to tune rewrite selection/task decomposition thresholds while maintaining protected invariants.

---

## 17. Important research questions

1. Which repository-health metrics predict future contributor success rather than merely looking tidy?
2. Can contradiction/duplication detection become reliable enough for automated proposals?
3. Does spectral/modularity-based document clustering produce structures humans find easier to navigate?
4. Can MDL-like restructuring reduce duplication without creating excessive abstraction?
5. Which graph-rewrite rules are safe enough for deterministic auto-merge?
6. Can post-merge outcome measurement detect when a theoretically “better” structure made onboarding worse?
7. What observation window is required before judging an evolution successful?
8. How should the system distinguish intentional repetition for pedagogy from harmful duplication?
9. Can evolutionary search find repository structures that human maintainers would not have proposed?
10. How can the system prevent agents from gaming health metrics by deleting difficult information?
11. Can documentation, task, code, contributor, and evidence graphs be co-optimized without destructive coupling?
12. When should a project cell split, merge, or become autonomous?
13. Can health-control loops remain stable when several independent agents optimize different subsystems?
14. Which invariants should be mathematically/formally verified?
15. At what autonomy level does reviewer workload actually begin to decrease?

---

## 18. References

- Kephart and Chess, `The Vision of Autonomic Computing`, IEEE Computer 36(1), 2003, DOI `10.1109/MC.2003.1160055`.
- W3C PROV-DM / PROV Constraints, Recommendations, 2013.
- Söldner and Plump, `Formalising the Double-Pushout Approach to Graph Transformation`, arXiv:2312.15641.
- van der Aalst et al., workflow-net soundness analysis, Formal Aspects of Computing 23, 2011.

## Working decision

IDKMesh should pursue **guarded semantic self-evolution**: observe the repository as a graph, propose typed transformations, test them in isolation, measure their effects, and learn which transformations help.

The repository may become progressively more autonomous, but **autonomy is an earned capability constrained by provenance, independent verification, protected invariants, reversibility, and governance**.
