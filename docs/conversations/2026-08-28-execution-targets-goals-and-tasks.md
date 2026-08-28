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

The repository's broad goals remain coherent, but several execution trackers described an older dependency state.

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

### Planning artifacts

Added on branch `planning/execution-target-graph-v0`:

- `docs/planning/EXECUTION_TARGET_GRAPH.md` — T0-T6 dependency graph, observable completion evidence, and NOW/NEXT/PARALLEL queues;
- `docs/planning/README.md` — index explaining the roles of goals, roadmap, priorities, execution graph, issues, and IDKGraph.

The execution graph intentionally prefers convergence and executable evidence over creating new protocols, large architecture documents, or large issue batches.

### Canonical tracker updates

Updated **Issue #5** from a general validator/benchmark request into the current P0 verifier task:

- explicitly recognizes the canonical VerificationResult contract as landed;
- makes executable verifier-owned checks the missing capability;
- defines a minimal Phase A verifier MVP;
- defers benchmark expansion until a 5–10 task first cohort is replayable.

Updated **Issue #4** to:

- recognize #3 as completed;
- depend on #34/#37 for canonical worker execution and #5 for executable verification;
- start with two isolated attempts before growing to 3–5;
- require replay, independent verification, and failure isolation before advanced scheduling.

Updated **Issue #16** to:

- mark #3 and #7 as completed foundations;
- recognize the canonical VerificationResult contract as landed;
- identify T1/T2/T3 as the blocking product gates;
- move #6/#17 to non-blocking parallel work;
- move #2/#30 to downstream real-task validation rather than treating them as prerequisites for implementing v0.1.

### Canonical worker integration gate

Rechecked PR #34.

Its current head has green Node CI and Phase 0 schema checks. GitHub currently reports it mergeable, but the branch has diverged from current `main`, which now contains the new verification-contract/backpressure work.

A PR comment therefore records the safe order:

1. synchronize #34 with current `main`;
2. rerun CI on that synchronized head;
3. execute Docker acceptance #37 against that head;
4. attach positive + negative runtime evidence;
5. obtain independent review;
6. integrate as the canonical T1 worker boundary.

## Deliberate non-actions

- no new large issue cohort was created because review capacity is already constrained;
- no autonomous merge was performed;
- no new verifier protocol was introduced;
- no advanced scheduler was started before a stable two-worker baseline;
- no broad repository restructure was bundled into this planning pass.

## Project rule preserved

This turn is stored publicly in the repository under the standing project-memory rule. No autonomous self-approval or self-merge is performed.
