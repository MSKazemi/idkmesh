# IDKMesh Evolution Strategy

**Status:** current strategic direction. Mechanisms remain experimental until their stated evidence gates pass.

IDKMesh is deliberately ambitious, but repository evolution should follow one rule:

> **Build the smallest verified capability that removes the current evidence bottleneck; do not add another layer merely because the long-term vision contains it.**

## Project identity

> **IDKMesh is a verification-first coordination fabric for humans, AI agents, tools, and heterogeneous compute working on uncertain goals.**

It should connect existing agents, protocols, Git/GitHub workflows, and execution systems rather than replacing commodity infrastructure.

The five coupled roles of the repository are:

1. coordination framework/protocol set;
2. Git-native Verified Swarm Runner reference application;
3. collective-intelligence research program;
4. open human+agent community;
5. self-hosting repository-evolution experiment.

See [`ITERATION_MODEL.md`](ITERATION_MODEL.md) for the canonical lifecycle and authority model.

## Current checkpoint

The project has already passed the earliest “design the first contracts/simulator” stage.

Current `main` includes:

- WorkUnit v0.2 and related versioned schemas;
- ResultManifest / EvaluatorPlan / VerificationResult separation;
- experiment, benchmark, compute, CI, and repository-graph contracts;
- deterministic simulation and analysis code;
- independent verification/provenance machinery;
- non-selecting reporting/replay research;
- protocol-neutral worker adapter infrastructure;
- A2A/MCP mappings plus identity/conformance helpers;
- zero-project-spend compute admission/routing research;
- IDKGraph observability/link-integrity tooling;
- repository evolution/CI-shadow/community-growth control experiments;
- protected `main` with stable Python 3.11/3.13 gates.

The immediate challenge is therefore **convergence and observed evidence**, not additional foundational vocabulary.

## Reference product

The first reference product remains a Git-native Verified Swarm Runner.

Target lifecycle:

```text
bounded Git task
 -> WorkUnit v0.2
 -> replaceable worker adapter(s)
 -> isolated candidate artifacts
 -> ResultManifest
 -> verifier-owned EvaluatorPlan
 -> independent VerificationResult
 -> evidence/report/replay
 -> explicit human/governance integration decision
```

The repository has substantial pieces of this flow, but should not call the reference runner complete until a newcomer can run the coherent path using current independently reviewed adapters and inspect/replay its evidence without relying on historical branches.

## Build vs reuse

### IDKMesh should own

- goal/question/evidence semantics;
- bounded WorkUnit authority and dependencies;
- coordination/decomposition policy;
- capability/resource matching semantics;
- verification and evidence aggregation;
- provenance bindings;
- experiment/benchmark contracts;
- community/governance feedback boundaries;
- measured self-improvement under external authority constraints.

### Prefer integration for

- Git/GitHub collaboration/history;
- A2A agent-to-agent communication;
- MCP tool/context/task integration;
- existing coding-agent harnesses;
- OCI containers and established stronger isolation systems;
- standard provenance/attestation patterns;
- mature networking/P2P stacks when networking is actually required.

Rule:

> **Innovate in coordination, verification, evidence, and collective intelligence—not in commodity transport or isolation without evidence of a real gap.**

## Interoperability direction

IDKMesh already has executable A2A/MCP mapping infrastructure. The next interoperability question is not whether to invent another task transport; it is whether current external SDKs/lifecycles can preserve IDKMesh semantics and provenance through the shared adapter boundary.

The intended relationship is:

```text
                 IDKMesh WorkUnit
     (scope + resources + risk + evidence + verification)
                         |
          +--------------+--------------+
          |                             |
          v                             v
       A2A binding                  MCP binding
          |                             |
          +--------------+--------------+
                         |
                         v
                external worker/tool
                         |
                         v
               canonical ResultManifest
                         |
                         v
              independent verification
```

Transport success must remain `pending_verification`, never automatic acceptance.

## Architecture layers

### A — Community and project surface

GitHub issues, pull requests, documentation, Pages, releases, IDKIPs, experiments, and human review remain the current public coordination surface.

### B — Goals, questions, and evidence

Use typed graph/project records to keep uncertainty, hypotheses, decisions, dependencies, artifacts, and provenance explicit.

### C — Bounded work

WorkUnit v0.2 defines the current vendor-neutral task semantics. Future breaking changes require evidence that the existing version cannot represent a necessary invariant.

### D — Worker adapters

Keep coordinator-facing execution replaceable. Local/direct, A2A/MCP, coding-agent, human/GitHub, and future worker systems should map through the same semantic boundary rather than importing their internals into coordinator logic.

### E — Resource admission and execution

Execution remains bounded by WorkUnit permissions/security requirements and repository policy. Project spending is currently capped at zero by repository policy; work cannot authorize billing by itself.

