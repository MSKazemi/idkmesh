# Project Turn: Extract Task 001 calibration onto canonical EvaluatorPlan v0.4

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Convergence discovered during continuation

The repository moved repeatedly while the Phase B2 calibration path was being prepared.

First, EvaluatorPlan v0.3 and benchmark-cohort schema-version routing landed. Before a v0.3-only calibration branch was opened, current `main` advanced again with PR #171 / merge `c60549c43232231c724fe3aaaac1f08a26998cbe`, establishing the canonical EvaluatorPlan v0.4 / verifier `0.3.0` transition contract:

```text
required added substring
+
required removed substring
```

This directly addresses the historical Goodhart failure where an inert added mention could satisfy an added-presence proxy while leaving the unsafe mechanism unchanged.

Closed PR #170 had independently developed a Task 001 correct-vs-decoy calibration surface. Its first behavioral attempt failed, then its latest head `67e4af4716584a0da051c9a400951a35e8f153b0` produced a green calibration run `33194220134`. Maintainer comments nevertheless correctly kept #170 closed because that branch also contained a divergent second verifier implementation.

The maintainer convergence instruction was explicit: preserve the successful calibration evidence, but extract **only** the Task 001 behavioral/adversarial calibration onto current `main`, invoking the canonical #171 implementation.

## Action in this turn

A fresh branch was created from current `main`:

`fix/task001-canonical-v04-calibration`

It adds only:

- `verification/fixtures/task001-transformation-calibration-evaluator-plan-v0.4.json`;
- `tools/task001_evaluator_calibration_v04.py`;
- `tools/task001_evaluator_calibration_v04_ci.py`;
- `.github/workflows/task001-canonical-v04-calibration.yml`;
- this archive.

It does **not** add or modify another verifier implementation.

The workflow compiles and invokes the canonical files already merged by #171:

- `experiments/evaluator_plan_runner.py`;
- `experiments/transition_patch_verifier.py`;
- `schemas/evaluator-plan-v0.4.schema.json`.

## Calibration matrix

Frozen public source:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`

Burned Task 001 WorkUnit:

`benchmark/phase-b2/001-cohort-path-boundary`

Burned cohort definition digest remains:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

The calibration generates two post-burn candidates from the exact frozen source:

1. **straightforward transformation**
   - removes both vulnerable `(ROOT / args.cohort).resolve()` loaders;
   - adds the repository-bounded `resolve_repo_file(args.cohort, label="BenchmarkCohort")` loader;
   - expected canonical v0.4 result: `passed / accept_candidate`;
   - separate behavioral matrix must reject absolute and traversal cohort paths as `unsafe path`.

2. **inert decoy**
   - leaves both vulnerable loaders unchanged;
   - appends only inert multiline-string text containing the historical resolver fragment;
   - expected canonical v0.4 result: `failed / reject_candidate` because the required unsafe-loader removal is absent;
   - separate behavioral matrix must demonstrate the absolute/traversal bypass remains accepted.

## Evidence-strength boundary

EvaluatorPlan v0.4 is still metadata-only and does not execute candidate code. Its added+removed transition evidence is stronger than added-presence alone but remains a static proxy.

The path-boundary behavioral execution is therefore kept as a separate, explicit calibration channel over fixed post-burn candidates and an immutable public source checkout.

Neither channel alone receives integration authority.

## Authority and scientific boundaries

This work:

- does not change the burned WorkUnit or old EvaluatorPlans;
- does not change the original definition digest;
- does not create successor benchmark outcomes;
- does not automatically select candidates;
- does not write canonical repository state from CI;
- does not push, approve, or merge pull requests;
- does not use secrets or project-paid compute authority;
- does not reinterpret historical v0.2/v0.3 semantics.

## Next gate

Open the extraction as a small current-main PR. The exact-head workflow must prove:

```text
straightforward: v0.4 support + behavioral boundary fixed
decoy:           v0.4 reject  + vulnerable behavior retained
```

If that matrix is green under the canonical #171 implementation, issue #157's remaining Task 001 calibration requirement can be evaluated for completion. Only after that should a fresh successor Phase B2 cohort be frozen before any new candidate outcomes.
