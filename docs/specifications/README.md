# Specifications

These documents define IDKMesh's versioned data, evaluation, repository-graph,
and project-configuration contracts. A status of experimental means the
contract can gain a new version; it does not permit silently changing the
meaning of an existing version.

## GitHub-First Product Operations

- [GitHub-First Operations v0.1](GITHUB_FIRST_OPERATIONS_V0_1.md) — implementation contract for no-server GitHub coordination: bootstrap, durable run ledger, idempotency/recovery, multi-user claims/authority, Actions security, optional Projects/Pages/OIDC/attestations, and the pilot test matrix.
- [GitHub Webhook Ingress v0.1](GITHUB_WEBHOOK_INGRESS_V0_1.md) — authenticated bounded webhook envelope: raw-body HMAC-SHA256, event/action allowlists, repository binding, delivery provenance, and no dispatch authority.

## Work and Evidence Contracts

- [Benchmark Cohort Index v0.1](BENCHMARK_COHORT_V0_1.md) — freezes a replayable
  task set over existing WorkUnit and evaluator objects.
- [CandidateReference v0.1](CANDIDATE_REFERENCE_V0_1.md) — binds a discovered PR or artifact bundle to an immutable provider-neutral candidate identity without granting verification or integration authority.
- [Worker ResultManifest v0.1](RESULT_MANIFEST_V0_1.md) — records worker-produced
  artifacts and claims without granting acceptance authority.
- [Run Evidence Report v0.1](RUN_EVIDENCE_REPORT_V0_1.md) — aggregates attempt
  and independent-verification evidence for human inspection.
- [Control Tower Local API v0.1](CONTROL_TOWER_LOCAL_API_V0_1.md) — versioned,
  loopback-only read API and presentation contract for Human Control Tower run
  evidence inspection.
- [HTTP Service Runtime Baseline v0.1](HTTP_SERVICE_RUNTIME_V0_1.md) —
  dependency-free request correlation, liveness/readiness, service metadata,
  and payload-free structured access logging for IDKMesh HTTP surfaces.
- [Verification Provenance Integrity](VERIFICATION_PROVENANCE_INTEGRITY.md) —
  binds WorkUnit, result, and verification objects with canonical digests.

- [Work Unit Composability Profile v0.2](WORK_UNIT_COMPOSABILITY_V0_2.md) —
  experimental reference profile adding the five-arm decomposition benchmark
  contract and a canonical WorkUnit DAG without changing either historical
  WorkUnit schema. Related: issues #3, #15, #17.
- [Local Agent Execution Boundary v0.1](LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md) —
  fail-closed C4 contract separating canonical WorkUnit/AgentPreset admission,
  platform-specific sandbox enforcement, bounded outside-authority candidate
  capture, and provider-neutral ResultManifest normalization.

## Evaluation Contracts

- [Gate Audit v0.1](GATE_AUDIT_V0_1.md) — the `idkmesh gate-audit` CLI contract:
  measures a verifier panel's effective independent votes, correlation
  structure, and seeded-probe breach rate from a verdict matrix; diagnostic
  only, no acceptance authority.
- [Marginal Evidence Analysis v0.1](MARGINAL_EVIDENCE_V0_1.md) — the
  `idkmesh gate-marginal` diagnostic contract: measures what one additional
  verifier changes for an already-selected panel under the exact same gate
  rule, with explicit censoring/uncertainty and no routing authority.
- [Marginal Evidence Held-Out Benchmark v0.1](MARGINAL_EVIDENCE_BENCHMARK_V0_1.md) —
  the `idkmesh gate-marginal-benchmark` contract: freezes five design-only
  verifier-selection rules and evaluates them on disjoint holdout rows without
  emitting a production winner or routing decision.
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

## API Conventions

- [API Conventions v0.1](API_CONVENTIONS_V0_1.md) — proposed shared HTTP conventions for namespace/versioning, errors, correlation, pagination, idempotency, concurrency, events, limits, OpenAPI/schema compatibility, deprecation, and deployment security profiles. Issue #736 owns review/freeze.

## Project Configuration

- [Enterprise Control Profile v0.1](ENTERPRISE_CONTROL_PROFILE_V0_1.md) —
  experimental machine-readable enterprise posture and deterministic
  declaration-preflight contract for tenancy, identity/SoD, data/egress,
  secrets, audit, recovery, supply chain, and emergency change.
- [ProjectManifest and DomainPack Interfaces](PROJECT_DOMAIN_INTERFACES.md) —
  separates reusable coordination core from declarative domain and project
  policy.
- [Connector Control API v0.1](CONNECTOR_CONTROL_API_V0_1.md) — experimental
  project-facing connection, dispatch, run-state, webhook, secret-reference,
  agent/model-provider, and error contract above the canonical WorkUnit and
  verification semantics.
- [Product Spine Service v0.1](PRODUCT_SPINE_SERVICE_V0_1.md) — provider-neutral application-service contract that composes WorkUnit, routing, dispatch, candidate normalization, verification, evidence, and Human Decision Record without creating a new correctness or merge authority.
- [Enterprise Tenant Scope v0.1](ENTERPRISE_TENANT_SCOPE_V0_1.md) —
  tenant/project-scoped resource, storage-key, and idempotency foundation with
  fail-closed cross-scope reference checks.
- [Enterprise Authorization Kernel v0.1](ENTERPRISE_AUTHORIZATION_V0_1.md) —
  strict ActorContext + RBAC/ABAC-style policy evaluation over exact tenant/project
  resource scope, including identity freshness, data clearance, risk floors, and
  distinct high-risk approval without executing the requested side effect.

When modifying a contract, update its schema, fixtures, implementation, and
tests together. Introduce a new explicit version when behavior changes; keep
old frozen evidence interpretable under its original meaning.
