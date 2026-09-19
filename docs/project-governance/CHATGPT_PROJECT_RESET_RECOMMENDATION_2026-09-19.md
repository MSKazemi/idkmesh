# ChatGPT Project Reset Recommendation

Date: 2026-09-19

## Recommendation

Start a new, clean ChatGPT Project connected to the existing `MSKazemi/idkmesh` GitHub repository, but do **not** delete the current ChatGPT Project immediately.

The current project has accumulated useful history together with early-stage ideas, duplicated directions, outdated assumptions, and experimental discussion. That makes it increasingly difficult for future conversations and agents to distinguish the current product direction from discarded ideas.

The GitHub repository should remain the durable source of truth. The reset should apply to the ChatGPT Project context, not to the repository.

## Proposed migration

1. Freeze the current ChatGPT Project and treat it as an archive.
2. Create a new ChatGPT Project, for example `IDKmesh Core` or `IDKmesh 2026`.
3. Connect the same GitHub repository: `MSKazemi/idkmesh`.
4. Bring only a small curated set of durable context into the new project:
   - current mission and problem statement;
   - architecture and system boundaries;
   - current roadmap and priorities;
   - contribution and agent instructions;
   - active scheduled-agent/task design;
   - important research decisions and ADRs;
   - links to canonical repository documentation.
5. Do not copy old chats wholesale. If an old idea is still valuable, convert it into repository documentation, an issue, an ADR, or a roadmap item first.
6. Make the repository—not ChatGPT conversation history—the canonical memory for decisions and implementation.
7. Keep the old project for a transition period and delete it only after confirming that no unique useful information remains.

## Why this is preferable

A clean project reduces context pollution and conflicting instructions, while preserving the valuable history in the old project. It also makes new agents easier to onboard because they can begin from curated, version-controlled documentation rather than years of mixed conversation context.

## Suggested canonical files

A clean IDKmesh project should ideally have a compact project context centered on repository files such as:

- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/PROJECT_STATE.md`
- `docs/decisions/` (ADRs)
- `docs/automation/` (scheduled jobs / agents)
- `docs/research/` (validated research directions)

## Practical rule

**Keep code, decisions, requirements, and plans in GitHub. Keep ChatGPT Projects disposable.**

A ChatGPT Project should be a working environment around the repository, not the only place where project knowledge exists.
