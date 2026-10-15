---
title: "Control Tower API Quickstart"
description: "Start the local Control Tower, then read runs, evidence, events, the live event stream, the live OpenAPI definition and metrics with curl and the official Python client, including error handling. Every Python snippet is executed by a test."
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

To walk every run without writing the loop, `client.iter_runs(max_pages=10,
limit=50)` lazily yields run items, and `client.iter_run_pages(...)` lazily
yields whole pages with their metadata. Both need a page budget, refuse a
repeated cursor and raise instead of silently truncating; pages already yielded
stay valid. `collect_run_pages` is the all-or-nothing tuple form.

```python
for item in client.iter_runs(max_pages=2, limit=50):
    print(item["run_id"])
```

`get_run_attempts`, `get_run_evidence`, `list_work_units`, `get_work_unit`,
`get_project`, `list_connections`, `get_connection`, `list_connector_drivers` and `list_events` follow the same shape. Run
IDs may contain `/` and `:`; the client encodes them for you.

### Follow the event stream

`client.stream_events(...)` opens `GET /api/v1/events/stream` (Server-Sent
Events) and yields validated events in sequence order. It makes exactly one
request, never reconnects, and ends when the server, you, or a bound you set
ends it. Use it as a context manager so the connection, and the server's stream
slot, is released as soon as you stop.

`idle_timeout` is mandatory: the longest the client waits for the next byte.
The server sends a keepalive comment every 15 seconds, so pass at least 20 for a
quiet stream. Without `last_event_id` the stream starts at the live tail; with
it, every event whose sequence is greater is replayed first (`0` replays the
whole history), then live events follow. Filters (`project_id`, `run_id`,
`work_unit_id`, `event_type`) mean what they mean on `list_events`.

```python
with client.stream_events(
    idle_timeout=20.0, last_event_id=0, max_events=1
) as stream:
    for item in stream:
        print(item.sequence, item.event_type, item.event["run_id"])
    print(stream.request_id, stream.last_event_id, stream.end_reason)
```

Each `StreamedEvent` carries `sequence`, `event_type` and the full
`idkmesh-event` envelope. Before an event reaches you, the client checks that
the frame matches the documented envelope (exact key set, `kind`,
`schema_version`, `event_id`), that its sequence is strictly greater than the
previous one, that it matches your filters, and that `payload_digest` is the
digest of `payload` (`IntegrityError` otherwise). Anything else on the wire,
an unknown field, a duplicate field, a comment other than `keepalive` or
`stream-ended`, or a line or frame over `max_frame_bytes` (default 1 MiB), is a
`ProtocolError`, and the stream closes itself.

Iteration stops with `stream.end_reason` set to the server's marker
(`max-duration` after 300 seconds, `shutdown`, `store-error`) or to a bound you
set (`client-max-events`, `client-max-seconds`). **Resuming is your job**: open
a new stream with `last_event_id=stream.last_event_id`. Delivery is
at-least-once across connections, so dedupe on `event_id`. A stalled stream or a
connection that drops without a marker raises `TransportError`; resume the same
way. Errors sent before the stream starts (bad token, `invalid_last_event_id`,
`too_many_streams`) are the usual `ApiResponseError`. The server rejects a
`Last-Event-ID` beyond its newest event with `400 invalid_last_event_id`, so
never carry an ID over from a different store.

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

The client never retries unless you ask it to, because a hidden retry could
repeat a mutation. To opt read calls into a small, bounded, deterministic retry,
pass a `RetryPolicy`:

```python
from idkmesh.api_client import RetryPolicy

resilient = ControlTowerClient(
    "http://127.0.0.1:8770",
    os.environ["IDKMESH_CONTROL_TOWER_TOKEN"],
    timeout=5.0,
    retry=RetryPolicy(max_attempts=3, base_delay=0.25, max_delay=5.0),
)
result = resilient.status()
print(result.request_id, "exchanges used:", result.metadata.attempts)
```

The policy applies only to idempotent `GET` reads. It retries a transport
failure and an API error the server marked `retryable` with HTTP 429, 502, 503
or 504; it never retries an integrity or protocol failure, a non-retryable API
error, or opening an event stream. The wait before retry *n* is
`min(max_delay, base_delay * 2**(n-1))` with no jitter, so a run is
reproducible; a server `Retry-After` can lengthen it up to `max_delay`, and a
longer one is not waited out. `max_attempts` is 2-5 and `max_delay` at most 30
seconds. A final error carries `attempts`, and `ApiResult.metadata.attempts`
says how many exchanges a success took. Without a policy the client makes
exactly one exchange per call, as before. Writing your own loop is still fine:

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

- One HTTP request per call by default; retry is opt-in (`RetryPolicy`), limited
  to idempotent reads, bounded and deterministic. Redirects are never followed
  and nothing is replayed behind your back.
- The session token is never part of `repr(client)` or of any exception message.
- Loopback `http` destinations only, so the local token cannot be sent elsewhere.
- The whole-response digest in `X-IDKMesh-Content-Digest` is recomputed before
  any document is returned; embedded evidence and snapshot digests are checked
  independently.
- Request IDs are exposed on every result and error.
- An event stream has a mandatory idle timeout and a wall-clock bound, bounded
  lines and frames, strict parsing, and a digest check on every event; it never
  reconnects on its own.

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
| a typed TypeScript client generated from the OpenAPI document | open on #746, deferred until v1 stabilizes |
| publishing the Python client to a package index | tracked separately; today it ships inside the `idkmesh` checkout |

## Where next

To compare two cumulative metrics snapshots without misreporting restarts or unknown windows, follow the [source-backed metrics interval guide](API_METRICS_INTERVAL_GUIDE.md). Its evaluator is library-only, not another HTTP route or a rolling SLO service.

[Control Tower Local API v0.1](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md)
is the complete endpoint contract, and the
[CLI and HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) lists every shipped
command and route.
