"""Judge a recovery drill against the profile's declared RPO and RTO (E6, #673).

The enterprise control profile *declares* ``reliability.rpo_minutes`` and
``reliability.rto_minutes``; the profile itself says its controls are
"declared_not_observed". Nothing compared a measured recovery with those
objectives, so an RPO/RTO was a number someone wrote down. This module is the
comparison, and nothing more: a pure function from a profile and one recorded
drill to PASS, FAIL or UNKNOWN with value-free reason codes.

It does not run a drill, back anything up, restore anything or read a clock. The
drill record is produced by an operator exercise (for example the local SQLite
restore drill in ``docs/operations/API_STORAGE_RESTORE_DRILL_V0_1.md``) and
carries only epochs, one boolean and a digest of the retained drill report.

Measurements, in whole seconds:

* ``data_loss_seconds`` -- how far behind the newest acknowledged write the
  restored state is: ``max(0, last_acknowledged_write - last_recovered_write)``.
  It is compared with ``rpo_minutes * 60``. Idle time before the failure is not
  data loss, so it is not counted;
* ``recovery_seconds`` -- ``service_restored_at - failure_injected_at``, compared
  with ``rto_minutes * 60``.

Both objectives are inclusive: meeting the objective exactly passes.

Outcomes follow the E9 vocabulary and are deliberately asymmetric:

* ``FAIL`` -- a measured objective was exceeded, or the restored state was not
  integrity-verified. This is evidence of a problem;
* ``PASS`` -- the drill is well-formed, matches the profile, is fresh enough when
  a maximum age is given, and met every objective. It is evidence about that one
  drill, not a guarantee about the next recovery;
* ``UNKNOWN`` -- there is nothing trustworthy to judge: no drill, a malformed or
  mismatched record, a stale or future-dated drill, or an invalid profile. A
  missing drill is never a pass.

Results carry identifiers, counts and reason codes only; untrusted text is never
echoed. The evaluation grants no runtime authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from idkmesh.enterprise_profile import (
    EnterpriseProfileError,
    validate_enterprise_profile,
)

DRILL_VERSION = "0.1"
DRILL_KIND = "idkmesh-enterprise-recovery-drill"
EVALUATION_KIND = "idkmesh-enterprise-recovery-drill-evaluation"
OUTCOMES = ("PASS", "FAIL", "UNKNOWN")

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIELDS = frozenset(
    {
        "kind",
        "schema_version",
        "drill_id",
        "profile_id",
        "last_acknowledged_write_epoch",
        "last_recovered_write_epoch",
        "failure_injected_at_epoch",
        "service_restored_at_epoch",
        "integrity_verified",
        "evidence_digest",
    }
)
_EPOCH_FIELDS = (
    "last_acknowledged_write_epoch",
    "last_recovered_write_epoch",
    "failure_injected_at_epoch",
    "service_restored_at_epoch",
)
# A generous ceiling that still rejects nonsense such as year 10^9.
_MAX_EPOCH = 4_102_444_800  # 2100-01-01T00:00:00Z


class RecoveryDrillError(ValueError):
    """A drill record is not acceptable; the message carries no input text."""

    def __init__(self, code: str, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


def _safe_id(value: object) -> str:
    """Return the value only when it is a well-formed identifier."""

    if isinstance(value, str) and _ID_RE.fullmatch(value):
        return value
    return "<invalid>"


def _epoch(value: object, field: str) -> int:
    if type(value) is not int or value < 0 or value > _MAX_EPOCH:
        raise RecoveryDrillError("invalid_epoch", field)
    return value


@dataclass(frozen=True, slots=True)
class RecoveryDrill:
    """One recorded recovery exercise. Credential-free by construction."""

    drill_id: str
    profile_id: str
    last_acknowledged_write_epoch: int
    last_recovered_write_epoch: int
    failure_injected_at_epoch: int
    service_restored_at_epoch: int
    integrity_verified: bool
    evidence_digest: str

    def __post_init__(self) -> None:
        for field in ("drill_id", "profile_id"):
            if _safe_id(getattr(self, field)) == "<invalid>":
                raise RecoveryDrillError("invalid_identifier", field)
        for field in _EPOCH_FIELDS:
            _epoch(getattr(self, field), field)
        if type(self.integrity_verified) is not bool:
            raise RecoveryDrillError("invalid_boolean", "integrity_verified")
        if not (
            isinstance(self.evidence_digest, str)
            and _DIGEST_RE.fullmatch(self.evidence_digest)
        ):
            raise RecoveryDrillError("invalid_digest", "evidence_digest")
        # Time cannot run backwards inside one drill.
        if self.last_acknowledged_write_epoch > self.failure_injected_at_epoch:
            raise RecoveryDrillError(
                "acknowledged_write_after_failure", "last_acknowledged_write_epoch"
            )
        if self.last_recovered_write_epoch > self.failure_injected_at_epoch:
            raise RecoveryDrillError(
                "recovered_write_after_failure", "last_recovered_write_epoch"
            )
        if self.service_restored_at_epoch < self.failure_injected_at_epoch:
            raise RecoveryDrillError(
                "restored_before_failure", "service_restored_at_epoch"
            )

    @property
    def data_loss_seconds(self) -> int:
        return max(
            0, self.last_acknowledged_write_epoch - self.last_recovered_write_epoch
        )

    @property
    def recovery_seconds(self) -> int:
        return self.service_restored_at_epoch - self.failure_injected_at_epoch

    @classmethod
    def from_dict(cls, value: object) -> "RecoveryDrill":
        """Strictly parse a drill record: exact fields, no coercion."""

        if not isinstance(value, Mapping):
            raise RecoveryDrillError("invalid_record", "$")
        keys = set(value)
        if any(not isinstance(key, str) for key in keys):
            raise RecoveryDrillError("invalid_record", "$")
        if keys != _FIELDS:
            raise RecoveryDrillError("invalid_fields", "$")
        if value["kind"] != DRILL_KIND:
            raise RecoveryDrillError("invalid_kind", "kind")
        if value["schema_version"] != DRILL_VERSION:
            raise RecoveryDrillError("invalid_version", "schema_version")
        return cls(
            drill_id=value["drill_id"],
            profile_id=value["profile_id"],
            last_acknowledged_write_epoch=value["last_acknowledged_write_epoch"],
            last_recovered_write_epoch=value["last_recovered_write_epoch"],
            failure_injected_at_epoch=value["failure_injected_at_epoch"],
            service_restored_at_epoch=value["service_restored_at_epoch"],
            integrity_verified=value["integrity_verified"],
            evidence_digest=value["evidence_digest"],
        )


@dataclass(frozen=True, slots=True)
class RecoveryDrillEvaluation:
    outcome: str
    code: str
    message: str
    profile_id: str
    drill_id: str
    objectives: Mapping[str, int | None]
    measured: Mapping[str, int | None]
    checks: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError("invalid outcome")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": EVALUATION_KIND,
            "schema_version": DRILL_VERSION,
            "outcome": self.outcome,
            "code": self.code,
            "message": self.message,
            "profile_id": self.profile_id,
            "drill_id": self.drill_id,
            "objectives": dict(self.objectives),
            "measured": dict(self.measured),
            "checks": dict(self.checks),
            "authority": {
                "runs_drill": False,
                "restores_data": False,
                "grants_runtime_authority": False,
            },
        }


_NO_MEASUREMENT: Mapping[str, int | None] = {
    "data_loss_seconds": None,
    "recovery_seconds": None,
}
_NO_CHECKS: Mapping[str, str] = {
    "integrity": "unknown",
    "rpo": "unknown",
    "rto": "unknown",
}


def evaluate_recovery_drill(
    profile: Any,
    drill: Any,
    *,
    evaluated_at_epoch: int,
    max_drill_age_seconds: int | None = None,
) -> RecoveryDrillEvaluation:
    """Compare one recorded drill with the profile's RPO and RTO.

    ``drill`` may be a :class:`RecoveryDrill`, a mapping that
    :meth:`RecoveryDrill.from_dict` accepts, or ``None`` (no evidence).
    ``max_drill_age_seconds`` bounds how old the drill may be, measured from
    ``service_restored_at_epoch``; ``None`` skips the freshness check. The
    profile declares no drill interval, so freshness is the caller's policy.
    """

    if type(evaluated_at_epoch) is not int or not 0 <= evaluated_at_epoch <= _MAX_EPOCH:
        raise ValueError("evaluated_at_epoch must be a non-negative integer epoch")
    if max_drill_age_seconds is not None and (
        type(max_drill_age_seconds) is not int or max_drill_age_seconds < 1
    ):
        raise ValueError("max_drill_age_seconds must be a positive integer or None")

    def unknown(code: str, message: str, *, profile_id: str = "<invalid>",
                drill_id: str = "<invalid>", objectives=None) -> RecoveryDrillEvaluation:
        return RecoveryDrillEvaluation(
            "UNKNOWN", code, message, profile_id, drill_id,
            objectives or {"rpo_seconds": None, "rto_seconds": None},
            _NO_MEASUREMENT, _NO_CHECKS,
        )

    try:
        validate_enterprise_profile(profile)
    except EnterpriseProfileError as exc:
        return unknown(
            "invalid_profile",
            f"enterprise profile failed validation: {exc.code}",
        )
    profile_id = _safe_id(profile["profile_id"])
    reliability = profile["reliability"]
    objectives = {
        "rpo_seconds": reliability["rpo_minutes"] * 60,
        "rto_seconds": reliability["rto_minutes"] * 60,
    }

    if drill is None:
        return unknown(
            "no_drill_evidence",
            "no recovery drill was recorded; nothing was measured",
            profile_id=profile_id,
            objectives=objectives,
        )
    if not isinstance(drill, RecoveryDrill):
        try:
            drill = RecoveryDrill.from_dict(drill)
        except RecoveryDrillError as exc:
            return unknown(
                "invalid_drill",
                f"recovery drill record was rejected: {exc.code} ({exc.field})",
                profile_id=profile_id,
                objectives=objectives,
            )
    if drill.profile_id != profile["profile_id"]:
        return unknown(
            "profile_mismatch",
            "the drill was recorded for a different profile",
            profile_id=profile_id,
            drill_id=drill.drill_id,
            objectives=objectives,
        )
    if evaluated_at_epoch < drill.service_restored_at_epoch:
        return unknown(
            "drill_from_future",
            "the drill finished after the evaluation time",
            profile_id=profile_id,
            drill_id=drill.drill_id,
            objectives=objectives,
        )
    if (
        max_drill_age_seconds is not None
        and evaluated_at_epoch - drill.service_restored_at_epoch > max_drill_age_seconds
    ):
        return unknown(
            "stale_drill",
            "the drill is older than the allowed age; run a new one",
            profile_id=profile_id,
            drill_id=drill.drill_id,
            objectives=objectives,
        )

    measured = {
        "data_loss_seconds": drill.data_loss_seconds,
        "recovery_seconds": drill.recovery_seconds,
    }
    checks = {
        "integrity": "pass" if drill.integrity_verified else "fail",
        "rpo": "pass" if drill.data_loss_seconds <= objectives["rpo_seconds"] else "fail",
        "rto": "pass" if drill.recovery_seconds <= objectives["rto_seconds"] else "fail",
    }
    failure_codes = (
        ("integrity", "integrity_not_verified",
         "the restored state was not verified against the retained records"),
        ("rpo", "rpo_exceeded", "measured data loss exceeds the declared RPO"),
        ("rto", "rto_exceeded", "measured recovery time exceeds the declared RTO"),
    )
    for name, code, message in failure_codes:
        if checks[name] == "fail":
            return RecoveryDrillEvaluation(
                "FAIL", code, message, profile_id, drill.drill_id,
                objectives, measured, checks,
            )
    return RecoveryDrillEvaluation(
        "PASS",
        "objectives_met",
        "the recorded drill met the declared RPO and RTO",
        profile_id,
        drill.drill_id,
        objectives,
        measured,
        checks,
    )
