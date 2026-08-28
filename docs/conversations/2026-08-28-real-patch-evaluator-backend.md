# Project Turn: Real Patch Evaluator Backend

Date: 2026-08-28

## Context

The current IDKMesh critical path had converged on one missing verification capability:

> independently evaluate a real repository patch/result bundle from the canonical node without creating another verifier architecture or executing candidate code.

The canonical foundations already existed:

- WorkUnit / ResultManifest contracts;
- VerificationResult v0.1;
- `experiments/local_verifier.py` from PR #72;
- EvaluatorPlan v0.1 / Evaluator Sovereignty from PR #81;
- two-attempt orchestration from PR #78;
- verifier/evaluator output-authority fix in green PR #90.

The canonical node branch #34 produces:

```text
changes.patch
stdout.txt
stderr.txt
result-manifest.json
```

with worker-declared SHA-256 values and worker-reported changed paths. Those claims are useful provenance, but they are not independent acceptance evidence.

## Design decision

Do **not** revive closed PR #61's second `verifier/` package and do **not** overload EvaluatorPlan v0.1's JSON-specific fields with fake patch configuration.

Instead:

1. keep `VerificationResult v0.1` canonical;
2. keep `idkmesh-local-verifier` canonical;
3. add EvaluatorPlan v0.2 selecting an explicit `unified_diff` backend;
4. dispatch through the existing `experiments/evaluator_plan_runner.py`;
5. add a `verify_patch_candidate()` backend inside `experiments/local_verifier.py`;
6. bind required validator coverage exactly to the WorkUnit.

The resulting trust chain remains:

```text
WorkUnit
 -> untrusted ResultManifest
 -> verifier-owned EvaluatorPlan
 -> canonical local verifier backend
 -> VerificationResult
 -> human/integration decision
```

## WorkUnit validator alignment

The patch fixture uses the same validator shape as the canonical node smoke:

- `result-manifest-schema`;
- `independent-review`.

The patch backend emits those exact IDs as required VerificationResult checks. The EvaluatorPlan runner fails closed if the selected backend's implemented validator IDs do not exactly equal the WorkUnit-required IDs.

This prevents a backend from claiming success while silently substituting a different verification contract.

## Independent evidence implemented

The backend does not trust worker extension fields such as `changed_paths` or `policy_violation_count` as acceptance evidence.

It independently reconstructs:

- candidate patch SHA-256;
- every declared log SHA-256;
- patch byte limits;
- old/new repository paths from unified-diff headers;
- WorkUnit `allowed_paths` / `forbidden_paths` / filesystem-write authority;
- verifier-owned required added hunk lines;
- worker execution status as a conservative prerequisite, not proof.

Absolute/traversal paths and candidate-root symlinks fail closed. Candidate code is never executed.

## Fixtures

A deterministic patch fixture family was added before code so the implementation had an external success target:

1. good README-only patch with the expected added marker;
2. scope-valid README patch with the wrong semantic marker;
3. forbidden `SECURITY.md` patch with the expected semantic marker;
4. forged-digest case constructed from the good candidate during self-test;
5. EvaluatorPlan WorkUnit-binding drift constructed during self-test.

The worker ResultManifests for the first three are self-consistent and report success. The independent evaluator must create the distinction.

## EvaluatorPlan v0.2

The v0.2 plan remains metadata-only and verifier-owned, but makes the backend explicit:

```text
backend.type = unified_diff
verifier.adapter = deterministic-patch-verifier
```

It binds:

- WorkUnit id/version/digest;
- source revision;
- exact required validator IDs;
- candidate artifact id;
- patch/log byte limits;
- verifier-owned required added text;
- evaluator independence/output rules.

EvaluatorPlan v0.1 remains unchanged for exact-JSON fixtures.

## CI

The Evaluator Plan Binding workflow was extended with a separate `patch-self-test` while preserving the existing v0.1 JSON self-test.

The new matrix requires:

- good patch -> support;
- wrong semantic -> reject without scope finding;
- forbidden path -> reject with scope finding;
- forged digest -> reject with provenance finding;
- WorkUnit-binding drift -> fail closed;
- required VerificationResult check IDs exactly match the WorkUnit validator IDs.

## Safety / non-goals

This work does not:

- apply patches;
- execute candidate code;
- execute worker-supplied commands;
- use network services or secrets;
- use project-paid compute;
- trust node-reported changed paths as independent evidence;
- select/merge candidates;
- introduce another verifier package.

A future verifier-owned test/static-analysis/sandbox backend will require a separately reviewed execution boundary.

## Stacking

