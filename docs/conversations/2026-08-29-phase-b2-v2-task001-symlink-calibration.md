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
