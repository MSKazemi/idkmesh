#!/usr/bin/env python3
"""Versioned semantic layer for deterministic patch verifier v0.2.0.

EvaluatorPlan v0.2 / patch verifier v0.1.1 intentionally keeps its historical
`required_added_text` behavior: every configured value must equal one complete
added line from a structurally valid unified-diff hunk.

This module adds a new, explicit contract for EvaluatorPlan v0.3:
`required_added_substrings`. Each configured fragment must occur verbatim inside
at least one added line returned by the *existing* strict v0.1.1 parser. The
parser, path checks, log checks, digest checks, ResultManifest binding, and
candidate-code non-execution behavior are reused rather than reimplemented.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import local_verifier
from provenance_integrity import validate_integrity

PATCH_VERIFIER_VERSION = "0.2.0"
POLICY_SCHEMA_VERSION = "0.3"
SEMANTIC_MODE = "substring_in_validated_added_line"


class SemanticVerifierError(local_verifier.VerifierError):
    """Raised when v0.2.0 semantic policy is malformed or unsafe."""


def validate_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "id", "candidate_artifact_id", "backend"}
    missing = sorted(required - set(policy))
    if missing:
        raise SemanticVerifierError(
            "semantic patch verifier policy missing field(s): " + ", ".join(missing)
        )
    if policy["schema_version"] != POLICY_SCHEMA_VERSION:
        raise SemanticVerifierError(
            f"semantic patch verifier requires policy schema_version={POLICY_SCHEMA_VERSION}"
        )
    if not isinstance(policy["candidate_artifact_id"], str) or not policy["candidate_artifact_id"]:
        raise SemanticVerifierError("candidate_artifact_id must be a non-empty string")

    backend = policy["backend"]
    if not isinstance(backend, dict) or backend.get("type") != "unified_diff":
        raise SemanticVerifierError("backend.type must be unified_diff")
    for field in ("max_candidate_bytes", "max_log_bytes"):
        if not isinstance(backend.get(field), int) or backend[field] < 1:
            raise SemanticVerifierError(f"backend.{field} must be a positive integer")

    required_logs = backend.get("required_log_types")
    if not isinstance(required_logs, list) or not required_logs:
        raise SemanticVerifierError("backend.required_log_types must be a non-empty list")
    if len(set(required_logs)) != len(required_logs):
        raise SemanticVerifierError("backend.required_log_types must be unique")
    if any(value not in local_verifier.RESULT_LOG_TYPES for value in required_logs):
        raise SemanticVerifierError("backend.required_log_types contains an unsupported log type")

    required = backend.get("required_added_substrings")
    if not isinstance(required, list) or not required:
        raise SemanticVerifierError(
            "backend.required_added_substrings must be a non-empty list"
        )
    if len(set(required)) != len(required):
        raise SemanticVerifierError("backend.required_added_substrings must be unique")
    for value in required:
        if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
            raise SemanticVerifierError(
                "backend.required_added_substrings entries must be non-empty single-line strings"
            )
    if "required_added_text" in backend:
        raise SemanticVerifierError(
            "v0.3 semantic policy may not reuse ambiguous v0.2 required_added_text"
        )
    if backend.get("require_nonempty_patch") is not True:
        raise SemanticVerifierError("semantic patch verifier requires require_nonempty_patch=true")
    if backend.get("verify_log_digests") is not True:
        raise SemanticVerifierError("semantic patch verifier requires verify_log_digests=true")


def substring_observation(
    added_lines: list[str], required_substrings: list[str]
) -> dict[str, Any]:
    matches: dict[str, list[str]] = {}
    missing: list[str] = []
    for expected in required_substrings:
        observed = [line for line in added_lines if expected in line]
        matches[expected] = observed
        if not observed:
            missing.append(expected)
    return {
        "semantic_mode": SEMANTIC_MODE,
        "required_added_substrings": required_substrings,
        "observed_added_lines": added_lines,
        "matches": matches,
        "missing_added_substrings": missing,
    }


def _missing_sentinel(fragment: str) -> str:
    digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
    return f"__IDKMESH_V020_MISSING_SUBSTRING_{digest}__"


def _legacy_policy_for_observation(
    policy: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Build a v0.1.1-compatible policy for all non-semantic checks.

    The legacy semantic check is deliberately fed complete observed added lines
    only when the v0.2.0 substring condition has independently matched. Missing
    fragments receive impossible deterministic sentinels so the reused verifier
    still fails its independent-review check. The resulting VerificationResult
    semantic evidence is replaced below with the explicit v0.2.0 observation.
    """

    backend = copy.deepcopy(policy["backend"])
    required_substrings = backend.pop("required_added_substrings")
    selected_lines: list[str] = []
    for fragment in required_substrings:
        lines = observation["matches"][fragment]
        value = lines[0] if lines else _missing_sentinel(fragment)
        if value not in selected_lines:
            selected_lines.append(value)
    backend["required_added_text"] = selected_lines
    return {
        "schema_version": "0.2",
        "id": policy["id"],
        "candidate_artifact_id": policy["candidate_artifact_id"],
        "backend": backend,
    }


