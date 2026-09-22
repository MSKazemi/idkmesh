# IDKMesh Documentation Navigation

This directory contains current architecture/specifications, research programs, security/community material, evidence, audits, findings, and historical project records.

This page is a **curated navigation and authority map, not an exhaustive catalog**. IDKMesh intentionally retains substantially more evidence than a newcomer should need to read.

For the public front door, start with [`BEGINNER_GUIDE.md`](BEGINNER_GUIDE.md) if you want a plain-language explanation, then continue with [`../README.md`](../README.md), [`GETTING_STARTED.md`](GETTING_STARTED.md), [`PROJECT_ADOPTION_GUIDE.md`](PROJECT_ADOPTION_GUIDE.md) if you want to use IDKMesh with another repository, [`../CONTRIBUTING.md`](../CONTRIBUTING.md), and [`../COMMUNITY.md`](../COMMUNITY.md).

## Current productization initiative

The current productization track turns the existing WorkUnit/worker/verification
foundation into an easy-to-connect GitHub + agent + model platform, then uses that
platform first on IDKMesh itself and next on a separate application.

Read in this order:

1. [Agent and Model Connector Control Plane](architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md) — system boundaries and connector architecture.
2. [Connector Control API v0.1](specifications/CONNECTOR_CONTROL_API_V0_1.md) — configuration, run, webhook, secret-reference, and error contract.
3. [Agent/Model Integration and Self-Hosting Plan](planning/AGENT_MODEL_INTEGRATION_SELF_HOSTING_PLAN_2026-09-22.md) — implementation sequence and Loop A/Loop B graduation gates.
4. [Model-Tier Dispatcher and Connector Routing](planning/MODEL_TIER_DISPATCHER_EXECUTION_PLAN_2026-09-22.md) — capability/authority routing, connector admission, escalation, and the exact #574 implementation breakdown.
4. [Live GitHub tracker #570](https://github.com/MSKazemi/idkmesh/issues/570) — current implementation state and bounded work queue.

The planned connector API is **not yet a finished capability on `main`**. Keep
implemented behavior, design contracts, and future milestones distinct.

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
| durable decisions | [`../DECISIONS.md`](../DECISIONS.md), [`decisions/`](decisions/README.md) |
| bounded review snapshots | [`audits/`](audits/README.md) |
| research/engineering findings | [`findings/`](findings/README.md) |
| community growth and the ACE stack | [`community/`](community/README.md) |
| append-only collaboration history | [`conversations/`](conversations/README.md) |

A conversation, old roadmap section, experiment note, or historical architecture sketch is evidence about project evolution; it does **not** automatically override current schemas, current architecture documents, or later accepted decisions.

## Current system map

For a newcomer trying to understand the executable foundation, this order is usually enough:

1. [`../README.md`](../README.md) — what exists and what does not;
2. [`GETTING_STARTED.md`](GETTING_STARTED.md) — the shortest current paths to run the contract demo, use `idkmesh gate-audit`, integrate the Action, or start contributing;
3. [`PROJECT_ADOPTION_GUIDE.md`](PROJECT_ADOPTION_GUIDE.md) — practical external-project workflow from GitHub setup through humans/agents, Work Units, verification, and protected integration;
4. [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — end-to-end work/evidence/authority path;
5. [`../schemas/README.md`](../schemas/README.md) — canonical machine-readable contracts;
6. [`specifications/README.md`](specifications/README.md) — written contract index;
7. [`architecture/README.md`](architecture/README.md) — subsystem architecture;
8. [`research/README.md`](research/README.md) — experiment/evidence program;
9. [`../ROADMAP.md`](../ROADMAP.md) — current evidence gates and next progression.

## Documentation indexes

- [Architecture index](architecture/README.md) — active system, compute, evidence, repository-evolution, CI, and retained historical designs.
- [Specifications index](specifications/README.md) — versioned work, evidence, evaluator, repository-graph, and project-configuration contracts.
- [Research index](research/README.md) — research programs, experiments, verification studies, and benchmark-calibration evidence.
- [Findings index](findings/README.md) — working theses, repository-health evidence, growth/landscape studies, and retained source notes.
- [Audits index](audits/README.md) — bounded review snapshots with the baseline revision each one declares.
- [Community and ACE index](community/README.md) — growth strategy, measurement models, the layered ACE control stack, and its bounded experiments.

## Important active subsystem documents

### Agent development automation

- [Jules development automation](operations/JULES_AUTOMATION.md) — who may mark work `agent-ready`, how the dispatcher adds `jules`, event-driven and recovery frequencies, concurrency/backpressure, veto labels, failure recovery, and the no-auto-merge boundary.

### Work, evidence, and interoperability

- [`../schemas/README.md`](../schemas/README.md) — current WorkUnit/ResultManifest/VerificationResult and related schema versions.
- [WorkUnit composability](specifications/WORK_UNIT_COMPOSABILITY_V0_2.md) — decomposition benchmark and evidence boundary.
- [A2A/MCP mapping](interoperability/A2A_MCP_MAPPING_V0_1.md) — external protocol bindings without redefining the WorkUnit semantic core.
- [Agent interoperability architecture](interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md) — identity/provenance and adapter boundary.
- [Agent interoperability monitoring update — 2026-09-10](../interop/AGENT_INTEROPERABILITY_UPDATE_2026-09-10.md) — material A2A/ARD, MCP Skills/security, OpenHands/ACP, provenance, sandbox, and information-flow developments with maturity labels and implementation priorities.

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

### Contribution surface and public front door

- [AI Agent Verification, Orchestration, and Trust Topics](topics/README.md) — search-oriented, evidence-linked guides for agent verification, multi-agent orchestration, AI code review, evaluator reliability, provenance, governance, MCP/A2A interoperability, verification scaling, and verified swarm engineering.
- [IDKMesh for Absolute Beginners](BEGINNER_GUIDE.md) — plain-language explanation of what IDKMesh is, what problem it solves, what is usable today, and the first commands to try.
- [Getting Started: Using IDKMesh](GETTING_STARTED.md) — practical newcomer paths for the contract demo, the `idkmesh gate-audit` CLI, GitHub Actions integration, contribution setup, and the implemented-vs-planned product boundary.
- [Use IDKMesh to Build Another Software Project](PROJECT_ADOPTION_GUIDE.md) — external-project adoption flow: repository setup, ProjectManifest/DomainPack policy, bounded Work Units, human/agent/model connection patterns, verification, and protected integration.
- [Gate Audit v0.1 specification](specifications/GATE_AUDIT_V0_1.md) — the user-facing contract for the dependency-free `idkmesh gate-audit` CLI installed by `pip install .`, including accepted input, exit/error behavior, JSON/Markdown outputs, and the diagnostic-only authority boundary.
- [Multidisciplinary Collaboration in IDKMesh](CONTRIBUTOR_PERSPECTIVES.md) —
  the contribution tracks a newcomer can enter from, and the rule that different
  perspectives are composed rather than forced into premature agreement.
- [GitHub Pages Front Door — Activation Runbook](PAGES_SETUP.md) — the
  dependency-free landing page, its activation and reverification procedure, and
  what the page is allowed to claim. Implementation surface for
  [ADR-0011](decisions/ADR-0011-discovery-surface-completion.md).
- [Artistic Inspiration: M. C. Escher](design/ARTISTIC_INSPIRATION_M_C_ESCHER.md)
  — recursion, local rules producing global order, self-reference, and
  composability as conceptual framing. Inspiration at the level of ideas, not a
  visual or branding directive.

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
