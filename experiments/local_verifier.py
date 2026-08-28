#!/usr/bin/env python3
"""Zero-cost executable independent verifier backends for IDKMesh.

This module is deliberately safe and small. It does not execute candidate code,
call a network service, use secrets, or grant merge authority. It currently
supports verifier-owned deterministic checks for JSON fixtures and unified-diff
candidate bundles, and emits the canonical VerificationResult v0.1 contract.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from provenance_integrity import canonical_digest, validate_integrity

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
WORK_UNIT_SCHEMA = SCHEMA_DIR / "work-unit-v0.2.schema.json"
RESULT_MANIFEST_SCHEMA = SCHEMA_DIR / "result-manifest-v0.1.schema.json"
VERIFICATION_RESULT_SCHEMA = SCHEMA_DIR / "verification-result-v0.1.schema.json"
VERIFIER_VERSION = "0.1"
PATCH_VERIFIER_VERSION = "0.1.1"
HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)
PATCH_METADATA_PREFIXES = (
    "index ",
    "old mode ",
    "new mode ",
    "new file mode ",
    "deleted file mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
)
RESULT_LOG_TYPES = {"stdout", "stderr", "trace", "tool_calls", "other"}


class VerifierError(RuntimeError):
    """Raised when verifier inputs/configuration are invalid or unsafe."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerifierError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifierError(f"{path} must contain a JSON object")
    return value


def load_schema(path: Path) -> dict[str, Any]:
    schema = load_json(path)
    Draft202012Validator.check_schema(schema)
    return schema


def validate_schema(instance: dict[str, Any], schema_path: Path, label: str) -> None:
    validator = Draft202012Validator(
        load_schema(schema_path),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    details = []
    for error in errors[:10]:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{location}: {error.message}")
    raise VerifierError(f"{label} failed schema validation: " + "; ".join(details))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(payload)


def resolve_repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise VerifierError(f"path escapes repository root: {raw}") from exc
    return path


def resolve_output_path(raw: str) -> Path:
    """Keep verifier-generated evidence inside the ignored results/ subtree."""

    path = resolve_repo_path(raw)
    relative = path.relative_to(ROOT)
    if not relative.parts or relative.parts[0] != "results":
        raise VerifierError(
            "verifier output must be under results/; canonical repository files are not writable"
        )
    return path


def validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "id",
        "candidate_artifact_id",
        "allowed_files",
        "max_candidate_bytes",
        "required_json",
    }
    missing = sorted(required - set(policy))
    if missing:
        raise VerifierError("verifier policy missing field(s): " + ", ".join(missing))
    if policy["schema_version"] != "0.1":
        raise VerifierError("unsupported verifier policy schema_version")
    if not isinstance(policy["candidate_artifact_id"], str) or not policy["candidate_artifact_id"]:
        raise VerifierError("candidate_artifact_id must be a non-empty string")
    if not isinstance(policy["allowed_files"], list) or not policy["allowed_files"]:
        raise VerifierError("allowed_files must be a non-empty list")
    if len(set(policy["allowed_files"])) != len(policy["allowed_files"]):
        raise VerifierError("allowed_files must be unique")
    for raw in policy["allowed_files"]:
        if not isinstance(raw, str) or not raw:
            raise VerifierError("allowed_files entries must be non-empty strings")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts:
            raise VerifierError(f"unsafe allowed_files entry: {raw}")
    if not isinstance(policy["max_candidate_bytes"], int) or policy["max_candidate_bytes"] < 1:
        raise VerifierError("max_candidate_bytes must be a positive integer")
    if not isinstance(policy["required_json"], dict):
        raise VerifierError("required_json must be an object")


def validate_patch_policy(policy: dict[str, Any]) -> None:
    required = {"schema_version", "id", "candidate_artifact_id", "backend"}
    missing = sorted(required - set(policy))
    if missing:
        raise VerifierError("patch verifier policy missing field(s): " + ", ".join(missing))
    if policy["schema_version"] != "0.2":
        raise VerifierError("unsupported patch verifier policy schema_version")
    if not isinstance(policy["candidate_artifact_id"], str) or not policy["candidate_artifact_id"]:
        raise VerifierError("candidate_artifact_id must be a non-empty string")
    backend = policy["backend"]
    if not isinstance(backend, dict) or backend.get("type") != "unified_diff":
        raise VerifierError("patch verifier backend.type must be unified_diff")
    for field in ("max_candidate_bytes", "max_log_bytes"):
        if not isinstance(backend.get(field), int) or backend[field] < 1:
            raise VerifierError(f"backend.{field} must be a positive integer")

    required_logs = backend.get("required_log_types")
    if not isinstance(required_logs, list) or not required_logs:
        raise VerifierError("backend.required_log_types must be a non-empty list")
    if len(set(required_logs)) != len(required_logs):
        raise VerifierError("backend.required_log_types must be unique")
    if any(value not in RESULT_LOG_TYPES for value in required_logs):
        raise VerifierError("backend.required_log_types contains an unsupported ResultManifest log type")

    required_text = backend.get("required_added_text")
    if not isinstance(required_text, list) or not required_text:
        raise VerifierError("backend.required_added_text must be a non-empty list")
    if len(set(required_text)) != len(required_text):
        raise VerifierError("backend.required_added_text must be unique")
    if any(not isinstance(value, str) or not value for value in required_text):
        raise VerifierError("backend.required_added_text entries must be non-empty strings")
    if backend.get("require_nonempty_patch") is not True:
        raise VerifierError("patch verifier requires backend.require_nonempty_patch=true")
    if backend.get("verify_log_digests") is not True:
        raise VerifierError("patch verifier requires backend.verify_log_digests=true")


