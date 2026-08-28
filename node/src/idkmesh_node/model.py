from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_VERSION = "0.1"
EXECUTION_EXTENSION = "org.idkmesh.execution.docker"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_ALLOWED_IMAGES = frozenset({"alpine:3.20", "python:3.12-alpine"})


class WorkUnitError(ValueError):
    """Raised when a canonical Work Unit or local execution binding is invalid."""


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
    max_patch_bytes: int
    max_log_bytes: int


@dataclass(frozen=True)
class WorkUnit:
    data: dict[str, Any]
    id: str
    version: int
    source: SourceSpec
    execution: ExecutionSpec
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    validator_ids: tuple[str, ...]


def repo_root() -> Path:
    # .../node/src/idkmesh_node/model.py -> repository root
    return Path(__file__).resolve().parents[3]


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_validator() -> Draft202012Validator:
    schema_path = repo_root() / "schemas/work-unit-v0.1.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkUnitError(
            "canonical Work Unit schema not found; run idkmesh-node from an IDKMesh checkout"
        ) from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_canonical(data: dict[str, Any]) -> None:
    errors = sorted(
        _canonical_validator().iter_errors(data),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    rendered: list[str] = []
    for error in errors[:10]:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    raise WorkUnitError("canonical Work Unit validation failed: " + "; ".join(rendered))


def _require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkUnitError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise WorkUnitError(f"{field} must be between {minimum} and {maximum}")
    return value


def _require_number(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkUnitError(f"{field} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise WorkUnitError(f"{field} must be between {minimum} and {maximum}")
    return result


def _validate_repo_url(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 500:
        raise WorkUnitError("git_ref locator must be a string up to 500 characters")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise WorkUnitError("MVP git_ref locator must use https://github.com/...")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WorkUnitError("git_ref locator must not contain credentials, query, or fragment")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if len(path.split("/")) != 2:
        raise WorkUnitError("git_ref locator must identify one GitHub owner/repository")
    return url


def _source_from_inputs(data: dict[str, Any]) -> SourceSpec:
    refs = [item for item in data["inputs"] if item.get("type") == "git_ref"]
    if len(refs) != 1:
        raise WorkUnitError("idkmesh-node requires exactly one input with type 'git_ref'")
    ref = refs[0]
    repo_url = _validate_repo_url(ref.get("locator"))
    digest = ref.get("digest")
    if not isinstance(digest, str) or not digest.startswith("git:"):
        raise WorkUnitError("git_ref digest must be 'git:<40-character commit SHA>'")
    revision = digest.split(":", 1)[1]
    if not SHA_RE.fullmatch(revision):
        raise WorkUnitError("git_ref digest must contain a full 40-character commit SHA")
    return SourceSpec(repo_url=repo_url, revision=revision.lower())


def _execution_from_extensions(
    data: dict[str, Any],
    *,
    allowed_images: frozenset[str],
) -> ExecutionSpec:
    extension = data.get("extensions", {}).get(EXECUTION_EXTENSION)
    if not isinstance(extension, dict):
        raise WorkUnitError(
            f"local Docker execution requires extensions.{EXECUTION_EXTENSION}"
        )
    unknown = set(extension) - {
        "image",
        "command",
        "timeout_seconds",
        "cpus",
        "memory_mb",
        "pids_limit",
        "max_patch_bytes",
        "max_log_bytes",
    }
    if unknown:
        raise WorkUnitError(
            f"unknown {EXECUTION_EXTENSION} field(s): {', '.join(sorted(unknown))}"
        )

    image = extension.get("image")
    if image not in allowed_images:
        raise WorkUnitError(f"execution image must be one of: {', '.join(sorted(allowed_images))}")

    command = extension.get("command")
    if not isinstance(command, list) or not command or len(command) > 64:
        raise WorkUnitError("execution command must be a non-empty array of at most 64 strings")
    if any(not isinstance(part, str) or not part or len(part) > 4096 for part in command):
        raise WorkUnitError("each execution command element must be a non-empty string up to 4096 characters")

    budget_limit = data.get("budget", {}).get("wall_seconds")
    max_timeout = 3600
    if isinstance(budget_limit, (int, float)) and not isinstance(budget_limit, bool) and budget_limit > 0:
        max_timeout = min(max_timeout, max(1, int(budget_limit)))
    timeout_seconds = _require_int(
        extension.get("timeout_seconds", min(300, max_timeout)),
        "execution.timeout_seconds",
        1,
        max_timeout,
    )

    return ExecutionSpec(
        image=image,
        command=tuple(command),
        timeout_seconds=timeout_seconds,
        cpus=_require_number(extension.get("cpus", 1.0), "execution.cpus", 0.1, 8.0),
        memory_mb=_require_int(extension.get("memory_mb", 1024), "execution.memory_mb", 64, 16384),
        pids_limit=_require_int(extension.get("pids_limit", 128), "execution.pids_limit", 16, 1024),
        max_patch_bytes=_require_int(
            extension.get("max_patch_bytes", 1_000_000),
            "execution.max_patch_bytes",
            1024,
            10_000_000,
        ),
        max_log_bytes=_require_int(
            extension.get("max_log_bytes", 262_144),
            "execution.max_log_bytes",
            1024,
            2_000_000,
        ),
    )


def parse_work_unit(
    data: dict[str, Any],
    *,
    allowed_images: frozenset[str] = DEFAULT_ALLOWED_IMAGES,
) -> WorkUnit:
    if not isinstance(data, dict):
        raise WorkUnitError("Work Unit root must be an object")
    _validate_canonical(data)

    permissions = data["permissions"]
    if permissions["network"] != "none":
        raise WorkUnitError("idkmesh-node MVP requires permissions.network = 'none'")
    if permissions["secrets"]:
        raise WorkUnitError("idkmesh-node MVP does not mount Work Unit secrets")
    if not permissions["process_execution"]:
        raise WorkUnitError("idkmesh-node cannot execute a Work Unit with process_execution=false")

    source = _source_from_inputs(data)
    execution = _execution_from_extensions(data, allowed_images=allowed_images)
    constraints = data["constraints"]
    validator_ids = tuple(v["id"] for v in data["validators"] if v["required"])

    return WorkUnit(
        data=data,
        id=data["id"],
        version=data["version"],
        source=source,
        execution=execution,
        allowed_paths=tuple(constraints["allowed_paths"]),
        forbidden_paths=tuple(constraints["forbidden_paths"]),
        validator_ids=validator_ids,
    )


def load_work_unit(path: str | Path) -> WorkUnit:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkUnitError(f"invalid JSON: {exc}") from exc
    return parse_work_unit(data)
