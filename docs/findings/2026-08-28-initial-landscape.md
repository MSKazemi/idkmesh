# Initial Landscape Findings — 2026-08-28

## Naming findings

The original working phrase **"I Don't Know"** was judged philosophically strong but poor as a primary public software name because it is extremely generic and difficult to search or distinguish.

An exact-name GitHub check for `idkmesh` / `IDKMesh` returned no existing repositories at the time of selection, which supported choosing **IDKMesh**.

`SwarmForge` was considered as a candidate but was already used in the AI-agent ecosystem, so it was rejected to reduce confusion.

## Related repository check: NovaFabric

The owner's existing public `MSKazemi/novafabric` repository was inspected before naming IDKMesh. NovaFabric is a different project: an open-source execution-capsule/replay system for AI and HPC workloads focused on capture, sealing, replay, diffing, audit evidence, provenance, and reproducibility.

Conclusion: IDKMesh should remain a distinct project rather than reusing the NovaFabric name. Future integration between the projects may be possible because provenance/replay could eventually be useful inside a distributed collective-intelligence system, but the product theses are different.

## Early conceptual finding: scale does not imply quality

The motivating question "Can 100 smaller-model vibe coders guarantee the quality of one strong coder/model?" has no general guarantee merely from increasing the number of contributors or agents.

Reasons include:

- correlated model errors;
- duplicated effort;
- integration failures;
- inconsistent assumptions;
- weak or circular review;
- security and supply-chain risk;
- communication overhead;
- verification becoming the bottleneck.

This produced an architectural principle: **proposal generation and independent verification must scale together**.

## Early conceptual finding: ambiguous goals require explicit state

Traditional project management assumes a sufficiently clear goal that can be decomposed into tasks. IDKMesh starts one level earlier: participants may disagree about what the goal means.

Therefore the system should eventually represent:

- alternative goal interpretations;
- hypotheses;
- assumptions;
- confidence;
- evidence;
- contradictions;
- experiments;
- decisions and their provenance.

A single issue tracker or flat backlog is likely insufficient as the core abstraction.

## Early conceptual finding: use a heterogeneous stack of coordination mechanisms

No single mechanism — voting, market pricing, blockchain consensus, reputation, or one optimization objective — appears suitable for every IDKMesh decision.

Likely separation:

- empirical questions -> tests/experiments;
- replicated critical state -> consensus/quorums where necessary;
- disconnected collaborative state -> CRDT/eventual consistency where appropriate;
- resource allocation -> scheduling/optimization/markets;
- uncertain strategy selection -> bandits/Bayesian methods;
- social/project policy -> governance/social-choice mechanisms;
- critical software correctness -> testing/formal verification/security review.

## Early implementation finding: simulate before decentralizing

The first useful prototype should not begin with millions of real machines. A single process or small cluster can simulate thousands of logical agents and nodes, making it possible to test task assignment, failure, reputation, diversity, verification, and communication policies cheaply and reproducibly.

A promising first research program is to compare coordination policies under controlled workloads and adversarial conditions before building a real volunteer-compute substrate.
