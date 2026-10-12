---
title: "Control Tower API Quickstart"
description: "Start the local Control Tower, then read runs, evidence, events, the live OpenAPI definition and metrics with curl and the official Python client, including error handling. Every Python snippet is executed by a test."
---
# Control Tower API quickstart

Five minutes from a checkout to your first authenticated read, with `curl` and
with the official Python client (`idkmesh.api_client.ControlTowerClient`). You
should not need to read server code. Companion pages:
[error catalog](API_ERROR_CATALOG.md), [service limits](API_LIMITS.md), and the
[compatibility and deprecation policy](../API_V1_BETA_MIGRATION_GUIDE.md).

**Scope.** This is the **local, loopback, single-token read and inspect
profile**. It is not a multi-user or network service and the token is a local
boundary, not an identity. Every Python snippet below is executed in-process
against a real server by `tests/test_api_reference_docs.py`, so a snippet that
stops working fails the suite. The `curl` URLs are checked against the
generated OpenAPI document.

## 1. Start the server

You need Python 3.11 or later and a repository checkout.

```bash
python -m pip install -e .
export IDKMESH_CONTROL_TOWER_TOKEN="$(openssl rand -hex 32)"
idkmesh run create examples/api/product-spine-run.example.json \
  --store state.sqlite --idempotency-key quickstart-1
idkmesh control-tower --no-browser --port 8770 --product-spine-store state.sqlite
```

The token is 32-4096 characters from letters, digits, `-`, `.`, `_` and `~`.
Keep it out of shell history and version control. The server binds `127.0.0.1`
only. Without `--product-spine-store` the read-model routes answer
`503 product_spine_store_not_configured`. The
[run lifecycle tutorial](../RUN_LIFECYCLE_TUTORIAL.md) builds the store step by
step.

## 2. First request with curl

Run this in a second terminal with the same `IDKMESH_CONTROL_TOWER_TOKEN`.
Send the token only in the `X-IDKMesh-UI-Token` header.

```bash
curl -s -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/status
curl -s -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  "http://127.0.0.1:8770/api/v1/runs?limit=10"
curl -s -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/runs/run/example-1
```

`GET /healthz` and `GET /readyz` need no token and expose no project state.

## 3. The same with the Python client

The client is standard-library only. Its `timeout` is mandatory by
construction: omitting it is a `TypeError`.

```python
import os

from idkmesh.api_client import ControlTowerClient

client = ControlTowerClient(
    "http://127.0.0.1:8770",
    os.environ["IDKMESH_CONTROL_TOWER_TOKEN"],
    timeout=5.0,
)
status = client.status()
print(status.request_id, status.value["kind"])
print(status.value["operations"]["limits"]["max_concurrent_requests"])
```

Every call returns an `ApiResult` with `value` (the verified document) and
`request_id` (also in `metadata`) for correlation and bug reports.

### Discover the live API

`client.get_openapi()` downloads the OpenAPI 3.x definition served by the exact
build you are talking to (`GET /api/v1/openapi.json`), and `client.get_metrics()`
reads the fixed-cardinality, privacy-safe operational metrics. Both fail closed:
a document that is not OpenAPI 3.x with `info` and `paths`, or a metrics
document of the wrong kind, raises `ProtocolError`.

```python
spec = client.get_openapi()
print(spec.value["openapi"], len(spec.value["paths"]), "paths")
metrics = client.get_metrics()
print(metrics.value["kind"])
```

### Read runs

List methods return a `ListPage`. Cursors are opaque: pass `next_cursor` back
unchanged and never build one. `limit` is 1-200 and is validated before any
network I/O.

```python
page = client.list_runs(limit=50)
for item in page.value.items:
    print(item["run_id"], item["state"])
while page.value.next_cursor is not None:
    page = client.list_runs(limit=50, cursor=page.value.next_cursor)

run = client.get_run("run/example-1")
print(run.request_id, run.value["run"]["state"])
```

`get_run_attempts`, `get_run_evidence`, `list_work_units`, `get_work_unit`,
`get_project`, `list_connections` and `list_events` follow the same shape. Run
IDs may contain `/` and `:`; the client encodes them for you.

### Inspect an evidence report

`inspect_run_evidence` sends a report you hold to `POST /api/v1/run-evidence/inspect`
and returns the deterministic inspection snapshot. Nothing is stored. The client
recomputes the snapshot digest and raises `IntegrityError` if it does not match.

