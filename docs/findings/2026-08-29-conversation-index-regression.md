# Conversation index regression found during repository-wide audit

**Date:** 2026-08-29

## Finding

The repository-wide documentation audit triggered the IDKGraph observatory on the exact pull-request head. Its focused navigation tests failed even though the audit had not added a new conversation record.

The failure identified a pre-existing drift introduced by the immediately preceding `main` change:

- `docs/conversations/2026-08-29-resolve-discovery-surface-gate.md` existed in the archive;
- `docs/conversations/README.md` still declared `146` records;
- the archive actually contained `147` records;
- the new record was absent from the exhaustive conversation index.

The deterministic failures were:

```text
test_declared_record_count_matches_the_archive: 146 != 147
test_every_conversation_record_is_indexed_once:
  missing 2026-08-29-resolve-discovery-surface-gate.md
```

## Correction

The audit PR repairs the index by:

1. changing the declared count from `146` to `147`;
2. adding `2026-08-29-resolve-discovery-surface-gate.md` under the 2026-08-29 index using its actual document title;
3. retaining the conversation record unchanged.

## Why this matters

This is exactly the type of cross-file documentation defect that a broad repository audit should catch. The correct response is not to delete the unindexed evidence or weaken the recurrence test; it is to repair the authoritative archive index and re-run the same exact-head checks.

The episode also validates the repository's documentation discipline:

```text
new historical record
 -> exhaustive index
 -> deterministic navigation test
 -> fail closed on drift
```

No runtime or protocol semantics are changed by this repair.
