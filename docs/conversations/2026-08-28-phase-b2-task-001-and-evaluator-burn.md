# Conversation record — Phase B2 task 001 and evaluator burn

Date: 2026-08-28

Repository: `MSKazemi/idkmesh`

## User direction

The user asked the project to continue development of the public IDKMesh repository.

## Live-state discovery

The repository had advanced beyond the previous turn:

- the Benchmark Cohort v0.1 contract was already merged;
- PR #134 had already frozen the first five Phase B2 task definitions;
- all five task evidence states were still pending;
- no open PR was solving task 001.

The frozen cohort used source revision:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`

and pre-outcome definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

## Task 001 real repository solution

Task 001 identified a real boundary defect in `tools/benchmark_cohort.py`: the `validate` and `definition-digest` CLI paths resolved `--cohort` directly instead of using the repository-bounded `resolve_repo_file` guard.

A bounded one-file change was created on branch:

`fix/phase-b2-task-001-cohort-path-boundary`

PR #153 changed only `tools/benchmark_cohort.py` and:

- routed both CLI entry points through `resolve_repo_file(args.cohort, ...)`;
- added deterministic traversal and absolute-path rejection coverage;
- kept the frozen WorkUnit/evaluator/cohort definition unchanged.

The frozen-source comparison confirmed that `tools/benchmark_cohort.py` had no unrelated drift between the frozen source SHA and the candidate beyond the task-001 patch.

Exact-head checks passed:

- Benchmark Cohort Contract workflow — success;
- IDKMesh Evolution Loop — success;
- frozen first-five cohort validation — success.

PR #153 was squash-merged as:

`c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`

## Critical pre-outcome evaluator finding

Before attaching a positive ResultManifest/VerificationResult, the frozen EvaluatorPlan was checked against the actual patch-verifier semantics.

Task 001's frozen plan contains:

```json
"required_added_text": ["resolve_repo_file(args.cohort"]
```

but deterministic patch verifier v0.1.1 computes missing expectations using exact membership in parsed added lines. The valid task-001 patch adds a complete Python statement containing the fragment, not a line exactly equal to the fragment.

Therefore the frozen evaluator would reject a legitimate candidate.

The audit then found the same mismatch pattern across the other frozen first-five evaluator plans, including fragments such as:

- `frozen cohort without definition_digest`
- `definition-json`
- `definition_projection(`
- `def load_cohort_argument(`
- `definition_digest`

This is a systemic frozen-evaluator semantics defect, not a task-001-only problem.

## Integrity decision

The project must not:

- reinterpret `required_added_text` under verifier v0.1.1 after seeing the result;
- mutate the frozen EvaluatorPlan digests;
- label the legitimate task-001 solution as incorrect because of a defective frozen evaluator;
- use the remaining plans for benchmark claims without a versioned correction.

Instead, the first-five cohort is retained as a **burned diagnostic pilot**.

The machine-readable cohort changes lifecycle/output state only; the pre-outcome definition remains immutable:

- `stage`: `burned`;
- all five evidence records: `excluded` with explicit reasons;
- original WorkUnits unchanged;
- original EvaluatorPlans unchanged;
- original definition digest unchanged.

## Successor work

Issue #157 was created:

`P0: Version patch-verifier semantic matching before Phase B2 successor cohort`

It requires:

1. preserving EvaluatorPlan v0.2 / verifier v0.1.1 exact-line behavior;
2. introducing an explicitly versioned semantic-fragment contract instead of silently changing meaning;
3. tests that distinguish exact-line and substring semantics;
4. exact provenance for the new plan/verifier versions;
5. freezing a successor cohort only after the new contract is green;
6. never treating task 001 as untouched held-out evidence because its solution is already known.

## Why this is useful

This is precisely what the pre-outcome commitment was designed to expose. A correct candidate revealed that the evaluator definition was defective, and the project preserved that negative evidence instead of changing the test after observing the answer.

The resulting rule is stronger:

> A frozen benchmark may fail because the candidate is wrong or because the benchmark is wrong. IDKMesh must preserve enough provenance to distinguish those cases, and it must version the benchmark/evaluator rather than rewriting history.

No step in this turn grants automatic candidate selection, merge authority to workers/verifiers, paid-compute authority, or autonomous canonical-write authority.
