"""Protocol-neutral worker adapters and canonical result normalization.

The coordinator in this module knows only the :class:`WorkerAdapter` protocol.
Local execution and an A2A-style lifecycle therefore cross the same boundary.
Adapters may report execution completion, but only the separate verifier below
may produce verification evidence; neither component can integrate a change.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping, Protocol

from interop.bindings import (
    BindingError,
    canonical_digest,
    canonical_json,
    from_a2a_send_message,
    normalize_external_completion,
    to_a2a_send_message,
)


@dataclass(frozen=True)
class CandidateArtifact:
    """One immutable artifact returned by a worker adapter."""

    id: str
    type: str
    locator: str
    content: bytes
    media_type: str = "application/octet-stream"


@dataclass(frozen=True)
class AdapterExecution:
    """Transport-neutral worker completion before canonical normalization."""

    protocol: str
    protocol_state: str
    execution_status: str
    acceptance_status: str
    work_unit_digest: str
    artifacts: tuple[CandidateArtifact, ...]
    lifecycle: tuple[str, ...]
    transport_digest: str | None = None
    stdout: bytes = b""
    stderr: bytes = b""


@dataclass(frozen=True)
class RunContext:
    source_revision: str
    started_at: str
    finished_at: str
    wall_seconds: float
    attempt: int = 1


@dataclass(frozen=True)
class VerificationContext:
    source_revision: str
    started_at: str
    finished_at: str
    wall_seconds: float
    verifier_id: str = "interop-independent-verifier"


@dataclass(frozen=True)
class ResultBundle:
    """Canonical manifest plus the immutable bytes it references."""

    result_manifest: dict[str, Any]
    artifact_bytes: Mapping[str, bytes]


class WorkerAdapter(Protocol):
    """The complete coordinator-facing worker interface."""

    worker_id: str
    adapter_id: str
    adapter_version: str

    def execute(self, work_unit: dict[str, Any]) -> AdapterExecution: ...


ArtifactHandler = Callable[[dict[str, Any]], tuple[CandidateArtifact, ...]]


class LocalAdapter:
    """Direct in-process adapter for a configured, side-effect-free handler."""

    worker_id = "local-mock-worker"
    adapter_id = "local-direct"
    adapter_version = "0.1"

    def __init__(self, handler: ArtifactHandler) -> None:
        self._handler = handler

    def execute(self, work_unit: dict[str, Any]) -> AdapterExecution:
        isolated = copy.deepcopy(work_unit)
        artifacts = self._handler(isolated)
        return AdapterExecution(
            protocol="local",
            protocol_state="completed",
            execution_status="succeeded",
            acceptance_status="pending_verification",
            work_unit_digest=canonical_digest(isolated),
            artifacts=artifacts,
            lifecycle=("submitted", "running", "completed"),
        )


class A2AMockAdapter:
    """Faithful transport mock using the canonical A2A binding round trip."""

    worker_id = "a2a-mock-worker"
    adapter_id = "a2a-send-message-mock"
    adapter_version = "0.1"

    def __init__(self, handler: ArtifactHandler) -> None:
        self._handler = handler

    def execute(self, work_unit: dict[str, Any]) -> AdapterExecution:
        envelope = to_a2a_send_message(copy.deepcopy(work_unit))
        wire_bytes = canonical_json(envelope).encode("utf-8")
        decoded_envelope = json.loads(wire_bytes)
        reconstructed = from_a2a_send_message(decoded_envelope)
        artifacts = self._handler(copy.deepcopy(reconstructed))
        completion = normalize_external_completion("a2a", "TASK_STATE_COMPLETED")
        return AdapterExecution(
            protocol="a2a",
            protocol_state="TASK_STATE_COMPLETED",
            execution_status=completion["execution_status"],
            acceptance_status=completion["acceptance_status"],
            work_unit_digest=canonical_digest(reconstructed),
            artifacts=artifacts,
            lifecycle=("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_COMPLETED"),
            transport_digest=canonical_digest(decoded_envelope),
        )


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise BindingError(f"{name} must be a non-empty string")
    return value


def _require_run_context(context: RunContext) -> None:
    _require_text(context.source_revision, "source_revision")
    _require_text(context.started_at, "started_at")
    _require_text(context.finished_at, "finished_at")
    if context.attempt < 1:
        raise BindingError("attempt must be positive")
    if context.wall_seconds < 0:
        raise BindingError("wall_seconds must be non-negative")


def _artifact_manifest(artifact: CandidateArtifact) -> dict[str, Any]:
    _require_text(artifact.id, "artifact id")
    _require_text(artifact.type, "artifact type")
    _require_text(artifact.locator, "artifact locator")
    if not isinstance(artifact.content, bytes):
        raise BindingError("artifact content must be bytes")
    return {
        "id": artifact.id,
        "type": artifact.type,
        "locator": artifact.locator,
        "digest": canonical_digest_bytes(artifact.content),
        "media_type": artifact.media_type,
    }


def canonical_digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def run_with_adapter(
    adapter: WorkerAdapter,
    work_unit: dict[str, Any],
    context: RunContext,
) -> ResultBundle:
    """Execute any adapter through one coordinator path and normalize its claim."""

    _require_run_context(context)
    _require_text(work_unit.get("id"), "Work Unit id")
    _require_text(work_unit.get("objective"), "Work Unit objective")
    if not isinstance(work_unit.get("version"), int) or work_unit["version"] < 1:
        raise BindingError("Work Unit version must be a positive integer")
    wall_budget = work_unit.get("budget", {}).get("wall_seconds")
    if isinstance(wall_budget, (int, float)) and context.wall_seconds > wall_budget:
        raise BindingError("adapter execution exceeded the Work Unit wall budget")
    expected_digest = canonical_digest(work_unit)
    execution = adapter.execute(copy.deepcopy(work_unit))
    if execution.work_unit_digest != expected_digest:
        raise BindingError("adapter completion is bound to a different Work Unit")
    if execution.acceptance_status != "pending_verification":
        raise BindingError("worker adapter attempted to claim acceptance")
    if execution.execution_status not in {"succeeded", "not_succeeded"}:
        raise BindingError("unsupported adapter execution status")
    if not execution.artifacts:
        raise BindingError("adapter returned no candidate artifacts")

    artifact_entries = [_artifact_manifest(item) for item in execution.artifacts]
    artifact_ids = [item["id"] for item in artifact_entries]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise BindingError("adapter returned duplicate artifact ids")

    adapter_binding = {
        "adapter": adapter.adapter_id,
        "adapter_version": adapter.adapter_version,
        "work_unit_digest": expected_digest,
    }
    result_id_suffix = canonical_digest(adapter_binding).split(":", 1)[1][:24]
    expected_validator_ids = sorted(
        item["id"] for item in work_unit.get("validators", []) if item.get("required") is True
    )
    result_manifest = {
        "schema_version": "0.1",
        "id": f"interop-result/{result_id_suffix}/attempt-{context.attempt}",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": context.attempt,
        "worker": {
            "id": adapter.worker_id,
            "type": "system",
            "adapter": adapter.adapter_id,
            "adapter_version": adapter.adapter_version,
        },
        "status": "succeeded" if execution.execution_status == "succeeded" else "failed",
        "started_at": context.started_at,
        "finished_at": context.finished_at,
        "produced_artifacts": artifact_entries,
        "logs": [
            {
                "type": "stdout",
                "locator": f"memory://{result_id_suffix}/stdout",
                "digest": canonical_digest_bytes(execution.stdout),
            },
            {
                "type": "stderr",
                "locator": f"memory://{result_id_suffix}/stderr",
                "digest": canonical_digest_bytes(execution.stderr),
            },
        ],
        "metrics": {"artifact_count": len(artifact_entries)},
        "resources": {"wall_seconds": context.wall_seconds},
        "self_report": {
            "summary": f"{adapter.adapter_id} reported {execution.execution_status}",
            "claims": ["external_or_local_execution_completed"],
        },
        "provenance": {
            "work_unit_digest": expected_digest,
            "source_revision": context.source_revision,
            "worker_config_digest": canonical_digest(adapter_binding),
            "environment": {
                "tool_versions": {adapter.adapter_id: adapter.adapter_version},
            },
        },
        "verification_request": {
            "expected_validator_ids": expected_validator_ids,
            "evidence_artifact_ids": artifact_ids,
            "notes": "Worker completion is pending separate independent verification.",
        },
        "extensions": {
            "org.idkmesh.interop": {
                "protocol": execution.protocol,
                "protocol_state": execution.protocol_state,
                "execution_status": execution.execution_status,
                "acceptance_status": execution.acceptance_status,
                "lifecycle": list(execution.lifecycle),
                "transport_digest": execution.transport_digest,
            }
        },
    }
    return ResultBundle(
        result_manifest=result_manifest,
        artifact_bytes={item.id: item.content for item in execution.artifacts},
    )


def verify_result_bundle(
    work_unit: dict[str, Any],
    bundle: ResultBundle,
    expected_artifacts: Mapping[str, bytes],
    context: VerificationContext,
) -> dict[str, Any]:
    """Independently check bindings and bytes without executing worker code."""

    manifest = bundle.result_manifest
    expected_work_unit_digest = canonical_digest(work_unit)
    binding_ok = (
        manifest.get("work_unit_id") == work_unit.get("id")
        and manifest.get("work_unit_version") == work_unit.get("version")
        and manifest.get("provenance", {}).get("work_unit_digest") == expected_work_unit_digest
    )
    declared = {item["id"]: item for item in manifest.get("produced_artifacts", [])}
    actual_ids = set(bundle.artifact_bytes)
    declared_ids = set(declared)
    expected_ids = set(expected_artifacts)
    digests_ok = actual_ids == declared_ids and all(
        declared[item_id].get("digest") == canonical_digest_bytes(content)
        for item_id, content in bundle.artifact_bytes.items()
        if item_id in declared
    )
    expected_ok = actual_ids == expected_ids and all(
        bundle.artifact_bytes[item_id] == expected
        for item_id, expected in expected_artifacts.items()
        if item_id in bundle.artifact_bytes
    )
    interop = manifest.get("extensions", {}).get("org.idkmesh.interop", {})
    authority_ok = interop.get("acceptance_status") == "pending_verification"
    execution_ok = (
        manifest.get("status") == "succeeded"
        and interop.get("execution_status") == "succeeded"
    )
    required_validator_ids = sorted(
        item["id"] for item in work_unit.get("validators", []) if item.get("required") is True
    )
    validators_ok = (
        manifest.get("verification_request", {}).get("expected_validator_ids")
        == required_validator_ids
    )
    output_ids = {item["id"] for item in work_unit.get("outputs", [])}
    output_contract_ok = declared_ids == output_ids

    check_values = [
        ("work-unit-binding", "other", binding_ok, "Manifest binds to the exact Work Unit."),
        ("execution-completion", "other", execution_ok, "Worker execution completed successfully."),
        ("validator-requirements", "policy", validators_ok, "All required validator identities were preserved."),
        ("output-contract", "policy", output_contract_ok, "Candidate artifact identities match the Work Unit outputs."),
        ("artifact-digests", "other", digests_ok, "Declared artifact digests match returned bytes."),
        ("expected-output", "reproduction", expected_ok, "Returned bytes match verifier-owned expectation."),
        ("authority-boundary", "policy", authority_ok, "Worker completion did not claim acceptance."),
    ]
    checks = [
        {
            "id": check_id,
            "type": check_type,
            "required": True,
            "status": "passed" if passed else "failed",
            "summary": summary,
            "evidence_ids": sorted(actual_ids) if check_id in {"artifact-digests", "expected-output"} else [],
        }
        for check_id, check_type, passed, summary in check_values
    ]
    passed = all(item[2] for item in check_values)
    result_digest = canonical_digest(manifest)
    verification_suffix = result_digest.split(":", 1)[1][:24]
    findings = [] if passed else [
        {
            "severity": "high",
            "category": "provenance",
            "summary": "One or more required interoperability verification checks failed.",
        }
    ]
    return {
        "schema_version": "0.1",
        "id": f"interop-verification/{verification_suffix}",
        "result_manifest_id": manifest["id"],
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": manifest["attempt"],
        "verifier": {
            "id": context.verifier_id,
            "type": "system",
            "adapter": "deterministic-artifact-verifier",
            "adapter_version": "0.1",
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": manifest["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": True,
            "correlation_notes": "Verifier is a separate component but this bounded mock runs in one process.",
        },
        "status": "passed" if passed else "failed",
        "started_at": context.started_at,
        "finished_at": context.finished_at,
        "checks": checks,
        "evidence": [
            {
                "id": item_id,
                "type": "artifact_hash",
                "locator": declared[item_id]["locator"],
                "digest": canonical_digest_bytes(content),
                "media_type": declared[item_id].get("media_type", "application/octet-stream"),
            }
            for item_id, content in sorted(bundle.artifact_bytes.items())
            if item_id in declared
        ],
        "findings": findings,
        "metrics": {"required_checks": len(checks), "passed_checks": sum(c[2] for c in check_values)},
        "resources": {"wall_seconds": context.wall_seconds},
        "provenance": {
            "result_manifest_digest": result_digest,
            "work_unit_digest": expected_work_unit_digest,
            "source_revision": context.source_revision,
            "verifier_config_digest": canonical_digest({
                "expected_artifacts": {
                    item_id: canonical_digest_bytes(content)
                    for item_id, content in sorted(expected_artifacts.items())
                }
            }),
            "environment": {"tool_versions": {"deterministic-artifact-verifier": "0.1"}},
        },
        "decision_support": {
            "recommendation": "accept_candidate" if passed else "reject_candidate",
            "confidence": 1.0,
            "rationale": "All verifier-owned deterministic checks passed." if passed else "A required deterministic check failed.",
        },
        "extensions": {
            "org.idkmesh.interop": {
                "candidate_code_executed_by_verifier": False,
                "integration_authority": False,
            }
        },
    }
