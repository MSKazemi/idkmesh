# Project Turn: Phase B2 successor Task 001 first bounded attempt

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Preconditions completed before this attempt

The fresh successor cohort was merged by PR #182 as:

`d331d635718bef5561ba815e76675b434e7c2bea`

Frozen cohort:

`benchmark/phase-b2-successor-five`

Frozen definition digest:

`sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`

Exact-head pre-merge checks succeeded:

- Benchmark Cohort Contract run `33195507668`;
- IDKMesh Evolution Loop run `33195507639`;
- idkgraph-observatory run `33195507701` on Python 3.11 and 3.13.

Every successor task still had `evidence.status = pending` at merge. No outcome was used to tune the definition.

## Scope of this execution

Only successor Task 001 is executed:

`benchmark/phase-b2-successor/001-negative-evidence-type-boundary`

Frozen source:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

Frozen WorkUnit digest:

`sha256:04258ad63d36368ae6780b351f5e3729fe5f7a12de66aee16d1bc475a8b69096`

Frozen EvaluatorPlan v0.4 digest:

`sha256:1abee7b4886e8c4626af8714cfad72c04cac6e93a42920af8dddf598a2236ddc`

Structural signature:

`single-worker-baseline-v1`

## Seeded bug

On the frozen source, `_validate_negative_case()` first checks the JSON digest and only applies semantic VerificationResult validation under:

```python
if negative["evidence_type"] == "verification_result":
```

Therefore a seeded negative declaring canonical category `security` can use `evidence_type = other` and a digest-valid but semantically unrelated JSON object, and validation accepts it.

The attempt harness proves this baseline behavior before modifying the isolated source.

## Candidate transform

The worker is a bounded deterministic baseline, not a benchmark oracle. It edits only:

`tools/benchmark_cohort.py`

The candidate changes the trust boundary to:

1. require `evidence_type == verification_result` whenever `expected_category` is one of the canonical finding categories;
2. return early for non-VerificationResult evidence only after that category-aware gate;
3. preserve canonical VerificationResult schema/recommendation/category validation.

The candidate must compile and the existing benchmark cohort self-test must still pass.

## Independent evidence channels

### Frozen metadata-only evaluator

The canonical EvaluatorPlan v0.4 checks the committed transition:

- add category-aware canonical-negative validation;
- add the VerificationResult requirement;
- remove the old evidence-type-only `if` gate.

The verifier remains metadata-only and does not execute candidate code.

### Behavioral seeded negative

The harness independently creates the same schema-valid cohort negative before and after the candidate using:

- `expected_category = security`;
- `evidence_status = verified`;
- `evidence_type = other`;
- a real existing JSON file with its correct canonical digest.

Required observation:

```text
frozen source -> accepts the opaque security evidence
candidate     -> rejects it specifically because canonical categories require VerificationResult evidence
```

A separate schema-valid VerificationResult is emitted for this deliberately invalid security negative with:

- `recommendation = reject_candidate`;
- a `security` finding;
- digest-bound behavioral observation evidence.

This seeded-negative object is not the candidate acceptance verdict.

## Output bundle

The read-only workflow emits under ignored `results/`:

- `candidate.patch`;
- `stdout.txt`;
- `stderr.txt`;
- `opaque-negative-observation.json`;
- canonical `result-manifest.json`;
- frozen-plan `verification-result.json`;
- `seeded-negative.verification-result.json`;
- `attempt-summary.json`.

The tool also prints the canonical objects between explicit log markers so durable evidence can be promoted after the exact-head run without changing the frozen benchmark definition.

## Authority boundary

This attempt does not:

- edit `benchmarks/phase-b2-successor-five/cohort.json`;
- edit any frozen EvaluatorPlan;
- auto-select the candidate;
- write canonical state from CI;
- push or merge code;
- approve a pull request;
- use secrets or project-paid compute authority.

The next decision depends on exact-head CI evidence. If the attempt fails, diagnose the worker/evidence harness without changing the frozen benchmark definition to fit the candidate.
