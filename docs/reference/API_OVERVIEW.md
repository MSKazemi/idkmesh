---
title: "Control Tower API Overview"
description: "One page for an integrator: what the local Control Tower API is, how it authenticates (a local session token, no scopes), every route, the response schemas, the OpenAPI download, event streaming, the official Python client, and what is not built yet."
---
# Control Tower API overview

Start here if you want to call the IDKMesh Control Tower without reading server
code. This page is a map; each topic links to the page that owns it.

## What this API is, and is not

The Control Tower API is a **local, loopback, read and inspect** HTTP API at
`/api/v1/`. It reports capability status, retained run evidence, the
Product Spine read model (runs, attempts, work units, projects, connection
metadata), operational metrics, and an event feed. It grants **no write
authority**: it does not record human decisions, dispatch work, change canonical
state, push Git or merge. It is not a multi-user or network service.

## Authentication and scopes

- Every `/api/v1/` route needs the local session token, sent only in the
  `X-IDKMesh-UI-Token` header. `/healthz` and `/readyz` need no token and expose
  no project state.
- The token is a single shared secret for the local process, **not an identity**:
  there are no users, roles or **scopes** today, and a valid token can call every
  read route. Do not treat it as an accountable human principal.
- Token format and handling are in the [quickstart](API_QUICKSTART.md#1-start-the-server).
  The Python client refuses any non-loopback `http` destination so the token
  cannot be sent elsewhere, never follows redirects, and keeps the token out of
  `repr()` and exception messages.
- The *proposed* endpoint-to-authority mapping for a future network profile is
  the [API authority matrix](../specifications/API_AUTHORITY_MATRIX_V0_1.md); it
  enforces nothing today.

## Routes

The authoritative list is the OpenAPI document (see
[Download the OpenAPI definition](#download-the-openapi-definition)); the
[CLI and HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) shows examples.

| Route | Purpose | Python client |
|---|---|---|
| `GET /api/v1/status` | capability status and the limits in force | `status()` |
| `GET /api/v1/openapi.json` | the running API definition | `get_openapi()` |
| `GET /api/v1/metrics` | fixed-cardinality operational metrics | `get_metrics()` |
| `POST /api/v1/run-evidence/inspect` | inspect an evidence report you supply | `inspect_run_evidence()` |
| `GET /api/v1/runs` | list runs (filters, cursor) | `list_runs()`, `iter_runs()` |
| `GET /api/v1/runs/{run_id}` | one run | `get_run()` |
| `GET /api/v1/runs/{run_id}/attempts` | the run's attempts | `get_run_attempts()` |
| `GET /api/v1/runs/{run_id}/evidence` | retained evidence report | `get_run_evidence()` |
| `GET /api/v1/work-units`, `GET /api/v1/work-units/{work_unit_id}` | derived work units | `list_work_units()`, `get_work_unit()` |
| `GET /api/v1/projects/{project_id}` | one project summary | `get_project()` |
| `GET /api/v1/connections` | secret-free connector metadata | `list_connections()` |
| `GET /api/v1/events` | keyset-paginated event list | `list_events()` |
| `GET /api/v1/events/stream` | Server-Sent Events | `stream_events()` |
| `GET /healthz`, `GET /readyz` | liveness and readiness, no token | not wrapped |

## Download the OpenAPI definition

The definition of the exact build you are talking to is served at
`GET /api/v1/openapi.json`:

```bash
curl -s -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  http://127.0.0.1:8770/api/v1/openapi.json -o control-tower-openapi.json
```

or `ControlTowerClient.get_openapi()`. A reviewed, versioned snapshot of the
public surface is also tracked in the repository as
[`openapi.yaml`](https://github.com/MSKazemi/idkmesh/blob/main/openapi.yaml).
When the two differ, the running server is the authority for that build.

## Schema catalog

Response documents carry a `kind` and `schema_version` and validate against the
JSON Schemas in
[`schemas/`](https://github.com/MSKazemi/idkmesh/tree/main/schemas). Schemas are
never edited incompatibly in place (see the
[compatibility policy](../API_V1_BETA_MIGRATION_GUIDE.md)).

| Document | Schema file |
|---|---|
| error envelope | `idkmesh-api-error-v0.1.schema.json` |
| list page | `idkmesh-list-v0.1.schema.json` |
| event | `idkmesh-event-v0.1.schema.json` |
| status | `idkmesh-control-tower-status-v0.1.schema.json` |
| operational metrics | `idkmesh-api-operational-metrics-v0.1.schema.json` |
| run | `idkmesh-control-tower-run-response-v0.1.schema.json` |
| run attempts | `idkmesh-control-tower-run-attempts-response-v0.1.schema.json` |
| run evidence | `idkmesh-control-tower-run-evidence-response-v0.1.schema.json` |
| evidence inspection | `idkmesh-control-tower-inspection-response-v0.1.schema.json` |
| work unit | `idkmesh-control-tower-work-unit-response-v0.1.schema.json` |
| project | `idkmesh-control-tower-project-response-v0.1.schema.json` |

## Errors, limits and event streaming

- Every stable error code, status and retry rule: [error catalog](API_ERROR_CATALOG.md).
- Timeouts, caps, body and header bounds, drain behaviour: [service limits](API_LIMITS.md).
- Event streaming: [quickstart, "Follow the event stream"](API_QUICKSTART.md#follow-the-event-stream)
  and the stream section of the
  [Control Tower Local API spec](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md).
  Delivery is at-least-once with a `Last-Event-ID` resume; de-duplicate on
  `event_id`.

## Python client

`idkmesh.api_client.ControlTowerClient` is standard-library only. It enforces a
mandatory timeout, verifies the whole-response `X-IDKMesh-Content-Digest` and
embedded evidence digests, exposes the request ID on every result, and raises a
stable exception taxonomy. It makes one exchange per call unless you pass a
`RetryPolicy`, which retries only idempotent reads, with bounded deterministic
backoff. Details and runnable snippets: [quickstart](API_QUICKSTART.md).

## Versioning, deprecation and migration

The URL carries the compatibility version; deprecations are announced in the
CHANGELOG with a replacement and an earliest removal. The binding rules and the
behaviour changes to check before pinning a beta are in the
[compatibility, deprecation and migration guide](../API_V1_BETA_MIGRATION_GUIDE.md).

## Deployment and threat model

The server binds loopback only. The security questions that must be answered
before any exposure beyond loopback are in the
[API threat model](../security/API_THREAT_MODEL_V0_1.md) (a planning baseline,
not a certification).

## Not built yet

Do not code against these (tracked on
[#746](https://github.com/MSKazemi/idkmesh/issues/746)):

- `record_human_decision(...)` and a decision route: blocked on
  [#740](https://github.com/MSKazemi/idkmesh/issues/740) (accountable identity).
- A typed TypeScript/web client generated from the OpenAPI document: deferred
  until v1 stabilizes; no JavaScript client is shipped or claimed.
- Publishing the Python client to a package index: the client ships inside the
  `idkmesh` checkout today.
