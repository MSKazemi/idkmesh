# Conversation Record — Framework and Multidisciplinary Collaboration

**Date:** 2026-08-28

## Questions from the project owner

- Has the GitHub repository been updated with the preceding chat and findings?
- How can IDKMesh be designed so people from different perspectives and backgrounds can collaborate?
- Is IDKMesh itself one project/application, or is it a project framework on top of which other distributed projects can be built?
- How should the project be understood in general?

## Clarification

IDKMesh should be treated primarily as a **general collaboration framework/platform and research program**, rather than only one fixed application.

Its first reference domain is distributed software engineering, because software provides strong automatic verification mechanisms and a practical environment in which to test the core hypotheses.

The proposed model has three layers:

1. **IDKMesh Core** — reusable primitives for evolving goals, Work Units, scheduling, execution, verification, provenance, reputation, governance, and metrics.
2. **Domain Packs / Project Protocols** — domain-specific Work Unit types, validators, roles, policies, evidence requirements, and risk models.
3. **Projects** — independent real-world projects that use the IDKMesh framework.

The initial project should be **IDKMesh improving IDKMesh**, because self-hosting creates a direct experimental feedback loop.

## Multidisciplinary collaboration principle

People should not need to share the exact same mental model of the final goal in order to contribute.

Instead, IDKMesh should provide shared boundary artifacts such as:

- Goal Graph nodes;
- Work Units;
- Result Manifests;
- RFCs;
- benchmarks;
- experiments;
- threat models;
- APIs/contracts;
- provenance records;
- architecture decisions.

Contributors can work through these interfaces while maintaining different perspectives.

## Relevant contributor perspectives

Potential contribution tracks include:

- software engineering;
- distributed systems;
- AI / machine learning;
- cybersecurity;
- mathematics and operations research;
- economics / mechanism design;
- governance / law / policy;
- open-source community development;
- UX / product design;
- scientific methodology;
- domain expertise;
- volunteer compute contribution.

These are not merely advisory roles. The project architecture should expose concrete tasks and artifacts for each of them.

## Working project definition

> **IDKMesh is an open framework, research program, and community for turning heterogeneous distributed participation — humans, AI agents, and computers — into verified useful work on complex and evolving goals.**

Software engineering is the first reference implementation, not necessarily the final boundary of the framework.

## Important constraint

The framework should not be generalized prematurely. Begin with a concrete software-engineering implementation, test the abstractions experimentally, and generalize only those primitives that prove reusable.

## Repository changes from this discussion

Added:

- `docs/WHAT_IS_IDKMESH.md`
- `docs/CONTRIBUTOR_PERSPECTIVES.md`
- this conversation record

The project should continue to preserve significant ChatGPT discussions and findings in the canonical public repository.