def _safe_candidate_path(candidate_root: Path, locator: str) -> Path:
    posix = PurePosixPath(locator)
    if not locator or posix.is_absolute() or ".." in posix.parts:
        raise VerifierError(f"unsafe candidate locator: {locator!r}")
    path = (candidate_root / Path(*posix.parts)).resolve()
    try:
        path.relative_to(candidate_root)
    except ValueError as exc:
        raise VerifierError(f"candidate locator escapes candidate root: {locator}") from exc
    return path


def observed_files(candidate_root: Path) -> list[str]:
    values: list[str] = []
    for path in sorted(candidate_root.rglob("*")):
        if path.is_symlink():
            raise VerifierError(f"candidate root contains unsupported symlink: {path}")
        if path.is_file():
            values.append(path.relative_to(candidate_root).as_posix())
    return values


def _evidence(
    *,
    evidence_id: str,
    evidence_type: str,
    locator: str,
    digest: str,
    description: str,
    media_type: str = "application/json",
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "type": evidence_type,
        "locator": locator,
        "digest": digest,
        "media_type": media_type,
        "description": description,
    }


def _required_validator_ids(work_unit: dict[str, Any]) -> set[str]:
    return {
        validator["id"]
        for validator in work_unit["validators"]
        if validator.get("required") is True
    }


def _validate_worker_binding(work_unit: dict[str, Any], worker_result: dict[str, Any]) -> str:
    if worker_result["work_unit_id"] != work_unit["id"]:
        raise VerifierError("worker ResultManifest references a different Work Unit")
    if worker_result["work_unit_version"] != work_unit["version"]:
        raise VerifierError("worker ResultManifest Work Unit version mismatch")
    expected_work_unit_digest = canonical_digest(work_unit)
    if worker_result["provenance"]["work_unit_digest"] != expected_work_unit_digest:
        raise VerifierError("worker ResultManifest is not bound to the exact Work Unit")

    expected_validator_ids = _required_validator_ids(work_unit)
    requested_validator_ids = set(worker_result["verification_request"]["expected_validator_ids"])
    if not expected_validator_ids.issubset(requested_validator_ids):
        missing = sorted(expected_validator_ids - requested_validator_ids)
        raise VerifierError(
            "worker ResultManifest did not request required validator(s): " + ", ".join(missing)
        )
    return expected_work_unit_digest


