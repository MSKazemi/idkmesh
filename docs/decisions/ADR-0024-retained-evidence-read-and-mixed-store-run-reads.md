# ADR-0024 — Serve Retained Run Evidence, and Read Product Spine Runs From a Mixed Store

**Status:** Accepted
**Date:** 2026-10-02

## Context

Issue #739 (API-4) lists `GET /api/v1/runs/{run_id}/evidence` and
`/decisions`. ADR-0019 reserved both suffixes. Memory and the 2026-09-27 notes
concluded that neither was buildable because "no store maps a digest back to
content". Reading the code shows that is only half true:

- **Evidence is retained.** The idempotent offline Product Spine
  (`idkmesh/product_spine_idempotency.py`) writes the full evidence report into
  the run row (`metadata.evidence_report`) next to the projection whose
  `evidence_report_digest` it must equal; its own replay path already verifies
  `canonical_digest(report) == projection.evidence_report_digest` and fails
  closed on a mismatch.
- **Decisions are not retained.** `human_decision_record_digest` has no
  retained content anywhere; `experiments/record_human_decision.py` writes only
  to caller-chosen files. That remains issue #740.
- **The shared `runs` table is mixed.** Product Spine CLI runs
  (`product-spine-cli-run`), idempotent offline results
  (`product-spine-idempotency-result`), their admission and error rows, and
  GitHub dispatch/status rows all live in it. `ProductSpineRunStore._restore`
  accepts only the CLI kind and raises for anything else, and
  `list_runs` returns every row. So `GET /api/v1/runs` and `idkmesh run list`
  fail for the whole page as soon as a store holds one non-CLI row, and a run
  that carries evidence cannot be read through `GET /api/v1/runs/{run_id}` at
  all.

## Decision

1. **`GET /api/v1/runs/{run_id}/evidence` serves the retained report**, after
   verifying `canonical_digest(report) == projection.evidence_report_digest`
   and that the projection is a valid Product Spine run. A mismatch answers
   `500 evidence_integrity_error` and the report is never served. Response:
   `{api_version, schema_version, kind: "idkmesh-control-tower-run-evidence-
   response", ok, run_id, evidence_report_digest, evidence_report}`.
2. **Errors are distinct.** Unknown run: `404 run_not_found`. A run that exists
   but has no retained evidence (a CLI-created run, or a run that has not
   reached `evidence_ready`): `404 evidence_not_available`, so a client can tell
   "no such run" from "no evidence yet".
3. **`/decisions` is not built.** It stays a plain `404 not_found` until #740
   provides a decision store and accountable-principal authentication. A
   decision is a governance act; this ADR does not widen anyone's authority.
4. **Product Spine run reads accept the idempotent offline result kind.**
   `_restore` accepts `product-spine-idempotency-result` rows (checking their
   `idempotency_request_digest` against the atomic record) in addition to CLI
   rows. Such a run reports the atomic record's request digest as
   `create_request_digest` and its stored idempotency key.
5. **`GET /api/v1/runs` lists only Product Spine runs.** `list_runs` takes an
   explicit set of row kinds and returns only those; admission-only,
   execution-error and GitHub rows are excluded, so a mixed store no longer
   breaks the list or its keyset pagination. This is a stated filter, not a
   silent one: the specification names which kinds a run list contains.
6. **No fabrication.** Nothing is synthesised for a run that has no evidence;
   the report is returned byte-for-byte as retained.

## Implementation contract

- `ProductSpineRunStore.get_run_evidence(run_id) -> {"run_id",
  "evidence_report_digest", "evidence_report"}`; error codes
  `invalid_run_id`, `run_not_found`, `evidence_not_available`,
  `evidence_integrity_error`, `store_error`.
- `LocalMetadataStore.list_runs(..., kinds=None)`: when given, restricts to rows
  whose `$.kind` is in `kinds`.
- `idkmesh/control_tower_ui.py`: `/runs/{run_id}/evidence` (ADR-0019 suffix
  resolution unchanged); `evidence_integrity_error` maps to 500.
- Schema `schemas/idkmesh-control-tower-run-evidence-response-v0.1.schema.json`.
- CLI: `idkmesh run evidence RUN_ID --store PATH [--json]`.

## Consequences

### Positive

- A Control Tower client can reconstruct a run and its evidence without
  repository files or supplying the evidence document (#739 acceptance).
- A defect in the shipped run list (one foreign row breaks the page) is fixed.
- Integrity is checked on every read, so a tampered row is refused, not shown.

### Costs

- The evidence response can be large (a whole report); it is bounded by what the
  producer already wrote and is returned as one document.
- `/decisions` and the human-decision API remain unbuilt.
- Excluding non-Product-Spine rows from the list means GitHub dispatch rows are
  not visible there; they are not Product Spine runs.

## Alternatives considered

### Keep requiring a separate evidence content store

Rejected. The content is already retained and digest-verified in the run row;
a second store would duplicate it.

### Return the report without re-verifying the digest

Rejected. The retained row is persisted state; fail-closed verification costs
one canonical hash and prevents serving a tampered or truncated report.

### Make the run list skip unrestorable rows silently

Rejected. A silent filter by exception hides corruption. Filtering by an
explicit, documented kind set is deterministic; a row of a listed kind that
fails to restore still fails loudly.

### Build `/decisions` and the human-decision API now

Rejected. It needs a decision store, an `Idempotency-Key` contract and an
authenticated human or governance principal (#670, enterprise identity). A local
session token is not an accountable person, so this is a governance gate, not
an implementation detail.

## Revisit conditions

Revisit when #740 lands a decision store, when another writer starts retaining
evidence, or when a run with a restorable kind other than the two listed
appears.

## Update 2026-10-02 (static review)

A read-only static review of the implementation, before any test had run, found
that decision 4 ("Product Spine run reads accept the idempotent offline result
kind") had an unintended consequence, and tightened decision 1. The decisions
are unchanged; reading is not controlling.

- **Offline-spine runs are read-only for control.** Because `status` now restores
  offline result rows, `ProductSpineRunStore.cancel` could succeed on one and
  rewrite its row into the CLI shape (`_metadata`), dropping the retained
  `evidence_report`, `source_run_record`, the offline idempotency identity and
  the result kind. `cancel` now refuses any run whose stored kind is not
  `product-spine-cli-run` with `cancel_not_allowed`; before decision 4 the same
  call failed closed on the kind check.
- **Evidence restore is as strict as `status` (decision 1).** `get_run_evidence`
  first restores the row through the same checks as `status` (kind, run id,
  state, request digests). A row that is not a Product Spine run is
  `run_not_found`; a Product Spine row that fails the checks, for example one
  with another run's metadata swapped in, is `evidence_integrity_error`.
- **Store faults.** A malformed `metadata_json` row makes the kind-filtered list
  query (decision 5) raise a SQL error. The store now raises it as
  `LocalStoreError`, reported as `store_error`, instead of an unhandled raw
  `sqlite3` error.
