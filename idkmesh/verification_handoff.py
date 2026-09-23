"""Prepare immutable verification handoffs without selecting a verifier.

C6-F closes candidate normalization by binding the exact WorkUnit,
ResultManifest, candidate artifact, and required verification policy into a
small provider-neutral handoff.

The handoff is not an EvaluatorPlan and does not choose a verifier. Evaluator
control data remains verifier-owned under Evaluator Sovereignty.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from idkmesh.work_unit_binding import canonical_digest


_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_STRATEGIES = {"all_required", "quorum", "threshold", "custom"}
_FORBIDDEN_RESULT_AUTHORITY_FIELDS = {
    "accepted",
    "verified",
    "verification_result",
    "merge_authorized",
    "integration_authorized",
    "human_decision",
}


class VerificationHandoffError(RuntimeError):
    """Raised when normalized evidence cannot safely enter verification."""


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationHandoffError(f"{field} must be a non-empty string")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise VerificationHandoffError(f"{field} must be an integer >= 1")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationHandoffError(f"{field} must be an integer >= 0")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise VerificationHandoffError(
            f"{field} must be a lowercase sha256 digest"
        )
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationHandoffError(f"{field} must be an object")
    return value


def _unique_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise VerificationHandoffError(f"{field} must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        normalized = _nonempty(item, f"{field}[{index}]")
        if normalized in seen:
            raise VerificationHandoffError(
                f"{field} must not contain duplicate value: {normalized}"
            )
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


@dataclass(frozen=True)
class VerificationHandoff:
    """Immutable coordinator-to-verifier evidence binding.

    This object deliberately contains no verifier identity, EvaluatorPlan,
    recommendation, verdict, acceptance, or integration authority.
    """

    work_unit_id: str
    work_unit_version: int
    work_unit_digest: str
    source_revision: str
    result_manifest_id: str
    result_manifest_digest: str
    attempt: int
    worker_id: str
    candidate_artifact_id: str
    candidate_artifact_digest: str
    required_validator_ids: tuple[str, ...]
    verification_strategy: str
    independent_from_worker: bool
    minimum_independent_verifiers: int
    quorum: int | None = None
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise VerificationHandoffError(
                "unsupported VerificationHandoff schema_version"
            )
        _nonempty(self.work_unit_id, "work_unit_id")
        _positive_int(self.work_unit_version, "work_unit_version")
        _sha256(self.work_unit_digest, "work_unit_digest")
        _nonempty(self.source_revision, "source_revision")
        _nonempty(self.result_manifest_id, "result_manifest_id")
        _sha256(self.result_manifest_digest, "result_manifest_digest")
        _positive_int(self.attempt, "attempt")
        _nonempty(self.worker_id, "worker_id")
        _nonempty(self.candidate_artifact_id, "candidate_artifact_id")
        _sha256(self.candidate_artifact_digest, "candidate_artifact_digest")
        if not self.required_validator_ids:
            raise VerificationHandoffError(
                "required_validator_ids must not be empty"
            )
        if len(set(self.required_validator_ids)) != len(
            self.required_validator_ids
        ):
            raise VerificationHandoffError(
                "required_validator_ids must be unique"
            )
        for index, validator_id in enumerate(self.required_validator_ids):
            _nonempty(
                validator_id,
                f"required_validator_ids[{index}]",
            )
        if self.verification_strategy not in _STRATEGIES:
            raise VerificationHandoffError(
                "unsupported verification_strategy"
            )
        if type(self.independent_from_worker) is not bool:
            raise VerificationHandoffError(
                "independent_from_worker must be boolean"
            )
        _nonnegative_int(
            self.minimum_independent_verifiers,
            "minimum_independent_verifiers",
        )
        if (
            self.independent_from_worker
            and self.minimum_independent_verifiers < 1
        ):
            raise VerificationHandoffError(
                "independent verification requires at least one independent verifier"
            )
        if self.verification_strategy == "quorum":
            if self.quorum is None:
                raise VerificationHandoffError(
                    "quorum strategy requires quorum"
                )
            _positive_int(self.quorum, "quorum")
        elif self.quorum is not None:
            _positive_int(self.quorum, "quorum")

    def evaluator_binding(self) -> dict[str, Any]:
        """Return the exact binding block an EvaluatorPlan must match."""

        return {
            "work_unit_id": self.work_unit_id,
            "work_unit_version": self.work_unit_version,
            "work_unit_digest": self.work_unit_digest,
            "source_revision": self.source_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "work_unit_id": self.work_unit_id,
            "work_unit_version": self.work_unit_version,
            "work_unit_digest": self.work_unit_digest,
            "source_revision": self.source_revision,
            "result_manifest_id": self.result_manifest_id,
            "result_manifest_digest": self.result_manifest_digest,
            "attempt": self.attempt,
            "worker_id": self.worker_id,
            "candidate_artifact_id": self.candidate_artifact_id,
            "candidate_artifact_digest": self.candidate_artifact_digest,
            "required_validator_ids": list(self.required_validator_ids),
            "verification_strategy": self.verification_strategy,
            "independent_from_worker": self.independent_from_worker,
            "minimum_independent_verifiers": self.minimum_independent_verifiers,
        }
        if self.quorum is not None:
            result["quorum"] = self.quorum
        return result


def _required_validator_ids(work_unit: Mapping[str, Any]) -> tuple[str, ...]:
    validators = work_unit.get("validators")
    if not isinstance(validators, list):
        raise VerificationHandoffError(
            "work_unit.validators must be an array"
        )

    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(validators):
        validator = _mapping(
            item,
            f"work_unit.validators[{index}]",
        )
        validator_id = _nonempty(
            validator.get("id"),
            f"work_unit.validators[{index}].id",
        )
        if validator_id in seen:
            raise VerificationHandoffError(
                f"duplicate WorkUnit validator id: {validator_id}"
            )
        seen.add(validator_id)
        if validator.get("required") is True:
            result.append(validator_id)
        elif validator.get("required") is not False:
            raise VerificationHandoffError(
                f"work_unit.validators[{index}].required must be boolean"
            )

    if not result:
        raise VerificationHandoffError(
            "WorkUnit has no required validators; no verification handoff is needed"
        )
    return tuple(result)


def _candidate_artifact(
    result_manifest: Mapping[str, Any],
    *,
    artifact_id: str,
) -> Mapping[str, Any]:
    artifacts = result_manifest.get("produced_artifacts")
    if not isinstance(artifacts, list):
        raise VerificationHandoffError(
            "result_manifest.produced_artifacts must be an array"
        )
    matches = [
        item
        for item in artifacts
        if isinstance(item, Mapping) and item.get("id") == artifact_id
    ]
    if len(matches) != 1:
        raise VerificationHandoffError(
            "candidate artifact id must match exactly one produced artifact"
        )
    return matches[0]


def prepare_verification_handoff(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    *,
    candidate_artifact_id: str | None = None,
) -> VerificationHandoff:
    """Bind normalized result evidence for the verifier-owned next stage."""

    work = _mapping(work_unit, "work_unit")
    result = _mapping(result_manifest, "result_manifest")

    forbidden = sorted(
        _FORBIDDEN_RESULT_AUTHORITY_FIELDS.intersection(result)
    )
    if forbidden:
        raise VerificationHandoffError(
            "ResultManifest contains forbidden authority field(s): "
            + ", ".join(forbidden)
        )

    work_unit_id = _nonempty(work.get("id"), "work_unit.id")
    work_unit_version = _positive_int(
        work.get("version"),
        "work_unit.version",
    )
    observed_work_unit_digest = canonical_digest(work)

    if result.get("work_unit_id") != work_unit_id:
        raise VerificationHandoffError(
            "ResultManifest references a different WorkUnit id"
        )
    if result.get("work_unit_version") != work_unit_version:
        raise VerificationHandoffError(
            "ResultManifest references a different WorkUnit version"
        )

    provenance = _mapping(
        result.get("provenance"),
        "result_manifest.provenance",
    )
    declared_work_unit_digest = _sha256(
        provenance.get("work_unit_digest"),
        "result_manifest.provenance.work_unit_digest",
    )
    if declared_work_unit_digest != observed_work_unit_digest:
        raise VerificationHandoffError(
            "ResultManifest is not bound to the exact WorkUnit content"
        )

    source_revision = _nonempty(
        provenance.get("source_revision"),
        "result_manifest.provenance.source_revision",
    )
    work_provenance = _mapping(
        work.get("provenance"),
        "work_unit.provenance",
    )
    work_source_revision = work_provenance.get("source_revision")
    if (
        work_source_revision is not None
        and _nonempty(
            work_source_revision,
            "work_unit.provenance.source_revision",
        )
        != source_revision
    ):
        raise VerificationHandoffError(
            "ResultManifest source revision differs from WorkUnit provenance"
        )

    request = _mapping(
        result.get("verification_request"),
        "result_manifest.verification_request",
    )
    requested_validator_ids = _unique_strings(
        request.get("expected_validator_ids"),
        "result_manifest.verification_request.expected_validator_ids",
    )
    required_validator_ids = _required_validator_ids(work)
    missing = sorted(
        set(required_validator_ids) - set(requested_validator_ids)
    )
    if missing:
        raise VerificationHandoffError(
            "ResultManifest verification request omits required validator(s): "
            + ", ".join(missing)
        )

    evidence_artifact_ids = _unique_strings(
        request.get("evidence_artifact_ids"),
        "result_manifest.verification_request.evidence_artifact_ids",
    )
    if candidate_artifact_id is None:
        if len(evidence_artifact_ids) != 1:
            raise VerificationHandoffError(
                "candidate_artifact_id is required when verification request "
                "contains zero or multiple evidence artifacts"
            )
        selected_artifact_id = evidence_artifact_ids[0]
    else:
        selected_artifact_id = _nonempty(
            candidate_artifact_id,
            "candidate_artifact_id",
        )
        if selected_artifact_id not in evidence_artifact_ids:
            raise VerificationHandoffError(
                "candidate_artifact_id is not requested as verification evidence"
            )

    artifact = _candidate_artifact(
        result,
        artifact_id=selected_artifact_id,
    )
    candidate_artifact_digest = _sha256(
        artifact.get("digest"),
        "candidate artifact digest",
    )

    policy = _mapping(
        work.get("verification_policy"),
        "work_unit.verification_policy",
    )
    strategy = _nonempty(
        policy.get("strategy"),
        "work_unit.verification_policy.strategy",
    )
    if strategy not in _STRATEGIES:
        raise VerificationHandoffError(
            "unsupported WorkUnit verification strategy"
        )
    independent = policy.get("independent_from_worker")
    if type(independent) is not bool:
        raise VerificationHandoffError(
            "work_unit.verification_policy.independent_from_worker must be boolean"
        )
    minimum = _nonnegative_int(
        policy.get("minimum_independent_verifiers"),
        "work_unit.verification_policy.minimum_independent_verifiers",
    )
    quorum = policy.get("quorum")
    if strategy == "quorum":
        quorum = _positive_int(
            quorum,
            "work_unit.verification_policy.quorum",
        )
    elif quorum is not None:
        quorum = _positive_int(
            quorum,
            "work_unit.verification_policy.quorum",
        )

    worker = _mapping(
        result.get("worker"),
        "result_manifest.worker",
    )

    return VerificationHandoff(
        work_unit_id=work_unit_id,
        work_unit_version=work_unit_version,
        work_unit_digest=observed_work_unit_digest,
        source_revision=source_revision,
        result_manifest_id=_nonempty(
            result.get("id"),
            "result_manifest.id",
        ),
        result_manifest_digest=canonical_digest(result),
        attempt=_positive_int(
            result.get("attempt"),
            "result_manifest.attempt",
        ),
        worker_id=_nonempty(
            worker.get("id"),
            "result_manifest.worker.id",
        ),
        candidate_artifact_id=selected_artifact_id,
        candidate_artifact_digest=candidate_artifact_digest,
        required_validator_ids=required_validator_ids,
        verification_strategy=strategy,
        independent_from_worker=independent,
        minimum_independent_verifiers=minimum,
        quorum=quorum,
    )
