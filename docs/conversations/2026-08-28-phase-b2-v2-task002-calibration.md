# 2026-08-28 — continue: calibrate non-finite free-compute routing

## Maintainer direction

Continue improving the repository and do something useful.

## Current state observed

At the start of this iteration the successor-v2 calibration ledger had two completed tasks (003 and 005) and three pending tasks (001, 002, 004). Current `main` still contained the original Task 002 source behavior, and repository PR search found no published Task 002 implementation.

## Chosen next step

Task 002 was selected because it protects the free-compute/resource-broker boundary. The frozen router uses Python `json.loads` and floating-point comparisons without an explicit finite-number gate. Python accepts `NaN` and Infinity tokens, and some JSON Schema numeric comparisons do not reject every non-finite value.

This can permit malformed numeric inputs to reach:

- repository/project spend-limit comparisons;
- offer eligibility;
- success-probability ranking;
- wait-time ranking;
- selected-offer JSON output.

## Calibration approach

The iteration adds evaluator-owned calibration machinery only. It does not publish the production Task 002 repair.

Two disposable candidates are constructed against exact source `a69aa0ae1ae4862e507511cbd9ad854237d0ad32`:

1. straightforward — recursively reject every non-finite float with `isfinite` immediately after JSON parsing;
2. inert decoy — add the lexical `isfinite` marker while preserving the vulnerable direct `json.loads` return.

The canonical EvaluatorPlan v0.4 must accept the first and reject the second.

A separate CLI behavioral matrix checks finite control routing plus NaN/+Infinity/-Infinity across WorkUnit budget, repository policy ceiling, offer project cost, offer success probability, and offer wait time.

## Important negative behavior

The calibration explicitly tests the dangerous case where an otherwise eligible zero-cost offer has `project_cost_usd = NaN`. In the vulnerable source, the cost comparison against NaN can evaluate false, the offer can remain selected, and `json.dumps` can emit a literal `NaN`, creating non-standard JSON evidence.

## Observed exact-source evidence

PR #207 initial calibration head `348efd9268c9e87aa5cff59cafff9969199de99a` ran successfully.

GitHub Actions:

- run `33203450690`;
- job `98958413889`;
- artifact `9698681251`;
- artifact ZIP SHA-256 `89b4af66402c4481a48603b4151db3d9942d4da450716002304d566a719d5d92`.

Straightforward candidate:

- canonical v0.4 verification: `passed`;
- decision support: `accept_candidate`;
- matched added transition: 1/1;
- matched removed transition: 1/1;
- behavioral result: `safe_nonfinite_matrix_passed=true`;
- ResultManifest digest: `sha256:9e2f20ceeb0367fae602b0795b6960f16071074798fa894c259e8dd856e7464c`;
- VerificationResult digest: `sha256:7f041b83cac9800ee9f05091d89a114e9a8cca6de16c8f090d9acae7aaadb6a5`.

Inert lexical decoy:

- canonical v0.4 verification: `failed`;
- decision support: `reject_candidate`;
- matched added transition: 1/1;
- matched removed transition: 0/1;
- behavioral result: `vulnerable_nonfinite_values_reach_routing=true`;
- ResultManifest digest: `sha256:c84c308cdc8503d819d6eb4522c2a47d81f2219edbe358c5a0fe48f1655d989b`;
- VerificationResult digest: `sha256:49c9af54233776502382800d36b23dd122b671f6e376ded644ccebeacdf2e1fc`.

The calibration therefore distinguished the real finite-number transition from a Goodhart-style lexical decoy while separately reproducing the unsafe non-finite routing behavior.

## Integration decision

As with Task 003, calibration machinery and calibration-ledger mutation are kept separate. PR #207 should land only the reusable calibration workflow/harness/documentation. After its final head is green, a second current-main PR may register the exact calibration receipt in `benchmarks/phase-b2-successor-v2/cohort.json`, remove only Task 002 from `calibration_pending_task_ids`, and keep `freeze_ready=false`.

## Scientific boundary

This is evaluator calibration before freeze, not a scored benchmark outcome. The successor remains `stage=scaffold`, Task 002 outcome evidence remains pending, and a fresh novelty audit is still required before any future freeze.

## Authority boundary

The workflow is read-only with respect to repository state: `contents: read`, no secrets, no persisted checkout credentials, no push/approval/merge/settings authority, no project spend, and no automatic candidate selection. Candidate execution occurs only in a disposable exact-source checkout.

Related: #180, PR #186, PR #198, PR #201, PR #207.