This branch is intentionally stacked on PR #90 because new evaluator functionality must inherit the corrected output-authority boundary: generated verification evidence is restricted to ignored root `results/` and cannot overwrite canonical tracked repository state.

After #90 merges, this patch backend should be rebased/retargeted to `main` before integration.

## Next product integration

After CI and independent review:

1. synchronize #34 with current `main`;
2. complete controlled Docker acceptance #37;
3. bind a real EvaluatorPlan v0.2 to the canonical node smoke WorkUnit;
4. replay the real node bundle through this backend;
5. connect that evaluator path to the merged PR #78 two-attempt orchestrator;
6. then build the first 5–10 real repository benchmark tasks.

No self-merge or autonomous integration is performed in this turn.

---

# Continuation — reconcile PR #105 with fast-moving `main`

## Project-owner instruction

> Continue

Repository context: `https://github.com/MSKazemi/idkmesh`

## Live-state recheck

The repository advanced substantially while this verification lane was in review:

- PR #98, the converged ACE workflow security/protected-integration hardening, merged into `main`;
- PR #103, the verifier/evaluator `results/`-only output-authority boundary, merged into `main`;
- PR #88, the non-selecting run Evidence Report/replay layer, merged into `main`;
- canonical node PR #91 remained deliberately frozen at `d638a2f78e4a89353b98e91052233e365f56f90a` for controlled Docker acceptance #37;
- raw GitHub PR state confirmed #91 remains clean/mergeable, so the frozen node candidate was **not** resynchronized merely because the base branch moved;
- PR #105, by contrast, had become genuinely `mergeable_state: dirty` because its stacked ancestry predated the merged verifier/evaluator safety base.

## Convergence decision

Do **not** disturb PR #91 while external runtime evidence is pending.

Do **not** open another patch-evaluator PR just because #105's ancestry became stale.

Instead, reconcile the existing canonical #105 branch by constructing a normal two-parent merge commit:

```text
parent 1 = existing #105 head 5548e6c927387ccc1931fa437d2ef35442369e0d
parent 2 = then-current main 10eb39070fb09195bea2e7824aa058b857acccd4
resolved tree = complete current-main tree
                + only the 20 reviewed patch-evaluator blobs
```

This preserves all unrelated current-main work while carrying forward only the intended evaluator delta.

No force push was used.

## Reconciled evaluator head

Merge commit:

`38cc816e7f78a65368433efa58ad2d104bfdbf15`

The 20 overlaid paths are limited to:

- Evaluator Plan Binding workflow;
- EvaluatorPlan v0.2 schema/fixture;
- patch evaluator specification/conversation record;
- patch-verifier WorkUnit and good/wrong-semantic/forbidden fixture bundles;
- `experiments/evaluator_plan_runner.py`;
- `experiments/local_verifier.py`.

The reconciled `local_verifier.py` retains PR #103's `resolve_output_path()` restriction, so generated verifier/evaluator evidence remains limited to ignored `results/` rather than regressing canonical-write authority.

## Evidence after reconciliation

A direct branch lookup confirmed `feature/evaluator-plan-patch-backend-v1` moved to `38cc816e7f78a65368433efa58ad2d104bfdbf15` with both expected parents.

The broad `randomness-lab` push run on this exact head completed successfully:

- run `33185194538` — success.

The GitHub PR metadata endpoint lagged behind the direct branch ref immediately after the low-level Git-data update, and the PR-specific `pull_request` workflow did not fire from that ref update path. This archive commit is intentionally made through the normal Contents API on the same branch so GitHub receives an ordinary branch update/synchronize event and can run the PR-specific evaluator checks on the resulting head.

## Current safety / integration rule

The real-worker and evaluator lanes now have different change policies:

```text
PR #91 / #37:
  freeze exact candidate SHA for external Docker evidence
  do not chase unrelated main movement

PR #105:
  not externally frozen
  reconcile stale ancestry when needed
  preserve current main wholesale
  overlay only reviewed evaluator delta
  require exact-head evaluator/Phase-0 evidence before integration
```

Neither lane gains automatic merge authority.

## Next step

After the normal branch update triggers exact-head CI:

1. require Evaluator Plan Binding / patch self-test success;
2. require relevant Phase 0 / broader regression checks;
3. update issue #5 and PR #105 with the exact reconciled head and run IDs;
4. leave #105 for independent integration;
5. keep #91 frozen until #37 supplies real controlled-Docker evidence;
6. after #37 and #105 are accepted, replay the first real node bundle through EvaluatorPlan v0.2 and VerificationResult v0.1.

No self-merge or autonomous integration is performed in this continuation.
