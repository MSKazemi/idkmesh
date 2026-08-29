# Findings Index

This directory holds research and engineering findings: analyses, landscape
studies, evidence reviews, and external source notes. A finding records what was
observed and what it implied **at its stated date**. It is not a canonical
contract, and it does not by itself authorize an implementation.

Canonical current authority lives in
[`../decisions/`](../decisions/), [`../specifications/README.md`](../specifications/README.md),
[`../architecture/README.md`](../architecture/README.md), and
[`../../PROJECT_RULES.md`](../../PROJECT_RULES.md). Where a finding and a canonical
artifact disagree, the canonical artifact wins.

The groups below separate findings that still state a working project thesis from
findings that are retained as historical or source material, because the directory
listing alone does not distinguish them.

## Working theses and program framing

These findings still express positions the project actively builds on, and are
referenced by open research issues.

- [Distributed Agent Coding and Collective Software Engineering](distributed-agent-coding.md)
  — the many-weaker-agents hypothesis, its failure modes, and the quality
  pipeline it requires. Cited by issue #2.
- [Emergence from Vague Goals](2026-08-28-emergence-from-vague-goals.md) —
  nature-inspired argument that variation plus constraints, selection, memory,
  and verification, not vagueness alone, can produce coherent systems.
  Cited by issue #22; measured against baselines in experiment
  [E024](../../experiments/E024-matched-budget-emergence.md).
- [Current Agent Ecosystem and the IDKMesh Evolution Wedge](2026-08-28-agent-ecosystem-and-idkmesh-evolution.md)
  — external-ecosystem review concluding that IDKMesh should integrate rather
  than recreate generic agent infrastructure.
- [Open-Source Community, Collaboration, and Platform Strategy](open-source-community-and-platform.md)
  — how an open contribution surface coexists with a tightly verified canonical
  product.

## Repository-health and navigation evidence

Bounded reviews produced under issue #152. Each records a source revision, a
measured observatory delta, and the reviewer judgement behind it. None of them
treats a lower warning count as a standalone objective.

- [IDKGraph Orphan-Warning Triage — cohort 001](2026-08-29-idkgraph-orphan-warning-triage.md)
  — the first sampled, seeded classification of orphan candidates.
- [IDKGraph Architecture Navigation Pass](2026-08-29-idkgraph-architecture-navigation.md)
  — indexing `docs/architecture/` by declared document status.
- [Conversation Index Drift Review](2026-08-29-conversation-index-drift.md) —
  the archive index had fallen behind the archive; repair and measured effect.
- [Conversation Index Regression](2026-08-29-conversation-index-regression.md) —
  the follow-on drift that motivated the deterministic index guard test.
- [IDKGraph Findings Navigation Pass](2026-08-29-idkgraph-findings-navigation.md)
  — this directory's own bounded pass: classification of all 15 findings and the
  measured effect of adding this index.
- [First Production Collaboration-Observables Snapshot](2026-08-29-collaboration-observables-first-snapshot.md)
- [Ownership Concentration: First Real Measurement](2026-08-30-ownership-concentration-first-measurement.md)
- [Five Committed Executables That Nothing Demonstrates Ever Ran](2026-08-30-executables-nothing-ever-ran.md)
- [Replaying the Node Evidence: One Digest Reproduces, Four Cannot](2026-08-30-node-evidence-replay-and-digest-reproducibility.md)
  — the only production run the observables pipeline has produced, committed
  before its 30-day artifact retention expired; which of its six zero-valued
  observables are real measurements and which are declared collector limitations.

## Growth, discovery, and free-compute landscape

- [Fast Growth and Free Compute Audit](2026-08-28-fast-growth-and-free-compute-audit.md)
  — diagnosis that the project was external-attention starved rather than
  compute starved.
- [Repository-Driven Community Growth](2026-08-28-repository-driven-community-growth.md)
  — the contribution flywheel and the `R_c` community-reproduction metric.
  Cited by issue #10.
- [Free / Low-Cost Agent Network Landscape](2026-08-28-free-agent-network-landscape.md)
  — the zero-cost hosted and volunteer-local compute options available to the
  project.

## Historical records and source notes

Retained as project memory and evidence references. They are **not** current
guidance, and the source notes do not imply that the cited authors endorse
IDKMesh.

- [Initial Landscape Findings](2026-08-28-initial-landscape.md) — naming
  decision, the NovaFabric distinction, and the first "scale does not imply
  quality" principle.
- [Reference Map and Lessons from Bitcoin/Crypto](2026-08-28-reference-map-and-crypto-lessons.md)
  — long reference map; reuse the distributed-systems ideas before the monetary
  layer.
- [Issue Resolution and Work Unit Track Closure](2026-08-29-issue-resolution-and-work-unit-track-closure.md)
  — record of the pass that converged the Work Unit protocol track.
- [Science and Blockchain Source Notes](science-blockchain-sources-2026-08-28.md)
  — external citations behind the statistical-mechanics, gossip, and percolation
  arguments.

## Adding a finding

Give the file a dated name, state the date and scope in the document, and add one
line to the group above that it belongs to. If a finding later becomes binding,
promote its conclusion into a decision, specification, or architecture document
rather than upgrading the finding's authority in place.
