# Storage restore and integrity drill v0.1

**Issue:** #750. **Status:** drill procedure; no restore execution claimed.

Existing local storage is SQLite with versioned migrations; GitHub-first durable
records have a separate ledger owner. Network/multi-user storage is a future
adapter, not an existing production database.

## Local development restore drill
1. Create a disposable SQLite store with several events, probe records and a
   run whose evidence has a retained digest.
2. Record schema version, event sequence IDs, counts and semantic digests.
3. Use SQLite online backup while source remains open, into a separate path.
4. Open the restored copy through LocalMetadataStore and compare the exact
   persisted run/event indexes to the pre-backup snapshot.
5. Replay a duplicate idempotency key and prove it never creates a second
   logical event or dispatch.
6. Corrupt an event JSON value without changing its recorded digest and
   assert the read fails closed instead of returning altered data.
7. Attempt to open a store with a newer unknown user_version; it must reject.
8. Record source SHA, tool versions and test output, including any failures.

## Non-goals and network boundary
Do not mark network backup/restore complete without a real adapter,
encrypted-backup ownership, RPO/RTO parameters and a destructive restore test.
Do not treat digests as writer authentication; an authorized attacker can
rewrite both payload and digest. No credential may be stored in event payloads.

**Acceptance:** recovery reconstructs the same immutable records while
corruption and unsupported migrations fail closed. This text is not evidence
that the drill has been run.


## Implemented local API and validation

`LocalMetadataStore.backup_to(destination)` now reserves a new destination
without overwriting existing files, uses SQLite's online backup protocol and
checks database integrity before returning. It does not restore, encrypt,
upload, retain, or authorize anything. Use a trusted, access-controlled
directory, keep the backup offline until verification, and validate a restored
copy by opening it and reading the original digests and event indices.

The `tests/test_local_metadata_online_backup.py` suite covers snapshot
independence, repeat/open-target refusal, source-path refusal, invalid
directories and symlinks. Network-profile restore remains entirely unbuilt.
