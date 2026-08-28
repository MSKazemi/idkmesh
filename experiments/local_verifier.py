#!/usr/bin/env python3
"""Zero-cost executable independent verifier MVP for IDKMesh.

This verifier is deliberately small and safe. It does not execute candidate code,
call a network service, use secrets, or grant merge authority. It evaluates an
isolated JSON candidate using verifier-owned deterministic policy and emits the
canonical VerificationResult v0.1 contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
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
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "type": evidence_type,
        "locator": locator,
        "digest": digest,
        "media_type": "application/json",
        "description": description,
    }


def verify_candidate(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    policy: dict[str, Any],
    candidate_root: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Execute verifier-owned deterministic checks and return VerificationResult."""

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

    if worker_result["work_unit_id"] != work_unit["id"]:
        raise VerifierError("worker ResultManifest references a different Work Unit")
    if worker_result["work_unit_version"] != work_unit["version"]:
        raise VerifierError("worker ResultManifest Work Unit version mismatch")
    expected_work_unit_digest = canonical_digest(work_unit)
    if worker_result["provenance"]["work_unit_digest"] != expected_work_unit_digest:
        raise VerifierError("worker ResultManifest is not bound to the exact Work Unit")

    expected_validator_ids = {
        validator["id"] for validator in work_unit["validators"] if validator["required"]
    }
    requested_validator_ids = set(worker_result["verification_request"]["expected_validator_ids"])
    if not expected_validator_ids.issubset(requested_validator_ids):
        missing = sorted(expected_validator_ids - requested_validator_ids)
        raise VerifierError(
            "worker ResultManifest did not request required validator(s): " + ", ".join(missing)
        )

    artifact_id = policy["candidate_artifact_id"]
    matches = [
        artifact for artifact in worker_result["produced_artifacts"] if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise VerifierError("candidate_artifact_id must match exactly one produced artifact")
    artifact = matches[0]
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

    scope_observation = {
        "allowed_files": allowed_files,
        "observed_files": files,
    }
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
    status = "passed" if all_required_passed else "failed"
    recommendation = "accept_candidate" if all_required_passed else "reject_candidate"

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
            "correlation_notes": (
                "Verifier policy is loaded outside the isolated candidate root and candidate code is never executed."
            ),
        },
        "status": status,
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
            "recommendation": recommendation,
            "confidence": 1.0,
            "rationale": (
                "All verifier-owned deterministic checks passed."
                if all_required_passed
                else "One or more required verifier-owned deterministic checks failed."
            ),
        },
        "extensions": {
            "org.idkmesh.local_verifier.policy_id": policy["id"],
        },
    }

    validate_schema(
        verification_result,
        VERIFICATION_RESULT_SCHEMA,
        "VerificationResult",
    )
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
    work_unit = load_json(work_unit_path)
    worker_result = load_json(result_manifest_path)
    policy = load_json(policy_path)
    return verify_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=policy,
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

    verify_parser = subparsers.add_parser("verify", help="Verify one isolated candidate bundle.")
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

    self_test = subparsers.add_parser("self-test", help="Run known-good and deliberately bad fixtures.")
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
        default="examples/verifier/good",
    )
    self_test.add_argument(
        "--bad-result-manifest",
        default="examples/verifier/bad/result-manifest.json",
    )
    self_test.add_argument(
        "--bad-candidate-root",
        default="examples/verifier/bad",
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
