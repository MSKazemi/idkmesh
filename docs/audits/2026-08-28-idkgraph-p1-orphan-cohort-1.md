# IDKGraph P1 — Orphan Warning Cohort 1 Classification

**Date:** 2026-08-28  
**Issue:** #152  
**Sampler:** `tools/idkgraph_warning_sample.py`  
**Category:** `orphan_document_candidate`  
**Seed:** `idkgraph-p1-orphans-v1`  
**Requested sample size:** 15  
**Eligible population in frozen PR #162 merge-ref run:** 132  
**Frozen source revision:** `d0bafb7fe64a5d15db82e721a281e0dee2d3cc30`

## Purpose

This is the first evidence-backed P1 classification of deterministic IDKGraph orphan warnings.

The P0 detector says only:

> no inbound resolved local Markdown link from another document was observed.

That is a reproducible structural observation, **not proof that the document is useless, misplaced, superseded, or safe to delete**.

The cohort was selected before classification with a public SHA-256 ranking. The classification below therefore cannot cherry-pick favorable examples after seeing their content.

## Classification vocabulary

- **confirmed_navigation_gap** — current protocol/research/architecture/security material that should have a human-visible inbound navigation path.
- **intentional_project_memory** — a structured conversation record required by project preservation rules; retain it without manufacturing a per-record backlink solely to satisfy the warning metric.
- **reference_evidence** — a finding/source note retained as evidence for project reasoning; category-level discoverability is sufficient unless a current canonical document depends on it directly.
- **uncertain** — evidence is insufficient; make no structural change.

## Evidence rules used

[`PROJECT_RULES.md`](../../PROJECT_RULES.md) requires substantive project conversations to be preserved under `docs/conversations/` and says findings belong under `docs/findings/`. It also says conversation archives are not substitutes for canonical maintenance: durable conclusions should be promoted into decisions, architecture, research, governance, or implementation artifacts.

[`EVOLUTION_ARTIFACT_MINIMIZATION.md`](../architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md) independently distinguishes deliberate curated project-chat memory from indiscriminate retention of raw GitHub input.

Therefore an archived conversation can be a legitimate durable record even when it is not a primary navigation destination.

## Frozen cohort review

| Rank | Candidate | Classification | Evidence / action |
| ---: | --- | --- | --- |
| 1 | `docs/conversations/2026-08-28-target-execution-convergence-followup.md` | intentional_project_memory | Path is inside the repository-mandated conversation archive. Preserve; no per-record backlink added in this cohort. |
| 2 | `docs/community/ACE_LINEAGE_PROTOCOL.md` | confirmed_navigation_gap | This is an active experimental evidence protocol defining ACE parent → seed → descendant semantics and a schema contract. Added to the curated docs navigation page. |
| 3 | `docs/research/R2_SCALE_REGIME_SWEEP.md` | confirmed_navigation_gap | Active #31 research layer with runnable scale/churn/staleness experiments and result semantics. Added to the curated docs navigation page. |
| 4 | `docs/findings/2026-08-28-agent-ecosystem-and-idkmesh-evolution.md` | reference_evidence | Explicit `Finding` document preserving external-ecosystem evidence behind the integration-first / Verified Swarm Runner direction. Canonical direction already lives in current architecture/evolution artifacts; retain as evidence. |
| 5 | `docs/conversations/2026-08-28-free-resource-mesh-integration-outcome.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |
| 6 | `docs/conversations/2026-08-28-framework-and-multidisciplinary-collaboration.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |
| 7 | `docs/conversations/2026-08-28-continue-ace-consolidation-and-live-capacity.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |
| 8 | `docs/architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md` | confirmed_navigation_gap | Current post-#148 architecture/hardening rule governing retained evolution evidence. Added to the curated docs navigation page. |
| 9 | `docs/findings/science-blockchain-sources-2026-08-28.md` | reference_evidence | The document explicitly identifies itself as external source/evidence notes, not a claim or current execution contract. Preserve as evidence; no forced per-file link. |
| 10 | `docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md` | confirmed_navigation_gap | Active synthetic reference experiment for issue #14 and ADR-0007; includes reproducible runner/results and negative trade-offs. Added to docs navigation. |
| 11 | `docs/conversations/2026-08-28-run-evidence-and-replay-continuation.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |
| 12 | `docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md` | confirmed_navigation_gap | Active #30 synthetic experiment with runnable commands, explicit negative-result fields, and held-out real-task next steps. Added to docs navigation. |
| 13 | `docs/security/ACE_THREAT_MODEL.md` | confirmed_navigation_gap | Current security review of a privileged `pull_request_target` workflow and its fail-closed authorization/controller-memory boundaries. Added to docs navigation. |
| 14 | `docs/conversations/2026-08-28-repository-audit-resource-contract-boundary.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |
| 15 | `docs/conversations/2026-08-28-verification-orchestration-collaboration.md` | intentional_project_memory | Required conversation-history class; no per-record metric-driven backlink. |

## Cohort result

Classification counts:

```text
confirmed_navigation_gap = 6
intentional_project_memory = 7
reference_evidence = 2
uncertain = 0
```

For this **single deterministic cohort only**:

```text
confirmed-action rate = 6 / 15 = 40%
intentional archive/reference rate = 9 / 15 = 60%
```

Do not generalize these percentages to the entire warning population from one sample. They are evidence that the detector is useful as a candidate generator but too coarse to authorize automatic repair or deletion.

## Correction strategy

The six confirmed gaps share one root cause: IDKMesh had no `docs/README.md` navigation layer.

Rather than add six unrelated backlinks, this cohort adds one curated documentation entrypoint linking the active protocol/research/architecture/security documents and explaining the archive/reference policy.

This is deliberately different from bulk warning suppression:

- every corrected file was present in the frozen sample;
- every correction has content-based evidence;
- all nine archive/reference warnings remain visible to the deterministic detector unless its semantics are separately changed and reviewed;
- no document is moved/deleted/rewritten;
- no semantic classification is performed automatically.

## Expected observatory effect

Because the new `docs/README.md` provides real Markdown inbound links to the six confirmed active documents, those six should leave the orphan-candidate set on the PR merge ref.

The nine intentional archive/reference files are expected to **remain warnings**. That is desirable: the cohort evidence is testing warning precision, not trying to force the total count toward zero.

The total repository orphan count may still change for unrelated concurrent documentation additions. Acceptance is therefore based on the **six frozen candidate paths**, not on a global warning-count target.

## Follow-up

1. Verify on CI that all six confirmed paths are no longer emitted as `orphan_document_candidate` findings.
2. Verify the nine intentional archive/reference paths remain warning candidates unless independently linked by concurrent work.
3. Preserve this cohort as a calibration set for future detector refinements.
4. Sample another cohort with a new public seed only after this one is integrated and its reviewer effort is recorded.
5. Consider a future warning taxonomy that can distinguish archive/reference collections from active navigation surfaces, but do not encode that policy from one cohort alone.
