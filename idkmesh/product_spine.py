"""Pure Product Spine lifecycle primitives.

This module implements the PS-A foundation from the Product Spine execution
plan. It is intentionally standard-library only and performs no provider,
network, filesystem, database, GitHub, verification, human-decision, or merge
side effects.

The lifecycle is an operational projection over existing canonical artifacts;
it is not a new correctness or authority protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping

RUN_STATES = frozenset(
    {
        "proposed",
        "previewed",
        "admission_blocked",
        "admitted",
        "dispatched",
        "attempt_failed",
        "candidate_observed",
        "normalized",
        "verification_requested",
        "verification_error",
        "evidence_ready",
        "awaiting_human_decision",
        "decided",
        "cancelled",
    }
)

ATTEMPT_STATES = frozenset(
    {
        "created",
        "dispatched",
        "worker_error",
        "candidate_observed",
        "normalization_error",
        "normalized",
        "verification_requested",
        "verification_error",
        "verified",
        "cancelled",
    }
)

_RUN_TRANSITIONS = {
    "proposed": frozenset({"previewed", "cancelled"}),
    "previewed": frozenset(
        {"admission_blocked", "admitted", "cancelled"}
    ),
    "admission_blocked": frozenset({"cancelled"}),
    "admitted": frozenset({"dispatched", "cancelled"}),
    "dispatched": frozenset(
        {"attempt_failed", "candidate_observed", "cancelled"}
    ),
    # A new explicit attempt may be dispatched after a failed attempt. The
    # failed attempt record remains immutable; this is not a state rewind.
    "attempt_failed": frozenset({"dispatched", "cancelled"}),
    "candidate_observed": frozenset({"normalized", "cancelled"}),
    "normalized": frozenset({"verification_requested", "cancelled"}),
    "verification_requested": frozenset(
        {"verification_error", "evidence_ready", "cancelled"}
    ),
    # An evaluator/control-path retry may request verification again while the
    # failed verifier attempt remains retained independently.
    "verification_error": frozenset(
        {"verification_requested", "evidence_ready", "cancelled"}
    ),
    "evidence_ready": frozenset({"awaiting_human_decision"}),
    "awaiting_human_decision": frozenset({"decided", "cancelled"}),
    "decided": frozenset(),
    "cancelled": frozenset(),
}

_ATTEMPT_TRANSITIONS = {
    "created": frozenset({"dispatched", "cancelled"}),
    "dispatched": frozenset(
        {"worker_error", "candidate_observed", "cancelled"}
    ),
    "worker_error": frozenset(),
    "candidate_observed": frozenset(
        {"normalization_error", "normalized", "cancelled"}
    ),
    "normalization_error": frozenset(),
    "normalized": frozenset({"verification_requested", "cancelled"}),
    "verification_requested": frozenset(
        {"verification_error", "verified", "cancelled"}
    ),
    "verification_error": frozenset(),
    "verified": frozenset(),
    "cancelled": frozenset(),
}

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_REVISION_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_AUTHORITY_MODES = frozenset(
    {
        "deterministic",
        "agent_candidate",
        "human_gate_then_agent",
        "human_required",
    }
)

_NO_AUTHORITY = {
    "canonical_state_write": False,
    "git_push": False,
    "merge": False,
}


class ProductSpineError(ValueError):
    """Stable fail-closed Product Spine contract error."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> ProductSpineError:
    return ProductSpineError(code, path, message)


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail("invalid_type", path, "must be a non-empty string")
    return value


def _identifier(value: Any, path: str) -> str:
    text = _text(value, path)
    if _ID_RE.fullmatch(text) is None:
        raise _fail(
            "invalid_identifier",
            path,
            "contains unsupported characters",
        )
    return text


def _digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise _fail(
            "invalid_digest",
            path,
            "must be sha256:<64 lowercase hex>",
        )
    return value


def _state(value: Any, path: str, allowed: frozenset[str]) -> str:
    text = _text(value, path)
    if text not in allowed:
        raise _fail(
            "invalid_state",
            path,
            "unsupported state",
        )
    return text


