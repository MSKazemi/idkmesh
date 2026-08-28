# Specifications

These documents define IDKMesh's versioned data, evaluation, repository-graph,
and project-configuration contracts. A status of experimental means the
contract can gain a new version; it does not permit silently changing the
meaning of an existing version.

## Work and Evidence Contracts

- [Benchmark Cohort Index v0.1](BENCHMARK_COHORT_V0_1.md) — freezes a replayable
  task set over existing WorkUnit and evaluator objects.
- [Worker ResultManifest v0.1](RESULT_MANIFEST_V0_1.md) — records worker-produced
  artifacts and claims without granting acceptance authority.
- [Run Evidence Report v0.1](RUN_EVIDENCE_REPORT_V0_1.md) — aggregates attempt
  and independent-verification evidence for human inspection.
- [Verification Provenance Integrity](VERIFICATION_PROVENANCE_INTEGRITY.md) —
  binds WorkUnit, result, and verification objects with canonical digests.

## Evaluation Contracts

- [Bound Unified-Diff Evaluator Backend](PATCH_EVALUATOR_BACKEND.md) — verifies
  untrusted patch bundles against an evaluator-owned plan.
- [EvaluatorPlan v0.3 Semantic Matching](EVALUATOR_PLAN_V0_3_SEMANTIC_MATCHING.md)
  — preserves the historical added-substring matching contract.
- [EvaluatorPlan v0.4 Transition Semantics](EVALUATOR_PLAN_V0_4_TRANSITION_SEMANTICS.md)
  — requires both added and removed transition evidence.

## Repository Graph Contracts

- [IDKGraph Repository Mapping v0.1](IDKGRAPH_REPOSITORY_MAPPING_V0_1.md) — maps
  explicit repository structure into deterministic typed graph facts.
- [IDKGraph P0 Observatory v0.1](IDKGRAPH_OBSERVATORY_V0_1.md) — composes the
  read-only graph and health checks into one replayable command.
- [IDKGraph P0 Residual Health Checks](IDKGRAPH_P0_RESIDUAL_HEALTH_CHECKS.md) —
  defines warning-only orphan and accepted-decision linkage rules.

## Project Configuration

- [ProjectManifest and DomainPack Interfaces](PROJECT_DOMAIN_INTERFACES.md) —
  separates reusable coordination core from declarative domain and project
  policy.

When modifying a contract, update its schema, fixtures, implementation, and
tests together. Introduce a new explicit version when behavior changes; keep
old frozen evidence interpretable under its original meaning.
