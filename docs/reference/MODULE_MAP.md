---
description: "Source-derived owner map for every installable idkmesh Python module at the 2026-10-10/11 baseline, with links to contracts and non-authority boundaries."
---
# Installable Python module map (as-built)

**Baseline:** `main@bee77a6125dbccb58f166ec363e978cd960f43f3` (2026-10-11). **Scope:** every direct `idkmesh/*.py` file, including `__init__.py` (85 at the baseline; `tests/test_module_map_docs.py` keeps the table complete as modules are added — `github_ledger_serialization.py` was added after the baseline). This is a **source navigation and responsibility map**, not a claim that all modules form a deployable service, a list of supported public Python APIs, or a test-coverage/qualification certificate. Public claims must follow [the canonical capability matrix](../CAPABILITY_MATRIX.md).

Each row points to real source code inspected for its module-level contract and exported declarations. A module can be pure/experimental, CLI-wired, local-only, or an adapter boundary; mere presence in the installable package does not grant execution, acceptance, human decision, or merge authority. See the [as-built flow](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md) and [CLI/HTTP reference](CLI_HTTP_QUICK_REFERENCE.md) for **exposed** behavior.

## CLI, local HTTP and operational telemetry

Primary context: [subsystem contract](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`__init__.py`](../../idkmesh/__init__.py) | Package boundary and version metadata |
| [`cli.py`](../../idkmesh/cli.py) | Argument parser and command handlers; does not replace domain services |
| [`api_client.py`](../../idkmesh/api_client.py) | Stdlib Python read/inspection client with typed errors and digest checks |
| [`api_observability.py`](../../idkmesh/api_observability.py) | Privacy-safe bounded-cardinality HTTP metrics |
| [`control_tower_api.py`](../../idkmesh/control_tower_api.py) | Evidence validation, read models, and OpenAPI document |
| [`control_tower_ui.py`](../../idkmesh/control_tower_ui.py) | Loopback-only Control Tower HTTP/UI adapter |
| [`gate_audit_ui.py`](../../idkmesh/gate_audit_ui.py) | Loopback-only verdict-panel browser UI |
| [`local_ui_security.py`](../../idkmesh/local_ui_security.py) | Loopback host, local session token, and security headers |
| [`otel_metrics.py`](../../idkmesh/otel_metrics.py) | Offline canonical-metrics to OTLP/HTTP JSON mapping |
| [`service_runtime.py`](../../idkmesh/service_runtime.py) | Request IDs, readiness, limits, logging, and draining |

## Evidence, verifier panels and candidate contracts

Primary context: [subsystem contract](../specifications/GATE_AUDIT_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`candidate_reference.py`](../../idkmesh/candidate_reference.py) | Provider-neutral candidate identities, not verification results |
| [`gate_audit.py`](../../idkmesh/gate_audit.py) | Panel error, dependence, effective-vote, and probe diagnostics |
| [`gate_audit_dependence.py`](../../idkmesh/gate_audit_dependence.py) | Per-pair measured verifier error correlation |
| [`gate_audit_uncertainty.py`](../../idkmesh/gate_audit_uncertainty.py) | Optional seeded finite-sample bootstrap uncertainty |
| [`local_candidate_reader.py`](../../idkmesh/local_candidate_reader.py) | Confined, content-addressed local artifact identity |
| [`marginal_evidence.py`](../../idkmesh/marginal_evidence.py) | Retrospective add-one-verifier analysis |
| [`marginal_evidence_benchmark.py`](../../idkmesh/marginal_evidence_benchmark.py) | Held-out selector-versus-baselines benchmark |
| [`marginal_evidence_synthesis.py`](../../idkmesh/marginal_evidence_synthesis.py) | Cross-cohort synthesis of frozen benchmark reports |
| [`result_manifest_builder.py`](../../idkmesh/result_manifest_builder.py) | Candidate-to-ResultManifest normalization |
| [`verification_handoff.py`](../../idkmesh/verification_handoff.py) | Exact WorkUnit/candidate/policy handoff; no verifier selection |
| [`work_unit_binding.py`](../../idkmesh/work_unit_binding.py) | WorkUnit digest bound to an exact Git source revision |

