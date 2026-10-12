---
title: "IDKMesh Executable Capability Reference"
description: "Code-backed CLI, local API, Python client, connector, GitHub, enterprise, execution, and evidence capabilities currently present in IDKMesh."
---

# IDKMesh Executable Capability Reference

This page answers a narrower question than the [Capability Truth Matrix](CAPABILITY_MATRIX.md):
**what executable surfaces and implementation modules exist in the repository today?**

The truth matrix remains the public evidence/claim boundary. This reference is an
implementation inventory. A module or command appearing here means code exists and is
covered by the repository's current tests; it does **not** promote that code to external
reproduction, production qualification, or autonomous integration authority.

This page is intentionally checked by `tests/test_executable_capability_docs.py` against
the real argparse command tree, Control Tower discovery document, public Python client
methods, and every top-level Python module in `idkmesh/`.

## Installed CLI surface

`pip install .` installs the `idkmesh` command. The current command tree is:

| Command | Implemented capability | Important boundary |
| --- | --- | --- |
| `idkmesh gate-audit` | audit verifier accuracy, dependence, effective votes, quorum behavior, and seeded-probe breaches | diagnostic only; does not run reviewers or approve work |
| `idkmesh gate-audit-dependence` | emit pairwise verifier error-dependence evidence | diagnostic only |
| `idkmesh gate-marginal` | measure marginal evidence contribution of candidate verifiers | diagnostic only |
| `idkmesh gate-marginal-benchmark` | compare the marginal-evidence selector with preregistered baselines | benchmark/evidence surface, not routing authority |
| `idkmesh gate-marginal-synthesis` | synthesize multiple benchmark cohorts descriptively | no cross-cohort winner or integration authority |
| `idkmesh init` | deterministic GitHub-first bootstrap planning/rendering of config and pinned workflow wrappers | `--github --dry-run` only; no repository or GitHub mutation; rendered wrappers call `idkmesh github-workflow`, whose `dispatch` and `verify` phases still fail closed |
| `idkmesh github-workflow` | runner the generated GitHub workflow wrappers call, driven by `IDKMESH_*` environment variables | `preview` and `status` are read-only; `dispatch` and `verify` fail closed; no merge, no provider secret, no issue comment |
| `idkmesh github-workflow preview` | derive a deterministic WorkUnit preview and digest for one issue from project policy | read-only; needs `metadata.github_issue_preview.allowed_paths`; no dispatch |
| `idkmesh github-workflow status` | project one run's latest durable-ledger record into the bounded status body and job summary | read-only transport; publishes no issue comment |
| `idkmesh github-workflow dispatch` | refuse with the stable `dispatch_unavailable` code | fails closed; reads no environment or secret |
| `idkmesh github-workflow verify` | refuse with the stable `verify_unavailable` code | fails closed; reads no environment, candidate, or secret |
| `idkmesh pages-site` | validate C14-D public-safe projections, render the C14-E static Pages file map, and write exactly those files to a local directory | local files only; no publication, workflow, network or GitHub call; refuses unsafe paths, symlinks, and unrecognised non-empty directories unless `--force` |
| `idkmesh release-provenance` | validate C14-D public-safe projections and print the C14-F release metadata/provenance record (or draft release notes with `--notes`) binding a proposed tag, target commit and artifact digests to that evidence | stdout only; creates no tag, GitHub Release or attestation and makes no network or GitHub call; commit and digests are caller-supplied and recorded as unverified; no timestamps |
| `idkmesh connections` | validate, normalize, persist, and inspect connector metadata | no live dispatch, no raw secret persistence |
| `idkmesh connections validate` | validate a versioned connector profile | read-only |
| `idkmesh connections list` | list normalized connector metadata from a profile | read-only |
| `idkmesh connections import` | persist safe normalized connector metadata in local SQLite | secret values are not persisted |
| `idkmesh connections stored` | read normalized persisted connector metadata | read-only |
| `idkmesh connections probe` | run offline fake-driver connector probes | no live provider call |
| `idkmesh doctor` | summarize connector readiness, or evaluate the read-only C12 GitHub governance preflight with `--github` | connector/GitHub PASS is diagnostic precondition evidence, not dispatch, admin, acceptance, or merge authority |
| `idkmesh route` | provider-neutral routing command family | read/explain surface |
| `idkmesh route explain` | explain eligible/rejected connectors and optional deterministic auto-selection | no external work or repository mutation |
| `idkmesh run` | durable local Product Spine run-control command family | no provider dispatch, candidate acceptance, push, or merge |
| `idkmesh run create` | persist one proposed Product Spine run with idempotency metadata | local state only |
| `idkmesh run status` | inspect one retained Product Spine run | read-only |
| `idkmesh run evidence` | return retained evidence only after digest verification | read-only; mismatch fails closed |
| `idkmesh run cancel` | record a lifecycle-valid cancelled transition | does not terminate an external provider process |
| `idkmesh run list` | keyset-paginated run listing with exact filters | read-only |
| `idkmesh work-unit` | derived WorkUnit read-model command family | no canonical WorkUnit body store |
| `idkmesh work-unit list` | list WorkUnits referenced by retained runs | derived read model |
| `idkmesh work-unit status` | inspect one WorkUnit identity and retained revisions | derived read model |
| `idkmesh project` | project read-model command family | no standalone project record |
| `idkmesh project status` | show per-state run counts and distinct WorkUnits for one project | read-only |
| `idkmesh events` | canonical durable event-stream command family | current event coverage is deliberately bounded |
| `idkmesh events list` | list append-only events with keyset pagination and exact filters | read-only |
| `idkmesh gate-audit-ui` | loopback browser UI over the gate-audit engine | no hosted upload and no merge authority |
| `idkmesh control-tower` | loopback Human Control Tower and versioned read-only API | cannot execute workers, record human decisions, push, or merge |
| `idkmesh steward-report` | render repository stewardship/report evidence | advisory/reporting surface |
| `idkmesh steward-report-ui` | local browser view of steward reports | local/read-only presentation |
| `idkmesh steward-history` | inspect retained stewardship history | read/report surface |
| `idkmesh steward-history-ui` | local browser view of stewardship history | local/read-only presentation |
| `idkmesh local-loop` | deterministic local Product Spine composition from bounded work through attempts/evidence | local/fake or bounded execution path; no automatic integration |

