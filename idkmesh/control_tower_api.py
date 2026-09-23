"""Read-only Control Tower API model for IDKMesh run evidence.

This module intentionally consumes the existing Run Evidence Report v0.1
contract.  It does not execute workers, rerun verifiers, select a candidate,
record a human decision, write canonical project state, push Git, or merge.

The Control Tower's job is to make already-produced evidence understandable to
humans and future UI clients without inventing a second source of truth.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
from typing import Any

API_VERSION = "v1"
API_SCHEMA_VERSION = "0.1"
SNAPSHOT_KIND = "idkmesh-control-tower-snapshot"
STATUS_KIND = "idkmesh-control-tower-status"
INSPECTION_KIND = "idkmesh-control-tower-inspection-response"
ERROR_KIND = "idkmesh-api-error"
REPORT_KIND = "idkmesh-run-evidence-report"
REPORT_VERSION = "0.1"
SOURCE_RUN_KIND = "idkmesh-two-attempt-run"
JSON_MEDIA_TYPE = "application/json"
V1_MEDIA_TYPE = "application/vnd.idkmesh.control-tower.v1+json"

ATTEMPT_STATES = {
    "verified",
    "worker_error",
    "result_manifest_error",
    "verification_error",
}
ERROR_STATES = {
    "worker_error",
    "result_manifest_error",
    "verification_error",
}
EVIDENCE_STATES = {
    "supported",
    "rejected",
    "inconclusive",
    *ERROR_STATES,
}
RECOMMENDATIONS = {
    "accept_candidate",
    "reject_candidate",
    "escalate",
    "insufficient_evidence",
}
EXPECTED_AUTHORITY = {
    "canonical_state_write": False,
    "git_push": False,
    "merge": False,
    "automatic_candidate_selection": False,
}
EXPECTED_HUMAN_DECISION = {
    "status": "pending",
    "selected_attempt_id": None,
    "integration_authority": "external_human_or_governance",
}
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ControlTowerInputError(ValueError):
    """Run evidence cannot be safely represented by the read-only UI."""


def canonical_digest(value: Any) -> str:
    """Return the repository-standard digest for one JSON-compatible value."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _reject_json_constant(token: str) -> Any:
    raise ControlTowerInputError(
        f"non-finite JSON constant {token!r} is not permitted")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ControlTowerInputError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def parse_report_text(
    text: str,
    *,
    source: str = "run evidence input",
) -> dict[str, Any]:
    """Parse one Run Evidence Report document with strict JSON semantics."""
    text = text.removeprefix("\ufeff")
    try:
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise ControlTowerInputError(
            f"{source}: not valid JSON ({exc})") from exc
    except ControlTowerInputError as exc:
        raise ControlTowerInputError(f"{source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlTowerInputError(
            f"{source}: report must be a JSON object")
    validate_run_evidence_report(value)
    return value


def _require_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ControlTowerInputError(
            f"{field} must be sha256:<64 lowercase hex>")
    return value


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ControlTowerInputError(f"{field} must be a non-empty string")
    return value


def _validate_check(check: Any, attempt_id: str, index: int) -> None:
    if not isinstance(check, dict):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: check #{index} must be an object")
    _require_non_empty_string(
        check.get("id"), f"attempt {attempt_id}: check #{index}.id")
    _require_non_empty_string(
        check.get("status"), f"attempt {attempt_id}: check #{index}.status")
    if not isinstance(check.get("required"), bool):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: check #{index}.required must be boolean")


