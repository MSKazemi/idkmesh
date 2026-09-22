# Connector Control API v0.1

**Status:** experimental design contract  
**Date:** 2026-09-22  
**Authority:** configuration/dispatch interface only; this API grants no acceptance or merge authority.

This specification defines the first product-facing API for connecting repositories, coding agents, model providers and execution backends to IDKMesh.

It does **not** replace WorkUnit, ResultManifest, EvaluatorPlan, VerificationResult, compute offers, or the existing A2A/MCP bindings.

## 1. Principles

1. A connection stores provider metadata and a **secret reference**, never a raw secret.
2. A model connection is not automatically a coding agent.
3. Agent completion becomes a candidate result, never acceptance.
4. GitHub/project authority is constrained independently from provider credentials.
5. Unknown connector kinds, drivers, versions and states fail closed.
6. CLI and HTTP surfaces use the same service layer and data contracts.
7. Every live call has an auditable connection/run identifier.

## 2. Version identifier

Configuration/API objects use:

```text
idkmesh.io/v1alpha1
```

The HTTP prefix is:

```text
/v1
```

The HTTP prefix is intentionally decoupled from alpha object-schema naming so future compatible fields do not require a new URL for every additive change.

## 3. Connection object

Example:

```json
{
  "api_version": "idkmesh.io/v1alpha1",
  "id": "jules-main",
  "kind": "agent",
  "driver": "jules",
  "enabled": true,
  "auth": {
    "secret_ref": "env:JULES_API_KEY"
  },
  "settings": {
    "source": "sources/github/MSKazemi/idkmesh",
    "starting_branch": "main",
    "require_plan_approval": true
  },
  "policy": {
    "task_classes": ["coder"],
    "allowed_risk": ["low"],
    "max_concurrency": 1,
    "external_processing": true,
    "project_spend_usd_max": 0
  }
}
```

### Required fields

- `api_version`;
- `id`;
- `kind`;
- `driver`;
- `enabled`.

### Connection kinds

- `scm`;
- `agent`;
- `model`;
- `execution`.

### Reserved fields

- `auth.secret_ref`;
- `settings`;
- `policy`.

Unknown top-level fields should be rejected in the first implementation unless the schema explicitly provides an extension namespace.

## 4. Secret references

Initial schemes:

```text
env:VARIABLE_NAME
```

A future implementation may add explicit resolvers such as:

```text
vault:...
onepassword:...
aws-secrets-manager:...
```

without changing connection semantics.

Prohibited:

```json
{
  "api_key": "actual-secret-value"
}
```

A connection may be stored even when its secret is unavailable; its probe state then reports a configuration/authentication failure and it is ineligible for routing.

## 5. Connection probe

Example:

```json
{
  "connection_id": "jules-main",
  "status": "healthy",
  "checked_at": "2026-09-22T12:00:00Z",
  "driver": {
    "id": "jules",
    "version": "0.1"
  },
  "observed": {
    "source": "sources/github/MSKazemi/idkmesh",
    "capabilities": ["coder", "git", "tests", "remote_sandbox"]
  },
  "auth": {
    "configured": true
  },
  "warnings": []
}
```

Probe statuses:

- `healthy`;
- `degraded`;
- `unavailable`;
- `disabled`.

A probe must never return credential values.

## 6. Work preview

`POST /v1/work-units:preview`

Purpose:

- convert an issue/spec/project event into the existing canonical WorkUnit;
- show derived scope, risk, path and validation requirements;
- perform no dispatch.

Example request:

```json
{
  "project_id": "MSKazemi/idkmesh",
  "source": {
    "type": "github_issue",
    "number": 123
  }
}
```

Response contains:

- canonical WorkUnit;
- source revision used;
- policy warnings;
- whether human approval is required before dispatch.

Issue text is untrusted input and cannot set connector credentials, executable paths, secret refs, merge authority, or repository administration permissions.

## 7. Route resolution

`POST /v1/routes:resolve`

