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

## Scientific boundary

This is evaluator calibration before freeze, not a scored benchmark outcome. The successor remains `stage=scaffold`, Task 002 outcome evidence remains pending, and a fresh novelty audit is still required before any future freeze.

## Authority boundary

The workflow is read-only with respect to repository state: `contents: read`, no secrets, no persisted checkout credentials, no push/approval/merge/settings authority, no project spend, and no automatic candidate selection. Candidate execution occurs only in a disposable exact-source checkout.

Related: #180, PR #186, PR #198, PR #201.
