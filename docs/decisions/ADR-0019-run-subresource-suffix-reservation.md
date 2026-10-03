# ADR-0019 — Reserve Run Sub-Resource Suffixes for the Product Spine Read API

**Status:** Accepted
**Date:** 2026-09-27

## Context

Issue #739 (API-4) targets, among other read surfaces, `GET
/api/v1/runs/{run_id}/attempts`, `/evidence`, and `/decisions` alongside the
already-shipped `GET /api/v1/runs/{run_id}` (PR #889) and `GET /api/v1/runs`
(PR #890, PR #891).

`idkmesh/product_spine.py`'s `ProductSpineRun.run_id` and the
`idkmesh-product-spine-run-v0.1.schema.json` schema place no constraint on
`run_id` beyond `minLength: 1` -- it is caller-supplied and, in practice,
shares WorkUnit's identifier grammar, which legitimately contains `/` (the
shipped test fixtures and this session's own smoke tests use ids such as
`run/http-read-1`). `idkmesh/control_tower_ui.py`'s `_run_id_from_path`
docstring already flagged this as an open ambiguity when it shipped the
single-run `GET` in PR #889: a path-nested sub-resource under an
arbitrary-content `run_id` cannot in general tell where the `run_id` ends
and the sub-resource name begins, and
`tests/test_control_tower.py::ControlTowerRunReadTests
::test_run_id_containing_a_slash_is_read_as_one_literal_id` pinned the
interim behavior (take everything after the prefix as one literal id, no
sub-resource) as a regression guard until this was resolved.

`docs/specifications/CONNECTOR_CONTROL_API_V0_1.md` (an aspirational,
not-yet-implemented specification for a different, future control plane)
already establishes the colon-suffix shape (`{run_id}:cancel`,
`{connection_id}:probe`) for this repository's mutation/action verbs, but it
uses that shape *only* for `POST` custom actions -- its own `GET
/api/v1/runs/{run_id}/events` sub-collection uses plain path nesting, the
same shape API-4 wants for `attempts`/`evidence`/`decisions`. Colon-suffix is
therefore not the right precedent to reuse here: it signals a mutation verb,
not a read sub-collection, and reusing it for a `GET` would blur that
distinction across the two control planes ADR-0016 already requires to
converge on shared semantics.

Percent-encoding the `run_id` segment (`%2F` for an embedded `/`) is the
general HTTP-correct answer, but it pushes real complexity onto every
client of a purely local, single-tenant development read API to protect
against a collision that the same caller who names runs can simply avoid.

## Decision

Reserve `attempts`, `evidence`, and `decisions` as the only recognized
trailing path segments under `/api/v1/runs/{run_id}/`. Resolution rule,
applied deterministically and independent of what a store currently holds
(ADR-0016's "no hidden winner selection" carried into this shape):

1. Take the path remainder after `/api/v1/runs/`.
2. If it ends with exactly one of `/attempts`, `/evidence`, `/decisions`
   *and* has at least one character before that suffix, the run_id is
   everything before the suffix and the sub-resource is the suffix name.
3. Otherwise, the entire remainder is the run_id (unchanged from PR #889),
   addressing the run itself.

This is a total function of the path string alone -- it never depends on
whether a run with that derived id exists, so routing is deterministic and
"run not found" (404) is the only error a caller can hit from an unknown or
mis-shaped id, never a silently different resource.

The cost this accepts: a `run_id` that itself ends in exactly `/attempts`,
`/evidence`, or `/decisions` can no longer be read via the plain
single-run `GET` -- that path now always resolves to the sub-resource. This
is a documented, narrow, caller-avoidable naming collision (three reserved
literal suffixes, not a reserved character), not the general percent-encoding
problem.

## Consequences

### Positive

- `GET /api/v1/runs/{run_id}/attempts` (this decision's first consumer) and
  the still-unbuilt `/evidence` and `/decisions` slices can ship without
  re-litigating URL shape per endpoint;
- routing stays a pure function of the path, matching issue #739's "no
  hidden winner selection" and "explicit 404" acceptance criteria;
- no client-side percent-encoding burden for the common case (a `run_id`
  that does not end in a reserved suffix, which is every id this repository
  itself generates).

### Costs

- `run_id` values ending in `/attempts`, `/evidence`, or `/decisions` are
  now unreadable via the plain single-run `GET`; callers minting run ids
  must avoid those three literal suffixes, and this restriction must be
  documented wherever `run_id` is described as free-form;
- `tests/test_control_tower.py`'s interim regression guard
  (`test_run_id_containing_a_slash_is_read_as_one_literal_id`) is superseded
  by this decision and rewritten to assert the resolved routing instead of
  the old "always one literal id" placeholder behavior.

## Alternatives considered

### Percent-encode `run_id` in sub-resource URLs, require raw `/` only as a real path separator

Rejected for this development-profile, single-tenant read API. It is the
theoretically clean answer and remains available to a future network/
multi-user deployment profile (ADR-0016) if that profile's `run_id` grammar
still allows embedded `/`; nothing in this decision forecloses adopting it
later.

### Reuse the colon-suffix action shape for the read sub-resources

Rejected. That shape already carries a specific meaning in this
repository's own aspirational connector-control specification --
`POST` custom actions, not `GET` sub-collections -- and its own `/events`
sub-collection already avoids it. Reusing it for a read would create two
different conventions for the same syntax across the converging API
surfaces ADR-0016 requires.

### Leave the ambiguity unresolved and keep every sub-resource unimplemented

Rejected. Issue #739 lists `attempts`, `evidence`, and `decisions` as target
read surfaces with real, already-shipped data behind them
(`ProductSpineRun.attempts` ships today); deferring indefinitely would block
real, grounded feature work over a narrow, documentable edge case.

## Implementation ownership

- Issue #739 (API-4) is the read-API-surface owner; this ADR unblocks its
  remaining `attempts`, `evidence`, and `decisions` slices.
- `idkmesh/control_tower_ui.py`'s `_run_id_from_path` (and any successor
  resolver function) implements the rule in section "Decision" above.

## Revisit conditions

Revisit this ADR if:

- a real deployment needs `run_id` values that legitimately end in one of
  the three reserved suffixes and cannot rename around it;
- a network/multi-user deployment profile (ADR-0016) needs the general
  percent-encoding answer instead of a fixed reserved-suffix list.

Any revision must preserve ADR-0016's authority invariant and issue #739's
"no hidden winner selection" requirement -- routing must stay a pure
function of the request path.

## Update 2026-10-02

The decision above is unchanged. Of the three reserved suffixes, `attempts`
(ADR-0019's first consumer) and now `evidence` are served:
[ADR-0024](ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md) serves
`GET /api/v1/runs/{run_id}/evidence` from the report the idempotent offline
spine retains in the run row. `decisions` stays reserved and unbuilt, because no
decision content is retained anywhere and recording one needs an authenticated,
accountable principal (issue #740).
