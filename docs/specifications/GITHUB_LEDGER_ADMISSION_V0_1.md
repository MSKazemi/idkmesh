---
description: "C9-D idempotent admission for the GitHub-native durable ledger: one admission ref per dispatch key created by compare-and-set, so a duplicate dispatch resolves to the existing run."
---
# GitHub Ledger Idempotent Admission v0.1

**Status:** experimental C9-D implementation contract  
**Issue:** #597 (slice C9-D), parent #570  
**Authority:** a record that a dispatch was admitted; it grants no authority to execute, verify, accept, integrate, push or merge.

## Purpose

A dispatch is identified by its deterministic `dispatch_key`. The same key
arriving twice — a replayed webhook, a duplicate label event, two humans or
automations acting on the same ready issue — must resolve to the **one** run that
was admitted first, never to a second run and a second provider attempt. That is
the acceptance bar of #597: "replay the same dispatch event twice → one attempt"
and "two humans/automations act on the same ready issue concurrently → no
duplicate admitted run". Code: `idkmesh/github_ledger_admission.py`.

## Mechanism

The admission is a tiny immutable record on its own ref,
`refs/idkmesh/admissions/<sha256(dispatch_key)>`, holding the `dispatch_key`, the
`request_digest`, the `run_id` and the run's ledger ref. It is created with the
compare-and-set of [C9-C](GITHUB_LEDGER_APPEND_V0_1.md): `git update-ref <ref>
<new> <all-zero id>` succeeds for exactly one creator and fails for every other.
The loser reads the winner's admission and returns it. The run's ledger lives at
`refs/idkmesh/ledger/<sha256(run_id)>`, so any run id yields a valid ref.

`admit_dispatch(repository, first_record, author_name=…, author_email=…)` takes a
valid ledger record with `ledger_sequence` 1 and:

| Situation | Result |
|---|---|
| first arrival | admission created, then the first ledger record is appended |
| exact replay (same key and `request_digest`) | the existing admission is returned; nothing is written (`created=False`, `recorded=False`) |
| duplicate for another run (same key and digest, different `run_id`) | the first run's admission is returned; no second ledger ref is created |
| same key, different `request_digest` | `AdmissionConflict`; the original admission and ledger are untouched |
| a crash left an admission with an empty ledger | a replay for that same run appends the first record (`recorded=True`); a replay for a different run never completes someone else's run |
| record is not sequence 1, enables authority, or is otherwise invalid | rejected before any ref is written |

The conflicting-replay rule matches the Product Spine's idempotency contract:
exact replay returns the original, a replay with different content fails closed.

## Guarantees

- **At most one admission per key.** The all-zero-old-value update is the single
  arbiter; there is no read-then-write window.
- **At most one run per key.** Concurrent duplicates all return the same run, and
  only that run's ledger ref exists.
- **The first record is written once** even when several exact replays race to
  complete it.
- **Nothing is overwritten.** Admission refs are only ever created, never moved.

## Verified by

`tests/test_github_ledger_admission.py` against a real bare repository: first
arrival; exact replay with unchanged refs; a duplicate for another run; a create
that loses a race (a stale read followed by a create that must lose, which only
the compare-and-set prevents from overwriting); a conflicting replay; independent
keys; crash recovery in both directions; and, in the nightly tier, concurrent
duplicates for different runs admitting exactly one and concurrent exact replays
recording the first entry once; sequence, authority and malformed
stored-admission rejection. Removing the expected-zero value from `update-ref`
fails the race test in the per-PR tier (and the two concurrency tests), and removing the digest comparison fails the
conflicting-replay test.

## Boundary with other C9 slices

C9-D does **not** implement provider resubmission or reconciliation, current-state
reconstruction from events (C9-E), killed-workflow recovery (C9-F), the GitHub
evidence-branch adapter or remote pushes (C9-G), or retention policy (C9-H). It
does not authenticate who may admit: anyone who can write refs can create an
admission, which is a repository-permission concern for C9-G. Local Git plumbing
only: no network, push, GitHub call or secret.
