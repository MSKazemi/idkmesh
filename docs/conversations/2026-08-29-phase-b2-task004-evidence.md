# Phase B2 Task 004 evidence

**Date:** 2026-08-29

## Scope

Issue #5 still lacked scored evidence for the frozen safe-cohort-loader
refactor. The bounded worker reconstructs that one-file change against source
`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`, without modifying the benchmark
definition or evaluator.

## Verification design

The candidate routes `validate` and `definition-digest` through one shared
repository-bounded loader. The frozen public EvaluatorPlan v0.4 checks the
patch structure, artifact hashes, logs, and WorkUnit binding. A separate
behavioral probe confirms both commands reject an external cohort path, then
temporarily restores the unsafe loader in only `definition-digest` and observes
the expected divergence.

## Authority boundary

The worker and seeded probe run in an isolated checkout. The metadata evaluator
does not execute candidate code. The resulting support recommendation does not
grant candidate-selection, canonical-write, push, or merge authority.
