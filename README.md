# IDKMesh

> **I don't know. You don't know. Together, the mesh can discover, build, and know.**

**IDKMesh** is an open-source research and engineering community exploring how very large numbers of humans, AI agents, and heterogeneous computers can collaborate on useful software and research — from one laptop to potentially millions of participating machines.

The final system is **not fully known yet**. That uncertainty is intentional.

The central question is:

> **Can a large open community of humans and AI agents collectively discover goals, decompose work, build, verify, and maintain enterprise-quality systems better than isolated developers or agents can?**

## Community first

**The community is part of the product.**

IDKMesh cannot first build a giant collaboration system and add contributors later. Every substantial addition should consider whether it makes the project easier to discover, understand, join, contribute to, review, maintain, and eventually lead.

You do **not** need to understand the whole architecture before helping.

Start here:

1. Read this README.
2. Read [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Pick a contribution path in [`COMMUNITY.md`](COMMUNITY.md).
4. Open a question, research idea, community improvement, bug report, or small pull request.

If something is confusing, **that itself is useful project feedback**.

### Want one bounded task right now?

ACE (Autocatalytic Community Evolution) is testing whether useful repository activity can create the next useful contribution opportunity while keeping review load bounded. The Bootstrap Cohort is intentionally small, and the public front door should show **open work, not historical work**.

Current open starter paths:

Before starting one, check its assignees, recent comments, and linked pull requests, then leave a short comment stating what you plan to change.

- [#24 — audit the 15-minute newcomer path](../../issues/24) — documentation/community; this is the best path if you are new to IDKMesh;
- [#167 — independently review IDKGraph orphan cohort 1](../../issues/167) — evidence/review; a bounded `good first issue` that records real reviewer attention rather than inventing it.

High-value expert contribution:

- [#138 — independently inspect PR #159 canonical-node evidence](../../issues/138) — security/runtime/evidence review. The automated and same-owner evidence is deliberately **not** treated as independent human approval.

Completed Bootstrap Cohort examples remain public provenance, but are no longer available starter tasks:

- #25 — ACE parent -> descendant evidence links;
- #26 — ACE workflow threat model;
- #27 — ACE population simulation;
- #28 — research-track microtask decomposition.

Check the live [ACE Bootstrap Cohort Observatory](../../issues/109) for the current evidence state. At the time of this update it reports no verified external ACE descendant yet. **That is evidence, not embarrassment.** We deliberately will **not** flood the tracker with Cohort 2 merely because review capacity is healthy.

See [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md), [`docs/community/ACE_BOOTSTRAP_EXPERIMENT.md`](docs/community/ACE_BOOTSTRAP_EXPERIMENT.md), and the [whole-system First Contact audit](docs/audits/2026-08-28-whole-system-first-contact-audit.md).

## IDKMesh in 60 seconds

- **IDK** means *I Don't Know*: incomplete knowledge and competing interpretations are first-class states.
- **Mesh** means a network of people, AI agents, knowledge, tasks, evidence, and compute.
- The first reference domain is **distributed software engineering**.
- Workers should receive bounded **Work Units**, not unlimited access to an entire project.
- Proposals are not trusted just because they came from a strong model, many models, or an expert human.
- Verification, testing, review, provenance, reproducibility, and security scale with generation.
- The project investigates whether many smaller agents can become powerful through diversity, specialization, coordination, competition, and independent verification.
- The repository is also a public research notebook: important decisions, findings, failed ideas, and project conversations should remain discoverable.

## Status

**Exploration / research / architecture / early-community phase.**

This is a good time to contribute because fundamental questions are still open. Architecture critiques, research, experiments, documentation, security analysis, governance work, UX, community building, benchmarks, and negative results are all valuable.

## What are we building first?

The first reference product is a **Git-native Verified Swarm Runner**.

A user gives IDKMesh a bounded repository task. Several replaceable human/AI worker adapters attempt the task in isolated Git worktrees/branches. A separate verifier evaluates the candidates and produces an evidence-backed report for human review.

```text
bounded Git task
      -> Work Contract
      -> isolated worker attempts
      -> independent verification
      -> Evidence Report
      -> human accept / reject / refine
```

The first release does **not** need decentralized networking and does **not** auto-merge into `main`.

This small product lets us test the central thesis before scaling it. Read [`EVOLUTION.md`](EVOLUTION.md) for the current evolution path and [`IDKIPS.md`](IDKIPS.md) for how major competing ideas are proposed and tested.

## Ways to contribute today

You can help even if you are not a core software engineer.

| You are interested in... | Useful contributions |
| --- | --- |
| Coding | prototypes, simulators, tests, tooling, schedulers, validators |
| AI agents | agent orchestration, decomposition, evaluation, model diversity |
| Distributed systems | scheduling, work stealing, CRDTs, consensus, fault tolerance |
| Security | sandboxing, provenance, supply chain, adversarial workers, Sybil resistance |
| Research | literature, falsifiable hypotheses, experiment design, reproductions |
| Mathematics | graphs, optimization, Bayesian methods, game theory, information theory |
| Documentation | newcomer explanations, tutorials, diagrams, examples, translations |
| Community | onboarding, governance, issue design, contributor growth, accessibility |
| Design / UX | developer experience, workflow design, observability, visual explanations |
| Domain expertise | real-world goals, constraints, tests, evaluation criteria |
| Compute | future volunteer-compute testing; today, help design safe worker protocols |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow and [`COMMUNITY.md`](COMMUNITY.md) for the contributor ladder.

## What are we trying to build?

IDKMesh is primarily a **general coordination framework, research program, and community**, not one fixed application.

A possible long-term structure is:

```text
IDKMesh Core
   |
   +-- domain/project protocols
          |
          +-- distributed software engineering
          +-- scientific/research collaboration
          +-- future collaborative domains
```

The core may eventually provide reusable primitives for:

- evolving goals and uncertainty;
- bounded Work Units;
- dependency/task graphs;
- capability-aware scheduling;
- isolated execution;
- independent verification;
- evidence and provenance;
- reputation and contribution history;
- governance and dispute resolution;
- metrics and observability.

Different projects can add their own validators, policies, roles, and evidence rules.

For a deeper explanation, read [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) and [`GOALS.md`](docs/foundations/GOALS.md).

## Flagship research question: many small coders vs one big coder

One motivating experiment is deliberately simple:

```text
1 strong coding model
        vs
1 small model
        vs
5 small independent models
        vs
10 small independent models
        vs
planner + implementers + tester + reviewer
        vs
parallel task-DAG teams
```

The interesting question is **not** whether 100 weak agents magically equal one frontier model. They do not provide a quality guarantee.

The real question is when this combination helps:

```text
diversity
+ decomposition
+ isolated attempts
+ specialization
+ independent tests
+ criticism
+ selection
+ integration
+ project memory
--------------------------------
= stronger collective engineering?
```

We want reproducible evidence about where this works and where it fails.

Important metrics include hidden-test success, regressions, security, human reviewer time, wall-clock time, compute cost, merge conflicts, error correlation, maintainability, and **verified useful work per unit of human attention and compute**.

See [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) and the project issues.

## Architecture at a glance

A candidate flow is:

```text
Goal / unresolved question
          |
          v
Goal Graph / specification
          |
          v
Task + dependency graph
          |
          v
Scheduler / matching
          |
     +----+--------------------+
     |            |            |
     v            v            v
   Human       AI agent    compute/test worker
     |            |            |
     +------------+------------+
                  |
                  v
          Candidate artifacts
                  |
                  v
       Verification / criticism
   tests | review | fuzz | security
                  |
                  v
        Selection / integration
                  |
                  v
      Canonical project + evidence
                  |
                  v
        Metrics / reputation / memory
```

The current scalability hypothesis is **Fractal Autonomous Cells**:

`node -> cell -> region/fabric -> federation`

Most coordination should remain local, with higher levels exchanging summaries, overflow work, discovery, attestations, and protocol metadata rather than centralizing every task globally.

This is a hypothesis to test, not settled truth. See [`docs/architecture/SCALABILITY_AND_AGILITY.md`](docs/architecture/SCALABILITY_AND_AGILITY.md).

## Project principles

**Community first.** Contributor experience and leadership scalability are engineering concerns.

**Proposal is not proof.** Human- or AI-generated output must be verified appropriately.

**Popularity is not correctness.** Votes, stars, reputation, or majority model agreement cannot replace evidence.

**More agents are not automatically better.** Diversity and independent error matter more than raw count.

**Uncertainty is first-class.** Competing goals, hypotheses, confidence, and unresolved questions should remain explicit.

**Decentralization still needs structure.** Interfaces, ownership, quality gates, security, and governance become more important at scale.

**Scientific analogies are hypotheses, not evidence.** Physics/economics/biology-inspired mechanisms must be converted into falsifiable experiments.

**Cryptographic provenance comes before blockchain.** Add expensive trust infrastructure only when a demonstrated problem requires it.

**Generation must not outrun verification.** AI-generated volume is not progress if humans and validators cannot maintain it.

**Integrate before reinventing.** Reuse open agent, tool, sandbox, provenance, and networking standards when they solve commodity problems; spend IDKMesh complexity on coordination, verification, evidence, and collective intelligence.

## How community and governance work

IDKMesh currently uses lightweight bootstrap governance.

- `@MSKazemi` is the initial bootstrap maintainer.
- Useful contribution is broader than code.
- The intended path is **Participant -> Contributor -> Reviewer -> Maintainer / Community Steward**.
- Leadership should become more distributed as sustained contributors emerge.
- Major changes should be public, document alternatives, and include **Community Impact**.
- Important disagreement can be resolved by competing experiments when possible.

Read [`GOVERNANCE.md`](GOVERNANCE.md), [`MAINTAINERS.md`](MAINTAINERS.md), and [`docs/community/COMMUNITY_GROWTH_STRATEGY.md`](docs/community/COMMUNITY_GROWTH_STRATEGY.md).

## Repository guide

### Start here

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — make a successful contribution.
- [`COMMUNITY.md`](COMMUNITY.md) — participation, community values, contributor ladder.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — ACE self-growing community algorithm and safeguards.
- [`docs/community/ACE_BOOTSTRAP_EXPERIMENT.md`](docs/community/ACE_BOOTSTRAP_EXPERIMENT.md) — Bootstrap Cohort protocol, evidence rules, and expansion gate.
- [`SUPPORT.md`](SUPPORT.md) — how to ask for help.
- [`GOVERNANCE.md`](GOVERNANCE.md) — roles and decisions.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community behavior.
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting.

### Understand the project

- [`EVOLUTION.md`](EVOLUTION.md) — what we build next and how the project should evolve.
- [`IDKIPS.md`](IDKIPS.md) — improvement-proposal process for major competing ideas.
- [`docs/foundations/`](docs/foundations/README.md) — vision, goals, and field-defining questions.
- [`GOALS.md`](docs/foundations/GOALS.md) — goal hierarchy and success criteria.
- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — framework/core/domain model.
- [`ROADMAP.md`](ROADMAP.md) — staged research and implementation path.
- [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) — open questions.
- [`docs/research/TOP_20_QUESTIONS.md`](docs/research/TOP_20_QUESTIONS.md) — current priorities.

### Go deeper

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system model.
- [`docs/architecture/SCALABILITY_AND_AGILITY.md`](docs/architecture/SCALABILITY_AND_AGILITY.md) — scaling hypothesis.
- [`docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`](docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md) — typed temporal hypergraph for goals, WorkUnits, evidence, provenance, documents, and executable projections.
- [`docs/architecture/SELF_EVOLVING_REPOSITORY.md`](docs/architecture/SELF_EVOLVING_REPOSITORY.md) — guarded repository self-evolution, graph rewrites, control loops, invariants, and autonomy ladder.
- [`docs/community/COMMUNITY_GROWTH_DYNAMICS.md`](docs/community/COMMUNITY_GROWTH_DYNAMICS.md) — branching, network, queueing, control, and information-theoretic models for contributor growth.
- [`schemas/idkgraph.schema.json`](schemas/idkgraph.schema.json) and [`examples/idkgraph.example.yaml`](examples/idkgraph.example.yaml) — initial machine-readable graph schema and example.
- [`MATHEMATICAL_FOUNDATIONS.md`](MATHEMATICAL_FOUNDATIONS.md) — algorithms and formulations.
- [`SCIENTIFIC_FOUNDATIONS.md`](SCIENTIFIC_FOUNDATIONS.md) — scientific inspirations mapped to experiments.
- [`BLOCKCHAIN_STRATEGY.md`](BLOCKCHAIN_STRATEGY.md) — staged trust/provenance strategy.
- [`docs/decisions/`](docs/decisions/) — architecture/major decision records.
- [`docs/findings/`](docs/findings/) — research findings.
- [`docs/conversations/`](docs/conversations/README.md) — structured project conversation records.

## Public project record

Project reasoning is part of the open-source artifact.

Useful IDKMesh conversations should be distilled into the repository as decisions, findings, research questions, issues, architecture, roadmap changes, community/process changes, or structured conversation records.

The goal is **not** to dump chats. The goal is to make the evolution of the project understandable to someone who was not present.

See [`PROJECT_RULES.md`](PROJECT_RULES.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

## The invitation

IDKMesh starts from a simple admission: **we do not yet know the best way to build a system like this.**

If you can improve the question, challenge an assumption, reproduce an experiment, write a test, explain the project more clearly, help a newcomer, design a protocol, find a security problem, or build a small verified component, you can contribute.

> **From uncertainty to collective intelligence.**