## Product Spine, coordination and human authority

Primary context: [subsystem contract](../specifications/PRODUCT_SPINE_SERVICE_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`coordination_preflight.py`](../../idkmesh/coordination_preflight.py) | Read-only prerequisite/effort/readiness projection |
| [`executor_admission.py`](../../idkmesh/executor_admission.py) | Revalidated local claim admission and stale-input submission fence |
| [`human_decision_service.py`](../../idkmesh/human_decision_service.py) | Authenticated actor input and immutable local decision record; no HTTP mutation adapter |
| [`product_spine.py`](../../idkmesh/product_spine.py) | Pure run and attempt lifecycle state transitions |
| [`product_spine_idempotency.py`](../../idkmesh/product_spine_idempotency.py) | Local restart-safe offline request reservation |
| [`product_spine_offline.py`](../../idkmesh/product_spine_offline.py) | Deterministic offline lifecycle/evidence composition |
| [`product_spine_run_store.py`](../../idkmesh/product_spine_run_store.py) | SQLite-backed bounded run CRUD/read/event projections |
| [`task_claims.py`](../../idkmesh/task_claims.py) | Atomic local claims and occupancy-aware recovery |

## Connector configuration and routing

Primary context: [subsystem contract](../specifications/CONNECTOR_CONTROL_API_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`connector_control_read.py`](../../idkmesh/connector_control_read.py) | Safe read-only persisted-connection projection |
| [`connector_errors.py`](../../idkmesh/connector_errors.py) | Typed errors and credential redaction |
| [`connector_inspection.py`](../../idkmesh/connector_inspection.py) | Offline probe/doctor/route explanation |
| [`connector_probe.py`](../../idkmesh/connector_probe.py) | Normalized observational driver probe |
| [`connector_profiles.py`](../../idkmesh/connector_profiles.py) | Versioned connector-profile parsing and validation |
| [`connector_registry.py`](../../idkmesh/connector_registry.py) | Provider-neutral driver declarations and fake registry |
| [`connector_routing.py`](../../idkmesh/connector_routing.py) | Pure capability, risk, and cost routing eligibility |
| [`connector_secrets.py`](../../idkmesh/connector_secrets.py) | Environment secret-reference/grant boundary |
| [`connector_store.py`](../../idkmesh/connector_store.py) | Local SQLite metadata and idempotency; not hosted ledger |

## GitHub intake, identity, publication and policy

