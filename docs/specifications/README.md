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

- [Work Unit Composability Profile v0.2](WORK_UNIT_COMPOSABILITY_V0_2.md) —
  experimental reference profile adding the five-arm decomposition benchmark
  contract and a canonical WorkUnit DAG without changing either historical
  WorkUnit schema. Related: issues #3, #15, #17.

## Evaluation Contracts

- [Gate Audit v0.1](GATE_AUDIT_V0_1.md) — the `idkmesh gate-audit` CLI contract:
  measures a verifier panel's effective independent votes, correlation
  structure, and seeded-probe breach rate from a verdict matrix; diagnostic
  only, no acceptance authority.
- [Bound Unified-Diff Evaluator Backend](PATCH_EVALUATOR_BACKEND.md) — verifies
  untrusted patch bundles against an evaluator-owned plan.
- [EvaluatorPlan v0.3 Semantic Matching](EVALUATOR_PLAN_V0_3_SEMANTIC_MATCHING.md)
  — preserves the historical added-substring matching contract.
- [EvaluatorPlan v0.4 Transition Semantics](EVALUATOR_PLAN_V0_4_TRANSITION_SEMANTICS.md)
  — requires both added and removed transition evidence.

- [EvaluatorPlan v0.4 Calibrated Transformation Semantics](EVALUATOR_PLAN_V0_4_TRANSFORMATION_CALIBRATION.md)
  — experimental P0 calibration contract for issue #157; adds a metadata-only
  transformation requirement so neither an exact-line false negative nor an
  inert-substring false positive passes.

## Repository Graph Contracts

- [IDKGraph Repository Mapping v0.1](IDKGRAPH_REPOSITORY_MAPPING_V0_1.md) — maps
  explicit repository structure into deterministic typed graph facts.
- [IDKGraph P0 Observatory v0.1](IDKGRAPH_OBSERVATORY_V0_1.md) — composes the
  read-only graph and health checks into one replayable command.
- [IDKGraph P0 Residual Health Checks](IDKGRAPH_P0_RESIDUAL_HEALTH_CHECKS.md) —
  defines warning-only orphan and accepted-decision linkage rules.
- [GitHub to IDKGraph Projection v0.1](GITHUB_IDKGRAPH_PROJECTION_V0_1.md) —
  deterministically joins normalized GitHub activity to the repository graph
  without granting write or execution authority.

## Project Configuration

- [ProjectManifest and DomainPack Interfaces](PROJECT_DOMAIN_INTERFACES.md) —
  separates reusable coordination core from declarative domain and project
  policy.

When modifying a contract, update its schema, fixtures, implementation, and
tests together. Introduce a new explicit version when behavior changes; keep
old frozen evidence interpretable under its original meaning.
