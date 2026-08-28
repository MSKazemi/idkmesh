# Active compute current-main convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Maintainer direction

Continue repository convergence without bulk-merging stale branches.

## State observed

Historical PR #195 proposed a guarded GitHub Actions compute pulse, but its source branch had drifted more than fifty commits behind current `main` and its latest head no longer had fresh PR workflow evidence.

The repository branch-lifecycle rule is therefore applied:

```text
stale useful branch
  -> inspect unique delta
  -> rebuild bounded delta on current main
  -> earn fresh exact-head CI
  -> preserve activation/review gates
```

Do not merge stale ancestry merely because its idea remains useful.

## Rebuilt bounded delta

The current-main integration branch restores only the still-useful active-compute surface:

- `.github/workflows/active-compute-pulse.yml`;
- `experiments/github_actions_compute_offer.py`;
- a small Phase 0 self-test hook for the live-offer promotion policy.

The older conversation file is not copied verbatim because it described the historical branch rather than the current integration state.

## Safety and authority boundary

The pulse remains dormant unless both conditions hold:

1. repository variable `ACTIVE_COMPUTE_PULSE_ENABLED` is exactly `true`;
2. GitHub reports the exact workflow SHA as the protected current `main` tip.

The workflow has read-only contents permission, persists no checkout credential, uses no repository secret, executes only a fixed checked-in deterministic smoke Work Unit, and has no issue/PR/branch/push/merge authority.

The live-offer adapter fails closed unless it is running in the canonical repository on `main` from `schedule` or `workflow_dispatch`, with explicit activation and protected-main evidence.

## Integration rule

Because merging the workflow into the default branch creates a new scheduled execution surface, the replacement PR remains **draft** until a separate reviewer/maintainer consciously accepts that activation boundary.

Green CI is required evidence but is not itself authorization to activate the scheduled lane.

## Relationship to branch convergence

- historical #195 should be closed once the replacement PR exists;
- its source branch should later be retired through the branch-cleanup process after exact-head revalidation;
- the replacement branch is the only active integration candidate for this active-compute delta;
- branch count is reduced by retiring superseded refs, not by merging stale ancestry into `main`.
