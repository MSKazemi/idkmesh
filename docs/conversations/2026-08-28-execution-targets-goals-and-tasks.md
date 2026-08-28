# Project Turn: Execution Targets, Goals, and Tasks

Date: 2026-08-28

## User direction

Continue working directly in the public IDKMesh repository, with emphasis on the repository's targets, goals, and tasks.

## Repository state inspected

The current repository was re-inspected rather than relying on an earlier snapshot.

Important changes observed on `main` include:

- an independent `VerificationResult v0.1` contract;
- positive and negative verification fixtures;
- cross-object verification/independence validation in the Phase 0 harness;
- verification-debt/backpressure research and executable controller work;
- additional synthetic R1 diversity experiments;
- continued zero-project-spend compute work.

Open project work still includes the canonical local node (#34/#37), executable validator (#5), multi-worker orchestrator (#4), v0.1 Verified Swarm Runner (#16), main-protection gate (#35), Repository Homeostasis (#36/#38), and ACE community evidence work.

## Main finding

The repository's broad goals remain coherent, but several execution trackers describe an older dependency state.

The most important update is:

> The project no longer needs to design the basic verification result format before starting #5. The contract now exists. The next missing capability is an **executable independent verifier** that runs checks against a real candidate and emits the canonical VerificationResult.

Similarly, the multi-worker orchestrator should be defined as a small two-attempt local loop first, with verification and replay, before introducing advanced scheduling.

## Execution hierarchy selected

The current critical chain is:

```text
protected integration
 -> canonical bounded local worker
 -> executable independent verifier
 -> multi-worker orchestrator
 -> Verified Swarm Runner v0.1
 -> real-task flagship experiment
 -> evidence-driven scaling
```

Community growth, repository homeostasis/IDKGraph, zero-spend compute, and synthetic research continue as parallel capacity-gated tracks rather than replacing the product critical path.

## Repository changes made in this turn

A new planning artifact was added:

- `docs/planning/EXECUTION_TARGET_GRAPH.md`

It maps the project's North Star and hard constraints into targets T0-T6, observable completion evidence, dependencies, and a claimable NOW/NEXT/PARALLEL queue.

The plan intentionally prefers convergence and executable evidence over creating new protocols, large architecture documents, or large issue batches.

## Next tracker maintenance

The existing GitHub Issues #5, #4, and #16 should be updated so their bodies match the current contract state and dependency graph:

- #5: focus first on the executable verifier and a small benchmark cohort;
- #4: start with a two-worker local orchestration loop and canonical ResultManifest/VerificationResult flow;
- #16: mark completed foundations (#3 and #7) and identify T1/T2/T3 as the remaining critical product gates.

## Project rule preserved

This turn is stored publicly in the repository under the standing project-memory rule. No autonomous merge or self-approval is performed.
