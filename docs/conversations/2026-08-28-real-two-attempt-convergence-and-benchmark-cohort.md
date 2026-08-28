# Project Turn: Real two-attempt convergence and benchmark cohort contract

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User message

> Okay, go ahead and continue.

## Live repository reassessment

This turn began by checking the current repository state rather than assuming the previous controlled-Docker gate was still open.

The critical path had advanced:

- issue #37 had completed controlled Docker acceptance for the exact canonical node candidate;
- PR #113 had already demonstrated one fresh real node bundle flowing into a verifier-owned EvaluatorPlan and independent VerificationResult;
- issue #5 therefore identified a **real multi-attempt run + combined Evidence Report/replay** as its next dependency before building the first benchmark cohort.

The first implementation target was consequently the same task through two real worker attempts rather than another verifier protocol.

## Independent real two-attempt implementation

A branch and PR #118 were built to compose existing canonical pieces:

```text
exact accepted node SHA
 -> real attempt 1 -> independent VerificationResult
 -> real attempt 2 -> independent VerificationResult
 -> existing idkmesh-two-attempt-run shape
 -> existing non-selecting Evidence Report
 -> replay report from saved run metadata
```

PR #118 introduced no new worker/verifier/result protocol. Its real GitHub Docker workflow ran successfully on head:

`8f86355f7822935e9f7bf29d3a6dab0ad57ddc97`

Workflow run:

`33187069657`

Job:

`98902714723`

The job passed all real-runtime steps:

- exact worker SHA check;
- accepted Docker image preload;
- real node attempt 1;
- independent verification of attempt 1;
- real node attempt 2;
- independent verification of attempt 2;
- canonical run-record composition;
- non-selecting Evidence Report generation;
- report replay from saved run metadata;
- assertions that both candidates remained visible and no automatic selection/write/merge authority appeared.

## Convergence with concurrent PR #117

Before PR #118 could be merged, `main` advanced with PR #117:

**Prove real two-attempt node evidence and fault isolation**

merge commit:

`35f427359b3bf38419c6028ac9d24a08e68269d4`

PR #117 proved the same core real two-attempt path and additionally exercised a **real worker process error** while preserving the independently verified peer attempt in the combined run/report.

Therefore PR #118 was deliberately **not merged**. It was closed as successful corroborating evidence because merging a parallel integration bridge/workflow would create duplicate canonical surfaces.

This is repository convergence, not experiment failure.

## Issue synchronization

Issues #4, #5, and #16 were updated with the merged PR #117 evidence and PR #118 corroboration.

The important state transition is:

```text
single real attempt proof       -> complete
real two-attempt proof          -> complete
real worker fault isolation     -> complete
combined non-selecting report   -> complete
saved-run report replay         -> complete
first small benchmark cohort    -> now unblocked
```

PR #91 remains separately human/reviewer-gated. The real evidence loops intentionally use its exact accepted SHA without claiming that this separate review gate is satisfied.

## Benchmark infrastructure gap

The repository tree was then inspected for a reusable benchmark-corpus contract.

Existing components include:

- generic ExperimentManifest v0.1;
- synthetic research benchmark harnesses;
- WorkUnit v0.2;
- EvaluatorPlan v0.2;
- ResultManifest v0.1;
- VerificationResult v0.1;
- run Evidence Report v0.1.

There was no general index representing:

- task family/difficulty/split;
- exact frozen source snapshot;
- WorkUnit digest;
- evaluator commitment;
- predeclared structural signatures;
- seeded-negative expectation;
- attached real attempts;
- resource/human-attention accounting requirements;
- exclusion state;
- a frozen pre-outcome definition digest.

ExperimentManifest should not be overloaded to carry these semantics because it answers a different question: experiment hypotheses/configurations/repetitions rather than corpus membership and evidence binding.

## New contract: Benchmark Cohort Index v0.1

A new branch was created from the merged real two-attempt baseline:

`feature/benchmark-cohort-contract-v1`

The branch adds:

- `schemas/benchmark-cohort-v0.1.schema.json`;
- `tools/benchmark_cohort.py`;
- `.github/workflows/benchmark-cohort-contract.yml`;
- `docs/specifications/BENCHMARK_COHORT_V0_1.md`;
- this conversation archive.

The cohort contract is deliberately a **thin index**, not a new task or verification protocol.

## Pre-Outcome Definition Commitment

The main new idea is a content commitment over the benchmark definition before analyzed outcomes are attached.

The definition projection commits:

```text
cohort identity
+ required families / minimum target size
+ task family / difficulty / split
+ immutable source snapshot
+ WorkUnit id/version/digest
+ EvaluatorPlan visibility/id/digest/backend
+ predeclared structural signatures
+ seeded-negative expectation
+ accounting requirements
+ no-auto-authority policy
```

Then:

```text
D_definition = SHA256(canonical(pre_outcome_definition))
```

Evidence/result paths and outcomes are excluded from this projection.

Therefore adding later ResultManifest/VerificationResult evidence should not change the definition digest, while changing task labels, source revision, WorkUnit, evaluator, negative expectation, or structural-signature taxonomy must change it.

This is intended to reduce post-outcome relabeling, evaluator drift, and benchmark overfitting/Goodhart pressure.

The digest proves content identity, not chronology by itself. Git history, PR review, signatures, or a future transparency log are needed to prove that the commitment existed before final outcomes were inspected.

## Cross-object validation

`tools/benchmark_cohort.py` validates the cohort schema plus canonical referenced objects.

For public evaluator plans it checks:

- WorkUnit v0.2 schema and canonical digest/id/version;
- source-revision alignment;
- EvaluatorPlan v0.2 schema;
- exact plan digest/id/backend;
- exact WorkUnit/source binding;
- exact required-validator set.

For verified attempts it additionally checks:

- ResultManifest v0.1 and VerificationResult v0.1 schemas;
- exact ResultManifest -> WorkUnit binding;
- exact VerificationResult -> ResultManifest binding;
- exact VerificationResult -> WorkUnit/source binding;
- exact verifier-config digest -> indexed EvaluatorPlan digest;
- independent-from-worker truth;
- outcome/recommendation consistency;
- predeclared structural signature;
- required accounting fields.

Hidden evaluators expose only a digest/id/backend commitment; their plan path is forbidden from the public index. A later VerificationResult must still bind to the hidden plan digest.

## Seeded-negative rule

Every task defines a meaningful negative expectation before final evidence, such as:

- correctness failure;
- forbidden scope;
- forged provenance;
- security regression;
- worker error.

With `--require-evidence`, an included task must have analyzed real attempts plus verified negative evidence. Excluded tasks retain explicit exclusion reasons rather than disappearing from the corpus.

## First cohort direction

The first Phase B2 cohort remains intentionally small: 5–10 repository-level tasks across bug fix, test/failure reproduction, bounded feature, refactor/code consistency, and documentation/code-contract work.

That number is an engineering bootstrap target, not a statistical-power claim.

The same cohort index is designed to scale into:

- #70 / #30 real replication-vs-diversity research;
- #96 future real train/development/held-out orchestration evolution;
- #14 real verifier-cost/backlog measurements.

The immediate next gate is CI/review of the cohort contract. After that, the project should instantiate the first real tasks rather than adding more synthetic infrastructure.
