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
| Local developer | `LocalMetadataStore` (`idkmesh/connector_store.py`), a SQLite file, reached through `ProductSpineRunStore` (`idkmesh/product_spine_run_store.py`). Human decisions use a separate append-only `HumanDecisionStore` SQLite file in the transport-neutral service core (#740). Development-mode metadata, not canonical application state. | Run store implemented (schema version 3); decision store implemented (schema version 1). No network decision endpoint. |
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

### Human Decision record integrity on read

The transport-neutral `HumanDecisionStore` (#740) persists immutable decision
JSON, its SHA-256 canonical digest, and indexed identity fields: decision ID,
run ID, evidence-report digest, decision timestamp, idempotency key, and request
digest. Its append-only triggers block ordinary updates/deletes. Both an
idempotent replay and `list_for_run()` now verify not only the JSON digest, but
that the record agrees with all indexed fields and that the decision ID can be
rederived from the idempotency key and request digest. On disagreement it raises
`persisted_state_corrupt` rather than returning a record for the wrong run or
a forged/rekeyed index. Regression tests alter each indexed field and also
recompute the JSON digest after changing the embedded run identity. This is
corruption/inconsistency detection, **not cryptographic authentication** against
an attacker able to rewrite every persisted column.

The decision service remains transport-neutral and does not provide a
production-authorized HTTP mutation endpoint. The local decision database is a
separate owned SQLite file: this slice neither unifies database layouts nor
implements a network storage adapter.

## Storage operations (library)

`idkmesh/api_storage_ops.py` (#750) turns three of the rules above into code.
It is reachable from the [`idkmesh api-storage` CLI](#command-line); no HTTP
route, scheduled job or existing store calls it, and it does not implement a
network-profile adapter. It never deletes a record, reads a credential, or
grants authority.

- **Migrations.** `MigrationStep(version, name, sql)` lists are contiguous from 1
  and forward-only. `plan_migrations()` is a read-only dry run;
  `apply_migrations()` runs every pending step, its ledger row
  (`idkmesh_schema_migrations`, with a SHA-256 of the normalised SQL) and
  `user_version` in one `BEGIN IMMEDIATE` transaction, so an error or a process
  crash at any point leaves the previous schema (`MigrationRunnerTests`,
  including a child process killed with `os._exit` mid-migration). It refuses an
  edited historical step (`checksum_mismatch`), a ledger gap, a ledger/`user_version`
  disagreement, a newer database, and a step containing transaction control,
  `PRAGMA user_version`, `VACUUM` or `ATTACH`. A database that already has a
  `user_version` but no ledger (the current `LocalMetadataStore` and
  `HumanDecisionStore` files) is refused unless `adopt_existing=True`, which
  records the already-applied steps as adopted without running them.
- **Retention.** `evaluate_retention()` returns `keep` or `expire` per record.
  Essential and configuration classes cannot be given an age limit; expendable
  and ephemeral classes need an explicit day limit; a record whose `run_id` or
  evidence digest appears in a Human Decision (read with
  `decision_references_from_store()`, read-only, fail-closed if unreadable) is
  always kept. Unknown classes, naive timestamps and duplicate IDs raise.
  Applying an `expire` decision remains the caller's separate step.
- **Backup / verify / restore.** `create_backup()` takes an online SQLite
  snapshot (private mode, no overwrite, no symlink following, atomic rename after
  an integrity check) and writes a manifest holding the file's SHA-256, size,
  schema version, per-table row counts and a manifest self-digest.
  `verify_backup()` recomputes all of them; `restore_backup()` verifies, stages
  next to the target, re-checks the digest, and `os.replace`s into place, removing
  stale `-wal`/`-shm`/`-journal` files, so a failure leaves the old target.
  The manifest self-digest detects accidental edits only: someone who can write
  both files can forge both, as with event digests above.

### Command line

`idkmesh api-storage` is a thin surface over the library above. It adds no new
record shape and no new authority.

| Verb | Writes? | Notes |
|---|---|---|
| `plan-migrations DATABASE --migrations DIR` | Never | Read-only plan. `DIR` holds `NNNN_name.sql` files numbered contiguously from `0001`; any other `*.sql` name, symlink or non-UTF-8 file is refused. |
| `apply-migrations DATABASE --migrations DIR [--apply]` | Only with `--apply` | Without the flag it prints the same plan and writes nothing. `--adopt-existing` records an already-versioned legacy store; it is a dry run too until `--apply`. |
| `plan-retention --records FILE --expendable-days N --ephemeral-days N (--decisions-store PATH \| --assume-no-decisions)` | Never | Plans only. The caller must name the Human Decision store (which must exist and be readable) or opt out explicitly, so a typo cannot make decided evidence look unreferenced. Nothing applies or schedules the plan. |
| `backup SOURCE BACKUP [--apply]` | Only with `--apply` | Dry run runs every path check. Never overwrites a backup or manifest. |
| `verify-backup BACKUP [--manifest PATH] [--max-schema-version N]` | Never | Digest, size, integrity check, schema version and row counts against the manifest. |
| `restore BACKUP TARGET [--manifest PATH] [--max-schema-version N] [--apply]` | Only with `--apply` | Verifies first. `TARGET` must not exist (the CLI deliberately does not expose the library's `replace`; move the old file aside) and must not be a symlink. |

Every verb accepts `--json` (deterministic output on stdout; failures as one JSON
object on stderr). Exit codes are stable: **0** success or a plan; **1** an
integrity finding (`backup_digest_mismatch`, `backup_corrupt`,
`manifest_digest_mismatch`, `manifest_invalid`, `checksum_mismatch`, `ledger_gap`,
`ledger_version_mismatch`); **2** a refused or unusable request (every other
library code, a bad argument, a symlink, an existing target, an unreadable
file). A failure prints one `error: CODE: message` line, never a traceback, and
messages carry paths you supplied but no file content or credential.
`tests/test_api_storage_cli.py` drives the real CLI for each of these.

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
| Human Decision records (local service core #740 implemented; HTTP endpoint still pending) | Essential, immutable | Kept; append-only SQLite triggers, digest and index consistency checked on read. |
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
| Migration / version strategy | Done; replay verified. Checksummed forward-only runner with dry run and crash-atomic apply available as a library and as `idkmesh api-storage plan-migrations` / `apply-migrations` (dry run unless `--apply`); no existing store has been moved onto it. |
| Retention matrix | Done; probe-history pruning implemented and tested. A retention planner that never expires decision-referenced evidence exists as a library; `idkmesh api-storage plan-retention` prints its plan and deletes nothing; claim/lease pruning, applying a plan, and any scheduled retention job are open. |
| Backup / restore test for the network adapter | Open: no network adapter. Local backup reconstruction is tested, and a digest-verified backup/restore procedure with negative tests exists as a [library](#storage-operations-library) with `idkmesh api-storage backup` / `verify-backup` / `restore` ([command line](#command-line); `restore` never overwrites). |
| Corruption / digest negative test | Done for runs, evidence, events, and local immutable Human Decision records. |
| Restart / reconstruction fixture | Done. |
| No duplicate canonical run / evidence / decision model | Held; this document defines no new record shape. |
