# Project Turn: Benchmark EvaluatorPlan version routing

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Continuation state

The repository had advanced past controlled Docker acceptance and two-real-attempt replay into Phase B2 benchmark work. The original first-five cohort was correctly burned after task 001 demonstrated that the frozen v0.2 evaluator proxy could both reject a natural correct patch and accept a decoy.

A successor definition was prepared in draft PR #163, but another repository thread correctly placed it behind issue #157 / PR #164 so benchmark work would not outrun the versioned verifier contract.

PR #164 subsequently merged as `a5e41dfc470e001d33dee18a6b795f1b91843d22`, establishing:

- EvaluatorPlan v0.2 + verifier v0.1.1: exact complete-added-line `required_added_text` semantics;
- EvaluatorPlan v0.3 + verifier v0.2.0: explicit case-sensitive, single-added-line `required_added_substrings` semantics;
- unchanged metadata-only candidate non-execution and provenance/authority boundaries.

The draft hold on #163 was not overridden while #164 was unresolved.

## Newly discovered integration gap

After v0.3 merged, the canonical benchmark cohort validator was checked before simply marking #163 ready.

`tools/benchmark_cohort.py` was still hard-wired to:

```python
EVALUATOR_PLAN_SCHEMA = SCHEMA_DIR / "evaluator-plan-v0.2.schema.json"
```

and `_validate_public_plan()` validated every public plan against that one schema.

Therefore a successor cohort could not actually commit a public EvaluatorPlan v0.3 through the canonical benchmark contract even though the evaluator runner supported it. Keeping #163 on v0.2 merely to satisfy the cohort validator would defeat the purpose of the version boundary.

## Fix

A small dependency branch, `fix/benchmark-cohort-evaluator-version-routing`, updates the canonical validator to route by the plan's declared `schema_version`:

- `0.2` -> `schemas/evaluator-plan-v0.2.schema.json`;
- `0.3` -> `schemas/evaluator-plan-v0.3.schema.json`;
- unknown/missing versions -> fail closed.

Historical v0.2 behavior is preserved.

The deterministic contract self-test now validates both:

1. the existing public v0.2 patch plan fixture;
2. the new public v0.3 substring-plan fixture;

and explicitly verifies that an unsupported evaluator schema version is rejected.

## Evidence-strength rule for the successor cohort

EvaluatorPlan v0.3 substring matching is a **structural semantic signal**, not correctness proof. For security/correctness/regression benchmark claims where a stronger seeded negative or behavioral check exists, final benchmark inclusion must still require independently verified negative-case evidence. A substring match alone must never become the task's correctness oracle.

## Next sequence

```text
merge v0.3 cohort-version routing
 -> update draft #163 to EvaluatorPlan v0.3
 -> recompute all plan digests and the pre-outcome definition digest
 -> validate the frozen successor definition
 -> only then generate candidate outcomes
```

No candidate outcomes for the successor cohort are generated in this dependency step, and no automatic selection, canonical write, push, approval, merge, or spending authority is introduced.
