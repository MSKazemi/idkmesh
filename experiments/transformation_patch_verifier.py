#!/usr/bin/env python3
"""Versioned metadata-only patch verifier for calibrated transformation evidence.

EvaluatorPlan v0.4 requires both:

- declared semantic fragments to appear in added lines; and
- declared vulnerable/obsolete fragments to appear in removed lines.

This module leaves v0.2 exact-line and v0.3 added-substring semantics unchanged.
It composes the v0.3 adapter for added-line checks, then adds independent
removed-line evidence. Candidate code is never executed here.

A transformation proxy is still not equivalent to behavioral correctness. Tasks
with a safe evaluator-owned behavioral regression must retain that stronger
channel separately before making security/correctness claims.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
from typing import Any

import local_verifier
import substring_patch_verifier
from provenance_integrity import canonical_digest, validate_integrity

PATCH_TRANSFORMATION_VERIFIER_VERSION = "0.3.0"
ADDED_SUBSTRING_CORE_VERSION = "0.2.0"
LEGACY_PATCH_CORE_VERSION = "0.1.1"
SEMANTIC_MODE = "added_and_removed_line_substring_all"


class TransformationVerifierError(local_verifier.VerifierError):
    """Raised when a v0.4 transformation policy or candidate boundary is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransformationVerifierError(message)


def validate_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "id", "candidate_artifact_id", "backend"}
    missing = sorted(required - set(policy))
    if missing:
        raise TransformationVerifierError(
            "transformation patch policy missing field(s): " + ", ".join(missing)
        )
    _require(policy["schema_version"] == "0.4", "unsupported transformation policy schema_version")
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
        "required_removed_substrings",
        "require_nonempty_patch",
        "verify_log_digests",
    }
    missing_backend = sorted(required_backend - set(backend))
    extra_backend = sorted(set(backend) - required_backend)
    if missing_backend or extra_backend:
        raise TransformationVerifierError(
            "transformation backend fields differ from v0.4 contract; "
            f"missing={missing_backend}, extra={extra_backend}"
        )
    _require(backend["type"] == "unified_diff", "backend.type must be unified_diff")
    for field in ("max_candidate_bytes", "max_log_bytes"):
        _require(
            isinstance(backend[field], int) and backend[field] >= 1,
            f"backend.{field} must be a positive integer",
        )
    logs = backend["required_log_types"]
    _require(isinstance(logs, list) and bool(logs), "required_log_types must be non-empty")
    _require(len(logs) == len(set(logs)), "required_log_types must be unique")
    _require(
        all(value in local_verifier.RESULT_LOG_TYPES for value in logs),
        "required_log_types contains an unsupported ResultManifest log type",
    )
    for field in ("required_added_substrings", "required_removed_substrings"):
        values = backend[field]
        _require(isinstance(values, list) and bool(values), f"{field} must be non-empty")
        _require(len(values) == len(set(values)), f"{field} must be unique")
        _require(
            all(isinstance(value, str) and bool(value) for value in values),
            f"{field} entries must be non-empty strings",
        )
    _require(backend["require_nonempty_patch"] is True, "require_nonempty_patch must be true")
    _require(backend["verify_log_digests"] is True, "verify_log_digests must be true")


