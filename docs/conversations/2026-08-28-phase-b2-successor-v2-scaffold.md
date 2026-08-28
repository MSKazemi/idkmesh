# Conversation record — Phase B2 successor first-five v2 scaffold

Date: 2026-08-28

Repository: `MSKazemi/idkmesh`

## User direction

The user asked the project to continue development of the public IDKMesh repository.

## Starting state

The earlier Phase B2 first-five v1 pilot remains burned after its frozen evaluator was shown to be defective. Task 001 is already known and cannot be reused as untouched held-out evidence.

The evaluator stack has since advanced through explicit versioning and calibration:

- v0.2 / verifier 0.1.1 — exact added-line matching, preserved historically;
- v0.3 / verifier 0.2.0 — explicit added-line substring semantics;
- v0.4 / verifier 0.3.0 — explicit added + removed transition semantics;
- real frozen-source Task 001 calibration — straightforward repair supported, inert Goodhart decoy rejected, with separate behavioral boundary evidence;
- Benchmark Cohort routing — public EvaluatorPlan v0.4 supported fail-closed.

Issue #157 was therefore closed completed and the next dependency became a genuinely new successor benchmark definition.

## Successor tracker

Issue #180 was created:

`Phase B2 successor: calibrate and freeze first-five v2 cohort`

The issue fixes the candidate task source snapshot to:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

This source snapshot is intentionally older than later control-plane/scaffold commits. The task-under-test state and the benchmark-definition state are separate provenance roles.

## Five new task hypotheses

The successor deliberately does not recycle the burned five tasks.

### V2-001 — BenchmarkCohort direct symlink reference

Surface: `tools/benchmark_cohort.py`

Family: `bug_fix`

Observed mechanism: `resolve_repo_file()` resolves the path before checking `is_symlink()`. A direct in-repository symlink can therefore lose its symlink identity before the guard is evaluated.

Target behavior:

- ordinary repository-relative files remain accepted;
- direct symlink references fail closed even if their targets remain inside the repository;
- existing absolute/traversal rejection remains intact.

### V2-002 — free-compute non-finite values

Surface: `experiments/free_compute_router.py`

Family: `test_failure`

Observed mechanism: Python `json.loads` accepts non-standard constants such as `NaN` by default, while comparisons with non-finite values can fail open. Non-finite cost/probability/resource inputs must not enter zero-spend eligibility/ranking.

Target behavior:

- `NaN`, `Infinity`, and `-Infinity` fail closed before routing;
- ordinary finite fixtures remain unchanged;
- non-finite project cost cannot bypass a zero-project-spend policy.

### V2-003 — branch audit without observed current head

Surface: `tools/branch_convergence_audit.py`

Family: `bounded_feature`

Observed mechanism: the merged-PR match branch currently treats `head_sha is None` as satisfying head-match logic, even though cleanup policy is supposed to depend on an exact observed current head.

Target behavior:

- matching observed head + merged PR remains `integrated-via-pr`;
- missing current-head evidence becomes an explicit hold/fail-closed state;
- cleanup eligibility remains false without exact current-head evidence.

### V2-004 — RWVB non-finite numerical domain

Surface: `experiments/verification_backpressure.py`

Family: `benchmark`

Observed mechanism: several numeric guards use inequalities only. Some non-finite values can evade those tests and poison verification debt, priority, or generation-fanout arithmetic.

Target behavior:

- every floating-point Candidate/ControllerConfig input is finite before range/domain checks;
- non-finite values fail deterministically;
- existing finite controller invariants remain unchanged.

### V2-005 — local compute discovery output authority

Surface: `experiments/local_compute_offer.py`

Family: `security`

Observed mechanism: the module states discovery-only/no-canonical-write authority, but `--output` is converted directly to `Path` and written without a repository/results boundary.

Target behavior:

- stdout remains allowed;
- generated files are allowed only in non-canonical `results/`;
- canonical paths, absolute paths, and traversal fail before any write;
- no registration/network/execution authority is added.

## Scientific design decision: scaffold before freeze

The new cohort is deliberately introduced as a mutable **scaffold**, not as a frozen benchmark.

Required progression:

```text
bounded WorkUnit
 -> provisional public EvaluatorPlan v0.4
 -> straightforward reference calibration
 -> inert/Goodhart near-miss calibration
 -> task-specific behavioral regression where safe
 -> only then freeze definition digest
 -> only after freeze generate scored candidates
```

A v0.4 static transition result is treated as a proxy, not a universal correctness oracle.

Calibration candidates are explicitly non-benchmark evidence.

## Scaffold branch and PR

Branch:

`benchmark/phase-b2-successor-v2-scaffold-current`

PR:

`#185 — Scaffold calibrated Phase B2 successor first-five v2`

The scaffold contains:

- `benchmarks/phase-b2-successor-v2/README.md`;
- `benchmarks/phase-b2-successor-v2/cohort.json`;
- five WorkUnit v0.2 files;
- five provisional public EvaluatorPlan v0.4 files;
- `.github/workflows/phase-b2-successor-v2-scaffold.yml`.

## Unfrozen invariants

The scaffold intentionally has:

- `stage = scaffold`;
- `taxonomy_frozen_before_outcomes = false`;
- no stored `definition_digest`;
- five tasks, each bound to exact source SHA `a69aa0ae1ae4862e507511cbd9ad854237d0ad32`;
- all task `evidence.status = pending`;
- all negative-case `evidence_status = pending`;
- all evaluator calibration states `pending`;
- authority false for canonical state writes, Git push, merge, and automatic candidate selection.

The workflow also prints a digest preview only for observability. A preview is explicitly not a freeze.

## Cross-object digests in the scaffold

WorkUnit digests:

- V2-001: `sha256:2e0b49e98e6626131c2b08916753b3b7f6ea7c25519cc9610f7212474d8712b3`
- V2-002: `sha256:1c3398ec000719eee21396b6214bc56bb410a4aa449cb7b4f9206811daf7a27d`
- V2-003: `sha256:a48ec044dea90201c2bd43505e54c94d9bb9830dad29b6397a943e19f4f3cc75`
- V2-004: `sha256:9f4d5dd07e7af04a2d603edc7eb1cd2a424ae389a0edc7496b9ae83bcf11f4e4`
- V2-005: `sha256:063dd0504fac4b9eb474f4d16e68ffc3680edd5ab6570f3473b1634cc8edd7f8`

Provisional EvaluatorPlan digests:

- V2-001: `sha256:8711a0c53d33cd89c865f06790ab4ddb2886a3147b114b02897127a277c8af4a`
- V2-002: `sha256:21d6ef9b1386adc2aeac8cb2c1d409b2ff32ff07686378d260b8a56399226a43`
- V2-003: `sha256:8e4dc161a2f1a4cb3009274c0e786047c77b15f5f9c59a2eb8a936a9b9cf8993`
- V2-004: `sha256:bcc64b4353033bfe265a32a2aab2cdc1076bad34a310926843b7bde93e8c192c`
- V2-005: `sha256:1965941c5c2844dc302049bcf461815df885571107e73d430ca3f68cac0adc16`

These evaluator digests are provisional until calibration. Changing a plan before freeze must update the scaffold index; after freeze, semantic changes require a new cohort/version rather than silent replacement.

## CI state at archive time

PR #185 exact head:

`7754b7b65ba0694636cb685f30ace7a68c2cdb02`

At the time this record was written:

- IDKMesh Evolution Loop had passed on the exact head;
- the dedicated `Phase B2 successor v2 scaffold` workflow was still running its dependency-install step and had not reported a failure;
- concurrent `main` changes since the PR base touched audit/conversation documentation only and did not overlap the scaffold definitions.

The PR must not be merged based on this record alone. Its dedicated cross-object/scaffold gate must complete successfully first.

## Next step

Once #185's scaffold validator is green and the PR is integrated, begin calibration with V2-001 (symlink boundary) or another task one at a time. Do **not** generate scored benchmark candidate outcomes yet.

The successor cohort may be frozen only after all five evaluator calibration gates are green.

This five-task scaffold is an engineering bootstrap, not a statistical-power claim and not a substitute for issue #70's larger real-coding corpus.

## Authority boundary

No work in this continuation grants workers or verifiers:

- canonical repository write authority;
- push authority;
- PR approval or merge authority;
- automatic candidate selection;
- secret access;
- project-paid compute/spending authority.