Run `idkmesh --help` or `idkmesh <command> --help` for argument-level help.

## Local Control Tower HTTP API

The implemented HTTP service is loopback-only and read/inspect oriented. The discovery
document currently advertises these exact endpoints:

| Endpoint | Capability |
| --- | --- |
| `GET /healthz` | cheap process liveness |
| `GET /readyz` | readiness metadata without project/evidence content |
| `GET /api/v1/status` | capability, endpoint, media-type, and runtime-limit discovery |
| `GET /api/v1/openapi.json` | dependency-free OpenAPI discovery |
| `GET /api/v1/metrics` | privacy-safe aggregate service metrics |
| `POST /api/v1/run-evidence/inspect` | validate and render one Run Evidence Report without selecting a candidate |
| `GET /api/v1/connections` | list persisted public-safe connector metadata with opaque keyset pagination |
| `GET /api/v1/runs` | list durable Product Spine runs |
| `GET /api/v1/runs/{run_id}` | read one run projection |
| `GET /api/v1/runs/{run_id}/attempts` | read one run's attempt projections |
| `GET /api/v1/runs/{run_id}/evidence` | read retained digest-verified run evidence |
| `GET /api/v1/work-units` | list WorkUnits derived from retained runs |
| `GET /api/v1/work-units/{work_unit_id}` | read one derived WorkUnit resource |
| `GET /api/v1/projects/{project_id}` | read one project summary derived from retained runs |
| `GET /api/v1/events` | query the canonical append-only event source |
| `GET /api/v1/events/stream` | resumable bounded Server-Sent Events stream |

The service also implements bounded request concurrency, request timeouts, overload
responses, graceful drain, a separate SSE client cap, content digests/ETags, request IDs,
optional access logging, traceparent propagation, and privacy-safe metrics. See
[Control Tower Local API v0.1](specifications/CONTROL_TOWER_LOCAL_API_V0_1.md),
[HTTP Service Runtime v0.1](specifications/HTTP_SERVICE_RUNTIME_V0_1.md), and
[API Observability v0.1](specifications/API_OBSERVABILITY_V0_1.md).

Not implemented on this transport: authenticated human-decision recording, worker
execution, connector mutation, canonical-state write, Git push, merge, or production
multi-user network exposure.

## Dependency-free Python client

`idkmesh.api_client.ControlTowerClient` provides the same read/inspect model without
requiring an HTTP client dependency. Current public methods are:

- `ControlTowerClient.request_id` — last response request ID exposed for correlation
- `ControlTowerClient.status()`
- `ControlTowerClient.get_openapi()` — download the OpenAPI 3.x definition served by the running API
- `ControlTowerClient.get_metrics()` — read the fixed-cardinality, privacy-safe operational metrics
- `ControlTowerClient.inspect_run_evidence()`
- `ControlTowerClient.get_run()`
- `ControlTowerClient.get_run_evidence()`
- `ControlTowerClient.get_run_attempts()`
- `ControlTowerClient.list_runs()`
- `ControlTowerClient.get_work_unit()`
- `ControlTowerClient.list_work_units()`
- `ControlTowerClient.list_connections()`
- `ControlTowerClient.get_project()`
- `ControlTowerClient.list_events()`
- `ControlTowerClient.stream_events()` — one bounded, strictly parsed read of the `events/stream` SSE endpoint (mandatory idle timeout, digest-checked events, caller-driven resume with `Last-Event-ID`)

