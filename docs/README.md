# IDKMesh Documentation Navigation

This directory contains architecture, research, security, community, findings, audits, and project-history records.

This page is a **curated navigation layer, not an exhaustive catalog**. IDKMesh preserves substantially more evidence than a newcomer should have to read. A document being absent from this page does not mean it is obsolete, and an `orphan_document_candidate` warning does not by itself mean a file should be linked, moved, or deleted.

For the project front door, start with [`../README.md`](../README.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md), and [`../COMMUNITY.md`](../COMMUNITY.md).

## Active subsystem documents from IDKGraph P1 cohort 1

The first deterministic orphan-warning cohort in issue #152 identified these active documents as genuine navigation gaps. They are linked here because they are current protocol, research, architecture, or security surfaces rather than archival records.

### Community / ACE

- [ACE Lineage Protocol v0.1](community/ACE_LINEAGE_PROTOCOL.md) — machine-readable parent → seed → descendant evidence semantics for Autocatalytic Community Evolution.

### Randomness and swarm research

- [R1 — Swarm Diversity vs Replication](research/R1_SWARM_DIVERSITY_EXPERIMENT.md) — synthetic mechanism test for when structural diversity helps or hurts relative to replication.
- [R2 Scale and Regime Sweep](research/R2_SCALE_REGIME_SWEEP.md) — scale/churn/staleness sweep for randomized local scheduling.
- [Verification Backpressure Temporal Benchmark](research/VERIFICATION_BACKPRESSURE_BENCHMARK.md) — multi-window benchmark for verification-debt scheduling and generation backpressure.

### Evolution architecture

- [Integrated Iteration Model](../ITERATION_MODEL.md) — canonical system identity, action contract, improvement rule, learning semantics, and end-to-end evolution algorithm.
- [Evolution Artifact Minimization](architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md) — retain the minimum evidence needed to reproduce and review repository-evolution decisions.

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

Do not optimize warning count as a standalone repository-health objective.
