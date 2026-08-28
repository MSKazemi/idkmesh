# Benchmark Cohort Index v0.1

Status: experimental Phase B2 contract  
Tracker: #5  
Related research: #30, #70, #96

## Purpose

IDKMesh now has real evidence for:

```text
WorkUnit
 -> exact-SHA real worker
 -> ResultManifest
 -> verifier-owned EvaluatorPlan
 -> independent VerificationResult
 -> multi-attempt run record
 -> non-selecting Evidence Report
```

The next problem is no longer how to represent one task or one verification result. It is how to assemble a **small, frozen, replayable benchmark cohort** without creating a second task protocol or changing task labels/evaluator expectations after outcomes are known.

`schemas/benchmark-cohort-v0.1.schema.json` is therefore a thin **index** over existing canonical objects.

It does not replace:

- WorkUnit v0.2;
- EvaluatorPlan v0.2;
- ResultManifest v0.1;
- VerificationResult v0.1;
- the run Evidence Report.

## Cohort lifecycle

A cohort moves through four explicit stages:

```text
scaffold -> collecting -> frozen -> burned
```

### `scaffold`

Contract/design work. References may use repository fixtures. It is not real benchmark evidence.

### `collecting`

Real task acquisition has begun. Every indexed source revision must be a full immutable 40-hex Git commit. Task taxonomy and evaluator commitments should already be treated as prospective definitions rather than labels inferred from outcomes.

### `frozen`

The pre-outcome definition is committed, the cohort contains at least `minimum_final_tasks`, and every family listed in `required_families` is represented. A frozen cohort may still be waiting for candidate evidence; freezing means the **test definition** is fixed, not that the experiment is complete.

### `burned`

Final outcomes have been inspected. The cohort must no longer be described as untouched held-out evidence for later tuning.

## Pre-Outcome Definition Commitment

The central anti-Goodhart mechanism is the cohort `definition_digest`.

The validator canonicalizes a projection containing:

- cohort id/title;
- minimum target size;
- required task families;
- no-auto-authority policy;
- task id;
- task family and difficulty;
- split (`pilot`, `train`, `development`, `held_out`);
- immutable source repository/revision;
- WorkUnit id/version/digest;
- EvaluatorPlan visibility/id/digest/backend;
- predeclared structural signatures;
- seeded-negative description/category;
- required accounting metrics.

It deliberately excludes:

- lifecycle stage;
- ResultManifest / VerificationResult paths and outcomes;
- negative-evidence completion status;
- storage paths for WorkUnit/EvaluatorPlan;
- extensions.

Therefore:

```text
D_definition = SHA256(canonical(pre_outcome_definition))
```

and attaching results later should satisfy:

```text
D_definition(before outcomes) == D_definition(after outcomes)
```

while changing difficulty, family, split, source revision, WorkUnit digest, evaluator digest, negative expectation, accounting requirements, or structural-signature taxonomy changes the digest.

This digest is a **content commitment**, not a time machine. The validator cannot prove by itself that the digest was published before outcomes were inspected. Git history, pull-request review, signed attestations, or future transparency-log records provide the temporal provenance.

## Task families

The first repository cohort should intentionally cover several kinds of bounded work rather than many variants of one smoke patch:

- `bug_fix`;
- `test_failure`;
- `bounded_feature`;
- `refactor`;
- `documentation_contract`;
- `other` only when a task does not fit the first five.

Issue #5 currently targets 5–10 tasks for the first cohort. Larger research corpora such as #70 can reuse the same index and increase `minimum_final_tasks` rather than creating a new evidence format.

## Structural signatures

Each task declares `declared_structural_signatures` **before** analyzed attempts are attached.

An attempt may only use one of those declared signatures.

Examples of future structural signatures could encode a fixed worker/model/prompt/tool structure, a second model family, a different toolchain, or a different orchestration role. The cohort contract does not prescribe the taxonomy; it prevents the taxonomy from being silently rewritten after benchmark outcomes are known.

This is specifically intended to support #70/#30 comparisons between replication and structural diversity under equal attempt budgets.

## Evaluator sovereignty and hidden controls

A benchmark task stores an evaluator commitment:

```text
visibility
plan_id
plan_digest
backend
```

