# Project Turn: Phase B2 evaluator-freeze audit and v2 benchmark commitment

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

> **Historical/supersession note:** this record preserves the reasoning from pre-v0.3 PR #163. Its anti-Goodhart conclusion remains valid, but its proposed v2 freeze using EvaluatorPlan v0.2 exact-line predicates was superseded before integration by issue #157 and merged PR #164, which introduced an explicit versioned v0.3 substring semantic contract. PR #163 was therefore closed unmerged; any successor cohort must be committed only after the new semantic contract/calibration matrix is green.

## Why the original cohort was burned

The frozen Phase B2 v1 cohort had definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

Several EvaluatorPlan v0.2 files encoded semantic fragments such as:

`resolve_repo_file(args.cohort`

while deterministic patch verifier v0.1.1 interprets `required_added_text` as exact equality against complete added hunk lines. Task 001's natural correct solution therefore passed its real path-boundary objective but was rejected by the frozen evaluator.

The correct response was not to edit the frozen plan after seeing the outcome. The cohort was retained as burned/diagnostic evidence, the real solution remained public, and later calibration also demonstrated that the old proxy could be gamed by inert exact-line text.

## Pre-v0.3 successor idea captured by PR #163

Before the explicit semantic version boundary landed, PR #163 proposed a fresh `phase-b2-first-five-v2` cohort with:

1. a new negative-evidence-type-boundary bug-fix WorkUnit;
2. the outcome-unseen original tasks 2–5;
3. new EvaluatorPlans using complete natural added-line predicates;
4. all evidence pending at freeze time;
5. no candidate generation, selection, push, merge, or canonical-write authority.

That proposal was intentionally pre-outcome and preserved the v1 burn. However, it still used EvaluatorPlan v0.2 / deterministic patch verifier v0.1.1 exact-line semantics.

## Why #163 was not integrated

Issue #157 made a stronger requirement after the calibration evidence:

- historical v0.2 / verifier 0.1.1 semantics must remain unchanged;
- semantic matching must become an explicitly versioned contract;
- legitimate and adversarial candidates must be distinguished in calibration;
- a successor cohort may be frozen only after that versioned contract and calibration matrix are green.

PR #164 subsequently merged EvaluatorPlan v0.3 / verifier 0.2.0 with explicit `required_added_substrings` semantics while retaining v0.2 behavior unchanged. Exact-head Evaluator Plan Binding, Phase 0, and Evolution checks were green for #164.

Therefore PR #163 became a stale pre-semantic-boundary freeze and was closed rather than rebased or silently translated.

## Durable rule

```text
observed evaluator defect
 -> preserve frozen cohort + outcome
 -> version semantics explicitly
 -> calibrate legitimate and adversarial examples
 -> only then freeze a new pre-outcome cohort
```

A benchmark definition is evidence only if its semantics were fixed before candidate outcomes. Repository activity or implementation convenience does not justify changing a frozen evaluator after seeing the answer.
