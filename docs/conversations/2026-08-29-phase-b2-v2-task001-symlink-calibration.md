# Conversation record — successor-v2 Task 001 symlink calibration

## Direction

Continue resolving the repository issue queue after Task 004 calibration.

## Finding

Task 001 was the last uncalibrated successor-v2 task. The frozen implementation
resolves a repository-relative path before checking `is_symlink()`, so a direct
symlink to a valid in-repository cohort loses its link identity and is accepted.

The provisional evaluator also failed to encode ordering. A patch can remove
the one-line resolve, add an `is_symlink()` line after a split resolve, and pass
the old lexical proxy without changing behavior.

## Action

The pre-freeze plan is strengthened to require construction of an unresolved
path, rejection of that path when it is a symlink, and resolution afterward.
A new exact-source harness verifies a straightforward repair and an ordering
decoy through canonical EvaluatorPlan v0.4, plus a separate path-boundary
behavioral matrix.

## Boundary

This is calibration, not a production fix or benchmark result. The scaffold
remains unfrozen and outcome-empty. Exact CI evidence must be registered in a
separate current-main change before declaring the final calibration complete.

## Outcome

PR #235 passed at exact head `8b9e4a238853b92d9546d06f36066283e5816bdb`
and merged as `b6505bd624f7e6a2b9285a9fe936288ea3920e4d`. Run
`33221041390`, job `99014922387`, and artifact `9705160930` proved the safe
ordering and rejected the vulnerable decoy. Its receipt completes all five
per-task calibrations and sets `freeze_ready=true`, while deliberately leaving
the scaffold unfrozen, without a definition digest or scored outcomes.
