# Conversation record: Phase B2 first-five benchmark

Date: 2026-08-28  
Repository: `MSKazemi/idkmesh`  
User direction: **Continue.**

## Context

The preceding project turn completed Phase 0: versioned WorkUnit / ExperimentManifest / ExperimentResult contracts, a safe deterministic harness, fixtures, and CI. The next stated engineering step was a small real software-engineering benchmark.

Before changing the repository, current state was re-evaluated because other project threads had advanced the codebase substantially.

Observed current state:

- issue #5 is the active P0 tracker for real node verification plus the first benchmark cohort;
- PR #116, EvaluatorPlan routing in the existing two-attempt orchestrator, is merged;
- PR #120, two real node attempts through independent verification/report/replay, was merged into current `main` while this turn was in progress;
- PR #126 already merged the reusable Benchmark Cohort v0.1 contract, cross-object validator, pre-outcome definition commitment, and read-only CI;
- therefore the next non-duplicative Phase B2 action is to instantiate the first five real repository tasks, not create another benchmark/evidence protocol.

The exact source snapshot frozen for the cohort is:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`

## Decision

Create a five-task **pilot** cohort across the five first-class task families required by the benchmark contract:

1. bug fix;
2. test failure;
3. bounded feature;
4. refactor;
5. documentation contract.

The cohort is frozen before candidate outcomes with:

`definition_digest = sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

Evidence is intentionally left `pending`. Freezing commits the prospective test definition; it does not invent outcomes.

## Two grounded gaps used as tasks

Inspection of `tools/benchmark_cohort.py` found two bounded current-main gaps suitable for the first cohort:

### Repository-boundary bug

`cmd_validate` and `cmd_definition_digest` load the user-provided cohort path via direct `Path.resolve()` instead of the repository-bounded `resolve_repo_file()` guard used for referenced artifacts. A caller can therefore point `--cohort` at an absolute/out-of-repository JSON path even though the CLI contract describes a repository-relative cohort path.

Task 001 freezes this as a bug-fix problem.

### Missing frozen-digest regression self-test

The BenchmarkCohort schema requires `definition_digest` when stage is `frozen`/`burned`, but the executable `benchmark_cohort.py self-test` does not explicitly pin the failure mode for a frozen cohort with the digest omitted.

Task 002 freezes this as a test/regression problem.

## Remaining task definitions

Task 003 asks for a read-only `definition-json` CLI view of the exact pre-outcome projection so reviewers can inspect what the digest commits to.

Task 004 asks for a shared safe cohort-argument loader to remove duplicated CLI loading logic while preserving repository-boundary behavior.

Task 005 asks for a compact First-five freeze checklist in the Benchmark Cohort specification.

These tasks are independent benchmark items evaluated against the same immutable source snapshot. They are not intended to be applied sequentially to one working tree.

## Structural-signature commitment

Before outcomes, every task declares the same initial experiment structures:

- `single-worker-baseline-v1`;
- `two-independent-attempts-v1`;
- `role-specialized-two-attempts-v1`.

This prevents structural-diversity labels from being rewritten after observed results.

## Authority and safety

The cohort preserves the existing project boundary:

```text
canonical_state_write = false
git_push = false
merge = false
automatic_candidate_selection = false
project_spend_usd_max = 0
```

The public bootstrap EvaluatorPlans use the existing metadata-only unified-diff backend. They do not execute candidate code. Evaluator support remains decision evidence, not integration authority.

The work is isolated on branch:

`benchmark/phase-b2-first-five`

and is intended to enter `main` only through the repository's normal PR/CI/review path.

## Files added or changed

- `benchmarks/phase-b2-first-five/cohort.json`
- `benchmarks/phase-b2-first-five/README.md`
- five WorkUnit v0.2 task definitions
- five public EvaluatorPlan v0.2 commitments
- `.github/workflows/benchmark-cohort-contract.yml` updated so the frozen cohort is validated by read-only CI
- this conversation record

## Next

Open the branch as a pull request tied to issue #5, confirm the Benchmark Cohort Contract workflow passes, and retain the cohort definition unchanged while candidate/negative evidence is generated in the next phase.
