# Conversation record — Community-first repository rule

**Date:** 2026-08-28

## Project-owner direction

The project owner clarified that the canonical public repository is:

`https://github.com/MSKazemi/idkmesh`

and established/reinforced two important project rules:

1. **All useful conversations inside the IDKMesh project should be represented in the GitHub repository in a structured form.**
2. **Building a large community is the most important repository-level priority.** Everything added to the project should be considered from the perspective of making the project easy to discover, follow, understand, join, and contribute to, using strong open-source practices.

The repository should not become a dump of raw conversations. Conversation output should be organized into the correct durable artifacts: findings, decisions, architecture, research questions, issues, contribution guidance, or concise conversation records.

## Interpretation

Community-first does not mean technical quality is secondary. It means the community is part of the technical system required to achieve IDKMesh's scale.

A change should therefore be judged along at least two axes:

- technical/research value;
- community/contributor value and cost.

For significant changes, contributor understandability, onboarding, review capacity, maintainability, governance, and documentation are engineering concerns.

## Repository gaps identified

At the time of this conversation, the README linked to `CONTRIBUTING.md` and `GOVERNANCE.md`, but those files were missing. Standard community-health documents and contribution templates were also incomplete.

This created immediate newcomer friction and contradicted the community-first goal.

## Actions initiated

A `community-first-foundation` branch was created to add:

- `COMMUNITY.md`;
- `CONTRIBUTING.md`;
- `GOVERNANCE.md`;
- `CODE_OF_CONDUCT.md`;
- `SUPPORT.md`;
- `SECURITY.md`;
- `MAINTAINERS.md`;
- GitHub issue templates;
- a pull-request template;
- `docs/community/COMMUNITY_GROWTH_STRATEGY.md`;
- `docs/decisions/ADR-0003-community-first.md`;
- updates to `PROJECT_RULES.md` and `README.md`.

## Governance direction

The initial governance should be explicit but lightweight:

- one bootstrap maintainer initially;
- visible contributor -> reviewer -> maintainer / Community Steward paths;
- public decisions by default;
- larger proposals include Community Impact;
- leadership should become distributed as contributors demonstrate sustained responsibility;
- do not prematurely create a complex committee structure before the real community requires it.

## Open-source practices emphasized

Useful current guidance was reviewed from GitHub and CNCF. Themes adopted include:

- community-health files and templates;
- explicit contribution guidance;
- clearly documented roles and responsibilities;
- attainable paths to leadership;
- governance that describes how the project actually works;
- support for non-code contribution;
- deliberate contributor growth and retention;
- public, asynchronous collaboration.

## Continuing rule for future project work

When a future ChatGPT conversation materially changes IDKMesh:

1. identify durable project knowledge;
2. update the canonical repository;
3. put information in the right layer (decision, finding, issue, research question, architecture, roadmap, conversation record, etc.);
4. optimize documentation for progressive disclosure rather than requiring newcomers to read everything;
5. evaluate substantial changes for Community Impact;
6. never publish secrets, sensitive personal information, private hidden reasoning, or confidential third-party material.
