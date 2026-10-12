---
description: "As-built architectural paths from local CLI, HTTP, adapters, execution, verification, and human authority to durable evidence as of 2026-10-10."
---
# As-built implementation and trust-boundary map

**Source baseline:** `main@bee77a6125dbccb58f166ec363e978cd960f43f3`, inspected 2026-10-10/11. This map is derived from the current source files and exposed handlers, not solely from older diagrams or future architecture proposals. Read [the module-by-module inventory](../reference/MODULE_MAP.md) for all 85 direct installable Python files, [the CLI and HTTP quick reference](../reference/CLI_HTTP_QUICK_REFERENCE.md) for supported entry points, and [the capability matrix](../CAPABILITY_MATRIX.md) for controlled maturity/evidence claims.

## What actually runs

```text
Developer / operator
  |
  +-- idkmesh gate-audit / gate-marginal / dependence
  |     CLI (idkmesh/cli.py)
  |       -> pure verdict analysis (gate_audit.py, marginal_evidence*.py)
  |       -> diagnostic output / report, never approval
  |
  +-- idkmesh init --github --dry-run
  |       -> github_bootstrap.py -> github_bootstrap_render.py
  |                              -> github_bootstrap_workflows.py
  |       -> reproducible file/owner-action plan + rendered config/workflow bytes, NO APPLY
  |
  +-- idkmesh github-workflow preview | status | dispatch | verify   [inside a generated wrapper]
  |       -> github_workflow_runner.py (stdlib-only; IDKMESH_* environment contract)
  |       -> preview: github_issue_source.py -> github_issue_preview.py (project policy, not issue text)
  |       -> status: github_ledger_github_store.py via a read-only transport -> github_status_comment.py body
  |       -> dispatch / verify: fail closed (dispatch_unavailable / verify_unavailable)
  |       -> NO dispatch, issue comment, provider secret, acceptance, or merge
  |
  +-- idkmesh doctor --github OBSERVATION [--workflow PATH]
  |       -> github_governance_policy.py -> github_governance_preflight.py
  |       -> fail-closed governance/workflow preflight only
  |       -> NO GitHub admin mutation, secret access, dispatch, acceptance, or merge
  |
  +-- idkmesh run create | status | evidence | list | cancel
  |       -> product_spine_run_store.py -> connector_store.py (local SQLite)
  |       -> local run/event projections, NO DISPATCH
  |
  +-- idkmesh local-loop CONFIG                  [checkout + verify extra]
  |       -> experiments/replay_run.py capture
  |       -> experiments/two_attempt_orchestrator.py
  |       -> independent verifier + run evidence report
  |       -> bounded local evidence/replay bundle
  |       -> human decision / replay remain separate, manual
  |
  +-- idkmesh pages-site --repository R --projection P... --out DIR
  |       -> github_public_evidence.py (strict projection validation)
  |       -> github_pages_site.py (pure file map) -> github_pages_writer.py
  |       -> local directory, all-or-nothing; NO PUBLICATION, NETWORK, or GITHUB CALL
  |
  +-- idkmesh control-tower [--product-spine-store SQLite]
          -> control_tower_ui.py (127.0.0.1:8770)
          -> control_tower_api.py (strict report validation + read projection)
          -> product_spine_run_store.py (optional read of local retained state)
          -> api_observability.py / service_runtime.py
          -> token-authenticated read-only /api/v1 + event SSE
          -> local browser; NO MUTATING HTTP CONTROLLER
```

The `idkmesh` Python distribution includes the package but **not** the research `experiments/`, `sim/`, `tools/`, `scripts/`, examples, or CI workflows. `local-loop` is intentionally checkout-dependent; installation alone is not evidence of a packaged standalone swarm runner. Consult [the quick reference](../reference/CLI_HTTP_QUICK_REFERENCE.md) for invocations.

## Product Spine, source binding and authority

