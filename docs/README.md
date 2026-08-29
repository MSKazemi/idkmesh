# IDKMesh Documentation Navigation

This directory contains current architecture/specifications, research programs, security/community material, evidence, audits, findings, and historical project records.

This page is a **curated navigation and authority map, not an exhaustive catalog**. IDKMesh intentionally retains substantially more evidence than a newcomer should need to read.

For the public front door, start with [`../README.md`](../README.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md), and [`../COMMUNITY.md`](../COMMUNITY.md).

## How to read the documentation

Different documents serve different roles. When two files appear to disagree, prefer the more specific current contract over older plans/history.

| Role | Primary source |
| --- | --- |
| project identity and current public status | [`../README.md`](../README.md) |
| canonical evolution vocabulary / authority lifecycle | [`../ITERATION_MODEL.md`](../ITERATION_MODEL.md) |
| high-level current architecture | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| machine-readable protocol truth | [`../schemas/`](../schemas/README.md) |
| versioned written specifications | [`specifications/`](specifications/README.md) |
| current architecture details | [`architecture/`](architecture/README.md) |
| research questions/programs/evidence | [`research/`](research/README.md) |
| current staged next gates | [`../ROADMAP.md`](../ROADMAP.md), [`../EVOLUTION.md`](../EVOLUTION.md) |
| governance / authority | [`../GOVERNANCE.md`](../GOVERNANCE.md), [`../CONSTITUTION.md`](../CONSTITUTION.md) |
| durable decisions | [`../DECISIONS.md`](../DECISIONS.md), [`decisions/`](decisions/) |
| bounded review snapshots | [`audits/`](audits/README.md) |
| research/engineering findings | [`findings/`](findings/README.md) |
| community growth and the ACE stack | [`community/`](community/README.md) |
| append-only collaboration history | [`conversations/`](conversations/README.md) |

A conversation, old roadmap section, experiment note, or historical architecture sketch is evidence about project evolution; it does **not** automatically override current schemas, current architecture documents, or later accepted decisions.

## Current system map

For a newcomer trying to understand the executable foundation, this order is usually enough:

