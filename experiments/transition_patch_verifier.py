#!/usr/bin/env python3
"""Versioned metadata-only patch verifier with added/removed transition semantics.

EvaluatorPlan v0.4 keeps every historical verifier meaning intact:

- v0.2 / verifier 0.1.1: exact full added-line matching;
- v0.3 / verifier 0.2.0: added-line substring matching;
- v0.4 / verifier 0.3.0: added-line AND removed-line substring matching.

The v0.4 adapter reuses the v0.3 verifier for strict unified-diff structure,
artifact/log integrity, WorkUnit scope, provenance, and added-substring checks.
It adds only an explicit removed-line transition requirement. Candidate code is
never executed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import local_verifier
import substring_patch_verifier
from provenance_integrity import canonical_digest, validate_integrity

PATCH_TRANSITION_VERIFIER_VERSION = "0.3.0"
ADDED_SUBSTRING_CORE_VERSION = "0.2.0"
SEMANTIC_MODE = "added_and_removed_line_substring_all"


class TransitionVerifierError(local_verifier.VerifierError):
    """Raised when the v0.4 transition policy or candidate boundary is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransitionVerifierError(message)


def validate_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "id", "candidate_artifact_id", "backend"}
    missing = sorted(required - set(policy))
    if missing:
        raise TransitionVerifierError(
            "transition patch verifier policy missing field(s): " + ", ".join(missing)
        )
    _require(policy["schema_version"] == "0.4", "unsupported transition patch policy schema_version")
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
        raise TransitionVerifierError(
            "transition backend fields differ from v0.4 contract; "
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


def _v03_policy(policy: dict[str, Any]) -> dict[str, Any]:
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


def _removed_semantic_observation(
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
            # The strict legacy parser validates all file/hunk boundaries first.
            # In a valid patch accepted by that parser, a '-' line outside a hunk
            # can only be the '--- ' file header, which is excluded below.
            local_verifier.parse_unified_diff(patch_text)
            removed_lines = [
                line[1:]
                for line in patch_text.splitlines()
                if line.startswith("-") and not line.startswith("--- ")
            ]
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


def _candidate_patch_bytes(
    *,
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
) -> bytes:
    artifact = substring_patch_verifier._candidate_artifact(  # noqa: SLF001
        worker_result,
        policy["candidate_artifact_id"],
    )
    candidate_path = substring_patch_verifier._safe_candidate_path(  # noqa: SLF001
        candidate_root,
        artifact["locator"],
    )
    _require(
        candidate_path.is_file() and not candidate_path.is_symlink(),
        "candidate patch must be a regular non-symlink file",
    )
    return candidate_path.read_bytes()


def _recompute_result_status(result: dict[str, Any]) -> None:
    passed_count = sum(
        check["status"] == "passed" for check in result["checks"] if check.get("required") is True
    )
    failed_count = sum(
        check["status"] == "failed" for check in result["checks"] if check.get("required") is True
    )
    all_required_passed = failed_count == 0
    result["metrics"]["required_checks_passed"] = passed_count
    result["metrics"]["required_checks_failed"] = failed_count
    result["status"] = "passed" if all_required_passed else "failed"
    result["decision_support"]["recommendation"] = (
        "accept_candidate" if all_required_passed else "reject_candidate"
    )
    result["decision_support"]["confidence"] = 1.0
    result["decision_support"]["rationale"] = (
        "All WorkUnit-required checks passed, including explicit v0.4 added-and-removed line substring transition semantics."
        if all_required_passed
        else "At least one WorkUnit-required check failed under v0.4 added-and-removed line substring transition semantics."
    )


def verify_patch_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Verify a v0.4 transition-policy patch without executing candidate code."""

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
        raise TransitionVerifierError(
            "verifier-owned policy must not live inside the candidate root"
        )

    patch_bytes = _candidate_patch_bytes(
        worker_result=worker_result,
        policy=policy,
        candidate_root=candidate_root,
    )
    removed_semantic = _removed_semantic_observation(
        patch_bytes=patch_bytes,
        max_candidate_bytes=policy["backend"]["max_candidate_bytes"],
        required_substrings=list(policy["backend"]["required_removed_substrings"]),
    )

    # Reuse v0.3 for the entire hardened patch-verification core plus explicit
    # added-line substring semantics. The v0.4 layer adds only the required
    # removal transition and updates versioned provenance.
    result = substring_patch_verifier.verify_patch_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=_v03_policy(policy),
        candidate_root=candidate_root,
        policy_path=policy_path,
    )

    evidence_id = "removed-substring-semantic-observation"
    result["evidence"].append(
        {
            "id": evidence_id,
            "type": "test_output",
            "locator": "inline://removed-substring-semantic-observation",
            "digest": local_verifier.sha256_json(removed_semantic),
            "media_type": "application/json",
            "description": (
                "Canonical digest of explicit case-sensitive, single-removed-line "
                "substring matching for EvaluatorPlan v0.4."
            ),
        }
    )

    independent_check: dict[str, Any] | None = None
    for check in result["checks"]:
        if check["id"] != "independent-review":
            continue
        independent_check = check
        if evidence_id not in check["evidence_ids"]:
            check["evidence_ids"].append(evidence_id)
        diagnostics = json.loads(check.get("diagnostics") or "{}")
        diagnostics["semantic_removed_substrings"] = removed_semantic
        diagnostics["semantic_transition_mode"] = SEMANTIC_MODE
        check["diagnostics"] = json.dumps(
            diagnostics,
            sort_keys=True,
            separators=(",", ":"),
        )
        if removed_semantic["missing_substrings"] or removed_semantic["parse_error"]:
            check["status"] = "failed"
            check["summary"] = (
                "Independent metadata-only patch review rejected the candidate because "
                "the v0.4 transition did not remove every verifier-owned unsafe substring "
                "or another required check failed."
            )
        elif check["status"] == "passed":
            check["summary"] = (
                "Independent metadata-only patch review passed artifact/log integrity, "
                "strict patch structure, scope, v0.3 added-line substring checks, and "
                "v0.4 removed-line transition checks."
            )

    _require(independent_check is not None, "VerificationResult omitted independent-review check")

    if removed_semantic["missing_substrings"] or removed_semantic["parse_error"]:
        result["findings"].append(
            {
                "severity": "high",
                "category": "correctness",
                "summary": (
                    "Candidate patch does not remove every verifier-owned required unsafe "
                    "substring within individual validated-hunk removed lines."
                ),
                "path": worker_result["produced_artifacts"][0]["locator"],
            }
        )

    required_removed = list(policy["backend"]["required_removed_substrings"])
    result["metrics"]["required_removed_substring_count"] = len(required_removed)
    result["metrics"]["matched_removed_substring_count"] = (
        len(required_removed) - len(removed_semantic["missing_substrings"])
    )

    result["verifier"]["adapter_version"] = PATCH_TRANSITION_VERIFIER_VERSION
    result["independence"]["correlation_notes"] = (
        "Evaluator control is outside the candidate root; candidate code is never "
        "executed. Strict diff/provenance/log/scope checks reuse verifier v0.1.1; "
        "v0.2.0 supplies explicit added-line substring matching; v0.3.0 additionally "
        "requires verifier-owned unsafe substrings to occur in validated removed lines."
    )
    result["provenance"]["verifier_config_digest"] = canonical_digest(policy)
    tool_versions = result["provenance"]["environment"].setdefault("tool_versions", {})
    tool_versions["deterministic-patch-verifier"] = PATCH_TRANSITION_VERIFIER_VERSION
    tool_versions["deterministic-patch-verifier-added-substring-core"] = (
        ADDED_SUBSTRING_CORE_VERSION
    )
    result.setdefault("extensions", {})[
        "org.idkmesh.local_verifier.semantic_match_mode"
    ] = SEMANTIC_MODE
    result["extensions"]["org.idkmesh.local_verifier.added_substring_core_version"] = (
        ADDED_SUBSTRING_CORE_VERSION
    )

    _recompute_result_status(result)
    local_verifier.validate_schema(
        result,
        local_verifier.VERIFICATION_RESULT_SCHEMA,
        "VerificationResult",
    )
    validate_integrity(work_unit, worker_result, result)
    return result
