# IDKMesh

> **I don't know. You don't know. Together, the mesh can discover, build, and know.**

**IDKMesh** is an open-source exploration of a decentralized collective-intelligence and distributed-computing platform where humans, AI agents, and heterogeneous compute nodes can collaborate on useful software and research — from one laptop to potentially millions of participating machines.

The name intentionally preserves uncertainty:

- **IDK** — *I Don't Know*: the final system is not assumed to be fully defined in advance.
- **Mesh** — a decentralized network of people, agents, knowledge, tasks, and compute.

The project starts from a question rather than a fixed product specification:

> Can a large community of humans and AI agents, using distributed commodity compute, collectively discover goals, design systems, write and verify code, and produce enterprise-grade open-source software at a scale that a single developer or model cannot?

## What is IDKMesh?

IDKMesh should be understood primarily as a **general framework/platform, research program, and community for distributed collaboration**, not as one fixed application.

The intended structure is:

```text
IDKMesh Core
   |
   +-- domain/project protocols
          |
          +-- software-engineering projects
          +-- scientific/research projects
          +-- other future collaborative domains
```

The core provides reusable primitives for evolving goals, bounded Work Units, scheduling, isolated execution, verification, provenance, reputation, governance, and metrics. Domain-specific layers add their own validators, policies, roles, and evidence rules. Independent projects can then run on top of the framework.

The first reference implementation is intentionally narrower: **distributed software engineering**, with IDKMesh eventually using IDKMesh to improve itself.

See [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) and [`GOALS.md`](GOALS.md).

## Status

**Exploration / research / architecture phase.**

IDKMesh is deliberately not pretending that its final architecture is known. The repository is both a software project and a public research notebook for discovering what the project should become.

## Core ambitions

1. Scale participation from one human + one laptop to very large communities and compute pools.
2. Coordinate many humans and many AI agents even when the target is initially ambiguous.
3. Preserve software quality as the number of contributors and agents grows.
4. Make contribution accessible to people with different skills, hardware, languages, disciplines, and levels of experience.
5. Use mathematical, economic, distributed-systems, and statistical mechanisms to allocate work and reach decisions.
6. Keep the project open, auditable, reproducible, and useful to humanity.
7. Build mechanisms for verification, trust, reputation, safety, governance, and conflict resolution rather than relying on a single central authority.
8. Allow other projects to reuse the coordination framework without becoming coupled to one AI model, Git forge, or application domain.

## Multidisciplinary collaboration

IDKMesh is deliberately open to contribution from software engineering, AI/ML, distributed systems, security, mathematics, operations research, economics, governance, open-source community building, UX/design, scientific methodology, domain experts, and compute contributors.

Different perspectives do **not** need to reach total conceptual agreement before useful work begins. They should collaborate through shared boundary artifacts such as Work Units, Goal Graph nodes, RFCs, APIs/contracts, benchmarks, threat models, experiment manifests, evidence, and architecture decisions.

See [`docs/CONTRIBUTOR_PERSPECTIVES.md`](docs/CONTRIBUTOR_PERSPECTIVES.md).

## Repository map

- [`VISION.md`](VISION.md) — what the project is trying to discover and why.
- [`GOALS.md`](GOALS.md) — concrete hierarchy of goals and success criteria.
- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — framework/core/domain-project model.
- [`docs/CONTRIBUTOR_PERSPECTIVES.md`](docs/CONTRIBUTOR_PERSPECTIVES.md) — multidisciplinary contribution model.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — initial system model and architectural directions.
- [`docs/architecture/SCALABILITY_AND_AGILITY.md`](docs/architecture/SCALABILITY_AND_AGILITY.md) — the proposed scale-from-1-to-millions fractal-cell architecture and agility rules.
- [`MATHEMATICAL_FOUNDATIONS.md`](MATHEMATICAL_FOUNDATIONS.md) — candidate mathematical formulations and algorithms.
- [`SCIENTIFIC_FOUNDATIONS.md`](SCIENTIFIC_FOUNDATIONS.md) — physics, complex-systems, thermodynamic, and quantum-inspired ideas mapped to testable IDKMesh experiments.
- [`BLOCKCHAIN_STRATEGY.md`](BLOCKCHAIN_STRATEGY.md) — where blockchain/shared ledgers can help, where they cannot, and the staged trust/provenance strategy.
- [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) — open technical, scientific, social, and governance questions.
- [`docs/research/TOP_20_QUESTIONS.md`](docs/research/TOP_20_QUESTIONS.md) — the twenty highest-priority questions currently shaping the project.
- [`DECISIONS.md`](DECISIONS.md) — durable decision log.
- [`docs/decisions/`](docs/decisions/) — architecture decision records, including the proposed Fractal Autonomous Cells design.
- [`ROADMAP.md`](ROADMAP.md) — staged research and implementation roadmap from the experimental kernel through Internet-scale research.
- [`GOVERNANCE.md`](GOVERNANCE.md) — initial governance model.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to participate.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — repository and project-record rules.
- [`docs/conversations/`](docs/conversations/) — project conversation archive and summaries.
- [`docs/findings/`](docs/findings/) — research findings and landscape notes.