```text
Trusted WorkUnit + exact Git source
  |  work_unit_binding.py
  v
Preflight / routing evidence              [no dispatch authorization]
  |  coordination_preflight.py
  |  connector_profiles/registry/probe/routing/inspection.py
  v
Policy-owned execution admission          [separate from observation]
  |  executor_admission.py + task_claims.py (local)
  |  github_dispatch_authorization.py + github_explicit_dispatch.py
  |  (GitHub adapter; explicitly authorized and idempotent)
  v
Worker attempt + identity                  [worker assertion, NOT acceptance]
  |  local_agent_runner/sandbox/artifacts.py OR Jules lifecycle
  |  candidate_reference.py + github_candidate_reader.py
  v
Canonical ResultManifest / verification handoff
  |  result_manifest_builder.py + verification_handoff.py
  v
Independent verification / Run Evidence Report
  |  experiments/local_verifier.py, evaluator_plan_runner.py,
  |  run_evidence_report.py; pure offline Product Spine composition
  v
Human decision (distinct trusted ActorContext)
  |  human_decision_service.py (local service + immutable records)
  v
Separate project integration policy and actual Git merge authority
```

The arrows are **semantic boundaries**, not a claim that a single production service wires every stage automatically. In particular, provider completion does not validate the Git head, a verified artifact does not approve itself, a local UI session token does not confer a trusted human actor identity, and a stored decision does not push or merge code. Pure-domain lifecycle in `product_spine.py`, offline composition in `product_spine_offline.py`, and local SQLite orchestration in `product_spine_run_store.py` are deliberately separate implementations.

**Evidence-to-decision seam (tested, not yet a state transition).** `tests/test_product_spine_human_decision_integration.py` drives the idempotent offline spine, the SQLite run store, `idkmesh run evidence`, the Control Tower HTTP route with `ControlTowerClient`, and `HumanDecisionService` together. It pins that the evidence digest shown by the CLI and the Control Tower is the digest a decision binds, that a swapped or post-hoc-changed digest fails closed with nothing stored, and that recording a decision leaves the run row, its events and the served evidence unchanged and spawns no process. Nothing yet moves a persisted offline run from `awaiting_human_decision` to `decided`: ADR-0024 keeps offline rows read-only and the authenticated decision adapter is still owed by #740, so a stored decision is not reflected in the run's `human_decision_record_digest`.

## HTTP and browser profile

```text
Browser / stdlib ControlTowerClient
    -> fixed 127.0.0.1 bind + Host/header validation
    -> X-IDKMesh-UI-Token (local session, not enterprise auth)
    -> content framing, bounded request size, timeout and concurrency
    -> /healthz, /readyz                    [operational]
    -> GET /api/v1/status/openapi.json/metrics
    -> POST /api/v1/run-evidence/inspect   [compute-only, no durable write]
    -> GET /api/v1/connections
    -> GET /api/v1/runs, .../attempts, .../evidence
    -> GET /api/v1/work-units, .../{id}, /projects/{id}
    -> GET /api/v1/events and /events/stream (SSE)
```

The runtime uses `service_runtime.py` for request correlation, readiness, resource ceilings and access logging; `api_observability.py` for privacy-safe fixed-cardinality operational metrics; and `otel_metrics.py` for **offline** OTLP/HTTP JSON mapping (not a built-in push exporter). OpenAPI is built by `control_tower_api.openapi_document()`; the running server's `GET /api/v1/openapi.json` is the authoritative route/schema discovery surface.

**Not routed:** privileged `POST /api/v1/human-decisions`, connector mutation/dispatch APIs, an authenticated multi-tenant network service, or merge endpoints. `human_decision_service.py` and enterprise authorization kernels do not themselves make such routes available. See [Control Tower Local API v0.1](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md), [API Conventions](../specifications/API_CONVENTIONS_V0_1.md), and [Enterprise Control Plane](ENTERPRISE_CONTROL_PLANE.md).

## Connector and provider boundaries

