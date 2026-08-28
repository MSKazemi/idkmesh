#!/usr/bin/env python3
"""Residual deterministic repository-health checks for IDKGraph P0.

This module fills two explicit issue #20 gaps without introducing semantic
inference:

- document orphan *candidates*: mapped ``document`` nodes below ``docs/`` that
  have no inbound resolved local Markdown link from another document;
- accepted ADR linkage: mapped ``decision`` nodes whose source file contains an
  explicit accepted ``Status:`` value but has no T3 ``implements`` edge from a
  mapped ``document`` node.

A document with no inbound Markdown link is not necessarily abandoned: it may be
owned by a workflow, script, or schema that references it by repository-relative
path. Those are reported separately, as a notice rather than an orphan warning,
because the condition is a navigation gap for human readers only -- the document
is demonstrably still referenced and maintained.

Both are warnings. Absence of a link cannot prove that a document is
unintentionally orphaned, and an accepted decision may intentionally affect
only non-document artifacts. The observatory therefore surfaces deterministic
conditions for human review rather than asserting semantic defects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import shape depends on invocation
    from .idkgraph_markdown_index import tracked_relative_paths
except ImportError:  # pragma: no cover
    from idkgraph_markdown_index import tracked_relative_paths

SCHEMA_VERSION = "idkgraph-health-checks-v0.1"
ACCEPTED_STATUS = re.compile(r"^accepted\b", re.IGNORECASE)
INDEX_FILENAMES = {"README.md", "index.md"}

# Repository-relative Markdown paths as they appear inside non-Markdown artifacts.
DOCUMENT_REFERENCE = re.compile(r"docs/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md")

# Artifact types that can legitimately own a document: workflows, scripts,
# schemas, and configuration. Deliberately an allowlist rather than "every file
# that is not Markdown", so that large result/data files are not rescanned and
# the scan cost stays bounded and predictable.
ARTIFACT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def _artifact_document_references(root: Path) -> dict[str, list[str]]:
    """Map document path -> sorted non-Markdown artifacts that reference it.

    Deterministic: the scan set is repository-tracked files with an allowlisted
    suffix, and every result list is sorted. Unreadable or non-UTF-8 files are
    skipped rather than guessed at.
    """
    tracked = tracked_relative_paths(root)
    references: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or not path.is_file():
            continue
        if path.suffix.lower() not in ARTIFACT_SUFFIXES:
            continue
        relative_posix = relative.as_posix()
        if tracked is not None and relative_posix not in tracked:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for target in DOCUMENT_REFERENCE.findall(text):
            references.setdefault(target, set()).add(relative_posix)
    return {target: sorted(sources) for target, sources in sorted(references.items())}


def _explicit_status(path: Path) -> str | None:
    """Read an explicit Markdown ``Status:`` field without interpreting prose."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None

    for line in lines:
        plain = line.replace("**", "").strip()
        plain = re.sub(r"^[-*]\s+", "", plain).strip()
        if plain.lower().startswith("status:"):
            value = plain.split(":", 1)[1].strip()
            return value or None
    return None


def _path_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        attributes = node.get("attributes")
        if not isinstance(attributes, dict):
            continue
        path = attributes.get("repository_path")
        if isinstance(path, str):
            result[path] = node
    return result


def check_residual_health(
    root: Path,
    graph: dict[str, Any],
    link_report: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic warning candidates for the two residual P0 checks."""
    root = root.resolve()
    path_to_node = _path_index(graph)
    nodes_by_id = {
        node["id"]: node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }

    inbound_local_markdown: set[str] = set()
    for link in link_report.get("resolved_links", []):
        if not isinstance(link, dict):
            continue
        source_path = link.get("source_path")
        target_path = link.get("target_path")
        if (
            isinstance(source_path, str)
            and isinstance(target_path, str)
            and source_path != target_path
        ):
            inbound_local_markdown.add(target_path)

    artifact_references = _artifact_document_references(root)

    findings: list[dict[str, Any]] = []

    # A deterministic candidate set, not a claim about intentionality:
    # - only typed documents;
    # - only below docs/;
    # - explicit directory index files are local entrypoints and are exempt.
    for path, node in sorted(path_to_node.items()):
        if node.get("type") != "document":
            continue
        if not path.startswith("docs/"):
            continue
        if Path(path).name in INDEX_FILENAMES:
            continue
        if path in inbound_local_markdown:
            continue
        owners = artifact_references.get(path)
        if owners:
            findings.append(
                {
                    "severity": "notice",
                    "category": "document_referenced_only_by_non_markdown_artifact",
                    "source_path": path,
                    "source_id": node["id"],
                    "line": 0,
                    "message": (
                        "No inbound Markdown link was observed, but the document is referenced by "
                        f"{len(owners)} non-Markdown repository artifact(s): {', '.join(owners)}. "
                        "The document is still referenced, so this is a navigation gap for human "
                        "readers rather than an orphan candidate."
                    ),
                    "evidence": {
                        "producer": "P0-health",
                        "producer_schema": SCHEMA_VERSION,
                        "rule": "typed_docs_document_referenced_only_by_non_markdown_artifact",
                        "referencing_artifacts": owners,
                    },
                }
            )
            continue
        findings.append(
            {
                "severity": "warning",
                "category": "orphan_document_candidate",
                "source_path": path,
                "source_id": node["id"],
                "line": 0,
                "message": (
                    "No inbound resolved local Markdown link from another document was observed. "
                    "This is a candidate for navigation review, not proof that the document is unintentionally orphaned."
                ),
                "evidence": {
                    "producer": "P0-health",
                    "producer_schema": SCHEMA_VERSION,
                    "rule": "typed_docs_document_without_inbound_local_markdown_link",
                },
            }
        )

    document_node_ids = {
        node_id for node_id, node in nodes_by_id.items() if node.get("type") == "document"
    }
    decisions_with_document_implementation = {
        target
        for edge in graph.get("hyperedges", [])
        if isinstance(edge, dict) and edge.get("relation") == "implements"
        for source in edge.get("sources", [])
        for target in edge.get("targets", [])
        if source in document_node_ids
    }

    for path, node in sorted(path_to_node.items()):
        if node.get("type") != "decision":
            continue
        status = _explicit_status(root / path)
        if status is None or ACCEPTED_STATUS.match(status) is None:
            continue
        if node["id"] in decisions_with_document_implementation:
            continue
        findings.append(
            {
                "severity": "warning",
                "category": "accepted_decision_without_document_link",
                "source_path": path,
                "source_id": node["id"],
                "line": 0,
                "message": (
                    "ADR has an explicit accepted status but no deterministic T3 implements relation "
                    "from a mapped document. Review whether an affected canonical document should declare the relationship."
                ),
                "evidence": {
                    "producer": "P0-health",
                    "producer_schema": SCHEMA_VERSION,
                    "rule": "accepted_adr_without_document_implements_edge",
                    "status": status,
                },
            }
        )

    findings.sort(
        key=lambda item: (
            item["category"],
            item["source_path"],
            item["source_id"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "orphan_document_candidates": sum(
                item["category"] == "orphan_document_candidate" for item in findings
            ),
            "accepted_decisions_without_document_link": sum(
                item["category"] == "accepted_decision_without_document_link" for item in findings
            ),
            "documents_referenced_only_by_non_markdown_artifacts": sum(
                item["category"] == "document_referenced_only_by_non_markdown_artifact"
                for item in findings
            ),
        },
        "findings": findings,
        "authority": {
            "repository_write": False,
            "semantic_inference": False,
            "automatic_repair": False,
        },
    }
