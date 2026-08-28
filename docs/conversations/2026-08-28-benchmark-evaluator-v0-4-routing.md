# Conversation record: route EvaluatorPlan v0.4 through benchmark cohorts

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner instructed: **Continue**.

The standing project rule is to preserve substantive collaboration publicly in the repository and to prefer bounded convergence work over creating another parallel protocol.

## Repository state observed

During this continuation, EvaluatorPlan v0.4 had already merged through PR #171.

The canonical semantic version boundaries are now:

```text
EvaluatorPlan v0.2 / verifier 0.1.1
    exact full added-line matching

EvaluatorPlan v0.3 / verifier 0.2.0
    added-line substring matching

EvaluatorPlan v0.4 / verifier 0.3.0
    added-line + removed-line substring transition matching
```

PR #171's calibration matrix was green before merge and preserves the historical v0.2/v0.3 meanings.

A separate concurrent change had also improved `tools/benchmark_cohort.py` so public benchmark EvaluatorPlans are selected fail-closed by their declared schema version. That validator, however, currently recognized only v0.2 and v0.3.

This left a small integration gap:

> the canonical verifier understood v0.4, but the canonical Benchmark Cohort validator could not yet index a public v0.4 EvaluatorPlan.

A successor Phase B2 cohort therefore could not safely freeze against the new contract even though the verifier itself was already merged.

## Change made

Extend the existing benchmark validator rather than introducing another benchmark tool.

`tools/benchmark_cohort.py` now routes:

```text
schema_version = 0.2 -> evaluator-plan-v0.2.schema.json
schema_version = 0.3 -> evaluator-plan-v0.3.schema.json
schema_version = 0.4 -> evaluator-plan-v0.4.schema.json
anything else         -> fail closed
```

The existing cross-object checks remain unchanged:

- repository-relative non-symlink plan path;
- exact EvaluatorPlan schema validation;
- exact plan id;
- exact canonical plan digest;
- evaluator backend equality;
- exact WorkUnit id/version/digest binding;
- exact source revision binding;
- exact required-validator set.

## Self-test extension

The deterministic benchmark self-test now constructs three otherwise equivalent scaffold cohorts using the checked-in patch verifier fixtures:

1. v0.2 plan;
2. v0.3 plan;
3. v0.4 transition plan.

Each must route through its declared schema and remain one pending scaffold task.

The existing unsupported `schema_version = 9.9` test remains and must fail closed.

The success message now explicitly reports v0.2/v0.3/v0.4 routing.

## Why this is the next step

Issue #157 requires a successor cohort to be frozen only after the new semantic contract and calibration matrix are green. PR #171 satisfied the verifier/calibration side. This change closes the benchmark-index side so a future cohort can actually bind to v0.4 without weakening schema or provenance checks.

It does **not** create or freeze the successor cohort yet.

The original Phase B2 first-five cohort remains burned diagnostic evidence with its original frozen definition digest. Task 001 remains known/solved and must not be reused as untouched held-out evidence.

## Authority boundary

This change adds no authority to:

- execute candidate code;
- write canonical repository state from CI;
- push branches automatically;
- approve or merge pull requests;
- select candidate outputs automatically;
- expose secrets;
- spend project funds.

The existing Benchmark Cohort Contract workflow is read-only and already runs `tools/benchmark_cohort.py self-test` whenever the validator changes, so the v0.4 routing will be exercised automatically in review.
