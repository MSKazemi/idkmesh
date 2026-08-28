#!/usr/bin/env python3
"""Versioned metadata-only patch verifier with explicit added-line substring semantics.

This module deliberately leaves ``local_verifier`` patch verifier v0.1.1 unchanged.
It reuses that verifier's strict unified-diff, provenance, log-integrity, and scope
checks, while adding a new v0.3 operational policy whose semantic requirement is
unambiguous: every configured substring must occur contiguously and
case-sensitively within at least one single added line in a validated diff hunk.

Candidate code is never executed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
from typing import Any

import local_verifier
from provenance_integrity import canonical_digest, validate_integrity

PATCH_SUBSTRING_VERIFIER_VERSION = "0.2.0"
LEGACY_PATCH_CORE_VERSION = "0.1.1"
SEMANTIC_MODE = "added_line_substring_all"


class SubstringVerifierError(local_verifier.VerifierError):
    """Raised when the v0.3 substring policy or candidate boundary is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SubstringVerifierError(message)


def validate_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "id", "candidate_artifact_id", "backend"}
    missing = sorted(required - set(policy))
    if missing:
        raise SubstringVerifierError(
            "substring patch verifier policy missing field(s): " + ", ".join(missing)
        )
    _require(policy["schema_version"] == "0.3", "unsupported substring patch policy schema_version")
    _require(isinstance(policy["id"], str) and bool(policy["id"]), "policy id must be non-empty")
    _require(
        isinstance(policy["candidate_artifact_id"], str) and bool(policy["candidate_artifact_id"]),
        "candidate_artifact_id must be non-empty",
    )

    backend = policy["backend"]
    _require(isinstance(backend, dict), "backend must be an object")
    required_backend = {
        "type",
        "max_candidate_bytes",
        "max_log_bytes",
        "required_log_types",
        "required_added_substrings",
        "require_nonempty_patch",
        "verify_log_digests",
    }
    missing_backend = sorted(required_backend - set(backend))
    extra_backend = sorted(set(backend) - required_backend)
    if missing_backend or extra_backend:
        raise SubstringVerifierError(
            "substring backend fields differ from v0.3 contract; "
            f"missing={missing_backend}, extra={extra_backend}"
        )
    _require(backend["type"] == "unified_diff", "backend.type must be unified_diff")
    for field in ("max_candidate_bytes", "max_log_bytes"):
        _require(
            isinstance(backend[field], int) and backend[field] >= 1,
            f"backend.{field} must be a positive integer",
        )
    required_logs = backend["required_log_types"]
    _require(isinstance(required_logs, list) and bool(required_logs), "required_log_types must be non-empty")
    _require(len(required_logs) == len(set(required_logs)), "required_log_types must be unique")
    _require(
        all(value in local_verifier.RESULT_LOG_TYPES for value in required_logs),
        "required_log_types contains an unsupported ResultManifest log type",
    )
    substrings = backend["required_added_substrings"]
    _require(isinstance(substrings, list) and bool(substrings), "required_added_substrings must be non-empty")
    _require(len(substrings) == len(set(substrings)), "required_added_substrings must be unique")
    _require(
        all(isinstance(value, str) and bool(value) for value in substrings),
        "required_added_substrings entries must be non-empty strings",
    )
    _require(backend["require_nonempty_patch"] is True, "require_nonempty_patch must be true")
    _require(backend["verify_log_digests"] is True, "verify_log_digests must be true")


