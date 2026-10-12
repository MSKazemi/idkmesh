---
description: "Which durable store backs the IDKMesh API in each deployment profile, the semantics every store must keep, the migration and retention rules, and what is verified today versus still open."
---
# API Storage Profiles v0.1

**Status:** experimental; the local profile is implemented, the GitHub-first profile is owned by its ledger, the network profile is an interface requirement with no implementation  
**Issue:** #750 (API-13), parent #713  
**Authority:** storage holds records; it grants no execution, acceptance, repository-write, or merge authority, and a storage adapter never creates authority.

## Purpose

The API must keep its records durable and checkable without this issue
replacing the two owners that already exist: the local SQLite metadata and
idempotency store (#616) and the GitHub-native durable ledger (#597). This
document fixes who owns what in each profile, the semantics every store must
keep, the migration and retention rules, and — separately — what is verified by
tests today and what is not.

It does not choose a hosted database vendor.

## Profile ownership

| Profile | Canonical durable owner | Status |
|---|---|---|
| GitHub-first / no-server | The GitHub ledger ([GitHub Ledger Record v0.1](GITHUB_LEDGER_RECORD_V0_1.md), #597). | Owned by #597. The API reads through it; it does not copy it. |
| Local developer | `LocalMetadataStore` (`idkmesh/connector_store.py`), a SQLite file, reached through `ProductSpineRunStore` (`idkmesh/product_spine_run_store.py`). Development-mode metadata, not canonical application state. | Implemented. Schema version 3. |
| Network / multi-user | None. A future adapter must satisfy the semantics below and the tenant boundaries of [Enterprise Tenant Scope v0.1](ENTERPRISE_TENANT_SCOPE_V0_1.md). | Interface requirement only; nothing to qualify yet. |

Large evidence and artifacts are content-addressed or referenced; they are not
held inside UI process memory. There is exactly one canonical run, evidence,
and event model (`ProductSpineRun`, the retained run-evidence report, the
ADR-0023 event envelope); a profile stores them, it does not define a second
shape.

## The storage port

The application services call one interface: the methods of
`ProductSpineRunStore`. An adapter for another profile conforms by providing
the same operations with the same guarantees.

| Operation | Guarantee |
|---|---|
| `create` | Atomic: run row, idempotency record and `run.created` event commit together or not at all. Exact replay of an idempotency key returns the original and appends nothing; a conflicting replay fails closed. |
| `status`, `list` | Rebuilt from durable records only. Stored projection, row state and identity are cross-checked; any disagreement is an error, never a guess. `list` is keyset-paginated and deterministic. |
| `cancel` | One canonical transition, in the same transaction as its event. No provider termination, no authority change. |
| `get_run_evidence` | Serves only the retained report, and only after its digest verifies. |
| `list_work_units`, `get_work_unit`, `get_project` | Derived views over run records; nothing is stored twice. |
| `list_events`, `events_after`, `latest_event_sequence` | The append-only event log in ascending sequence, with cursors that stay valid across restarts. Every event read is integrity-checked (below). |

Connector configuration records contain secret *references* (`env:NAME`) only;
the store rejects secret-valued metadata.

## Required semantics, and what verifies each

| Semantics | Local profile today | Verified by |
|---|---|---|
| Migrations explicit and replayable | `PRAGMA user_version`, additive in-place upgrade, reopening is a no-op | `MigrationReplayTests` |
| A newer schema is refused | Opening fails closed and leaves the file untouched | `MigrationReplayTests`, `test_connector_store.py` |
| Digests detect corruption and substitution | Run create-digest, projection state and identity, retained evidence digest, event `payload_digest` and indexed columns | `test_product_spine_run_store.py`, `test_control_tower_run_evidence.py`, `EventIntegrityTests` |
| Immutable records never silently rewritten | Events: `BEFORE UPDATE/DELETE` triggers abort. Run rows change state through the one canonical transition | `EventIntegrityTests` |
| Recovery rebuilds current state from durable records | Run state, event log and cursors are rebuilt from the file alone | `RestartReconstructionTests` |
| No raw credentials in API state | Sensitive keys and secret-valued objects are rejected on write | `test_connector_store.py` |
| Storage adapters create no authority | Run projections carry `candidate_accepted: false`, `merge_authority: false` | `test_product_spine_run_store.py` |

### Event integrity on read

The append-only triggers stop the *application* from rewriting an event. They
do not stop a damaged or hand-edited database file, so every event read
recomputes `payload_digest` over the payload and checks that the indexed
columns (`occurred_at`, `event_type`, `project_id`, `work_unit_id`, `run_id`,
`attempt_id`) still equal the envelope that is about to be served. Either
mismatch raises a store error: `GET /api/v1/events` answers `500 store_error`
and the altered content is not returned, while reads that do not touch the
damaged row keep working. Before this check was added, `payload_digest` was
written but never verified, so an edited payload was served as the original.

The digest protects against corruption and accidental substitution. It does not
authenticate the writer: someone who can rewrite a payload can also recompute
its digest. Tamper-evidence against a malicious writer needs the hash-chained
[Enterprise Audit Ledger](ENTERPRISE_AUDIT_LEDGER_V0_1.md) or the GitHub ledger.

## Migration strategy

- The schema version is the SQLite `user_version`. Opening a database applies
  every missing step in order; running the steps again changes nothing.
- A database newer than the code is refused, not downgraded.
- Upgrades so far are additive (new tables, triggers, indexes) and keep every
  existing row. A step that rewrites or drops data must ship with a new schema
  version, a documented backup instruction, and a fixture of the old layout in
  `MigrationReplayTests`.
- Adding a column to a stored JSON document is a versioned-schema change under
  [schemas/README.md](https://github.com/MSKazemi/idkmesh/blob/main/schemas/README.md), not a store migration.

## Retention matrix

Pruning is deliberately narrow in v0.1: the only implemented pruner is
`LocalMetadataStore.prune_probe_history()`, which removes superseded probe rows
and keeps the latest per connection. It is a library call, not a scheduled job.
Nothing else is pruned automatically. This matrix states what may be pruned, so
that no pruner can remove evidence by accident.

| Record | Class | Retention |
|---|---|---|
| Event log | Essential | Kept; append-only. |
| Run rows and idempotency records | Essential | Kept while the run exists; an idempotency record outlives replay needs. |
| Retained run-evidence report | Essential | Kept with its run; digest-bound. |
| Human Decision records (#740, not built) | Essential, immutable | Kept; never rewritten. |
| Connector configuration | Configuration | Kept until superseded; secret references only. |
| Probe history | Expendable | Only the latest probe per connection is needed. Pruned by `prune_probe_history()`; `ProbeHistoryPruningTests` proves runs, idempotency records and events are untouched. |
| Task claims and leases | Ephemeral | Expired and released rows are expendable after their lease window. Not pruned yet: rows carry epoch fencing and occupancy state, so a pruner needs its own design and tests. |
| Raw logs and large artifacts | Not stored | Referenced by content digest; their retention belongs to the artifact store. |

## Backup and restore

Local profile: the database is one SQLite file. A consistent copy is taken with
SQLite's online backup (`sqlite3.Connection.backup`) or by copying the file
while no writer is active; restoring is replacing the file. A restored file is
validated by opening it (which runs the migration check) and reading runs and
events back; `RestartReconstructionTests` proves reconstruction from a backup
copy equals the original.

The network profile has no adapter, so no backup/restore procedure or test for
it exists yet.

## Acceptance status (issue #750)

| Acceptance item | State |
|---|---|
| One storage-port contract shared by application services | Documented above as the `ProductSpineRunStore` operations; no separate `Protocol` type, to avoid a second model. |
| Local / GitHub / network ownership documented | Done (this document). |
| Migration / version strategy | Done; replay verified. |
| Retention matrix | Done; probe-history pruning implemented and tested. Claim/lease pruning and any scheduled retention job are open. |
| Backup / restore test for the network adapter | Open: no network adapter. Local backup reconstruction is tested. |
| Corruption / digest negative test | Done for runs, evidence and events. |
| Restart / reconstruction fixture | Done. |
| No duplicate canonical run / evidence / decision model | Held; this document defines no new record shape. |
