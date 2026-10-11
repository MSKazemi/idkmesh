---
description: "C9-B deterministic canonical serialization and complete-chain verification for GitHub-native durable ledger records."
---
# GitHub Ledger Serialization v0.1

**Status:** experimental C9-B implementation contract  
**Issue:** #597  
**Record contract:** [GitHub Durable Ledger Record v0.1](GITHUB_LEDGER_RECORD_V0_1.md)  
**Authority:** serialization and integrity checking only; no dispatch, verification, acceptance, repository write, integration, or merge authority.

## Purpose

C9-A froze the shape of one durable GitHub ledger record. C9-B freezes the
next boundary: **how an already-shaped record becomes deterministic bytes and
how a complete local chain proves append-only linkage before any GitHub storage
adapter exists**.

The implementation is:

`idkmesh/github_ledger_serialization.py`

It is pure and stdlib-only. It performs no filesystem write, Git command,
GitHub API call, provider request, dispatch, verification, acceptance, or
integration action.

## Canonical record bytes

`serialize_github_ledger_record(record)` first converts the supplied mapping
to plain JSON-compatible values and applies the C9-B semantic checks below.

The canonical JSON text is then produced with the same frozen convention used
by `idkmesh.work_unit_binding.canonical_digest()`:

- object keys sorted lexicographically;
- compact separators `,` and `:`;
- UTF-8;
- non-ASCII text retained rather than escaped for presentation;
- no whitespace dependent on input formatting or key insertion order.

The returned `record_digest` is exactly
`canonical_digest(normalized_record)`.

The returned `content` is:

```text
canonical-json-utf8 + LF
```

The trailing LF is a storage/text-file convention only. It is **not** part of
the canonical object digest used by `previous_record_digest`. This keeps the
ledger digest identical to the repository's existing canonical JSON digest
semantics while still producing normal newline-terminated Git blobs.

## Numeric boundary

The v0.1 ledger schema uses integers for numeric fields. The serializer rejects
floating-point values before JSON encoding, including non-finite values, rather
than inheriting implementation-specific or non-JSON NaN/Infinity behavior.

This is intentionally narrower than generic JSON serialization.

## Semantic writer checks

JSON Schema validates the structural record contract, but two cross-field
relationships are intentionally enforced by C9-B at the writer boundary:

1. when `attempt` is present,
   `attempt.attempt_number == idempotency.attempt_number`;
2. when `attempt` is present,
   `attempt.connector_id == routing.selected_connection_id`.

A durable record must not say that dispatch was admitted for one attempt or
connector while its attempt object names another.

The serializer also independently enforces the complete v0.1 authority object:
all seven authority fields must be present and must be `false`. This prevents
a caller that skipped JSON Schema validation from turning a serialization
helper into an authority-bearing record.

These checks do not replace the canonical JSON Schema. Producers should still
construct objects that validate against
`schemas/github-ledger-record-v0.1.schema.json`.

## Complete-chain verification

`serialize_github_ledger_chain(records)` verifies one **complete run chain**.

A complete chain must:

- contain at least one record;
- start at `ledger_sequence = 1`;
- increment sequence by exactly one with no gaps;
- keep repository, project, run, and exact WorkUnit identity unchanged;
- use unique `record_id` values;
- use unique `event.event_id` values;
- use `previous_record_digest = null` for the first record;
- bind every later `previous_record_digest` to the actual canonical digest of
  the immediately preceding record.

The fixed chain identity is:

- repository;
- project ID;
- run ID;
- WorkUnit ID;
- WorkUnit version;
- WorkUnit digest;
- WorkUnit source revision.

Routing, attempt, provider, evidence, failure, and human-decision state may
evolve through later records.

The chain verifier deliberately does **not** require timestamps to be
monotonic. An observation appended later may legitimately describe an event
that occurred earlier. Sequence is append order; `event.occurred_at` remains
event time.

## Local Git fixture

The deterministic fixture is under:

`tests/fixtures/github-ledger/`

It contains two canonical records and a manifest freezing their digests.

The test `test_local_git_fixture_second_commit_only_appends_next_record`:

1. creates a temporary local Git repository;
2. commits record 1;
3. commits record 2;
4. proves the second commit only adds record 2;
5. proves record 1 remains byte-identical at both commits.

That is the C9-B append-only **fixture**. It proves the serialization is
suitable for immutable Git blobs without prematurely choosing the production
GitHub branch/path layout.

The temporary `records/` path in the test is non-normative. C9-G owns the
real GitHub storage adapter and evidence-branch/equivalent layout.

## Frozen fixture digests

The two synthetic fixture digests are:

```text
record 1
sha256:eb3266592fab12710bfd959a640b68c4c79cf2ea6466d70febf5ec9a0f114d2c

record 2
sha256:f6e63deb2a80bceb871c027b031c22f3d76ef3c46bf76cd11ae357d66a8a57ee
```

Record 2 carries record 1's digest as its
`previous_record_digest`.

These values are compatibility fixtures, not security claims about GitHub
storage.

## Failure semantics

C9-B fails closed with stable error codes including:

- `unsupported_schema_version`;
- `invalid_kind`;
- `non_canonical_number`;
- `invalid_json_key`;
- `non_json_value`;
- `invalid_record`;
- `invalid_chain_position`;
- `attempt_number_mismatch`;
- `attempt_connector_mismatch`;
- `authority_forbidden`;
- `empty_chain`;
- `sequence_gap`;
- `chain_identity_changed`;
- `duplicate_record_id`;
- `duplicate_event_id`;
- `previous_digest_mismatch`.

A failure produces no partial Git or filesystem mutation because the
implementation is pure.

## Boundary with later C9 slices

C9-B does **not** implement:

- compare-and-set / optimistic Git append;
- concurrent-writer retry;
- idempotent admission reservation;
- provider resubmission/reconciliation;
- current-state recovery;
- killed-workflow recovery;
- GitHub evidence-branch writes;
- retention policy.

Those remain C9-C through C9-H.

In particular, passing `serialize_github_ledger_chain()` proves only that the
supplied records form a deterministic internally linked chain. It does not
prove that a remote branch was not rewritten or that two concurrent writers
cannot race. C9-C owns that concurrency/storage proof; it is specified in [GitHub Ledger Optimistic Append v0.1](GITHUB_LEDGER_APPEND_V0_1.md).

## Security and authority

Serialized records remain metadata/evidence.

The serializer:

- never reads secret values;
- never accepts raw provider payloads as an execution channel;
- never materializes credentials;
- never dispatches work;
- never verifies or accepts a candidate;
- never pushes Git;
- never integrates or merges.

The all-false authority ceiling from C9-A remains mandatory after
serialization.
