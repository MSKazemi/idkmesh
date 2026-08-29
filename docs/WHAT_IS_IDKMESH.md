# What Is IDKMesh?

## Short answer

**IDKMesh is an open research and engineering program building a verification-first coordination framework for distributed human + AI work. Its first reference application is a Git-native Verified Swarm Runner, and this repository is its first self-hosting experiment.**

It is intended to become reusable infrastructure, not only one application. That generality is a design target, not a capability already proven at scale.

The framework, research program, community, reference implementation, and self-hosting experiment are different layers of one system. [`../ITERATION_MODEL.md`](../ITERATION_MODEL.md) defines their shared lifecycle and authority vocabulary.

The first major use case is collaborative software engineering because software gives unusually strong verification tools: tests, compilers, static analysis, reproducible builds, benchmarks, code review, and version control.

## Five views of the same project

IDKMesh is simultaneously:

1. **a coordination framework and protocol set** — bounded work, evidence, provenance, resources, and authority;
2. **a research program** — experiments about collective intelligence, verification, scheduling, diversity, and governance;
3. **an open community** — humans and agents working in public with explicit review/authority boundaries;
4. **a reference application** — the Git-native Verified Swarm Runner;
5. **a self-hosting experiment** — IDKMesh is already being used as the subject of its own repository/community evolution experiments.

These are complementary layers, not separate projects.

## Framework layers

### Layer 1 — IDKMesh Core

Reusable semantics and infrastructure for coordinating work:

- goals, questions, assumptions, and evolving intent;
- WorkUnit contracts;
- task/dependency/evidence graphs;
- participant/capability/resource discovery;
- scheduling and matching;
- isolated execution boundaries;
- artifact exchange;
- verification and evidence aggregation;
- provenance;
- experiment/metrics infrastructure;
- governance and integration authority.

The repository already contains executable pieces of many of these functions, but they are not all packaged as one production service.

### Layer 2 — Domain Packs / Project Protocols

Different projects need different validators, roles, risks, evidence, and integration rules.

Example domains include:

- software development;
- scientific research;
- data analysis and simulation;
- documentation/knowledge projects;
- hardware design;
- open educational resources.

A domain/project layer can define:

- allowed WorkUnit kinds;
- verification rules;
- domain-specific worker roles;
- risk/security classes;
- required evidence;
- integration policies;
- project-specific metrics.

### Layer 3 — Actual Projects

Independent projects should eventually be able to use the framework without becoming IDKMesh itself.

```text
IDKMesh Core
   |
   +-- software-engineering project
   +-- scientific reproduction project
   +-- benchmark-improvement project
   +-- knowledge/documentation project
   +-- IDKMesh improving IDKMesh
```

The final item is not merely future intent: this repository already runs bounded self-observation, CI/evolution, IDKGraph, and community-growth experiments against itself.

## What exists today

Current `main` includes, among other things:

- WorkUnit v0.2 as the current bounded-work semantic contract;
- ResultManifest/EvaluatorPlan/VerificationResult evidence separation;
- experiment and benchmark schemas;
- deterministic simulators and analysis code;
- independent verification/provenance checks;
- protocol-neutral worker-adapter infrastructure plus A2A/MCP mappings;
- zero-project-spend compute admission/routing experiments;
- repository graph/observability/link-integrity tooling;
- GitHub-native evolution and community-growth experiments;
- protected integration through stable PR gates.

This means IDKMesh is beyond a pure architecture proposal. It does **not** mean the full reference runner or a distributed production mesh is complete.

## The core abstraction

A useful conceptual flow is:

```text
uncertain goal
   -> competing interpretations / hypotheses
   -> bounded WorkUnits
   -> matched humans / agents / tools / resources
   -> candidate artifacts + worker provenance
   -> independent verification and evidence
   -> explicit integration / rejection / further questions
   -> updated project state
   -> next bounded work
```

The critical trust rule is that stages do not grant themselves the authority of later stages:

```text
worker completion != acceptance
verification recommendation != canonical integration
```

## Why the framework approach matters

If IDKMesh were one giant application, contributors would have to agree on that application's complete product goal before making useful progress.

A framework lets different expertise compose through explicit contracts:

- distributed-systems researchers can study scheduling/locality;
- security engineers can study sandboxing/provenance;
- AI researchers can study model/agent diversity and verification;
- mathematicians can study allocation, dependence, and aggregation;
- governance/community researchers can study review, authority, and contributor capacity;
- software engineers can improve adapters, validators, tooling, and runner UX;
- designers/documentarians can reduce comprehension and coordination cost;
- domain experts can define project-specific tasks and evaluation criteria.

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

It may integrate mechanisms from those areas, but the unifying problem is **how to convert heterogeneous, imperfect, distributed participation into verified useful work on evolving goals**.

## Architectural boundary

The semantic core should know as little as practical about a specific model vendor, agent harness, Git forge, cloud, or domain.

External systems should connect through adapters and protocol mappings. In particular, A2A/MCP are useful interoperability surfaces; IDKMesh should not create another generic transport simply to carry its own WorkUnit semantics.

Project-specific behavior belongs in versioned schemas, policies, adapters, validators, domain/project configurations, and evidence rules.

## Current scope

The implementation is intentionally focused on the software-engineering domain and GitHub-native self-hosting because they offer strong observable verification and provenance.

The immediate task is not to generalize everything. It is to make the current local/interop/evidence path coherent, independently reviewed, reproducible, and useful—then generalize only where observed evidence supports it.

For the current truth and next gates, see:

- [`../README.md`](../README.md);
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
- [`../schemas/README.md`](../schemas/README.md);
- [`../ROADMAP.md`](../ROADMAP.md);
- [`README.md`](README.md) for documentation navigation.
