# Project Turn: Continue unified-diff verification and the controlled Docker gate

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User message

> https://github.com/MSKazemi/idkmesh Continue

## Repository reassessment

The continuation began by re-reading current issue #5 and the rapidly moving repository state rather than assuming the previous turn's backlog was still current.

Issue #5 had converged on a concrete two-stage remaining verification path:

1. verify one **real bundle** from the canonical `idkmesh-node` worker;
2. only then build the first 5–10 replayable repository benchmark tasks.

The prerequisite software pieces were already present or in active review:

- PR #103 had merged the verifier output-authority boundary, restricting generated verifier/evaluator output to ignored `results/`;
- PR #105 contained an already-green EvaluatorPlan v0.2 + metadata-only unified-diff evaluator backend, but rapid `main` movement had made its ancestry stale;
- PR #91 remained the frozen real-worker candidate awaiting controlled-Docker runtime acceptance in issue #37.

## Convergence rather than duplication

The implementation in PR #105 was not reimplemented from scratch. The repository was checked to confirm that the evaluator paths touched by the reviewed PR had not changed since its clean safety base. The already-reviewed evaluator blobs were then transplanted onto current `main` without overwriting concurrent R4, evidence-report, ACE, security, or documentation work.

A clean replacement PR #107 was opened and PR #105 was closed as superseded public provenance.

## PR #107 outcome

PR #107 — **Add bound unified-diff evaluator backend on current main** — passed:

- Evaluator Plan Binding CI;
- Phase 0 schema check;
- IDKMesh Evolution Loop.

The dedicated evaluator job confirmed both the existing JSON evaluator path and the new unified-diff backend/negative matrix.

PR #107 was squash-merged as:

`2e5512f8ee905f9f21384ebba420dc36160ba37e`

The landed backend adds:

- EvaluatorPlan v0.2 with explicit `unified_diff` backend selection;
- independent SHA-256 recomputation for patch and declared log evidence;
- independent unified-diff path parsing;
- WorkUnit allowed/forbidden/filesystem-write authority enforcement;
- a verifier-owned narrow semantic expectation;
- exact WorkUnit / ResultManifest / EvaluatorPlan binding;
- exact required-validator alignment;
- deterministic good, wrong-semantic, forbidden-path, forged-digest, and binding-drift cases;
- no patch application or candidate-code execution;
- no network, secrets, paid compute, or merge authority.

This removes the metadata-only software blocker for replaying a real node patch bundle.

## Controlled Docker gate status

PR #91 remains intentionally frozen at:

`d638a2f78e4a89353b98e91052233e365f56f90a`

with its exact-head Node CI and Phase 0 checks already green. Issue #37 requires a **real controlled Docker host** and positive plus negative runtime evidence.

The current assistant execution environment was checked for Docker and returned `docker: command not found`. Therefore no runtime acceptance was claimed and issue #37 remains open.

This is an important evidence-discipline decision: static CI or synthetic fixtures must not be relabeled as controlled-runtime evidence.

## New continuation: acceptance harness

To reduce the external gate's manual burden without changing PR #91's frozen head, a new main-side helper was started:

`scripts/pr91_acceptance.py`

Design principle: the acceptance helper lives on `main` while the candidate under test remains a separate exact PR #91 checkout. Improving the helper therefore does not mutate the candidate and invalidate its frozen evidence target.

The helper provides:

- exact PR #91 SHA preflight;
- Python/Git/Docker availability checks;
- Docker image inspection requiring immutable local image ID plus matching repository digest;
- no implicit image pull;
- positive node installation/test/validate/run orchestration;
- independent result-bundle validation;
- patch/stdout/stderr SHA-256 recomputation;
- independent unified-diff path parsing and WorkUnit scope enforcement;
- exact source-revision checks;
- zero-untracked/zero-policy-violation/zero-patch-truncation requirements;
- immutable container-evidence comparison;
- exact required-validator verification-request checks;
- rejection of worker-side acceptance/verification claims;
- machine-readable positive evidence report.

The helper intentionally does **not** claim to automate away issue #37's five required negative runtime checks. Those remain real controlled-host evidence requirements.

## Docker-free CI layer

A dedicated workflow was added:

`.github/workflows/pr91-acceptance-harness-check.yml`

It compiles the helper and runs its deterministic `self-test` without Docker. The self-test checks image-inspect parsing, safe unified-diff paths, a synthetic positive evidence bundle, and detection of tampered patch bytes.

This CI is explicitly **not** issue #37 runtime evidence.

## Runbook

A contributor-facing runbook was added:

`docs/acceptance/PR91_CONTROLLED_DOCKER_GATE.md`

It documents:

- the exact frozen candidate and CI run IDs;
- two-checkout trust separation;
- manual image preload;
- preflight and positive-run commands;
- evidence checked independently by the helper;
- required negative runtime matrix A–E;
- evidence to attach to issue #37;
- the next Phase B1 chain after real runtime acceptance.

## Current decision

Do not create benchmark inventory merely to appear busy while the first real worker bundle remains unverified. The correct next evidence sequence is:

```text
controlled Docker host
 -> frozen PR #91 node run
 -> positive + negative runtime evidence
 -> real ResultManifest bundle
 -> EvaluatorPlan v0.2
 -> unified-diff independent VerificationResult
 -> Evidence Report/replay
 -> first 5–10 benchmark tasks
```

Issue #37 remains a genuine external execution gate, not a documentation checkbox.
