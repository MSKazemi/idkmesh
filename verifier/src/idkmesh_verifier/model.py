from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "schemas"
WORK_UNIT_SCHEMA = SCHEMA_DIR / "work-unit-v0.2.schema.json"
RESULT_MANIFEST_SCHEMA = SCHEMA_DIR / "result-manifest-v0.1.schema.json"
VERIFICATION_RESULT_SCHEMA = SCHEMA_DIR / "verification-result-v0.1.schema.json"
VERIFIER_PLAN_SCHEMA = SCHEMA_DIR / "verifier-plan-v0.1.schema.json"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_ALLOWED_IMAGES = frozenset({"python:3.12-alpine", "alpine:3.20"})


class VerifierError(ValueError):
    pass


@dataclass(frozen=True)
class CheckSpec:
    id: str
    type: str
    required: bool
    mode: str
    command: tuple[str, ...]
    timeout_seconds: int
    description: str


@dataclass(frozen=True)
class VerificationContext:
    work_unit: dict[str, Any]
    worker_result: dict[str, Any]
    plan: dict[str, Any]
    repo_url: str
    source_revision: str
    candidate_artifact: dict[str, Any]
    verifier_id: str
    verifier_adapter: str
    verifier_adapter_version: str
    container_image: str
    checks: tuple[CheckSpec, ...]


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_schema(path: Path) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_schema(instance: Any, schema_path: Path, label: str) -> None:
    validator = Draft202012Validator(_load_schema(schema_path), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    rendered = []
    for error in errors[:12]:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    raise VerifierError(f"{label} failed schema validation: " + "; ".join(rendered))


def validate_verification_result(result: dict[str, Any]) -> None:
    validate_schema(result, VERIFICATION_RESULT_SCHEMA, "VerificationResult")


def _repo_url(work_unit: dict[str, Any], source_input_id: str) -> str:
    matches = [item for item in work_unit["inputs"] if item["id"] == source_input_id]
    if len(matches) != 1:
        raise VerifierError("source_input_id must reference exactly one WorkUnit input")
    source = matches[0]
    if source["type"] != "git_ref":
        raise VerifierError("source_input_id must reference a git_ref input")
    locator = source["locator"]
    parsed = urlparse(locator)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise VerifierError("verifier v0.1 supports public https://github.com repositories only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise VerifierError("git_ref locator must not include credentials, query, or fragment")
    return locator


def _validate_repo_pattern(pattern: str, field: str) -> None:
    path = PurePosixPath(pattern)
    if path.is_absolute() or ".." in path.parts:
        raise VerifierError(f"{field} must be repository-relative: {pattern}")


def _verify_lineage(work_unit: dict[str, Any], worker_result: dict[str, Any]) -> None:
    if worker_result["work_unit_id"] != work_unit["id"]:
        raise VerifierError("worker ResultManifest references a different WorkUnit id")
    if worker_result["work_unit_version"] != work_unit["version"]:
        raise VerifierError("worker ResultManifest references a different WorkUnit version")
    expected_digest = canonical_digest(work_unit)
    if worker_result["provenance"]["work_unit_digest"] != expected_digest:
        raise VerifierError("worker ResultManifest work_unit_digest does not bind to exact WorkUnit")
    if worker_result["status"] != "succeeded":
        raise VerifierError("verifier v0.1 accepts only worker ResultManifest status='succeeded'")
    source_revision = worker_result["provenance"]["source_revision"]
    if not SHA_RE.fullmatch(source_revision):
        raise VerifierError("verifier v0.1 requires a full immutable 40-character Git source revision")


def _verify_policy(work_unit: dict[str, Any], worker_result: dict[str, Any], plan: dict[str, Any]) -> None:
    security = work_unit["security"]
    if security["risk_class"] != "low" or security["data_classification"] != "public":
        raise VerifierError("verifier v0.1 Docker profile accepts only low-risk public WorkUnits")
    if not security["sandbox_required"]:
        raise VerifierError("verifier v0.1 requires security.sandbox_required=true")
    if work_unit["permissions"]["secrets"]:
        raise VerifierError("verifier v0.1 does not expose WorkUnit secrets")
    policy = work_unit["verification_policy"]
    if not policy["independent_from_worker"] or policy["minimum_independent_verifiers"] < 1:
        raise VerifierError("WorkUnit must require at least one independent verifier")
    if plan["verifier"]["id"] == worker_result["worker"]["id"]:
        raise VerifierError("verifier identity must differ from worker identity")

    plan_ids = {check["id"] for check in plan["checks"]}
    required_ids = {v["id"] for v in work_unit["validators"] if v["required"]}
    requested_ids = set(worker_result["verification_request"]["expected_validator_ids"])
    missing = sorted((required_ids | requested_ids) - plan_ids)
    if missing:
        raise VerifierError("VerifierPlan is missing required/requested check(s): " + ", ".join(missing))

    for raw in work_unit["constraints"]["allowed_paths"]:
        _validate_repo_pattern(raw, "constraints.allowed_paths")
    for raw in work_unit["constraints"]["forbidden_paths"]:
        _validate_repo_pattern(raw, "constraints.forbidden_paths")


def parse_context(
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    plan: dict[str, Any],
    *,
    allowed_images: frozenset[str] = DEFAULT_ALLOWED_IMAGES,
) -> VerificationContext:
    validate_schema(work_unit, WORK_UNIT_SCHEMA, "WorkUnit")
    validate_schema(worker_result, RESULT_MANIFEST_SCHEMA, "ResultManifest")
    validate_schema(plan, VERIFIER_PLAN_SCHEMA, "VerifierPlan")
    _verify_lineage(work_unit, worker_result)
    _verify_policy(work_unit, worker_result, plan)

    artifact_id = plan["candidate_artifact_id"]
    artifacts = [a for a in worker_result["produced_artifacts"] if a["id"] == artifact_id]
    if len(artifacts) != 1:
        raise VerifierError("candidate_artifact_id must reference exactly one ResultManifest artifact")
    artifact = artifacts[0]
    if artifact["type"] != "patch":
        raise VerifierError("verifier v0.1 currently accepts candidate artifacts of type 'patch' only")

    image = plan["container_image"]
    if image not in allowed_images:
        raise VerifierError(f"container_image must be one of: {', '.join(sorted(allowed_images))}")

    checks = tuple(
        CheckSpec(
            id=check["id"],
            type=check["type"],
            required=check["required"],
            mode=check["mode"],
            command=tuple(check.get("command", [])),
            timeout_seconds=int(check.get("timeout_seconds", 300)),
            description=check.get("description", ""),
        )
        for check in plan["checks"]
    )
    verifier = plan["verifier"]
    return VerificationContext(
        work_unit=work_unit,
        worker_result=worker_result,
        plan=plan,
        repo_url=_repo_url(work_unit, plan["source_input_id"]),
        source_revision=worker_result["provenance"]["source_revision"].lower(),
        candidate_artifact=artifact,
        verifier_id=verifier["id"],
        verifier_adapter=verifier["adapter"],
        verifier_adapter_version=verifier.get("adapter_version", "0.1"),
        container_image=image,
        checks=checks,
    )


def load_json_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerifierError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifierError(f"{path} must contain a JSON object")
    return value
