# Specifications

These documents define IDKMesh's versioned data, evaluation, repository-graph,
and project-configuration contracts. A status of experimental means the
contract can gain a new version; it does not permit silently changing the
meaning of an existing version.

## GitHub-First Product Operations

- [GitHub Run Label Projection v0.1](GITHUB_RUN_LABEL_PROJECTION_V0_1.md) — C13-E read-only canonical Product Spine run-state display labels and idempotent diff, without GitHub mutation or authority.
- [GitHub Projects Routing Field Sync v0.1](GITHUB_PROJECTS_SYNC_V0_1.md) — C13-F read-only, digest-bound, idempotent routing/risk/review field plan; Projects is never an execution-authority source and the API writer remains unimplemented.
- [GitHub-First Operations v0.1](GITHUB_FIRST_OPERATIONS_V0_1.md) — implementation contract for no-server GitHub coordination: bootstrap, durable run ledger, idempotency/recovery, multi-user claims/authority, Actions security, optional Projects/Pages/OIDC/attestations, and the pilot test matrix.
- [GitHub Governance Preflight v0.1](GITHUB_GOVERNANCE_PREFLIGHT_V0_1.md) — C12 read-only governance admission contract: normalized protection observations, PASS/WARN/FAIL/UNKNOWN semantics, least-privilege workflow linting, explicit-owner CODEOWNERS recommendations, optional OIDC shape checks, and no automatic GitHub administration authority.
- [GitHub Durable Ledger Record v0.1](GITHUB_LEDGER_RECORD_V0_1.md) — C9-A compact append-only run/event/route/idempotency/attempt/evidence-reference contract for restart-safe GitHub-first coordination; secret-free and structurally without dispatch, verification, integration, or merge authority.
- [GitHub Ledger Serialization v0.1](GITHUB_LEDGER_SERIALIZATION_V0_1.md) — C9-B deterministic canonical bytes/digests, semantic writer checks, complete sequence/digest-chain verification, and a two-commit append-only local Git fixture; pure serialization only, with no remote write or integration authority.
- [GitHub Bootstrap Config Rendering v0.1](GITHUB_BOOTSTRAP_CONFIG_RENDERING_V0_1.md) — deterministic C8-C rendering of the ProjectManifest seed, disabled secret-reference connector template, repository-local software-engineering DomainPack, generated ownership README, and content digests; rendering only, with no apply or GitHub mutation authority.
- [GitHub Bootstrap Workflow Wrappers v0.1](GITHUB_BOOTSTRAP_WORKFLOW_WRAPPERS_V0_1.md) — deterministic C8-D rendering of the four thin pinned preview/dispatch/verify/status workflow wrappers: full-SHA Action pins, explicit IDKMesh runtime pin, least-privilege permissions, environment-gated secrets, and a fail-closed runner probe; rendering only; the runner they call is specified separately.
- [GitHub Bootstrap Safe Local Apply v0.1](GITHUB_BOOTSTRAP_SAFE_APPLY_V0_1.md) — C8-F opt-in POSIX local file installation, digest-bound reruns and conflict refusal; no GitHub mutation.
- [GitHub Workflow Runner v0.1](GITHUB_WORKFLOW_RUNNER_V0_1.md) — the stdlib-only `idkmesh github-workflow` command the generated wrappers call: read-only issue `preview` from project policy and ledger `status` over a mutation-refusing transport, `dispatch` and `verify` failing closed, the `IDKMESH_*` environment contract, and stable error codes; no dispatch, comment, secret, or merge authority.
- [GitHub Webhook Ingress v0.1](GITHUB_WEBHOOK_INGRESS_V0_1.md) — authenticated bounded webhook envelope: raw-body HMAC-SHA256, event/action allowlists, repository binding, delivery provenance, and no dispatch authority.
- [GitHub WorkUnit Intake v0.1](GITHUB_WORKUNIT_INTAKE_V0_1.md) — normalized untrusted GitHub Issue Form planning hints with an explicit all-false authority ceiling; requested paths, risk, review, processing, and connector values cannot broaden trusted project policy. The C13-B WorkUnit request Issue Form uses exactly these field ids and enums.

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
  telemetry, W3C traceparent v00 pass-through, explicit local-profile SLO/alert
  targets (also as a machine-readable, schema-validated SLO contract with
  offline evaluators), a Prometheus text renderer, and a dependency-free
  transport-neutral OTLP/HTTP JSON mapping
  adapter. Collector transport and Human Decision ingestion telemetry remain
  separate follow-up work under #744.
- [API Storage Profiles v0.1](API_STORAGE_PROFILES_V0_1.md) —
  which durable store owns the API in the GitHub-first, local and network
  profiles, the storage-port operations and required semantics (migration
  replay, digest-checked reads, append-only events, restart reconstruction),
  the retention matrix, and an honest verified-versus-open acceptance table.
- [API v1 Beta Release Gate v0.1](API_V1_BETA_RELEASE_GATE_V0_1.md) —
  the evidence a first API beta needs, how each item is verified (evidence files,
  a current green qualification report, a clean tagged revision), what the
  release note must state, and the tool that reports the gate as ready or not.
- [GitHub Ledger Optimistic Append v0.1](GITHUB_LEDGER_APPEND_V0_1.md) —
  C9-C compare-and-set append to the GitHub-native durable ledger: conflict
  detection on a Git ref, bounded retry, linear never-rewritten history, and an
  honest account of what it does not prove.
