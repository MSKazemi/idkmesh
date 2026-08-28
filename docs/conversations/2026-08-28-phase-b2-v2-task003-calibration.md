# 2026-08-28 — continue: calibrate branch unobserved-head evidence

## Maintainer direction

Continue improving the repository and do something concretely useful.

## Chosen next step

The repository had one intentionally blocked open PR (#159) requiring genuinely
independent human review. Rather than bypass that gate or create another broad
controller, the next unblocked high-value task was selected from issue #180:
calibrate Phase B2 successor-v2 Task 003.

Task 003 is directly relevant to the repository's current branch-convergence
problem. Its frozen objective is to ensure that historical merged-PR evidence
cannot classify a branch as integrated/cleanup-ready when the branch's current
head SHA was not observed.

## Why calibration before publishing the fix

The successor-v2 scaffold is deliberately pre-outcome. Publishing the canonical
fix first would contaminate the task before its provisional evaluator had been
calibrated. Therefore this iteration adds only evaluator-owned calibration
machinery against immutable source `a69aa0ae...`.

The calibration constructs:

1. a straightforward transition that requires `head_sha is not None` before an
   exact merged-PR head can match; and
2. an inert lexical decoy that mentions the required text but preserves the
   vulnerable condition.

The canonical EvaluatorPlan v0.4 must accept the first and reject the second.
A separate behavioral matrix must also prove that:

- missing current head -> fail closed / not cleanup eligible;
- exact reviewed current head -> integrated-via-pr / cleanup eligible;
- moved current head -> post-merge-branch-moved / not cleanup eligible.

## Scientific boundary

This is calibration evidence, not a benchmark outcome and not a production
patch. The successor-v2 scaffold remains unfrozen, task evidence stays pending,
and a fresh novelty audit is still required before any future freeze.

## Authority boundary

The workflow uses read-only GitHub permissions, no secrets, no persisted checkout
credentials, and no push/approval/merge/automatic-selection authority. Candidate
code execution occurs only in a disposable evaluator-owned calibration checkout;
the canonical v0.4 verifier remains metadata-only.

Related: #127, #180, PR #186, PR #189.