Primary context: [subsystem contract](../specifications/GITHUB_WEBHOOK_INGRESS_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`github_actions_summary.py`](../../idkmesh/github_actions_summary.py) | Bounded digest-bound Actions step-summary renderer |
| [`github_bootstrap.py`](../../idkmesh/github_bootstrap.py) | GitHub-first bootstrap file/owner-action plan (pure) |
| [`github_bootstrap_render.py`](../../idkmesh/github_bootstrap_render.py) | Deterministic bootstrap config rendering (pure) |
| [`github_branch_reader.py`](../../idkmesh/github_branch_reader.py) | Exact immutable branch-head observation |
| [`github_candidate_reader.py`](../../idkmesh/github_candidate_reader.py) | PR discovery reconciled to trusted GitHub head identity |
| [`github_delivery_idempotency.py`](../../idkmesh/github_delivery_idempotency.py) | Delivery reservation before external side effects |
| [`github_dispatch_authorization.py`](../../idkmesh/github_dispatch_authorization.py) | Explicit trusted-actor/label authorization |
| [`github_evidence_link.py`](../../idkmesh/github_evidence_link.py) | Immutable Git-backed evidence URL validation |
| [`github_explicit_dispatch.py`](../../idkmesh/github_explicit_dispatch.py) | Idempotent explicitly authorized dispatch boundary |
| [`github_governance_policy.py`](../../idkmesh/github_governance_policy.py) | Declarative GitHub repository governance rules |
| [`github_issue_preview.py`](../../idkmesh/github_issue_preview.py) | Untrusted issue-to-policy-owned WorkUnit preview |
| [`github_issue_source.py`](../../idkmesh/github_issue_source.py) | Bounded GitHub REST issue read adapter |
| [`github_ledger_serialization.py`](../../idkmesh/github_ledger_serialization.py) | Pure canonical serialization and append-only chain verification for GitHub ledger records; performs no Git or GitHub action |
| [`github_public_evidence.py`](../../idkmesh/github_public_evidence.py) | Strict public-safe evidence publication projection |
| [`github_rest_source.py`](../../idkmesh/github_rest_source.py) | Bounded GitHub identity REST transport |
| [`github_routing_projection.py`](../../idkmesh/github_routing_projection.py) | Read-only GitHub UI projection of routing decision |
| [`github_status_comment.py`](../../idkmesh/github_status_comment.py) | One idempotently synchronized run-status comment |
| [`github_status_update.py`](../../idkmesh/github_status_update.py) | Immutable single-comment publication and recovery |
| [`github_webhook_ingress.py`](../../idkmesh/github_webhook_ingress.py) | HMAC-verified bounded webhook normalization |

## Jules connector lifecycle

Primary context: [subsystem contract](../architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`jules_actions.py`](../../idkmesh/jules_actions.py) | Explicit operator authorization for approve/message actions |
| [`jules_candidate_binding.py`](../../idkmesh/jules_candidate_binding.py) | Untrusted PR hint to trusted SCM identity bridge |
| [`jules_candidates.py`](../../idkmesh/jules_candidates.py) | Untrusted provider PR-output hint discovery |
| [`jules_client.py`](../../idkmesh/jules_client.py) | Bounded provider REST transport and errors |
| [`jules_lifecycle.py`](../../idkmesh/jules_lifecycle.py) | Session completion plus independent candidate readiness |
| [`jules_observation.py`](../../idkmesh/jules_observation.py) | Normalized session/activity snapshots without raw messages |
| [`jules_revision_binding.py`](../../idkmesh/jules_revision_binding.py) | Authorized source revision matched to observed Git head |
| [`jules_sessions.py`](../../idkmesh/jules_sessions.py) | Session creation only with verified revision binding |
| [`jules_sources.py`](../../idkmesh/jules_sources.py) | Source/repository/branch validation |

## Local execution boundary and reference loop

Primary context: [subsystem contract](../specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`agent_presets.py`](../../idkmesh/agent_presets.py) | Maintainer-owned executable/argument/network presets |
| [`local_agent_artifacts.py`](../../idkmesh/local_agent_artifacts.py) | Controller-owned bounded candidate artifact capture |
| [`local_agent_runner.py`](../../idkmesh/local_agent_runner.py) | Worktree/process limits and fail-closed sandbox interface |
| [`local_agent_sandbox.py`](../../idkmesh/local_agent_sandbox.py) | Linux bubblewrap network-disabled sandbox backend |
| [`local_loop.py`](../../idkmesh/local_loop.py) | Checkout-only two-attempt R1 execution and evidence bundle |

## OpenAI-compatible model adapters

Primary context: [subsystem contract](../architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`openai_compatible.py`](../../idkmesh/openai_compatible.py) | Pure model connection validation |
| [`openai_compatible_capabilities.py`](../../idkmesh/openai_compatible_capabilities.py) | Explicit model capability evidence and identity |
| [`openai_compatible_http.py`](../../idkmesh/openai_compatible_http.py) | Provider-neutral HTTP transport and models probe |
| [`openai_compatible_inference.py`](../../idkmesh/openai_compatible_inference.py) | Normalized non-streaming text/chat completion |
| [`openai_compatible_smoke.py`](../../idkmesh/openai_compatible_smoke.py) | Secret-safe probe and completion digest evidence |

