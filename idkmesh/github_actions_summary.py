"""Public-safe, deterministic GitHub Actions summary projection for C14-A.

Inputs are canonical IDs/digests/revisions and bounded check states only: no raw
issue text, provider payload, prompt, log, credential, or secret is accepted.
Rendering is side-effect free and grants no execution or integration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from idkmesh.product_spine import ATTEMPT_STATES, RUN_STATES

_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REVISION = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_CHECK_STATUSES = frozenset({"passed", "failed", "skipped", "inconclusive", "error"})
_VERIFICATION_STATUSES = frozenset(
    {"passed", "failed", "inconclusive", "error", "timeout", "cancelled"}
)
_CANDIDATE_REQUIRED = frozenset(
    {
        "candidate_observed",
        "normalization_error",
        "normalized",
        "verification_requested",
        "verification_error",
        "verified",
    }
)
_MAX_CHECKS = 200
_MAX_BYTES = 64 * 1024


def _inline(value: object, field: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds maximum length")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{field} contains control characters")
    if "`" in value or "|" in value:
        raise ValueError(f"{field} contains unsupported Markdown delimiters")
    return value


def _identifier(value: object, field: str) -> str:
    text = _inline(value, field, 192)
    if _ID.fullmatch(text) is None:
        raise ValueError(f"{field} contains unsupported characters")
    return text


def _revision(value: object, field: str) -> str:
    if not isinstance(value, str) or _REVISION.fullmatch(value) is None:
        raise ValueError(f"{field} must be a 40- or 64-character Git object id")
    return value.lower()


@dataclass(frozen=True, slots=True)
class GitHubActionsCheck:
    check_id: str
    status: str
    required: bool

    def __post_init__(self) -> None:
        _inline(self.check_id, "check_id", 128)
        if self.status not in _CHECK_STATUSES:
            raise ValueError("status must be a VerificationResult check status")
        if not isinstance(self.required, bool):
            raise ValueError("required must be boolean")


@dataclass(frozen=True, slots=True)
class GitHubActionsRunSummary:
    """One non-authoritative Actions summary built from validated records."""

    repository: str
    work_unit_id: str
    work_unit_digest: str
    run_id: str
    run_state: str
    attempt_id: str
    attempt_state: str
    source_revision: str
    connector_id: str
    worker_id: str
    candidate_revision: str | None = None
    verification_status: str | None = None
    checks: tuple[GitHubActionsCheck, ...] = ()
    evidence_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.repository, str) or _REPOSITORY.fullmatch(self.repository) is None:
            raise ValueError("repository must be in owner/name form")
        for field in ("work_unit_id", "run_id", "attempt_id", "connector_id"):
            _identifier(getattr(self, field), field)
        if not isinstance(self.work_unit_digest, str) or _DIGEST.fullmatch(self.work_unit_digest) is None:
            raise ValueError("work_unit_digest must be a lowercase sha256 digest")
        if self.run_state not in RUN_STATES:
            raise ValueError("run_state must be a Product Spine run state")
        if self.attempt_state not in ATTEMPT_STATES:
            raise ValueError("attempt_state must be a Product Spine attempt state")
        object.__setattr__(self, "source_revision", _revision(self.source_revision, "source_revision"))
        _inline(self.worker_id, "worker_id", 256)

        if self.candidate_revision is not None:
            object.__setattr__(
                self,
                "candidate_revision",
                _revision(self.candidate_revision, "candidate_revision"),
            )
        if self.attempt_state in _CANDIDATE_REQUIRED and self.candidate_revision is None:
            raise ValueError("candidate_revision is required once a candidate has been observed")

        if self.verification_status is not None:
            if self.verification_status not in _VERIFICATION_STATUSES:
                raise ValueError("verification_status must be a VerificationResult status")
            if self.attempt_state != "verified":
                raise ValueError("verification_status is only valid for a verified attempt")
        elif self.attempt_state == "verified":
            raise ValueError("verified attempt requires verification_status")

        try:
            checks = tuple(self.checks)
        except TypeError as exc:
            raise ValueError("checks must be iterable") from exc
        if len(checks) > _MAX_CHECKS or any(not isinstance(c, GitHubActionsCheck) for c in checks):
            raise ValueError("checks must contain at most 200 GitHubActionsCheck values")
        ids = [c.check_id for c in checks]
        if len(ids) != len(set(ids)):
            raise ValueError("checks must not contain duplicate check_id values")
        object.__setattr__(self, "checks", tuple(sorted(checks, key=lambda c: c.check_id)))
        if self.evidence_reference is not None:
            _inline(self.evidence_reference, "evidence_reference", 2048)

    @property
    def candidate_state(self) -> str:
        if self.candidate_revision is None:
            return "not_observed"
        if self.attempt_state == "candidate_observed":
            return "observed"
        if self.attempt_state == "normalization_error":
            return "normalization_error"
        if self.attempt_state == "cancelled":
            return "retained_before_cancellation"
        return "normalized"

    @property
    def verification_state(self) -> str:
        if self.attempt_state == "verified":
            return self.verification_status or "error"
        return {
            "verification_requested": "pending",
            "verification_error": "error",
            "cancelled": "cancelled",
        }.get(self.attempt_state, "not_started")

    @property
    def human_decision_state(self) -> str:
        return {
            "decided": "recorded",
            "awaiting_human_decision": "pending",
            "cancelled": "not_applicable",
        }.get(self.run_state, "not_ready")

    def render_markdown(self) -> str:
        candidate = self.candidate_revision or "not available"
        evidence = self.evidence_reference or "not available"
        rows = (
            ("Repository", self.repository),
            ("WorkUnit", self.work_unit_id),
            ("WorkUnit digest", self.work_unit_digest),
            ("Run", self.run_id),
            ("Run state", self.run_state),
            ("Attempt", self.attempt_id),
            ("Attempt state", self.attempt_state),
            ("Base/source SHA", self.source_revision),
            ("Candidate SHA", candidate),
            ("Connector", self.connector_id),
            ("Worker", self.worker_id),
            ("Candidate state", self.candidate_state),
            ("Verification state", self.verification_state),
            ("Human decision state", self.human_decision_state),
            ("Durable evidence reference", evidence),
        )
        lines = ["## IDKMesh run summary", "", "| Field | Value |", "| --- | --- |"]
        lines.extend(f"| {name} | `{value}` |" for name, value in rows)
        lines.extend(["", "### Deterministic checks", ""])
        if self.checks:
            lines.extend(["| Check | Required | Status |", "| --- | --- | --- |"])
            lines.extend(
                f"| `{c.check_id}` | `{'yes' if c.required else 'no'}` | `{c.status}` |"
                for c in self.checks
            )
        else:
            lines.append("_No deterministic checks recorded._")
        lines.extend(
            [
                "",
                "### Authority boundary",
                "",
                "| Capability | This summary grants |",
                "| --- | --- |",
                "| Candidate acceptance | `no` |",
                "| Canonical state write | `no` |",
                "| Git push | `no` |",
                "| Merge | `no` |",
                "",
                "This read-only projection does not dispatch work, accept a candidate, "
                "record a human decision, push Git, or merge.",
            ]
        )
        rendered = "\n".join(lines) + "\n"
        if len(rendered.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("rendered GitHub Actions summary exceeds safety bound")
        return rendered
