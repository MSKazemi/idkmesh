# ADR-0021 — Serve WorkUnits and Projects as Read Models Derived from Stored Runs

**Status:** Accepted
**Date:** 2026-10-01

## Context

Issue #739 (API-4) lists eight read surfaces. Three are shipped on `main`
(`GET /api/v1/runs`, `GET /api/v1/runs/{run_id}`,
`GET /api/v1/runs/{run_id}/attempts`); `/evidence` and `/decisions` are
blocked on the content store owned by issue #740. That leaves
`GET /api/v1/work-units`, `GET /api/v1/work-units/{id}` and
`GET /api/v1/projects/{project_id}`.

Reading the code rather than the issue text shows what the Product Spine
actually persists:

- A run stores a WorkUnit **reference** only:
  `{id, version, digest, source_revision}`
  (`schemas/idkmesh-product-spine-run-v0.1.schema.json`). No component stores
  a WorkUnit body.
- `project_id` is a bare string on the run. No project record or store
  exists; `project-manifest.schema.json` is a repository file contract, not a
  served resource.
- Nothing in the run store lets a caller ask "which runs used this WorkUnit"
  or "what has this project run", although both are answerable from data
  already held.

The decision is therefore not *whether* to serve these surfaces but *what they
may truthfully claim*. Issue #739 requires stable identities, exact
source-revision/digest binding, deterministic ordering, bounded filters,
cursor pagination, no hidden winner selection, explicit 404 behavior and no
mutation authority. ADR-0016 requires one API shape with separate authority
and forbids a read surface from acquiring write or selection authority.

## Decision

`work-units` and `projects` are **read models derived on demand from stored
run projections**. They introduce no new store, no new write path and no field
that is not a pure function of stored run references.

1. **WorkUnit resource**, keyed by WorkUnit `id`:
   - `id`;
   - `run_count`: number of stored runs referencing this id;
   - `revisions`: the distinct `{version, digest, source_revision}` references
     seen for this id, each with its own `run_count`, ordered ascending by
     `(version, digest, source_revision)`.
   No WorkUnit body is returned, because none is stored; `digest` is the
   binding a caller uses to fetch or verify a body elsewhere.
2. **Project resource**, keyed by `project_id`:
   - `project_id`;
   - `run_count`;
   - `runs_by_state`: every canonical run state present as a key, zero-filled,
     so the shape is identical for every project;
   - `work_unit_count`: number of distinct WorkUnit ids referenced.
   Per-project WorkUnits are reached with `GET /api/v1/work-units?project_id=`,
   not embedded, so the response stays bounded.
3. **No hidden winner selection.** Neither resource exposes a "latest",
   "current" or "preferred" revision and neither exposes a health, status or
   score rollup. Revisions and states are ordered by explicit keys only.
4. **Identity and routing.** `GET /api/v1/work-units/{id}` takes the entire
   path remainder as the literal id, because WorkUnit ids share the run-id
   grammar and may contain `/`. v0.1 reserves no sub-resource suffix for
   work-units; adding one requires a new ADR that extends ADR-0019's
   path-only resolution rule. `GET /api/v1/projects/{project_id}` follows the
   same literal-remainder rule.
5. **Listing.** `GET /api/v1/work-units` is ordered by `id` ascending,
   keyset-paginated with an opaque self-issued cursor
   (`product-spine-work-unit-list-cursor-v1`), bounded by the existing
   `limit` range, with one declared filter, `project_id`. Any other query
   parameter fails with the conventions' explicit unknown-parameter error.
   There is no `GET /api/v1/projects` list in this ADR; it is not in #739's
   target surfaces and is deferred.
6. **Errors and authority.** Same local API token and same
   `product_spine_store_not_configured` behavior as `/runs`. Unknown ids return
   `work_unit_not_found` / `project_not_found` (404). The endpoints are `GET`
   only and add no authority, matching ADR-0016.
7. **Contracts.** Each resource gets a frozen JSON Schema
   (`idkmesh-work-unit-resource-v0.1`, `idkmesh-project-resource-v0.1`) and
   reuses the existing `idkmesh-list-v0.1` envelope. ADR-0020's
   backward-compatibility gate applies from first commit.

## Consequences

### Positive

- #739's remaining unblocked surfaces ship against real data with no new
  persistence and no migration.
- Every field is checkable against the run store, so the read model cannot
  drift from the run record or claim something the system does not hold.
- A WorkUnit that ran at several revisions is visible as several explicit
  revisions rather than collapsed to one.

### Costs

- Derivation scans stored run projections via `json_extract`, as `list_runs`
  already does for `project_id`. Acceptable at local development-store scale;
  a dedicated index or table is a revisit condition, not a v0.1 requirement.
- A WorkUnit or project that has never had a run is invisible. That is a
  property of the data held, and the documentation must say so.
- Counts are consistent only per request: a concurrent run creation can
  change them between two calls. Cursor pagination over a mutable set carries
  the same caveat as `/runs`.

## Alternatives considered

### Add dedicated WorkUnit and project stores first

Rejected. It needs authority and lifecycle decisions (who may create a
project, how WorkUnit bodies are validated and versioned) that no issue or ADR
has settled, and it would block a read slice whose data already exists.

### Return the WorkUnit body by reading repository files

Rejected. Issue #739's acceptance requires a client to work without reading
repository files, and a body fetched from a working tree is not bound to the
stored digest.

### Collapse each WorkUnit to its latest revision

Rejected. "Latest" is an implicit selection, which #739 and ADR-0016 forbid,
and it hides runs that used earlier revisions.

### Embed per-project WorkUnit lists and run lists in the project resource

Rejected. It is unbounded for a busy project; the filtered list endpoints
already give a bounded, paginated route to the same data.

## Implementation ownership

- Issue #739 owns the surfaces; BL-002 (work-units) and BL-003 (projects) in
  the delivery log implement this ADR.
- `idkmesh/connector_store.py` owns the derivation queries,
  `idkmesh/product_spine_run_store.py` the typed service methods and cursor,
  `idkmesh/control_tower_ui.py` routing, and
  `docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md` the endpoint contract.

## Revisit conditions

Revisit this ADR if:

- issue #740 or a later issue introduces a real WorkUnit or project store;
- derivation cost becomes a measured problem on a realistic run count;
- a deployment profile needs a project list or per-project WorkUnit embedding.

Any revision must preserve ADR-0016's authority invariant and #739's "no
hidden winner selection" requirement.