The client requires an explicit timeout, refuses non-loopback destinations, exposes
request IDs, validates content digests, and performs no implicit retry or reconnect.

## Implemented library/runtime capability groups

### Connector configuration, inspection, and routing

Versioned profile parsing, connector registry, offline probing, provider-neutral routing,
secret-reference validation/redaction, local SQLite persistence, stable connector errors,
and the public-safe connector read projection are implemented. The CLI surfaces these
through `connections`, `doctor`, and `route explain`; HTTP exposes the read-only connection
list. Live connector dispatch remains separately authority-gated.

### Product Spine, evidence, and local control state

The codebase implements Product Spine lifecycle projections, idempotent create/replay
control, durable local run storage, retained evidence reads, derived WorkUnit/project read
models, append-only run events, result-manifest building, verification handoff, and the
bounded `local-loop` composition.

### Provider and agent adapters

- Jules: HTTP transport shell, Source/session lifecycle, revision binding, observations,
  candidate hints/binding, and action helpers.
- OpenAI-compatible: static model configuration, capability declaration, bounded HTTP
  transport/inference helpers, and smoke-test composition for compatible endpoints.
- Local agents: preset resolution, bounded subprocess execution, explicit sandbox
  capability contracts, artifact/candidate normalization, and fail-closed enforcement
  checks. This is not a project-wide claim of production-safe hostile-code sandboxing.

### GitHub-native control plane

The package contains bounded GitHub repository/ref readers, issue-source normalization,
issue preview/routing projection, authenticated webhook ingress, delivery idempotency,
deterministic ledger-record serialization with append-only chain verification, local
compare-and-set append/admission/recovery machinery, and a GitHub-native durable storage
adapter that uses one dedicated orphan ledger branch with fast-forward-only ref updates.
The recovery planner reconciles unconfirmed provider submissions rather than resubmitting
blindly; none of these ledger layers grants dispatch, verification, acceptance, application
branch write, integration, or merge authority. The package also includes explicit dispatch
authorization/bridge logic, exact candidate observation, evidence/status publication
helpers, governance-policy and read-only governance-preflight checks, public-evidence projection, a static Pages site generator with a local-directory writer (`idkmesh pages-site`; no publication), a release metadata/provenance record (`idkmesh release-provenance`; no tag, release, or attestation), and deterministic
GitHub-first bootstrap planning/rendering.

### Enterprise control primitives

Tenant scoping, normalized enterprise actor contexts, GitHub and OIDC identity bindings,
deterministic authorization decisions, enterprise control-profile validation, and an
append-only tamper-evident enterprise audit ledger are implemented as control primitives.
They are building blocks, not a claim that the local Control Tower is a production
multi-tenant enterprise service or that configuration equals compliance certification.

### Coordination, admission, runtime, and observability

Local task claims, coordination preflight, stale-input-safe executor admission, bounded
HTTP service runtime behavior, request/trace correlation, privacy-safe metrics, OTLP metric
export support, and local UI security helpers are implemented. Live-provider composition
varies by subsystem and remains subject to each specification's authority boundary.

### Diagnostics, stewardship, and research tooling

Review-gate auditing, dependence measurement, marginal-evidence analysis/benchmark/synthesis,
steward reports/history plus local UIs, Control Tower evidence rendering, simulations,
experiments, and protocol conformance helpers are present. Research tooling does not become
a scientific conclusion merely because it is executable.

## Full `idkmesh/` module inventory

This appendix is intentionally exhaustive for top-level Python modules in the installable
`idkmesh` package. The CI guard requires every module here to remain discoverable. A module
name documents implementation presence, not stability as a public Python API.

