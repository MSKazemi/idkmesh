---
title: "API v1 Beta: Compatibility, Deprecation and Migration Guide"
description: "What a consumer of the IDKMesh Control Tower API can rely on, how changes and deprecations are announced, and the behaviour changes to check before pinning a beta."
---
# API v1 beta: compatibility, deprecation and migration

This guide is for anyone calling the Control Tower local API (`/api/v1/...`) or
using the Python client (`idkmesh.api_client.ControlTowerClient`). It states what
is stable, how change is announced, and which behaviour changed while the API was
being qualified, so you can check your integration against it.

The API is a **loopback, single-token, read/inspect profile**. It is not a
multi-user service, and nothing here describes network exposure. Whether a given
revision is releasable as "v1 beta" is decided by the
[beta release gate](specifications/API_V1_BETA_RELEASE_GATE_V0_1.md); until that
gate reports *ready*, treat every behaviour below as pre-beta.

## What you can rely on

Frozen by [API Conventions v0.1](specifications/API_CONVENTIONS_V0_1.md); a change
to any of these is a *breaking* change that needs an explicit decision record:

- the `/api/v1/` prefix and the separate `/healthz` and `/readyz` probes;
- the response and error envelopes (`api_version`, `schema_version`, `kind`,
  `ok`, and `error.code`), and the HTTP status mapping;
- error **`code` values** — match on `code`, never on `message`, which is
  explanatory text and may change;
- one request ID per response (`X-Request-ID`), for correlation only;
- object schemas under `schemas/`: a shipped schema file is never edited
  incompatibly in place. A narrowing change arrives as a new, separately
  versioned file, and `tools/schema_compat_check.py` fails the required PR gate
  otherwise.

URL version and object schema version are independent. A new `schema_version`
inside `/api/v1` is not a new API version.

## What is not stable yet

- Human Decision records, run `decisions` and `attempts` sub-resources, and any
  mutation beyond inspecting a supplied evidence report are **not built**
  (issues #740, #739). Do not code against their absence being permanent.
- No multi-user or network authentication profile exists (#743). The session
  token is a local boundary, not an identity.
- The typed web client is not built and the Python client is not published to a
  package index (#746, #769).
- Anything under `docs/specifications/` marked *experimental*.

## How change is announced

| Class | What it means for you | Where it appears |
|---|---|---|
| Documentation only | none | CHANGELOG |
| Additive compatible | new fields, endpoints or codes — ignore what you do not know | CHANGELOG, **Added** |
| Behaviour clarification | a previously unspecified case now behaves one defined way | CHANGELOG, **Fixed** |
| Deprecated | still works; has a replacement and an earliest-removal version | CHANGELOG, **Deprecated** |
| Breaking | needs migration; has a decision record and migration notes | CHANGELOG and release notes |

A deprecation states the affected version/path/object, the replacement, the
earliest removal date or version, and a migration guide (section 20 of the
conventions). Nothing is removed merely because a newer UI stopped using it.

**No deprecation is currently in force.** The CHANGELOG has no *Deprecated*
entries; if that changes, this guide is updated in the same change.

## Behaviour changes to check

These were clarifications found while qualifying the API
(issue #745). Each is covered by a test; none changed a documented contract, but
each changes what an unusual request returns. Check the ones that apply to you.

| Request | Before | Now | Test |
|---|---|---|---|
| Deeply nested JSON body or report | raw `RecursionError` escaped | controlled error (`ProtocolError` in the client, `invalid_event_json` for audit events) | `tests/test_api_qualification_fuzz.py` |
| `Accept` with an explicit `q=0` | served anyway | `406 not_acceptable` if all entries are `q=0`; `q=0` on the vendor type falls back to `application/json` | `tests/test_api_header_boundary_fuzz.py` |
| Response `Content-Type` differing only in case or whitespace | client raised `ProtocolError` | accepted, normalised like the server | `tests/test_api_header_boundary_fuzz.py` |
| `Content-Length` such as `+2` or `-0` | accepted | `400 invalid_content_length` (digits only, RFC 9110) | `tests/test_api_header_boundary_fuzz.py` |
| `X-IDKMesh-UI-Token` with a non-ASCII byte | connection dropped, no response | `403 invalid_session_token` | `tests/test_api_security_matrix.py` |
| Unauthenticated request with a stray query string | `400 unexpected_query_parameters` | `403 invalid_session_token` (the query is judged only after the token) | `tests/test_api_security_matrix.py` |
| `PUT`/`PATCH`/`DELETE`/`TRACE` on `/readyz` | `404 not_found` | `405 method_not_allowed`, `Allow: GET, HEAD` | `tests/test_api_security_matrix.py` |
| Reading an event whose stored payload no longer matches its digest | altered content served | `500 store_error`; the altered content is withheld | `tests/test_api_storage_integrity.py` |
| `ProductSpineRun.transition()` given identity or authority fields (library) | silently applied | `invalid_update` | `tests/test_api_state_idempotency_properties.py` |

## Making your integration robust

- Branch on `error.code` and on `error.retryable`; honour `Retry-After` on `503`.
- The Python client sends exactly one HTTP request per call and never retries on
  its own. Its errors form a stable taxonomy (`ClientConfigurationError`,
  `TransportError`, `ProtocolError`, `IntegrityError`, `ApiResponseError`).
- Treat unknown fields as additive; do not reject a response for having them.
- Send `Accept: application/json` (or the vendor type) and a numeric
  `Content-Length`; send the token only in `X-IDKMesh-UI-Token`.

## Checking a revision

```bash
make qualify-api BASE=<previous-tag> STRICT=1   # contract, fuzz, security, reliability, install
make beta-readiness                              # is the release gate satisfied?
python tools/schema_compat_check.py --base <previous-tag>
```

`make qualify-api` writes a JSON report with the exact commands and results. See
[`TESTING.md`](TESTING.md#api-release-qualification).

## Reporting a problem

Report a compatibility regression as an issue with the request, the response, and
the revision. Report a vulnerability through `SECURITY.md`, never a public issue.