For a **public** evaluator, `plan_path` is required and `tools/benchmark_cohort.py` independently validates:

- EvaluatorPlan v0.2 schema;
- exact plan digest/id/backend;
- WorkUnit id/version/digest binding;
- source revision binding;
- exact required-validator coverage.

For a **hidden** evaluator, `plan_path` is forbidden. The public cohort retains only the cryptographic plan commitment and non-secret metadata. Later VerificationResults must still bind `provenance.verifier_config_digest` to that exact hidden-plan digest.

This permits held-out/hidden evaluator control without putting worker-visible hidden tests into the candidate workspace or public index.

## Evidence binding

For every `verified` attempt, the cross-object validator checks:

1. ResultManifest and VerificationResult schema validity;
2. indexed object ids and canonical SHA-256 digests;
3. exact ResultManifest -> WorkUnit id/version/digest/source binding;
4. required verifier request coverage;
5. exact VerificationResult -> ResultManifest binding;
6. exact VerificationResult -> WorkUnit/source binding;
7. exact `verifier_config_digest` -> indexed EvaluatorPlan digest;
8. `independent_from_worker == true`;
9. indexed outcome equals verifier recommendation;
10. structural signature was predeclared;
11. required resource/accounting fields are present in worker or verifier evidence.

The cohort never turns a worker self-report into correctness.

## Seeded-negative evidence

Every task defines one meaningful negative expectation before final evidence is considered, for example:

- semantically wrong but scope-valid patch -> `correctness`;
- forbidden-path change -> `scope`;
- forged artifact digest -> `provenance`;
- security regression -> `security`;
- worker process failure -> `worker_error`.

When `negative_case.evidence_status = verified`, the referenced evidence digest is checked. If it is a VerificationResult and the expected category maps to a canonical finding category, the validator additionally requires that finding and rejects an `accept_candidate` recommendation.

When `--require-evidence` is used, included benchmark tasks must have both real analyzed attempts and verified seeded-negative evidence. Excluded tasks retain an explicit exclusion reason instead of disappearing from the corpus.

## Duplicate protection

Within one cohort:

- task ids must be unique;
- attempt ids must be unique within a task;
- the same `(repository, revision, WorkUnit id, WorkUnit version)` cannot be counted twice as separate benchmark items.

This prevents easy inflation of task count by duplicating one frozen work item under multiple labels.

## Authority boundary

Every cohort must explicitly preserve:

```json
{
  "canonical_state_write": false,
  "git_push": false,
  "merge": false,
  "automatic_candidate_selection": false
}
```

A benchmark measures candidates. It does not grant integration authority.

## CLI

Validate a cohort and all currently attached evidence:

```bash
python tools/benchmark_cohort.py validate --cohort path/to/cohort.json
```

Require the cohort to contain no pending tasks and require verified seeded-negative evidence for every included task:

```bash
python tools/benchmark_cohort.py validate \
  --cohort path/to/cohort.json \
  --require-evidence
```

Calculate the pre-outcome commitment:

```bash
python tools/benchmark_cohort.py definition-digest \
  --cohort path/to/cohort.json
```

Run contract/drift tests without executing candidate code:

```bash
python tools/benchmark_cohort.py self-test
```

## What v0.1 intentionally does not do

This contract does not:

- generate benchmark tasks;
- execute workers;
- execute candidate code;
- implement hidden tests;
- decide a winner;
- merge a candidate;
- claim statistical power from five tasks;
- prove that a definition digest was published before results without external history/attestation;
- define the final structural-signature taxonomy for #70;
- replace ExperimentManifest for experiment-level hypotheses/configurations/repetitions.

ExperimentManifest and BenchmarkCohort answer different questions:

```text
ExperimentManifest: what experiment/configurations/metrics are being run?
BenchmarkCohort:     what frozen task/evaluator/evidence objects constitute the corpus?
```

## First real cohort next step

After this contract is reviewed and merged, Phase B2 should instantiate 5–10 real repository-level tasks across the first five task families, freeze their definition digest before final outcomes, generate equal-budget attempts, independently verify all included candidates, retain negative/failure evidence, and only then expand toward the larger #70 real coding corpus.
