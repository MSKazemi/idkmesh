# GitHub Projects synchronization contract (C13-F/G)

**Issue:** #608. **Status:** contract plus offline planner, guarded apply and an offline GraphQL mutation builder (recording-fake-transport tests); no live GitHub Projects adapter, HTTP client or token handling.

## Trust boundary
Canonical WorkUnit, route and run records are the only sources of truth.
A Project item is a view, not a policy or dispatch input. Manual Project edits
must not alter authority, risk, connector choice, or Human Decision Records.

## Derived field profile
| Field | Source | Failure |
| --- | --- | --- |
| State | canonical run/WorkUnit | unknown stays unknown |
| Task class | WorkUnit kind | absent stays blank |
| Risk | trusted policy | requester never downgrades |
| Connector | verified routing | Projects never selects |
| Verification | retained verifier result | absent is unverified |
| Human decision | immutable decision record | absent is unrecorded |
| Blockers | canonical dependencies | display only |

## Algorithm and acceptance
Freeze canonical source digest, exact revision, destination item ID and trusted
field mapping. Compute deterministic desired fields; if they match current
values, do not write. If the source changed while publishing, abort rather
than creating a mixed-revision view. The caller must not execute issue text.

Required negative fixtures: Project state manually changed to approved;
repeat delivery; absent Projects permission; out-of-repository item; unknown
field/state; malicious issue body; changing source digest during update.
No scenario may broaden permissions or block canonical WorkUnit execution.

**Remaining:** C13-F/G implementation, mocked API tests and idempotency proof.
This document alone does not establish working Projects synchronization.


## Implemented pure routing-field plan

`idkmesh.github_routing_projection.plan_github_project_routing_fields()`
now derives three bounded optional Project field values from the canonical
`RoutingDecision` and `RouteResolution`: trusted risk, routing state and independent-review
requirement. The caller supplies trusted field IDs and observed display
values. It returns only necessary updates, an exact routing digest and a
no-op result on unchanged replay. Tests reject stale digests, duplicate IDs,
malformed field values and manually changed Project approval fields.

There are **no GitHub API writes** and no Projects state reads in the actual
worker coordinator. This is C13-F planning groundwork, **not** completion
of the C13-G GitHub API sync, concurrency control or project audit trail.

## Run-state label projection (C13-E)

The pure `github_run_label_projection.plan_github_run_labels()` function
plans three dedicated run/verification/human-state **display labels** from a
trusted Product Spine run snapshot. It preserves routing-managed and human
labels and never reads Project fields to choose a run state. The exact mapping,
trust boundary and fail-closed limitations are in
[GitHub Run Label Projection v0.1](GITHUB_RUN_LABEL_PROJECTION_V0_1.md).
There is still no live GitHub label/Project API writer.

## Run-field planning and guarded apply (C13-F/G, offline)

`idkmesh.github_project_sync` adds two pure-Python pieces; neither talks to GitHub.

* `plan_github_project_run_fields(...)` maps a trusted canonical run state to three
  Project single-select values (`state`, `verification`, `human_decision`) using the same table as the
  [run label projection](GITHUB_RUN_LABEL_PROJECTION_V0_1.md). Caller-supplied trusted field ids
  must be exactly those three keys and distinct. `observed_fields` only decides which writes are
  redundant: a manually edited value (for example `approved`) is overwritten with the canonical value.
* `apply_github_project_plan(plan, item_id=..., trusted_item_ids=..., writer=..., read_canonical_digest=...)`
  re-validates the plan (accepts only the run plan and the existing routing plan; all authority flags
  must be false; values must be bounded lowercase tokens; updates must be a subset of desired fields),
  refuses an item id outside the trusted set, and re-reads the canonical digest before the first and
  every later write. A changed digest returns `aborted_source_changed` without further writes.

| Result `status` | Meaning |
| --- | --- |
| `noop` | Project already matches; the writer and store are not touched |
| `applied` | all planned fields written |
| `skipped_unauthorized` | writer raised `ProjectPermissionError`; canonical state unaffected |
| `aborted_source_changed` | canonical digest moved; replan from the new revision |
| `failed` | transport or canonical-store error; only the exception class name is reported |

Operational failures are returned, not raised, so a missing permission, a deleted Project or an outage
never blocks WorkUnit execution. Malformed arguments or a tampered plan do raise, before any write.
Replaying `plan` against the Project values observed after a successful apply yields `noop`.

## GraphQL mutation builder (C13-G, offline transport seam)

`GraphQLProjectFieldWriter(transport, schema_snapshot)` is a `ProjectFieldWriter` that turns an already
validated field plan into GitHub Projects V2 `updateProjectV2ItemFieldValue` requests. It never touches a
network: each request is handed to the injected `transport(query: str, variables: dict) -> dict` callable,
which owns the HTTP client, authentication and any token. This module reads no environment variable and
stores no credential.

* The mutation text is the fixed constant `UPDATE_FIELD_VALUE_MUTATION`. Project, item, field and value
  travel only as GraphQL **variables** (`projectId`, `itemId`, `fieldId`, `value`); nothing is interpolated.
* Ids come only from the caller-supplied **schema snapshot**
  (`kind: idkmesh-project-schema-snapshot`, `schema_version: 0.1`, a `project_id` and a bounded list of
  `fields` with `field_id`, `data_type` and, for `single_select` only, `options` of `value`/`option_id`).
  It is validated strictly (exact keys, bounded identifiers, unique ids, no options on non-select fields).
  The item/field lookup query is deliberately **not** provided: the plan already carries trusted field ids
  and the caller supplies the trusted item id, so no id is ever guessed or discovered at write time.
* Value mapping by `data_type`: `single_select` -> `{"singleSelectOptionId": <id>}`; `text` ->
  `{"text": <token>}`; `number` -> `{"number": <float>}` (non-negative integer tokens only); `date` ->
  `{"date": "YYYY-MM-DD"}` (a real calendar date). An unknown field, an unknown option or an unrepresentable
  value raises `ProjectSchemaError`.
* `preflight(updates)` is called by `apply_github_project_plan` before any canonical read or write, so a
  plan the snapshot cannot express returns `failed` with **zero** writes rather than a partial update.
  The stale-digest abort, trusted item check and idempotent `noop` behave exactly as above.
* GraphQL `errors` of type `FORBIDDEN`, `INSUFFICIENT_SCOPES` or `UNAUTHORIZED` raise
  `ProjectPermissionError` (result `skipped_unauthorized`). Any other `errors`, a non-object response, or a
  response that does not confirm the written item id raises `ProjectGraphQLError` (result `failed`). Exception
  messages are fixed strings; no response body, error message, variable or token is copied into a result.
  There are no retries beyond the single attempt per field made by the applier.

**Still a separate reviewed change:** a real transport (HTTP client), token acquisition and its storage, the
permission model for who may write which Project, reading the live Project schema to produce the snapshot,
serialization of concurrent syncs, and an audit trail. Nothing here is wired into a CLI verb, workflow or the
worker coordinator, and idempotence is demonstrated only against recording fake transports.
