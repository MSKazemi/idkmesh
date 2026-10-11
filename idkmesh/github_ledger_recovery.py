"""Recovery reader for the C9 GitHub-native durable ledger (slice C9-E).

Ledger records are immutable observations; "current state" is never stored, so a
coordinator that restarts (or a new one after a killed workflow) has to *derive*
it. This module does that, as a pure function of the records:

``reconstruct_run_state(records)`` first verifies the records as a complete
chain (:func:`serialize_github_ledger_chain`), then replays them in order,
checking that the history is one a real run could have produced:

* every change of ``event.state`` is a legal Product Spine transition
  (:func:`idkmesh.product_spine.transition_run_state`), and a terminal state
  (``decided``, ``cancelled``) is never left;
* attempt numbers never decrease, and one ``attempt_id`` keeps one number and
  one connector;
* a recorded human decision never reverts to pending/not-recorded and never has
  its record replaced, and only a ``recorded`` decision carries a record.

It never drops negative evidence: every failure observation is retained in
order, and a provider submission left ``ambiguous`` is reported as a hazard so a
recovering coordinator reconciles instead of blindly resubmitting.

The result is a description, not a decision. This module performs no I/O in its
pure form, and :func:`recover_run` only reads a :class:`GitLedger`. It never
dispatches, resubmits, verifies, accepts, pushes or merges; what to *do* about a
hazard is C9-F's job, under the usual authority gates.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from idkmesh.github_ledger_append import GitHubLedgerAppendError, GitLedger
from idkmesh.github_ledger_serialization import serialize_github_ledger_chain
from idkmesh.product_spine import ProductSpineError, transition_run_state

TERMINAL_STATES = frozenset({"decided", "cancelled"})


class RecoveryError(GitHubLedgerAppendError):
    """The records are a valid chain but not a history a run could have made."""

    code = "recovery_inconsistent"

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {message}")


@dataclass(frozen=True, slots=True)
class AttemptState:
    attempt_id: str
    attempt_number: int
    connector_id: str
    reason: str
    first_sequence: int
    last_sequence: int
    #: Latest provider submission state seen for this attempt, or None.
    submission_state: str | None
    external_run_id: str | None
    external_session_id: str | None
    external_job_id: str | None
    #: Latest failure observed on this attempt, as ``(code, classification, retryable)``.
    failure: tuple[str, str, bool] | None


@dataclass(frozen=True, slots=True)
class FailureObservation:
    sequence: int
    attempt_id: str | None
    code: str
    classification: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class RecoveredRunState:
    repository: str
    project_id: str
    run_id: str
    work_unit_id: str
    dispatch_key: str
    request_digest: str
    state: str
    terminal: bool
    last_sequence: int
    head_digest: str
    last_event_id: str
    last_event_type: str
    last_occurred_at: str
    attempts: tuple[AttemptState, ...]
    #: Every failure observation, in ledger order. Never filtered.
    failures: tuple[FailureObservation, ...]
    candidate_reference: tuple[str, str | None] | None
    result_manifest: tuple[str, str | None] | None
    verification_results: tuple[tuple[str, str | None], ...]
    human_decision_state: str
    human_decision_record: tuple[str, str | None] | None
    #: Attempts whose latest submission state is ``ambiguous``: it is unknown
    #: whether the provider accepted the work, so do not resubmit blindly.
    ambiguous_attempts: tuple[str, ...]

    @property
    def needs_reconciliation(self) -> bool:
        return bool(self.ambiguous_attempts)


def _ref(value: Mapping[str, Any] | None) -> tuple[str, str | None] | None:
    return None if value is None else (value["digest"], value.get("storage_path"))


def reconstruct_run_state(records: Iterable[Mapping[str, Any]]) -> RecoveredRunState:
    """Derive the current state of one run from its complete record chain."""

    materialized = list(records)
    chain = serialize_github_ledger_chain(materialized)  # integrity first
    first = materialized[0]

    state: str | None = None
    attempts: dict[str, dict[str, Any]] = {}
    last_attempt_number = 0
    failures: list[FailureObservation] = []
    candidate = manifest = None
    verification: list[tuple[str, str | None]] = []
    human_state = "not_recorded"
    human_record: tuple[str, str | None] | None = None

    for record, item in zip(materialized, chain):
        sequence = item.sequence
        new_state = record["event"]["state"]
        if state is not None and new_state != state:
            try:
                transition_run_state(state, new_state)
            except ProductSpineError as exc:
                raise RecoveryError(
                    "illegal_transition",
                    f"record {sequence}: {state} -> {new_state} is not a legal transition",
                ) from exc
        state = new_state

        attempt = record.get("attempt")
        provider = record.get("provider")
        failure = record.get("failure")
        attempt_id = None
        if attempt is not None:
            attempt_id = attempt["attempt_id"]
            number = attempt["attempt_number"]
            if number < last_attempt_number:
                raise RecoveryError(
                    "attempt_number_regressed",
                    f"record {sequence}: attempt {number} after attempt {last_attempt_number}",
                )
            last_attempt_number = number
            known = attempts.get(attempt_id)
            if known is not None and (
                known["attempt_number"] != number or known["connector_id"] != attempt["connector_id"]
            ):
                raise RecoveryError(
                    "attempt_identity_changed",
                    f"record {sequence}: {attempt_id} changed number or connector",
                )
            entry = attempts.setdefault(
                attempt_id,
                {
                    "attempt_id": attempt_id,
                    "attempt_number": number,
                    "connector_id": attempt["connector_id"],
                    "reason": attempt["reason"],
                    "first_sequence": sequence,
                    "submission_state": None,
                    "external_run_id": None,
                    "external_session_id": None,
                    "external_job_id": None,
                    "failure": None,
                },
            )
            entry["last_sequence"] = sequence
            if provider is not None:
                entry["submission_state"] = provider["submission_state"]
                for key in ("external_run_id", "external_session_id", "external_job_id"):
                    if provider[key] is not None:
                        entry[key] = provider[key]
            if failure is not None:
                entry["failure"] = (failure["code"], failure["classification"], failure["retryable"])
        if failure is not None:
            failures.append(
                FailureObservation(
                    sequence, attempt_id, failure["code"], failure["classification"],
                    failure["retryable"],
                )
            )

        if record.get("candidate_reference") is not None:
            candidate = _ref(record["candidate_reference"])
        if record.get("result_manifest") is not None:
            manifest = _ref(record["result_manifest"])
        for ref in record.get("verification_results") or ():
            pair = _ref(ref)
            if pair not in verification:
                verification.append(pair)

        decision = record["human_decision"]
        decision_state = decision["state"]
        decision_record = _ref(decision["record"])
        if (decision_state == "recorded") != (decision_record is not None):
            raise RecoveryError(
                "human_decision_inconsistent",
                f"record {sequence}: only a recorded decision carries a record reference",
            )
        if human_state == "recorded" and (
            decision_state != "recorded" or decision_record != human_record
        ):
            raise RecoveryError(
                "human_decision_changed",
                f"record {sequence}: a recorded human decision was reverted or replaced",
            )
        human_state, human_record = decision_state, decision_record

    last = materialized[-1]
    last_item = chain[-1]
    assert state is not None
    attempt_states = tuple(
        AttemptState(
            e["attempt_id"], e["attempt_number"], e["connector_id"], e["reason"],
            e["first_sequence"], e["last_sequence"], e["submission_state"],
            e["external_run_id"], e["external_session_id"], e["external_job_id"], e["failure"],
        )
        for e in sorted(attempts.values(), key=lambda e: (e["attempt_number"], e["first_sequence"]))
    )
    return RecoveredRunState(
        repository=first["repository"],
        project_id=first["project_id"],
        run_id=first["run_id"],
        work_unit_id=first["work_unit"]["id"],
        dispatch_key=first["idempotency"]["dispatch_key"],
        request_digest=first["idempotency"]["request_digest"],
        state=state,
        terminal=state in TERMINAL_STATES,
        last_sequence=last_item.sequence,
        head_digest=last_item.record_digest,
        last_event_id=last["event"]["event_id"],
        last_event_type=last["event"]["event_type"],
        last_occurred_at=last["event"]["occurred_at"],
        attempts=attempt_states,
        failures=tuple(failures),
        candidate_reference=candidate,
        result_manifest=manifest,
        verification_results=tuple(verification),
        human_decision_state=human_state,
        human_decision_record=human_record,
        ambiguous_attempts=tuple(
            a.attempt_id for a in attempt_states if a.submission_state == "ambiguous"
        ),
    )


def recover_run(ledger: GitLedger) -> RecoveredRunState | None:
    """Read ``ledger`` and derive its run's state; ``None`` if nothing is recorded."""

    records = ledger.read_records()
    return reconstruct_run_state(records) if records else None