This is advisory/deterministic routing, not execution.

Request:

```json
{
  "project_id": "MSKazemi/idkmesh",
  "work_unit": { "...": "canonical WorkUnit" }
}
```

Response:

```json
{
  "eligible": [
    {
      "connection_id": "jules-main",
      "reasons": ["task_class_supported", "risk_allowed", "capacity_available"]
    }
  ],
  "ineligible": [
    {
      "connection_id": "local-goose",
      "reasons": ["required_model_unavailable"]
    }
  ],
  "selected": null
}
```

The endpoint should not select a connector unless the caller explicitly asks for the project's deterministic auto-routing policy to be applied.

## 8. Run creation

`POST /v1/runs`

Request:

```json
{
  "project_id": "MSKazemi/idkmesh",
  "work_unit": { "...": "canonical WorkUnit" },
  "connection_id": "jules-main",
  "approval": {
    "dispatch_approved": true
  }
}
```

Response:

```json
{
  "id": "run-...",
  "state": "dispatched",
  "work_unit_id": "wu-...",
  "work_unit_digest": "sha256:...",
  "connection_id": "jules-main",
  "source_revision": "<commit-sha>",
  "external_ref": {
    "provider": "jules",
    "id": "sessions/..."
  }
}
```

Creating a run does not approve any future code change.

## 9. Run state

States:

- `created`;
- `admitted`;
- `dispatched`;
- `waiting_for_agent`;
- `candidate_ready`;
- `verification_pending`;
- `verified`;
- `verification_failed`;
- `awaiting_human_decision`;
- `integrated`;
- `rejected`;
- `cancelled`;
- `failed`.

State transitions must be monotonic except for explicitly modeled retry/attempt records.

A retry creates a new attempt identity; it must not rewrite historical evidence.

## 10. Run inspection

`GET /v1/runs/{run_id}`

Minimum response fields:

- run ID/state;
- WorkUnit ID/version/digest;
- source revision;
- connection/driver/version;
- execution backend;
- external provider/session/job reference;
- attempt number;
- timestamps;
- candidate reference when available;
- ResultManifest reference;
- VerificationResult references;
- human-decision state;
- failure classification.

## 11. Run events

`GET /v1/runs/{run_id}/events`

Events are append-only observations such as:

- `run.created`;
- `run.dispatched`;
- `agent.plan_ready`;
- `agent.progress`;
- `agent.completed`;
- `candidate.discovered`;
- `result.normalized`;
- `verification.started`;
- `verification.completed`;
- `human.decision_recorded`;
- `run.failed`;
- `run.cancelled`.

Provider-specific payloads belong under an extension namespace and must not redefine canonical state.

## 12. Cancellation

`POST /v1/runs/{run_id}:cancel`

Cancellation means:

- ask the external/local worker to stop when supported;
- mark the attempt accordingly;
- preserve any evidence already produced;
- do not delete provider history to make the run appear clean.

Cancellation is best effort for external systems whose API cannot guarantee immediate stop.

## 13. Connection management endpoints

### List

`GET /v1/connections`

### Create

`POST /v1/connections`

The API accepts secret references only.

### Inspect

`GET /v1/connections/{connection_id}`

### Probe

`POST /v1/connections/{connection_id}:probe`

### Enable/disable

`POST /v1/connections/{connection_id}:enable`

`POST /v1/connections/{connection_id}:disable`

Deleting a connection should not delete historical run/evidence records.

## 14. Project endpoints

Minimum:

- `GET /v1/projects`;
- `POST /v1/projects`;
- `GET /v1/projects/{project_id}`.

Project record should include:

- SCM/repository identity;
- default branch;
- policy profile;
- allowed connector IDs or connector classes;
- project spend ceiling;
- external-processing policy;
- auto-dispatch risk ceiling.

Project policy never contains provider API keys.

## 15. GitHub webhook ingress

`POST /v1/webhooks/github`

Requirements:

- verify `X-Hub-Signature-256`;
- record/check GitHub delivery ID;
- reject unsupported event types;
- de-duplicate replayed deliveries;
- parse payload as untrusted input;
- map only configured repository installations;
- never treat a label/comment as permission to bypass project policy.

Initial accepted event families can be limited to:

- issues;
- issue_comment;
- pull_request;
- check_suite/check_run if needed for observation.

Start with label/manual dispatch, not every event.

## 16. Candidate references

A run may point to one of:

```json
{
  "type": "github_pull_request",
  "repository": "MSKazemi/idkmesh",
  "number": 999,
  "head_sha": "..."
}
```

or:

```json
{
  "type": "artifact_bundle",
  "locator": "file://...",
  "digest": "sha256:..."
}
```

The normalizer converts the external candidate into canonical ResultManifest/artifact evidence.

## 17. Model connection example

```json
{
  "api_version": "idkmesh.io/v1alpha1",
  "id": "gemini-compat",
  "kind": "model",
  "driver": "openai-compatible",
  "enabled": true,
  "auth": {
    "secret_ref": "env:GEMINI_API_KEY"
  },
  "settings": {
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "model": "<configured-model>"
  },
  "policy": {
    "external_processing": true,
    "project_spend_usd_max": 0
  }
}
```

Local Ollama can use the same driver with localhost base URL and no secret reference when its local policy permits that.

## 18. Local agent connection example

```json
{
  "api_version": "idkmesh.io/v1alpha1",
  "id": "goose-local",
  "kind": "agent",
  "driver": "cli",
  "enabled": true,
  "settings": {
    "preset": "goose",
    "model_connection_id": "ollama-local",
    "execution_connection_id": "idkmesh-node-local"
  },
  "policy": {
    "task_classes": ["coder", "researcher"],
    "allowed_risk": ["low"],
    "network": "disabled"
  }
}
```

The `preset` resolves to maintainer-controlled executable/arguments. WorkUnit content must not inject or replace those command templates.

## 19. Error envelope

Example:

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Connector is temporarily rate limited.",
    "retryable": true,
    "connection_id": "jules-main",
    "run_id": "run-...",
    "details": {
      "retry_after_seconds": 120
    }
  }
}
```

Initial error codes:

- `configuration_error`;
- `authentication_error`;
- `authorization_error`;
- `rate_limited`;
- `quota_exhausted`;
- `provider_unavailable`;
- `source_not_connected`;
- `sandbox_failure`;
- `agent_failed`;
- `timeout`;
- `cancelled`;
- `result_normalization_error`;
- `policy_denied`;
- `verification_failed`;
- `conflict`;
- `not_found`.

Do not include secrets or raw authorization headers in `details`.

## 20. Idempotency

Any mutating HTTP call should support an idempotency key.

Required first:

- run creation;
- GitHub webhook processing;
- provider session creation where duplicate external work is possible.

If a retry arrives with the same idempotency key and equivalent request digest, return the existing object.

If the same key is reused for different content, fail with `conflict`.

## 21. Authentication for the control API

Bootstrap local mode may bind only to localhost and rely on local user access.

A networked/hosted control plane requires explicit authentication/authorization before it can mutate connection or run state.

Do not expose an unauthenticated write-capable control service.

GitHub webhook authentication is separate from operator/API authentication.

## 22. Data retention

Retain:

- canonical object identifiers/digests;
- configuration minus secrets;
- run state/events;
- provider/external IDs;
- candidate/result/verification references;
- human decision.

Do not retain provider credentials.

Provider prompts/responses should be retained only to the extent required for provenance/replay and permitted by data policy; prefer bounded task/evidence artifacts over storing unnecessary conversational material.

## 23. Compatibility

This API is a control surface above the existing semantic contracts:

```text
Connector API
 -> WorkUnit
 -> WorkerAdapter / external agent
 -> ResultManifest
 -> EvaluatorPlan
 -> VerificationResult
 -> Evidence Report
 -> human decision
```

A change to this control API must not silently change the meaning of those canonical objects.
