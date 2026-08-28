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