## Enterprise reference policy and audit

Primary context: [subsystem contract](../architecture/ENTERPRISE_CONTROL_PLANE.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`enterprise_audit.py`](../../idkmesh/enterprise_audit.py) | Tenant-scoped tamper-evident audit ledger and exports |
| [`enterprise_authz.py`](../../idkmesh/enterprise_authz.py) | Actor/policy/action authorization kernel |
| [`enterprise_identity_github.py`](../../idkmesh/enterprise_identity_github.py) | Trusted GitHub actor binding to ActorContext |
| [`enterprise_identity_oidc.py`](../../idkmesh/enterprise_identity_oidc.py) | Trusted IdP claims binding to ActorContext |
| [`enterprise_profile.py`](../../idkmesh/enterprise_profile.py) | Strict enterprise profile and cross-field validation |
| [`tenant_scope.py`](../../idkmesh/tenant_scope.py) | Tenant-scoped resource/idempotency identities and memory fixture |

## Steward report read models

Primary context: [subsystem contract](../operations/AUTO_DRAFT_PR_STEWARD.md).

| Source file | Responsibility / authority limit |
| --- | --- |
| [`steward_history.py`](../../idkmesh/steward_history.py) | Offline deterministic report aggregation |
| [`steward_history_ui.py`](../../idkmesh/steward_history_ui.py) | Loopback static history dashboard |
| [`steward_report.py`](../../idkmesh/steward_report.py) | Offline contract-validated steward report reader |
| [`steward_report_ui.py`](../../idkmesh/steward_report_ui.py) | Loopback static single-report dashboard |

## Other executable/source areas (review scope boundary)

The wider repository is more than its installable package. These directories have their own specifications, CI contracts, and experimental maturity; the counts below are from the same pinned Git tree, **not** claims of line-by-line semantic validation:

| Area | Files at baseline | Closest maintained navigation |
| --- | ---: | --- |
| `experiments/*.py` | 26 | [research index](../research/README.md), [test practice](../TESTING.md) |
| `tools/*.py` | 67 | [operations](../operations/JULES_AUTOMATION.md), [contribution workflow](../../CONTRIBUTING.md) |
| `scripts/*.py` | 38 | [test practice](../TESTING.md), [architecture](../architecture/README.md) |
| `sim/*.py` | 42 | [sim guide](../../sim/README.md), [research index](../research/README.md) |
| `randomness_lab/*.py` | 23 | [randomness lab guide](../../randomness_lab/README.md) |
| `interop/*.py` (excluding tests) | 5 | [interop guide](../../interop/README.md) |
| `.github/workflows/*.yml` | 61 | [testing/CI](../TESTING.md), [operations](../operations/JULES_AUTOMATION.md) |
| `tests/**/*.py` | 318 | [testing/CI](../TESTING.md) |

These areas and their validation needs are recorded as the follow-up code-by-code documentation pass in [the dated audit](../audits/2026-10-10-code-documentation-reconciliation.md). Do not infer an external deployment from a GitHub Action definition or infer a product guarantee from a synthetic test.

## How to maintain this map

1. For a changed `idkmesh/*.py` module, verify its public entry points, authority boundary, and tests, then revise its row and the appropriate subsystem specification **in the same PR**.
2. For new/removed modules, compare this table to the current Git tree; preserve a single row per direct package module.
3. Update the [CLI/HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) when `idkmesh/cli.py`, `idkmesh/control_tower_ui.py`, or `idkmesh/control_tower_api.py` changes. The generated `GET /api/v1/openapi.json` document and CLI `--help` are the executable reference.
4. Do not import an old planned feature into the current-state map without verifying merged `main` and its test/evidence contract. Record unmerged PR behavior as pending only.