def _git_revision(value: Any, path: str) -> str:
    text = _text(value, path)
    if _GIT_REVISION_RE.fullmatch(text) is None:
        raise _fail(
            "invalid_source_revision",
            path,
            "must be a 40- or 64-character hexadecimal Git object id",
        )
    return text.lower()


def _optional_digest(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _digest(value, path)


def _optional_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _text(value, path)


def transition_run_state(current: str, target: str) -> str:
    """Validate one run-level transition and return the target state.

    Re-applying the current state is an idempotent no-op. Every other edge must
    be explicitly listed in the v0.1 lifecycle graph.
    """

    current = _state(current, "current", RUN_STATES)
    target = _state(target, "target", RUN_STATES)
    if target == current:
        return current
    if target not in _RUN_TRANSITIONS[current]:
        raise _fail(
            "invalid_run_transition",
            "state",
            f"{current!r} cannot transition to {target!r}",
        )
    return target


def transition_attempt_state(current: str, target: str) -> str:
    """Validate one attempt-level transition and return the target state."""

    current = _state(current, "current", ATTEMPT_STATES)
    target = _state(target, "target", ATTEMPT_STATES)
    if target == current:
        return current
    if target not in _ATTEMPT_TRANSITIONS[current]:
        raise _fail(
            "invalid_attempt_transition",
            "state",
            f"{current!r} cannot transition to {target!r}",
        )
    return target


@dataclass(frozen=True, slots=True)
class AttemptProjection:
    """Immutable operational projection for one worker/verifier attempt."""

    attempt_id: str
    order: int
    connector_id: str
    state: str = "created"
    provider_reference: str | None = None
    candidate_reference_digest: str | None = None
    result_manifest_digest: str | None = None
    verification_semantic_digest: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.attempt_id, "attempt_id")
        _identifier(self.connector_id, "connector_id")
        _state(self.state, "state", ATTEMPT_STATES)
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 1:
            raise _fail("invalid_value", "order", "must be an integer >= 1")
        _optional_text(self.provider_reference, "provider_reference")
        _optional_digest(
            self.candidate_reference_digest,
            "candidate_reference_digest",
        )
        _optional_digest(
            self.result_manifest_digest,
            "result_manifest_digest",
        )
        _optional_digest(
            self.verification_semantic_digest,
            "verification_semantic_digest",
        )
        _optional_text(self.error_code, "error_code")
        self._validate_evidence_shape()

    def _validate_evidence_shape(self) -> None:
        if self.state == "worker_error":
            if self.error_code is None:
                raise _fail(
                    "invalid_attempt_evidence",
                    "error_code",
                    "worker_error requires an error code",
                )
            if any(
                value is not None
                for value in (
                    self.candidate_reference_digest,
                    self.result_manifest_digest,
                    self.verification_semantic_digest,
                )
            ):
                raise _fail(
                    "invalid_attempt_evidence",
                    "state",
                    "worker_error cannot claim candidate/result/verification evidence",
                )
            return

        if self.state == "normalization_error":
            if self.error_code is None or self.candidate_reference_digest is None:
                raise _fail(
                    "invalid_attempt_evidence",
                    "state",
                    "normalization_error requires a candidate reference and error code",
                )
            if any(
                value is not None
                for value in (
                    self.result_manifest_digest,
                    self.verification_semantic_digest,
                )
            ):
                raise _fail(
                    "invalid_attempt_evidence",
                    "state",
                    "normalization_error cannot claim result/verification evidence",
                )
            return

        if self.state == "verification_error":
            if self.error_code is None or self.result_manifest_digest is None:
                raise _fail(
                    "invalid_attempt_evidence",
                    "state",
                    "verification_error requires a ResultManifest and error code",
                )
            if self.verification_semantic_digest is not None:
                raise _fail(
                    "invalid_attempt_evidence",
                    "verification_semantic_digest",
                    "verification_error cannot claim verification success evidence",
                )
            return

        if self.state in {
            "candidate_observed",
            "normalized",
            "verification_requested",
            "verified",
        } and self.candidate_reference_digest is None:
            raise _fail(
                "invalid_attempt_evidence",
                "candidate_reference_digest",
                f"{self.state} requires a candidate reference digest",
            )

        if self.state in {"normalized", "verification_requested", "verified"}:
            if self.result_manifest_digest is None:
                raise _fail(
                    "invalid_attempt_evidence",
                    "result_manifest_digest",
                    f"{self.state} requires a ResultManifest digest",
                )

        if self.state == "verified" and self.verification_semantic_digest is None:
            raise _fail(
                "invalid_attempt_evidence",
                "verification_semantic_digest",
                "verified requires verification semantic evidence",
            )

        if self.error_code is not None and self.state not in {
            "worker_error",
            "normalization_error",
            "verification_error",
        }:
            raise _fail(
                "invalid_attempt_evidence",
                "error_code",
                "error_code is only valid for explicit error states",
            )

    def transition(self, target: str, **changes: Any) -> "AttemptProjection":
        """Return a new immutable attempt after one legal transition."""

        state = transition_attempt_state(self.state, target)
        try:
            return replace(self, state=state, **changes)
        except TypeError as exc:
            raise _fail(
                "invalid_update",
                "attempt",
                "unsupported attempt projection field",
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "order": self.order,
            "connector_id": self.connector_id,
            "state": self.state,
            "provider_reference": self.provider_reference,
            "candidate_reference_digest": self.candidate_reference_digest,
            "result_manifest_digest": self.result_manifest_digest,
            "verification_semantic_digest": self.verification_semantic_digest,
            "error_code": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class ProductSpineRun:
    """Immutable read projection over one Product Spine lifecycle."""

    run_id: str
    request_digest: str
    project_id: str
    work_unit_id: str
    work_unit_version: int
    work_unit_digest: str
    source_revision: str
    authority_mode: str
    routing_policy_version: str
    state: str = "proposed"
    admitted_connectors: tuple[str, ...] = ()
    attempts: tuple[AttemptProjection, ...] = ()
    evidence_report_digest: str | None = None
    human_decision_record_digest: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.run_id, "run_id")
        _digest(self.request_digest, "request_digest")
        _identifier(self.project_id, "project_id")
        _identifier(self.work_unit_id, "work_unit_id")
        if (
            isinstance(self.work_unit_version, bool)
            or not isinstance(self.work_unit_version, int)
            or self.work_unit_version < 1
        ):
            raise _fail(
                "invalid_value",
                "work_unit_version",
                "must be an integer >= 1",
            )
        _digest(self.work_unit_digest, "work_unit_digest")
        normalized_revision = _git_revision(
            self.source_revision,
            "source_revision",
        )
        object.__setattr__(self, "source_revision", normalized_revision)
        _text(self.authority_mode, "authority_mode")
        if self.authority_mode not in _AUTHORITY_MODES:
            raise _fail(
                "invalid_authority_mode",
                "authority_mode",
                "must match connector routing authority semantics",
            )
        _text(self.routing_policy_version, "routing_policy_version")
        _state(self.state, "state", RUN_STATES)
        _optional_digest(
            self.evidence_report_digest,
            "evidence_report_digest",
        )
        _optional_digest(
            self.human_decision_record_digest,
            "human_decision_record_digest",
        )

        if len(self.admitted_connectors) != len(set(self.admitted_connectors)):
            raise _fail(
                "duplicate_connector",
                "admitted_connectors",
                "connector ids must be unique",
            )
        for index, connector_id in enumerate(self.admitted_connectors):
            _identifier(connector_id, f"admitted_connectors[{index}]")

        if self.state in {
            "admitted",
            "dispatched",
            "attempt_failed",
            "candidate_observed",
            "normalized",
            "verification_requested",
            "verification_error",
            "evidence_ready",
            "awaiting_human_decision",
            "decided",
        } and not self.admitted_connectors:
            raise _fail(
                "invalid_admission",
                "admitted_connectors",
                f"{self.state} requires at least one admitted connector",
            )
        if self.state in {"proposed", "previewed", "admission_blocked"} and self.attempts:
            raise _fail(
                "invalid_attempt_state",
                "attempts",
                f"{self.state} cannot contain worker attempts",
            )

        attempt_ids = [attempt.attempt_id for attempt in self.attempts]
        if len(attempt_ids) != len(set(attempt_ids)):
            raise _fail(
                "duplicate_attempt",
                "attempts",
                "attempt ids must be unique",
            )
        orders = [attempt.order for attempt in self.attempts]
        if orders != list(range(1, len(self.attempts) + 1)):
            raise _fail(
                "invalid_attempt_order",
                "attempts",
                "attempt order must be contiguous and match tuple order",
            )

        if self.state in {"evidence_ready", "awaiting_human_decision", "decided"}:
            if self.evidence_report_digest is None:
                raise _fail(
                    "invalid_run_evidence",
                    "evidence_report_digest",
                    f"{self.state} requires an evidence report digest",
                )
        if self.state == "decided" and self.human_decision_record_digest is None:
            raise _fail(
                "invalid_run_evidence",
                "human_decision_record_digest",
                "decided requires a human decision record digest",
            )
        if (
            self.human_decision_record_digest is not None
            and self.state != "decided"
        ):
            raise _fail(
                "invalid_run_evidence",
                "human_decision_record_digest",
                "human decision evidence is only valid in decided state",
            )

    def transition(self, target: str, **changes: Any) -> "ProductSpineRun":
        """Return a new immutable run after one legal lifecycle transition."""

        state = transition_run_state(self.state, target)
        if state == "admitted" and self.authority_mode == "human_required":
            raise _fail(
                "human_authority_required",
                "authority_mode",
                "human_required work cannot enter automatic connector admission",
            )
        try:
            return replace(self, state=state, **changes)
        except TypeError as exc:
            raise _fail(
                "invalid_update",
                "run",
                "unsupported run projection field",
            ) from exc

    def append_attempt(self, attempt: AttemptProjection) -> "ProductSpineRun":
        """Return a run with one newly created attempt appended.

        Attempt creation is only valid after admission. Failed prior attempts
        stay retained; retries append a new identity rather than rewriting one.
        """

        if not isinstance(attempt, AttemptProjection):
            raise _fail(
                "invalid_type",
                "attempt",
                "must be AttemptProjection",
            )
        if self.state not in {"admitted", "dispatched", "attempt_failed"}:
            raise _fail(
                "attempt_not_admitted",
                "state",
                "attempt creation requires an admitted run",
            )
        if attempt.order != len(self.attempts) + 1:
            raise _fail(
                "invalid_attempt_order",
                "attempt.order",
                "new attempt order must follow retained attempts",
            )
        if attempt.attempt_id in {item.attempt_id for item in self.attempts}:
            raise _fail(
                "duplicate_attempt",
                "attempt.attempt_id",
                "attempt id already exists",
            )
        if (
            self.admitted_connectors
            and attempt.connector_id not in self.admitted_connectors
        ):
            raise _fail(
                "connector_not_admitted",
                "attempt.connector_id",
                "attempt connector is not in the admitted connector set",
            )
        return replace(self, attempts=self.attempts + (attempt,))

    def replace_attempt(
        self,
        attempt: AttemptProjection,
    ) -> "ProductSpineRun":
        """Replace one attempt projection by identity without changing order."""

        if not isinstance(attempt, AttemptProjection):
            raise _fail(
                "invalid_type",
                "attempt",
                "must be AttemptProjection",
            )
        matches = [
            index
            for index, item in enumerate(self.attempts)
            if item.attempt_id == attempt.attempt_id
        ]
        if len(matches) != 1:
            raise _fail(
                "unknown_attempt",
                "attempt.attempt_id",
                "attempt id must match exactly one retained attempt",
            )
        index = matches[0]
        if attempt.order != self.attempts[index].order:
            raise _fail(
                "invalid_attempt_order",
                "attempt.order",
                "attempt order is immutable",
            )
        updated = list(self.attempts)
        updated[index] = attempt
        return replace(self, attempts=tuple(updated))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "kind": "idkmesh-product-spine-run",
            "run_id": self.run_id,
            "request_digest": self.request_digest,
            "project_id": self.project_id,
            "work_unit": {
                "id": self.work_unit_id,
                "version": self.work_unit_version,
                "digest": self.work_unit_digest,
                "source_revision": self.source_revision,
            },
            "routing": {
                "policy_version": self.routing_policy_version,
                "authority_mode": self.authority_mode,
                "admitted_connectors": list(self.admitted_connectors),
            },
            "state": self.state,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "evidence_report_digest": self.evidence_report_digest,
            "human_decision_record_digest": self.human_decision_record_digest,
            "authority": dict(_NO_AUTHORITY),
        }


