# IDKGraph: Task, Evidence, Provenance, and Evolution Model

Date: 2026-08-28
Status: working architecture / research specification

## Purpose

IDKMesh needs a representation that can handle all of these at once:

- ambiguous goals;
- questions and competing hypotheses;
- executable tasks and dependencies;
- artifacts and tests;
- evidence that supports or contradicts claims;
- humans, AI agents, and compute workers;
- documentation and concepts;
- decisions and their provenance;
- repository restructuring and self-evolution over time.

A plain task list is too weak. A single DAG is too restrictive because the knowledge layer may contain cycles, contradictions, alternatives, and superseding relationships. An e-graph is also too specialized because equality is only one kind of relation.

The proposed canonical representation is **IDKGraph**: a **typed, temporal, multiplex directed hypergraph with an append-only event/provenance history**.

The global graph is rich. Simpler formal projections are derived from it for specific jobs:

- a DAG / AND-OR dependency graph for executable work;
- a Petri-net/workflow-net projection for task-state and concurrency analysis;
- a provenance graph compatible in spirit with W3C PROV;
- a documentation/concept graph for repository consistency;
- a contributor/task bipartite graph for matching and community analysis;
- an optional e-graph for true equivalence-saturation problems.

This separation is important: one graph representation should not be forced to provide every formal property by itself.

---

## 1. Canonical mathematical object

At time `t`, define

`G(t) = (V(t), E_H(t), L, X(t), I, Omega(t))`

where:

- `V(t)` is the set of typed nodes;
- `E_H(t)` is the set of typed directed hyperedges;
- `L` maps nodes/edges into semantic layers;
- `X(t)` stores attributes and measured state;
- `I` is the set of invariants/constraints;
- `Omega(t)` is an append-only event log describing how the graph reached its current state.

A directed hyperedge is

`e = (S_e, T_e, r_e, x_e)`

where:

- `S_e subseteq V` is a set of source nodes;
- `T_e subseteq V` is a set of target nodes;
- `r_e` is a typed relation;
- `x_e` stores metadata such as confidence, author/agent, timestamp, evidence strength, and provenance.

Hyperedges are useful because real work is often many-to-many:

`{specification, dataset, implementation} -> verification activity -> {test result, benchmark report, decision evidence}`.

A binary graph can encode this by creating intermediary nodes, but a hypergraph makes the semantics explicit.

---

## 2. Node types

Initial canonical node types:

- **Goal** — desired outcome.
- **Question** — unresolved question.
- **Hypothesis** — candidate answer/explanation.
- **Constraint** — requirement or invariant.
- **WorkUnit** — bounded task with inputs, outputs, acceptance conditions, risk, and resource needs.
- **Artifact** — code, dataset, schema, benchmark result, model, diagram, release.
- **Evidence** — observation, test result, paper result, reproduction, counterexample.
- **Decision** — accepted/rejected/deferred architecture or governance choice.
- **Metric** — measurable variable and its definition.
- **Contributor** — human participant.
- **Agent** — identifiable AI/software agent.
- **ComputeResource** — worker/device/cell.
- **Document** — file or section in the repository.
- **Concept** — named mathematical/technical/community concept.
- **Policy** — rule governing assignment, verification, permissions, or evolution.
- **Experiment** — explicit falsifiable trial linking hypothesis, workload, metric, result, and stopping rule.

Every node should have a globally unique stable identifier independent of its current filename or location.

---

## 3. Edge / hyperedge types

Initial relation vocabulary:

- `decomposes_into`
- `depends_on`
- `requires`
- `produces`
- `blocks`
- `supports`
- `contradicts`
- `verifies`
- `invalidates`
- `derived_from`
- `supersedes`
- `implements`
- `documents`
- `defines`
- `mentions`
- `duplicates`
- `assigned_to`
- `reviewed_by`
- `generated_by`
- `uses_compute`
- `measured_by`
- `governed_by`
- `bridges`

Relations should have explicit semantics. For example, `supports` is not the same as `verifies`, and `supersedes` is not the same as deletion.

---

## 4. Why the executable task graph should be a projection

Define the executable projection

`D_exec = P_exec(G)`.

`D_exec` contains only WorkUnits and prerequisite relations that must satisfy acyclic execution semantics for a specific planning horizon.

The global knowledge graph may contain cycles:

`hypothesis A contradicts B`, `B motivates experiment C`, `C changes confidence in A`.

That is legitimate. The executable dependency projection should not contain an unresolved dependency cycle.

### AND / OR prerequisites

Some tasks require all inputs:

`A AND B AND C -> T`.

Other tasks can proceed if any acceptable alternative exists:

`A OR B -> T`.

Therefore the execution layer should support an **AND/OR dependency hypergraph**, not only pairwise precedence edges.

A simple readiness predicate is

`Ready(T) = PreconditionsSatisfied(T) * NoOpenBlocker(T) * CapacityAvailable(T)`.

For an AND group all required predecessor predicates must be true. For an OR group at least one admissible predecessor path must be true.

---

