#!/usr/bin/env python3
"""Safe local independent validator for IDKMesh candidate workspaces.

v0.1 is intentionally metadata-only: it validates schemas, path authority,
artifact hashes, provenance, and verification requests without executing
candidate-controlled code. A future sandbox backend may add hidden tests.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from harness import (
    HarnessError,
    ROOT,
    VERIFICATION_RESULT_SCHEMA,
    WORKER_RESULT_SCHEMA,
    WORK_UNIT_SCHEMA,
    canonical_digest,
    load_json,
    validate_instance,
    validate_verification_result_contract,
)

VALIDATOR_VERSION = "0.1"
EVALUATOR_PLAN_SCHEMA = ROOT / "schemas" / "evaluator-plan-v0.1.schema.json"
SUPPORTED_BUILTINS = {
    "input_schema",
    "scope",
    "artifact_digest",
    "provenance",
    "verification_request",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def normalize_relpath(raw: str) -> str:
    if not raw or "\\" in raw:
        raise HarnessError(f"unsafe or empty repository-relative path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HarnessError(f"unsafe repository-relative path: {raw!r}")
    return path.as_posix()


def path_matches_scope(path: str, scope: str) -> bool:
    scope = normalize_relpath(scope.rstrip("/"))
    return path == scope or path.startswith(scope + "/")


def is_ignored(path: str, ignore_paths: list[str]) -> bool:
    return any(path_matches_scope(path, item) for item in ignore_paths)


def resolve_inside(root: Path, raw: str) -> Path:
    rel = normalize_relpath(raw)
    candidate = (root / Path(*PurePosixPath(rel).parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise HarnessError(f"path escapes candidate root: {raw}") from exc
    return candidate


def snapshot_tree(
    root: Path,
    ignore_paths: list[str],
    reject_symlinks: bool,
) -> tuple[dict[str, str], list[str]]:
    root = root.resolve()
    if not root.is_dir():
        raise HarnessError(f"candidate root is not a directory: {root}")

    normalized_ignores = [normalize_relpath(item.rstrip("/")) for item in ignore_paths]
    files: dict[str, str] = {}
    symlinks: list[str] = []

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        rel_dir = current_path.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            rel = f"{rel_dir}/{dirname}".lstrip("/")
            if is_ignored(rel, normalized_ignores):
                continue
            path = current_path / dirname
            if path.is_symlink():
                symlinks.append(rel)
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            rel = f"{rel_dir}/{filename}".lstrip("/")
            if is_ignored(rel, normalized_ignores):
                continue
            path = current_path / filename
            if path.is_symlink():
                symlinks.append(rel)
                if reject_symlinks:
                    continue
            if path.is_file():
                files[rel] = sha256_file(path)

    return files, sorted(symlinks)


def baseline_map(plan: dict[str, Any]) -> dict[str, str]:
    baseline: dict[str, str] = {}
    for entry in plan["baseline"]["files"]:
        path = normalize_relpath(entry["path"])
        if path in baseline:
            raise HarnessError(f"duplicate path in evaluator baseline: {path}")
        baseline[path] = entry["digest"]
    return baseline


def compute_changes(
    baseline: dict[str, str], candidate: dict[str, str]
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for path in sorted(set(baseline) | set(candidate)):
        if path not in baseline:
            changes.append({"path": path, "change": "added"})
        elif path not in candidate:
            changes.append({"path": path, "change": "deleted"})
        elif baseline[path] != candidate[path]:
            changes.append({"path": path, "change": "modified"})
    return changes


def authorize_change(work_unit: dict[str, Any], path: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    allowed = work_unit["constraints"]["allowed_paths"]
    forbidden = work_unit["constraints"]["forbidden_paths"]
    writable = work_unit["permissions"]["filesystem_write"]

    if not any(path_matches_scope(path, item) for item in allowed):
        reasons.append("outside constraints.allowed_paths")
    if any(path_matches_scope(path, item) for item in forbidden):
        reasons.append("inside constraints.forbidden_paths")
    if not any(path_matches_scope(path, item) for item in writable):
        reasons.append("outside permissions.filesystem_write")
    return (not reasons), reasons


def safe_check_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")
    return cleaned or "check"


def write_check_evidence(
    bundle_root: Path,
    check_id: str,
    evidence_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_dir = bundle_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_check_id(check_id) + ".json"
    path = evidence_dir / filename
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
    return {
        "id": f"evidence/{check_id}",
        "type": evidence_type,
        "locator": f"evidence/{filename}",
        "digest": sha256_file(path),
        "media_type": "application/json",
        "description": f"Deterministic evidence emitted by local validator check {check_id}.",
    }


def build_finding(
    severity: str,
    category: str,
    summary: str,
    path: str | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "severity": severity,
        "category": category,
        "summary": summary,
    }
    if path is not None:
        finding["path"] = path
    return finding


def check_input_schema(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    payload = {
        "work_unit_schema": WORK_UNIT_SCHEMA.name,
        "result_manifest_schema": WORKER_RESULT_SCHEMA.name,
        "evaluator_plan_schema": EVALUATOR_PLAN_SCHEMA.name,
        "status": "passed",
    }
    return "passed", "Input contracts are schema-valid.", payload, []


def check_scope(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    changes = context["changes"]
    symlinks = context["symlinks"]
    violations: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for item in changes:
        authorized, reasons = authorize_change(work_unit, item["path"])
        if not authorized:
            violation = {**item, "reasons": reasons}
            violations.append(violation)
            findings.append(
                build_finding(
                    "high",
                    "scope",
                    f"Unauthorized {item['change']} path: {', '.join(reasons)}",
                    item["path"],
                )
            )

    if symlinks and plan["policy"]["reject_symlinks"]:
        for path in symlinks:
            violations.append({"path": path, "change": "symlink", "reasons": ["symlink rejected"]})
            findings.append(
                build_finding(
                    "high",
                    "security",
                    "Candidate workspace contains a symlink; metadata-only v0.1 rejects symlinks to avoid path-boundary ambiguity.",
                    path,
                )
            )

    payload = {
        "baseline_file_count": len(context["baseline"]),
        "candidate_file_count": len(context["candidate_snapshot"]),
        "changes": changes,
        "symlinks": symlinks,
        "violations": violations,
    }
    if violations:
        return "failed", f"Found {len(violations)} scope/security violation(s).", payload, findings
    return "passed", f"All {len(changes)} detected change(s) stay inside declared write authority.", payload, findings


def check_artifact_digest(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    candidate_root: Path = context["candidate_root"]
    checks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    failures = 0

    for artifact in result_manifest["produced_artifacts"]:
        row: dict[str, Any] = {
            "id": artifact["id"],
            "locator": artifact["locator"],
            "declared_digest": artifact["digest"],
        }
        try:
            path = resolve_inside(candidate_root, artifact["locator"])
        except HarnessError as exc:
            failures += 1
            row.update({"status": "failed", "error": str(exc)})
            findings.append(build_finding("high", "provenance", str(exc)))
            checks.append(row)
            continue

        if not path.is_file():
            failures += 1
            row.update({"status": "failed", "error": "artifact is missing or not a regular file"})
            findings.append(
                build_finding(
                    "high",
                    "provenance",
                    "Produced artifact locator is missing or is not a regular file.",
                    artifact["locator"],
                )
            )
            checks.append(row)
            continue

        observed = sha256_file(path)
        row["observed_digest"] = observed
        if observed != artifact["digest"]:
            failures += 1
            row["status"] = "failed"
            findings.append(
                build_finding(
                    "high",
                    "provenance",
                    "Produced artifact digest does not match the candidate file.",
                    artifact["locator"],
                )
            )
        else:
            row["status"] = "passed"
        checks.append(row)

    payload = {"artifacts": checks, "failure_count": failures}
    if failures:
        return "failed", f"{failures} produced artifact digest check(s) failed.", payload, findings
    return "passed", f"Verified {len(checks)} produced artifact digest(s).", payload, findings


def check_provenance(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    observed_work_unit_digest = canonical_digest(work_unit)
    expected_work_unit_digest = plan["binding"]["work_unit_digest"]
    result_work_unit_digest = result_manifest["provenance"]["work_unit_digest"]
    expected_revision = plan["source_revision"]
    result_revision = result_manifest["provenance"]["source_revision"]

    failures: list[str] = []
    findings: list[dict[str, Any]] = []
    if observed_work_unit_digest != expected_work_unit_digest:
        failures.append("evaluator plan is bound to a different WorkUnit digest")
    if result_work_unit_digest != observed_work_unit_digest:
        failures.append("ResultManifest WorkUnit digest does not match the supplied WorkUnit")
    if plan["policy"]["require_source_revision_match"] and result_revision != expected_revision:
        failures.append("ResultManifest source revision does not match evaluator plan source revision")

    for summary in failures:
        findings.append(build_finding("high", "provenance", summary))

    payload = {
        "observed_work_unit_digest": observed_work_unit_digest,
        "expected_work_unit_digest": expected_work_unit_digest,
        "result_manifest_work_unit_digest": result_work_unit_digest,
        "expected_source_revision": expected_revision,
        "result_manifest_source_revision": result_revision,
        "failures": failures,
    }
    if failures:
        return "failed", "; ".join(failures), payload, findings
    return "passed", "WorkUnit digest and source revision provenance match the trusted evaluator binding.", payload, findings


def check_verification_request(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    produced = {item["id"] for item in result_manifest["produced_artifacts"]}
    requested_artifacts = set(result_manifest["verification_request"]["evidence_artifact_ids"])
    requested_validators = set(result_manifest["verification_request"]["expected_validator_ids"])
    required_validators = {
        item["id"] for item in work_unit["validators"] if item["required"]
    }
    plan_validators = {item["id"] for item in plan["checks"]}

    missing_artifacts = sorted(requested_artifacts - produced)
    omitted_required = sorted(required_validators - requested_validators)
    uncovered_required = sorted(required_validators - plan_validators)
    failures: list[str] = []
    findings: list[dict[str, Any]] = []
    if missing_artifacts:
        failures.append("verification request references unknown artifacts: " + ", ".join(missing_artifacts))
    if omitted_required:
        failures.append("worker verification request omits required validators: " + ", ".join(omitted_required))
    if uncovered_required:
        failures.append("evaluator plan does not cover required validators: " + ", ".join(uncovered_required))

    for summary in failures:
        findings.append(build_finding("medium", "policy", summary))

    payload = {
        "produced_artifact_ids": sorted(produced),
        "requested_artifact_ids": sorted(requested_artifacts),
        "required_validator_ids": sorted(required_validators),
        "requested_validator_ids": sorted(requested_validators),
        "evaluator_plan_check_ids": sorted(plan_validators),
        "failures": failures,
    }
    if failures:
        return "failed", "; ".join(failures), payload, findings
    return "passed", "Worker verification request is complete and covered by the trusted evaluator plan.", payload, findings


CHECKS = {
    "input_schema": (check_input_schema, "trace"),
    "scope": (check_scope, "trace"),
    "artifact_digest": (check_artifact_digest, "artifact_hash"),
    "provenance": (check_provenance, "trace"),
    "verification_request": (check_verification_request, "trace"),
}


def ensure_plan_outside_candidate(plan_path: Path, candidate_root: Path) -> None:
    plan_resolved = plan_path.resolve()
    candidate_resolved = candidate_root.resolve()
    try:
        plan_resolved.relative_to(candidate_resolved)
    except ValueError:
        return
    raise HarnessError(
        "evaluator plan is inside the candidate workspace; independent verification control data must be verifier-owned"
    )


def validate_bindings(
    work_unit: dict[str, Any],
    result_manifest: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    if result_manifest["work_unit_id"] != work_unit["id"]:
        raise HarnessError("ResultManifest work_unit_id does not match WorkUnit")
    if result_manifest["work_unit_version"] != work_unit["version"]:
        raise HarnessError("ResultManifest work_unit_version does not match WorkUnit")
    if plan["binding"]["work_unit_id"] != work_unit["id"]:
        raise HarnessError("EvaluatorPlan work_unit_id does not match WorkUnit")
    if plan["binding"]["work_unit_version"] != work_unit["version"]:
        raise HarnessError("EvaluatorPlan work_unit_version does not match WorkUnit")
    if plan["binding"]["work_unit_digest"] != canonical_digest(work_unit):
        raise HarnessError("EvaluatorPlan work_unit_digest does not match WorkUnit")

    if work_unit["verification_policy"]["independent_from_worker"]:
        if plan["verifier"]["id"] == result_manifest["worker"]["id"]:
            raise HarnessError("independent verifier id must differ from worker id")

    check_ids: set[str] = set()
    for check in plan["checks"]:
        if check["id"] in check_ids:
            raise HarnessError(f"duplicate evaluator check id: {check['id']}")
        check_ids.add(check["id"])
        if check["builtin"] not in SUPPORTED_BUILTINS:
            raise HarnessError(f"unsupported evaluator builtin: {check['builtin']}")


def shared_model_family(result_manifest: dict[str, Any], plan: dict[str, Any]) -> bool:
    worker_model = result_manifest["worker"].get("model")
    verifier_model = plan["verifier"].get("model")
    if not worker_model or not verifier_model:
        return False
    return (
        worker_model.get("provider") == verifier_model.get("provider")
        and worker_model.get("name") == verifier_model.get("name")
    )


def run_verification(
    work_unit_path: Path,
    result_manifest_path: Path,
    plan_path: Path,
    candidate_root: Path,
    output_dir: Path,
) -> Path:
    started_at = utc_now()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    work_unit = load_json(work_unit_path)
    result_manifest = load_json(result_manifest_path)
    plan = load_json(plan_path)
    validate_instance(work_unit, WORK_UNIT_SCHEMA, str(work_unit_path))
    validate_instance(result_manifest, WORKER_RESULT_SCHEMA, str(result_manifest_path))
    validate_instance(plan, EVALUATOR_PLAN_SCHEMA, str(plan_path))
    validate_bindings(work_unit, result_manifest, plan)

    candidate_root = candidate_root.resolve()
    output_dir = output_dir.resolve()
    if plan["policy"]["require_plan_outside_candidate_root"]:
        ensure_plan_outside_candidate(plan_path, candidate_root)
    try:
        output_dir.relative_to(candidate_root)
    except ValueError:
        pass
    else:
        raise HarnessError("verification output directory must be outside the candidate workspace")

    output_dir.mkdir(parents=True, exist_ok=True)
    baseline = baseline_map(plan)
    candidate_snapshot, symlinks = snapshot_tree(
        candidate_root,
        plan["baseline"].get("ignore_paths", []),
        plan["policy"]["reject_symlinks"],
    )
    changes = compute_changes(baseline, candidate_snapshot)
    context = {
        "candidate_root": candidate_root,
        "baseline": baseline,
        "candidate_snapshot": candidate_snapshot,
        "changes": changes,
        "symlinks": symlinks,
    }

    checks: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for spec in plan["checks"]:
        func, evidence_type = CHECKS[spec["builtin"]]
        status, summary, payload, check_findings = func(
            work_unit, result_manifest, plan, context
        )
        evidence_record = write_check_evidence(
            output_dir, spec["id"], evidence_type, payload
        )
        evidence.append(evidence_record)
        findings.extend(check_findings)
        checks.append(
            {
                "id": spec["id"],
                "type": spec["type"],
                "required": spec["required"],
                "status": status,
                "summary": summary,
                "evidence_ids": [evidence_record["id"]],
                "diagnostics": json.dumps(payload, sort_keys=True),
            }
        )

    work_unit_required_ids = {
        item["id"] for item in work_unit["validators"] if item["required"]
    }
    plan_required_ids = {item["id"] for item in plan["checks"] if item["required"]}
    required_ids = work_unit_required_ids | plan_required_ids
    check_ids = {item["id"] for item in checks}
    for missing_id in sorted(work_unit_required_ids - check_ids):
        checks.append(
            {
                "id": missing_id,
                "type": "other",
                "required": True,
                "status": "inconclusive",
                "summary": "Required WorkUnit validator is not implemented by the supplied EvaluatorPlan.",
                "evidence_ids": [],
                "diagnostics": "Evaluator plan coverage gap.",
            }
        )
        findings.append(
            build_finding(
                "medium",
                "policy",
                f"Required validator {missing_id!r} is not covered by the evaluator plan.",
            )
        )

    required_statuses = [
        item["status"] for item in checks if item["id"] in required_ids
    ]
    if any(status in {"failed", "error"} for status in required_statuses):
        overall_status = "failed"
        recommendation = "reject_candidate"
        confidence = 1.0
        rationale = "At least one required deterministic verification check failed."
    elif any(status != "passed" for status in required_statuses):
        overall_status = "inconclusive"
        recommendation = "insufficient_evidence"
        confidence = 1.0
        rationale = "At least one required validator lacks conclusive evidence."
    else:
        overall_status = "passed"
        recommendation = "accept_candidate"
        confidence = 1.0
        rationale = (
            "All required checks in this metadata-only evaluator plan passed. "
            "This is confidence in the deterministic policy evaluation, not a claim of semantic correctness beyond the checks declared by the WorkUnit."
        )

    finished_at = utc_now()
    verification_result = {
        "schema_version": "0.1",
        "id": f"{result_manifest['id']}/verification/{safe_check_id(plan['id'])}",
        "result_manifest_id": result_manifest["id"],
        "work_unit_id": result_manifest["work_unit_id"],
        "work_unit_version": result_manifest["work_unit_version"],
        "attempt": result_manifest["attempt"],
        "verifier": plan["verifier"],
        "independence": {
            "independent_from_worker": plan["verifier"]["id"] != result_manifest["worker"]["id"],
            "worker_id_observed": result_manifest["worker"]["id"],
            "shared_model_family": shared_model_family(result_manifest, plan),
            "shared_runtime": True,
            "correlation_notes": (
                "Local verifier may share a host with the worker, but evaluator control data is outside the candidate root. "
                "v0.1 does not execute candidate-controlled code."
            ),
        },
        "status": overall_status,
        "started_at": started_at,
        "finished_at": finished_at,
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "changed_path_count": len(changes),
            "finding_count": len(findings),
            "produced_artifact_count": len(result_manifest["produced_artifacts"]),
        },
        "resources": {
            "wall_seconds": max(0.0, time.perf_counter() - wall_start),
            "cpu_seconds": max(0.0, time.process_time() - cpu_start),
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(result_manifest),
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": plan["source_revision"],
            "verifier_config_digest": canonical_digest(plan),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {"idkmesh-local-validator": VALIDATOR_VERSION},
            },
        },
        "decision_support": {
            "recommendation": recommendation,
            "confidence": confidence,
            "rationale": rationale,
        },
        "extensions": {
            "org.idkmesh.validator.execution_mode": plan["execution_mode"],
            "org.idkmesh.validator.evaluator_plan_id": plan["id"],
            "org.idkmesh.validator.evaluator_visibility": plan["visibility"],
            "org.idkmesh.validator.candidate_code_executed": False,
        },
    }

    result_path = output_dir / "verification-result.json"
    with result_path.open("w", encoding="utf-8") as handle:
        json.dump(verification_result, handle, sort_keys=True, indent=2)
        handle.write("\n")

    validate_instance(
        verification_result,
        VERIFICATION_RESULT_SCHEMA,
        str(result_path),
    )
    validate_verification_result_contract(
        result_path,
        result_manifest,
        {work_unit["id"]: work_unit},
    )
    return result_path


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")


def build_self_test_documents(candidate_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validator_ids = [
        "input-schema",
        "scope",
        "artifact-digest",
        "provenance",
        "verification-request",
    ]
    work_unit: dict[str, Any] = {
        "schema_version": "0.2",
        "id": "validator/self-test-work-unit",
        "version": 1,
        "kind": "testing",
        "objective": "Exercise the local independent validator without executing candidate-controlled code.",
        "inputs": [],
        "outputs": [
            {
                "id": "candidate-output",
                "type": "file",
                "description": "Self-test candidate artifact.",
                "media_type": "text/plain",
            }
        ],
        "dependencies": [],
        "requirements": {
            "capabilities": ["local-filesystem"],
            "resources": {
                "cpu_cores_min": 0.1,
                "memory_mb_min": 32,
                "disk_mb_min": 1,
                "gpu": "none",
                "accelerator_capabilities": [],
            },
        },
        "constraints": {
            "allowed_paths": ["src/"],
            "forbidden_paths": ["secrets/"],
            "policies": ["Metadata-only verification; do not execute candidate code."],
        },
        "uncertainty": [],
        "security": {
            "risk_class": "low",
            "data_classification": "public",
            "minimum_worker_trust": "untrusted",
            "sandbox_required": False,
            "notes": "Self-test uses only static files.",
        },
        "permissions": {
            "network": "none",
            "filesystem_write": ["src/"],
            "secrets": [],
            "process_execution": False,
        },
        "verification_policy": {
            "strategy": "all_required",
            "independent_from_worker": True,
            "minimum_independent_verifiers": 1,
            "acceptance_rule": "All required deterministic metadata checks must pass.",
        },
        "validators": [
            {"id": "input-schema", "type": "schema", "required": True},
            {"id": "scope", "type": "other", "required": True},
            {"id": "artifact-digest", "type": "other", "required": True},
            {"id": "provenance", "type": "other", "required": True},
            {"id": "verification-request", "type": "other", "required": True},
        ],
        "evidence_requirements": [
            {"type": "trace", "required": True},
            {"type": "artifact_hash", "required": True},
        ],
        "budget": {
            "wall_seconds": 5,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
            "project_spend_usd_max": 0,
            "paid_fallback_allowed": False,
        },
        "provenance": {
            "created_by": "IDKMesh local validator self-test",
            "creator_type": "system",
            "source": "experiments/local_validator.py",
        },
        "failure_semantics": {
            "retryable": False,
            "max_attempts": 1,
            "on_failure": "stop",
        },
        "extensions": {},
    }
    work_unit_digest = canonical_digest(work_unit)
    output_digest = sha256_file(candidate_root / "src" / "output.txt")
    result_manifest: dict[str, Any] = {
        "schema_version": "0.1",
        "id": "validator/self-test-result",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": "self-test-worker",
            "type": "system",
            "adapter": "fixture",
            "adapter_version": "0.1",
        },
        "status": "succeeded",
        "started_at": "2026-08-28T00:00:00Z",
        "finished_at": "2026-08-28T00:00:01Z",
        "produced_artifacts": [
            {
                "id": "candidate-output",
                "type": "file",
                "locator": "src/output.txt",
                "digest": output_digest,
                "media_type": "text/plain",
                "description": "Self-test output.",
            }
        ],
        "logs": [],
        "metrics": {},
        "resources": {"wall_seconds": 1.0},
        "self_report": {"summary": "Fixture completed.", "claims": []},
        "provenance": {
            "work_unit_digest": work_unit_digest,
            "source_revision": "self-test-base",
            "environment": {"platform": "fixture", "tool_versions": {}},
        },
        "verification_request": {
            "expected_validator_ids": validator_ids,
            "evidence_artifact_ids": ["candidate-output"],
        },
        "extensions": {},
    }
    baseline_digest = sha256_file(candidate_root / "src" / "input.txt")
    plan: dict[str, Any] = {
        "schema_version": "0.1",
        "id": "validator/self-test-plan",
        "binding": {
            "work_unit_id": work_unit["id"],
            "work_unit_version": work_unit["version"],
            "work_unit_digest": work_unit_digest,
        },
        "visibility": "public",
        "execution_mode": "metadata_only",
        "verifier": {
            "id": "self-test-independent-verifier",
            "type": "system",
            "adapter": "idkmesh-local-validator",
            "adapter_version": VALIDATOR_VERSION,
        },
        "source_revision": "self-test-base",
        "checks": [
            {"id": "input-schema", "type": "schema", "required": True, "builtin": "input_schema"},
            {"id": "scope", "type": "policy", "required": True, "builtin": "scope"},
            {"id": "artifact-digest", "type": "policy", "required": True, "builtin": "artifact_digest"},
            {"id": "provenance", "type": "policy", "required": True, "builtin": "provenance"},
            {"id": "verification-request", "type": "policy", "required": True, "builtin": "verification_request"},
        ],
        "baseline": {
            "algorithm": "sha256",
            "complete": True,
            "files": [{"path": "src/input.txt", "digest": baseline_digest}],
            "ignore_paths": [],
        },
        "policy": {
            "require_plan_outside_candidate_root": True,
            "reject_symlinks": True,
            "require_source_revision_match": True,
            "require_candidate_local_artifacts": True,
        },
        "extensions": {},
    }
    return work_unit, result_manifest, plan


def cmd_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="idkmesh-validator-") as raw:
        root = Path(raw)
        candidate = root / "candidate"
        control = root / "control"
        candidate.joinpath("src").mkdir(parents=True)
        candidate.joinpath("src/input.txt").write_text("baseline\n", encoding="utf-8")
        candidate.joinpath("src/output.txt").write_text("candidate output\n", encoding="utf-8")

        work_unit, result_manifest, plan = build_self_test_documents(candidate)
        wu_path = control / "work-unit.json"
        rm_path = control / "result-manifest.json"
        plan_path = control / "evaluator-plan.json"
        write_json(wu_path, work_unit)
        write_json(rm_path, result_manifest)
        write_json(plan_path, plan)

        passed_path = run_verification(
            wu_path, rm_path, plan_path, candidate, root / "bundle-pass"
        )
        passed = load_json(passed_path)
        if passed["status"] != "passed" or passed["decision_support"]["recommendation"] != "accept_candidate":
            raise HarnessError("self-test expected the authorized candidate to pass")

        candidate.joinpath("secrets").mkdir()
        candidate.joinpath("secrets/leak.txt").write_text("not allowed\n", encoding="utf-8")
        failed_path = run_verification(
            wu_path, rm_path, plan_path, candidate, root / "bundle-scope-fail"
        )
        failed = load_json(failed_path)
        if failed["status"] != "failed" or failed["decision_support"]["recommendation"] != "reject_candidate":
            raise HarnessError("self-test expected forbidden-path mutation to fail")
        candidate.joinpath("secrets/leak.txt").unlink()
        candidate.joinpath("secrets").rmdir()

        candidate.joinpath("src/output.txt").write_text("tampered\n", encoding="utf-8")
        digest_fail_path = run_verification(
            wu_path, rm_path, plan_path, candidate, root / "bundle-digest-fail"
        )
        digest_failed = load_json(digest_fail_path)
        if digest_failed["status"] != "failed":
            raise HarnessError("self-test expected artifact digest mismatch to fail")
        candidate.joinpath("src/output.txt").write_text("candidate output\n", encoding="utf-8")

        inside_plan = candidate / "evaluator-plan.json"
        write_json(inside_plan, plan)
        try:
            run_verification(
                wu_path,
                rm_path,
                inside_plan,
                candidate,
                root / "bundle-plan-boundary-fail",
            )
        except HarnessError:
            pass
        else:
            raise HarnessError("self-test expected candidate-owned evaluator plan to be rejected")

    print("OK: local independent validator passed positive, scope, digest, and control-boundary self-tests")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    files, symlinks = snapshot_tree(root, args.ignore, reject_symlinks=True)
    if symlinks:
        raise HarnessError("snapshot refuses symlinks: " + ", ".join(symlinks))
    baseline = {
        "algorithm": "sha256",
        "complete": True,
        "files": [{"path": path, "digest": files[path]} for path in sorted(files)],
        "ignore_paths": [normalize_relpath(item.rstrip("/")) for item in args.ignore],
    }
    output = Path(args.output)
    write_json(output, baseline)
    print(f"OK: wrote trusted baseline snapshot with {len(files)} file(s) to {output}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    result_path = run_verification(
        Path(args.work_unit),
        Path(args.result_manifest),
        Path(args.evaluator_plan),
        Path(args.candidate_root),
        Path(args.output_dir),
    )
    result = load_json(result_path)
    print(
        f"OK: verification status={result['status']} recommendation={result['decision_support']['recommendation']} output={result_path}"
    )
    return 0 if result["status"] == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Run metadata-only independent verification.")
    verify.add_argument("--work-unit", required=True)
    verify.add_argument("--result-manifest", required=True)
    verify.add_argument("--evaluator-plan", required=True)
    verify.add_argument("--candidate-root", required=True)
    verify.add_argument("--output-dir", required=True)
    verify.set_defaults(func=cmd_verify)

    snapshot = sub.add_parser("snapshot", help="Create a trusted SHA-256 baseline snapshot block.")
    snapshot.add_argument("--root", required=True)
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--ignore", action="append", default=[".git/"], help="Repository-relative path prefix to ignore; may be repeated.")
    snapshot.set_defaults(func=cmd_snapshot)

    self_test = sub.add_parser("self-test", help="Run deterministic validator safety tests.")
    self_test.set_defaults(func=cmd_self_test)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (HarnessError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
