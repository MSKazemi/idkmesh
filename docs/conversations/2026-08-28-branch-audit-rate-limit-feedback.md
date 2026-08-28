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

The next full branch resnapshot is produced only by:

- a push to `main`;
- the scheduled audit;
- manual dispatch.

A `pull_request` that changes the auditor/planner runs deterministic proposed-code tests only. It deliberately does not spend the live branch-observation API budget.

## API-budget gate

Before an expensive canonical full scan, the workflow observes the GitHub core rate budget. The final preflight reserve is **1500 remaining core requests**.

The earlier 500-request prototype was empirically insufficient: PR #222 run `33206118365` passed the preflight but still encountered installation rate exhaustion at the first branch-list request because the shared budget could change between observations.

Therefore the final design uses two fail-closed layers:

1. **Preflight:** if the observed remaining budget is below 1500, or the budget cannot be observed, skip the live classification and emit no branch merge plan.
2. **Mid-scan:** if GitHub still returns a rate-limit error during classification, capture `scan-blocked.json`, set `full_scan_complete=false` and `merge_authorized=false`, emit no plan, and complete the observer as a blocked state rather than treating partial data as authority.

Non-rate-limit auditor errors still fail normally.

## Why cancellation alone was insufficient

`cancel-in-progress` stops stale jobs but cannot refund API requests already consumed before cancellation. With more than one hundred branches, several overlapping scans can spend hundreds of requests even if only one eventually survives.

The corrected controller therefore reduces **observation metabolism**, not only concurrency. Cheap PR invalidations also use a separate concurrency class so they cannot cancel an already-running canonical full scan.

## Controller lesson

A self-evolving repository must account for the cost of observing itself:

```text
observation value / observation cost
```

is part of the control problem. More frequent sensing is not automatically better. When observation itself can saturate a resource, a safe controller should downgrade from "resnapshot now" to "invalidate prior belief and wait for capacity."

This is the same homeostatic principle used elsewhere in IDKMesh: capacity pressure suppresses reproduction/amplification rather than being compensated by activity.

## Authority boundary

The correction does not add merge, approval, push, deletion, settings, spending, or compute authority. A lifecycle invalidation makes prior branch conclusions *less* authoritative. A blocked full scan produces no plan. All exact-head integration decisions must still be revalidated independently.