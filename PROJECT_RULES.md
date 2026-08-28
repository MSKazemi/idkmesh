# IDKMesh Project Rules

## Canonical public repository

The canonical public repository for this project is:

`https://github.com/MSKazemi/idkmesh`

## Rule 1 — Community first

**Building a large, healthy, open community is a core project objective and a design constraint for everything added to IDKMesh.**

Every substantial technical, research, governance, documentation, tooling, or roadmap change should consider whether it makes the project easier or harder for people to:

- discover;
- understand progressively;
- join without private context;
- find useful work;
- make a first contribution;
- receive review and feedback;
- reproduce evidence;
- become a reviewer or maintainer;
- maintain the project over time.

For non-trivial proposals and pull requests, include a **Community Impact** section when practical.

Community work — onboarding, documentation, review, moderation, accessibility, contributor growth, governance, and communication — is first-class project work, not an activity to postpone until after the technology is built.

See [`COMMUNITY.md`](COMMUNITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`GOVERNANCE.md`](GOVERNANCE.md), and [`docs/community/COMMUNITY_GROWTH_STRATEGY.md`](docs/community/COMMUNITY_GROWTH_STRATEGY.md).

## Rule 2 — Preserve useful project conversations in GitHub

For ChatGPT conversations related to IDKMesh, useful project outputs should be reflected in this repository. This includes, when relevant:

- findings and research notes;
- architectural ideas;
- mathematical formulations;
- decisions and rejected alternatives;
- roadmaps and implementation plans;
- important questions and hypotheses;
- governance and community-design proposals;
- benchmarks and experiment results;
- code and documentation produced for the project;
- concise conversation records sufficient to preserve project context.

The goal is to make the evolution of the project understandable to future contributors.

## Structured preservation, not transcript dumping

A conversation does not need to be copied word-for-word.

Prefer transforming useful output into durable project artifacts:

- **decision** -> `DECISIONS.md` and/or `docs/decisions/ADR-*.md`;
- **research question** -> `RESEARCH_QUESTIONS.md` or a research issue;
- **finding** -> `docs/findings/`;
- **architecture** -> architecture docs / ADR;
- **plan** -> `ROADMAP.md` or issue/milestone;
- **community/process change** -> community/governance docs;
- **important context** -> `docs/conversations/` summary.

Conversation records should help a new contributor understand why the project evolved, not force them to reconstruct the project from chat transcripts.

## Progressive disclosure rule

Repository organization should make the project understandable in layers:

1. **Visitor:** README — what, why, status, how to join.
2. **Contributor:** CONTRIBUTING, COMMUNITY, starter issues, runnable examples.
3. **Subsystem contributor:** architecture, APIs/protocols, tests, experiments, ADRs.
4. **Researcher/maintainer:** deep mathematical/scientific foundations, governance evolution, threat models, extensive research notes.

Do not require Level 4 understanding before someone can make a useful Level 2 contribution.

## What should not be committed

The public repository must not contain:

- passwords, access tokens, API keys, or other secrets;
- private credentials or authentication material;
- sensitive personal information;
- private internal model reasoning or hidden chain-of-thought;
- third-party confidential material;
- copyrighted content that cannot legally be redistributed.

When a conversation contains both useful project information and material that should not be public, preserve a safe project summary rather than the sensitive material.

## Conversation preservation format

Conversation records should distinguish where possible between:

1. **Questions / ideas from the project owner**
2. **Research findings**
3. **Decisions**
4. **Open questions**
5. **Action items / implementation artifacts**
6. **Community impact / contributor implications**

A faithful structured summary is preferred when exact reproduction would add noise or expose information that should not be public.

## Decision discipline

Major decisions should also be added to `DECISIONS.md` and/or an ADR, including:

- date;
- decision;
- rationale;
- alternatives considered;
- consequences or unresolved risks;
- community impact when relevant;
- evidence or conditions that could cause the decision to be revisited.

## Research discipline

Claims should distinguish:

- established fact;
- external evidence;
- working hypothesis;
- speculative inspiration;
- implementation decision.

IDKMesh should not convert attractive analogies from physics, economics, biology, mathematics, social systems, or distributed systems into engineering claims without testing them.

## Agent/AI contribution discipline

AI-assisted work is welcome, but generation volume must not overwhelm verification and maintenance capacity.

For materially AI-generated artifacts, preserve provenance when practical and independently verify important claims, code, tests, or security-sensitive changes.

Raw agent count, raw output volume, commit count, stars, or engagement are not substitutes for verified useful work.

## Open-source discipline

As the repository evolves:

- keep community-health files current;
- keep contribution paths clear;
- prefer public asynchronous decisions;
- make leadership paths visible and attainable;
- value non-code contributions;
- keep issues small and verifiable when possible;
- avoid undocumented private project context;
- grow reviewers/maintainers before contribution volume becomes a bottleneck;
- revise governance to reflect the community that actually exists rather than importing unnecessary bureaucracy.
