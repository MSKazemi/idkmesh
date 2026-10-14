# GitHub Projects synchronization contract (C13-F/G)

**Issue:** #608. **Status:** contract plus offline planner and guarded apply (mocked-writer tests); no live GitHub Projects adapter.

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

**Still not implemented:** the live GraphQL/REST writer and reader, token and permission acquisition,
reading the Project schema to derive field ids, serialization of concurrent syncs, and an audit trail.
The tests use an in-memory fake writer and prove idempotence only against that fake.