def _validate_attempt(attempt: Any, seen_ids: set[str]) -> str | None:
    if not isinstance(attempt, dict):
        raise ControlTowerInputError("every attempt must be an object")
    attempt_id = _require_non_empty_string(
        attempt.get("attempt_id"), "attempt_id")
    if attempt_id in seen_ids:
        raise ControlTowerInputError(f"duplicate attempt_id: {attempt_id!r}")
    seen_ids.add(attempt_id)

    order = attempt.get("order")
    if not isinstance(order, int) or isinstance(order, bool) or order < 1:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: order must be a positive integer")

    state = attempt.get("state")
    if state not in ATTEMPT_STATES:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: unsupported state {state!r}")
    evidence_state = attempt.get("evidence_state")
    if evidence_state not in EVIDENCE_STATES:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: unsupported evidence_state "
            f"{evidence_state!r}")
    _require_non_empty_string(
        attempt.get("worker_adapter"),
        f"attempt {attempt_id}: worker_adapter",
    )

    worker = attempt.get("worker")
    verifier = attempt.get("verifier")
    error = attempt.get("error")
    if error is not None and not isinstance(error, str):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: error must be a string or null")

    if state == "worker_error":
        if worker is not None or verifier is not None:
            raise ControlTowerInputError(
                f"attempt {attempt_id}: worker_error cannot claim worker or "
                "verification evidence")
        if evidence_state != "worker_error":
            raise ControlTowerInputError(
                f"attempt {attempt_id}: worker_error state/evidence mismatch")
        return None

    if state == "result_manifest_error":
        if worker is not None or verifier is not None:
            raise ControlTowerInputError(
                f"attempt {attempt_id}: result_manifest_error cannot claim "
                "parsed worker or verification evidence")
        if evidence_state != "result_manifest_error":
            raise ControlTowerInputError(
                f"attempt {attempt_id}: result_manifest_error state/evidence "
                "mismatch")
        return None

    if worker is None:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: this state requires a worker "
            "ResultManifest summary")
    if not isinstance(worker, dict):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: worker must be an object or null")
    _require_non_empty_string(
        worker.get("id"), f"attempt {attempt_id}: worker.id")
    _require_non_empty_string(
        worker.get("status"), f"attempt {attempt_id}: worker.status")
    _require_non_empty_string(
        worker.get("result_manifest_id"),
        f"attempt {attempt_id}: worker.result_manifest_id",
    )
    _require_digest(
        worker.get("result_manifest_digest"),
        f"attempt {attempt_id}: worker.result_manifest_digest",
    )

    if state == "verification_error":
        if verifier is not None or evidence_state != "verification_error":
            raise ControlTowerInputError(
                f"attempt {attempt_id}: verification_error state/evidence "
                "mismatch")
        return None

    if state != "verified" or not isinstance(verifier, dict):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: verified state requires verifier evidence")
    _require_non_empty_string(
        verifier.get("id"), f"attempt {attempt_id}: verifier.id")
    _require_non_empty_string(
        verifier.get("status"), f"attempt {attempt_id}: verifier.status")
    recommendation = verifier.get("recommendation")
    if recommendation not in RECOMMENDATIONS:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: unsupported recommendation "
            f"{recommendation!r}")
    _require_digest(
        verifier.get("verification_semantic_digest"),
        f"attempt {attempt_id}: verifier.verification_semantic_digest",
    )
    checks = verifier.get("checks")
    if not isinstance(checks, list):
        raise ControlTowerInputError(
            f"attempt {attempt_id}: verifier.checks must be an array")
    for index, check in enumerate(checks, start=1):
        _validate_check(check, attempt_id, index)

    expected_evidence_state = {
        "accept_candidate": "supported",
        "reject_candidate": "rejected",
        "escalate": "inconclusive",
        "insufficient_evidence": "inconclusive",
    }[recommendation]
    if evidence_state != expected_evidence_state:
        raise ControlTowerInputError(
            f"attempt {attempt_id}: evidence_state {evidence_state!r} does "
            f"not match recommendation {recommendation!r}")
    return recommendation


