# Phase B2 first-five benchmark cohort

This directory instantiates the first real five-task repository benchmark requested by issue #5 using the canonical Benchmark Cohort v0.1 index.

## Frozen definition

- source repository: `https://github.com/MSKazemi/idkmesh`
- immutable source revision: `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`
- lifecycle stage: `frozen`
- task count: `5`
- pre-outcome definition digest: `sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`
- current evidence state: all tasks `pending`

Freezing commits the task taxonomy, source revision, WorkUnit/evaluator digests, negative expectations, accounting requirements, and structural-signature taxonomy before candidate outcomes. It does **not** claim that any task has been solved or verified.

## Tasks

| Task | Family | Difficulty | Bounded target |
| --- | --- | --- | --- |
| `001-cohort-path-boundary` | bug fix | small | `tools/benchmark_cohort.py` |
| `002-frozen-definition-digest-test` | test failure | small | `tools/benchmark_cohort.py` |
| `003-definition-json-command` | bounded feature | small | `tools/benchmark_cohort.py` |
| `004-safe-cohort-loader-refactor` | refactor | small | `tools/benchmark_cohort.py` |
| `005-first-five-freeze-checklist` | documentation contract | trivial | `docs/specifications/BENCHMARK_COHORT_V0_1.md` |

The first two tasks are grounded in current-main gaps observed before the cohort was frozen: the CLI accepts a directly resolved `--cohort` path instead of the repository-bounded resolver used for referenced artifacts, and the self-test does not explicitly pin the frozen-without-`definition_digest` failure mode.

## Prospective structural signatures

Each task predeclares the same initial structures so later experiments cannot rename the taxonomy after seeing outcomes:

- `single-worker-baseline-v1`
- `two-independent-attempts-v1`
- `role-specialized-two-attempts-v1`

These labels define experiment structure, not model quality or expected winners.

## Verification boundary

Each task has:

- a WorkUnit v0.2 bound to the immutable source SHA;
- a public EvaluatorPlan v0.2 bound to the exact WorkUnit canonical digest;
- a seeded negative expectation;
- wall-time and human-attention accounting requirements;
- zero project spend;
- no canonical write, push, merge, or automatic candidate-selection authority.

The bootstrap evaluator is the existing metadata-only `unified_diff` backend. It validates patch/log provenance, WorkUnit path scope, and predeclared verifier-owned added-text expectations. It does not execute candidate code and should not be mistaken for a universal semantic code reviewer.

## Validate the frozen definition

```bash
python tools/benchmark_cohort.py validate \
  --cohort benchmarks/phase-b2-first-five/cohort.json
```

The dedicated read-only CI runs the same validation. `--require-evidence` is intentionally not used yet because outcomes and seeded-negative evidence are still pending.

## Next evidence step

For each task, generate attempts using the predeclared structural signatures, produce canonical ResultManifest objects, verify them independently through the bound evaluator, retain a meaningful negative case, and attach evidence without changing the pre-outcome definition digest.

Only after evidence is complete should the cohort be used for claims about agent diversity, verification cost, or collective scaling. Five tasks are an engineering bootstrap cohort, not a statistical-power claim.