| Layer | Source of truth | Guarantees / limits |
| --- | --- | --- |
| Versioned configuration | `connector_profiles.py`, `connector_secrets.py` | Validate metadata/secret references, not provider access |
| Driver and health | `connector_registry.py`, `connector_probe.py` | Static declarations and normalized observational probes; CLI `connections probe` uses offline fake drivers |
| Eligibility | `connector_routing.py`, `connector_inspection.py` | Deterministic selection/explanation; no authority escalation |
| GitHub ingress | `github_webhook_ingress.py`, `github_issue_preview.py` | Verify HMAC; issue text remains untrusted data; policy owns WorkUnit authority (a parsed Issue Form may only narrow it) |
| GitHub governance preflight | `github_governance_policy.py`, `github_governance_preflight.py` | Evaluate trusted normalized protection/workflow observations and fail closed on required UNKNOWN/FAIL; no GitHub administration or secret-value access |
| GitHub mutable source | `github_branch_reader.py`, `github_candidate_reader.py` | Bind requested source/candidate to exact observed Git object identity |
| GitHub dispatch/publication | `github_delivery_idempotency.py`, `github_explicit_dispatch.py`, `github_status_comment.py`, `github_pages_site.py`, `github_pages_writer.py` | Explicit actor/role authorization, idempotency/reconciliation; no automatic merge |
| Jules | `jules_sources.py`, `jules_sessions.py`, `jules_observation.py`, `jules_candidates.py`, `jules_candidate_binding.py`, `jules_lifecycle.py` | Provider Session completion is not trusted candidate identity or verification |
| Local coding agent | `agent_presets.py`, `local_agent_runner.py`, `local_agent_sandbox.py`, `local_agent_artifacts.py` | Fail-closed `LocalSandboxExecutor`; Linux bubblewrap network-disabled only, not arbitrary network-safe agent execution |
| OpenAI-compatible model | `openai_compatible*.py` | Model discovery/chat inference and capability evidence; model connection is not a coding-agent permission |

The execution-substrate abstraction and GitHub-first deployment model remain **architectural goals with bounded implemented slices**. A local SQLite store is not a durable hosted multi-tenant state ledger, a GitHub publication projection is not independent evidence, and a policy object is not proof of a running provider integration.

## Evidence, enterprise, research and automation

- **Candidate/evidence identity:** `candidate_reference.py`, `result_manifest_builder.py`, `verification_handoff.py`, `github_evidence_link.py`, `github_public_evidence.py`. Content and source bindings carry evidence, not accept/merge authority.
- **Review-panel diagnostics:** `gate_audit.py`, `gate_audit_dependence.py`, `gate_audit_uncertainty.py`, `marginal_evidence*.py`. Observed dependence matters more than nominal reviewer count; held-out selection/benchmark results are not a generalized external-performance claim.
- **Local human/enterprise kernels:** `human_decision_service.py`, `tenant_scope.py`, `enterprise_authz.py`, `enterprise_identity_github.py`, `enterprise_identity_oidc.py`, `enterprise_audit.py`, `enterprise_profile.py`. Authorization depends on independently trusted identity; in-memory scope fixtures and local ledgers are not hosted-service qualification.
- **Experimental/repository systems:** `experiments/` implements verifiers, replay, candidate/evidence/report contracts and orchestration; `sim/` and `randomness_lab/` test research questions; `tools/`, `scripts/` and 61 GitHub workflows provide specialized checks, GitHub automation and source observation. See [research](../research/README.md), [testing](../TESTING.md), and [reproducibility evidence](../audits/2026-10-10-code-documentation-reconciliation.md).

## Failure and deployment boundaries

1. **No unattended merge path is implied.** Verification, human authority, and integration remain different stages.
2. **No default cloud multi-user controller is implied.** The local HTTP API is loopback-only with local session tokens; serverless/GitHub planning and local SQLite are not equivalents of enterprise auth.
3. **No universal hostile-code sandbox claim is implied.** Bubblewrap support is limited to Linux network-disabled admission under host capability constraints; raw process limits are not isolation.
4. **No CI green claim is made from source inspection.** New/modified documentation still needs exact-head link/schema/test gates when the PR is opened.
5. **No historical planned label is a current status.** The [2026-09-23 API catalog](../planning/API_V1_SURFACE_CATALOG_2026-09-23.md) is a planning snapshot; the current CLI/router and specifications win.

For developer help see [troubleshooting](../help/TROUBLESHOOTING.md), for source-by-source navigation see [module map](../reference/MODULE_MAP.md), and for the architectural contract outside this bounded as-built review see [root architecture](https://github.com/MSKazemi/idkmesh/blob/main/ARCHITECTURE.md).
