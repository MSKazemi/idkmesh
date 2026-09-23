"""Build canonical ResultManifest v0.1 objects from normalized candidates.

This module is the C6 provider-erasure boundary. It consumes:
- an exact WorkUnit + WorkUnitSourceBinding;
- one provider-neutral CandidateReference;
- normalized worker/run metadata.

It emits a schema-shaped ResultManifest dictionary. It does not execute
verification, interpret validator outcomes, or grant merge/integration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    CandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.work_unit_binding import (
    WorkUnitSourceBinding,
    canonical_digest,
    validate_work_unit_source_binding,
)


_MANIFEST_ID_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{2,127}\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_WORKER_TYPES = {"human", "agent", "system", "hybrid"}
_STATUSES = {"succeeded", "failed", "error", "timeout", "cancelled"}
_LOG_TYPES = {"stdout", "stderr", "trace", "tool_calls", "other"}
_CONFIDENCE_MEANINGS = {
    "probability_of_success",
    "subjective",
    "uncalibrated",
}
_REFERENCE_MEDIA_TYPE = "application/vnd.idkmesh.candidate-reference+json"
_REFERENCE_EXTENSION_KEY = "org.idkmesh.candidate_reference"
_NORMALIZATION_EXTENSION_KEY = "org.idkmesh.normalization"


class ResultManifestBuildError(RuntimeError):
    """Raised when normalized inputs cannot safely form ResultManifest v0.1."""


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultManifestBuildError(f"{field} must be a non-empty string")
    return value


def _optional_nonempty(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _nonempty(value, field)


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ResultManifestBuildError(
            f"{field} must be a lowercase sha256 content digest"
        )
    return value


def _nonnegative_number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultManifestBuildError(f"{field} must be a number")
    if not math.isfinite(float(value)) or value < 0:
        raise ResultManifestBuildError(f"{field} must be finite and >= 0")
    return value


def _utc_timestamp(value: datetime, field: str) -> str:
    if not isinstance(value, datetime):
        raise ResultManifestBuildError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResultManifestBuildError(f"{field} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        text = normalized.isoformat(timespec="microseconds")
    else:
        text = normalized.isoformat(timespec="seconds")
    return text.replace("+00:00", "Z")


@dataclass(frozen=True)
class ModelIdentity:
    """Optional normalized model identity for one worker attempt."""

    name: str
    provider: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"name": _nonempty(self.name, "model.name")}
        provider = _optional_nonempty(self.provider, "model.provider")
        version = _optional_nonempty(self.version, "model.version")
        if provider is not None:
            result["provider"] = provider
        if version is not None:
            result["version"] = version
        return result


@dataclass(frozen=True)
class WorkerIdentity:
    """Provider-neutral worker provenance retained in ResultManifest."""

    id: str
    type: str
    adapter: str
    adapter_version: str | None = None
    model: ModelIdentity | None = None

    def to_dict(self) -> dict[str, Any]:
        worker_id = _nonempty(self.id, "worker.id")
        if self.type not in _WORKER_TYPES:
            raise ResultManifestBuildError(
                "worker.type must be one of: " + ", ".join(sorted(_WORKER_TYPES))
            )
        result: dict[str, Any] = {
            "id": worker_id,
            "type": self.type,
            "adapter": _nonempty(self.adapter, "worker.adapter"),
        }
        adapter_version = _optional_nonempty(
            self.adapter_version,
            "worker.adapter_version",
        )
        if adapter_version is not None:
            result["adapter_version"] = adapter_version
        if self.model is not None:
            if not isinstance(self.model, ModelIdentity):
                raise ResultManifestBuildError(
                    "worker.model must be ModelIdentity when supplied"
                )
            result["model"] = self.model.to_dict()
        return result


@dataclass(frozen=True)
class LogReference:
    """Bounded log reference; log bodies are never inlined here."""

    type: str
    locator: str
    digest: str | None = None

    def to_dict(self) -> dict[str, str]:
        if self.type not in _LOG_TYPES:
            raise ResultManifestBuildError(
                "log.type must be one of: " + ", ".join(sorted(_LOG_TYPES))
            )
        result = {
            "type": self.type,
            "locator": _nonempty(self.locator, "log.locator"),
        }
        if self.digest is not None:
            result["digest"] = _sha256(self.digest, "log.digest")
        return result


@dataclass(frozen=True)
class ResourceUsage:
    """Normalized bounded resource measurements."""

    wall_seconds: int | float
    cpu_seconds: int | float | None = None
    max_rss_mb: int | float | None = None
    compute_units: int | float | None = None
    human_minutes: int | float | None = None
    tokens: int | None = None

    def to_dict(self) -> dict[str, int | float]:
        result: dict[str, int | float] = {
            "wall_seconds": _nonnegative_number(
                self.wall_seconds,
                "resources.wall_seconds",
            )
        }
        for field in (
            "cpu_seconds",
            "max_rss_mb",
            "compute_units",
            "human_minutes",
        ):
            value = getattr(self, field)
            if value is not None:
                result[field] = _nonnegative_number(
                    value,
                    f"resources.{field}",
                )
        if self.tokens is not None:
            if (
                isinstance(self.tokens, bool)
                or not isinstance(self.tokens, int)
                or self.tokens < 0
            ):
                raise ResultManifestBuildError(
                    "resources.tokens must be an integer >= 0"
                )
            result["tokens"] = self.tokens
        return result


@dataclass(frozen=True)
class ExecutionEnvironment:
    """Portable environment metadata only; no secrets or provider payloads."""

    platform: str | None = None
    python: str | None = None
    container_image: str | None = None
    tool_versions: Mapping[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in ("platform", "python", "container_image"):
            value = _optional_nonempty(getattr(self, field), f"environment.{field}")
            if value is not None:
                result[field] = value

        if self.tool_versions is not None:
            if not isinstance(self.tool_versions, Mapping):
                raise ResultManifestBuildError(
                    "environment.tool_versions must be an object"
                )
            normalized: dict[str, str] = {}
            for key, value in self.tool_versions.items():
                normalized[_nonempty(key, "environment.tool_versions key")] = _nonempty(
                    value,
                    f"environment.tool_versions[{key!r}]",
                )
            result["tool_versions"] = dict(sorted(normalized.items()))
        return result


@dataclass(frozen=True)
class SelfReport:
    """Worker/provider self-report kept explicitly separate from verification."""

    summary: str
    claims: tuple[str, ...] = ()
    confidence_value: float | None = None
    confidence_meaning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if not isinstance(self.summary, str):
            raise ResultManifestBuildError("self_report.summary must be a string")
        claims: list[str] = []
        for index, claim in enumerate(self.claims):
            if not isinstance(claim, str):
                raise ResultManifestBuildError(
                    f"self_report.claims[{index}] must be a string"
                )
            claims.append(claim)

        result: dict[str, Any] = {
            "summary": self.summary,
            "claims": claims,
        }

        supplied = (
            self.confidence_value is not None,
            self.confidence_meaning is not None,
        )
        if supplied == (True, False) or supplied == (False, True):
            raise ResultManifestBuildError(
                "self_report confidence value and meaning must be supplied together"
            )
        if self.confidence_value is not None:
            if (
                isinstance(self.confidence_value, bool)
                or not isinstance(self.confidence_value, (int, float))
                or not math.isfinite(float(self.confidence_value))
                or not 0 <= self.confidence_value <= 1
            ):
                raise ResultManifestBuildError(
                    "self_report.confidence.value must be finite and in [0, 1]"
                )
            if self.confidence_meaning not in _CONFIDENCE_MEANINGS:
                raise ResultManifestBuildError(
                    "unsupported self_report confidence meaning"
                )
            result["confidence"] = {
                "value": self.confidence_value,
                "meaning": self.confidence_meaning,
            }
        return result


def _candidate_locator(candidate: CandidateReference) -> str:
    if isinstance(candidate, GitHubPullRequestCandidateReference):
        return f"{candidate.canonical_url}#idkmesh-head={candidate.head_sha}"
    if isinstance(candidate, ArtifactBundleCandidateReference):
        return candidate.locator
    raise ResultManifestBuildError("unsupported CandidateReference implementation")


def _validator_ids(work_unit: Mapping[str, Any]) -> list[str]:
    validators = work_unit.get("validators")
    if not isinstance(validators, list) or not validators:
        raise ResultManifestBuildError(
            "work_unit.validators must be a non-empty array"
        )

    result: list[str] = []
    seen: set[str] = set()
    for index, validator in enumerate(validators):
        if not isinstance(validator, Mapping):
            raise ResultManifestBuildError(
                f"work_unit.validators[{index}] must be an object"
            )
        validator_id = _nonempty(
            validator.get("id"),
            f"work_unit.validators[{index}].id",
        )
        if validator_id in seen:
            raise ResultManifestBuildError(
                f"duplicate WorkUnit validator id: {validator_id}"
            )
        seen.add(validator_id)
        result.append(validator_id)
    return result


def _metrics(values: Mapping[str, Any] | None) -> dict[str, int | float | None]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ResultManifestBuildError("metrics must be an object")

    result: dict[str, int | float | None] = {}
    for key, value in values.items():
        metric = _nonempty(key, "metrics key")
        if value is None:
            result[metric] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ResultManifestBuildError(
                f"metrics[{metric!r}] must be numeric or null"
            )
        if not math.isfinite(float(value)):
            raise ResultManifestBuildError(
                f"metrics[{metric!r}] must be finite"
            )
        result[metric] = value
    return dict(sorted(result.items()))


def build_result_manifest(
    work_unit: dict[str, Any],
    binding: WorkUnitSourceBinding,
    candidate: CandidateReference,
    *,
    manifest_id: str,
    attempt: int,
    worker: WorkerIdentity,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    resources: ResourceUsage,
    self_report: SelfReport | None = None,
    self_report_source: str = "absent",
    logs: tuple[LogReference, ...] = (),
    metrics: Mapping[str, Any] | None = None,
    environment: ExecutionEnvironment | None = None,
    worker_config_digest: str | None = None,
    artifact_id: str = "candidate",
    verification_notes: str | None = None,
) -> dict[str, Any]:
    """Build a provider-neutral ResultManifest v0.1 without verification authority."""

    if not isinstance(binding, WorkUnitSourceBinding):
        raise ResultManifestBuildError(
            "binding must be a WorkUnitSourceBinding"
        )
    try:
        validate_work_unit_source_binding(
            work_unit,
            binding,
            source_revision=binding.source_revision,
        )
    except Exception as exc:
        raise ResultManifestBuildError(
            "WorkUnit/source binding validation failed"
        ) from exc

    if not isinstance(manifest_id, str) or _MANIFEST_ID_RE.fullmatch(manifest_id) is None:
        raise ResultManifestBuildError(
            "manifest_id must satisfy ResultManifest v0.1 id syntax"
        )
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ResultManifestBuildError("attempt must be an integer >= 1")
    if not isinstance(worker, WorkerIdentity):
        raise ResultManifestBuildError("worker must be WorkerIdentity")
    if status not in _STATUSES:
        raise ResultManifestBuildError(
            "status must be one of: " + ", ".join(sorted(_STATUSES))
        )
    if not isinstance(resources, ResourceUsage):
        raise ResultManifestBuildError("resources must be ResourceUsage")

    started = _utc_timestamp(started_at, "started_at")
    finished = _utc_timestamp(finished_at, "finished_at")
    if finished_at.astimezone(timezone.utc) < started_at.astimezone(timezone.utc):
        raise ResultManifestBuildError(
            "finished_at must not be earlier than started_at"
        )

    if not isinstance(
        candidate,
        (GitHubPullRequestCandidateReference, ArtifactBundleCandidateReference),
    ):
        raise ResultManifestBuildError(
            "candidate must be CandidateReference v0.1"
        )

    artifact = _nonempty(artifact_id, "artifact_id")
    reference = candidate.to_dict()
    reference_digest = canonical_digest(reference)

    normalized_self_report: SelfReport
    if self_report is None:
        if self_report_source != "absent":
            raise ResultManifestBuildError(
                "self_report_source must be absent when self_report is omitted"
            )
        normalized_self_report = SelfReport(
            summary="No worker-authored self-report was supplied during normalization.",
            claims=(),
        )
    else:
        if not isinstance(self_report, SelfReport):
            raise ResultManifestBuildError(
                "self_report must be SelfReport when supplied"
            )
        if self_report_source not in {"worker", "provider", "normalizer"}:
            raise ResultManifestBuildError(
                "self_report_source must be worker, provider, or normalizer"
            )
        normalized_self_report = self_report

    normalized_logs: list[dict[str, str]] = []
    for index, log in enumerate(logs):
        if not isinstance(log, LogReference):
            raise ResultManifestBuildError(
                f"logs[{index}] must be LogReference"
            )
        normalized_logs.append(log.to_dict())

    if environment is None:
        normalized_environment: dict[str, Any] = {}
    elif isinstance(environment, ExecutionEnvironment):
        normalized_environment = environment.to_dict()
    else:
        raise ResultManifestBuildError(
            "environment must be ExecutionEnvironment when supplied"
        )

    provenance: dict[str, Any] = {
        "work_unit_digest": binding.work_unit_digest,
        "source_revision": binding.source_revision,
        "environment": normalized_environment,
    }
    if worker_config_digest is not None:
        provenance["worker_config_digest"] = _sha256(
            worker_config_digest,
            "worker_config_digest",
        )

    verification_request: dict[str, Any] = {
        "expected_validator_ids": _validator_ids(work_unit),
        "evidence_artifact_ids": [artifact],
    }
    if verification_notes is not None:
        if not isinstance(verification_notes, str):
            raise ResultManifestBuildError(
                "verification_notes must be a string"
            )
        verification_request["notes"] = verification_notes

    return {
        "schema_version": "0.1",
        "id": manifest_id,
        "work_unit_id": binding.work_unit_id,
        "work_unit_version": binding.work_unit_version,
        "attempt": attempt,
        "worker": worker.to_dict(),
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "produced_artifacts": [
            {
                "id": artifact,
                "type": "other",
                "locator": _candidate_locator(candidate),
                "digest": reference_digest,
                "media_type": _REFERENCE_MEDIA_TYPE,
                "description": (
                    "Normalized CandidateReference v0.1 identity. The SHA-256 "
                    "digest binds the reference envelope; it is not a verifier verdict."
                ),
            }
        ],
        "logs": normalized_logs,
        "metrics": _metrics(metrics),
        "resources": resources.to_dict(),
        "self_report": normalized_self_report.to_dict(),
        "provenance": provenance,
        "verification_request": verification_request,
        "extensions": {
            _REFERENCE_EXTENSION_KEY: {
                "reference": reference,
                "reference_digest": reference_digest,
                "digest_semantics": "candidate_reference_envelope",
            },
            _NORMALIZATION_EXTENSION_KEY: {
                "profile": "c6-result-manifest-v0.1",
                "self_report_source": self_report_source,
            },
        },
    }
