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

## Observed calibration result

The first exact calibration head passed in GitHub Actions:

- run `33201309072`;
- job `98951164080`;
- artifact `9697855139`;
- artifact ZIP digest `sha256:9212f58c076324cb9aa6659c1c5cd54f9c61746d1de51647bc3f5576cf972136`.

Straightforward candidate:

- metadata verification: `passed`;
- recommendation: `accept_candidate`;
- required added transition: `1/1`;
- required removed transition: `1/1`;
- behavioral matrix: `safe_unobserved_head_matrix_passed=true`;
- ResultManifest digest: `sha256:b5c2ce3beba36f4a6d8ed45497f1384063a542dbedf0153718f38f165c7ea5d3`;
- VerificationResult digest: `sha256:1ec0fa91f62a3bc86c2562919b2790eae057dbb749994037d72b857f89c3a078`.

Inert lexical decoy:

- metadata verification: `failed`;
- recommendation: `reject_candidate`;
- required added transition: `1/1`;
- required removed transition: `0/1`;
- behavioral matrix confirms the vulnerable missing-head behavior remains;
- ResultManifest digest: `sha256:1fbd1a3bb430bb7e2ba90f9869ef175a67a6dfbf1779a0fcb0026d14c7215a77`;
- VerificationResult digest: `sha256:7bb19325c1ed6c10f3a6b54e1f972145aff600e077aacc619a5e3c7a240df796`.

The workflow also confirmed that calibration candidates are not benchmark
outcomes, the canonical verifier remains metadata-only, and no candidate has
canonical-write, push, merge, or automatic-selection authority.

## Evidence registration separation

A temporary same-PR scaffold-state update was deliberately removed. PR #198 is
kept as calibration machinery/evidence only, and the scaffold file is restored
byte-for-byte from `main`. If #198 lands unchanged, calibration registration
should be a separate small current-main PR that adds the run/artifact receipt,
removes only Task 003 from `calibration_pending_task_ids`, keeps
`freeze_ready=false`, and leaves actual Task 003 benchmark evidence pending.

This avoids coupling evidence generation to evidence registration and prevents a
fast-moving `main` from being overwritten by a stale scaffold snapshot.

## Scientific boundary

This is calibration evidence, not a benchmark outcome and not a production
patch. The successor-v2 scaffold remains unfrozen, task evidence stays pending,
and a fresh novelty audit is still required before any future freeze.

## Authority boundary

The workflow uses read-only GitHub permissions, no secrets, no persisted checkout
credentials, and no push/approval/merge/automatic-selection authority. Candidate
code execution occurs only in a disposable evaluator-owned calibration checkout;
the canonical v0.4 verifier remains metadata-only.

Related: #127, #180, PR #186, PR #189, PR #198.