def validate_run_evidence_report(report: dict[str, Any]) -> None:
    """Validate the evidence invariants the Control Tower depends on.

    This validation is deliberately read-only and contract-focused.  It checks
    the complete fields rendered by the UI and recomputes summary/disagreement
    values so presentation cannot silently launder a self-selected candidate
    into an authoritative result.
    """
    if report.get("kind") != REPORT_KIND:
        raise ControlTowerInputError(
            f"kind must be {REPORT_KIND!r}")
    if report.get("schema_version") != REPORT_VERSION:
        raise ControlTowerInputError(
            f"schema_version must be {REPORT_VERSION!r}")
    _require_non_empty_string(report.get("run_id"), "run_id")
    if report.get("source_run_kind") != SOURCE_RUN_KIND:
        raise ControlTowerInputError(
            f"source_run_kind must be {SOURCE_RUN_KIND!r}")
    _require_digest(report.get("source_run_digest"), "source_run_digest")
    _require_digest(report.get("source_config_digest"), "source_config_digest")
    _require_digest(
        report.get("verifier_policy_digest"), "verifier_policy_digest")
    _require_non_empty_string(
        report.get("orchestrator_version"), "orchestrator_version")

    work_unit = report.get("work_unit")
    if not isinstance(work_unit, dict):
        raise ControlTowerInputError("work_unit must be an object")
    _require_non_empty_string(work_unit.get("id"), "work_unit.id")
    version = work_unit.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ControlTowerInputError(
            "work_unit.version must be a positive integer")
    _require_digest(work_unit.get("digest"), "work_unit.digest")

    attempts = report.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ControlTowerInputError(
            "attempts must be a non-empty array")
    seen_ids: set[str] = set()
    recommendations: list[str] = []
    for attempt in attempts:
        recommendation = _validate_attempt(attempt, seen_ids)
        if recommendation is not None:
            recommendations.append(recommendation)

    warnings = report.get("warnings")
    if (
        not isinstance(warnings, list)
        or not warnings
        or any(not isinstance(item, str) or not item for item in warnings)
    ):
        raise ControlTowerInputError(
            "warnings must be a non-empty array of strings")

    if report.get("authority") != EXPECTED_AUTHORITY:
        raise ControlTowerInputError(
            "authority must remain read-only: no canonical write, push, merge, "
            "or automatic candidate selection")
    if report.get("human_decision") != EXPECTED_HUMAN_DECISION:
        raise ControlTowerInputError(
            "human_decision must remain pending with no selected attempt")

    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ControlTowerInputError("summary must be an object")
    counts = Counter(item["evidence_state"] for item in attempts)
    expected_summary = {
        "attempt_count": len(attempts),
        "supported": counts["supported"],
        "rejected": counts["rejected"],
        "inconclusive": counts["inconclusive"],
        "control_errors": sum(counts[state] for state in ERROR_STATES),
        "verification_disagreement": len(set(recommendations)) > 1,
        "control_failure_present": any(
            item["state"] in ERROR_STATES for item in attempts),
    }
    for field, expected in expected_summary.items():
        if summary.get(field) != expected:
            raise ControlTowerInputError(
                f"summary.{field} is {summary.get(field)!r}; recomputed value "
                f"is {expected!r}")


def _check_summary(checks: list[dict[str, Any]]) -> str:
    required = [check for check in checks if check["required"]]
    passed = sum(check["status"] == "passed" for check in required)
    return f"{passed}/{len(required)} required checks passed"


