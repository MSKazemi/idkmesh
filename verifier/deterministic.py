#!/usr/bin/env python3
"""Deterministic, read-only verifier for IDKMesh candidate result bundles.

This verifier never executes candidate code. It validates the canonical Work Unit
and ResultManifest contracts, recomputes declared SHA-256 digests, checks the
worker's declared Work Unit digest, and evaluates patch paths against the Work
Unit scope. Unsupported required validators are reported as inconclusive rather
than silently treated as passed.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import platform
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

VERIFIER_ID_DEFAULT = "idkmesh/deterministic-bundle-verifier"
VERIFIER_VERSION = "0.1"
SUPPORTED_VALIDATORS = {
    "result-manifest-schema",
    "work-unit-digest",
    "artifact-digests",
    "path-policy",
}


class VerificationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validator_for(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_instance(instance: Any, schema_path: Path, label: str) -> None:
    errors = sorted(
        validator_for(schema_path).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    lines = [f"{label} failed {len(errors)} schema check(s):"]
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        lines.append(f"  - {location}: {error.message}")
    raise VerificationError("\n".join(lines))


def resolve_under(root: Path, locator: str) -> Path:
    candidate = Path(locator)
    if candidate.is_absolute():
        raise VerificationError(f"artifact locator must be relative: {locator}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise VerificationError(f"artifact locator escapes artifact root: {locator}") from exc
    return resolved


def normalize_repo_path(raw: str) -> str:
    raw = raw.replace("\\", "/")
    path = PurePosixPath(raw)
    normalized = str(path)
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def path_matches(path: str, pattern: str) -> bool:
    path = normalize_repo_path(path)
    pattern = normalize_repo_path(pattern)
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(char in pattern for char in "*?["):
        return fnmatch.fnmatchcase(path, pattern)
    return path == pattern


def parse_patch_paths(path: Path) -> list[str]:
    changed: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("+++ "):
                continue
            raw = line[4:].strip()
            if not raw:
                continue
            try:
                parts = shlex.split(raw)
                token = parts[0] if parts else raw
            except ValueError:
                token = raw.split("\t", 1)[0]
            if token == "/dev/null":
                continue
            if token.startswith("b/"):
                token = token[2:]
            changed.append(normalize_repo_path(token))
    return sorted(set(changed))


def build_check(
    check_id: str,
    check_type: str,
    required: bool,
    status: str,
    summary: str,
    evidence_ids: list[str] | None = None,
    diagnostics: str | None = None,
) -> dict[str, Any]:
    check: dict[str, Any] = {
        "id": check_id,
        "type": check_type,
        "required": required,
        "status": status,
        "summary": summary,
        "evidence_ids": evidence_ids or [],
    }
    if diagnostics:
        check["diagnostics"] = diagnostics
    return check


def verify(
    repo_root: Path,
    artifact_root: Path,
    work_unit_path: Path,
    result_manifest_path: Path,
    output_path: Path,
    verifier_id: str,
) -> tuple[dict[str, Any], int]:
    started_at = utc_now()
    timer = time.perf_counter()

    schema_dir = repo_root / "schemas"
    work_unit_schema = schema_dir / "work-unit-v0.2.schema.json"
    result_manifest_schema = schema_dir / "result-manifest-v0.1.schema.json"
    verification_schema = schema_dir / "verification-result-v0.1.schema.json"

    work_unit = load_json(work_unit_path)
    result_manifest = load_json(result_manifest_path)
    validate_instance(work_unit, work_unit_schema, str(work_unit_path))
    validate_instance(result_manifest, result_manifest_schema, str(result_manifest_path))

    if result_manifest["work_unit_id"] != work_unit["id"]:
        raise VerificationError(
            f"ResultManifest work_unit_id mismatch: {result_manifest['work_unit_id']!r} != {work_unit['id']!r}"
        )
    if result_manifest["work_unit_version"] != work_unit["version"]:
        raise VerificationError(
            "ResultManifest work_unit_version mismatch: "
            f"{result_manifest['work_unit_version']} != {work_unit['version']}"
        )
    worker_id = result_manifest["worker"]["id"]
    if verifier_id == worker_id:
        raise VerificationError("verifier id must differ from worker id")

    validator_specs = {item["id"]: item for item in work_unit["validators"]}
    requested = set(result_manifest["verification_request"]["expected_validator_ids"])
    required_ids = {item["id"] for item in work_unit["validators"] if item["required"]}
    all_ids = sorted(required_ids | requested)

    checks: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    digest_failures = 0
    path_violations = 0

    schema_required = validator_specs.get("result-manifest-schema", {}).get("required", False)
    checks.append(
        build_check(
            "result-manifest-schema",
            "schema",
            schema_required,
            "passed",
            "Worker ResultManifest validates against result-manifest-v0.1.schema.json.",
        )
    )

    declared_work_unit_digest = result_manifest["provenance"]["work_unit_digest"]
    actual_work_unit_digest = canonical_digest(work_unit)
    work_unit_digest_ok = declared_work_unit_digest == actual_work_unit_digest
    work_unit_digest_required = validator_specs.get("work-unit-digest", {}).get("required", False)
    checks.append(
        build_check(
            "work-unit-digest",
            "reproduction",
            work_unit_digest_required,
            "passed" if work_unit_digest_ok else "failed",
            "Worker provenance Work Unit digest matches independently recomputed canonical digest."
            if work_unit_digest_ok
            else "Worker provenance Work Unit digest does not match independently recomputed canonical digest.",
        )
    )
    if not work_unit_digest_ok:
        findings.append(
            {
                "severity": "high",
                "category": "provenance",
                "summary": "Worker-declared Work Unit digest does not match verifier recomputation.",
            }
        )

    artifact_evidence_ids: list[str] = []
    digest_diagnostics: list[str] = []
    all_declared_files: list[tuple[str, str, str, str]] = []
    for artifact in result_manifest["produced_artifacts"]:
        all_declared_files.append(
            (f"artifact:{artifact['id']}", artifact["locator"], artifact["digest"], artifact["type"])
        )
    for index, log in enumerate(result_manifest["logs"]):
        if "digest" in log:
            all_declared_files.append(
                (f"log:{index}:{log['type']}", log["locator"], log["digest"], "log")
            )

    for label, locator, declared_digest, artifact_type in all_declared_files:
        try:
            artifact_path = resolve_under(artifact_root, locator)
            if not artifact_path.is_file():
                raise VerificationError(f"declared file does not exist: {locator}")
            actual_digest = file_digest(artifact_path)
            evidence_id = "hash-" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
            evidence.append(
                {
                    "id": evidence_id,
                    "type": "artifact_hash",
                    "locator": locator,
                    "digest": actual_digest,
                    "description": f"Verifier-computed SHA-256 for {label}.",
                }
            )
            artifact_evidence_ids.append(evidence_id)
            if actual_digest != declared_digest:
                digest_failures += 1
                digest_diagnostics.append(
                    f"{label}: declared {declared_digest}, computed {actual_digest}"
                )
                findings.append(
                    {
                        "severity": "high",
                        "category": "provenance",
                        "summary": f"Digest mismatch for {label}.",
                        "path": locator,
                    }
                )
        except VerificationError as exc:
            digest_failures += 1
            digest_diagnostics.append(f"{label}: {exc}")
            findings.append(
                {
                    "severity": "high",
                    "category": "provenance",
                    "summary": str(exc),
                    "path": locator,
                }
            )

    artifact_digest_required = validator_specs.get("artifact-digests", {}).get("required", False)
    checks.append(
        build_check(
            "artifact-digests",
            "reproduction",
            artifact_digest_required,
            "passed" if digest_failures == 0 else "failed",
            "All declared artifact/log digests matched independently computed SHA-256 values."
            if digest_failures == 0
            else f"{digest_failures} declared artifact/log digest check(s) failed.",
            artifact_evidence_ids,
            "\n".join(digest_diagnostics) if digest_diagnostics else None,
        )
    )

    patch_artifacts = [
        artifact for artifact in result_manifest["produced_artifacts"] if artifact["type"] == "patch"
    ]
    path_policy_required = validator_specs.get("path-policy", {}).get("required", False)
    path_diagnostics: list[str] = []
    path_evidence_ids: list[str] = []
    if not patch_artifacts:
        path_status = "failed" if path_policy_required else "skipped"
        path_summary = "No patch artifact was available for path-policy verification."
    else:
        allowed = work_unit["constraints"]["allowed_paths"]
        forbidden = work_unit["constraints"]["forbidden_paths"]
        for artifact in patch_artifacts:
            try:
                patch_path = resolve_under(artifact_root, artifact["locator"])
                changed_paths = parse_patch_paths(patch_path)
                matching_evidence = next(
                    (
                        item["id"]
                        for item in evidence
                        if item["locator"] == artifact["locator"] and item["type"] == "artifact_hash"
                    ),
                    None,
                )
                if matching_evidence:
                    path_evidence_ids.append(matching_evidence)
                if not changed_paths:
                    path_violations += 1
                    path_diagnostics.append(
                        f"{artifact['id']}: patch contains no parseable target paths"
                    )
                    continue
                for changed_path in changed_paths:
                    forbidden_match = any(
                        path_matches(changed_path, pattern) for pattern in forbidden
                    )
                    allowed_match = any(path_matches(changed_path, pattern) for pattern in allowed)
                    if forbidden_match or not allowed_match:
                        path_violations += 1
                        reason = "forbidden" if forbidden_match else "outside allowed_paths"
                        path_diagnostics.append(f"{changed_path}: {reason}")
                        findings.append(
                            {
                                "severity": "high",
                                "category": "scope",
                                "summary": f"Changed path violates Work Unit scope: {reason}.",
                                "path": changed_path,
                            }
                        )
            except VerificationError as exc:
                path_violations += 1
                path_diagnostics.append(f"{artifact['id']}: {exc}")
        path_status = "passed" if path_violations == 0 else "failed"
        path_summary = (
            "All patch target paths are inside allowed_paths and outside forbidden_paths."
            if path_violations == 0
            else f"{path_violations} patch path-policy violation(s) detected."
        )

    checks.append(
        build_check(
            "path-policy",
            "policy",
            path_policy_required,
            path_status,
            path_summary,
            sorted(set(path_evidence_ids)),
            "\n".join(path_diagnostics) if path_diagnostics else None,
        )
    )

    existing_check_ids = {check["id"] for check in checks}
    for validator_id in all_ids:
        if validator_id in existing_check_ids:
            continue
        spec = validator_specs.get(validator_id, {})
        checks.append(
            build_check(
                validator_id,
                spec.get("type", "other"),
                bool(spec.get("required", validator_id in required_ids)),
                "inconclusive",
                "This deterministic verifier does not implement this validator.",
                diagnostics=(
                    f"Supported validator ids: {', '.join(sorted(SUPPORTED_VALIDATORS))}"
                ),
            )
        )

    required_checks = [check for check in checks if check["required"]]
    failed_required = [
        check for check in required_checks if check["status"] in {"failed", "error"}
    ]
    incomplete_required = [
        check
        for check in required_checks
        if check["status"] in {"inconclusive", "skipped"}
    ]

    independent_required = work_unit["verification_policy"]["independent_from_worker"]
    independent = verifier_id != worker_id
    if independent_required and not independent:
        failed_required.append(
            build_check(
                "verifier-independence",
                "policy",
                True,
                "failed",
                "Verifier identity must differ from worker identity.",
            )
        )

    if failed_required:
        status = "failed"
        recommendation = "reject_candidate"
        confidence = 1.0
        rationale = "One or more required deterministic verification checks failed."
        exit_code = 1
    elif incomplete_required:
        status = "inconclusive"
        recommendation = "insufficient_evidence"
        confidence = 1.0
        rationale = "One or more required validators are not implemented by this verifier."
        exit_code = 1
    else:
        status = "passed"
        recommendation = "accept_candidate"
        confidence = 1.0
        rationale = (
            "All required deterministic checks implemented by this verifier passed. "
            "This is decision support, not merge authority."
        )
        exit_code = 0

    elapsed = max(0.0, time.perf_counter() - timer)
    verifier_config = {
        "id": verifier_id,
        "version": VERIFIER_VERSION,
        "supported_validators": sorted(SUPPORTED_VALIDATORS),
        "executes_candidate_code": False,
        "network_required": False,
    }
    verification_result = {
        "schema_version": "0.1",
        "id": f"verification/{result_manifest['id'].replace('/', '-')}",
        "result_manifest_id": result_manifest["id"],
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": result_manifest["attempt"],
        "verifier": {
            "id": verifier_id,
            "type": "system",
            "adapter": "deterministic-bundle-verifier",
            "adapter_version": VERIFIER_VERSION,
        },
        "independence": {
            "independent_from_worker": independent,
            "worker_id_observed": worker_id,
            "shared_model_family": False,
            "shared_runtime": True,
            "correlation_notes": (
                "No model is used. The verifier may share a host runtime but does not execute "
                "candidate code and recomputes evidence from bundle bytes."
            ),
        },
        "status": status,
        "started_at": started_at,
        "finished_at": utc_now(),
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "declared_file_count": len(all_declared_files),
            "digest_failures": digest_failures,
            "patch_artifact_count": len(patch_artifacts),
            "path_violations": path_violations,
            "unsupported_required_validators": len(incomplete_required),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(result_manifest),
            "work_unit_digest": actual_work_unit_digest,
            "source_revision": result_manifest["provenance"]["source_revision"],
            "verifier_config_digest": canonical_digest(verifier_config),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {
                    "deterministic-bundle-verifier": VERIFIER_VERSION,
                },
            },
        },
        "decision_support": {
            "recommendation": recommendation,
            "confidence": confidence,
            "rationale": rationale,
        },
        "extensions": {
            "org.idkmesh.verifier.executes_candidate_code": False,
            "org.idkmesh.verifier.network_used": False,
        },
    }
    validate_instance(verification_result, verification_schema, "generated VerificationResult")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(verification_result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return verification_result, exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-unit", required=True, help="Path to canonical Work Unit JSON.")
    parser.add_argument(
        "--result-manifest", required=True, help="Path to worker ResultManifest JSON."
    )
    parser.add_argument(
        "--artifact-root",
        default=".",
        help="Trusted root under which ResultManifest locators are resolved.",
    )
    parser.add_argument(
        "--output",
        default="results/verification-result.json",
        help="Path to write the schema-valid VerificationResult.",
    )
    parser.add_argument(
        "--verifier-id",
        default=VERIFIER_ID_DEFAULT,
        help="Stable verifier identity; must differ from the worker id.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        result, exit_code = verify(
            repo_root=repo_root,
            artifact_root=Path(args.artifact_root),
            work_unit_path=Path(args.work_unit),
            result_manifest_path=Path(args.result_manifest),
            output_path=Path(args.output),
            verifier_id=args.verifier_id,
        )
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"{result['status'].upper()}: {result['decision_support']['recommendation']} "
        f"({len(result['checks'])} checks, {len(result['findings'])} findings)"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
