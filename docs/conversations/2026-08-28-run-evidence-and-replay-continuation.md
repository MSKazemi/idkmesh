# Conversation Record — Run Evidence and Replay Continuation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

The project owner asked:

> `https://github.com/MSKazemi/idkmesh Continue.`

The standing project rule requires substantive project work from this chat to be preserved in the public repository.

## Repository state observed

This continuation inspected current `main` rather than relying on the previous turn's snapshot.

Several important components had landed rapidly:

- PR #72 / `experiments/local_verifier.py`: executable zero-cost independent verifier MVP;
- PR #78 / `experiments/two_attempt_orchestrator.py`: deterministic two-attempt orchestration kernel;
- PR #81 / EvaluatorPlan: verifier-control binding to exact WorkUnit/source revision;
- additional R1/R2 scheduling and verifier-independence experiments.

Issue #16 still identified a product-facing gap that does **not** require waiting for Docker acceptance #37:

```text
minimal Evidence Report / replay UX over the canonical run record
+ per-attempt ResultManifest + VerificationResult evidence
```

The repository also still reports `main` as unprotected, so no stronger autonomous integration authority should be added.

## Decision

Implement the smallest read-only evidence/replay layer over the already-landed two-attempt kernel.

Do **not**:

- create another worker protocol;
- create another independent-verifier protocol;
- revive the candidate-level Evidence Report proposal from closed PR #42;
- select a winning candidate;
- add merge/push authority;
- execute candidate code.

The canonical verifier result remains `VerificationResult v0.1`.

The new artifact is specifically a **run-level aggregation view** for humans/governance.

## Implementation branch

`feature/run-evidence-replay-v0`

### `experiments/run_evidence_report.py`

Adds a standard-library product-facing utility that:

1. validates the deterministic orchestration run record;
2. re-checks WorkUnit / ResultManifest / VerificationResult digest binding;
3. maps every attempt into exactly one evidence state:
   - supported;
   - rejected;
   - inconclusive;
   - worker error;
   - ResultManifest error;
   - verification error;
4. preserves worker/verifier failures instead of dropping failed attempts;
5. surfaces differing independent verifier recommendations as disagreement;
6. leaves human integration decision explicitly pending;
7. provides JSON + Markdown reports;
8. provides complete-record deterministic replay checking.

### Hard authority invariant

Generated evidence contains:

```text
selected_attempt_id = null
automatic_candidate_selection = false
canonical_state_write = false
git_push = false
merge = false
```

### Provenance guard

Before rendering, the tool requires:

```text
verification.result_manifest_digest == summarized ResultManifest digest
verification.work_unit_digest == run WorkUnit digest
```

A mismatch fails closed.

### Replay rule

For deterministic fixture runs:

```text
ReplayMatch = SHA256(canonical(saved_run))
              ==
              SHA256(canonical(replayed_run))
```

Replay equality is explicitly treated as reproducibility evidence, **not correctness**.

Real model/agent workers may later need an explicit provenance-equivalent or semantic replay mode. v0.1 does not silently weaken exact replay.

## New artifacts

- `experiments/run_evidence_report.py`
- `schemas/run-evidence-report-v0.1.schema.json`
- `docs/specifications/RUN_EVIDENCE_REPORT_V0_1.md`
- `.github/workflows/run-evidence-report-check.yml`
- this conversation record.

The CI workflow pins `actions/checkout` and `actions/setup-python` to the commit SHAs currently resolved by GitHub for their major-version tags and executes only repository-controlled fixture logic.

## Self-test expectations

The self-test requires:

- known-good attempt -> independent support;
- known-bad attempt -> independent rejection;
- support/reject disagreement remains visible;
- human decision remains pending;
- automatic selection remains false;
- one worker failure does not erase a surviving supported attempt;
- identical deterministic replay matches;
- tampered saved run does not match;
- ResultManifest/VerificationResult digest-binding drift is rejected.

## Product impact

This advances the v0.1 user journey from:

```text
run two attempts -> raw machine record
```

toward:

```text
run two attempts
 -> independent verification per attempt
 -> inspect one combined evidence view
 -> replay-check saved run
 -> human decision remains external
```

It does not claim the real worker path is complete. The remaining critical path still includes #34/#37 and repository-candidate verification under #5 before this evidence surface is exercised over real isolated node attempts.

## Community impact

A newcomer can now work on evidence rendering, replay semantics, human-decision UX, disagreement visualization, or real-adapter integration without modifying worker or verifier internals.

The design deliberately rewards convergence: it composes already-merged protocols and control-plane code instead of adding another competing architecture.