## 5. WorkUnit state as a Petri-net / workflow-net projection

A WorkUnit lifecycle can be represented as places and transitions:

`proposed -> specified -> ready -> executing -> candidate -> verifying -> {accepted | rejected} -> integrated`

with optional paths such as:

- needs clarification;
- blocked;
- superseded;
- retry;
- split into subtasks.

Petri-net semantics are useful because tokens and transitions naturally represent concurrency, resource availability, synchronization, and illegal state transitions. Workflow-net soundness analysis can detect classes of deadlocks, livelocks, or incomplete workflows before the workflow engine is deployed.

Do not force the entire knowledge graph into a Petri net. Use the Petri net only for operational state and workflow semantics.

---

## 6. Provenance as a first-class graph

Every important artifact/result should be traceable through relationships similar to W3C PROV concepts:

`Agent -> Activity -> Entity`

and derivations such as:

`artifact B wasDerivedFrom artifact A`.

W3C PROV explicitly models entities, activities, agents, derivations, collections, and provenance bundles. IDKGraph should reuse those ideas rather than inventing incompatible provenance semantics unnecessarily.

For IDKMesh this means a contributor should be able to ask:

- Which task produced this artifact?
- Which model/human/agent produced it?
- Which inputs and versions were used?
- Which tests verified it?
- Which evidence affected the decision to accept it?
- Which later artifact superseded it?

---

## 7. Event-sourced temporal evolution

The current graph is a materialized state. The durable truth of evolution is an append-only sequence of public-safe events:

`Omega = {omega_1, omega_2, ..., omega_n}`.

Example events:

- `NodeCreated`
- `EdgeAdded`
- `ClaimUpdated`
- `EvidenceAttached`
- `TaskSplit`
- `TaskMerged`
- `DocumentMoved`
- `DecisionSuperseded`
- `VerificationPassed`
- `VerificationFailed`
- `PolicyChanged`

Each event stores actor/provenance and references affected stable IDs.

Advantages:

- reproducible project history;
- rollback and audit;
- learning from past restructures;
- measuring which graph changes improved outcomes;
- reconstructing earlier project states;
- preventing filename moves from destroying conceptual identity.

Git already provides content history. IDKGraph should add **semantic event history** over Git rather than replacing Git.

---

## 8. Task value should be multi-objective

For each WorkUnit `i`, define a vector rather than immediately collapsing everything into one score:

`z_i = (`
`  impact_i,`
`  information_gain_i,`
`  unlock_i,`
`  bridge_i,`
`  urgency_i,`
`  success_probability_i,`
`  -cost_i,`
`  -risk_i,`
`  -duplication_i`
`)`.

Prefer Pareto selection for high-level planning. A policy can use a scalar score when an actual queue needs ordering:

`Score_i = wI*Impact_i + wG*EIG_i + wU*Unlock_i + wB*Bridge_i + wA*Aging_i + wP*Psuccess_i - wC*Cost_i - wR*Risk_i - wD*Duplication_i`.

The weights are policy parameters and should be versioned and experimentally evaluated.

### Expected information gain

For uncertain project state `Theta` and current evidence `D`:

`EIG(T) = H(Theta | D) - E_y[ H(Theta | D, y_T) ]`.

This makes a reproduction experiment or counterexample valuable even if it does not produce code: it can reduce uncertainty.

### Downstream unlock value

One useful graph heuristic is

`Unlock(i) = sum_{j in Desc(i)} value_j * exp(-lambda * distance(i,j))`.

A small task that unlocks many high-value descendants can rank above an isolated large feature.

### Cross-discipline bridge value

Let `L_c` be the Laplacian of a contributor/discipline collaboration graph. A candidate bridge task can be assigned a predicted connectivity benefit such as

`Bridge(i) ~= max(0, lambda_2(L_after_i) - lambda_2(L_before))`.

This explicitly rewards tasks likely to connect isolated scientific/engineering communities rather than only adding more work inside an already dense cluster.

---

## 9. Matching tasks to humans, agents, and compute

Let `x_ai in {0,1}` mean actor/resource `a` is assigned to WorkUnit `i`.

A scheduling objective can include

`maximize sum_(a,i) x_ai * (`
`  task_value_i`
`  + skill_match_ai`
`  + independent_information_ai`
`  + locality_ai`
`  - expected_cost_ai`
`  - correlated_failure_ai`
`  - security_risk_ai`
`)`.

Subject to:

- capacity constraints;
- WorkUnit dependencies;
- resource requirements;
- trust/risk policies;
- verifier independence requirements;
- data locality/privacy rules.

For high-risk tasks, the graph can require explicit independent verification hyperedges before integration becomes reachable.

---

## 10. Where e-graphs / equality saturation fit

If “ES graph” refers to an **e-graph** / equality-saturation graph, it is useful, but it should not be the global IDKGraph.

E-graphs compactly represent many equivalent expressions and rewrite-derived forms. Equality saturation applies rewrite rules non-destructively and later extracts a preferred equivalent form using a cost function.

Good IDKMesh uses:

- mathematical-expression normalization;
- proving two scheduler cost formulations equivalent under assumptions;
- exploring equivalent query/planning expressions;
- compiler/DSL optimization;
- deduplicating semantically equivalent schema expressions;
- retaining multiple equivalent representations while selecting the cheapest/clearest one.

Bad use:

- representing disagreement (`supports` vs `contradicts`);
- representing arbitrary dependencies;
- representing trust/provenance;
- representing task lifecycle.

Those are not equivalence relations.

The `egg` work is a strong reference for this specialized layer. Its e-graphs represent equivalence classes and equality saturation avoids destructive phase-ordering by accumulating equivalent rewrites before extraction.

---

## 11. If “ES” means event structure

Event structures are also relevant for concurrency: events, causality, conflict, and concurrency can be modeled explicitly.

IDKMesh can compare event-structure semantics with Petri-net semantics for difficult concurrency cases. Petri nets are the better P0 engineering baseline because workflow tooling and soundness concepts are well established; event structures can become a research projection where true-concurrency semantics matter.

---

## 12. Stigmergic task discovery as a biological experiment

A biological inspiration from ant systems is **stigmergy**: agents coordinate indirectly through state left in the environment.

For each task `i`, define a bounded attention/pheromone variable `tau_i`:

`tau_i(t+1) = (1-rho) * tau_i(t) + Delta_i(t)`

where:

- `rho` is evaporation;
- `Delta_i` reflects verified useful progress, unmet demand, or credible contributor interest.

A stochastic task-discovery policy could use

`P(select i) = tau_i^alpha * eta_i^beta / sum_j tau_j^alpha * eta_j^beta`

where `eta_i` is intrinsic task utility/fit.

Evaporation prevents old popularity from dominating forever.

This should remain an experiment because naive pheromone systems can create rich-get-richer bias. Add caps, novelty, exploration, and newcomer fairness.

---

## 13. Invariants

IDKGraph should be designed around machine-checkable invariants.

Examples:

1. Every integrated artifact has provenance.
2. Every high-risk artifact has an independent verification path.
3. Every WorkUnit has explicit acceptance conditions.
4. Every `supersedes` edge points to an existing prior object.
5. The executable dependency projection has no unresolved cycle.
6. Every canonical claim has an owner/source and confidence/evidence status.
7. Every canonical document has at least one incoming navigation/discovery path unless explicitly marked archival.
8. A node cannot simultaneously be `accepted` and `rejected` in the same version without an explicit conflict object.
9. Agent-generated changes retain agent/model/tool provenance.
10. No autonomous agent can both propose and solely authorize the same protected change.

The graph becomes useful when these invariants are executable rather than prose only.

---

## 14. Minimal implementation schema

A first machine-readable WorkUnit should contain at least:

```yaml
id: WU-...
type: work_unit
title: ...
state: proposed|specified|ready|executing|candidate|verifying|accepted|rejected|integrated
inputs: []
outputs: []
requires_all: []
requires_any: []
blocks: []
acceptance_tests: []
risk: low|medium|high|critical
estimated_cost: {}
expected_impact: ...
expected_information_gain: ...
provenance: {}
assigned_to: []
verifiers: []
created_at: ...
supersedes: []
```

The initial graph can be serialized as JSON/YAML/JSON-LD and rendered into human-friendly Markdown. The repository remains Git-native; a graph database is not required for P0.

---

## 15. P0 implementation order

1. Define stable IDs and schemas for Goal, Question, WorkUnit, Artifact, Evidence, Decision, and Document.
2. Store a small IDKGraph in versioned JSON/YAML.
3. Build the executable DAG/AND-OR projection and cycle checker.
4. Build a documentation/concept projection and broken/orphan link checks.
5. Add provenance fields compatible with W3C PROV concepts.
6. Add the WorkUnit state machine/Petri-net projection.
7. Add task-ranking metrics: impact, EIG, unlock, cost, risk.
8. Add contributor/task matching only after the graph produces useful WorkUnits.
9. Experiment with e-graphs and stigmergic discovery as specialized layers, not as the foundation.

---

## 16. References

- W3C PROV overview and PROV-DM, 2013: provenance model for entities, activities, agents, derivations, collections, and validation constraints.
- Willsey et al., `egg: Fast and Extensible Equality Saturation`, POPL 2021; republished in Communications of the ACM in 2026.
- van der Aalst et al., `Soundness of workflow nets: classification, decidability, and analysis`, Formal Aspects of Computing, 2011.
- Söldner and Plump, formalisation of the double-pushout graph-transformation approach in Isabelle/HOL, 2023/2024.
- Di Caro and Dorigo, AntNet / stigmergic distributed network control.

## Working decision

Use a **typed temporal directed hypergraph as the canonical project representation**. Enforce simpler mathematical semantics through projections instead of forcing the entire project into one graph family.

The most important early projection is the executable AND/OR task DAG. The most important trust projection is provenance. The most important self-evolution property is that every semantic graph change remains observable, reversible, attributable, and verifiable.