def build_timeline(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive a semantic, ordered trace without inventing wall-clock times."""
    validate_run_evidence_report(report)
    events: list[dict[str, Any]] = []

    def add(
        event_type: str,
        title: str,
        detail: str,
        *,
        actor: str | None = None,
        attempt_id: str | None = None,
        evidence_ref: str | None = None,
    ) -> None:
        events.append(
            {
                "sequence": len(events) + 1,
                "type": event_type,
                "title": title,
                "detail": detail,
                "actor": actor,
                "attempt_id": attempt_id,
                "evidence_ref": evidence_ref,
            }
        )

    add(
        "observation",
        "Run evidence loaded",
        (
            f"Run {report['run_id']} describes WorkUnit "
            f"{report['work_unit']['id']} v{report['work_unit']['version']}."
        ),
        evidence_ref=report["source_run_digest"],
    )

    for attempt in sorted(report["attempts"], key=lambda item: item["order"]):
        attempt_id = attempt["attempt_id"]
        worker = attempt["worker"]
        verifier = attempt["verifier"]
        if attempt["state"] == "worker_error":
            add(
                "control_error",
                "Worker attempt failed",
                attempt.get("error") or "Worker failed before usable evidence.",
                attempt_id=attempt_id,
            )
            continue

        if worker is not None:
            add(
                "claim",
                "Worker ResultManifest recorded",
                (
                    f"Worker reports status {worker['status']!r} through "
                    f"adapter {attempt['worker_adapter']!r}."
                ),
                actor=worker["id"],
                attempt_id=attempt_id,
                evidence_ref=worker["result_manifest_digest"],
            )

        if attempt["state"] == "verification_error":
            add(
                "control_error",
                "Independent verification failed to complete",
                attempt.get("error") or "No usable VerificationResult exists.",
                attempt_id=attempt_id,
            )
            continue

        if verifier is not None:
            add(
                "evidence",
                "Independent checks recorded",
                _check_summary(verifier["checks"]),
                actor=verifier["id"],
                attempt_id=attempt_id,
                evidence_ref=verifier["verification_semantic_digest"],
            )
            add(
                "recommendation",
                "Verifier recommendation recorded",
                (
                    f"{verifier['recommendation']} → evidence state "
                    f"{attempt['evidence_state']}."
                ),
                actor=verifier["id"],
                attempt_id=attempt_id,
                evidence_ref=verifier["verification_semantic_digest"],
            )

    if report["summary"]["verification_disagreement"]:
        add(
            "attention",
            "Verification disagreement detected",
            (
                "Independent recommendations differ. The Control Tower "
                "preserves the disagreement and does not select a winner."
            ),
        )
    if report["summary"]["control_failure_present"]:
        add(
            "attention",
            "Control-path failure preserved",
            (
                "At least one attempt failed in the worker/result/verifier "
                "control path; surviving peer evidence remains visible."
            ),
        )
    add(
        "authority",
        "Human integration decision remains pending",
        (
            "No candidate is selected automatically. Integration authority "
            "remains external human or governance."
        ),
    )
    return events


def build_provenance(report: dict[str, Any]) -> dict[str, Any]:
    """Project explicit evidence bindings without inferring trust or independence."""
    validate_run_evidence_report(report)

    attempts: list[dict[str, Any]] = []
    for attempt in sorted(report["attempts"], key=lambda item: item["order"]):
        worker = attempt["worker"]
        verifier = attempt["verifier"]

        result_manifest = None
        if worker is not None:
            result_manifest = {
                "worker_id": worker["id"],
                "worker_status": worker["status"],
                "result_manifest_id": worker["result_manifest_id"],
                "result_manifest_digest": worker["result_manifest_digest"],
            }

        verification = None
        if verifier is not None:
            required_checks = [
                {
                    "id": check["id"],
                    "status": check["status"],
                }
                for check in verifier["checks"]
                if check["required"]
            ]
            verification = {
                "verifier_id": verifier["id"],
                "verifier_status": verifier["status"],
                "recommendation": verifier["recommendation"],
                "verification_semantic_digest": verifier[
                    "verification_semantic_digest"
                ],
                "required_checks": required_checks,
                "identity_distinct_from_worker": (
                    worker is not None and verifier["id"] != worker["id"]
                ),
                "independence_claim": (
                    "identity distinction is visible; statistical or "
                    "organizational independence is not inferred by this view"
                ),
            }

        attempts.append(
            {
                "attempt_id": attempt["attempt_id"],
                "order": attempt["order"],
                "worker_adapter": attempt["worker_adapter"],
                "result_manifest": result_manifest,
                "verification": verification,
                "evidence_state": attempt["evidence_state"],
                "error": attempt["error"],
            }
        )

    return {
        "work_unit": {
            "id": report["work_unit"]["id"],
            "version": report["work_unit"]["version"],
            "digest": report["work_unit"]["digest"],
        },
        "run": {
            "run_id": report["run_id"],
            "source_run_digest": report["source_run_digest"],
            "source_config_digest": report["source_config_digest"],
            "verifier_policy_digest": report["verifier_policy_digest"],
            "orchestrator_version": report["orchestrator_version"],
        },
        "attempts": attempts,
        "authority": {
            **dict(report["authority"]),
            "human_decision_status": report["human_decision"]["status"],
            "integration_authority": report["human_decision"][
                "integration_authority"
            ],
        },
    }


def build_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    """Build the UI/API view over one validated run evidence report."""
    validate_run_evidence_report(report)
    summary = report["summary"]
    provenance = build_provenance(report)
    attention: list[dict[str, str]] = []

    identity_overlap = any(
        attempt["verification"] is not None
        and not attempt["verification"]["identity_distinct_from_worker"]
        for attempt in provenance["attempts"]
    )
    if identity_overlap:
        attention.append(
            {
                "severity": "high",
                "code": "worker_verifier_identity_overlap",
                "title": "Worker/verifier identity overlap is visible",
                "why": (
                    "At least one attempt records the same worker and verifier "
                    "identity. The Control Tower does not treat that as "
                    "independent verification."
                ),
            }
        )

    if summary["verification_disagreement"]:
        attention.append(
            {
                "severity": "high",
                "code": "verification_disagreement",
                "title": "Verifier disagreement needs human review",
                "why": (
                    "Independent recommendations differ; majority truth is "
                    "not inferred."
                ),
            }
        )
    if summary["control_failure_present"]:
        attention.append(
            {
                "severity": "high",
                "code": "control_failure_present",
                "title": "A worker/verifier control path failed",
                "why": (
                    "The failed attempt remains visible while peer evidence is "
                    "preserved."
                ),
            }
        )
    if summary["rejected"]:
        attention.append(
            {
                "severity": "medium",
                "code": "rejected_attempts",
                "title": f"{summary['rejected']} attempt(s) rejected by evidence",
                "why": (
                    "Worker completion is not acceptance; inspect the failing "
                    "checks before deciding."
                ),
            }
        )
    attention.append(
        {
            "severity": "action",
            "code": "human_decision_pending",
            "title": "Human integration decision is pending",
            "why": (
                "This report intentionally carries no selected candidate and "
                "no merge authority."
            ),
        }
    )

    attempts = []
    for attempt in sorted(report["attempts"], key=lambda item: item["order"]):
        worker = attempt["worker"]
        verifier = attempt["verifier"]
        attempts.append(
            {
                "attempt_id": attempt["attempt_id"],
                "order": attempt["order"],
                "state": attempt["state"],
                "evidence_state": attempt["evidence_state"],
                "worker_adapter": attempt["worker_adapter"],
                "claim": (
                    None
                    if worker is None
                    else {
                        "worker_id": worker["id"],
                        "worker_status": worker["status"],
                        "result_manifest_id": worker["result_manifest_id"],
                        "result_manifest_digest": worker[
                            "result_manifest_digest"],
                    }
                ),
                "evidence": (
                    None
                    if verifier is None
                    else {
                        "verifier_id": verifier["id"],
                        "verifier_status": verifier["status"],
                        "recommendation": verifier["recommendation"],
                        "verification_digest": verifier[
                            "verification_semantic_digest"],
                        "checks": verifier["checks"],
                    }
                ),
                "error": attempt["error"],
            }
        )

    return {
        "api_version": API_VERSION,
        "schema_version": API_SCHEMA_VERSION,
        "kind": SNAPSHOT_KIND,
        "source": {
            "kind": report["kind"],
            "evidence_report_digest": canonical_digest(report),
            "schema_version": report["schema_version"],
            "run_id": report["run_id"],
            "source_run_digest": report["source_run_digest"],
            "source_config_digest": report["source_config_digest"],
            "verifier_policy_digest": report["verifier_policy_digest"],
        },
        "work_unit": report["work_unit"],
        "summary": dict(summary),
        "attention": attention,
        "attempts": attempts,
        "provenance": provenance,
        "timeline": build_timeline(report),
        "warnings": list(report["warnings"]),
        "human_decision": dict(report["human_decision"]),
        "authority": dict(report["authority"]),
        "interpretation_rules": [
            "worker success != verified correctness",
            "verifier recommendation != human integration decision",
            "multiple recommendations != majority truth",
            "replay equality != correctness",
        ],
    }


def status_document() -> dict[str, Any]:
    """Return the stable discovery/status document for API clients."""
    return {
        "api_version": API_VERSION,
        "schema_version": API_SCHEMA_VERSION,
        "kind": STATUS_KIND,
        "ok": True,
        "service": "idkmesh-control-tower",
        "mode": "local-read-only",
        "media_types": [JSON_MEDIA_TYPE, V1_MEDIA_TYPE],
        "source_contracts": [
            f"{REPORT_KIND}/{REPORT_VERSION}",
        ],
        "schemas": {
            "run_evidence_report": (
                "https://idkmesh.org/schemas/"
                "run-evidence-report-v0.1.schema.json"
            ),
            "control_tower_snapshot": (
                "https://idkmesh.org/schemas/"
                "control-tower-snapshot-v0.1.schema.json"
            ),
        },
        "capabilities": {
            "run_evidence_inspection": True,
            "semantic_timeline": True,
            "provenance_chain": True,
            "human_decision_recording": False,
            "worker_execution": False,
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
        "operations": {
            "request_id_header": "X-Request-ID",
            "liveness": "GET /healthz",
            "readiness": "GET /readyz",
            "access_log_env": "IDKMESH_HTTP_ACCESS_LOG",
            "access_logs_include_bodies": False,
            "access_logs_include_authentication": False,
        },
        "endpoints": {
            "status": "GET /api/v1/status",
            "openapi": "GET /api/v1/openapi.json",
            "inspect_run_evidence": "POST /api/v1/run-evidence/inspect",
            "health": "GET /healthz",
            "readiness": "GET /readyz",
        },
    }


def openapi_document() -> dict[str, Any]:
    """Return a dependency-free OpenAPI description for local API clients."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "IDKMesh Control Tower Local API",
            "version": API_SCHEMA_VERSION,
            "description": (
                "Loopback-only, read-only evidence inspection API. "
                "It cannot execute workers, select candidates, push, or merge."
            ),
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/healthz": {
                "get": {
                    "summary": "Process liveness probe",
                    "description": (
                        "Returns a minimal liveness response and no project state."
                    ),
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Process is alive",
                            "content": {
                                "text/plain": {
                                    "schema": {
                                        "type": "string",
                                        "example": "ok\\n",
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/readyz": {
                "get": {
                    "summary": "Service readiness probe",
                    "description": (
                        "Returns minimal service/API readiness metadata and no "
                        "project, run, evidence, secret, or identity state."
                    ),
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Service is ready",
                            "content": {
                                JSON_MEDIA_TYPE: {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "status",
                                            "service",
                                            "service_version",
                                            "mode",
                                            "api_version",
                                        ],
                                        "properties": {
                                            "status": {"const": "ready"},
                                            "service": {
                                                "const": "idkmesh-control-tower"
                                            },
                                            "service_version": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "mode": {
                                                "const": "local-read-only"
                                            },
                                            "api_version": {
                                                "const": API_VERSION
                                            },
                                        },
                                        "additionalProperties": False,
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/status": {
                "get": {
                    "summary": "Discover API capabilities and authority limits",
                    "security": [{"LocalSessionToken": []}],
                    "responses": {
                        "200": {
                            "description": "Control Tower status",
                            "content": {
                                JSON_MEDIA_TYPE: {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "api_version", "schema_version",
                                            "kind", "ok", "capabilities",
                                        ],
                                    }
                                },
                                V1_MEDIA_TYPE: {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "api_version", "schema_version",
                                            "kind", "ok", "capabilities",
                                        ],
                                    }
                                },
                            },
                        }
                    },
                }
            },
            "/api/v1/openapi.json": {
                "get": {
                    "summary": "Read this OpenAPI contract",
                    "security": [{"LocalSessionToken": []}],
                    "responses": {
                        "200": {
                            "description": "OpenAPI 3.1 document",
                            "content": {
                                JSON_MEDIA_TYPE: {
                                    "schema": {"type": "object"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/run-evidence/inspect": {
                "post": {
                    "summary": (
                        "Validate and render one Run Evidence Report v0.1"
                    ),
                    "description": (
                        "Pure read-only inspection. The same valid input "
                        "produces the same response body and content digest."
                    ),
                    "security": [{"LocalSessionToken": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            JSON_MEDIA_TYPE: {
                                "schema": {
                                    "$ref": (
                                        "https://idkmesh.org/schemas/"
                                        "run-evidence-report-v0.1.schema.json"
                                    )
                                }
                            },
                            V1_MEDIA_TYPE: {
                                "schema": {
                                    "$ref": (
                                        "https://idkmesh.org/schemas/"
                                        "run-evidence-report-v0.1.schema.json"
                                    )
                                }
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Validated read-only snapshot",
                            "content": {
                                JSON_MEDIA_TYPE: {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "api_version", "schema_version",
                                            "kind", "ok", "snapshot",
                                            "snapshot_digest",
                                        ],
                                        "properties": {
                                            "snapshot": {
                                                "$ref": (
                                                    "https://idkmesh.org/"
                                                    "schemas/"
                                                    "control-tower-snapshot-"
                                                    "v0.1.schema.json"
                                                )
                                            }
                                        },
                                    }
                                },
                                V1_MEDIA_TYPE: {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "api_version", "schema_version",
                                            "kind", "ok", "snapshot",
                                            "snapshot_digest",
                                        ],
                                        "properties": {
                                            "snapshot": {
                                                "$ref": (
                                                    "https://idkmesh.org/"
                                                    "schemas/"
                                                    "control-tower-snapshot-"
                                                    "v0.1.schema.json"
                                                )
                                            }
                                        },
                                    }
                                },
                            },
                        },
                        "400": {"description": "Invalid run evidence"},
                        "403": {"description": "Invalid local session token"},
                        "406": {"description": "Requested response type unsupported"},
                        "413": {"description": "Request body too large"},
                        "415": {"description": "Request content type unsupported"},
                    },
                }
            },
        },
        "components": {
            "headers": {
                "RequestId": {
                    "description": (
                        "Opaque request correlation identifier. A safe incoming "
                        "X-Request-ID is echoed; invalid values are replaced."
                    ),
                    "schema": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                },
                "Service": {
                    "description": "IDKMesh service identity",
                    "schema": {"const": "idkmesh-control-tower"},
                },
                "ReadOnly": {
                    "description": "Whether this service grants write authority",
                    "schema": {"const": "true"},
                },
            },
            "securitySchemes": {
                "LocalSessionToken": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-IDKMesh-UI-Token",
                }
            }
        },
    }


def error_document(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if details is not None:
        error["details"] = details
    return {
        "api_version": API_VERSION,
        "schema_version": API_SCHEMA_VERSION,
        "kind": ERROR_KIND,
        "ok": False,
        "error": error,
    }


def success_document(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Wrap one immutable inspection snapshot in the stable success envelope."""
    return {
        "api_version": API_VERSION,
        "schema_version": API_SCHEMA_VERSION,
        "kind": INSPECTION_KIND,
        "ok": True,
        "snapshot_digest": canonical_digest(snapshot),
        "snapshot": snapshot,
    }