def projection_from_mapping(raw: Mapping[str, Any]) -> ProductSpineRun:
    """Strictly parse one Product Spine projection emitted by to_dict()."""

    if not isinstance(raw, Mapping):
        raise _fail("invalid_type", "$", "projection must be an object")
    required = {
        "schema_version",
        "kind",
        "run_id",
        "request_digest",
        "project_id",
        "work_unit",
        "routing",
        "state",
        "attempts",
        "evidence_report_digest",
        "human_decision_record_digest",
        "authority",
    }
    missing = required - set(raw)
    if missing:
        raise _fail(
            "missing_field",
            "$",
            "missing: " + ", ".join(sorted(missing)),
        )
    unexpected = set(raw) - required
    if unexpected:
        raise _fail(
            "unknown_field",
            "$",
            "unknown: " + ", ".join(sorted(unexpected)),
        )
    if raw["schema_version"] != "0.1":
        raise _fail(
            "unsupported_version",
            "schema_version",
            "must be '0.1'",
        )
    if raw["kind"] != "idkmesh-product-spine-run":
        raise _fail(
            "invalid_kind",
            "kind",
            "must be 'idkmesh-product-spine-run'",
        )
    if raw["authority"] != _NO_AUTHORITY:
        raise _fail(
            "authority_violation",
            "authority",
            "Product Spine projection cannot grant write/push/merge authority",
        )

    work = raw["work_unit"]
    route = raw["routing"]
    attempts_raw = raw["attempts"]
    if not isinstance(work, Mapping):
        raise _fail("invalid_type", "work_unit", "must be an object")
    if not isinstance(route, Mapping):
        raise _fail("invalid_type", "routing", "must be an object")
    if not isinstance(attempts_raw, list):
        raise _fail("invalid_type", "attempts", "must be an array")

    work_fields = {"id", "version", "digest", "source_revision"}
    route_fields = {
        "policy_version",
        "authority_mode",
        "admitted_connectors",
    }
    if set(work) != work_fields:
        raise _fail(
            "invalid_shape",
            "work_unit",
            "work_unit fields do not match v0.1 projection",
        )
    if set(route) != route_fields:
        raise _fail(
            "invalid_shape",
            "routing",
            "routing fields do not match v0.1 projection",
        )
    connectors = route["admitted_connectors"]
    if not isinstance(connectors, list):
        raise _fail(
            "invalid_type",
            "routing.admitted_connectors",
            "must be an array",
        )

    attempts: list[AttemptProjection] = []
    for index, item in enumerate(attempts_raw):
        if not isinstance(item, Mapping):
            raise _fail(
                "invalid_type",
                f"attempts[{index}]",
                "must be an object",
            )
        expected_attempt_fields = {
            "attempt_id",
            "order",
            "connector_id",
            "state",
            "provider_reference",
            "candidate_reference_digest",
            "result_manifest_digest",
            "verification_semantic_digest",
            "error_code",
        }
        if set(item) != expected_attempt_fields:
            raise _fail(
                "invalid_shape",
                f"attempts[{index}]",
                "attempt fields do not match v0.1 projection",
            )
        attempts.append(AttemptProjection(**dict(item)))

    return ProductSpineRun(
        run_id=raw["run_id"],
        request_digest=raw["request_digest"],
        project_id=raw["project_id"],
        work_unit_id=work["id"],
        work_unit_version=work["version"],
        work_unit_digest=work["digest"],
        source_revision=work["source_revision"],
        authority_mode=route["authority_mode"],
        routing_policy_version=route["policy_version"],
        state=raw["state"],
        admitted_connectors=tuple(connectors),
        attempts=tuple(attempts),
        evidence_report_digest=raw["evidence_report_digest"],
        human_decision_record_digest=raw["human_decision_record_digest"],
    )
