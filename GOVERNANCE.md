# IDKMesh Governance

IDKMesh is currently in a **bootstrap governance phase**. The community is small, so the project should keep governance explicit but lightweight. Governance should become more distributed as real contributors and subprojects emerge.

The purpose of governance is to make participation fair, understandable, and scalable — not to create bureaucracy.

## Principles

1. **Community first.** Technical decisions must consider contributor experience and long-term community health.
2. **Public by default.** Important project decisions should be discussable and discoverable in public repository artifacts.
3. **Evidence over authority.** Maintainers have integration responsibility, not automatic correctness.
4. **Leadership is earned and renewable.** Responsibility grows through sustained constructive contribution.
5. **Non-code leadership counts.** Research, review, security, documentation, design, moderation, and community work can lead to maintainer responsibility.
6. **Prefer reversible experiments.** When the project is uncertain, test alternatives instead of forcing premature consensus.
7. **Document dissent.** Major decisions should preserve important objections and the evidence that could reopen the decision.
8. **No permanent founder veto as a target state.** Early bootstrap authority exists to establish the project, but governance should reduce single-person dependency as trusted contributors emerge.

## Current roles

### Participant

Anyone who uses, reads, discusses, tests, or follows the project.

### Contributor

Anyone with an accepted useful contribution, including code, review, documentation, research, experiments, design, security, community work, triage, or other durable artifacts.

### Reviewer

A contributor trusted to review a defined area. Reviewers can recommend acceptance and help maintain quality, but merge authority may remain with maintainers.

### Maintainer

A contributor trusted with integration and project stewardship. Maintainers are responsible for:

- reviewing and merging changes;
- protecting project quality and security;
- keeping decisions and processes transparent;
- supporting contributors and developing new reviewers/maintainers;
- avoiding review bottlenecks;
- maintaining community health as well as code health.

### Community Steward

A trusted contributor focused on onboarding, conduct, documentation usability, accessibility, moderation, contributor growth, and community metrics. Community Stewards should have real influence on project decisions affecting participation.

## Bootstrap maintainer

During the bootstrap phase, the repository owner `@MSKazemi` is the initial maintainer.

This is an operational starting condition, not a claim that project leadership should remain centralized. The project should add trusted reviewers and maintainers as soon as sustained contributors emerge.

## Becoming a reviewer

A contributor may become a reviewer for a scoped area after demonstrating several of the following:

- repeated useful contributions in that area;
- reliable and constructive reviews;
- ability to distinguish evidence from speculation;
- understanding of security and maintenance consequences;
- respectful collaboration;
- support for newcomers;
- willingness to document decisions and limitations.

Existing maintainers should discuss and record reviewer appointments publicly.

## Becoming a maintainer

Maintainer status should reflect sustained responsibility, not a fixed number of commits.

Signals include:

- consistent high-quality contributions over time;
- dependable review and integration judgment;
- demonstrated care for community health;
- constructive handling of disagreement;
- ability to mentor contributors;
- understanding of project principles and major architectural constraints;
- willingness to do maintenance work, not only feature work.

A strong non-code contributor may become a maintainer or Community Steward.

As multiple maintainers emerge, new maintainer appointments should require support from existing maintainers plus evidence of community trust. The exact threshold should be revised once the project has enough maintainers for voting rules to be meaningful.

## Inactivity and stepping down

Maintainers who are inactive for a sustained period should be encouraged to move to emeritus status rather than remain required approvers. Returning contributors can regain active responsibilities through renewed participation.

No maintainer role should become a permanent blocking dependency.

## Decision classes

### Routine / reversible

Examples: small documentation updates, narrow bug fixes, tests, refactors with no interface change.

Process: normal pull-request review.

### Significant

Examples: new subsystem, protocol changes, contributor-process changes, major dependencies, benchmark methodology changes.

Process: public issue or RFC before or alongside implementation. Include alternatives, risks, evaluation plan, and **Community Impact**.

### High-impact / hard to reverse

Examples: governance restructuring, security/trust model changes, stable protocol commitments, major data model changes, economic/incentive mechanisms.

Process: RFC + explicit decision record + broader review + evidence/experiment where feasible.

## Resolving disagreements

Preferred order:

1. Clarify the actual disagreement and assumptions.
2. Identify evidence already available.
3. Determine whether both approaches can be tested.
4. Run a bounded experiment when practical.
5. Seek rough consensus.
6. If a decision is required, maintainers decide within their scope and document:
   - rationale;
   - alternatives;
   - important dissent;
   - risks;
   - evidence that could reopen the decision.

Personal authority should be the last mechanism, not the first.

## Subprojects and future federation

IDKMesh may eventually contain many subprojects or autonomous cells. We should not invent that bureaucracy before it is needed.

A subproject governance model becomes appropriate when an area has:

- a stable scope;
- multiple sustained contributors;
- distinct review expertise;
- enough activity that centralized review is a bottleneck.

At that point, scoped ownership, reviewers, maintainers, decision records, and interfaces should be delegated while shared project principles remain common.

## Community impact requirement

Substantial RFCs and pull requests should answer:

- Does this make onboarding easier or harder?
- Does it increase or reduce contributor prerequisites?
- Does it create a new maintainer burden or bottleneck?
- Can non-expert contributors still understand where to participate?
- Does it move important work into private or inaccessible systems?
- Are documentation and examples updated?

Community impact is part of engineering impact.

## Governance changes

This document is expected to evolve. Governance changes should themselves follow the significant/high-impact decision process and should reflect how the community actually works rather than copying a complex model prematurely.