def _declared_artifact(worker_result: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    matches = [
        artifact for artifact in worker_result["produced_artifacts"] if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise VerifierError("candidate_artifact_id must match exactly one produced artifact")
    return matches[0]


def _normalize_repo_path(raw: str) -> str | None:
    if raw == "/dev/null":
        return None
    value = raw
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise VerifierError(f"unsafe repository path in unified diff: {raw!r}")
    normalized = path.as_posix()
    if normalized in ("", "."):
        raise VerifierError(f"empty repository path in unified diff: {raw!r}")
    return normalized


def _parse_path_token(payload: str, label: str) -> str | None:
    try:
        parsed = shlex.split(payload)
    except ValueError as exc:
        raise VerifierError(f"invalid {label}: {payload!r}") from exc
    if len(parsed) != 1:
        raise VerifierError(f"{label} must contain exactly one path token")
    return _normalize_repo_path(parsed[0])


def parse_unified_diff(patch_text: str) -> tuple[list[str], list[str]]:
    """Parse the supported textual Git unified-diff subset and validate hunk counts.

    The v0.1.1 metadata-only verifier deliberately rejects binary/mode-only or
    structurally ambiguous patches. Semantic `+` lines count only while inside a
    syntactically valid, count-balanced `@@` hunk.
    """

    paths: set[str] = set()
    added_lines: list[str] = []
    current_diff_paths: set[str] | None = None
    file_header_paths: set[str] = set()
    saw_old_header = False
    saw_new_header = False
    saw_hunk = False
    hunk_old_remaining: int | None = None
    hunk_new_remaining: int | None = None

    def finish_hunk(line_number: int) -> None:
        nonlocal hunk_old_remaining, hunk_new_remaining
        if hunk_old_remaining is None:
            return
        if hunk_old_remaining != 0 or hunk_new_remaining != 0:
            raise VerifierError(
                "unified-diff hunk count mismatch before line "
                f"{line_number}: old_remaining={hunk_old_remaining}, "
                f"new_remaining={hunk_new_remaining}"
            )
        hunk_old_remaining = None
        hunk_new_remaining = None

    def finish_file(line_number: int) -> None:
        nonlocal current_diff_paths
        if current_diff_paths is None:
            return
        finish_hunk(line_number)
        if not saw_old_header or not saw_new_header or not saw_hunk:
            raise VerifierError(
                f"unified-diff file section ending before line {line_number} lacks ---/+++/@@ structure"
            )
        if file_header_paths != current_diff_paths:
            raise VerifierError(
                "unified-diff diff --git paths disagree with ---/+++ paths: "
                f"diff={sorted(current_diff_paths)}, headers={sorted(file_header_paths)}"
            )
        current_diff_paths = None

    lines = patch_text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if line.startswith("diff --git "):
            finish_file(line_number)
            try:
                parsed = shlex.split(line)
            except ValueError as exc:
                raise VerifierError(f"invalid diff --git header at line {line_number}: {line!r}") from exc
            if len(parsed) != 4:
                raise VerifierError(
                    f"diff --git header at line {line_number} must contain exactly two paths"
                )
            normalized = [_normalize_repo_path(token) for token in parsed[2:4]]
            if any(value is None for value in normalized):
                raise VerifierError("diff --git header may not use /dev/null")
            current_diff_paths = {value for value in normalized if value is not None}
            if not current_diff_paths:
                raise VerifierError("diff --git header did not name a repository path")
            paths.update(current_diff_paths)
            file_header_paths = set()
            saw_old_header = False
            saw_new_header = False
            saw_hunk = False
            hunk_old_remaining = None
            hunk_new_remaining = None
            continue

        if current_diff_paths is None:
            if line.strip():
                raise VerifierError(
                    f"content outside diff --git section at line {line_number}: {line!r}"
                )
            continue

        if hunk_old_remaining is not None:
            if line.startswith("@@ "):
                finish_hunk(line_number)
            elif line == "\\ No newline at end of file":
                continue
            else:
                if hunk_old_remaining == 0 and hunk_new_remaining == 0:
                    raise VerifierError(
                        f"unexpected content after completed hunk at line {line_number}: {line!r}"
                    )
                prefix = line[:1]
                if prefix == " ":
                    hunk_old_remaining -= 1
                    hunk_new_remaining -= 1
                elif prefix == "-":
                    hunk_old_remaining -= 1
                elif prefix == "+":
                    hunk_new_remaining -= 1
                    added_lines.append(line[1:])
                else:
                    raise VerifierError(
                        f"invalid unified-diff hunk line at {line_number}: {line!r}"
                    )
                if hunk_old_remaining < 0 or hunk_new_remaining < 0:
                    raise VerifierError(
                        f"unified-diff hunk exceeded declared line counts at line {line_number}"
                    )
                continue

        if line.startswith("@@ "):
            if not saw_old_header or not saw_new_header:
                raise VerifierError(f"hunk at line {line_number} appears before ---/+++ headers")
            match = HUNK_HEADER_RE.fullmatch(line)
            if match is None:
                raise VerifierError(f"invalid unified-diff hunk header at line {line_number}: {line!r}")
            old_count = int(match.group(2) if match.group(2) is not None else "1")
            new_count = int(match.group(4) if match.group(4) is not None else "1")
            hunk_old_remaining = old_count
            hunk_new_remaining = new_count
            saw_hunk = True
            continue

        if line.startswith("--- "):
            if saw_old_header or saw_new_header:
                raise VerifierError(f"duplicate/out-of-order --- header at line {line_number}")
            old_path = _parse_path_token(line[4:].strip(), "--- path header")
            if old_path is not None:
                file_header_paths.add(old_path)
                paths.add(old_path)
            saw_old_header = True
            continue

        if line.startswith("+++ "):
            if not saw_old_header or saw_new_header:
                raise VerifierError(f"out-of-order +++ header at line {line_number}")
            new_path = _parse_path_token(line[4:].strip(), "+++ path header")
            if new_path is not None:
                file_header_paths.add(new_path)
                paths.add(new_path)
            saw_new_header = True
            continue

        if saw_old_header or saw_new_header:
            raise VerifierError(
                f"unexpected content between file headers and hunk at line {line_number}: {line!r}"
            )
        if not line.startswith(PATCH_METADATA_PREFIXES):
            raise VerifierError(
                f"unsupported unified-diff metadata at line {line_number}: {line!r}"
            )

    finish_file(len(lines) + 1)
    if not paths:
        raise VerifierError("unified diff contains no repository paths")
    return sorted(paths), added_lines


def parse_unified_diff_paths(patch_text: str) -> list[str]:
    """Backward-compatible path-only view of the strict unified-diff parser."""

    paths, _ = parse_unified_diff(patch_text)
    return paths


def parse_added_lines(patch_text: str) -> list[str]:
    """Return only additions inside structurally valid unified-diff hunks."""

    _, added = parse_unified_diff(patch_text)
    return added


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def verify_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Execute verifier-owned deterministic JSON checks."""

    validate_schema(work_unit, WORK_UNIT_SCHEMA, "Work Unit")
    validate_schema(worker_result, RESULT_MANIFEST_SCHEMA, "ResultManifest")
    validate_policy(policy)

    candidate_root = candidate_root.resolve()
    if not candidate_root.is_dir():
        raise VerifierError(f"candidate root is not a directory: {candidate_root}")
    policy_path = policy_path.resolve()
    try:
        policy_path.relative_to(candidate_root)
    except ValueError:
        pass
    else:
        raise VerifierError("verifier-owned policy must not live inside the candidate root")

    expected_work_unit_digest = _validate_worker_binding(work_unit, worker_result)
    artifact = _declared_artifact(worker_result, policy["candidate_artifact_id"])
    candidate_path = _safe_candidate_path(candidate_root, artifact["locator"])
    if not candidate_path.is_file():
        raise VerifierError(f"candidate artifact not found: {artifact['locator']}")
    if candidate_path.is_symlink():
        raise VerifierError("candidate artifact may not be a symlink")

    started_at = utc_now()
    started = time.monotonic()

    candidate_bytes = candidate_path.read_bytes()
    observed_digest = sha256_bytes(candidate_bytes)
    digest_passed = observed_digest == artifact["digest"]

    files = observed_files(candidate_root)
    allowed_files = sorted(policy["allowed_files"])
    scope_passed = files == allowed_files

    parse_error: str | None = None
    observed_json: Any = None
    if len(candidate_bytes) > policy["max_candidate_bytes"]:
        parse_error = (
            f"candidate is {len(candidate_bytes)} bytes, exceeding "
            f"max_candidate_bytes={policy['max_candidate_bytes']}"
        )
    else:
        try:
            observed_json = json.loads(candidate_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_error = str(exc)
    acceptance_passed = parse_error is None and observed_json == policy["required_json"]

    scope_observation = {"allowed_files": allowed_files, "observed_files": files}
    acceptance_observation = {
        "expected": policy["required_json"],
        "observed": observed_json,
        "parse_error": parse_error,
    }

    checks = [
        {
            "id": "artifact-digest",
            "type": "reproduction",
            "required": True,
            "status": "passed" if digest_passed else "failed",
            "summary": (
                "Observed candidate SHA-256 matches the worker ResultManifest."
                if digest_passed
                else "Observed candidate SHA-256 does not match the worker ResultManifest."
            ),
            "evidence_ids": ["candidate-artifact-hash"],
        },
        {
            "id": "candidate-scope",
            "type": "review",
            "required": True,
            "status": "passed" if scope_passed else "failed",
            "summary": (
                "Candidate root contains only verifier-policy-approved files."
                if scope_passed
                else "Candidate root contains a missing or unauthorized file set."
            ),
            "evidence_ids": ["candidate-scope-observation"],
        },
        {
            "id": "independent-acceptance",
            "type": "test",
            "required": True,
            "status": "passed" if acceptance_passed else "failed",
            "summary": (
                "Verifier-owned deterministic acceptance expectation passed."
                if acceptance_passed
                else "Verifier-owned deterministic acceptance expectation failed."
            ),
            "evidence_ids": ["acceptance-observation"],
            "diagnostics": parse_error or "",
        },
    ]

    evidence = [
        _evidence(
            evidence_id="candidate-artifact-hash",
            evidence_type="artifact_hash",
            locator=artifact["locator"],
            digest=observed_digest,
            media_type=artifact.get("media_type", "application/octet-stream"),
            description="SHA-256 observed directly from candidate artifact bytes.",
        ),
        _evidence(
            evidence_id="candidate-scope-observation",
            evidence_type="trace",
            locator="inline://candidate-scope",
            digest=sha256_json(scope_observation),
            description="Canonical digest of allowed and observed candidate file lists.",
        ),
        _evidence(
            evidence_id="acceptance-observation",
            evidence_type="test_output",
            locator="inline://acceptance-observation",
            digest=sha256_json(acceptance_observation),
            description="Canonical digest of verifier-owned expected and observed JSON values.",
        ),
    ]

    findings: list[dict[str, Any]] = []
    if not digest_passed:
        findings.append(
            {
                "severity": "high",
                "category": "provenance",
                "summary": "Candidate artifact bytes do not match worker-declared digest.",
                "path": artifact["locator"],
            }
        )
    if not scope_passed:
        findings.append(
            {
                "severity": "high",
                "category": "scope",
                "summary": "Candidate file set violates verifier-owned scope policy.",
            }
        )
    if not acceptance_passed:
        findings.append(
            {
                "severity": "high",
                "category": "correctness",
                "summary": "Candidate failed verifier-owned deterministic acceptance expectations.",
                "path": artifact["locator"],
            }
        )

    passed_count = sum(check["status"] == "passed" for check in checks)
    failed_count = sum(check["status"] == "failed" for check in checks)
    all_required_passed = failed_count == 0
    elapsed = max(0.0, time.monotonic() - started)
    verification_result = {
        "schema_version": "0.1",
        "id": f"{worker_result['id']}/local-verification",
        "result_manifest_id": worker_result["id"],
        "work_unit_id": worker_result["work_unit_id"],
        "work_unit_version": worker_result["work_unit_version"],
        "attempt": worker_result["attempt"],
        "verifier": {
            "id": "idkmesh-local-verifier",
            "type": "system",
            "adapter": "deterministic-json-verifier",
            "adapter_version": VERIFIER_VERSION,
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": worker_result["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": False,
            "correlation_notes": "Verifier policy is loaded outside the isolated candidate root and candidate code is never executed.",
        },
        "status": "passed" if all_required_passed else "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "required_checks_passed": passed_count,
            "required_checks_failed": failed_count,
            "candidate_bytes": len(candidate_bytes),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(worker_result),
            "work_unit_digest": expected_work_unit_digest,
            "source_revision": worker_result["provenance"]["source_revision"],
            "verifier_config_digest": canonical_digest(policy),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {
                    "idkmesh-local-verifier": VERIFIER_VERSION,
                    "jsonschema": "installed",
                },
            },
        },
        "decision_support": {
            "recommendation": "accept_candidate" if all_required_passed else "reject_candidate",
            "confidence": 1.0,
            "rationale": (
                "All verifier-owned deterministic checks passed."
                if all_required_passed
                else "One or more required verifier-owned deterministic checks failed."
            ),
        },
        "extensions": {"org.idkmesh.local_verifier.policy_id": policy["id"]},
    }
    validate_schema(verification_result, VERIFICATION_RESULT_SCHEMA, "VerificationResult")
    validate_integrity(work_unit, worker_result, verification_result)
    return verification_result


def verify_patch_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Verify a unified-diff bundle without executing candidate code."""

    validate_schema(work_unit, WORK_UNIT_SCHEMA, "Work Unit")
    validate_schema(worker_result, RESULT_MANIFEST_SCHEMA, "ResultManifest")
    validate_patch_policy(policy)

    candidate_root = candidate_root.resolve()
    if not candidate_root.is_dir():
        raise VerifierError(f"candidate root is not a directory: {candidate_root}")
    policy_path = policy_path.resolve()
    try:
        policy_path.relative_to(candidate_root)
    except ValueError:
        pass
    else:
        raise VerifierError("verifier-owned policy must not live inside the candidate root")

    expected_work_unit_digest = _validate_worker_binding(work_unit, worker_result)
    required_ids = _required_validator_ids(work_unit)
    expected_patch_ids = {"result-manifest-schema", "independent-review"}
    if required_ids != expected_patch_ids:
        raise VerifierError(
            "deterministic patch verifier v0.1.1 requires exactly these required validators: "
            + ", ".join(sorted(expected_patch_ids))
        )

    backend = policy["backend"]
    artifact = _declared_artifact(worker_result, policy["candidate_artifact_id"])
    candidate_path = _safe_candidate_path(candidate_root, artifact["locator"])
    if not candidate_path.is_file() or candidate_path.is_symlink():
        raise VerifierError("candidate patch must be a regular non-symlink file")

    started_at = utc_now()
    started = time.monotonic()
    patch_bytes = candidate_path.read_bytes()
    patch_size_ok = len(patch_bytes) <= backend["max_candidate_bytes"]
    observed_patch_digest = sha256_bytes(patch_bytes)
    artifact_digest_ok = observed_patch_digest == artifact["digest"]

    decode_error: str | None = None
    patch_text = ""
    changed_paths: list[str] = []
    added: list[str] = []
    try:
        patch_text = patch_bytes.decode("utf-8")
        changed_paths, added = parse_unified_diff(patch_text)
    except (UnicodeDecodeError, VerifierError) as exc:
        decode_error = str(exc)

    nonempty_patch_ok = bool(patch_bytes) and bool(changed_paths) and decode_error is None

    constraints = work_unit["constraints"]
    allowed_patterns = list(constraints.get("allowed_paths", []))
    forbidden_patterns = list(constraints.get("forbidden_paths", []))
    write_patterns = list(work_unit["permissions"].get("filesystem_write", []))
    scope_violations: list[str] = []
    for path in changed_paths:
        if forbidden_patterns and _matches_any(path, forbidden_patterns):
            scope_violations.append(f"forbidden path changed: {path}")
        if not allowed_patterns or not _matches_any(path, allowed_patterns):
            scope_violations.append(f"path outside constraints.allowed_paths: {path}")
        if not write_patterns or not _matches_any(path, write_patterns):
            scope_violations.append(f"path outside permissions.filesystem_write: {path}")
    scope_ok = nonempty_patch_ok and not scope_violations

    missing_added_text = [
        expected for expected in backend["required_added_text"] if expected not in added
    ]
    semantic_ok = nonempty_patch_ok and not missing_added_text

    required_log_types = list(backend["required_log_types"])
    log_type_counts = {log_type: 0 for log_type in required_log_types}
    seen_log_locators: set[str] = set()
    log_observations: list[dict[str, Any]] = []
    log_integrity_ok = True
    for index, log in enumerate(worker_result.get("logs", []), start=1):
        locator = log["locator"]
        log_type = log["type"]
        declared_digest = log.get("digest")
        if log_type in log_type_counts:
            log_type_counts[log_type] += 1
        observation: dict[str, Any] = {
            "index": index,
            "type": log_type,
            "locator": locator,
            "declared_digest": declared_digest,
        }

        if locator in seen_log_locators:
            observation["error"] = "duplicate log locator"
            observation["matches"] = False
            log_integrity_ok = False
            log_observations.append(observation)
            continue
        seen_log_locators.add(locator)

        if not declared_digest:
            observation["error"] = "log digest is required by evaluator policy"
            observation["matches"] = False
            log_integrity_ok = False
            log_observations.append(observation)
            continue

        log_path = _safe_candidate_path(candidate_root, locator)
        if not log_path.is_file() or log_path.is_symlink():
            observation["error"] = "log is missing or not a regular file"
            observation["matches"] = False
            log_integrity_ok = False
        else:
            data = log_path.read_bytes()
            observed = sha256_bytes(data)
            within_limit = len(data) <= backend["max_log_bytes"]
            matches = observed == declared_digest and within_limit
            observation.update(
                {
                    "observed_digest": observed,
                    "bytes": len(data),
                    "within_limit": within_limit,
                    "matches": matches,
                }
            )
            if not matches:
                log_integrity_ok = False
        log_observations.append(observation)

    log_coverage_violations: list[str] = []
    for log_type in required_log_types:
        count = log_type_counts[log_type]
        if count == 0:
            log_coverage_violations.append(f"required log type missing: {log_type}")
        elif count > 1:
            log_coverage_violations.append(
                f"required log type must appear exactly once: {log_type} (observed {count})"
            )
    if log_coverage_violations:
        log_integrity_ok = False

    log_observation_payload = {
        "required_log_types": required_log_types,
        "observed_type_counts": log_type_counts,
        "coverage_violations": log_coverage_violations,
        "logs": log_observations,
    }

    worker_status_ok = worker_result["status"] == "succeeded"
    independent_review_ok = all(
        [
            patch_size_ok,
            artifact_digest_ok,
            nonempty_patch_ok,
            log_integrity_ok,
            scope_ok,
            semantic_ok,
            worker_status_ok,
        ]
    )

    patch_observation = {
        "artifact_locator": artifact["locator"],
        "declared_digest": artifact["digest"],
        "observed_digest": observed_patch_digest,
        "bytes": len(patch_bytes),
        "within_limit": patch_size_ok,
        "decode_error": decode_error,
    }
    scope_observation = {
        "changed_paths": changed_paths,
        "allowed_paths": allowed_patterns,
        "forbidden_paths": forbidden_patterns,
        "filesystem_write": write_patterns,
        "violations": scope_violations,
    }
    semantic_observation = {
        "required_added_text": backend["required_added_text"],
        "observed_added_lines": added,
        "missing_added_text": missing_added_text,
    }
    status_observation = {"worker_status": worker_result["status"]}

    evidence = [
        _evidence(
            evidence_id="result-manifest-canonical",
            evidence_type="attestation",
            locator="inline://result-manifest-canonical",
            digest=canonical_digest(worker_result),
            description="Canonical digest of the schema-valid worker ResultManifest evaluated by the verifier.",
        ),
        _evidence(
            evidence_id="candidate-patch-hash",
            evidence_type="artifact_hash",
            locator=artifact["locator"],
            digest=observed_patch_digest,
            media_type=artifact.get("media_type", "text/x-diff"),
            description="SHA-256 observed directly from candidate patch bytes.",
        ),
        _evidence(
            evidence_id="log-integrity-observation",
            evidence_type="trace",
            locator="inline://log-integrity",
            digest=sha256_json(log_observation_payload),
            description="Canonical digest of evaluator-required log coverage and independently recomputed log integrity observations.",
        ),
        _evidence(
            evidence_id="patch-scope-observation",
            evidence_type="static_analysis",
            locator="inline://patch-scope",
            digest=sha256_json(scope_observation),
            description="Canonical digest of independently parsed unified-diff paths and WorkUnit scope checks.",
        ),
        _evidence(
            evidence_id="patch-semantic-observation",
            evidence_type="test_output",
            locator="inline://patch-semantic",
            digest=sha256_json(semantic_observation),
            description="Canonical digest of verifier-owned required-added-text checks from validated hunks only.",
        ),
        _evidence(
            evidence_id="worker-status-observation",
            evidence_type="trace",
            locator="inline://worker-status",
            digest=sha256_json(status_observation),
            description="Canonical digest of the worker execution status observed by the verifier.",
        ),
    ]

    diagnostics = {
        "artifact": patch_observation,
        "logs": log_observation_payload,
        "scope": scope_observation,
        "semantic": semantic_observation,
        "worker_status": worker_result["status"],
    }
    checks = [
        {
            "id": "result-manifest-schema",
            "type": "schema",
            "required": True,
            "status": "passed",
            "summary": "Worker ResultManifest is schema-valid and bound to the exact WorkUnit.",
            "evidence_ids": ["result-manifest-canonical"],
        },
        {
            "id": "independent-review",
            "type": "review",
            "required": True,
            "status": "passed" if independent_review_ok else "failed",
            "summary": (
                "Independent metadata-only patch review passed artifact/log completeness and integrity, strict patch structure, scope, and verifier-owned semantic checks."
                if independent_review_ok
                else "Independent metadata-only patch review rejected the candidate bundle."
            ),
            "evidence_ids": [
                "candidate-patch-hash",
                "log-integrity-observation",
                "patch-scope-observation",
                "patch-semantic-observation",
                "worker-status-observation",
            ],
            "diagnostics": json.dumps(diagnostics, sort_keys=True, separators=(",", ":")),
        },
    ]

    findings: list[dict[str, Any]] = []
    if not patch_size_ok:
        findings.append(
            {
                "severity": "high",
                "category": "policy",
                "summary": "Candidate patch exceeds verifier-owned byte limit.",
                "path": artifact["locator"],
            }
        )
    if not artifact_digest_ok:
        findings.append(
            {
                "severity": "high",
                "category": "provenance",
                "summary": "Candidate patch bytes do not match worker-declared digest.",
                "path": artifact["locator"],
            }
        )
    if decode_error is not None or not nonempty_patch_ok:
        findings.append(
            {
                "severity": "high",
                "category": "correctness",
                "summary": "Candidate patch is empty, undecodable, or structurally invalid as a supported textual Git unified diff.",
                "path": artifact["locator"],
            }
        )
    if not log_integrity_ok:
        findings.append(
            {
                "severity": "high",
                "category": "provenance",
                "summary": "Evaluator-required worker logs are missing/duplicated, lack digests, are oversized, missing, or do not match declared digests.",
            }
        )
    for violation in scope_violations:
        findings.append({"severity": "high", "category": "scope", "summary": violation})
    if not semantic_ok:
        findings.append(
            {
                "severity": "high",
                "category": "correctness",
                "summary": "Candidate patch does not contain all verifier-owned required added text inside validated hunks.",
                "path": artifact["locator"],
            }
        )
    if not worker_status_ok:
        findings.append(
            {
                "severity": "medium",
                "category": "policy",
                "summary": f"Worker ResultManifest status is {worker_result['status']!r}, not 'succeeded'.",
            }
        )

    passed_count = sum(check["status"] == "passed" for check in checks)
    failed_count = sum(check["status"] == "failed" for check in checks)
    all_required_passed = failed_count == 0
    elapsed = max(0.0, time.monotonic() - started)
    verification_result = {
        "schema_version": "0.1",
        "id": f"{worker_result['id']}/patch-verification",
        "result_manifest_id": worker_result["id"],
        "work_unit_id": worker_result["work_unit_id"],
        "work_unit_version": worker_result["work_unit_version"],
        "attempt": worker_result["attempt"],
        "verifier": {
            "id": "idkmesh-local-verifier",
            "type": "system",
            "adapter": "deterministic-patch-verifier",
            "adapter_version": PATCH_VERIFIER_VERSION,
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": worker_result["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": False,
            "correlation_notes": "Evaluator policy is verifier-owned and outside the candidate root; candidate code is never executed. Patch structure/paths, artifact/log digests, required log coverage, and semantic markers are independently recomputed.",
        },
        "status": "passed" if all_required_passed else "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "required_checks_passed": passed_count,
            "required_checks_failed": failed_count,
            "candidate_bytes": len(patch_bytes),
            "changed_path_count": len(changed_paths),
            "log_count": len(log_observations),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(worker_result),
            "work_unit_digest": expected_work_unit_digest,
            "source_revision": worker_result["provenance"]["source_revision"],
            "verifier_config_digest": canonical_digest(policy),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {
                    "idkmesh-local-verifier": VERIFIER_VERSION,
                    "deterministic-patch-verifier": PATCH_VERIFIER_VERSION,
                    "jsonschema": "installed",
                },
            },
        },
        "decision_support": {
            "recommendation": "accept_candidate" if all_required_passed else "reject_candidate",
            "confidence": 1.0,
            "rationale": (
                "Both WorkUnit-required validators passed using independently observed metadata-only evidence."
                if all_required_passed
                else "At least one WorkUnit-required validator failed under independently observed metadata-only evidence."
            ),
        },
        "extensions": {
            "org.idkmesh.local_verifier.policy_id": policy["id"],
            "org.idkmesh.local_verifier.backend": "unified_diff",
        },
    }
    validate_schema(verification_result, VERIFICATION_RESULT_SCHEMA, "VerificationResult")
    validate_integrity(work_unit, worker_result, verification_result)
    return verification_result


