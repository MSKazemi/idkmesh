#!/usr/bin/env python3
"""Fail closed when a package release tag disagrees with shipped version metadata."""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_INIT = ROOT / "idkmesh" / "__init__.py"


class ReleaseVersionError(ValueError):
    """The release tag and package version sources do not form one identity."""


def pyproject_version() -> str:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ReleaseVersionError("pyproject.toml has no non-empty project.version")
    return version.strip()


def package_version() -> str:
    tree = ast.parse(PACKAGE_INIT.read_text(encoding="utf-8"), filename=str(PACKAGE_INIT))
    found: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            raise ReleaseVersionError("idkmesh.__version__ must be a literal string")
        found.append(node.value.value.strip())

    if len(found) != 1 or not found[0]:
        raise ReleaseVersionError(
            f"expected exactly one non-empty idkmesh.__version__, found {len(found)}"
        )
    return found[0]


def version_from_tag(tag: str) -> str:
    value = tag.strip()
    if value.startswith("refs/tags/"):
        value = value[len("refs/tags/") :]
    if value.startswith("v"):
        value = value[1:]
    if not value or any(character.isspace() for character in value):
        raise ReleaseVersionError(f"invalid release tag: {tag!r}")
    return value


def verify(tag: str) -> str:
    declared = pyproject_version()
    runtime = package_version()
    tagged = version_from_tag(tag)

    if declared != runtime:
        raise ReleaseVersionError(
            "package version drift: "
            f"pyproject.toml={declared!r}, idkmesh.__version__={runtime!r}"
        )
    if tagged != declared:
        raise ReleaseVersionError(
            "release tag does not match package version: "
            f"tag={tag!r} -> {tagged!r}, package={declared!r}"
        )
    return declared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        required=True,
        help="GitHub release tag, for example v0.1.0",
    )
    args = parser.parse_args(argv)

    try:
        version = verify(args.tag)
    except (OSError, SyntaxError, tomllib.TOMLDecodeError, ReleaseVersionError) as exc:
        print(f"release version preflight failed: {exc}", file=sys.stderr)
        return 2

    print(f"release version preflight passed: idkmesh {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
