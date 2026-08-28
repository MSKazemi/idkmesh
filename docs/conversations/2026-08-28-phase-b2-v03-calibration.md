# Project Turn: Phase B2 v0.3 legitimate-vs-decoy calibration

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Why this step exists

The original Phase B2 first-five cohort was burned after real Task 001 evidence showed that the frozen EvaluatorPlan v0.2 exact-line proxy produced both a false negative and a false positive.

PR #164 subsequently merged EvaluatorPlan v0.3 / deterministic patch verifier v0.2.0 with explicit single-added-line substring semantics while preserving v0.2 history. PR #168 then taught the canonical Benchmark Cohort validator to route public evaluator plans by declared v0.2/v0.3 schema version.

Issue #157 nevertheless remained open because the successor contract still needed calibration against the **actual legitimate Task 001 patch and the actual inert decoy** preserved by closed diagnostic PR #158.

## Preserved source evidence

The original read-only workflow artifact is:

- run: `33193136434`;
- artifact: `9694595266`;
- artifact ZIP digest: `sha256:ce7d4ca382f0dec58ac8a05a31ceff3cc88aec887345eebd099d7a8c553aaba1`.

Two exact patch artifacts are copied into stable calibration fixtures:

- straightforward patch: `sha256:9248e19254bf46bf11ac254dca3302eccdcc2f498117e07f3c86ce0b9f3bb65a`;
- inert decoy patch: `sha256:f315def3f8d16b4eb3ec7ea3a56ab73d696d08a6cf58b60b06e9e297c3997c17`.

Frozen source revision remains:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`

## Prospective v0.3 calibration plan

A dedicated calibration-only EvaluatorPlan v0.3 is bound to the original Task 001 WorkUnit and source. It requires the added-line substrings:

```text
load_json(resolve_repo_file(args.cohort
label="BenchmarkCohort"
```

These occur in the natural fix but not in the historical inert exact-line decoy.

This structural predicate is **not** treated as security correctness proof. It is only the semantic discrimination layer for the versioned metadata-only verifier.

## Two-layer calibration matrix

`tools/phase_b2_task001_v03_calibration.py` requires:

1. **metadata-only semantic layer**
   - straightforward patch -> `passed / accept_candidate` under v0.3;
   - historical inert decoy -> `failed / reject_candidate` under v0.3;
   - exact plan digest and verifier version `0.2.0` are preserved in VerificationResult provenance.

2. **separate behavioral layer**
   - apply each fixed checked-in patch to an independent checkout of the exact frozen public source;
   - generate a schema-valid external cohort fixture from the unmodified frozen source;
   - straightforward patch must reject an absolute out-of-repository `--cohort` path specifically as unsafe;
   - decoy patch must still accept the same absolute path and emit a definition digest.

The behavioral check is not part of the metadata-only evaluator backend. It is a trusted regression test over two fixed calibration fixtures, so v0.3 does not gain arbitrary candidate-code execution authority.

## Evidence-strength rule

A future successor benchmark may use v0.3 substring semantics as a structural signal, but security/correctness/regression inclusion must still require independently verified seeded-negative or behavioral evidence whenever such a stronger check exists.

Thus:

```text
substring match != correctness
substring match + independent behavioral negative evidence -> usable decision support
```

## Authority boundary

This calibration adds no:

- automatic candidate selection;
- canonical repository write authority;
- Git push authority;
- PR approval or merge authority;
- spending authority.

The original burned cohort and its definition digest remain unchanged. No successor candidate outcomes are generated in this calibration step.

## Next gate

If the exact-head calibration workflow is green, issue #157's legitimate-vs-decoy calibration requirement can be considered satisfied. Only then should a fresh successor Phase B2 cohort be frozen under v0.3, with all outcomes pending and the new definition digest committed before candidate generation.
