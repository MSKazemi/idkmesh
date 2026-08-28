# Phase B2 successor five-task benchmark

This directory is the first **fresh successor freeze** after the original `phase-b2-first-five` cohort was burned for an evaluator-contract defect.

## Pre-outcome commitment

- cohort id: `benchmark/phase-b2-successor-five`
- definition digest: `sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`
- stage: `frozen`
- evidence at freeze: **all five tasks pending**
- automatic candidate selection: disabled
- canonical write / push / merge authority: disabled

Do not edit evaluator commitments after observing candidate outcomes. If a new definition defect appears, burn/supersede the affected commitment rather than tuning it to the observed solution.

## Relationship to the burned cohort

The known Task 001 path-boundary problem is **not** reused as held-out evidence. It remains public post-burn calibration evidence for EvaluatorPlan v0.4.

Tasks 2–5 reuse only their original **outcome-unseen WorkUnits and immutable source snapshot** from the burned cohort. Their burned evaluator plans are not reused. New v0.3/v0.4 EvaluatorPlans are committed here before candidate generation.

Task 001 is a fresh bug against source revision `a69aa0ae1ae4862e507511cbd9ad854237d0ad32`: canonical finding categories must not become verified from opaque negative evidence after only a digest check.

## Evidence hierarchy

The public patch plans are bounded structural signals:

- v0.3: required added-line substring evidence;
- v0.4: required added + removed transition evidence.

Neither is a universal correctness oracle. Every task declares a seeded-negative or behavioral gate, and final cohort inclusion requires that stronger evidence to be independently verified.

## First five

1. fresh bug fix — negative-evidence type/category boundary;
2. test failure — frozen cohort without `definition_digest` must fail closed;
3. bounded feature — render the pre-outcome definition projection without outcome fields;
4. refactor — one repository-bounded cohort loader shared by validation/digest commands;
5. documentation contract — explicit freeze checklist without granting integration authority.

## Validate the freeze

```bash
python tools/benchmark_cohort.py validate \
  --cohort benchmarks/phase-b2-successor-five/cohort.json
```

Do not use `--require-evidence` until all five items have analyzed attempts plus verified seeded-negative evidence.
