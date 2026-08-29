# Phase B2 first-five benchmark v2

This directory is a **new pre-outcome commitment** replacing the original `phase-b2-first-five` definition for future benchmark evidence.

## Why v2 exists

The original frozen cohort remains public and is not rewritten. Before candidate execution for tasks 2–5, task 001 was solved independently on `main` by commit `c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`. Comparing that natural correct patch to the already-frozen task-001 EvaluatorPlan exposed a definition defect: `required_added_text` is exact complete-line matching, but the v1 plan froze the fragment `resolve_repo_file(args.cohort`.

The natural correct added line was:

```python
    cohort_path = resolve_repo_file(args.cohort, label="BenchmarkCohort")
```

Therefore the v1 evaluator would reject the correct solution. Because the task-001 outcome is now known, its evaluator must not be tuned and reused as held-out evidence.

## v2 definition

- cohort id: `benchmark/phase-b2-first-five-v2`
- definition digest: `sha256:0c694c65bb944debfd0877942384e7c1dfa1069e0aaa5e6f581d7afdb7f01712`
- new bug-fix source revision: `48a7e75aa60fce7ba7f1a39554ba43f66348219c`
- tasks 2–5 retain their original immutable source revision: `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`
- all evidence is pending at freeze time
- automatic candidate selection / canonical write / push / merge authority remain false

v2 replaces task 001 with a fresh benchmark-integrity bug: canonical negative categories must not be considered verified from opaque `other` or unvalidated run-record JSON merely because a digest matches.

Tasks 2–5 retain the original WorkUnits, which have no inspected candidate outcomes, but use newly committed v2 EvaluatorPlans with **complete natural added-line predicates** instead of fragments.

## Evidence discipline

The v1 definition digest remains unchanged and its task-001 solution is retained as calibration/burn evidence. v2 must not be edited after candidate outcomes to make solutions pass. If another definition defect is found, burn/supersede again rather than silently tuning the evaluator.

Validate:

```bash
python tools/benchmark_cohort.py validate \
  --cohort benchmarks/phase-b2-first-five-v2/cohort.json
```

Do not use `--require-evidence` until all five tasks have analyzed attempts and verified seeded-negative evidence.