def semantic_signature(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result["status"],
        "checks": [
            (check["id"], check["status"], tuple(check["evidence_ids"]))
            for check in result["checks"]
        ],
        "evidence": [(item["id"], item["digest"]) for item in result["evidence"]],
        "recommendation": result["decision_support"]["recommendation"],
    }


def run_fixture(
    *,
    work_unit_path: Path,
    result_manifest_path: Path,
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    return verify_candidate(
        work_unit=load_json(work_unit_path),
        worker_result=load_json(result_manifest_path),
        policy=load_json(policy_path),
        candidate_root=candidate_root,
        policy_path=policy_path,
    )


def cmd_verify(args: argparse.Namespace) -> int:
    work_unit_path = resolve_repo_path(args.work_unit)
    result_manifest_path = resolve_repo_path(args.result_manifest)
    candidate_root = resolve_repo_path(args.candidate_root)
    policy_path = resolve_repo_path(args.policy)
    output_path = resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=result_manifest_path,
        candidate_root=candidate_root,
        policy_path=policy_path,
    )
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{result['status']}: wrote {output_path}; "
        f"recommendation={result['decision_support']['recommendation']}"
    )
    return 0 if result["status"] == "passed" else 1


def cmd_self_test(args: argparse.Namespace) -> int:
    work_unit_path = resolve_repo_path(args.work_unit)
    policy_path = resolve_repo_path(args.policy)
    try:
        resolve_output_path("README.md")
    except VerifierError:
        pass
    else:
        raise VerifierError("canonical repository path was accepted as verifier output")
    allowed_output = resolve_output_path("results/verification/self-test.json")
    if allowed_output.relative_to(ROOT).parts[0] != "results":
        raise VerifierError("results/ output path guard rejected its own invariant")

    good = run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=resolve_repo_path(args.good_result_manifest),
        candidate_root=resolve_repo_path(args.good_candidate_root),
        policy_path=policy_path,
    )
    good_again = run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=resolve_repo_path(args.good_result_manifest),
        candidate_root=resolve_repo_path(args.good_candidate_root),
        policy_path=policy_path,
    )
    bad = run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=resolve_repo_path(args.bad_result_manifest),
        candidate_root=resolve_repo_path(args.bad_candidate_root),
        policy_path=policy_path,
    )

    if good["status"] != "passed" or good["decision_support"]["recommendation"] != "accept_candidate":
        raise VerifierError("known-good fixture was not accepted by verifier-owned checks")
    if semantic_signature(good) != semantic_signature(good_again):
        raise VerifierError("known-good fixture did not reproduce the same semantic verification result")
    if bad["status"] != "failed" or bad["decision_support"]["recommendation"] != "reject_candidate":
        raise VerifierError("deliberately incorrect fixture was not rejected")

    bad_checks = {check["id"]: check["status"] for check in bad["checks"]}
    if bad_checks.get("artifact-digest") != "passed":
        raise VerifierError("bad fixture should have an honest matching artifact digest")
    if bad_checks.get("candidate-scope") != "passed":
        raise VerifierError("bad fixture should remain within the allowed candidate scope")
    if bad_checks.get("independent-acceptance") != "failed":
        raise VerifierError("bad fixture must fail the verifier-owned acceptance check")

    print(
        "OK: executable verifier accepts known-good candidate, rejects self-consistent incorrect "
        "candidate via verifier-owned check, emits schema-valid provenance-bound VerificationResult, "
        "reproduces semantic outcomes, and restricts generated evidence to results/"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify one isolated JSON candidate bundle.")
    verify_parser.add_argument("--work-unit", required=True)
    verify_parser.add_argument("--result-manifest", required=True)
    verify_parser.add_argument("--candidate-root", required=True)
    verify_parser.add_argument("--policy", required=True)
    verify_parser.add_argument(
        "--output",
        required=True,
        help="Repository-relative generated evidence path under results/.",
    )
    verify_parser.set_defaults(func=cmd_verify)

    self_test = subparsers.add_parser(
        "self-test",
        help="Run known-good and deliberately bad JSON fixtures.",
    )
    self_test.add_argument(
        "--work-unit",
        default="examples/work-units/local-verifier-smoke.work-unit.json",
    )
    self_test.add_argument(
        "--policy",
        default="verification/fixtures/verifier-smoke-policy.json",
    )
    self_test.add_argument(
        "--good-result-manifest",
        default="examples/verifier/good/result-manifest.json",
    )
    self_test.add_argument(
        "--good-candidate-root",
        default="examples/verifier/good/candidate-root",
    )
    self_test.add_argument(
        "--bad-result-manifest",
        default="examples/verifier/bad/result-manifest.json",
    )
    self_test.add_argument(
        "--bad-candidate-root",
        default="examples/verifier/bad/candidate-root",
    )
    self_test.set_defaults(func=cmd_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (VerifierError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
