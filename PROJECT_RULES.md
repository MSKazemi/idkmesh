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

## Rule 2 — Mandatory chat-to-repository preservation

For every substantive ChatGPT conversation in the IDKMesh project, the public GitHub repository is the durable project record whenever repository access is available.

**Default rule: every substantive user message and every substantive assistant output related to IDKMesh must be preserved in the repository in the same turn when practical and safe.**

This includes:

- user questions, ideas, requirements, corrections, and project rules;
- assistant answers, recommendations, and proposed interpretations;
- findings and research notes;
- architectural ideas;
- mathematical formulations;
- decisions and rejected alternatives;
- roadmaps and implementation plans;
- important questions and hypotheses;
- governance and community-design proposals;
- benchmarks and experiment results;
- code and documentation produced for the project;
- links/reference maps used to support project decisions;
- follow-up constraints and repository rules.

Conversation records should normally be stored under `docs/conversations/`, while durable findings, decisions, specifications, architecture, roadmap changes, community/process rules, and implementation artifacts should also be promoted into their appropriate canonical files/directories.

The goal is that a contributor should be able to understand the evolution of IDKMesh from the public repository without depending on access to the original ChatGPT conversation.

## Rule 3 — Zero project spend for compute

**IDKMesh currently cannot pay for computing resources, hosted model usage, GPU rental, cloud instances, or other execution capacity. Project-funded compute spend is therefore a hard constraint of `$0`.**

The repository-level policy is stored in [`config/compute-policy.json`](config/compute-policy.json). Work Units may tighten that policy but must not relax it. In particular:

- the automatic compute path must never silently fall back to a paid provider;
- when no eligible zero-project-cost resource exists, the correct behavior is to queue, replan, reduce the task, ask for donated capacity, or fail closed;
- local hardware, volunteer hardware, public-project CI, grants, and genuine free tiers may be used only within their applicable terms and limits;
- donated compute is not economically “free”: electricity, hardware wear, bandwidth, thermal load, and attention are borne by the donor, so donation must be opt-in, transparent, resource-capped, and easy to pause or stop;
- no contributor should be pressured to donate compute in order to participate or gain standing in the community;
- paid-provider adapters may be studied for interoperability, but they are disabled by project policy and are not part of the active execution path while this rule is in force;
- free quotas must be treated as opportunistic capacity, not as architectural guarantees.

The executable prototype enforcing this rule is [`experiments/free_compute_router.py`](experiments/free_compute_router.py). Its safety invariant is:

> **No eligible zero-project-cost offer → no execution selection. Never convert resource scarcity into an unapproved bill.**

Any future proposal to permit project spending must be an explicit governance/maintainer decision that changes this rule and the repository policy; a Work Unit, agent, scheduler, issue, or contributor cannot enable spending by itself.

## Structured preservation, not transcript dumping

Preservation does not mean turning the repository into an undifferentiated transcript archive.

Prefer promoting useful output into durable project artifacts:

- **decision** -> `DECISIONS.md` and/or `docs/decisions/ADR-*.md`;
- **research question** -> `RESEARCH_QUESTIONS.md` or a research issue;
- **finding** -> `docs/findings/`;
- **architecture** -> architecture docs / ADR;
- **plan** -> `ROADMAP.md` or issue/milestone;
- **community/process change** -> community/governance docs;
- **important chat context** -> `docs/conversations/` structured record.

Preserve visible chat content verbatim when practical and useful. When verbatim reproduction would create unnecessary duplication, expose restricted material, or violate redistribution constraints, preserve a faithful structured record instead.

Conversation archives are not a substitute for maintaining the project itself. If a chat changes architecture, roadmap, governance, research direction, schemas, implementation, or decisions, update those canonical artifacts in addition to archiving the conversation.

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

When a conversation contains both useful project information and material that should not be public, preserve the public-safe portion and a faithful project summary of the remainder rather than exposing restricted material.

## Conversation preservation format

Conversation records should distinguish where possible between:

1. **Questions / ideas / requirements from the project owner**
2. **Assistant output / proposed interpretation**
3. **Research findings**
4. **Decisions**
5. **Open questions**
6. **Action items / implementation artifacts**
7. **Community impact / contributor implications**

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
