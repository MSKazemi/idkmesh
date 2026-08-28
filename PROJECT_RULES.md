# IDKMesh Project Rules

## Canonical public repository

The canonical public repository for this project is:

`https://github.com/MSKazemi/idkmesh`

## Mandatory chat-to-repository rule

For every ChatGPT conversation in the IDKMesh project, the public GitHub repository is the durable project record.

**Default rule: every substantive user message and every substantive assistant output related to IDKMesh must be preserved in the repository in the same turn whenever repository access is available.**

This includes:

- user questions, ideas, requirements, and corrections;
- assistant answers and recommendations;
- findings and research notes;
- architectural ideas;
- mathematical formulations;
- decisions and rejected alternatives;
- roadmaps and implementation plans;
- important questions and hypotheses;
- governance and community-design proposals;
- benchmarks and experiment results;
- code and documentation produced for the project;
- links and reference maps used to support the project;
- follow-up rules such as this repository-preservation requirement.

Conversation records should normally be stored under `docs/conversations/`, while durable findings, decisions, specifications, and implementation artifacts should also be promoted into their appropriate canonical files/directories.

The goal is that a contributor should be able to understand the evolution of IDKMesh from the public repository without depending on access to the original ChatGPT conversation.

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

1. **Questions / ideas from the project owner**
2. **Assistant output / proposed interpretation**
3. **Research findings**
4. **Decisions**
5. **Open questions**
6. **Action items / implementation artifacts**

Preserve visible chat content verbatim when practical and useful. When verbatim reproduction would create unnecessary duplication, expose restricted material, or violate redistribution constraints, preserve a faithful structured record instead.

## Promotion rule

Conversation archives are not a substitute for maintaining the project itself. If a chat changes the architecture, roadmap, governance, research direction, schemas, implementation, or decisions, update the relevant canonical project files in addition to archiving the conversation.

## Decision discipline

Major decisions should also be added to `DECISIONS.md`, including:

- date;
- decision;
- rationale;
- alternatives considered;
- consequences or unresolved risks.

## Research discipline

Claims should distinguish:

- established fact;
- external evidence;
- working hypothesis;
- speculative inspiration;
- implementation decision.

IDKMesh should not convert attractive analogies from physics, economics, biology, or mathematics into engineering claims without testing them.
