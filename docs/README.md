# IDKMesh Documentation Navigation

This directory contains architecture, research, security, community, findings, audits, and project-history records.

This page is a **curated navigation layer, not an exhaustive catalog**. IDKMesh preserves substantially more evidence than a newcomer should have to read. A document being absent from this page does not mean it is obsolete, and an `orphan_document_candidate` warning does not by itself mean a file should be linked, moved, or deleted.

For the project front door, start with [`../README.md`](../README.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md), and [`../COMMUNITY.md`](../COMMUNITY.md).

## Documentation indexes

- [Architecture index](architecture/README.md) — active system, compute,
  evidence, repository-evolution, CI, and retained historical designs.
- [Specifications index](specifications/README.md) — versioned work, evidence,
  evaluator, repository-graph, and project-configuration contracts.
- [Research index](research/README.md) — research programs, experiments,
  verification studies, and benchmark-calibration evidence.

## Active subsystem documents from IDKGraph P1 cohort 1

The first deterministic orphan-warning cohort in issue #152 identified these active documents as genuine navigation gaps. They are linked here because they are current protocol, research, architecture, or security surfaces rather than archival records.

### Community / ACE

- [ACE Lineage Protocol v0.1](community/ACE_LINEAGE_PROTOCOL.md) — machine-readable parent → seed → descendant evidence semantics for Autocatalytic Community Evolution.

### Randomness and swarm research

- [R1 — Swarm Diversity vs Replication](research/R1_SWARM_DIVERSITY_EXPERIMENT.md) — synthetic mechanism test for when structural diversity helps or hurts relative to replication.
- [R2 Scale and Regime Sweep](research/R2_SCALE_REGIME_SWEEP.md) — scale/churn/staleness sweep for randomized local scheduling.
- [Verification Backpressure Temporal Benchmark](research/VERIFICATION_BACKPRESSURE_BENCHMARK.md) — multi-window benchmark for verification-debt scheduling and generation backpressure.
- [Coordination Criticality and Finite-Difference Response](research/CRITICALITY_AND_FLUCTUATION_RESPONSE.md) — matched load probes and ordinary queue-threshold baselines for early overload warning.
- [Task 001 Symlink-Boundary Calibration](research/PHASE_B2_V2_TASK001_SYMLINK_CALIBRATION.md) — ordering-sensitive path-boundary calibration for the final successor-v2 task.
- [Task 004 Non-Finite RWVB Calibration](research/PHASE_B2_V2_TASK004_NONFINITE_RWVB_CALIBRATION.md) — pre-freeze evaluator and behavioral calibration for finite controller inputs.

### Evolution architecture

- [Integrated Iteration Model](../ITERATION_MODEL.md) — canonical system identity, action contract, improvement rule, learning semantics, and end-to-end evolution algorithm.
- [Evolution Artifact Minimization](architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md) — retain the minimum evidence needed to reproduce and review repository-evolution decisions.
- [CI Shadow Planner v0.1](architecture/CI_SHADOW_PLANNER.md) — exact-revision, dependency-closed CI planning in advisory shadow mode.
- [CI Shadow Outcome Evaluator v0.1](architecture/CI_SHADOW_OUTCOME_EVALUATOR.md) — joins exact-head plans to observed checks without gaining execution or merge authority.

### Security

- [ACE GitHub Workflow Threat Model](security/ACE_THREAT_MODEL.md) — trust boundaries and fail-closed requirements for ACE's privileged GitHub workflow.

## Archive and evidence collections

Some IDKMesh records are intentionally preserved as **project memory or evidence**, not as primary navigation destinations.

- [`conversations/`](conversations/) contains structured records of substantive project conversations required by [`../PROJECT_RULES.md`](../PROJECT_RULES.md). Important conclusions should also be promoted into canonical architecture, decisions, research, governance, or implementation artifacts.
- [`findings/`](findings/) contains research findings and source/evidence notes. Some are historical evidence for a decision rather than current implementation documentation.
- [`audits/`](audits/) contains bounded reviews and evidence snapshots. They should remain reproducible records even after their findings are resolved or superseded.

For these collections, **category-level discoverability can be sufficient**. The project should not manufacture one inbound Markdown link per archival record merely to reduce a warning counter. If a record becomes an active dependency for current work, link it from the relevant canonical document.

## IDKGraph warning discipline

The deterministic repository observatory intentionally emits warning candidates rather than semantic deletion/rewrite decisions.

The P1 rule is:

```text
warning candidate
 -> bounded reproducible sample
 -> inspect repository evidence
 -> classify
 -> fix only confirmed navigation defects
 -> preserve intentional archive/reference cases
```

The first cohort classification is recorded in [IDKGraph P1 orphan cohort 1](audits/2026-08-28-idkgraph-p1-orphan-cohort-1.md).
The later bounded architecture-directory correction is recorded in
[IDKGraph architecture navigation pass](findings/2026-08-29-idkgraph-architecture-navigation.md).

Do not optimize warning count as a standalone repository-health objective.
