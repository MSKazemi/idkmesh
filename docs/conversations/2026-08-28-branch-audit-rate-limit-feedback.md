# Conversation Record — Branch Steward rate-limit feedback

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Trigger

After PR #217 made pull-request lifecycle events launch canonical branch resnapshots, the design was exercised under the repository's unusually high PR/branch activity.

The first important feedback was positive: `pull_request_target` events fired using trusted repository-owned workflow code and read-only permissions. But the full branch audit is O(number of branches) in GitHub API observations/comparisons. Multiple lifecycle scans, main-push scans, and concurrent repository activity consumed the GitHub App installation API budget faster than cancellation could prevent.

Post-#221 Branch Convergence Audit run `33205890139` therefore failed during live classification with GitHub HTTP 403:

```text
API rate limit exceeded for installation
```

The deterministic auditor/planner tests had passed before the API call failure. The failure was resource pressure in the observation mechanism, not evidence that a branch was safe or unsafe.

## Design correction

A PR lifecycle event is now treated as a **plan invalidation**, not as permission to immediately perform another full graph scan.

For `pull_request_target` events the workflow performs no checkout, runs no repository code, calls no GitHub API, and emits only a bounded summary containing event identity plus:

```text
previous plan stale = true
full scan performed = false
merge authorized = false
```

The next full branch resnapshot is produced by:

- a push to `main`;
- the scheduled audit;
- manual dispatch;
- or a proposed auditor/planner PR test when API budget is sufficient.

## API-budget gate

Before an expensive full scan, the workflow observes the GitHub core rate budget. A full scan requires at least 500 remaining core requests.

If the budget is lower or cannot be observed:

- deterministic local planner tests still run;
- live branch classification is skipped;
- no branch merge plan is produced;
- the run records a blocked rate-limit state;
- `merge_authorized` remains false.

This is deliberately fail-closed. Partial branch data is not converted into a plan.

## Why cancellation alone was insufficient

`cancel-in-progress` stops stale jobs but cannot refund API requests already consumed before cancellation. With more than one hundred branches, several overlapping scans can spend hundreds of requests even if only one eventually survives.

The corrected controller therefore reduces **observation metabolism**, not only concurrency.

## Controller lesson

A self-evolving repository must account for the cost of observing itself:

```text
observation value / observation cost
```

is part of the control problem. More frequent sensing is not automatically better. When observation itself can saturate a resource, a safe controller should downgrade from "resnapshot now" to "invalidate prior belief and wait for capacity."

This is the same homeostatic principle used elsewhere in IDKMesh: capacity pressure suppresses reproduction/amplification rather than being compensated by activity.

## Authority boundary

The correction does not add merge, approval, push, deletion, settings, or compute authority. Branch plans remain decision support only, and all exact-head integration decisions must still be revalidated independently.