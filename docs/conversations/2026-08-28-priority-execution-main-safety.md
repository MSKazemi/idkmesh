# Project Conversation — Execute Current Priorities and Protect `main`

**Date:** 2026-08-28

## Project-owner direction

After reviewing the repository priority audit, the project owner instructed the assistant to proceed with the highest-priority work in the public repository.

## Repository state observed

The execution pass confirmed:

- `main` was publicly reported by GitHub as **unprotected**;
- issue #35 already tracks protection of the canonical integration boundary;
- PR #34 is the highest-value executable integration path for the canonical local node;
- PR #34 is under active concurrent modification: its head changed repeatedly while synchronization work was being prepared;
- the assistant therefore refused to force-update the branch or overwrite concurrent work;
- the ACE community workflow already has bounded write capability to issues/labels and a reproductive Growth Seed actuator.

## Actions taken

### 1. Attempted safe synchronization of PR #34

The assistant inspected the PR diff and found its node integration to be isolated to a new `node/` subtree, a node CI workflow, and the node execution-binding schema. A merge commit was prepared using current `main` plus those additions.

Before the branch ref could be advanced, PR #34 received new concurrent commits. GitHub correctly rejected the update as non-fast-forward. A second synchronization attempt observed another concurrent head change and was also not force-applied.

### Decision

Do **not** force-push over active concurrent work. Preserve contributor/agent work and continue with another P0 task that does not conflict.

### 2. Added a fail-closed ACE protection gate

On branch `safety/main-protection-guard`, the ACE workflow was changed to inspect GitHub's actual protection state for `main`.

While `main` is unprotected:

- ACE reports `CONSOLIDATE` mode;
- its public evidence ledger may continue updating;
- its automatic Growth Seed reproductive actuator is disabled;
- project instructions are explicitly treated as insufficient substitutes for repository policy enforcement.

This preserves observability while preventing the community-growth controller from autonomously reproducing work before the canonical integration boundary is protected.

### 3. Defined the protected integration contract

Added `docs/admin/MAIN_PROTECTION.md` with:

- minimum ruleset/branch-protection requirements;
- candidate required CI checks;
- bootstrap single-maintainer constraints;
- GitHub admin UI setup steps;
- verification steps after configuration;
- a staged authority ladder for future automation.

### 4. Updated governance

`GOVERNANCE.md` now states the integration invariant:

> No autonomous actor may propose, approve, and merge the same protected change by itself.

The governance document links to the operational protection policy and issue #35.

## Safety rationale

The project is beginning to use GitHub workflows and agents as control surfaces. Prompts and repository text are advisory policy; GitHub rulesets, independent CI, and review boundaries are enforcement mechanisms.

The project should therefore separate:

```text
proposal
 -> evidence / verification
 -> protected integration
 -> canonical state
```

This same separation is intended to become a core Verified Swarm Runner property.

## Next actions

1. Review and merge the `main` protection guard PR.
2. Repository admin enables the actual GitHub ruleset/branch protection described in `docs/admin/MAIN_PROTECTION.md`.
3. Verify GitHub reports `main` as protected.
4. Continue synchronization/integration of PR #34 without force-overwriting active concurrent work.
5. Complete controlled Docker acceptance #37 before merging the canonical node.
6. Continue independent verifier and local multi-worker orchestration work after the canonical node path is integrated.

## Community impact

This change intentionally reduces automation authority rather than increasing it. It makes the project's safety model visible to contributors and ensures community-growth automation cannot silently outrun repository integration controls.
