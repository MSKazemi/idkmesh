# Conversation record: continue Phase B2 evaluator calibration with v0.4

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner instructed: **Continue**.

The standing project rule is to preserve substantive collaboration publicly in the repository and to prefer bounded, executable, independently reviewable progress over untested expansion.

## Starting point

Issue #157 records the Phase B2 first-five benchmark burn and the Task 001 calibration result:

- a legitimate Task 001 patch was rejected by the frozen v0.2 / verifier 0.1.1 exact-line evaluator;
- an inert exact-line decoy was accepted while the original path-boundary vulnerability remained;
- the first-five cohort remains burned with its original frozen definition digest;
- successor semantic contracts must be versioned rather than retroactively changing frozen evaluator meaning.

While this continuation was beginning, concurrent PR #164 merged EvaluatorPlan v0.3 and verifier 0.2.0. v0.3 correctly preserved historical v0.2 semantics and introduced explicit added-line substring matching.

That concurrent implementation was therefore adopted rather than duplicated.

## Remaining calibration gap

The post-burn Task 001 adversarial evidence demonstrates that **added-substring presence alone is not sufficient** for the calibrated transition objective.

A decoy can mention a safe API in an added line while leaving the unsafe mechanism untouched.

Changing v0.3 in place after this evidence would repeat the same semantic-integrity mistake the project is trying to prevent. The continuation therefore introduces another explicit version boundary instead.

## EvaluatorPlan v0.4 decision

EvaluatorPlan v0.4 / deterministic patch verifier 0.3.0 represents a textual **transition** as both:

```text
required safe substring appears in an added line
AND
required unsafe substring appears in a removed line
```

v0.4 does not execute candidate code. It reuses:

- v0.1.1 strict unified-diff parsing, artifact/log integrity, scope, and provenance checks;
- v0.2.0 added-line substring semantics;

and adds only the required removed-line substring observation.

Historical meanings remain distinct:

```text
v0.2 / verifier 0.1.1 = exact full added lines
v0.3 / verifier 0.2.0 = added-line substrings
v0.4 / verifier 0.3.0 = added-line + removed-line substrings
```

## Calibration fixtures

A small deterministic fixture is used instead of rewriting the burned benchmark:

Correct replacement:

```text
-unsafe_call(args.value)
+safe_call(args.value)
```

Goodhart decoy:

```text
 unsafe_call(args.value)
+<!-- safe_call( -->
```

The same correct patch is evaluated through v0.2, v0.3, and v0.4. The decoy is evaluated through v0.3 and v0.4.

Expected matrix:

```text
correct: v0.2 reject, v0.3 support, v0.4 support
decoy:   v0.3 support, v0.4 reject
```

This preserves the historical v0.3 weakness as evidence rather than hiding it.

## Files introduced/changed

- `schemas/evaluator-plan-v0.4.schema.json`
- `experiments/transition_patch_verifier.py`
- `experiments/evaluator_plan_runner.py` — canonical v0.4 routing only; v0.1–v0.3 meanings remain available
- `verification/fixtures/patch-transition-evaluator-plan-v0.4.json`
- `verification/fixtures/patch-transition/correct.patch`
- `verification/fixtures/patch-transition/decoy.patch`
- `tests/test_patch_evaluator_transition_v04.py`
- `.github/workflows/phase0-schema-check.yml`
- `docs/specifications/EVALUATOR_PLAN_V0_4_TRANSITION_SEMANTICS.md`

## Evidence-strength boundary

Added+removed substring checks are stronger than added presence alone but are still static proxies.

They do not prove behavioral correctness or security. When a stronger behavioral/negative evaluator is warranted, it should be separately versioned, sandboxed, provenance-bound, and frozen before outcomes. Candidate code remains unexecuted by the v0.4 metadata-only backend.

## Authority boundary

This work grants no canonical-write, push, approval, merge, candidate-selection, or project-spending authority.

The change is intended to remain a reviewable pull request. The original Phase B2 first-five cohort and frozen evaluator plans remain untouched.
