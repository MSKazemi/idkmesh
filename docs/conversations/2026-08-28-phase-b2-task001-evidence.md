# Conversation record: Phase B2 Task 001 evidence and evaluator calibration

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner instructed: **Continue**.

The standing project rule is to preserve substantive collaboration in the public repository and to prefer measurable, executable progress over additional untested theory when the next engineering step is clear.

## Starting repository state

The repository had advanced substantially since the earlier canonical-node integration work:

- PR #91 remains deliberately frozen in draft pending a separate human/reviewer inspection; its exact-head Docker acceptance matrix is already complete.
- PR #116 merged EvaluatorPlan v0.2 routing into the existing two-attempt orchestrator.
- PR #120 merged two-real-attempt orchestration, independent verification, non-selecting report generation, and exact replay evidence.
- Issue #5 therefore marked Phase B1 experimentally complete and Phase B2 as the next verifier/product milestone.
- Commit `7d932081a91ca840f22d992441c0e11f148e37c7` froze the first five Phase B2 benchmark definitions before candidate outcomes.

The first frozen task was:

`benchmark/phase-b2/001-cohort-path-boundary`

with frozen source revision:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`.

It targeted a real repository-boundary bug in `tools/benchmark_cohort.py`: the public `validate` and `definition-digest` commands directly resolved `--cohort` with `(ROOT / args.cohort).resolve()` instead of using the existing repository-bounded `resolve_repo_file(...)` guard.

## Scientific boundary

The frozen Task 001 WorkUnit intentionally contains no node-specific execution extension. Adding such an extension after the task was frozen would change the canonical WorkUnit digest and invalidate the already-bound public EvaluatorPlan.

Therefore this turn did **not** mutate the frozen task definition to force it through `idkmesh-node`.

A worker-neutral deterministic baseline instead:

1. checked out the exact frozen source separately;
2. replaced exactly the two vulnerable cohort-loading lines with the existing fail-closed repository resolver;
3. changed only `tools/benchmark_cohort.py`;
4. emitted a canonical ResultManifest v0.1 plus a strict unified-diff candidate;
5. passed four controlled negative regressions:
   - `validate` with an absolute path;
   - `definition-digest` with an absolute path;
   - `validate` with traversal;
   - `definition-digest` with traversal;
6. routed the candidate through the exact frozen public EvaluatorPlan v0.2.

## First observed outcome: valid fix rejected

The frozen evaluator rejected the straightforward candidate.

The reason was not provenance, scope, schema, artifact digest, log integrity, or worker status. Those checks passed. The only missing semantic item was:

`resolve_repo_file(args.cohort`

The frozen plan stores that value as `required_added_text`, while deterministic patch verifier v0.1.1 interprets each entry as **exact full added-line membership**. The correct candidate adds full Python statements containing the fragment, so the exact-line predicate does not match.

This was a legitimate benchmark failure signal: changing the meaning of `required_added_text` after seeing the candidate would violate the pre-outcome freeze.

## Concurrent mainline convergence

While this experiment was running, the repository independently converged on the same integrity decision:

- real solution PR #153 merged as commit `c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`, fixing the live repository bug and adding path-boundary regression coverage;
- the first-five cohort was changed to stage `burned` while preserving its original definition digest;
- all five frozen tasks were excluded because their evaluator plans use semantic fragments under verifier v0.1.1 exact-line semantics;
- successor issue #157 was opened: **Version patch-verifier semantic matching before Phase B2 successor cohort**.

The original frozen definition digest remains:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`.

This branch therefore stopped trying to attach Task 001 as a verified benchmark outcome and became diagnostic/evaluator-calibration work only.

## Stronger calibration: false negative and false positive

The experiment then tested whether the exact-line evaluator was merely too strict or was also gameable.

An adversarial calibration candidate was constructed on the same frozen source. It intentionally **did not repair the security bug**. It only added an inert valid-Python multiline string containing an exact added line:

`resolve_repo_file(args.cohort`

The candidate stayed inside the WorkUnit path scope and produced schema-valid, digest-consistent metadata.

The frozen evaluator **accepted this decoy** with recommendation `accept_candidate`.

A separate controlled execution against that decoy source then passed an absolute out-of-repository cohort file to `definition-digest`. The command returned exit code `0` and printed the cohort definition digest, proving that the original path-boundary vulnerability remained present.

Therefore the frozen Task 001 evaluator demonstrates both:

1. **false negative** — rejects the straightforward correct fix that passes the seeded security regressions;
2. **false positive** — accepts an inert exact-line decoy while the indexed security bug remains.

This is stronger evidence than a simple matching mismatch. The exact-line proxy is not calibrated to the task objective and can be Goodharted.

## Final reproducible evidence

The final exact-head GitHub Actions run was:

- workflow: `Phase B2 Task 001 Evidence`;
- run: `33193136434`;
- result: **success**;
- artifact ID: `9694595266`;
- artifact ZIP SHA-256: `ce7d4ca382f0dec58ac8a05a31ceff3cc88aec887345eebd099d7a8c553aaba1`.

Key canonical evidence digests reported by the finalizer:

- straightforward VerificationResult: `sha256:c19b09e563653422962f84a91a802a62cefd8577f5e77605ca02cd0d0bd7d732` — status `failed`, recommendation `reject_candidate`;
- decoy ResultManifest: `sha256:c199edcff24358eb2b3abb3cbf0a39e80d076dbaceb62e926d907457f3e459a8`;
- decoy VerificationResult: `sha256:bfe06352d53fdc137412b071080ab7208161a79380257681afbaba871c2710bd` — status `passed`, recommendation `accept_candidate`.

The decoy boundary observation independently returned:

- exit code: `0`;
- accepted absolute path: `true`;
- output: the unchanged frozen definition digest.

## New executable artifacts

This branch adds:

- `tools/phase_b2_task001_evidence.py` — straightforward frozen-source candidate + regression evidence;
- `tools/phase_b2_task001_evaluator_probe.py` — adversarial evaluator calibration;
- `tools/phase_b2_task001_burn_evidence.py` — final validation against the canonical burned cohort;
- `.github/workflows/phase-b2-task001-evidence.yml` — read-only exact-source replay and evidence artifact publication.

## Decision and next step

Do **not** reinterpret or mutate the frozen evaluator plan after this result.

Retain the first-five cohort as burned diagnostic evidence and continue through issue #157 with an explicitly versioned successor semantic contract, for example a field whose name and implementation unambiguously specify substring matching. The successor evaluator should contain tests showing the difference between exact-line and substring semantics and should be frozen before the next cohort sees candidate outcomes.

Task 001 is already solved in the live repository and is no longer untouched held-out evidence.

## Authority boundary

This experiment grants no:

- canonical repository write authority;
- push authority;
- pull-request approval authority;
- merge authority;
- automatic candidate-selection authority.

Worker success is not acceptance. Verifier recommendation is decision support, not integration authority. Even the adversarial verifier acceptance is explicitly treated as a calibration false positive, not as evidence that the decoy solves the task.
