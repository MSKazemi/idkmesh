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


## Judging a drill against the profile (E6, #673)

A drill is only worth recording if something compares it with the objectives the
deployment declared. `idkmesh/enterprise_recovery_drill.py` is that comparison:
`evaluate_recovery_drill(profile, drill, evaluated_at_epoch=..., max_drill_age_seconds=...)`
checks one drill record against `reliability.rpo_minutes` and
`reliability.rto_minutes` of a validated enterprise control profile. It runs
nothing and restores nothing; the operator runs the drill above and records:

~~~json
{
  "kind": "idkmesh-enterprise-recovery-drill",
  "schema_version": "0.1",
  "drill_id": "drill:2026-10-14-restore",
  "profile_id": "example-g2-self-hosted",
  "last_acknowledged_write_epoch": 1789999995,
  "last_recovered_write_epoch": 1789999990,
  "failure_injected_at_epoch": 1790000000,
  "service_restored_at_epoch": 1790000600,
  "integrity_verified": true,
  "evidence_digest": "sha256:<64 hex of the retained drill report>"
}
~~~

The record has exactly these fields; unknown, missing or coerced values are
rejected, and time may not run backwards (acknowledged and recovered writes no
later than the failure, restoration no earlier than the failure).

| Measurement | Definition | Compared with |
| --- | --- | --- |
| data loss | newest acknowledged write minus newest recovered write, never below zero; idle time before the failure is not loss | `rpo_minutes` x 60 |
| recovery time | service restored minus failure injected | `rto_minutes` x 60 |

Both comparisons are inclusive. The outcome is **FAIL** when an objective is
exceeded (`rpo_exceeded`, `rto_exceeded`) or the restored state was not
integrity-verified (`integrity_not_verified`); **PASS** (`objectives_met`) when
all three checks pass; **UNKNOWN** when there is nothing trustworthy to judge:
`no_drill_evidence`, `invalid_drill`, `profile_mismatch`, `invalid_profile`,
`drill_from_future`, or `stale_drill` when `max_drill_age_seconds` is given and
exceeded. A missing drill is never a pass, and a stale failing drill is UNKNOWN,
not FAIL, because old evidence is not a current measurement. The profile
declares no restore-test interval, so freshness is the caller's policy.

A PASS is evidence about that one drill, not a guarantee about the next
recovery, and `integrity_verified` is the operator's claim, bound only by the
retained `evidence_digest`. Results carry identifiers, counts and reason codes;
untrusted text is never echoed. This is **not** a recorded drill: the module
only judges one, and none has been run.

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
