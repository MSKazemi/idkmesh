---
description: "C9-F safe next-step planning for a recovered ledger run, and the exhaustive kill-matrix proof that a killed coordinating workflow is recovered with exactly one provider submission."
---
# GitHub Ledger Recovery Planning and Killed-Workflow Proof v0.1

**Status:** experimental C9-F implementation contract  
**Issue:** #597 (slice C9-F), parent #570  
**Authority:** advisory planning only; it dispatches, resubmits, verifies, accepts, integrates, pushes and merges nothing.

## Purpose

[C9-E](GITHUB_LEDGER_RECOVERY_V0_1.md) derives a run's state from its records.
After a coordinating workflow is killed, a recovery workflow still has to decide
what is **safe** to do next, and the one thing that cannot be undone is sending
work to a provider twice. #597's acceptance is explicit: "kill/fail the
coordinating workflow after dispatch → a later recovery workflow reconstructs the
run and continues observation safely". Code: `idkmesh/github_ledger_recovery_plan.py`.

## The plan

`plan_recovery(state) -> RecoveryPlan` is a pure function of a `RecoveredRunState`
returning `action`, `reason`, `blind_resubmission_forbidden` and
`authority_required`.

| Recovered situation | Action | Notes |
|---|---|---|
| terminal (`decided`, `cancelled`) or `admission_blocked` | `none` | |
| any attempt with an `ambiguous` submission | `reconcile_provider` | blind resubmission forbidden |
| `dispatched`, submission `not_submitted` or unrecorded | `reconcile_provider` | the intent is recorded but the provider call may have gone out before the crash |
| `dispatched`, submission confirmed | `observe_provider` | continue by the recorded external ids |
| `proposed` / `previewed` | `preview` / `admit` | |
| `admitted`, nothing sent | `dispatch` | needs the `dispatch` authority gate |
| `attempt_failed`, retryable | `retry_attempt` | needs the `dispatch` gate; blind resubmission is not forbidden because the provider definitely failed |
| `attempt_failed`, not retryable | `await_operator` | |
| `candidate_observed` → `normalized` → `verification_requested` → `evidence_ready` | `normalize` → `request_verification` → `observe_verification` → `request_human_decision` | verification needs the `verification` gate |
| `verification_error` | `retry_verification` | needs the `verification` gate |
| `awaiting_human_decision` | `await_human_decision` | needs the `human_decision` gate |

`reconcile_provider` means: look the work up by its deterministic dispatch key and
**adopt** what the provider has. Only if the provider demonstrably has nothing may
the coordinator submit, and that decision belongs to the coordinator, made on the
lookup result, never on the ledger alone. `authority_required` names the gate that
must independently allow a step; the plan grants none.

## Intent before effect

The protocol the proof relies on: a coordinator records the **intent** to dispatch
(`dispatched` with `submission_state=not_submitted`) before it contacts the
provider, then records the confirmation (`submitted`, with the external ids) after.
A crash then leaves one of three recoverable shapes: no intent (nothing was sent,
dispatch again), intent only (look up, then submit if absent), or confirmation
(observe). Combined with [C9-D](GITHUB_LEDGER_ADMISSION_V0_1.md) idempotent
admission and [C9-C](GITHUB_LEDGER_APPEND_V0_1.md) compare-and-set appends, no
shape produces a second attempt.

## The kill-matrix proof

`tests/test_github_ledger_killed_workflow.py` drives one run from proposal to a
recorded human decision with a small coordinator, a fake provider that counts every
`submit` call, and a ledger that verifies the chain on every append. It then:

1. counts the coordinator's side-effect points (before and after every ledger
   append and provider call);
2. kills the coordinator at **each** point in turn, starts a brand-new coordinator
   that has only the ledger and the provider, and requires the run to finish with
   a recorded decision, one attempt, no failures, unique event ids and **exactly
   one** provider submission;
3. kills the recovery too, over a sample of pairs per PR and every pair in the
   nightly tier;
4. pins the two dangerous points individually: a crash between the intent record
   and the provider call (found by lookup, not resubmitted) and a crash after the
   provider call but before it is recorded (adopted, not resubmitted);
5. repeats the guarantee on a real Git ledger (nightly tier).

Making the planner treat an unconfirmed dispatch as plain `dispatch` fails the
proof, and so does a coordinator that submits without looking up (kill points 10
and 11 — after the provider call, before it is recorded).

## Limits

The proof uses a fake provider whose lookup is exact. A real provider's lookup by
dispatch key may be eventually consistent, rate-limited or absent; how a real
driver reconciles is that driver's contract, and a driver that cannot look up by
key must report `ambiguous` and stop for an operator rather than resubmit.
Resuming under live GitHub Actions concurrency, the evidence-branch adapter and
retention remain C9-G and C9-H. Local plumbing only: no network, push, GitHub call
or secret.