def _candidate_added_lines(
    *, worker_result: dict[str, Any], policy: dict[str, Any], candidate_root: Path
) -> list[str]:
    artifact = local_verifier._declared_artifact(  # noqa: SLF001 - shared verifier kernel
        worker_result, policy["candidate_artifact_id"]
    )
    candidate_path = local_verifier._safe_candidate_path(  # noqa: SLF001
        candidate_root.resolve(), artifact["locator"]
    )
    if not candidate_path.is_file() or candidate_path.is_symlink():
        raise SemanticVerifierError("candidate patch must be a regular non-symlink file")
    patch_bytes = candidate_path.read_bytes()
    if len(patch_bytes) > policy["backend"]["max_candidate_bytes"]:
        # Let the reused verifier produce the canonical byte-limit failure; no
        # semantic fragment can be trusted from an over-limit candidate.
        return []
    try:
        patch_text = patch_bytes.decode("utf-8")
        _, added_lines = local_verifier.parse_unified_diff(patch_text)
    except (UnicodeDecodeError, local_verifier.VerifierError):
        # Structural failures are handled canonically by v0.1.1. Returning no
        # lines ensures v0.2.0 semantics also fail closed.
        return []
    return added_lines


def verify_patch_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Verify v0.3 substring semantics while reusing the v0.1.1 safety kernel."""

    validate_policy(policy)
    added_lines = _candidate_added_lines(
        worker_result=worker_result,
        policy=policy,
        candidate_root=candidate_root,
    )
    observation = substring_observation(
        added_lines, list(policy["backend"]["required_added_substrings"])
    )
    legacy_policy = _legacy_policy_for_observation(policy, observation)

    result = local_verifier.verify_patch_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=legacy_policy,
        candidate_root=candidate_root,
        policy_path=policy_path,
    )

    result["verifier"]["adapter_version"] = PATCH_VERIFIER_VERSION
    tool_versions = result["provenance"]["environment"]["tool_versions"]
    tool_versions["deterministic-patch-verifier"] = PATCH_VERIFIER_VERSION

    semantic_digest = local_verifier.sha256_json(observation)
    for evidence in result["evidence"]:
        if evidence["id"] == "patch-semantic-observation":
            evidence["digest"] = semantic_digest
            evidence["description"] = (
                "Canonical digest of explicit required-added-substring matches "
                "computed only from structurally validated unified-diff hunk additions."
            )
            break
    else:
        raise SemanticVerifierError("legacy verifier result omitted patch semantic evidence")

    independent_review = next(
        (check for check in result["checks"] if check["id"] == "independent-review"),
        None,
    )
    if independent_review is None:
        raise SemanticVerifierError("legacy verifier result omitted independent-review check")
    diagnostics = json.loads(independent_review.get("diagnostics", "{}"))
    diagnostics["semantic"] = observation
    independent_review["diagnostics"] = json.dumps(
        diagnostics, sort_keys=True, separators=(",", ":")
    )
    if independent_review["status"] == "passed":
        independent_review["summary"] = (
            "Independent metadata-only patch review passed artifact/log completeness and "
            "integrity, strict patch structure, scope, and explicit added-line substring checks."
        )

    missing = observation["missing_added_substrings"]
    semantic_findings = [
        finding
        for finding in result["findings"]
        if finding.get("category") == "correctness"
        and "required added text" in finding.get("summary", "")
    ]
    if missing:
        for finding in semantic_findings:
            finding["summary"] = (
                "Candidate patch does not contain every verifier-owned required substring "
                "inside structurally validated added lines."
            )
    else:
        # The derived legacy semantic expectation must be satisfied whenever all
        # explicit substrings matched. Any remaining legacy semantic finding would
        # indicate an adapter invariant failure rather than a candidate outcome.
        if semantic_findings:
            raise SemanticVerifierError(
                "substring semantics matched but legacy semantic kernel reported failure"
            )

    result["independence"]["correlation_notes"] = (
        "Evaluator policy is verifier-owned and outside the candidate root; candidate code is "
        "never executed. Patch structure/paths, artifact/log digests, required log coverage, "
        "and v0.2.0 substring matches over validated added lines are independently recomputed."
    )
    result.setdefault("extensions", {})[
        "org.idkmesh.local_verifier.semantic_match"
    ] = SEMANTIC_MODE

    local_verifier.validate_schema(
        result, local_verifier.VERIFICATION_RESULT_SCHEMA, "VerificationResult"
    )
    validate_integrity(work_unit, worker_result, result)
    return result
