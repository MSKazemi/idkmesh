#!/usr/bin/env python3
"""Deterministically map explicit repository structure into IDKGraph v0.

This P0 mapper deliberately avoids semantic inference. It recognizes only:

- ordinary Markdown files -> ``document`` using the canonical T1 document ID;
- ``docs/decisions/ADR-NNNN-*.md`` -> ``decision`` by filename convention;
- ``*.work-unit.json`` with a stable JSON ``id`` -> ``work_unit``;
- files below ``schemas/`` and non-WorkUnit files below ``examples/`` -> ``artifact``.

Relations are created only from explicit machine-readable or convention-bound
sources:

- paths listed under an ADR ``## Implementation references`` section ->
  ``implements`` the decision;
- WorkUnit ``inputs[].locator`` paths -> ``requires`` the mapped artifact.

No concept/support/contradiction/duplicate relation is inferred from prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.idkgraph_markdown_index import document_id, parse_markdown

SCHEMA_VERSION = "idkgraph-repository-mapping-v0.1"
ADR_NAME = re.compile(r"^(ADR-\d{4})-[A-Za-z0-9._-]+\.md$")
WORK_UNIT_SUFFIX = ".work-unit.json"
IMPLEMENTATION_HEADING = re.compile(r"^##\s+Implementation references\s*$", re.IGNORECASE)
NEXT_HEADING = re.compile(r"^#{1,6}\s+")
CODE_PATH_BULLET = re.compile(r"^\s*[-*]\s+`([^`]+)`(?:\s|$)")


def _edge_id(relation: str, sources: Iterable[str], targets: Iterable[str]) -> str:
    payload = "\0".join([relation, *sorted(sources), "->", *sorted(targets)]).encode("utf-8")
    return f"edge:{hashlib.sha256(payload).hexdigest()[:24]}"


def _artifact_id(relative_path: str) -> str:
    return f"artifact:{relative_path}"


def _decision_id(adr_number: str) -> str:
    return f"decision:{adr_number}"


def _work_unit_id(source_id: str) -> str:
    return f"work_unit:{source_id}"


def _first_heading_title(path: Path, root: Path) -> str:
    parsed = parse_markdown(path, root)
    return parsed["headings"][0]["text"] if parsed["headings"] else path.stem


def _node(
    *,
    node_id: str,
    node_type: str,
    title: str,
    relative_path: str,
    source_kind: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_attributes = {
        "repository_path": relative_path,
        "source_kind": source_kind,
        "mapping_method": "deterministic_repository_structure",
    }
    if attributes:
        merged_attributes.update(attributes)
    return {
        "id": node_id,
        "type": node_type,
        "title": title,
        "attributes": merged_attributes,
        "provenance": {
            "source": relative_path,
            "tool": SCHEMA_VERSION,
        },
    }


def classify_repository_file(path: Path, root: Path) -> dict[str, Any] | None:
    """Map one repository file to at most one canonical P0 node."""
    relative_path = path.relative_to(root).as_posix()

    if path.suffix.lower() == ".md":
        adr_match = ADR_NAME.fullmatch(path.name) if relative_path.startswith("docs/decisions/") else None
        if adr_match:
            adr_number = adr_match.group(1)
            return _node(
                node_id=_decision_id(adr_number),
                node_type="decision",
                title=_first_heading_title(path, root),
                relative_path=relative_path,
                source_kind="architecture_decision_file",
                attributes={"decision_key": adr_number},
            )
        return _node(
            node_id=document_id(relative_path),
            node_type="document",
            title=_first_heading_title(path, root),
            relative_path=relative_path,
            source_kind="markdown_document",
            attributes={"t1_identity": True},
        )

    if path.name.endswith(WORK_UNIT_SUFFIX):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        source_id = value.get("id") if isinstance(value, dict) else None
        if not isinstance(source_id, str) or not source_id.strip():
            return None
        objective = value.get("objective")
        title = objective if isinstance(objective, str) and objective.strip() else source_id
        return _node(
            node_id=_work_unit_id(source_id),
            node_type="work_unit",
            title=title,
            relative_path=relative_path,
            source_kind="canonical_work_unit",
            attributes={"work_unit_source_id": source_id, "schema_version": value.get("schema_version")},
        )

    if relative_path.startswith("schemas/") or relative_path.startswith("examples/"):
        return _node(
            node_id=_artifact_id(relative_path),
            node_type="artifact",
            title=relative_path,
            relative_path=relative_path,
            source_kind="repository_artifact",
        )

    return None


def _adr_implementation_paths(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    paths: list[str] = []
    for line in lines:
        if IMPLEMENTATION_HEADING.match(line):
            in_section = True
            continue
        if in_section and NEXT_HEADING.match(line):
            break
        if not in_section:
            continue
        match = CODE_PATH_BULLET.match(line)
        if match:
            paths.append(match.group(1))
    return sorted(set(paths))


def _work_unit_input_paths(path: Path) -> list[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(value, dict):
        return []
    paths: list[str] = []
    for item in value.get("inputs", []):
        if not isinstance(item, dict):
            continue
        locator = item.get("locator")
        if isinstance(locator, str) and locator.strip():
            paths.append(locator)
    return sorted(set(paths))


def build_repository_graph(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )

    nodes: list[dict[str, Any]] = []
    path_to_node: dict[str, dict[str, Any]] = {}
    for path in files:
        node = classify_repository_file(path, root)
        if node is None:
            continue
        relative_path = path.relative_to(root).as_posix()
        nodes.append(node)
        path_to_node[relative_path] = node

    edges: list[dict[str, Any]] = []

    for relative_path, node in sorted(path_to_node.items()):
        source_path = root / relative_path
        if node["type"] == "decision":
            for referenced_path in _adr_implementation_paths(source_path):
                referenced = path_to_node.get(referenced_path)
                if referenced is None:
                    continue
                sources = [referenced["id"]]
                targets = [node["id"]]
                edges.append(
                    {
                        "id": _edge_id("implements", sources, targets),
                        "relation": "implements",
                        "sources": sources,
                        "targets": targets,
                        "attributes": {
                            "mapping_rule": "adr_implementation_reference",
                            "declared_in": relative_path,
                            "declared_path": referenced_path,
                        },
                        "provenance": {"source": relative_path, "tool": SCHEMA_VERSION},
                    }
                )

        if node["type"] == "work_unit":
            for input_path in _work_unit_input_paths(source_path):
                referenced = path_to_node.get(input_path)
                if referenced is None:
                    continue
                sources = [node["id"]]
                targets = [referenced["id"]]
                edges.append(
                    {
                        "id": _edge_id("requires", sources, targets),
                        "relation": "requires",
                        "sources": sources,
                        "targets": targets,
                        "attributes": {
                            "mapping_rule": "work_unit_input_locator",
                            "declared_in": relative_path,
                            "declared_path": input_path,
                        },
                        "provenance": {"source": relative_path, "tool": SCHEMA_VERSION},
                    }
                )

    nodes.sort(key=lambda item: item["id"])
    edges.sort(key=lambda item: item["id"])
    return {
        "graph_id": "repository:deterministic-p0",
        "version": "0.1",
        "nodes": nodes,
        "hyperedges": edges,
        "events": [],
    }


def serialize_graph(graph: dict[str, Any], pretty: bool = False) -> str:
    if pretty:
        return json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map explicit repository structures into deterministic IDKGraph nodes/relations.")
    parser.add_argument("root", nargs="?", default=".", help="Repository or fixture root.")
    parser.add_argument("--output", help="Write graph JSON to this path instead of stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    payload = serialize_graph(build_repository_graph(root), pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
