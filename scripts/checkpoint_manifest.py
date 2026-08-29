#!/usr/bin/env python3
"""Create and verify fail-closed checkpoint integrity manifests.

The manifest binds checkpoint files to the GitHub run that produced them.  It
uses only the Python standard library so trusted workflows can verify a
download before passing persistent state to any other repository code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SCHEMA_VERSION = 1
_UNSPECIFIED = object()
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEAD_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+\.ya?ml$")
_EVENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ManifestError(ValueError):
    """A checkpoint manifest or its corresponding files are invalid."""


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{field}: expected positive integer")
    return value


def _validate_provenance(provenance: Any) -> dict[str, Any]:
    if not isinstance(provenance, dict):
        raise ManifestError("provenance: expected object")
    expected_keys = {
        "repository",
        "workflow",
        "run_id",
        "head_sha",
        "event_name",
        "parent_run_id",
    }
    if set(provenance) != expected_keys:
        raise ManifestError("provenance: unexpected or missing fields")

    repository = provenance["repository"]
    workflow = provenance["workflow"]
    head_sha = provenance["head_sha"]
    event_name = provenance["event_name"]
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        raise ManifestError("provenance.repository: expected owner/repository")
    if not isinstance(workflow, str) or not _WORKFLOW_RE.fullmatch(workflow):
        raise ManifestError("provenance.workflow: expected a workflow filename")
    if not isinstance(head_sha, str) or not _HEAD_SHA_RE.fullmatch(head_sha):
        raise ManifestError("provenance.head_sha: expected lowercase 40-character SHA")
    if not isinstance(event_name, str) or not _EVENT_RE.fullmatch(event_name):
        raise ManifestError("provenance.event_name: expected GitHub event name")
    run_id = _positive_int(provenance["run_id"], "provenance.run_id")
    parent_run_id = provenance["parent_run_id"]
    if parent_run_id is not None:
        parent = _positive_int(parent_run_id, "provenance.parent_run_id")
        if parent >= run_id:
            raise ManifestError("provenance.parent_run_id: expected an earlier run")
    return provenance


def _validate_name(name: Any) -> str:
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise ManifestError("file name: expected safe non-empty relative path")
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"file name {name!r}: unsafe path")
    if path.as_posix() != name:
        raise ManifestError(f"file name {name!r}: non-canonical path")
    return name


def parse_file_specs(specs: Sequence[str]) -> dict[str, Path]:
    """Parse NAME=PATH arguments, rejecting aliases and unsafe logical names."""
    if not specs:
        raise ManifestError("at least one --file NAME=PATH is required")
    files: dict[str, Path] = {}
    physical_paths: set[Path] = set()
    for spec in specs:
        if not isinstance(spec, str) or "=" not in spec:
            raise ManifestError(f"invalid file spec {spec!r}; expected NAME=PATH")
        name, raw_path = spec.split("=", 1)
        _validate_name(name)
        if not raw_path:
            raise ManifestError(f"file {name!r}: path must not be empty")
        path = Path(raw_path)
        resolved = path.resolve(strict=False)
        if name in files:
            raise ManifestError(f"duplicate file name: {name}")
        if resolved in physical_paths:
            raise ManifestError(f"duplicate file path: {path}")
        files[name] = path
        physical_paths.add(resolved)
    return files


def _hash_file(path: Path) -> tuple[str, int]:
    if path.is_symlink():
        raise ManifestError(f"{path}: symbolic links are not allowed")
    if not path.is_file():
        raise ManifestError(f"{path}: missing regular file")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
    except OSError as exc:
        raise ManifestError(f"{path}: cannot read file: {exc}") from exc
    return digest.hexdigest(), size


def build_manifest(
    *,
    repository: str,
    workflow: str,
    run_id: int,
    head_sha: str,
    event_name: str,
    parent_run_id: int | None,
    files: dict[str, Path],
) -> dict[str, Any]:
    """Build a validated manifest for the supplied named files."""
    provenance = _validate_provenance(
        {
            "repository": repository,
            "workflow": workflow,
            "run_id": run_id,
            "head_sha": head_sha,
            "event_name": event_name,
            "parent_run_id": parent_run_id,
        }
    )
    if not files:
        raise ManifestError("at least one named file is required")
    entries: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for name in sorted(files):
        _validate_name(name)
        path = Path(files[name])
        resolved = path.resolve(strict=False)
        if resolved in seen_paths:
            raise ManifestError(f"duplicate file path: {path}")
        seen_paths.add(resolved)
        digest, size = _hash_file(path)
        entries.append({"name": name, "sha256": digest, "size": size})
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": provenance,
        "files": entries,
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    """Write canonical JSON after validating the complete manifest shape."""
    validate_manifest_shape(manifest)
    destination = Path(path)
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{path}: cannot load manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError("manifest: expected JSON object")
    validate_manifest_shape(value)
    return value


def validate_manifest_shape(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest: expected object")
    if set(manifest) != {"schema_version", "provenance", "files"}:
        raise ManifestError("manifest: unexpected or missing fields")
    if (
        isinstance(manifest["schema_version"], bool)
        or not isinstance(manifest["schema_version"], int)
        or manifest["schema_version"] != SCHEMA_VERSION
    ):
        raise ManifestError(f"schema_version: unsupported value {manifest['schema_version']!r}")
    _validate_provenance(manifest["provenance"])
    entries = manifest["files"]
    if not isinstance(entries, list) or not entries:
        raise ManifestError("files: expected non-empty array")
    names: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"name", "sha256", "size"}:
            raise ManifestError(f"files[{index}]: unexpected or missing fields")
        name = _validate_name(entry["name"])
        if name in names:
            raise ManifestError(f"files[{index}]: duplicate name {name!r}")
        names.add(name)
        if not isinstance(entry["sha256"], str) or not _SHA256_RE.fullmatch(entry["sha256"]):
            raise ManifestError(f"files[{index}].sha256: expected lowercase SHA-256")
        if isinstance(entry["size"], bool) or not isinstance(entry["size"], int) or entry["size"] < 0:
            raise ManifestError(f"files[{index}].size: expected non-negative integer")


def verify_manifest(
    manifest: dict[str, Any],
    *,
    repository: str,
    workflow: str,
    run_id: int,
    head_sha: str,
    event_name: str,
    parent_run_id: int | None | object = _UNSPECIFIED,
    files: dict[str, Path],
) -> None:
    """Verify exact provenance, file membership, sizes, and SHA-256 hashes."""
    validate_manifest_shape(manifest)
    expected_provenance = _validate_provenance(
        {
            "repository": repository,
            "workflow": workflow,
            "run_id": run_id,
            "head_sha": head_sha,
            "event_name": event_name,
            # A valid placeholder lets the common provenance validator check
            # every required expected value even when the caller does not
            # possess the producing run's optional lineage pointer.
            "parent_run_id": None if parent_run_id is _UNSPECIFIED else parent_run_id,
        }
    )
    compared_fields = ["repository", "workflow", "run_id", "head_sha", "event_name"]
    if parent_run_id is not _UNSPECIFIED:
        compared_fields.append("parent_run_id")
    mismatches = [
        key
        for key in compared_fields
        if manifest["provenance"].get(key) != expected_provenance[key]
    ]
    if mismatches:
        raise ManifestError(f"provenance mismatch: {', '.join(mismatches)}")
    if not files:
        raise ManifestError("at least one named file is required")
    expected_files = {entry["name"]: entry for entry in manifest["files"]}
    if set(files) != set(expected_files):
        raise ManifestError("file set does not match manifest")
    seen_paths: set[Path] = set()
    for name, path_value in files.items():
        _validate_name(name)
        path = Path(path_value)
        resolved = path.resolve(strict=False)
        if resolved in seen_paths:
            raise ManifestError(f"duplicate file path: {path}")
        seen_paths.add(resolved)
        digest, size = _hash_file(path)
        expected = expected_files[name]
        if size != expected["size"]:
            raise ManifestError(f"{name}: size mismatch")
        if digest != expected["sha256"]:
            raise ManifestError(f"{name}: SHA-256 mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--manifest", required=True, type=Path)
        subparser.add_argument("--repository", required=True)
        subparser.add_argument("--workflow", required=True)
        subparser.add_argument("--run-id", required=True, type=int)
        subparser.add_argument("--head-sha", required=True)
        subparser.add_argument("--event-name", required=True)
        subparser.add_argument("--parent-run-id", type=int, default=argparse.SUPPRESS)
        subparser.add_argument("--file", action="append", default=[], metavar="NAME=PATH")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        files = parse_file_specs(args.file)
        fields = {
            "repository": args.repository,
            "workflow": args.workflow,
            "run_id": args.run_id,
            "head_sha": args.head_sha,
            "event_name": args.event_name,
            "files": files,
        }
        if args.command == "create":
            fields["parent_run_id"] = getattr(args, "parent_run_id", None)
            write_manifest(args.manifest, build_manifest(**fields))
        else:
            if hasattr(args, "parent_run_id"):
                fields["parent_run_id"] = args.parent_run_id
            verify_manifest(load_manifest(args.manifest), **fields)
    except ManifestError as exc:
        print(f"checkpoint manifest error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
