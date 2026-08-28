from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

WORK_UNIT_VERSION = "0.1"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_ALLOWED_IMAGES = frozenset({"alpine:3.20", "python:3.12-alpine"})


class WorkUnitError(ValueError):
    """Raised when a Work Unit violates the MVP schema or safety policy."""


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


@dataclass(frozen=True)
class OutputSpec:
    max_patch_bytes: int
    max_log_bytes: int


@dataclass(frozen=True)
class WorkUnit:
    version: str
    id: str
    source: SourceSpec
    execution: ExecutionSpec
    output: OutputSpec


def _require_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkUnitError(f"{field} must be an object")
    return value


def _require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkUnitError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise WorkUnitError(f"{field} must be between {minimum} and {maximum}")
    return value


def _require_number(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkUnitError(f"{field} must be a number")
    value = float(value)
    if not minimum <= value <= maximum:
        raise WorkUnitError(f"{field} must be between {minimum} and {maximum}")
    return value


def _validate_repo_url(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 500:
        raise WorkUnitError("source.repo_url must be a string up to 500 characters")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise WorkUnitError("MVP source.repo_url must use https://github.com/...")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WorkUnitError("source.repo_url must not contain credentials, query, or fragment")
    path = parsed.path.strip("/")
    if len(path.split("/")) != 2:
        raise WorkUnitError("source.repo_url must identify one GitHub owner/repository")
    return url


def parse_work_unit(data: dict[str, Any], *, allowed_images: frozenset[str] = DEFAULT_ALLOWED_IMAGES) -> WorkUnit:
    if data.get("version") != WORK_UNIT_VERSION:
        raise WorkUnitError(f"version must be {WORK_UNIT_VERSION!r}")

    work_id = data.get("id")
    if not isinstance(work_id, str) or not ID_RE.fullmatch(work_id):
        raise WorkUnitError("id must use 1-128 letters, numbers, '.', '_' or '-'")

    source_data = _require_dict(data.get("source"), "source")
    repo_url = _validate_repo_url(source_data.get("repo_url"))
    revision = source_data.get("revision")
    if not isinstance(revision, str) or not SHA_RE.fullmatch(revision):
        raise WorkUnitError("source.revision must be a full 40-character Git commit SHA")

    execution_data = _require_dict(data.get("execution"), "execution")
    image = execution_data.get("image")
    if image not in allowed_images:
        raise WorkUnitError(f"execution.image must be one of: {', '.join(sorted(allowed_images))}")

    command = execution_data.get("command")
    if not isinstance(command, list) or not command or len(command) > 64:
        raise WorkUnitError("execution.command must be a non-empty array of at most 64 strings")
    if any(not isinstance(part, str) or not part or len(part) > 4096 for part in command):
        raise WorkUnitError("each execution.command element must be a non-empty string up to 4096 characters")

    network = execution_data.get("network", "none")
    if network != "none":
        raise WorkUnitError("MVP execution.network must be 'none'")

    timeout_seconds = _require_int(execution_data.get("timeout_seconds", 300), "execution.timeout_seconds", 1, 3600)
    cpus = _require_number(execution_data.get("cpus", 1.0), "execution.cpus", 0.1, 8.0)
    memory_mb = _require_int(execution_data.get("memory_mb", 1024), "execution.memory_mb", 64, 16384)
    pids_limit = _require_int(execution_data.get("pids_limit", 128), "execution.pids_limit", 16, 1024)

    output_data = _require_dict(data.get("output", {}), "output")
    max_patch_bytes = _require_int(output_data.get("max_patch_bytes", 1_000_000), "output.max_patch_bytes", 1_024, 10_000_000)
    max_log_bytes = _require_int(output_data.get("max_log_bytes", 262_144), "output.max_log_bytes", 1_024, 2_000_000)

    unknown = set(data) - {"version", "id", "source", "execution", "output"}
    if unknown:
        raise WorkUnitError(f"unknown top-level fields: {', '.join(sorted(unknown))}")

    return WorkUnit(
        version=WORK_UNIT_VERSION,
        id=work_id,
        source=SourceSpec(repo_url=repo_url, revision=revision.lower()),
        execution=ExecutionSpec(
            image=image,
            command=tuple(command),
            timeout_seconds=timeout_seconds,
            cpus=cpus,
            memory_mb=memory_mb,
            pids_limit=pids_limit,
        ),
        output=OutputSpec(max_patch_bytes=max_patch_bytes, max_log_bytes=max_log_bytes),
    )


def load_work_unit(path: str | Path) -> tuple[WorkUnit, bytes]:
    raw = Path(path).read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkUnitError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkUnitError("Work Unit root must be an object")
    return parse_work_unit(data), raw
