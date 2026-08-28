# Project Turn: Freeze the fresh Phase B2 successor five-task cohort

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Convergence before the freeze

This continuation repeatedly re-read the live repository instead of duplicating fast-moving parallel work.

The important sequence that had completed on `main` was:

1. the original first-five cohort was burned after Task 001 exposed a Goodhartable evaluator proxy;
2. issue #157 required versioned semantic matching and real legitimate-vs-decoy calibration;
3. EvaluatorPlan v0.3 / verifier 0.2.0 added explicit added-line substring semantics;
4. EvaluatorPlan v0.4 / verifier 0.3.0 added explicit added+removed transition semantics;
5. Benchmark Cohort v0.1 was updated to route public v0.2/v0.3/v0.4 plans by declared schema version;
6. PR #177 merged canonical real Task 001 v0.4 calibration on the exact burned source;
7. the calibration workflow accepted the straightforward transition, rejected the inert Goodhart decoy, and independently confirmed the path-boundary behavioral matrix;
8. issue #157 closed completed.

The old definition digest remains:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

and the known Task 001 solution is not reused as held-out benchmark evidence.

## Fresh successor freeze

A new branch was created from immutable source revision:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

Branch:

`benchmark/phase-b2-successor-five`

New cohort:

`benchmark/phase-b2-successor-five`

Definition digest:

`sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`

At freeze time:

- stage is `frozen`;
- all five task evidence states are `pending`;
- no candidate ResultManifest exists;
- no VerificationResult outcome exists;
- no seeded-negative evidence is marked verified;
- automatic candidate selection is false;
- canonical write, Git push, and merge authority are false.

## Task 001 — fresh outcome-unseen bug

The fresh bug exists on the new source snapshot in `tools/benchmark_cohort.py`.

Current `_validate_negative_case()` only applies canonical semantic checks when:

```text
evidence_type == verification_result
```

For opaque `other` / unvalidated run-record JSON, a matching digest can therefore be enough to reach `evidence_status = verified` even when the task declares a canonical finding category such as security, regression, or correctness.

The new WorkUnit requires replacing that evidence-type-only dispatch with category-aware validation:

- canonical finding categories must require canonical VerificationResult evidence;
- non-canonical control-failure categories may retain their appropriate evidence types.

WorkUnit digest:

`sha256:04258ad63d36368ae6780b351f5e3729fe5f7a12de66aee16d1bc475a8b69096`

Its EvaluatorPlan v0.4 commits both sides of the intended transition:

- added category-aware / VerificationResult requirement;
- removal of the old evidence-type-only `if` gate.

Plan digest:

`sha256:1abee7b4886e8c4626af8714cfad72c04cac6e93a42920af8dddf598a2236ddc`

The plan is structural transition evidence only. Final inclusion still requires a verified seeded negative proving opaque security evidence fails closed.

## Tasks 2–5 — outcome-unseen WorkUnits only

The successor deliberately reuses the four original WorkUnits whose candidate outcomes were never inspected before the predecessor was burned:

2. frozen-definition-digest regression test;
3. definition-json bounded feature;
4. safe cohort-loader refactor;
5. first-five freeze checklist documentation contract.

It does **not** reuse their burned evaluator commitments.

New evaluator-plan digests:

- task 002 v0.3: `sha256:185b46d16cb45948fc03b05a40622a58d96de05a149a1528d166625f1b82a059`;
- task 003 v0.3: `sha256:8466c3bddc442451582d52f7616dfb55351e5bef851891a72249f219b1e43d3d`;
- task 004 v0.4: `sha256:00e20edc78efdf96206e7f532aaac2ed2389e35644f986da1d7354fed410ba17`;
- task 005 v0.3: `sha256:e27ac0fe418f068b853b2041f0bcb419573c7d5215a6b4d3b7942f4c3027bd6f`.

v0.4 is used where the intended task is explicitly a remove-unsafe/add-safe transition. v0.3 is used for additive-only tasks. In both cases the plan extensions state that structural semantics are not a final correctness oracle; seeded-negative/behavioral evidence is required before verified inclusion.

## CI change

The existing read-only Benchmark Cohort Contract workflow is extended to validate both:

- the burned original cohort; and
- the fresh successor five-task freeze.

It still executes no candidate code, exposes no worker secrets/network/spending authority, and has no repository write or integration authority.

## Next step after exact-head contract validation

Only after the successor definition passes the repository's own exact-head cohort contract should candidate generation start.

The first execution should be bounded to one task rather than immediately fanning out all five:

```text
successor task 001
 -> isolated candidate ResultManifest + patch/log bundle
 -> frozen EvaluatorPlan v0.4
 -> independent VerificationResult
 -> explicit seeded negative with opaque evidence_type=other
 -> attach evidence without changing definition_digest
 -> replay cohort definition
```

Then proceed to tasks 2–5 only if the first task's verifier/reviewer burden remains healthy.

If any new definition defect is discovered after observing an outcome, burn/supersede the affected commitment. Do not tune the frozen plan to make an observed candidate pass.
