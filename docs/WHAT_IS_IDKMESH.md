# What Is IDKMesh?

## Short answer

**IDKMesh is a general framework and experimental platform for distributed human + AI collaboration on complex projects.**

It is not intended to be only one application.

The first major use case is collaborative software engineering, because software gives us unusually strong verification tools: tests, compilers, static analysis, reproducible builds, benchmarks, code review, and version control. But the underlying framework should be general enough to support other research and engineering projects later.

## Three layers

### Layer 1 — IDKMesh Core

Reusable infrastructure for coordinating work:

- Goal Graph / evolving intent;
- Work Unit protocol;
- participant and capability discovery;
- task decomposition;
- scheduling and matching;
- isolated execution;
- artifact exchange;
- verification;
- provenance;
- reputation and contribution history;
- governance primitives;
- experiment and metrics infrastructure.

This is the part that other projects should eventually be able to use.

### Layer 2 — Domain Packs / Project Protocols

Different projects need different schemas, validators, roles, and constraints.

Examples:

- software development;
- scientific research;
- data analysis;
- simulation;
- documentation / knowledge projects;
- hardware design;
- open educational resources.

A domain pack may define:

- allowed Work Unit types;
- verification rules;
- domain-specific worker roles;
- risk classes;
- required evidence;
- integration rules;
- project-specific metrics.

### Layer 3 — Actual Projects

Independent projects can run on top of IDKMesh.

Examples:

```text
IDKMesh Core
   |
   +-- Project A: build an open-source application
   +-- Project B: reproduce a scientific result
   +-- Project C: improve an AI benchmark
   +-- Project D: create an open knowledge base
   +-- Project E: IDKMesh improving IDKMesh
```

The first practical project should be **IDKMesh improving IDKMesh**, because it creates a tight feedback loop and directly tests the platform.

## Why the framework approach matters

If IDKMesh is defined as one giant application, contributors must agree on that application's product goal before they can contribute meaningfully.

If IDKMesh is a collaboration framework, people can contribute to different layers without sharing the exact same product perspective.

A distributed-systems researcher can improve scheduling.
A security engineer can improve sandboxing and provenance.
An AI researcher can study model diversity and verification.
A mathematician can work on allocation and aggregation mechanisms.
An economist can study incentives.
A governance researcher can study decision systems.
A community organizer can improve onboarding and contributor health.
A software engineer can build the coordinator, worker, or verifier.
A designer can improve contributor UX.
A domain expert can define project-specific Work Units and acceptance criteria.

Their work can compose through explicit interfaces.

## Project identity

IDKMesh is best understood simultaneously as:

1. **an open-source framework** — reusable software/protocols for distributed collaboration;
2. **a research program** — experiments about collective intelligence, distributed work, verification, incentives, and governance;
3. **a community** — humans and AI agents from different disciplines working in public;
4. **a reference implementation** — software that demonstrates the protocols;
5. **a meta-project** — a system that should eventually help improve itself;
6. **a substrate for other projects** — future projects should be able to use IDKMesh without becoming IDKMesh itself.

## What IDKMesh is not

It is not merely:

- a multi-agent chat room;
- a GitHub bot;
- a distributed inference cluster;
- a volunteer-compute clone;
- a single coding agent;
- one fixed enterprise application;
- a blockchain network;
- a social network for developers.

It may borrow mechanisms from all of those areas, but the unifying problem is **how to convert heterogeneous, imperfect, distributed participation into verified useful work on evolving goals**.

## The core abstraction

A useful conceptual flow is:

```text
uncertain goal
   -> competing interpretations / hypotheses
   -> decomposed Work Units
   -> matched humans / agents / machines
   -> independent candidate artifacts
   -> verification and evidence
   -> integration / rejection / further questions
   -> updated Goal Graph
   -> next Work Units
```

This loop is more fundamental than any specific application built on top of it.

## Architectural boundary

The core should know as little as possible about a specific model, coding environment, Git forge, or project domain.

The core should provide primitives for:

- identity/capability;
- goals and dependencies;
- bounded work;
- artifacts;
- evidence;
- verification;
- scheduling;
- trust/provenance;
- governance.

Project-specific behavior should be expressed through adapters, policies, schemas, and domain packs.

## Initial scope

To avoid becoming too abstract, the first implementation is intentionally narrow:

> build and experimentally validate the software-engineering domain on top of the general framework.

That means the first reference implementation will focus on Git repositories, coding agents, tests, isolated worktrees/sandboxes, validators, and integration workflows.

If those abstractions prove useful, generalize them only where evidence supports generalization.
