# Conversation Record — Evidence Convergence and Node Integrity Review

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

The project owner asked the assistant to continue improving the public repository:

> `https://github.com/MSKazemi/idkmesh Continue.`

The standing project rule requires substantive work from this project chat to remain inspectable in the public repository.

## Repository state at the start of this continuation

The repository had advanced quickly since the preceding ACE/MOSAIC work. In particular, current `main` already contained:

- the zero-cost deterministic independent verifier from PR #72;
- the deterministic two-attempt orchestration kernel from PR #78;
- Evaluator Sovereignty / `EvaluatorPlan v0.1` from PR #81;
- verification-provenance binding and backpressure work;
- R1/R2/R3 experimental infrastructure.

This shifted the immediate bottleneck away from new theory and toward convergence of the first executable Verified Swarm Runner path.

## Workstream A — non-selecting run evidence + replay

Issue #16 still needed a combined product-facing evidence/replay view over the two-attempt run record.

Branch `feature/run-evidence-replay-v0` / PR #88 was created with:

- `experiments/run_evidence_report.py`;
- `schemas/run-evidence-report-v0.1.schema.json`;
- `docs/specifications/RUN_EVIDENCE_REPORT_V0_1.md`;
- `.github/workflows/run-evidence-report-check.yml`;
- a conversation archive.

The run-level report deliberately **does not create a new verifier protocol**. It aggregates canonical worker `ResultManifest` and independent `VerificationResult` evidence while fixing:

```text
human_decision.status = pending
selected_attempt_id = null
automatic_candidate_selection = false
canonical_state_write = false
git_push = false
merge = false
```

It fails closed if verifier evidence is no longer bound to the exact summarized WorkUnit/ResultManifest digests and preserves support/reject/inconclusive/control-error states separately.

The first CI run found a real integration defect: the new workflow did not install `requirements-phase0.txt`, so importing the existing orchestration/verifier path failed on `jsonschema`. The workflow was corrected rather than weakening the test. Both the new evidence/replay check and existing Phase 0 suite then passed.

## Workstream B — prevent duplicate verifier control planes

Open PR #76 extends independent verification to bounded repository patches and hidden checks. During current-main review, the repository's accepted ADR-0009 was found to make `EvaluatorPlan` the canonical verifier-owned control-plane object and explicitly names sandboxed hidden tests as its follow-up.

PR #76 also introduced `VerifierPlan v0.1`, creating overlapping verifier-plan semantics.

A public review was posted asking #76 to converge on:

```text
WorkUnit
 -> ResultManifest
 -> EvaluatorPlan
 -> sandboxed repository-patch evaluator backend
 -> VerificationResult
 -> human/governance decision
```

rather than maintaining parallel `EvaluatorPlan` and `VerifierPlan` lineages.

The review also identified:

- candidate workspace mutability across hidden checks;
- mutable container image tags;
- duplicate check-ID ambiguity;
- correlation/provenance details.

PR #76 was moved back to draft pending reconciliation. This was a convergence action, not a rejection of the patch-verifier capability.

## Workstream C — canonical node replacement and independent source review

PR #34 had already become stale and was explicitly superseded by PR #91, which transplanted only the canonical node worker surface onto current `main`.

The first review of PR #91 found two concrete evidence-integrity blockers:

1. a tracked diff could exceed `max_patch_bytes`, be truncated in `changes.patch`, and still be represented as worker `status: succeeded`;
2. the task-writable workspace contained ordinary `.git` metadata, while post-run evidence depended on Git commands over that same candidate-writable state.

These findings were posted publicly and #37 runtime acceptance was paused so no one would freeze runtime evidence against a head known to require changes.

Concurrent convergence work then fixed both issues more comprehensively:

- trusted Git metadata is now stored outside `/workspace`;
- task-side metadata is mounted read-only;
- host Git result capture uses explicit trusted `--git-dir` / `--work-tree` paths;
- inherited/system/global Git configuration is isolated;
- `.git` pointer tampering is detected;
- ignored untracked outputs remain observable;
- candidate patch truncation is a fail-closed output-policy violation.

## Additional runtime-evidence hardening in this continuation

Two remaining review items were then implemented directly on PR #91's branch.

### Whole-attempt wall budget

The node's parsed WorkUnit now requires a positive `budget.wall_seconds` and retains it as a first-class worker bound.

Runtime enforcement now applies a single deadline across:

- immutable local container-image resolution;
- Git source preparation/fetch/checkout;
- container execution.

If final measured attempt time exceeds the declared budget, a runtime-policy violation is retained and the worker cannot report success.

This closes the earlier gap where only the container command had a timeout while `git fetch` could exceed the WorkUnit wall budget.

### Immutable container runtime identity

The execution binding still uses a small tag allowlist as the configuration/routing selector, but a tag alone is not acceptable runtime provenance.

Node v0.1 now requires the allowed image to be **preloaded on the controlled host**, resolves it using Docker to its immutable local image ID (`sha256:...`), executes the container using that exact image ID, and records the ID in:

`extensions.org.idkmesh.node.v0_1.container_image_id`

The node deliberately does not perform an implicit image pull during task execution. Image acquisition stays outside the WorkUnit's task authority.

Tests were added for:

- tag -> immutable image-ID resolution;
- fail-closed behavior when the allowed image is not preloaded;
- execution by resolved image ID;
- propagation of the whole-attempt wall budget.

The node README was updated with the corresponding controlled-host procedure.

## Verification discipline

At no point was green unit/schema CI treated as proof of Docker containment.

The current sequence remains:

```text
code/security review
 -> deterministic Node CI + Phase 0
 -> freeze exact PR #91 head
 -> independent controlled-host Docker acceptance #37
 -> positive + negative runtime evidence
 -> only then consider worker readiness
```

The runtime gate must be re-frozen whenever the candidate worker tree changes.

## Current product graph

The convergence target is now:

```text
WorkUnit v0.2
 -> idkmesh-node (real worker candidate, PR #91)
 -> ResultManifest v0.1
 -> EvaluatorPlan-bound independent verifier
 -> VerificationResult v0.1
 -> run evidence/replay view (PR #88)
 -> external human/governance decision
```

The landed two-attempt coordinator remains the later fan-out layer. It should receive a real node adapter only after the single real worker + verifier path has produced controlled evidence.

## Safety / governance state

- No assistant-created work in this continuation was auto-merged.
- PR #76 and PR #91 were moved to draft when review found unresolved convergence/evidence issues.
- Main-branch protection remains an external repository-settings gate tracked by #35.
- Worker, verifier, report, and coordinator remain unable to grant themselves canonical merge authority.
- Project compute spend remains fixed at zero.

## Community impact

This continuation intentionally reduced protocol proliferation and integration ambiguity rather than opening new architecture layers.

The repository now has clearer independent contribution surfaces around:

- controlled Docker acceptance;
- EvaluatorPlan-backed repository-patch verification;
- real worker adapter integration;
- evidence/replay UX;
- heterogeneous second adapter work;
- branch-protection/governance administration.

The design principle reinforced by the work is:

> **Converge protocols, freeze evidence to exact artifacts, and fail closed whenever an output or measurement boundary is incomplete or candidate-controlled.**
