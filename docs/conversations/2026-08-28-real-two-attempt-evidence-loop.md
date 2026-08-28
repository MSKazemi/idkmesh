# Project Turn: Real two-attempt worker -> verifier -> Evidence Report loop

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User message

> Okay, go ahead and continue.

## Repository reassessment

The continuation began by checking the live repository rather than assuming the prior Docker gate was still the bottleneck.

The critical path had advanced substantially:

- issue #37 controlled Docker acceptance had completed for PR #91 exact head `520ad2c9aa5825476de4957da4702d6823f4edb3`;
- PR #113 had generated one fresh real node bundle and independently verified it through the current EvaluatorPlan v0.2 unified-diff verifier;
- issue #5 therefore moved its next dependency to a **real multi-attempt orchestration run**, followed by the already-merged non-selecting Evidence Report/replay layer;
- issue #4 still needed two real isolated attempts from the same WorkUnit/source revision.

This made the correct next engineering target:

```text
same bounded WorkUnit
 -> real node attempt 1 -> ResultManifest -> independent VerificationResult
 -> real node attempt 2 -> ResultManifest -> independent VerificationResult
 -> existing idkmesh-two-attempt-run record
 -> existing non-selecting Evidence Report
 -> replay report from saved run metadata
 -> human integration decision remains pending
```

## Design choice: bridge existing surfaces, do not create a new protocol

The repository already has:

- the accepted exact-SHA worker candidate;
- `tools/real_node_verifier_e2e.py` from PR #113;
- the canonical `idkmesh-two-attempt-run` record shape from PR #78;
- `experiments/run_evidence_report.py` from PR #88.

Therefore this continuation does **not** create a second worker, verifier, run schema, or report format.

A small integration bridge was added:

`tools/real_two_attempt_evidence.py`

Its responsibility is limited to validating already-produced real attempt evidence and composing the existing run/report contracts.

## Binding rules

For each attempt the bridge requires:

- exact WorkUnit id/version binding in ResultManifest;
- ResultManifest `provenance.work_unit_digest` equals the canonical WorkUnit digest;
- VerificationResult references the exact ResultManifest id;
- VerificationResult WorkUnit id/version and WorkUnit digest match;
- VerificationResult `result_manifest_digest` equals the actual canonical ResultManifest digest;
- VerificationResult `verifier_config_digest` equals the actual canonical EvaluatorPlan digest;
- `independence.independent_from_worker == true`.

Across the two attempts it additionally requires:

- exactly the same WorkUnit object;
- exactly the same verifier-owned EvaluatorPlan;
- exactly two ordered run attempt ids: `attempt-001`, `attempt-002`.

The bridge does not reinterpret worker success as correctness. It summarizes the independent verifier outcome already bound to each result.

## Authority invariant

The generated run record inherits the existing non-authoritative shape:

```json
{
  "canonical_state_write": false,
  "git_push": false,
  "merge": false,
  "automatic_candidate_selection": false
}
```

The Evidence Report must retain:

```text
human_decision.status = pending
selected_attempt_id = null
integration_authority = external_human_or_governance
```

Two supported candidates therefore remain two supported candidates. The orchestration/report layer does not manufacture a winner.

## Real Docker workflow

A new read-only GitHub workflow was added:

`.github/workflows/real-two-attempt-evidence-e2e.yml`

The workflow:

1. checks out the evaluator-owned current PR tree;
2. checks out the exact accepted worker SHA `520ad2c...` separately;
3. verifies the producer SHA;
4. preloads the accepted `python:3.12-alpine` runtime image;
5. runs `tools/real_node_verifier_e2e.py` for attempt 1;
6. runs the same exact worker/evaluator path independently for attempt 2;
7. composes the existing `idkmesh-two-attempt-run` record;
8. builds the existing non-selecting Evidence Report;
9. rebuilds the report from the saved run record and requires semantic report equality;
10. asserts both attempts remain independently visible and that no automatic selection or merge authority appears.

The workflow uses `contents: read`, does not persist checkout credentials, receives no repository secrets for candidate execution, and does not approve/push/merge.

## Replay semantics

Raw real executions can contain nondeterministic timestamps, resource measurements, generated IDs, or other runtime observations. The replay requirement for this integration is therefore **not** to pretend a second Docker execution is byte-identical.

Instead, once the real run record is saved, the Evidence Report must be deterministically reconstructible from that saved, cryptographically bound metadata. The replay check compares canonical report digests and requires equality without re-executing candidate code.

This is the appropriate replay boundary for a presentation/aggregation layer while the underlying real artifacts remain retained separately.

## Expected evidence if CI passes

The target run should demonstrate:

- two real isolated node attempts from the same exact WorkUnit/source revision;
- one canonical ResultManifest per attempt;
- one independent canonical VerificationResult per attempt;
- both attempts preserved independently in the run record;
- one non-selecting Evidence Report over the real run;
- deterministic report reconstruction from saved run metadata;
- human decision remains pending;
- no automatic merge/selection authority.

A peer worker failure-isolation invariant remains covered by the existing PR #78 deterministic orchestrator tests. This new workflow specifically adds the missing **two real attempt** evidence surface.

## Next decision after CI

If the real workflow is green and the branch remains mergeable:

1. merge this bounded integration proof;
2. update #4/#5/#16 with exact workflow evidence;
3. treat the first real two-attempt run + Evidence Report as the entry gate for the initial 5–10 task benchmark cohort;
4. do not scale to 3–5 workers until the two-attempt real path is stable and reviewable.