1. [`../README.md`](../README.md) — what exists and what does not;
2. [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — end-to-end work/evidence/authority path;
3. [`../schemas/README.md`](../schemas/README.md) — canonical machine-readable contracts;
4. [`specifications/README.md`](specifications/README.md) — written contract index;
5. [`architecture/README.md`](architecture/README.md) — subsystem architecture;
6. [`research/README.md`](research/README.md) — experiment/evidence program;
7. [`../ROADMAP.md`](../ROADMAP.md) — current evidence gates and next progression.

## Documentation indexes

- [Architecture index](architecture/README.md) — active system, compute, evidence, repository-evolution, CI, and retained historical designs.
- [Specifications index](specifications/README.md) — versioned work, evidence, evaluator, repository-graph, and project-configuration contracts.
- [Research index](research/README.md) — research programs, experiments, verification studies, and benchmark-calibration evidence.
- [Findings index](findings/README.md) — working theses, repository-health evidence, growth/landscape studies, and retained source notes.
- [Audits index](audits/README.md) — bounded review snapshots with the baseline revision each one declares.
- [Community and ACE index](community/README.md) — growth strategy, measurement models, the layered ACE control stack, and its bounded experiments.

## Important active subsystem documents

### Work, evidence, and interoperability

- [`../schemas/README.md`](../schemas/README.md) — current WorkUnit/ResultManifest/VerificationResult and related schema versions.
- [WorkUnit composability](specifications/WORK_UNIT_COMPOSABILITY_V0_2.md) — decomposition benchmark and evidence boundary.
- [A2A/MCP mapping](interoperability/A2A_MCP_MAPPING_V0_1.md) — external protocol bindings without redefining the WorkUnit semantic core.
- [Agent interoperability architecture](interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md) — identity/provenance and adapter boundary.

### Community / ACE

- [Community and ACE index](community/README.md) — every community document by layer, with the authority each one declares.
- [ACE Lineage Protocol v0.1](community/ACE_LINEAGE_PROTOCOL.md) — machine-readable parent → seed → descendant evidence semantics.
- [ACE Bootstrap Experiment](community/ACE_BOOTSTRAP_EXPERIMENT.md) — bounded cohort/evidence rules.
- [`../COMMUNITY_GROWTH_ENGINE.md`](../COMMUNITY_GROWTH_ENGINE.md) — growth model, capacity, and safeguards.

### Research and verification

- [R1 — Swarm Diversity vs Replication](research/R1_SWARM_DIVERSITY_EXPERIMENT.md) — synthetic mechanism test for structural diversity vs replication.
- [R2 Scale and Regime Sweep](research/R2_SCALE_REGIME_SWEEP.md) — randomized local scheduling under scale/churn/staleness.
- [Verification Backpressure Temporal Benchmark](research/VERIFICATION_BACKPRESSURE_BENCHMARK.md) — generation/verification debt dynamics.
- [Coordination Criticality and Finite-Difference Response](research/CRITICALITY_AND_FLUCTUATION_RESPONSE.md) — overload-warning experiment.

### Repository evolution

- [Integrated Iteration Model](../ITERATION_MODEL.md) — canonical event/action/iteration/improvement/learning definitions.
- [Self-Evolving Repository](architecture/SELF_EVOLVING_REPOSITORY.md) — guarded proposal/evaluation architecture.
- [Mathematical Evolution Kernel](architecture/MATHEMATICAL_EVOLUTION_KERNEL.md) — reusable evolution-control primitives.
- [Conjunctive Evolution Control](architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md) — non-compensating hard-guard composition.
- [Evolution Artifact Minimization](architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md) — retain reproducible evidence without unnecessary untrusted content.
- [CI Shadow Planner](architecture/CI_SHADOW_PLANNER.md) and [CI Shadow Outcome Evaluator](architecture/CI_SHADOW_OUTCOME_EVALUATOR.md) — advisory exact-revision CI planning/evaluation without skip or merge authority.

### Security

- [ACE GitHub Workflow Threat Model](security/ACE_THREAT_MODEL.md) — trust boundaries and fail-closed requirements for privileged ACE workflows.
- [`../SECURITY.md`](../SECURITY.md) — project vulnerability-reporting boundary.

## Evidence classification

A major source of documentation confusion is treating every artifact as the same kind of truth. Use this ladder:

```text
proposal / hypothesis
 -> implemented mechanism
 -> synthetic fixture or simulation
 -> observed controlled evidence
 -> scoped accepted conclusion
```

The repository often intentionally stops at an earlier stage. For example, a benchmark contract plus synthetic fixture means the experiment is runnable; it does not mean a strategy has already been shown superior.

## Archive and evidence collections

Some records are intentionally preserved as **project memory or evidence**, not primary navigation destinations.

- [`conversations/`](conversations/README.md) contains structured records of substantive project conversations required by [`../PROJECT_RULES.md`](../PROJECT_RULES.md). Important conclusions should also be promoted into canonical architecture, decisions, research, governance, or implementation artifacts.
- [`findings/`](findings/README.md) contains research/engineering findings and source/evidence notes. Some are historical support for later decisions rather than current implementation documentation; the index separates the two.
- [`audits/`](audits/README.md) contains bounded reviews and evidence snapshots. They remain useful after findings are resolved because they preserve what was inspected and why a decision changed. Read each as a snapshot at its stated baseline, not as current status.
- [`evidence/`](evidence/) contains retained evidence artifacts where a subsystem requires a durable evidence surface.

For these collections, **category-level discoverability can be sufficient**. Do not manufacture one inbound link per archival record merely to reduce a warning counter.

## IDKGraph warning discipline

The repository observatory deliberately emits warning candidates rather than semantic deletion/rewrite decisions.

The rule is:

```text
warning candidate
 -> bounded reproducible sample
 -> inspect repository evidence
 -> classify
 -> fix only confirmed navigation/correctness defects
 -> preserve intentional archive/reference cases
```

Relevant records include:

- [IDKGraph P1 orphan cohort 1](audits/2026-08-28-idkgraph-p1-orphan-cohort-1.md);
- [IDKGraph architecture navigation pass](findings/2026-08-29-idkgraph-architecture-navigation.md);
- [Conversation index drift review](findings/2026-08-29-conversation-index-drift.md);
- [IDKGraph P1 ADR-0011 linkage review](audits/2026-08-29-idkgraph-p1-adr-0011-linkage.md);
- [IDKGraph findings navigation pass](findings/2026-08-29-idkgraph-findings-navigation.md).

Do not optimize warning count as a standalone repository-health objective.

## Documentation maintenance rule

When code/schema/workflow behavior changes, update the smallest canonical documentation surface that describes that behavior. Prefer:

- correcting current README/architecture/spec/roadmap text;
- preserving historical records unchanged;
- adding a finding/audit when a correction requires explanation;
- relying on deterministic link checks and tests rather than manually asserting that navigation is valid.

The documentation should make a clear distinction between **what the repository can execute today**, **what has only been tested synthetically**, and **what remains a long-term hypothesis**.