- [GitHub Ledger Idempotent Admission v0.1](GITHUB_LEDGER_ADMISSION_V0_1.md) —
  C9-D one-admission-ref-per-dispatch-key by compare-and-set, so a duplicate or
  concurrent dispatch resolves to the existing run; conflicting replays fail
  closed and a crash between admission and the first record is recoverable.
- [GitHub Ledger Recovery Reader v0.1](GITHUB_LEDGER_RECOVERY_V0_1.md) —
  C9-E derives a run's current state from its immutable ledger records, never
  drops negative evidence, surfaces ambiguous provider submissions, and refuses
  histories no real run could have produced.
- [GitHub Ledger Recovery Planning and Killed-Workflow Proof v0.1](GITHUB_LEDGER_RECOVERY_PLAN_V0_1.md) —
  C9-F pure next-step planning for a recovered run (reconcile, never blindly
  resubmit) and the exhaustive kill-matrix test that a killed coordinating
  workflow is recovered with exactly one provider submission.
- [GitHub Ledger GitHub Storage v0.1](GITHUB_LEDGER_GITHUB_STORAGE_V0_1.md) —
  C9-G durable GitHub storage on one dedicated orphan ledger branch: hashed
  immutable paths, fast-forward-only branch updates with bounded retry, C9-D
  admission replay/conflict semantics, C9-E recovery reads, and no protected
  application-branch write or integration authority.
- [GitHub Ledger Retention and Reference Policy v0.1](GITHUB_LEDGER_RETENTION_V0_1.md) —
  C9-H advisory policy and checks: mandatory durable compact evidence per run
  state, references that stay interpretable after raw artifacts expire, raw
  expiry that never strands the sole copy, and ledger growth bounded without
  rewriting history.
- [API Authority Matrix v0.1](API_AUTHORITY_MATRIX_V0_1.md) —
  which principal may call which Control Tower endpoint: a proposed mapping onto
  the enterprise authorization kernel for the network profile, what the loopback
  API enforces today (a session token, not a principal), and a guard that keeps
  the matrix complete against the served routes.
- [Release Supply-Chain Baseline v0.1](RELEASE_SUPPLY_CHAIN_V0_1.md) —
  release SBOM/checksum/source-workflow identity evidence, immutable-pinned
  GitHub build provenance, consumer verification, and vulnerability/update
  policy for enterprise release integrity (#674).
- [GitHub Public Evidence Projection v0.1](GITHUB_PUBLIC_EVIDENCE_V0_1.md) —
  strict C14-D whitelist for public GitHub publication: exact digest-bound
  run/candidate/verification metadata only, with raw evidence, logs, prompts,
  provider payloads, identities, artifact locators, secrets, and all actuation
  authority excluded.
- [GitHub Pages Site Projection v0.1](GITHUB_PAGES_SITE_V0_1.md) —
  C14-E pure, deterministic static-site file map generated only from C14-D
  public-safe projections: health, active work, verification debt, per-run
  provenance; no scripts, no external assets, no mutation or approval surface.
  `idkmesh pages-site` writes the map to a local directory; it never publishes.
- [GitHub Release Provenance v0.1](GITHUB_RELEASE_PROVENANCE_V0_1.md) —
  C14-F offline metadata record binding a proposed release (tag, target commit,
  artifact digests, all caller-supplied and unverified) to the C14-D run
  evidence it references; `idkmesh release-provenance` prints the record or
  draft notes. It creates no tag, release, or attestation and claims none.
- [GitHub Release Statement v0.1](GITHUB_RELEASE_STATEMENT_V0_1.md) —
  C14-G unsigned in-toto Statement v1 rendered from a release record (artifact
  digests as subjects, the record as predicate); `idkmesh release-provenance
  --statement` prints it. Nothing is signed or registered, no SLSA or
  correctness claim; signing needs a CI workflow identity.
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

- [Python API Client Compatibility Checks v0.1](API_PYTHON_CLIENT_COMPATIBILITY_CHECKS_V0_1.md) — bounded cursor-safe run pagination, client integrity/error tests and still-open TypeScript/mutation contracts.
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
- [Enterprise Control Service Boundary v0.1](ENTERPRISE_CONTROL_SERVICE_V0_1.md) —
  normative E8 G2/G3 deployment reference for plane separation, per-tenant
  authorization, durable state, private workers, scale/idempotency,
  migrations/backups/probes, upgrade/rollback, and the GitHub integration
  authority ceiling.
- [ProjectManifest and DomainPack Interfaces](PROJECT_DOMAIN_INTERFACES.md) —
  separates reusable coordination core from declarative domain and project
  policy.
- [Connector Control API v0.1](CONNECTOR_CONTROL_API_V0_1.md) — experimental
  project-facing connection, dispatch, run-state, webhook, secret-reference,
  agent/model-provider, and error contract above the canonical WorkUnit and
  verification semantics.
- [Jules Trusted Source-Revision Binding](JULES_SOURCE_REVISION_BINDING.md) — fail-closed comparison boundary that permits `ScmRevisionBinding.verified=True` only when the authorized repository/branch/revision matches independently observed SCM identity.
- [Product Spine Service v0.1](PRODUCT_SPINE_SERVICE_V0_1.md) — provider-neutral application-service contract that composes WorkUnit, routing, dispatch, candidate normalization, verification, evidence, and Human Decision Record without creating a new correctness or merge authority.
- [Enterprise Data Policy Kernel v0.1](ENTERPRISE_DATA_POLICY_V0_1.md) — pure, fail-closed external-processing, egress, credential and secret-access decisions derived from the enterprise control profile; not yet wired into any runtime path.
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
