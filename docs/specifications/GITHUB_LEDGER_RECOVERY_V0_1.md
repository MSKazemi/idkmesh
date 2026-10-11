---
description: "C9-E recovery reader for the GitHub-native durable ledger: derive a run's current state from its immutable records, never dropping negative evidence, and refuse histories no real run could have produced."
---
# GitHub Ledger Recovery Reader v0.1

**Status:** experimental C9-E implementation contract  
**Issue:** #597 (slice C9-E), parent #570  
**Authority:** a description of recorded state; it does not dispatch, resubmit, verify, accept, integrate, push or merge.

## Purpose

Ledger records are immutable observations. "Current state" is never stored, so a
coordinator that restarts — or a new one after a killed workflow — has to derive
it from the records alone ("status can be reconstructed after a coordinator
workflow is killed and restarted", #597). Code: `idkmesh/github_ledger_recovery.py`.

## Interface

- `reconstruct_run_state(records) -> RecoveredRunState` — pure, deterministic,
  does not mutate its input.
- `recover_run(ledger) -> RecoveredRunState | None` — reads a
  [`GitLedger`](GITHUB_LEDGER_APPEND_V0_1.md) and reconstructs; `None` if nothing
  is recorded yet.

`RecoveredRunState` carries: run identity and dispatch key; the current `state`
and whether it is `terminal` (`decided`, `cancelled`); the head sequence and
digest; the last event; one `AttemptState` per attempt (number, connector,
reason, latest provider submission state and external ids, latest failure);
**every** failure observation in ledger order; the latest candidate reference and
result manifest, all verification results, and the human-decision state and
record; and `ambiguous_attempts`.

## What it checks

1. **Chain integrity first.** The records must verify as a complete chain
   ([C9-B](GITHUB_LEDGER_SERIALIZATION_V0_1.md)); a broken link fails before any
   replay.
2. **Legal lifecycle.** Every change of `event.state` must be a legal Product
   Spine transition (`transition_run_state`), and nothing follows a terminal
   state. A repeat of the same state (a further observation) is allowed.
3. **Attempt identity.** Attempt numbers never decrease; one `attempt_id` keeps
   one number and one connector.
4. **Human decision.** Only a `recorded` decision carries a record reference, and
   once recorded it is never reverted to `pending`/`not_recorded` or replaced.

A violation raises `RecoveryError` (code `recovery_inconsistent`, with a `reason`
such as `illegal_transition`, `attempt_number_regressed`,
`attempt_identity_changed`, `human_decision_changed`,
`human_decision_inconsistent`). The reader refuses rather than reconstructing a
state the run could not have reached.

Note that the frozen C9-B fixture is a valid *chain* but not a legal *history*
(it goes `proposed → admitted`, skipping `previewed`), because it exercises
serialization only; recovery says so.

## Negative evidence is never dropped

Failed, cancelled and recovery-required observations stay in `failures` in ledger
order, and a failed attempt remains in `attempts` after a retry. A provider
submission whose latest state is `ambiguous` is reported in `ambiguous_attempts`
(`needs_reconciliation`): it is unknown whether the provider accepted the work,
so a recovering coordinator must reconcile, not blindly resubmit. A later record
that resolves the submission clears the hazard.

## Restart safety

Reconstruction works from **any prefix** of a valid chain, because a crash can
land after any record; the test suite replays every prefix of a full run and
recovers a run from a real Git ledger through freshly constructed ledger objects
with only the repository surviving.

## Boundary with other C9 slices

C9-E reports state and hazards. It does **not** decide what to do about them:
resuming observation after a killed workflow, reconciling an ambiguous
submission, and the recovery test that kills a workflow are C9-F; the GitHub
evidence-branch adapter is C9-G; retention is C9-H. It authenticates no one and
reads no secret; `recover_run` is the only function that touches Git, and only to
read.
