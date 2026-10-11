"""Safe next-step planning for a recovered ledger run (slice C9-F).

C9-E derives a run's current state from its records. After a coordinating
workflow is killed, a recovery workflow still has to decide what is *safe* to do
next. This module is that decision as a pure function of the recovered state,
and it is deliberately conservative about the one thing that cannot be undone:
sending work to a provider twice.

The rules, in priority order:

* a terminal run needs nothing;
* a run with an **ambiguous or unconfirmed provider submission** gets
  ``reconcile_provider``: look the work up by its deterministic dispatch key and
  adopt what the provider has. Only if the provider demonstrably has nothing may
  the coordinator submit, and that decision is the coordinator's, made on the
  lookup result, never on the ledger alone;
* otherwise the plan follows the lifecycle: the next Product Spine step for the
  recorded state.

A plan is advisory. ``authority_required`` names the gate that must independently
allow a step (dispatch, verification, a human decision); the plan itself grants
none, and nothing here dispatches, resubmits, verifies, accepts, pushes or merges.
"""

from __future__ import annotations

from dataclasses import dataclass

from idkmesh.github_ledger_recovery import RecoveredRunState

# action -> (reason, authority gate that must allow it, or None)
_STEPS: dict[str, tuple[str, str | None]] = {
    "preview": ("run is proposed; build its preview", None),
    "admit": ("run is previewed; admission decides eligibility", None),
    "dispatch": ("run is admitted and nothing has been sent to a provider", "dispatch"),
    "observe_provider": ("work was submitted; keep observing it by its external ids", None),
    "retry_attempt": ("the last attempt failed with a retryable failure", "dispatch"),
    "await_operator": ("the last attempt failed and is not retryable; an operator decides", None),
    "normalize": ("a candidate was observed; normalize it into a result manifest", None),
    "request_verification": ("a result manifest exists; request verification", "verification"),
    "observe_verification": ("verification was requested; observe its result", None),
    "retry_verification": ("verification errored; request it again", "verification"),
    "request_human_decision": ("evidence is ready; ask for a human decision", None),
    "await_human_decision": ("a human decision is pending", "human_decision"),
    "reconcile_provider": (
        "it is unknown whether the provider accepted the work; look it up by dispatch key", None,
    ),
    "none": ("the run is finished", None),
}
ACTIONS = frozenset(_STEPS)

_BY_STATE = {
    "proposed": "preview",
    "previewed": "admit",
    "admission_blocked": "none",
    "admitted": "dispatch",
    "candidate_observed": "normalize",
    "normalized": "request_verification",
    "verification_requested": "observe_verification",
    "verification_error": "retry_verification",
    "evidence_ready": "request_human_decision",
    "awaiting_human_decision": "await_human_decision",
    "decided": "none",
    "cancelled": "none",
}


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    action: str
    reason: str
    #: Whether sending the work to the provider again without first looking it up
    #: could create a duplicate attempt. True whenever any provider contact has
    #: been recorded for the current attempt.
    blind_resubmission_forbidden: bool
    #: The independent authority gate that must allow this step, if any.
    authority_required: str | None


def plan_recovery(state: RecoveredRunState) -> RecoveryPlan:
    """The next safe step for a recovered run."""

    current = state.attempts[-1] if state.attempts else None
    contacted = current is not None and current.submission_state not in (None, "definite_failure")

    if state.terminal or state.state == "admission_blocked":
        return _plan("none", False)
    if state.needs_reconciliation:
        return _plan("reconcile_provider", True)

    if state.state == "dispatched":
        if current is None or current.submission_state in (None, "not_submitted"):
            # The intent to dispatch is recorded but nothing confirms the
            # provider call: it may have gone out before the crash.
            return _plan("reconcile_provider", True)
        return _plan("observe_provider", True)

    if state.state == "attempt_failed":
        retryable = current is not None and current.failure is not None and current.failure[2]
        return _plan("retry_attempt" if retryable else "await_operator", contacted)

    return _plan(_BY_STATE[state.state], contacted)


def _plan(action: str, forbidden: bool) -> RecoveryPlan:
    reason, authority = _STEPS[action]
    return RecoveryPlan(action, reason, forbidden, authority)
