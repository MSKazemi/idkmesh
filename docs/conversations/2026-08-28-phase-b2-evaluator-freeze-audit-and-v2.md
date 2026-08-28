# Project Turn: Phase B2 evaluator-freeze audit and v2 benchmark commitment

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Repository reassessment

The continuation re-read current repository state before creating new work.

The critical path had advanced substantially:

- controlled Docker acceptance issue #37 is complete;
- PR #116 EvaluatorPlan-aware two-attempt routing is merged;
- PR #120 two-real-attempt verification/report/replay is merged;
- issue #5 has moved into Phase B2 benchmark work;
- a Benchmark Cohort v0.1 contract and a frozen first-five cohort had already landed, so no duplicate benchmark protocol was created.

The existing first-five cohort was frozen at definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

with five task families and pending evidence.

## Evaluator-definition audit

Before generating candidate evidence, the unified-diff verifier implementation was checked against the frozen evaluator plans.

The verifier treats `backend.required_added_text` as **exact equality against complete added hunk lines**. It is not substring or regular-expression matching.

Several v1 evaluator plans had frozen fragments such as:

```text
resolve_repo_file(args.cohort
```

rather than complete expected added lines.

This was initially a definition-quality concern. It became concrete when task 001 was independently fixed on `main` by commit:

`c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`

The natural correct patch added:

```python
    cohort_path = resolve_repo_file(args.cohort, label="BenchmarkCohort")
```

That correct complete line does not equal the v1 fragment. Therefore the frozen v1 task-001 evaluator would reject the correct merged solution.

## Anti-Goodhart decision

Do **not** edit the frozen evaluator after observing task 001's solution and then reuse the task as held-out evidence.

Instead:

1. preserve the original definition digest;
2. mark the v1 cohort `burned`;
3. explicitly exclude task 001 as calibration evidence;
4. keep the natural correct solution and evaluator mismatch public;
5. create a separate v2 cohort commitment before generating outcomes for its included tasks.

This preserves the Benchmark Cohort contract's central rule: outcome evidence must not silently rewrite pre-outcome evaluator commitments.

## Fresh replacement bug

A new bug-fix task was selected without first generating a candidate solution.

Current `tools/benchmark_cohort.py` accepts `negative_case.evidence_type = run_record` or `other` with only a JSON digest check. For canonical finding categories such as correctness, scope, provenance, security, and regression, the evidence content is therefore not currently required to establish that category.

The v2 replacement task freezes the requirement that canonical finding categories must use canonical `VerificationResult` evidence. Opaque/unvalidated evidence types remain available for non-canonical control-failure categories where appropriate, but cannot establish a canonical security/regression/correctness finding merely by matching a digest.

The new replacement WorkUnit is bound to immutable source revision:

`48a7e75aa60fce7ba7f1a39554ba43f66348219c`

WorkUnit digest:

`sha256:be724106c699da2a52d92432bb8dcce49892eb84181dfdc66fdacb12a74b8623`

## Phase B2 first-five v2

A new cohort was frozen under:

`benchmarks/phase-b2-first-five-v2/`

Definition digest:

`sha256:0c694c65bb944debfd0877942384e7c1dfa1069e0aaa5e6f581d7afdb7f01712`

The cohort contains:

1. fresh negative-evidence-type-boundary bug fix;
2. frozen-definition-digest regression test;
3. definition-json bounded feature;
4. safe cohort-loader refactor;
5. first-five freeze checklist documentation contract.

Tasks 2–5 retain their original WorkUnits and immutable source revision because no candidate outcomes for them were inspected. They receive new v2 EvaluatorPlans with complete natural-line predicates, committed before candidate generation.

All v2 evidence remains `pending` at freeze time.

## Authority boundary

Neither cohort grants:

- canonical repository write authority;
- Git push authority;
- merge authority;
- automatic candidate selection.

A deterministic evaluator recommendation remains decision support, not integration authority.

## CI change

The existing read-only Benchmark Cohort Contract workflow is extended to validate both:

- the burned v1 historical record; and
- the frozen v2 pre-outcome definition.

The workflow still executes no candidate code and has read-only repository permission.

## Next evidence step

Only after the v2 definition is reviewed/merged should candidate generation begin.

The next sequence is:

```text
frozen v2 definition
 -> generate bounded candidate attempt
 -> canonical ResultManifest + patch/log bundle
 -> frozen EvaluatorPlan v2
 -> independent VerificationResult
 -> seeded-negative evidence
 -> attach evidence without changing definition_digest
 -> replay/validate cohort
```

If another evaluator-definition defect is discovered after outcomes, the correct action is to burn/supersede again rather than tune the frozen evaluator to the observed solution.