## First principles

IDKMesh should be designed around several separations:

**Proposal is not proof.** AI-generated code, human-generated code, and design proposals should all be treated as hypotheses until tested or verified.

**Popularity is not correctness.** Voting and reputation can help coordinate work but cannot replace tests, formal constraints, security review, or empirical evidence.

**Decentralization is not absence of structure.** A large mesh requires protocols, interfaces, incentives, quality gates, and explicit governance.

**More agents do not automatically mean better results.** The system must measure marginal value, redundancy, diversity, correlated failure, and verification cost.

**Uncertainty is a first-class state.** Requirements, beliefs, confidence, conflicting hypotheses, and unresolved questions should be represented explicitly rather than hidden.

**Scientific analogies are hypotheses, not evidence.** Ideas from physics, economics, biology, or quantum information must be mapped to variables, baselines, metrics, and falsifiable experiments before becoming architecture.

**Cryptographic provenance comes before blockchain.** Use hashes, signatures, attestations, and transparency logs first; add blockchain only when a real multi-party trust or settlement problem justifies it.

## Candidate system layers

A long-term IDKMesh system may include:

1. **Identity & capability layer** — participants, agents, hardware, skills, permissions, reputation.
2. **Knowledge layer** — goals, assumptions, evidence, decisions, artifacts, provenance.
3. **Task graph** — decomposition of uncertain goals into proposals, experiments, implementations, tests, reviews, and integration tasks.
4. **Matching & scheduling** — assignment of tasks to humans, agents, and compute based on capability, cost, trust, diversity, and expected information gain.
5. **Execution mesh** — local laptops, workstations, clusters, cloud, edge, and volunteer compute.
6. **Verification layer** — testing, review, adversarial evaluation, reproducibility, formal checks, consensus where appropriate.
7. **Governance & incentive layer** — reputation, contribution accounting, dispute resolution, policy evolution, anti-Sybil mechanisms.
8. **Integration layer** — version control, continuous integration, release engineering, observability, rollback, security and supply-chain controls.

## Current scalability hypothesis

IDKMesh should not become one giant cluster, scheduler, database, or multi-agent conversation. The current default hypothesis is a **Fractal Autonomous Cells** architecture:

`node -> cell -> fabric/region -> global federation`

Most scheduling, execution, verification, state, and observability stay local to a cell. Higher layers exchange only summaries, overflow work, discovery information, attestations, and protocol metadata. This hypothesis is explicitly falsifiable and must be tested against centralized and sharded alternatives before being accepted permanently.

See [`docs/architecture/SCALABILITY_AND_AGILITY.md`](docs/architecture/SCALABILITY_AND_AGILITY.md) and [`docs/decisions/ADR-0002-fractal-autonomous-cells.md`](docs/decisions/ADR-0002-fractal-autonomous-cells.md).

## Recommended starting point

Read [`GOALS.md`](GOALS.md), [`ROADMAP.md`](ROADMAP.md), [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md), [`docs/research/TOP_20_QUESTIONS.md`](docs/research/TOP_20_QUESTIONS.md), and [`docs/architecture/SCALABILITY_AND_AGILITY.md`](docs/architecture/SCALABILITY_AND_AGILITY.md), then begin with the **experimental kernel**, not the million-node system.

The first engineering artifacts are machine-readable Work Unit/Task Contract, Result/Artifact Manifest, and Goal Graph schemas plus a simulator and common metrics harness.

The first headline scientific experiments should include:

1. comparing a single-agent coding baseline with same-agent replication and a structured, diverse, independently verified agent swarm under comparable resource budgets; and
2. comparing one global scheduler, sharded scheduling, and autonomous-cell federation from 10 to 100,000 simulated workers while measuring per-task coordination cost.

## Why `IDKMesh`?

The project began with the phrase **"I don't know"** because its creator did not want to prematurely constrain the idea. The public name **IDKMesh** keeps that philosophy while making the distributed nature of the project discoverable and memorable.

Tagline:

> **From uncertainty to collective intelligence.**

## Public project record

IDKMesh treats its reasoning history as part of the open-source artifact. Project-related findings, decisions, research notes, and relevant conversation outputs should be committed to this repository so contributors can understand not only *what* was built, but *why*.

See [`PROJECT_RULES.md`](PROJECT_RULES.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

## Contributing

The project is intentionally early. That means architecture critiques, literature references, mathematical models, simulations, prototypes, benchmarks, governance proposals, documentation, UX work, domain expertise, compute contributions, and negative results are all valuable contributions.

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/CONTRIBUTOR_PERSPECTIVES.md`](docs/CONTRIBUTOR_PERSPECTIVES.md), [`ROADMAP.md`](ROADMAP.md), [`docs/research/TOP_20_QUESTIONS.md`](docs/research/TOP_20_QUESTIONS.md), and [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md).
