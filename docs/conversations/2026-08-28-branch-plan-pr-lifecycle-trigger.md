# Conversation Record — PR-Lifecycle Resnapshot for Branch Steward

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Context

The executable Branch Steward was merged through #211, and #215 added automatic resnapshotting after every push to `main`.

That feedback loop worked immediately:

1. run #11 (`33204420843`) observed two active-review candidates at `main@528690273...`;
2. PR #203 merged seconds later;
3. the resulting `main@bc5b1554...` push automatically launched run #12 (`33204576976`);
4. run #12 reduced the active-review lane from two candidates to one and moved the integrated branch into retirement state.

This is direct evidence that eligibility must be treated as a state snapshot, not a durable permission.

## Remaining freshness gap

Not every PR lifecycle change modifies `main`.

Examples:

- a ready PR is converted to draft;
- a PR closes unmerged;
- a closed PR reopens;
- a PR head moves;
- a new PR opens.

All of these can change branch classification and the Branch Steward plan while the `main` SHA remains unchanged.

A schedule-only fallback is therefore insufficient for a responsive branch-management agent.

## Change

Add a `pull_request_target` observer for bounded lifecycle events:

```text
opened
reopened
closed
synchronize
ready_for_review
converted_to_draft
```

This event is used only for **canonical-state observation**. It explicitly checks out the trusted PR base SHA, never the contributor head, and retains only:

```text
contents: read
pull-requests: read
```

The ordinary path-filtered `pull_request` trigger remains separate so proposed changes to the auditor/planner code itself are tested using the proposed PR code.

## Concurrency rule

Canonical-state observations from:

- `main` pushes;
- PR lifecycle events;
- schedule;
- manual dispatch

share one concurrency group with `cancel-in-progress: true`.

Therefore a newer repository/PR-state event supersedes an older scan instead of allowing multiple stale canonical plans to race.

PR-code tests keep their own per-PR concurrency group.

## Resulting observation loop

```text
main change OR relevant PR-state change
 -> trusted read-only observer
 -> deterministic branch audit
 -> deterministic Branch Steward plan
 -> artifact + summary
 -> external integration decision
```

The planner still has no approval, merge, push, branch-deletion, issue-write, label-write, or settings authority.

## Security boundary

`pull_request_target` is potentially dangerous if contributor-head code is executed. This workflow therefore pins checkout to `github.event.pull_request.base.sha` for that event. No repository secrets are introduced, checkout credentials remain unpersisted, and the token remains read-only.

The goal is faster observation, not stronger authority.