def _candidate_artifact(worker_result: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    matches = [
        artifact for artifact in worker_result["produced_artifacts"] if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise TransformationVerifierError(
            "candidate_artifact_id must match exactly one produced artifact"
        )
    return matches[0]


def _safe_candidate_path(candidate_root: Path, locator: str) -> Path:
    posix = PurePosixPath(locator)
    if not locator or posix.is_absolute() or ".." in posix.parts:
        raise TransformationVerifierError(f"unsafe candidate locator: {locator!r}")
    path = (candidate_root / Path(*posix.parts)).resolve()
    try:
        path.relative_to(candidate_root)
    except ValueError as exc:
        raise TransformationVerifierError(
            f"candidate locator escapes candidate root: {locator}"
        ) from exc
    return path


def _parse_removed_lines(patch_text: str) -> list[str]:
    # First reuse the legacy parser as the structural source of truth. It raises
    # on malformed/out-of-contract unified diffs before we interpret removed lines.
    local_verifier.parse_unified_diff(patch_text)

    removed: list[str] = []
    in_hunk = False
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("\\ No newline at end of file"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
    return removed


def _removed_observation(
    *,
    patch_bytes: bytes,
    max_candidate_bytes: int,
    required_substrings: list[str],
) -> dict[str, Any]:
    removed_lines: list[str] = []
    parse_error: str | None = None
    if len(patch_bytes) > max_candidate_bytes:
        parse_error = (
            f"candidate is {len(patch_bytes)} bytes, exceeding "
            f"max_candidate_bytes={max_candidate_bytes}"
        )
    else:
        try:
            patch_text = patch_bytes.decode("utf-8")
            removed_lines = _parse_removed_lines(patch_text)
        except (UnicodeDecodeError, local_verifier.VerifierError) as exc:
            parse_error = str(exc)

    matches: list[dict[str, Any]] = []
    missing: list[str] = []
    for substring in required_substrings:
        matched_line = next((line for line in removed_lines if substring in line), None)
        matches.append({"substring": substring, "matched_line": matched_line})
        if matched_line is None:
            missing.append(substring)

    return {
        "semantic_mode": "removed_line_substring_all",
        "required_removed_substrings": required_substrings,
        "observed_removed_lines": removed_lines,
        "matches": matches,
        "missing_substrings": missing,
        "parse_error": parse_error,
    }


def _added_policy(policy: dict[str, Any]) -> dict[str, Any]:
    backend = copy.deepcopy(policy["backend"])
    backend.pop("required_removed_substrings")
    derived = {
        "schema_version": "0.3",
        "id": policy["id"],
        "candidate_artifact_id": policy["candidate_artifact_id"],
        "backend": backend,
    }
    substring_patch_verifier.validate_policy(derived)
    return derived


def verify_patch_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Verify a v0.4 transformation policy without executing candidate code."""

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
        raise TransformationVerifierError(
            "verifier-owned policy must not live inside the candidate root"
        )

    artifact = _candidate_artifact(worker_result, policy["candidate_artifact_id"])
    candidate_path = _safe_candidate_path(candidate_root, artifact["locator"])
    _require(
        candidate_path.is_file() and not candidate_path.is_symlink(),
        "candidate patch must be a regular non-symlink file",
    )
    patch_bytes = candidate_path.read_bytes()
    removed = _removed_observation(
        patch_bytes=patch_bytes,
        max_candidate_bytes=policy["backend"]["max_candidate_bytes"],
        required_substrings=list(policy["backend"]["required_removed_substrings"]),
    )

    result = substring_patch_verifier.verify_patch_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=_added_policy(policy),
        candidate_root=candidate_root,
        policy_path=policy_path,
    )

    evidence_id = "removed-substring-semantic-observation"
    result["evidence"].append(
        {
            "id": evidence_id,
            "type": "test_output",
            "locator": "inline://removed-substring-semantic-observation",
            "digest": local_verifier.sha256_json(removed),
            "media_type": "application/json",
            "description": (
                "Canonical digest of case-sensitive required-substring matching "
                "over removed lines in structurally validated unified-diff hunks."
            ),
        }
    )

    independent_review = next(
        (check for check in result["checks"] if check["id"] == "independent-review"),
        None,
    )
    if independent_review is None:
        raise TransformationVerifierError("VerificationResult lacks independent-review check")
    independent_review["evidence_ids"].append(evidence_id)
    diagnostics = json.loads(independent_review.get("diagnostics") or "{}")
    diagnostics["semantic_removed_substrings"] = removed
    independent_review["diagnostics"] = json.dumps(
        diagnostics, sort_keys=True, separators=(",", ":")
    )

    missing_removed = list(removed["missing_substrings"])
    if missing_removed:
        independent_review["status"] = "failed"
        independent_review["summary"] = (
            "Independent metadata-only transformation review rejected the candidate: "
            "at least one required removed-line substring was absent or another "
            "required patch check failed."
        )
        result["status"] = "failed"
        result["decision_support"] = {
            "recommendation": "reject_candidate",
            "confidence": 0.99,
            "rationale": (
                "The patch does not demonstrate all verifier-owned required removals; "
                "added proxy text alone is insufficient transformation evidence."
            ),
        }
        result["findings"].append(
            {
                "severity": "high",
                "category": "correctness",
                "summary": (
                    "Candidate patch is missing verifier-owned required removed-line "
                    "transformation evidence."
                ),
            }
        )
    elif independent_review["status"] == "passed":
        independent_review["summary"] = (
            "Independent metadata-only transformation review passed artifact/log "
            "integrity, strict patch structure, scope, required added substrings, "
            "and required removed substrings."
        )
        result["decision_support"]["rationale"] = (
            "All WorkUnit-required metadata-only checks passed, including explicit "
            "v0.4 added-and-removed transformation semantics. Behavioral correctness "
            "remains a separate evidence question."
        )

    result["metrics"]["required_removed_substring_count"] = len(
        policy["backend"]["required_removed_substrings"]
    )
    result["metrics"]["matched_removed_substring_count"] = len(
        policy["backend"]["required_removed_substrings"]
    ) - len(missing_removed)

    result["verifier"]["adapter_version"] = PATCH_TRANSFORMATION_VERIFIER_VERSION
    result["independence"]["correlation_notes"] = (
        "Evaluator control is outside the candidate root; candidate code is never "
        "executed by this verifier. v0.3 provides explicit added-line substring "
        "checks and the unchanged v0.1.1 core provides strict diff/provenance/log/"
        "scope checks; v0.3.0 additionally requires declared removed-line evidence."
    )
    result["provenance"]["verifier_config_digest"] = canonical_digest(policy)
    tool_versions = result["provenance"]["environment"].setdefault("tool_versions", {})
    tool_versions["deterministic-patch-verifier"] = PATCH_TRANSFORMATION_VERIFIER_VERSION
    tool_versions["deterministic-patch-verifier-added-substring-core"] = (
        ADDED_SUBSTRING_CORE_VERSION
    )
    tool_versions["deterministic-patch-verifier-legacy-core"] = LEGACY_PATCH_CORE_VERSION
    result.setdefault("extensions", {})[
        "org.idkmesh.local_verifier.semantic_match_mode"
    ] = SEMANTIC_MODE
    result["extensions"]["org.idkmesh.local_verifier.added_substring_core_version"] = (
        ADDED_SUBSTRING_CORE_VERSION
    )
    result["extensions"]["org.idkmesh.local_verifier.legacy_patch_core_version"] = (
        LEGACY_PATCH_CORE_VERSION
    )
    result["extensions"]["org.idkmesh.local_verifier.behavioral_correctness_claim"] = False

    local_verifier.validate_schema(
        result,
        local_verifier.VERIFICATION_RESULT_SCHEMA,
        "VerificationResult",
    )
    validate_integrity(work_unit, worker_result, result)
    return result
