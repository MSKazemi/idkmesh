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
NODE_BINDING_SCHEMA = SCHEMA_DIR / "node-execution-binding-v0.1.schema.json"
RESULT_MANIFEST_SCHEMA = SCHEMA_DIR / "result-manifest-v0.1.schema.json"
NODE_EXTENSION_KEY = "org.idkmesh.node.execution"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_ALLOWED_IMAGES = frozenset({"alpine:3.20", "python:3.12-alpine"})


class WorkUnitError(ValueError):
    """Raised when a canonical Work Unit violates the node contract or safety policy."""


@dataclass(frozen=True)
class SourceSpec:
    repo_url: str
    revision: str


@dataclass(frozen=True)
class ExecutionSpec:
    image: str
    command: tuple[str, ...]
    timeout_seconds: int
    cpus: float
    memory_mb: int
    pids_limit: int
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class OutputSpec:
    max_patch_bytes: int
    max_log_bytes: int


@dataclass(frozen=True)
class WorkUnit:
    id: str
    version: int
    document: dict[str, Any]
    binding: dict[str, Any]
    source: SourceSpec
    execution: ExecutionSpec
    output: OutputSpec
    wall_seconds: float
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    write_paths: tuple[str, ...]
    required_validator_ids: tuple[str, ...]
    minimum_independent_verifiers: int


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_schema(instance: Any, schema_path: Path, label: str) -> None:
    validator = Draft202012Validator(_load_schema(schema_path), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    details: list[str] = []
    for error in errors[:12]:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{location}: {error.message}")
    if len(errors) > 12:
        details.append(f"... and {len(errors) - 12} more error(s)")
    raise WorkUnitError(f"{label} failed schema validation: " + "; ".join(details))


def validate_result_manifest(instance: Any) -> None:
    _validate_schema(instance, RESULT_MANIFEST_SCHEMA, "ResultManifest")


def _validate_repo_url(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 500:
        raise WorkUnitError("git_ref locator must be a string up to 500 characters")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise WorkUnitError("node v0.1 git_ref locator must use https://github.com/...")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WorkUnitError("git_ref locator must not contain credentials, query, or fragment")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if len(path.split("/")) != 2:
        raise WorkUnitError("git_ref locator must identify exactly one GitHub owner/repository")
    return url


def _validate_path_patterns(patterns: list[str], field: str) -> tuple[str, ...]:
    if not patterns:
        raise WorkUnitError(f"{field} must contain at least one repository-relative path or glob")
    clean: list[str] = []
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            raise WorkUnitError(f"{field} entries must be non-empty strings")
        path = PurePosixPath(pattern)
        if path.is_absolute() or ".." in path.parts:
            raise WorkUnitError(f"{field} entries must be repository-relative and may not contain '..': {pattern}")
        clean.append(pattern)
    return tuple(clean)


def _enforce_v0_2_policy(data: dict[str, Any], binding: dict[str, Any]) -> None:
    permissions = data["permissions"]
    if permissions["network"] != "none":
        raise WorkUnitError("node v0.1 requires permissions.network='none'")
    if permissions.get("network_allowlist"):
        raise WorkUnitError("node v0.1 rejects network_allowlist when network is disabled")
    if permissions["secrets"]:
        raise WorkUnitError("node v0.1 does not expose secrets to task containers")
    if permissions["process_execution"] is not True:
        raise WorkUnitError("node execution requires permissions.process_execution=true")

    security = data["security"]
    if security["data_classification"] != "public":
        raise WorkUnitError("node v0.1 accepts only security.data_classification='public'")
    if security["minimum_worker_trust"] != "untrusted":
        raise WorkUnitError("node v0.1 currently satisfies only minimum_worker_trust='untrusted'")
    if security["risk_class"] != "low":
        raise WorkUnitError("node v0.1 Docker profile accepts only security.risk_class='low'")

    verification = data["verification_policy"]
    if verification["independent_from_worker"] is not True:
        raise WorkUnitError("node v0.1 requires verification_policy.independent_from_worker=true")
    if verification["minimum_independent_verifiers"] < 1:
        raise WorkUnitError("node v0.1 requires at least one independent verifier")

    budget = data["budget"]
    if float(budget["project_spend_usd_max"]) != 0.0:
        raise WorkUnitError("node v0.1 requires budget.project_spend_usd_max=0")
    if budget["paid_fallback_allowed"] is not False:
        raise WorkUnitError("node v0.1 requires budget.paid_fallback_allowed=false")
    wall_seconds = budget.get("wall_seconds")
    if wall_seconds is None or float(wall_seconds) <= 0:
        raise WorkUnitError("node v0.1 requires a positive budget.wall_seconds whole-attempt limit")

    requirements = data["requirements"]
    provided_capabilities = set(binding["capabilities"])
    missing_capabilities = sorted(set(requirements["capabilities"]) - provided_capabilities)
    if missing_capabilities:
        raise WorkUnitError(
            "node execution binding is missing required capability/capabilities: "
            + ", ".join(missing_capabilities)
        )
    resources = requirements["resources"]
    if resources["gpu"] == "required":
        raise WorkUnitError("node v0.1 Docker profile does not provide a GPU")
    if float(binding["limits"]["cpus"]) < float(resources["cpu_cores_min"]):
        raise WorkUnitError("node limits.cpus is below requirements.resources.cpu_cores_min")
    if int(binding["limits"]["memory_mb"]) < int(resources["memory_mb_min"]):
        raise WorkUnitError("node limits.memory_mb is below requirements.resources.memory_mb_min")


def parse_work_unit(
    data: dict[str, Any],
    *,
    allowed_images: frozenset[str] = DEFAULT_ALLOWED_IMAGES,
) -> WorkUnit:
    _validate_schema(data, WORK_UNIT_SCHEMA, "Work Unit")

    extensions = data.get("extensions", {})
    binding = extensions.get(NODE_EXTENSION_KEY)
    if binding is None:
        raise WorkUnitError(f"Work Unit must include extensions.{NODE_EXTENSION_KEY}")
    _validate_schema(binding, NODE_BINDING_SCHEMA, "node execution binding")
    _enforce_v0_2_policy(data, binding)

    permissions = data["permissions"]
    allowed_paths = _validate_path_patterns(data["constraints"]["allowed_paths"], "constraints.allowed_paths")
    write_paths = _validate_path_patterns(permissions["filesystem_write"], "permissions.filesystem_write")
    forbidden_paths = tuple(data["constraints"]["forbidden_paths"])
    for pattern in forbidden_paths:
        path = PurePosixPath(pattern)
        if path.is_absolute() or ".." in path.parts:
            raise WorkUnitError(
                f"constraints.forbidden_paths entries must be repository-relative and may not contain '..': {pattern}"
            )

    source_input_id = binding["source_input_id"]
    matches = [item for item in data["inputs"] if item["id"] == source_input_id]
    if len(matches) != 1:
        raise WorkUnitError("node binding source_input_id must reference exactly one Work Unit input")
    source_input = matches[0]
    if source_input["type"] != "git_ref":
        raise WorkUnitError("node binding source_input_id must reference an input of type 'git_ref'")
    repo_url = _validate_repo_url(source_input["locator"])
    revision = binding["source_revision"]
    if not SHA_RE.fullmatch(revision):
        raise WorkUnitError("node v0.1 source_revision must be a full 40-character Git commit identifier")
    provenance_revision = data["provenance"].get("source_revision")
    if not provenance_revision:
        raise WorkUnitError("node v0.1 requires provenance.source_revision for source traceability")
    if provenance_revision.lower() != revision.lower():
        raise WorkUnitError("node binding source_revision must match provenance.source_revision")

    container = binding["container"]
    image = container["image"]
    if image not in allowed_images:
        raise WorkUnitError(f"container.image must be one of: {', '.join(sorted(allowed_images))}")

    limits = binding["limits"]
    wall_budget = float(data["budget"]["wall_seconds"])
    if limits["timeout_seconds"] > wall_budget:
        raise WorkUnitError("node timeout_seconds may not exceed Work Unit budget.wall_seconds")

    required_validator_ids = tuple(
        validator["id"] for validator in data["validators"] if validator["required"]
    )

    return WorkUnit(
        id=data["id"],
        version=data["version"],
        document=data,
        binding=binding,
        source=SourceSpec(repo_url=repo_url, revision=revision.lower()),
        execution=ExecutionSpec(
            image=image,
            command=tuple(container["command"]),
            timeout_seconds=limits["timeout_seconds"],
            cpus=float(limits["cpus"]),
            memory_mb=limits["memory_mb"],
            pids_limit=limits["pids_limit"],
            capabilities=tuple(binding["capabilities"]),
        ),
        output=OutputSpec(
            max_patch_bytes=binding["output_limits"]["max_patch_bytes"],
            max_log_bytes=binding["output_limits"]["max_log_bytes"],
        ),
        wall_seconds=wall_budget,
        allowed_paths=allowed_paths,
        forbidden_paths=forbidden_paths,
        write_paths=write_paths,
        required_validator_ids=required_validator_ids,
        minimum_independent_verifiers=data["verification_policy"]["minimum_independent_verifiers"],
    )


def load_work_unit(path: str | Path) -> WorkUnit:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkUnitError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkUnitError("Work Unit root must be an object")
    return parse_work_unit(data)
