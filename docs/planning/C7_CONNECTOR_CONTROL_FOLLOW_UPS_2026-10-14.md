# C7 Connector Control: Slice Status and Follow-ups

**Date:** 2026-10-14  
**Status:** planning note; not a claim that any listed follow-up is implemented  
**Tracker:** #580 (umbrella, retains `needs-decomposition`)  
**Parent:** #570

This note records which C7 micro-slices the repository can honestly take next, and what each is
blocked on. It is derived from the code on `main`, not from the tracker's checklist.

## Landed in this slice (C7-F, single-connection read)

- `GET /api/v1/connections/{connection_id}` on the existing Control Tower service, backed by
  `ConnectorControlReadService.get_connection()` (same projection and fail-closed rules as the list).
- `ControlTowerClient.get_connection()`.
- Schema `idkmesh-control-tower-connection-response-v0.1`, example, OpenAPI entry, error catalog
  rows (`connection_not_found`, `invalid_connection_id`), authority-matrix row, access-log route
  template `/api/v1/connections/{connection_id}`.

Invariants this slice relies on and its tests exercise: the endpoint performs no probe, no secret
resolution, no dispatch, and no provider call; the id grammar excludes `/` and `:`; the session
token is checked before any lookup; a malformed id is a 400 that does not echo the value; a stored
row that does not match the public contract (or whose key disagrees with its `id`) is a 500
`connection_record_invalid` that does not echo row data.

## Landed in the second slice (C7-F remainder, driver listing)

- `GET /api/v1/connector-drivers` and `ControlTowerClient.list_connector_drivers()`, backed by
  `connector_control_read.list_connector_drivers()`.
- Serves only the registry descriptors (`kind`, `driver`, `version`), ordered by kind then driver id.
  The decision recorded here: the only registry constructible without live adapters is the offline
  fake-driver registry, so the envelope names it (`registry: "offline-fake"`, `live_adapters: false`)
  instead of presenting test doubles as live drivers. Capabilities are deliberately not served.
- Needs no store, reads no connector configuration, performs no probe, secret resolution, dispatch or
  provider call. GET/HEAD only, no query string (400), session token checked first (403). A
  declaration outside the kind/identifier grammar fails closed with 500 `driver_record_invalid`.
- Companions: schema `idkmesh-control-tower-connector-drivers-response-v0.1`, example, OpenAPI entry
  (static and generated), error-catalog row, authority-matrix row, spec section, access-log route
  template, tests in `tests/test_connector_drivers_api.py`.

## Remaining C7 slices

| Slice | State | Blocked on / next step |
| --- | --- | --- |
| C7-A service-layer extraction | partial | #682/#684 own Product Spine application-service composition. |
| C7-C WorkUnit/issue preview CLI | partial | Bind to the Product Spine service after #684; `route explain` already exists. |
| C7-E dedicated evidence CLI | partial | Converge on `control-tower` / `run evidence`; do not add a second evidence model. |
| C7-F remainder: registry/driver listing | done (descriptors only) | Landed as `GET /api/v1/connector-drivers` (see below). Still open: per-driver declared capabilities (a function of a connector configuration, not of the driver alone) and a live registry once real adapters exist. |
| C7-F remainder: latest probe / admission state | not started | `LocalMetadataStore.latest_probe()` exists, but probe records are free-form and would need their own public projection and schema before they can be served. |
| C7-G mutating HTTP auth boundary | pending | Align with #743; no network mutation endpoint may exist before it. |
| C7-H HTTP mutations (`POST /connections`, `:probe`, `:enable`, `:disable`) | pending | Needs C7-A, C7-G and API contracts. The `:verb` suffixes are already reserved by the id grammar. Any state-changing control must default to dry-run and must not itself grant execution authority. |

## Rules for the next slice

- Reuse `ConnectorControlReadService`; do not serialize stored rows verbatim.
- Keep one HTTP server (Control Tower); no connector-specific server.
- A new endpoint needs the same companion set as this slice: schema, example, OpenAPI entries (static
  and generated), conformance catalog entries, error-catalog rows, authority-matrix row, spec
  section, client method, and tests.