### F — Verification and evidence

Independent checks, provenance, reproducibility, correlation awareness, evidence aggregation, and human escalation are first-class. Generation volume cannot outrun verification capacity.

### G — Integration authority

Canonical state changes only through the repository/governance integration boundary. A worker, verifier, controller, benchmark, CI planner, or statistical score cannot grant itself merge authority.

### H — Remote mesh/federation

Remote workers, multi-machine state, federation, and stronger trust infrastructure come only after the local product/evidence path is coherent enough to justify them.

## Current evolution priorities

### Priority 1 — finish a coherent local runner path

Make one bounded task flow understandable and reproducible end to end with current contracts, multiple attempts, independent verification, replay, and explicit human decision.

### Priority 2 — prove worker interchangeability

Run at least two materially heterogeneous worker implementations through the same coordinator-facing semantics without changing coordinator core.

### Priority 3 — execute real comparative WorkUnit research

The five-arm decomposition benchmark exists. Issue #15 remains open because the observations must become real controlled evidence, not because another WorkUnit schema is needed.

### Priority 4 — strengthen interoperability evidence

Use official/current A2A/MCP SDK/type behavior where feasible; retain semantic round-trip, artifact, identity, and provenance evidence.

### Priority 5 — reduce human/reviewer bottlenecks

Measure independent review time, recurrence, disagreement, and onboarding cost. Do not fake community independence with automation or same-owner evidence.

### Priority 6 — package a reproducible public release

Turn research infrastructure into a small install/run/inspect/replay experience with known limitations and exact evidence.

## Scaling strategy

The current scalability hypothesis remains hierarchical/federated locality:

```text
node -> cell -> region/fabric -> federation
```

Do not centralize every worker/task/evidence event globally. Test which summaries can safely cross levels while detailed work remains local.

Scale steps should proceed approximately through:

```text
single-machine coherent product
 -> small number of real heterogeneous workers/resources
 -> 3–10 machine experiment
 -> external/community cohort
 -> larger federated experiments
 -> Internet-scale simulation and progressively larger deployment
```

Each step requires measurements for throughput, latency, state/control overhead, failure/churn, security, resource cost, verification cost, and human governance/review load.

## Research priorities

Useful research families include:

- diversity vs replication under matched budgets;
- adaptive fan-out;
- error-correlation-aware routing;
- verification backpressure and markets;
- sequential/anytime evidence;
- decomposition strategy;
- goal ambiguity as branching search;
- human-attention scheduling;
- community reproduction/capacity;
- repository evolution and Anti-Goodhart controls;
- provenance/isolation/federation trade-offs.

The desired output is evidence about boundary conditions, including negative results—not a proof that the preferred architecture must win.

## Community evolution

The community must grow with the software.

Important milestones are not raw issue/PR volume. They include:

- external contributors finding bounded useful work;
- recurring contributors;
- genuinely independent reviewers;
- contributors owning subsystems/benchmarks/docs;
- reduced maintainer concentration;
- reproducible public results that outsiders can challenge or extend.

ACE and related community experiments should remain quiet and capacity-bounded. `0` autonomous public actions is a valid outcome.

## Decision rule for new mechanisms

Before adding a major mechanism, ask:

1. What current bottleneck or falsifiable question does it address?
2. Is an open standard/project already adequate?
3. What evidence would show the mechanism helps?
4. What is the authority/security boundary?
5. What does it cost in verification and contributor complexity?
6. Can the idea be tested reversibly at smaller scale?
7. Does it improve the current evidence bottleneck, or merely add architecture?

If these questions do not have good answers, prefer a smaller experiment, integration, documentation correction, or no-op.

## Non-goals for the current stage

Do not prematurely require or claim:

- a custom generic agent protocol;
- a custom cryptocurrency/token;
- a public blockchain;
- autonomous self-approval/merge;
- a one-million-node production network;
- production hostile multi-tenant guarantees without isolation evidence;
- synchronized giant-model training on volunteer Internet machines;
- superiority of many-agent/decomposition strategies before controlled results;
- one universal reputation score or one permanent objective function.

## Evolution test

A healthy project transition should leave this chain:

```text
baseline
 -> bounded action or deliberate no-op
 -> exact artifacts/provenance
 -> independent verification
 -> explicit decision
 -> observed outcome
 -> updated evidence/state
 -> next bounded question
```

That is the practical meaning of IDKMesh “learning”: inspectable, evidence-linked state and policy change—not hidden self-training or activity for its own sake.

See [`ROADMAP.md`](ROADMAP.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`schemas/README.md`](schemas/README.md), and [`docs/README.md`](docs/README.md) for the current implementation and navigation layers.
