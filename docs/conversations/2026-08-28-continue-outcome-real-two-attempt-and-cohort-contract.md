# Continuation outcome: real multi-attempt convergence and benchmark cohort contract

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User request

> Okay, go ahead and continue.

## Completed outcomes

### 1. Reassessed the live critical path

The prior controlled-Docker gate was no longer the bottleneck. Issue #37 had completed and PR #113 had already demonstrated one fresh real node bundle flowing through the current independent verifier.

The next dependency was the real two-attempt product evidence loop.

### 2. Built and ran an independent real two-attempt proof

PR #118 was implemented and its real GitHub Docker workflow succeeded on exact head:

`8f86355f7822935e9f7bf29d3a6dab0ad57ddc97`

Workflow:

`33187069657`

Job:

`98902714723`

It proved:

- two real executions of the exact accepted node SHA;
- one independently bound VerificationResult per attempt;
- existing two-attempt run-record composition;
- existing non-selecting Evidence Report generation;
- deterministic report reconstruction from saved run metadata;
- no automatic candidate selection or merge authority;
- human integration decision remained pending.

Before #118 merged, concurrent PR #117 landed the same core evidence plus a real worker-error fault-isolation scenario. Therefore #118 was closed as successful corroborating evidence instead of duplicating the stronger canonical surface.

PR #117 merge:

`35f427359b3bf38419c6028ac9d24a08e68269d4`

### 3. Updated the real-orchestration trackers

Issues #4, #5, and #16 were updated with the merged #117 evidence and the independent #118 corroboration.

The real two-attempt + combined Evidence Report dependency is now complete at the current exact-SHA experiment boundary.

PR #91 remains separately human/reviewer-gated; none of this work claims that independent human review has occurred.

### 4. Identified the next missing infrastructure

After real multi-attempt evidence landed, issue #5's next concrete dependency became the first 5–10 task benchmark cohort.

The repository had canonical WorkUnit, EvaluatorPlan, ResultManifest, VerificationResult, ExperimentManifest, and run Evidence Report contracts, but no reusable benchmark-corpus index that could freeze:

- immutable task source;
- family/difficulty/split;
- WorkUnit digest;
- evaluator commitment;
- seeded-negative expectation;
- structural-signature taxonomy;
- evidence/exclusion state;
- accounting requirements;
- pre-outcome benchmark definition.

ExperimentManifest was intentionally not overloaded with these semantics.

### 5. Implemented Benchmark Cohort v0.1

PR #126 added:

- `schemas/benchmark-cohort-v0.1.schema.json`;
- `tools/benchmark_cohort.py`;
- `.github/workflows/benchmark-cohort-contract.yml`;
- `docs/specifications/BENCHMARK_COHORT_V0_1.md`;
- the detailed project-turn archive.

The main new mechanism is **Pre-Outcome Definition Commitment**:

```text
D_definition = SHA256(canonical(pre_outcome_definition))
```

The definition commits task source/taxonomy/split, WorkUnit, evaluator digest, seeded-negative expectation, accounting requirements, structural signatures, and no-auto-authority policy while excluding later ResultManifest/VerificationResult outcomes.

Attaching results should not change the definition digest. Changing the benchmark after seeing outcomes must change it.

The digest proves content identity, not chronology by itself; Git/PR/signature/transparency history remains necessary to establish when the commitment was published.

### 6. Cross-object benchmark validation

The validator fails closed on, among other conditions:

- WorkUnit digest/id/version/source drift;
- public EvaluatorPlan digest/id/backend/binding drift;
- required-validator mismatch;
- ResultManifest/VerificationResult provenance mismatch;
- verifier-config digest mismatch;
- non-independent analyzed verification;
- recommendation/outcome mismatch;
- undeclared structural signatures;
- duplicate source-revision/WorkUnit benchmark entries;
- missing required accounting metrics;
- incomplete seeded-negative evidence under `--require-evidence`;
- insufficient task count/family coverage for frozen or burned cohorts.

Hidden evaluators may expose only a commitment digest/id/backend; their plan path is forbidden from the public index and later VerificationResults must bind to the hidden plan digest.

### 7. CI and merge evidence

Benchmark Cohort Contract workflow:

- run `33187715869`;
- job `98904936488`;
- compile step passed;
- deterministic cross-object/self-test passed.

Phase 0 schema and Evolution Loop checks also passed on the PR head.

PR #126 was squash-merged as:

`8dea3769ce07693562bdbacc661bc9feaa271d97`

### 8. Research/project synchronization

Issue #5 was updated to record that the corpus-format/anti-drift blocker is removed but the 5–10 real tasks do **not** exist yet.

Issue #70 was updated to explain that BenchmarkCohort v0.1 is reusable real-corpus infrastructure, not real R1 evidence. Its larger held-out real coding corpus, equal attempt budgets, and measured diversity outcomes remain future work.

## Next concrete implementation

The next internal benchmark step is now:

```text
instantiate 5–10 real bounded task definitions
 -> cover bug_fix / test_failure / bounded_feature / refactor / documentation_contract
 -> bind immutable source + WorkUnit + EvaluatorPlan
 -> predeclare structural signatures + negative expectations
 -> publish/freeze definition digest before final outcomes
 -> generate candidates
 -> independently verify candidates and negatives
 -> retain failures/exclusions
 -> validate with --require-evidence
```

This is an engineering bootstrap cohort, not a claim of statistical power. Larger research corpora such as #70 should reuse the same index and increase sample size under a preregistered experiment protocol.
