#!/usr/bin/env python3
"""Build deterministic release inventory metadata for IDKMesh artifacts.

The output is evidence about what was built, not evidence that the software is
correct. Signing/attestation is performed separately by GitHub Actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_sha(value: str, field: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-hex Git commit SHA")
    return value


def _load_project(pyproject: Path) -> dict[str, Any]:
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml is missing [project]")
    name = project.get("name")
    version = project.get("version")
    dependencies = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    if not isinstance(name, str) or not name:
        raise ValueError("project.name must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("project.version must be a non-empty string")
    if not isinstance(dependencies, list) or any(not isinstance(x, str) for x in dependencies):
        raise ValueError("project.dependencies must be an array of strings")
    if not isinstance(optional, dict) or any(
        not isinstance(group, str)
        or not isinstance(items, list)
        or any(not isinstance(item, str) for item in items)
        for group, items in optional.items()
    ):
        raise ValueError("project.optional-dependencies must map names to string arrays")
    return {"name": name, "version": version, "dependencies": dependencies, "optional": optional}


def build_metadata(
    *,
    pyproject: Path,
    dist_dir: Path,
    source_sha: str,
    source_ref: str,
    workflow_ref: str,
    workflow_sha: str,
    run_id: str,
    run_attempt: str,
    created_at: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    project = _load_project(pyproject)
    source_sha = _required_sha(source_sha, "source_sha")
    workflow_sha = _required_sha(workflow_sha, "workflow_sha")
    artifacts = sorted(path for path in dist_dir.iterdir() if path.is_file())
    if not artifacts:
        raise ValueError("dist directory contains no release artifacts")

    files = [
        {"name": path.name, "sha256": _sha256(path), "size_bytes": path.stat().st_size}
        for path in artifacts
    ]
    checksums = "".join(f"{item['sha256']}  {item['name']}\n" for item in files)

    root_spdx = f"SPDXRef-Package-{project['name']}"
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{project['name']}-{project['version']}-release",
        "documentNamespace": (
            f"https://github.com/MSKazemi/idkmesh/releases/{source_sha}/sbom"
        ),
        "creationInfo": {
            "creators": ["Tool: idkmesh-build-release-supply-chain/0.1"],
            "created": created_at,
        },
        "packages": [
            {
                "name": project["name"],
                "SPDXID": root_spdx,
                "versionInfo": project["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "externalRefs": [],
                "annotations": [
                    {
                        "annotationType": "OTHER",
                        "annotator": "Tool: idkmesh-build-release-supply-chain/0.1",
                        "annotationDate": created_at,
                        "comment": json.dumps(
                            {
                                "runtime_dependencies": project["dependencies"],
                                "optional_dependencies": project["optional"],
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": root_spdx,
            }
        ],
    }

    provenance = {
        "schema_version": "0.1",
        "kind": "idkmesh-release-provenance",
        "package": {"name": project["name"], "version": project["version"]},
        "source": {"commit_sha": source_sha, "ref": source_ref},
        "workflow": {
            "ref": workflow_ref,
            "commit_sha": workflow_sha,
            "run_id": str(run_id),
            "run_attempt": str(run_attempt),
        },
        "artifacts": files,
        "sbom": {"format": "SPDX-2.3", "path": "sbom.spdx.json"},
        "authority": {
            "proves_functional_correctness": False,
            "proves_security": False,
            "grants_merge_authority": False,
        },
    }
    return sbom, provenance, checksums


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("release-metadata"))
    parser.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--source-ref", default=os.environ.get("GITHUB_REF", ""))
    parser.add_argument("--workflow-ref", default=os.environ.get("GITHUB_WORKFLOW_REF", ""))
    parser.add_argument("--workflow-sha", default=os.environ.get("GITHUB_WORKFLOW_SHA", ""))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args(argv)

    sbom, provenance, checksums = build_metadata(
        pyproject=args.pyproject,
        dist_dir=args.dist,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        workflow_ref=args.workflow_ref,
        workflow_sha=args.workflow_sha,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        created_at=args.created_at,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "sbom.spdx.json", sbom)
    _write_json(args.output / "release-provenance.json", provenance)
    (args.output / "checksums.txt").write_text(checksums, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