- `idkmesh/agent_presets.py`
- `idkmesh/api_client.py`
- `idkmesh/api_observability.py`
- `idkmesh/candidate_reference.py`
- `idkmesh/cli.py`
- `idkmesh/connector_control_read.py`
- `idkmesh/connector_errors.py`
- `idkmesh/connector_inspection.py`
- `idkmesh/connector_probe.py`
- `idkmesh/connector_profiles.py`
- `idkmesh/connector_registry.py`
- `idkmesh/connector_routing.py`
- `idkmesh/connector_secrets.py`
- `idkmesh/connector_store.py`
- `idkmesh/control_tower_api.py`
- `idkmesh/control_tower_ui.py`
- `idkmesh/coordination_preflight.py`
- `idkmesh/enterprise_audit.py`
- `idkmesh/enterprise_authz.py`
- `idkmesh/enterprise_authz_cache.py`
- `idkmesh/enterprise_conformance.py`
- `idkmesh/enterprise_data_policy.py`
- `idkmesh/enterprise_identity_github.py`
- `idkmesh/enterprise_identity_oidc.py`
- `idkmesh/enterprise_profile.py`
- `idkmesh/executor_admission.py`
- `idkmesh/gate_audit.py`
- `idkmesh/gate_audit_dependence.py`
- `idkmesh/gate_audit_ui.py`
- `idkmesh/gate_audit_uncertainty.py`
- `idkmesh/github_actions_summary.py`
- `idkmesh/github_bootstrap.py`
- `idkmesh/github_bootstrap_render.py`
- `idkmesh/github_bootstrap_workflows.py`
- `idkmesh/github_branch_reader.py`
- `idkmesh/github_candidate_reader.py`
- `idkmesh/github_delivery_idempotency.py`
- `idkmesh/github_dispatch_authorization.py`
- `idkmesh/github_evidence_link.py`
- `idkmesh/github_explicit_dispatch.py`
- `idkmesh/github_governance_policy.py`
- `idkmesh/github_governance_preflight.py`
- `idkmesh/github_issue_preview.py`
- `idkmesh/github_issue_source.py`
- `idkmesh/github_ledger_admission.py`
- `idkmesh/github_ledger_append.py`
- `idkmesh/github_ledger_github_store.py`
- `idkmesh/github_ledger_recovery.py`
- `idkmesh/github_ledger_recovery_plan.py`
- `idkmesh/github_ledger_serialization.py`
- `idkmesh/github_pages_site.py`
- `idkmesh/github_pages_writer.py`
- `idkmesh/github_public_evidence.py`
- `idkmesh/github_release_provenance.py`
- `idkmesh/github_rest_source.py`
- `idkmesh/github_routing_projection.py`
- `idkmesh/github_status_comment.py`
- `idkmesh/github_status_update.py`
- `idkmesh/github_webhook_ingress.py`
- `idkmesh/github_workflow_runner.py`
- `idkmesh/github_workunit_intake.py`
- `idkmesh/human_decision_service.py`
- `idkmesh/jules_actions.py`
- `idkmesh/jules_candidate_binding.py`
- `idkmesh/jules_candidates.py`
- `idkmesh/jules_client.py`
- `idkmesh/jules_lifecycle.py`
- `idkmesh/jules_observation.py`
- `idkmesh/jules_revision_binding.py`
- `idkmesh/jules_sessions.py`
- `idkmesh/jules_sources.py`
- `idkmesh/local_agent_artifacts.py`
- `idkmesh/local_agent_runner.py`
- `idkmesh/local_agent_sandbox.py`
- `idkmesh/local_candidate_reader.py`
- `idkmesh/local_loop.py`
- `idkmesh/local_ui_security.py`
- `idkmesh/marginal_evidence.py`
- `idkmesh/marginal_evidence_benchmark.py`
- `idkmesh/marginal_evidence_synthesis.py`
- `idkmesh/openai_compatible.py`
- `idkmesh/openai_compatible_capabilities.py`
- `idkmesh/openai_compatible_http.py`
- `idkmesh/openai_compatible_inference.py`
- `idkmesh/openai_compatible_smoke.py`
- `idkmesh/otel_metrics.py`
- `idkmesh/product_spine.py`
- `idkmesh/product_spine_idempotency.py`
- `idkmesh/product_spine_offline.py`
- `idkmesh/product_spine_run_store.py`
- `idkmesh/result_manifest_builder.py`
- `idkmesh/service_runtime.py`
- `idkmesh/steward_history.py`
- `idkmesh/steward_history_ui.py`
- `idkmesh/steward_report.py`
- `idkmesh/steward_report_ui.py`
- `idkmesh/task_claims.py`
- `idkmesh/tenant_scope.py`
- `idkmesh/verification_handoff.py`
- `idkmesh/work_unit_binding.py`

## Relationship to architecture and claim truth

Use the documents in this order when the word *capability* is ambiguous:

1. **Does code exist?** This executable capability reference.
2. **What is its semantic/authority contract?** The relevant specification/schema and
   [architecture index](architecture/README.md).
3. **How strong a public claim is supported?** The
   [Capability Truth Matrix](CAPABILITY_MATRIX.md).
4. **Has it been externally reproduced or production-qualified?** Only the evidence level
   and qualification artifact in the truth matrix may answer yes.

Historical plans and conversations do not override current code, schemas, specifications,
or this CI-checked executable inventory.
