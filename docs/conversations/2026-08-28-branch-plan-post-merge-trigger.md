# Conversation Record — Close the Branch Planner Feedback Loop

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Context

The transactional Branch Steward / merge planner was rebuilt on current `main` and merged through PR #211 as commit `dd2e223fa43cf91c96ef58601c000e7fe3f82afd` after fresh exact-head Evolution, IDKGraph, randomness-lab, and Branch Convergence Audit evidence passed.

The planner's canonical transaction rule is:

```text
merge one accepted PR
 -> main changed
 -> discard old eligibility
 -> resnapshot
 -> rerun branch audit
 -> rebuild plan
 -> evaluate the next exact-head PR
```

## Gap discovered immediately after integration

The Branch Convergence Audit workflow could run manually, on a schedule, or when its own implementation/policy files changed in a pull request. It did not run automatically when `main` changed.

That meant the implementation did not yet guarantee its own stated transaction rule after every integration.

## Correction

Add a read-only workflow trigger for every push to `main`:

```yaml
push:
  branches:
    - main
```

The workflow remains non-authoritative. Its permissions stay:

```text
contents: read
pull-requests: read
```

It can observe branch/PR state, run deterministic tests, generate an advisory convergence plan, and upload evidence. It still cannot approve, merge, push, delete branches, or change repository settings.

## Resulting control loop

```text
main changes
 -> Branch Convergence Audit runs
 -> deterministic branch states
 -> deterministic Branch Steward plan
 -> artifact + step summary
 -> human/independent integration decision outside the planner
 -> if another PR merges, repeat from the new main state
```

This makes branch planning event-driven as well as scheduled, while preserving the invariant that the agent is a planner/steward rather than a self-authorizing merger.
