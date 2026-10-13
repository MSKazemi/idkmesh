# GitHub Projects synchronization contract (C13-F/G)

**Issue:** #608. **Status:** proposed contract; no Projects adapter implemented.

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
