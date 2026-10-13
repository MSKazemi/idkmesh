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