```python
import json
from pathlib import Path

report = json.loads(Path("examples/api/run-evidence-report.example.json").read_text())
inspection = client.inspect_run_evidence(report)
print(inspection.value["snapshot_digest"])
```

### Handle errors

Server errors arrive as `ApiResponseError` with the stable `code`, the
`retryable` flag, the HTTP `status_code`, optional `details`, and the
`request_id`. Branch on `code`; the full list is in the
[error catalog](API_ERROR_CATALOG.md).

```python
from idkmesh.api_client import ApiResponseError

try:
    client.get_run("run/does-not-exist")
except ApiResponseError as error:
    print(error.status_code, error.code, error.retryable, error.request_id)
    assert error.code == "run_not_found"
```

The client never retries on its own, because a hidden retry could repeat a
mutation. If you retry, retry only reads, only when `retryable` is true, and
honour the server's hint:

```python
import time


def read_with_backoff(call, attempts=3):
    for attempt in range(attempts):
        try:
            return call()
        except ApiResponseError as error:
            if not error.retryable or attempt == attempts - 1:
                raise
            time.sleep(error.details.get("retry_after_seconds", 1))


print(read_with_backoff(client.status).request_id)
```

The other exception classes are `ClientConfigurationError` (unsafe or invalid
setup, before any I/O), `TransportError` (the one exchange could not complete),
`ProtocolError` (the response broke the published contract, including a response
that names a different run, work unit or project than you asked for) and
`IntegrityError` (a content or evidence digest did not verify). All derive from
`ControlTowerClientError`.

## What the client guarantees

- One HTTP request per call; no retry, no redirect, no hidden replay.
- Loopback `http` destinations only, so the local token cannot be sent elsewhere.
- The whole-response digest in `X-IDKMesh-Content-Digest` is recomputed before
  any document is returned; embedded evidence and snapshot digests are checked
  independently.
- Request IDs are exposed on every result and error.

## Response headers

| Header | Meaning |
|---|---|
| `X-Request-ID` | one ID per response, for correlation only; a safe `X-Request-ID` you send is echoed |
| `X-IDKMesh-Content-Digest` | `sha256:` digest of the canonical response document; the client verifies it |
| `ETag` | the same digest as a quoted entity tag |
| `X-IDKMesh-Service` and `X-IDKMesh-Service-Version` | which service and build answered |
| `X-IDKMesh-API-Version` | the URL version served, currently `v1` |
| `X-IDKMesh-Read-Only` | `true`: this service grants no write authority |
| `Retry-After` | seconds to wait; present on the three retryable `503` capacity errors |
| `Allow` | permitted methods; present on `405` |

## Versioning and deprecation

The URL carries the compatibility version (`/api/v1/`); the object
`schema_version` inside a response versions independently and a new one is not a
new API version. Error codes are frozen, schemas are never edited incompatibly in
place, and any deprecation is announced with a replacement and an earliest
removal in the CHANGELOG. The binding rules, the announcement classes and the
behaviour changes found while qualifying the API are in the
[compatibility, deprecation and migration guide](../API_V1_BETA_MIGRATION_GUIDE.md).

## Planned, not available today

These appear in issue [#746](https://github.com/MSKazemi/idkmesh/issues/746) and
are **not** built. Do not code against them.

| Planned | Status |
|---|---|
| `client.record_human_decision(...)` and `POST /api/v1/human-decisions` | blocked on [#740](https://github.com/MSKazemi/idkmesh/issues/740): it needs an authenticated, accountable identity, and the local session token is not one |
| `GET /api/v1/runs/{run_id}/decisions` | same blocker (#740); the route answers `404 not_found` today |
| a Python client helper for the event stream | open on #746. The server stream, `GET /api/v1/events/stream` (Server-Sent Events, resumable with `Last-Event-ID`), exists and can be read with plain HTTP; the client has no wrapper for it |
| a typed TypeScript client generated from the OpenAPI document | open on #746, deferred until v1 stabilizes |
| publishing the Python client to a package index | tracked separately; today it ships inside the `idkmesh` checkout |

## Where next

[Control Tower Local API v0.1](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md)
is the complete endpoint contract, and the
[CLI and HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) lists every shipped
command and route.
