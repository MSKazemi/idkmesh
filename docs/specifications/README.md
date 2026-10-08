# Specifications

These documents define IDKMesh's versioned data, evaluation, repository-graph,
and project-configuration contracts. A status of experimental means the
contract can gain a new version; it does not permit silently changing the
meaning of an existing version.

## GitHub-First Product Operations

- [GitHub-First Operations v0.1](GITHUB_FIRST_OPERATIONS_V0_1.md) — implementation contract for no-server GitHub coordination: bootstrap, durable run ledger, idempotency/recovery, multi-user claims/authority, Actions security, optional Projects/Pages/OIDC/attestations, and the pilot test matrix.
- [GitHub Bootstrap Config Rendering v0.1](GITHUB_BOOTSTRAP_CONFIG_RENDERING_V0_1.md) — deterministic C8-C rendering of the ProjectManifest seed, disabled secret-reference connector template, repository-local software-engineering DomainPack, generated ownership README, and content digests; rendering only, with no apply or GitHub mutation authority.
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
  evidence inspection, plus read-only Product Spine run, attempt, retained
  run-evidence ([ADR-0024](../decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)), and derived
  WorkUnit and project views ([ADR-0021](../decisions/ADR-0021-derived-work-unit-and-project-read-models.md)),
  the bounded service limits the development server enforces
  ([ADR-0022](../decisions/ADR-0022-control-tower-bounded-service-limits.md)),
  and the canonical event history and resumable SSE stream
  ([ADR-0023](../decisions/ADR-0023-canonical-append-only-event-source.md)).
- [HTTP Service Runtime Baseline v0.1](HTTP_SERVICE_RUNTIME_V0_1.md) —
  dependency-free request correlation, liveness/readiness, service metadata,
  payload-free structured access logging, and reusable bounded-limit
  primitives for IDKMesh HTTP surfaces.
- [API Observability v0.1](API_OBSERVABILITY_V0_1.md) —
  privacy-safe, fixed-cardinality request/status/latency/admission/concurrency
  telemetry, W3C traceparent v00 pass-through, and explicit local-profile
  SLO/alert targets. The OpenTelemetry exporter remains follow-up work under
  #744.
- [Release Supply-Chain Baseline v0.1](RELEASE_SUPPLY_CHAIN_V0_1.md) —
  release SBOM/checksum/source-workflow identity evidence, immutable-pinned
  GitHub build provenance, consumer verification, and vulnerability/update
  policy for enterprise release integrity (#674).
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
- [Marginal Evidence Cross-Cohort Synthesis v0.1](MARGINAL_EVIDENCE_SYNTHESIS_V0_1.md) —
  the `idkmesh gate-marginal-synthesis` contract: aggregates a frozen set of
  held-out benchmark reports descriptively across cohorts while refusing
  duplicate evidence and emitting no strategy ranking or routing authority.
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

- [API Conventions v0.1](API_CONVENTIONS_V0_1.md) — frozen shared HTTP conventions for namespace/versioning, errors, correlation, pagination, idempotency, concurrency, events, limits, OpenAPI/schema compatibility, deprecation, and deployment security profiles. Frozen by issue #736 / [ADR-0018](../decisions/ADR-0018-freeze-api-conventions-v0-1.md); its error and list envelopes have canonical schemas under `schemas/idkmesh-api-error-v0.1.schema.json` and `schemas/idkmesh-list-v0.1.schema.json`.

## Project Configuration

- [Executor Admission v0.1](EXECUTOR_ADMISSION_V0_1.md) — readiness-checked
  atomic claims: the exact execution binding is derived and claimed in one
  operation, dispatch intent and submission revalidate the admission-time
  input snapshot, and changed upstream inputs fail closed. Local composition
  only; no dispatch, verification, acceptance or merge authority.

- [Coordination Preflight v0.1](COORDINATION_PREFLIGHT_V0_1.md) — read-only
  exact-input prerequisite readiness, replay/descendant invalidation,
  declared-effort capability advice and critical-path estimates; reuses the
  connector resolver and grants no admission/dispatch authority.

- [Local Task Claims v0.1](LOCAL_TASK_CLAIMS_V0_1.md) — local SQLite atomic
  human/agent claims, immutable task limits, four deadlines, per-slot fencing
  and persistent unknown execution occupancy; no live provider or distributed
  ledger integration.

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
- [Jules Trusted Source-Revision Binding](JULES_SOURCE_REVISION_BINDING.md) — fail-closed comparison boundary that permits `ScmRevisionBinding.verified=True` only when the authorized repository/branch/revision matches independently observed SCM identity.
- [Product Spine Service v0.1](PRODUCT_SPINE_SERVICE_V0_1.md) — provider-neutral application-service contract that composes WorkUnit, routing, dispatch, candidate normalization, verification, evidence, and Human Decision Record without creating a new correctness or merge authority.
- [Enterprise Tenant Scope v0.1](ENTERPRISE_TENANT_SCOPE_V0_1.md) —
  tenant/project-scoped resource, storage-key, and idempotency foundation with
  fail-closed cross-scope reference checks.
- [Enterprise Authorization Kernel v0.1](ENTERPRISE_AUTHORIZATION_V0_1.md) —
  strict ActorContext + RBAC/ABAC-style policy evaluation over exact tenant/project
  resource scope, including identity freshness, data clearance, risk floors, and
  distinct high-risk approval without executing the requested side effect. Also
  carries the trusted identity adapter contracts that may produce an
  ActorContext: E3-B from GitHub actor claims, E3-C from enterprise IdP
  (OIDC/SAML/SSO) claims. Neither adapter verifies a live credential.
- [Enterprise Audit Ledger v0.1](ENTERPRISE_AUDIT_LEDGER_V0_1.md) —
  dedicated append-only SQLite security/audit evidence stream for E4: exact
  tenant/project, actor/service identity, authorization decision digest,
  immutable resource revision, outcome, retention, hash-chain integrity,
  checkpoint-based truncation detection, and a vendor-neutral SIEM/archive
  export sink. Audit evidence grants no action or integration authority.

When modifying a contract, update its schema, fixtures, implementation, and
tests together. Introduce a new explicit version when behavior changes; keep
old frozen evidence interpretable under its original meaning.
