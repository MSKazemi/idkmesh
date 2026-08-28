# IDKMesh Community

> **Community first. Technology serves the community, not the other way around.**

IDKMesh is an open research and engineering community. The project may eventually coordinate very large numbers of humans, AI agents, and computers, but that scale is impossible without a community that is easy to enter, easy to understand, fair to participate in, and capable of growing new leaders.

## The community-first rule

Every meaningful project change should be considered from two perspectives:

1. **Does this improve the technical or research system?**
2. **Does this make the project easier for people to discover, understand, join, contribute to, review, maintain, or trust?**

A technically impressive change that makes the project inaccessible, opaque, or dependent on a small inner circle has a real cost and should state that cost explicitly.

For substantial proposals and pull requests, include a short **Community Impact** section covering effects on onboarding, contributor experience, documentation, accessibility, governance, or maintainability.

## What kind of community are we building?

IDKMesh should be:

- **Open by default** — discussions, decisions, experiments, and roadmaps should be public whenever possible.
- **Beginner-legible** — a new visitor should be able to understand the project without reading the entire research archive.
- **Contributor-friendly** — useful work must exist for coders, researchers, reviewers, writers, designers, security practitioners, community builders, domain experts, and compute contributors.
- **Evidence-driven** — status or popularity does not make an argument correct.
- **Respectful of uncertainty** — saying “I do not know” is valid; unresolved questions should become explicit research objects.
- **Leadership-generating** — long-term contributors should have a visible path toward review and maintainer responsibility.
- **Agent-transparent** — AI-assisted work is welcome, but its provenance and verification should be visible when material.
- **Asynchronous-first** — participation should not require living in a particular time zone or attending private meetings.
- **Portable** — GitHub is the current public front door, but community knowledge and project protocols should remain exportable.

## Your first 15 minutes

You do not need to understand the entire IDKMesh architecture before contributing.

1. Read the first section of [`README.md`](README.md).
2. Read [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Pick one contribution path below.
4. Open a small issue or pull request rather than waiting for perfect understanding.
5. State what you understand, what you are unsure about, and what evidence would change your view.

## Contribution paths

### I want to code

Implement a small bounded component, improve tests, build a simulator, add validation, improve developer tooling, or prototype an experiment. Prefer small changes with clear acceptance criteria.

### I want to research

Add literature, reproduce a result, challenge an assumption, design a falsifiable experiment, improve metrics, or document a negative result.

### I want to review

Review pull requests, reproduce experiments, inspect assumptions, improve tests, threat-model proposals, or check whether documentation is understandable to a newcomer.

### I want to improve the community

Improve onboarding, documentation, issue templates, contributor journeys, accessibility, translations, community metrics, events, communications, or governance.

### I am a domain expert

Help translate real-world problems into goals, constraints, Work Units, acceptance tests, threat models, or evaluation criteria.

### I want to contribute compute

The volunteer-compute protocol is not ready yet. Contributions to sandboxing, capability discovery, scheduling, verification, privacy, and threat modeling are useful now.

## Contributor ladder

Leadership should be earned through demonstrated, constructive participation rather than granted permanently at project creation.

### Participant

Anyone reading, discussing, testing, or using IDKMesh.

### Contributor

Someone who makes useful public contributions: code, reviews, documentation, experiments, issue triage, design, community work, research, or other project artifacts.

### Reviewer

A trusted contributor who has demonstrated sound judgment in a particular area and helps evaluate changes there.

### Maintainer

A contributor with sustained responsibility for project quality, community health, integration, and decision-making. Maintainers are expected to develop other contributors rather than becoming bottlenecks.

### Community Steward

A contributor trusted to focus on onboarding, moderation, contributor experience, community metrics, accessibility, and healthy participation. This path is equal in legitimacy to a code-maintainer path.

As IDKMesh grows, these roles can become scoped to subprojects or cells.

## How decisions should work

- Small, reversible changes: normal pull-request review.
- Significant technical or community changes: public issue/RFC, alternatives, evidence, and community impact.
- High-risk or hard-to-reverse changes: explicit decision record and broader review.
- Experiments: disagreement can often be resolved by running competing approaches under agreed metrics.

Consensus is useful but not mandatory. When consensus cannot be reached, maintainers should record the decision, rationale, dissenting arguments, and what future evidence could reopen it.

## Community metrics

We should measure community health without turning people into a leaderboard. Useful aggregate signals include:

- time to first response for newcomer issues and pull requests;
- percentage of first-time contributors receiving meaningful review;
- first contribution -> second contribution conversion;
- number of active reviewers and maintainers;
- contributor concentration / bus factor;
- review turnaround time;
- number of non-code contributions accepted;
- documentation/onboarding failure reports;
- contributor retention over time;
- unresolved conduct or governance problems.

Metrics are diagnostic tools, not targets to game.

## Community anti-patterns

IDKMesh should actively avoid:

- requiring newcomers to read dozens of documents before they can help;
- architecture discussions that occur only in private channels;
- equating commit count with contribution value;
- allowing AI-generated volume to overwhelm human review capacity;
- making maintainership an invisible or personality-based privilege;
- rewarding engagement or popularity instead of durable usefulness;
- accepting huge unreviewable pull requests when work can be decomposed;
- treating documentation, testing, review, moderation, or community work as second-class contributions;
- prematurely creating complex committees that do not reflect the actual community.

## Communication

The repository is currently the canonical asynchronous public record.

Use:

- **Issues** for questions with an actionable project outcome, proposals, bugs, experiments, and research topics.
- **Pull requests** for concrete changes.
- **Decision records** for durable major decisions.
- **Conversation summaries** for relevant project discussions that need to remain discoverable.

GitHub Discussions should become the preferred place for broad community Q&A and open-ended discussion if/when it is enabled.

## A community is part of the product

IDKMesh cannot achieve its technical vision first and “add community later.” The contributor experience, governance, documentation, communication structure, recognition system, and path to leadership are themselves core system design problems.
