# ADR-0005: IDKGraph and Guarded Self-Evolution

Date: 2026-08-28
Status: Proposed / experimental

## Context

IDKMesh needs to coordinate goals, unresolved questions, hypotheses, tasks, evidence, artifacts, decisions, documentation, humans, AI agents, and compute resources. It also aims to become progressively better at maintaining its own repository structure and project memory.

A single plain task DAG cannot represent contradictions, alternatives, provenance, cross-document concepts, or project history. Conversely, a fully general graph without constrained operational projections is difficult to validate and schedule.

Self-evolution also creates a safety problem: a repository that can rewrite itself must not permit an autonomous actor to change goals, tests, policy, documentation, and authorization boundaries and then approve the same change.

## Decision

Adopt the following as the default architecture hypothesis for experimentation:

1. The canonical semantic project model will be a **typed temporal directed hypergraph**, called **IDKGraph**.
2. Specialized formal projections will be derived from the canonical graph:
   - executable AND/OR task DAG;
   - Petri-net/workflow view for lifecycle/concurrency;
   - provenance graph using W3C PROV concepts where practical;
   - documentation/concept graph;
   - contributor/task matching graphs;
   - optional e-graphs only for genuine equivalence/equality-saturation problems.
3. Repository/project semantic changes will retain append-only provenance/event history in addition to Git history.
4. Self-evolution will follow a **guarded feedback loop**:
   `observe -> analyze -> propose rewrite -> simulate/sandbox -> verify -> independent review/policy gate -> integrate -> measure outcome -> learn`.
5. Structural changes should be represented where possible as typed graph-rewrite rules with preconditions, transformations, postconditions, and risk classes.
6. Self-evolution is multi-objective. It must consider correctness, consistency, provenance, navigation, modularity, newcomer accessibility, reviewability, security, uncertainty reduction, and maintainer leverage rather than optimizing a single repository-health metric.
7. Autonomy must be earned in stages. High-risk semantic, governance, security, or architectural changes continue to require independent approval.

## Safety invariants

- No autonomous actor may propose and solely authorize the same protected change.
- Acceptance tests cannot be silently weakened to make a proposal pass.
- Important evidence and rejected alternatives are superseded/archived with provenance rather than silently deleted.
- Autonomous changes are bounded and reversible unless a separately reviewed migration requires otherwise.
- Generation rate must remain controlled by verification/review capacity.

## Rationale

### Why a hypergraph?

Many project relations are naturally many-to-many, for example a set of inputs and constraints producing an artifact that is jointly verified by several tests and reviewers. Hyperedges preserve this structure directly.

### Why projections?

Different problems require different mathematics. Executable tasks benefit from DAG/AND-OR semantics; concurrency can use Petri nets; provenance has established entity/activity/agent semantics; equivalence optimization can use e-graphs. Forcing all of these into one formalism would weaken clarity and validation.

### Why graph rewrites?

Explicit rewrite rules make self-maintenance inspectable, bounded, testable, and learnable. They are safer than unconstrained repository-wide text generation.

### Why guarded evolution?

IDKMesh should be able to learn from the effects of its own maintenance changes, but project survival, provenance, and governance matter more than edit speed.

## Consequences

Positive:

- one semantic model can connect tasks, evidence, documentation, decisions, and contributors;
- task scheduling remains mathematically simpler through projections;
- repository maintenance can become measurable and eventually partially automated;
- graph changes can be audited and compared experimentally;
- the system gains a path toward dogfooding IDKMesh on its own repository.

Costs/risks:

- stable IDs and schema governance add initial complexity;
- extracting semantic claims/duplicates/contradictions from prose is uncertain and must not be treated as deterministic truth;
- multi-objective optimization requires careful metrics and can still be gamed;
- autonomous restructuring could create churn if not rate-limited;
- graph projections can become inconsistent if they are manually duplicated rather than generated from canonical state.

## Alternatives considered

### One global task DAG

Rejected as the canonical model because it cannot naturally represent contradictory evidence, competing hypotheses, semantic documentation links, or cyclic knowledge relationships.

### One generic property graph only

Useful storage option, but insufficient as the design itself because operational semantics and invariants remain implicit.

### E-graph as the global representation

Rejected. E-graphs are powerful when the primary relation is equivalence. Most IDKMesh relations are dependency, provenance, support, contradiction, assignment, verification, or supersession rather than equality.

### Fully autonomous repository agent

Rejected as an initial approach because it creates circular authorization, metric-gaming, and irreversible structural-risk problems.

## Implementation references

- `docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`
- `docs/architecture/SELF_EVOLVING_REPOSITORY.md`
- `docs/community/COMMUNITY_GROWTH_DYNAMICS.md`
- `schemas/idkgraph.schema.json`
- `examples/idkgraph.example.yaml`

## Review criteria

This ADR should remain experimental until the project demonstrates that:

1. the graph representation helps create/coordinate real WorkUnits;
2. generated projections remain understandable and validate useful invariants;
3. repository observatory metrics identify real maintenance problems;
4. at least one bounded rewrite rule improves repository health without unacceptable reviewer burden;
5. outcome tracking can detect regressions and unsuccessful restructures.
