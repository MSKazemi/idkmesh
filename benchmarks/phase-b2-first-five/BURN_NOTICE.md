# Phase B2 first-five burn notice

The original `phase-b2-first-five` cohort is retained as a **burned diagnostic pilot**.

Its pre-outcome definition digest remains unchanged:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

## What exposed the problem

Task 001 (`benchmark/phase-b2/001-cohort-path-boundary`) was solved as real repository work in PR #153 and merged as `c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`.

The solution correctly adds a Python statement containing:

```text
resolve_repo_file(args.cohort
```

The frozen task-001 EvaluatorPlan v0.2 also stores that fragment in `backend.required_added_text`.

However deterministic patch verifier v0.1.1 interprets `required_added_text` as **exact added-line equality**, not substring containment. The real added line contains the fragment but is not equal to it, so the frozen evaluator would reject a legitimate solution.

The same semantic mismatch pattern exists in the other frozen plans, which contain fragments such as:

- `frozen cohort without definition_digest`
- `definition-json`
- `definition_projection(`
- `def load_cohort_argument(`
- `definition_digest`

## Why the cohort is burned instead of repaired

Changing the frozen EvaluatorPlan contents or silently changing verifier v0.1.1 semantics after seeing task-001's solution would violate the pre-outcome commitment.

Therefore:

- the original WorkUnits and EvaluatorPlans remain unchanged;
- the original definition digest remains unchanged;
- all five task outcomes are excluded from benchmark claims;
- the machine-readable cohort lifecycle is `burned`;
- the evaluator defect is preserved as evidence rather than erased.

This is a successful use of the freeze mechanism: it prevented the benchmark from redefining success after observing a candidate.

## Successor

Issue #157 tracks an explicitly versioned semantic-match contract for a successor cohort. Existing EvaluatorPlan v0.2 / patch-verifier v0.1.1 exact-line behavior must remain reproducible.

A successor must not treat task 001 as untouched held-out evidence because its solution is already known.

No burn or successor mechanism grants automatic candidate selection, merge, push, or canonical-write authority.