def _candidate_artifact(worker_result: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    matches = [
        artifact for artifact in worker_result["produced_artifacts"] if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise SubstringVerifierError(
            "candidate_artifact_id must match exactly one produced artifact"
        )
    return matches[0]


def _safe_candidate_path(candidate_root: Path, locator: str) -> Path:
    posix = PurePosixPath(locator)
    if not locator or posix.is_absolute() or ".." in posix.parts:
        raise SubstringVerifierError(f"unsafe candidate locator: {locator!r}")
    path = (candidate_root / Path(*posix.parts)).resolve()
    try:
        path.relative_to(candidate_root)
    except ValueError as exc:
        raise SubstringVerifierError(
            f"candidate locator escapes candidate root: {locator}"
        ) from exc
    return path


def _semantic_observation(
    *,
    patch_bytes: bytes,
    max_candidate_bytes: int,
    required_substrings: list[str],
) -> tuple[dict[str, Any], list[str]]:
    added_lines: list[str] = []
    parse_error: str | None = None
    if len(patch_bytes) > max_candidate_bytes:
        parse_error = (
            f"candidate is {len(patch_bytes)} bytes, exceeding "
            f"max_candidate_bytes={max_candidate_bytes}"
        )
    else:
        try:
            patch_text = patch_bytes.decode("utf-8")
            _, added_lines = local_verifier.parse_unified_diff(patch_text)
        except (UnicodeDecodeError, local_verifier.VerifierError) as exc:
            parse_error = str(exc)

    matches: list[dict[str, Any]] = []
    missing: list[str] = []
    representative_lines: list[str] = []
    for substring in required_substrings:
        matched_line = next((line for line in added_lines if substring in line), None)
        matches.append({"substring": substring, "matched_line": matched_line})
        if matched_line is None:
            missing.append(substring)
            # Because no added line contains the substring, requiring the substring
            # itself as an exact line forces the legacy core to fail semantically.
            representative_lines.append(substring)
        else:
            representative_lines.append(matched_line)

    # The legacy v0.1.1 core requires unique exact-line expectations. Multiple
    # substrings may intentionally match the same added line, so deduplicate only
    # the derived implementation detail, never the v0.3 semantic requirements.
    derived_exact_lines = list(dict.fromkeys(representative_lines))
    observation = {
        "semantic_mode": SEMANTIC_MODE,
        "required_added_substrings": required_substrings,
        "observed_added_lines": added_lines,
        "matches": matches,
        "missing_substrings": missing,
        "parse_error": parse_error,
    }
    return observation, derived_exact_lines


def _legacy_policy(policy: dict[str, Any], derived_exact_lines: list[str]) -> dict[str, Any]:
    backend = copy.deepcopy(policy["backend"])
    backend.pop("required_added_substrings")
    backend["required_added_text"] = derived_exact_lines
    derived = {
        "schema_version": "0.2",
        "id": policy["id"],
        "candidate_artifact_id": policy["candidate_artifact_id"],
        "backend": backend,
    }
    # Fail closed before delegation if our derived policy is somehow invalid.
    local_verifier.validate_patch_policy(derived)
    return derived


def verify_patch_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Verify a v0.3 substring-policy patch without executing candidate code."""

    local_verifier.validate_schema(work_unit, local_verifier.WORK_UNIT_SCHEMA, "Work Unit")
    local_verifier.validate_schema(
        worker_result,
        local_verifier.RESULT_MANIFEST_SCHEMA,
        "ResultManifest",
    )
    validate_policy(policy)

    candidate_root = candidate_root.resolve()
    _require(candidate_root.is_dir(), f"candidate root is not a directory: {candidate_root}")
    policy_path = policy_path.resolve()
    try:
        policy_path.relative_to(candidate_root)
    except ValueError:
        pass
    else:
        raise SubstringVerifierError(
            "verifier-owned policy must not live inside the candidate root"
        )

    artifact = _candidate_artifact(worker_result, policy["candidate_artifact_id"])
    candidate_path = _safe_candidate_path(candidate_root, artifact["locator"])
    _require(
        candidate_path.is_file() and not candidate_path.is_symlink(),
        "candidate patch must be a regular non-symlink file",
    )
    patch_bytes = candidate_path.read_bytes()
    semantic, derived_exact_lines = _semantic_observation(
        patch_bytes=patch_bytes,
        max_candidate_bytes=policy["backend"]["max_candidate_bytes"],
        required_substrings=list(policy["backend"]["required_added_substrings"]),
    )

    result = local_verifier.verify_patch_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=_legacy_policy(policy, derived_exact_lines),
        candidate_root=candidate_root,
        policy_path=policy_path,
    )

    semantic_evidence_id = "added-substring-semantic-observation"
    result["evidence"].append(
        {
            "id": semantic_evidence_id,
            "type": "test_output",
            "locator": "inline://added-substring-semantic-observation",
            "digest": local_verifier.sha256_json(semantic),
            "media_type": "application/json",
            "description": (
                "Canonical digest of explicit case-sensitive, single-added-line "
                "substring matching for EvaluatorPlan v0.3."
            ),
        }
    )

    for check in result["checks"]:
        if check["id"] != "independent-review":
            continue
        check["evidence_ids"].append(semantic_evidence_id)
        diagnostics = json.loads(check.get("diagnostics") or "{}")
        diagnostics["semantic_substrings"] = semantic
        check["diagnostics"] = json.dumps(
            diagnostics, sort_keys=True, separators=(",", ":")
        )
        if check["status"] == "passed":
            check["summary"] = (
                "Independent metadata-only patch review passed artifact/log integrity, "
                "strict patch structure, scope, and explicit v0.3 added-line substring checks."
            )
        else:
            check["summary"] = (
                "Independent metadata-only patch review rejected the candidate bundle "
                "under v0.3 added-line substring semantics or another required check."
            )

    legacy_summary = (
        "Candidate patch does not contain all verifier-owned required added text "
        "inside validated hunks."
    )
    for finding in result["findings"]:
        if finding.get("summary") == legacy_summary:
            finding["summary"] = (
                "Candidate patch does not contain all verifier-owned required added "
                "substrings within individual validated-hunk added lines."
            )

    result["metrics"]["required_substring_count"] = len(
        policy["backend"]["required_added_substrings"]
    )
    result["metrics"]["matched_substring_count"] = len(
        policy["backend"]["required_added_substrings"]
    ) - len(semantic["missing_substrings"])

    result["verifier"]["adapter_version"] = PATCH_SUBSTRING_VERIFIER_VERSION
    result["independence"]["correlation_notes"] = (
        "Evaluator control is outside the candidate root; candidate code is never "
        "executed. Strict diff/provenance/log/scope checks reuse verifier v0.1.1, "
        "while v0.2.0 adds explicit case-sensitive substring matching within each "
        "validated-hunk added line."
    )
    result["provenance"]["verifier_config_digest"] = canonical_digest(policy)
    tool_versions = result["provenance"]["environment"].setdefault("tool_versions", {})
    tool_versions["deterministic-patch-verifier"] = PATCH_SUBSTRING_VERIFIER_VERSION
    tool_versions["deterministic-patch-verifier-legacy-core"] = LEGACY_PATCH_CORE_VERSION
    result.setdefault("extensions", {})[
        "org.idkmesh.local_verifier.semantic_match_mode"
    ] = SEMANTIC_MODE
    result["extensions"]["org.idkmesh.local_verifier.legacy_patch_core_version"] = (
        LEGACY_PATCH_CORE_VERSION
    )

    if result["status"] == "passed":
        result["decision_support"]["rationale"] = (
            "All WorkUnit-required checks passed, including explicit v0.3 "
            "added-line substring semantics."
        )
    elif semantic["missing_substrings"]:
        result["decision_support"]["rationale"] = (
            "At least one required added-line substring was absent or another "
            "WorkUnit-required check failed."
        )

    local_verifier.validate_schema(
        result,
        local_verifier.VERIFICATION_RESULT_SCHEMA,
        "VerificationResult",
    )
    validate_integrity(work_unit, worker_result, result)
    return result
