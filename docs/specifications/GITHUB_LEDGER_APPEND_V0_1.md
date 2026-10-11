---
description: "C9-C optimistic append protocol for the GitHub-native durable ledger: compare-and-set on a Git ref, conflict detection, bounded retry, and what it does and does not prove."
---
# GitHub Ledger Optimistic Append v0.1

**Status:** experimental C9-C implementation contract  
**Issue:** #597 (slice C9-C), parent #570  
**Authority:** evidence/state record only; no dispatch, verification, acceptance, integration, Git-push, or merge authority.

## Purpose

[C9-B](GITHUB_LEDGER_SERIALIZATION_V0_1.md) made one record, and a whole chain,
deterministic and verifiable. It deliberately did not say what happens when two
writers append to the same run's ledger at once. Without an answer, a duplicate
event, a replayed webhook or two automations acting on the same issue can
overwrite each other and silently lose a record. C9-C supplies the answer, as
code in `idkmesh/github_ledger_append.py`.

## The primitive

`git update-ref <ref> <new> <old>` moves a ref **only if it still points at
`<old>`**, atomically. A writer that read a stale head therefore loses cleanly
instead of overwriting the winner. For the first record `<old>` is the all-zero
object id, meaning "the ref must not exist yet". This is the same
expected-SHA compare-and-set that the GitHub refs API offers, so the protocol
carries over to the C9-G storage adapter unchanged.

## Protocol

1. **Snapshot.** Read the head commit and every record under `records/`, and
   verify the result as a complete chain with `serialize_github_ledger_chain`.
   A tampered or out-of-order entry fails here, not later.
2. **Build.** The caller builds the next record from that snapshot.
3. **Check.** Verify `snapshot records + new record` is still a valid chain: the
   next sequence, the exact previous-record digest, fixed run identity, unique
   record and event ids, and the all-false authority ceiling.
4. **Write.** Write the blob, the `records/` tree and a commit whose only parent
   is the snapshot head.
5. **Compare-and-set.** Move the ref from the snapshot head to the new commit.
   If it moved, raise `LedgerConflict` carrying the actual head.

`GitLedger.append_with_retry(build)` repeats 1–5 after every `LedgerConflict`,
rebuilding from a fresh snapshot, up to `max_attempts` (default 16). It then
raises `LedgerConflictExhausted`; it never loops unbounded. `build` may return
`None` to say there is nothing left to write — for example because a retry finds
the event already recorded — which returns `appended=False` without writing.

## Storage layout

One ref per run under `refs/idkmesh/ledger/`, one blob per record at
`records/<20-digit sequence>.json`, content exactly the C9-B canonical bytes. The
history is a single linear chain: each commit adds one record, has one parent,
and never touches an earlier blob.

## Guarantees

- **No lost update.** Two writers racing from the same head cannot both succeed;
  the loser sees `head_conflict` and the winner's record is untouched.
- **History only grows.** The ref is never force-moved. Every earlier head is an
  ancestor of every later one; there is no rewrite to hide a failed or cancelled
  attempt.
- **Fail closed.** A record that does not extend the verified chain, or that
  enables any authority field, is rejected before any ref change.
- **Bounded.** Retries are capped.

## Verified by

`tests/test_github_ledger_append.py` against a real bare repository: ordered
append and read-back, linear history with one record per commit, a stale writer
losing without disturbing the winner, a mid-append race caught by the atomic ref
update alone (removing the expected-old value from `update-ref` fails two tests),
eight concurrent writers all landing with sequences 1–8, bounded retry, the
nothing-to-write case, and tamper detection on read.

## Boundary with other C9 slices

C9-C does **not** implement:

- idempotent admission (duplicate dispatch resolving to the existing run) — C9-D;
  the `build` returning `None` hook is where C9-D plugs in;
- reconstruction of current run state from events — C9-E;
- killed-workflow recovery — C9-F;
- the GitHub evidence-branch adapter, remote pushes, or branch protection — C9-G;
- retention policy — C9-H.

It also does not authenticate a writer: anyone who can move the ref can append
well-formed records. Who may write is a repository permission and C9-G concern.
The chain digest detects corruption and reordering, not a malicious writer who
rewrites history *and* recomputes digests; protecting the ref against that is
branch protection, not this module.

Local Git plumbing only: no network, no push, no GitHub call, no secret.
