# Conversation record — successor-v2 Task 004 calibration

## Project direction

Continue resolving the repository issue queue while preserving branch, review,
evidence, and authority rules.

## Selected action

Issue #180 had two remaining calibration tasks. Task 004 was selected because
it is locally reproducible and not externally human-gated. A repository-history
and pull-request search found no previously published solution.

## Finding

The frozen RWVB source uses inequality-only validation. Several `NaN` and
Infinity values pass `Candidate` or `ControllerConfig` validation and can
produce non-finite debt/priority values or delayed arithmetic failures.

The provisional evaluator was itself too weak: an unused `math.isfinite`
reference plus a syntactic rewrite of the impact comparison met both required
transitions without fixing validation. Because the scaffold is explicitly
mutable before freeze, the evaluator was strengthened rather than treating the
near-miss as success.

## Implementation

`tools/task004_rwvb_nonfinite_calibration.py` constructs a straightforward
repair and an inert decoy against exact source `a69aa0a...`. It routes both
patches through canonical EvaluatorPlan v0.4 and separately executes 33
non-finite behavioral probes. The corresponding read-only workflow publishes
the calibration artifacts.

## Decision boundary

This work calibrates an evaluator. It does not publish the production repair,
freeze the scaffold, generate a scored result, choose a candidate, or authorize
repository writes or integration. The exact successful CI receipt must be
registered separately before Task 004 is marked calibrated.

## Outcome

PR #233 passed at exact head `44590d08274dcf0ebdf9f1680c18875a977e2fdc`
and merged as `621e648d6eb9503489a7cbddd53f95bfaf9941e7`. Calibration
run `33220488843`, job `99013300808`, and artifact `9704970824` proved the
straightforward 33/33 rejection matrix and rejected the behaviorally vulnerable
decoy. The separate receipt records those digests while leaving Task 001 as the
only pending calibration and keeping the scaffold unfrozen.
