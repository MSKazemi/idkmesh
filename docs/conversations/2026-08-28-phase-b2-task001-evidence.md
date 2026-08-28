# Conversation record: execute Phase B2 benchmark Task 001

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner instructed: **Continue**.

The standing project rule is to preserve substantive collaboration in the public repository and to prefer measurable, executable progress over additional untested theory when the next engineering step is clear.

## Repository state observed

The repository had advanced substantially since the earlier canonical-node integration work:

- PR #91 remains deliberately frozen in draft pending a separate human/reviewer inspection; its exact-head Docker acceptance matrix is already complete.
- PR #116 merged EvaluatorPlan v0.2 routing into the existing two-attempt orchestrator.
- PR #120 merged two-real-attempt orchestration, independent verification, non-selecting report generation, and exact replay evidence.
- Issue #5 therefore marks Phase B1 experimentally complete and Phase B2 as the next verifier/product milestone.
- Commit `7d932081a91ca840f22d992441c0e11f148e37c7` froze the first five Phase B2 benchmark definitions before candidate outcomes.

The first frozen task is:

`benchmark/phase-b2/001-cohort-path-boundary`

It targets a real repository boundary bug in `tools/benchmark_cohort.py`: the public `validate` and `definition-digest` commands directly resolved `--cohort` with `(ROOT / args.cohort).resolve()` instead of using the existing repository-bounded `resolve_repo_file(...)` guard.

## Scientific boundary

The frozen Task 001 WorkUnit intentionally contains no node-specific execution extension. Adding such an extension after the task was frozen would change the canonical WorkUnit digest and invalidate the already-bound public EvaluatorPlan.

Therefore this turn does **not** mutate the frozen task definition to force it through `idkmesh-node`.

Instead it adds a worker-neutral deterministic single-worker baseline evidence harness that:

1. checks out the exact frozen source revision `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2` separately;
2. verifies the source checkout is clean and exact;
3. replaces exactly the two vulnerable cohort-loading lines with the already-existing fail-closed `resolve_repo_file(args.cohort, label="BenchmarkCohort")` guard;
4. generates the candidate as a Git unified diff without touching the benchmark/evaluator control plane;
5. packages the candidate, stdout, and stderr as canonical worker `ResultManifest v0.1` evidence;
6. routes the bundle through the frozen public Task 001 `EvaluatorPlan v0.2` and the existing metadata-only `unified_diff` verifier;
7. requires an independently supported `VerificationResult v0.1`;
8. executes four seeded negative path-boundary checks against the patched frozen repository tool:
   - `validate` with an absolute path;
   - `definition-digest` with an absolute path;
   - `validate` with traversal;
   - `definition-digest` with traversal;
9. requires every unsafe input to fail closed specifically as an `unsafe path`;
10. constructs a prospective cohort attachment and validates it through the canonical Benchmark Cohort v0.1 cross-object checks;
11. proves that attaching Task 001 evidence leaves the frozen pre-outcome definition digest unchanged and changes only the evidence state from `0 verified / 5 pending` to `1 verified / 4 pending`.

## New executable artifacts

- `tools/phase_b2_task001_evidence.py`
- `.github/workflows/phase-b2-task001-evidence.yml`

The workflow is read-only and uses no secrets. It checks out the evaluator/control plane separately from the frozen source, installs only the existing Phase 0 verifier dependency, generates the evidence bundle under ignored `results/`, publishes a non-selecting summary, and uploads the exact result bundle as a temporary GitHub Actions artifact.

## Authority boundary

This experiment grants no:

- canonical repository write authority;
- push authority;
- pull-request approval authority;
- merge authority;
- automatic candidate-selection authority.

Worker success is not acceptance. Verifier support is decision support, not integration authority. The cohort remains a five-task engineering bootstrap, not a statistical-power claim.

## Next evidence step

Open the branch as a reviewable PR and let GitHub Actions execute the exact frozen-source evidence job. If it passes, inspect the generated ResultManifest, VerificationResult, negative evidence, and unchanged definition digest before deciding whether to retain Task 001 evidence in the repository.

The same pattern can then be generalized carefully to Tasks 002–005 only after Task 001 is demonstrably replayable and reviewer/verifier capacity remains healthy.
