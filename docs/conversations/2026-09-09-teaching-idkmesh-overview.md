# Teaching overview: what exists in IDKMesh

**Date:** 2026-09-09  
**Source main commit inspected:** `1460713f1b5a8554ec8b7c4036c5129618de08e4`

This note explains the current repository in a simple mental model and distinguishes implemented mechanisms from research ambitions.

## The shortest explanation

IDKMesh is a verification-first coordination system for humans, AI agents, software tools, and compute working on uncertain goals.

The core idea is:

```text
uncertain goal
  -> bounded WorkUnit
  -> worker/agent attempt
  -> candidate artifacts + ResultManifest
  -> independent EvaluatorPlan / VerificationResult
  -> evidence report
  -> explicit human/governance integration decision
  -> updated project state
```

The authority rule is:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human approval
```

## Five things IDKMesh is at the same time

1. **Coordination framework / protocol set** — contracts for work, evidence, provenance, resources, and authority.
2. **Reference product** — a Git-native Verified Swarm Runner.
3. **Research program** — experiments on collective intelligence, verification, diversity, scheduling, and governance.
4. **Open community** — humans and agents contributing through GitHub with explicit review boundaries.
5. **Self-hosting experiment** — the repository uses its own evolution, graph, CI, and community-growth mechanisms to study how it changes.

## What is implemented now

Current `main` already includes:

- WorkUnit v0.2 and versioned schemas;
- ResultManifest, EvaluatorPlan, and VerificationResult separation;
- cross-object provenance and integrity validation;
- deterministic simulators and experiment harnesses;
- verification, quorum, correlation, and evidence-aggregation research;
- protocol-neutral worker adapter infrastructure;
- A2A and MCP mappings and conformance helpers;
- zero-project-spend compute admission experiments;
- IDKGraph repository/evidence observability;
- GitHub-native repository evolution workflows;
- ACE community-growth workflows and ledgers;
- protected-main CI gates;
- an installable `idkmesh` Python package with the `gate-audit` CLI and GitHub Action.

## What is not finished

The repository should not yet be described as:

- a production Internet-scale distributed mesh;
- a finished many-agent autonomous software company;
- a system proven to coordinate thousands or millions of machines;
- a system where agents may autonomously approve or merge their own work;
- a polished end-to-end Verified Swarm Runner with multiple production worker adapters;
- scientific proof that multi-agent/decomposition strategies outperform alternatives.

The project has substantial infrastructure, but the main bottleneck is now convergence and observed evidence rather than inventing more foundational vocabulary.

## The most important concepts

### 1. WorkUnit

A WorkUnit is a bounded task contract. It defines scope, permissions, security/resource requirements, expected outputs, and verification expectations. The point is to give workers limited authority rather than the whole project.

### 2. Candidate vs canonical state

A worker produces a candidate. A candidate is not automatically accepted. It must pass verification and then an explicit integration decision.

### 3. Independent verification

Verification is a separate actor/system. Worker claims, verifier recommendations, and merge authority are intentionally distinct.

### 4. Evidence and provenance

The repository tries to bind claims to exact artifacts, source revisions, identities, checks, and decision history. Evidence is first-class state, not an afterthought.

### 5. Iteration

An iteration is not a commit. It is a closed evidence cycle:

```text
baseline
 -> bounded action or deliberate no-op
 -> execution
 -> verification
 -> decision
 -> outcome observation
 -> state/belief update
```

A failed experiment can still be useful if it reduces uncertainty.

### 6. Improvement

Improvement is multi-dimensional and evidence-backed. More commits, issues, stars, or PRs are not automatically improvement. Security, governance, verification, maintainability, reviewer burden, community capacity, and information gain all matter.

### 7. IDKGraph

The conceptual state is a collection of interacting graphs:

- goals/questions/hypotheses;
- work/dependencies;
- evidence/provenance;
- participants/capabilities/resources.

Git and GitHub are the current storage and actuation surfaces over that semantic model.

### 8. ACE — Autocatalytic Community Evolution

ACE asks whether one useful contribution can create conditions for another useful contribution.

Its desired loop is:

```text
verified contribution
 -> lower friction / clearer knowledge
 -> bounded Growth Seed
 -> new contributor or reviewer
 -> independent verification
 -> verified descendant
 -> adapt future growth strategy
```

ACE explicitly does not optimize raw stars, forks, comments, commits, or PR volume. Its target is closer to verified useful descendants per unit of scarce reviewer/maintainer attention.

At the time of this note, the live ACE ledger reports `CONSOLIDATE` mode, a capacity multiplier around `0.562`, and autonomous public ACE actuation disabled. The current bootstrap cohort still has no verified external descendants, so the system correctly recommends holding the cohort rather than manufacturing growth activity.

## The first real product surface

The most concrete shipped user-facing capability is currently `idkmesh gate-audit`.

It analyzes a panel of verifier/reviewer votes and reports signals such as effective independent vote count, dependence/correlation structure, and seeded known-bad probe breach rate. It is diagnostic only and does not grant acceptance or merge authority.

## The current strategic bottleneck

The highest-level priority is no longer "design the architecture." The repository already has a lot of architecture.

The current priorities are:

1. finish one coherent local Verified Swarm Runner path end to end;
2. demonstrate at least two materially different worker implementations behind the same adapter semantics;
3. run real controlled comparative WorkUnit experiments;
4. strengthen A2A/MCP interoperability evidence;
5. reduce human/reviewer bottlenecks and obtain genuine external participation;
6. package a reproducible public release that newcomers can install, run, inspect, and replay.

## A useful mental model

Think of IDKMesh as a small experimental operating system for collective work:

```text
Constitution / governance
        |
Goals + uncertainty + evidence
        |
Bounded work contracts
        |
Humans / agents / tools / compute
        |
Candidate artifacts
        |
Independent verification
        |
Explicit integration authority
        |
Canonical repository state
        |
Outcome evidence and next questions
```

The long-term ambition is a large heterogeneous intelligence mesh. The current repository is the GitHub-native laboratory where the contracts, evidence mechanisms, community dynamics, and control loops needed for that ambition are being tested.

## Suggested learning order

To understand the project efficiently, read in this order:

1. `README.md`
2. `docs/WHAT_IS_IDKMESH.md`
3. `ITERATION_MODEL.md`
4. `ARCHITECTURE.md`
5. `EVOLUTION.md`
6. `schemas/README.md`
7. `COMMUNITY_GROWTH_ENGINE.md`
8. one concrete subsystem or experiment that interests you

The key is to keep asking: **what is the goal, what is the bounded action, what is the evidence, who has authority, and what did we actually learn?**
