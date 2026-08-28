# Findings — Open-source community, collaboration, and platform strategy

Date: 2026-08-28

## Core community principle

IDKMesh should be designed as both a technical system and a social system. Generating more code is easy compared with maintaining shared intent, review capacity, architectural coherence, trust, and long-term contributor motivation.

## When the goal is not fully clear

A community does not need a perfectly specified final product to collaborate productively. It does need a shared process for handling uncertainty.

Recommended structure:

1. **North Star** — a stable explanation of the human problem and long-term ambition.
2. **Goal Graph** — explicit goals, questions, assumptions, hypotheses, evidence, and conflicts.
3. **RFCs** — concrete proposals with alternatives and consequences.
4. **Experiments** — competing approaches can be tested in parallel.
5. **Decision log** — record why temporary commitments were made.
6. **Reversibility** — preserve the ability to revise decisions when evidence changes.

The project should not force premature consensus where empirical comparison is possible.

## Enterprise-quality open-source development

The contribution surface can be very open while the canonical product remains tightly verified. Recommended controls include:

- explicit subsystem ownership;
- protected default branch;
- mandatory CI and security checks;
- reproducible tests and environments;
- compatibility contracts;
- dependency and supply-chain policy;
- lightweight RFC requirement for cross-cutting architecture changes;
- independent review for high-risk modules;
- release engineering and rollback;
- post-merge monitoring;
- provenance of human and agent-generated artifacts.

This separates **freedom to propose** from **authority to integrate**.

## Contributor roles

The project should make contributions possible beyond feature coding. Useful roles include:

- implementer;
- issue decomposer;
- test author;
- benchmark author;
- reproducer;
- security reviewer;
- architecture reviewer;
- documentation writer;
- researcher;
- compute donor;
- integration maintainer;
- community/onboarding contributor.

Contribution reputation should recognize all of these forms of work.

## Community growth

The most compelling growth loop for IDKMesh is likely a visible, reproducible public experiment rather than generic promotion.

Candidate flagship experiment:

> **Many Small Coding Agents vs One Strong Model**

Publish transparent metrics such as accepted changes, hidden-test success, regressions, security findings, human reviewer minutes, compute consumed, latency, and cost per regression-free accepted change.

A contributor should be able to improve a scheduler, validator, prompt, model adapter, task decomposition method, or benchmark and immediately see whether the system improved.

## Onboarding funnel

Design a progression such as:

```text
observer
 -> star/follow
 -> reproduce experiment
 -> report result
 -> solve bounded task
 -> review another result
 -> own a small component
 -> become reviewer
 -> become maintainer
```

New contributors should encounter bounded, well-specified tasks with visible impact before needing deep understanding of the whole project.

## Social-media lessons

Useful mechanics:

- task recommendations based on capability/interests;
- follows/subscriptions for subprojects;
- notification streams;
- contribution profiles;
- visible recognition and badges for meaningful verified work;
- shareable benchmark results;
- easy discovery of active discussions;
- progressive permissions based on demonstrated contribution.

Avoid:

- optimizing for time-on-platform;
- follower count as technical authority;
- opaque popularity ranking;
- incentives for controversy;
- rewarding commit volume rather than durable useful work;
- gamification that encourages low-quality submissions.

## Platform strategy

### GitHub now

Use GitHub as the initial public front door because it provides a large developer audience and mature workflows for repositories, issues, pull requests, CI, code review, security tooling, and community discovery.

### Git as portable core

Do not make IDKMesh's worker protocol, task model, identity, reputation, or verification semantics depend on GitHub. Git should remain a portable versioned-artifact/provenance layer.

### Evaluate alternatives later

Potential future integrations include:

- GitLab for integrated/self-hosted workflows;
- Forgejo for community-controlled/self-hosted forges and future federation experiments;
- Radicle or other P2P Git collaboration for decentralized replication/provenance research;
- custom IDKMesh coordination services where existing forges do not model Work Units, Goal Graphs, reputation, or validation adequately.

The project should earn the complexity of decentralizing each component rather than decentralizing everything by default.

## Governance patterns worth studying

Large successful open-source systems suggest several recurring practices:

- divide ownership by subsystem rather than centralizing every decision;
- keep important decisions public and asynchronous where possible;
- use explicit proposal processes for cross-cutting changes;
- make maintainer/reviewer roles and responsibilities visible;
- allow authority to grow from demonstrated contribution;
- preserve strong quality gates even when contribution is open;
- document decisions and rejected alternatives;
- maintain codes of conduct and dispute-resolution processes;
- explicitly manage maintainer workload and succession.

## Success metrics

Do not optimize primarily for GitHub stars. Stars and attention are useful discovery signals, but healthier measures include:

- first-time contributor conversion;
- time to first response;
- time to first accepted contribution;
- reviewer/maintainer load;
- contributor retention;
- diversity of active contributors and models;
- reproducibility rate of experiments;
- accepted useful work;
- post-merge defect rate;
- documentation freshness;
- bus factor / ownership concentration;
- percentage of important decisions with recorded rationale.

The best dissemination strategy is to create results that other developers want to reproduce, criticize, benchmark, and improve.
