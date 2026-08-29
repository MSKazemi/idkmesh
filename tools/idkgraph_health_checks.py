#!/usr/bin/env python3
"""Residual deterministic repository-health checks for IDKGraph P0.

This module fills two explicit issue #20 gaps without introducing semantic
inference:

- document orphan *candidates*: mapped ``document`` nodes below ``docs/`` that
  have no inbound resolved local Markdown link from another document;
- accepted ADR linkage: mapped ``decision`` nodes whose source file contains an
  explicit accepted ``Status:`` value but has no T3 ``implements`` edge from a
  mapped ``document`` node;
- executables that nothing exercises: committed Python entry points below
  ``tools/`` or ``scripts/`` that no workflow and no test names, and whose name
  appears in no recorded result, benchmark, or document.

The third check is deliberately conjunctive. A one-shot calibration tool that
ran once and left committed evidence behind is doing exactly its job and is not
debt; only a tool that is neither wired into automation *nor* traceable to any
recorded output is a review candidate. It is reported as a notice, because an
executable can be legitimately dormant -- waiting on an absent dependency, or
staged ahead of the run that will use it -- and this module cannot tell that
apart from abandonment.

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

# Committed Python entry points. Dunder files are module plumbing, not entry
# points, so a package's ``__main__.py`` is never a candidate on its own.
EXECUTABLE_PREFIXES = ("scripts/", "tools/")

# What counts as exercising an executable: CI wiring or the test suite.
EXERCISER_PREFIXES = (".github/workflows/", "tests/")

# Where a tool's output would have been recorded if it had ever produced one.
RECORDED_OUTPUT_PREFIXES = ("benchmarks/", "docs/", "experiments/results/", "results/")

# Findings reports are excluded, and the exclusion is not hypothetical. The first
# report this check produced named all five of its own findings in a table, which
# cleared all five on the next run. A report *about* repository health is analysis,
# not evidence that a tool ran; without this exclusion the check silences itself the
# moment anyone writes down what it found.
RECORDED_OUTPUT_EXCLUDED_PREFIXES = ("docs/findings/",)

# Binary and compressed payloads are skipped rather than decoded; a tool name
# hidden inside a gzip member is not a reference a human reviewer could follow.
OPAQUE_SUFFIXES = {".gz", ".jpg", ".jpeg", ".pdf", ".png", ".zip"}

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


def _tool_id(relative_path: str) -> str:
    """Identify an executable that the T3 mapping does not give a node.

    ``tools/`` and ``scripts/`` are outside the typed graph, so this identifier
    is deliberately in its own namespace rather than borrowing ``artifact:``.
    """
    return f"executable:{relative_path}"


def _mentions(blob: str, relative_path: str) -> bool:
    """True when text refers to an executable by path, module, or bare stem.

    The stem must match on identifier boundaries. Plain substring matching is
    wrong here: ``tools/real_node_verifier_e2e.py`` contains the stem of
    ``tools/node_verifier_e2e.py``, so a substring test would silently clear an
    executable that nothing actually references.
    """
    if relative_path in blob:
        return True
    module = relative_path[:-3].replace("/", ".")
    if module in blob:
        return True
    stem = re.escape(Path(relative_path).stem)
    return re.search(rf"(?<![A-Za-z0-9_]){stem}(?![A-Za-z0-9_])", blob) is not None


def _readable_blob(
    root: Path,
    tracked: set[str],
    prefixes: tuple[str, ...],
    excluded: tuple[str, ...] = (),
) -> str:
    """Concatenate tracked text files under the given prefixes, in path order."""
    parts: list[str] = []
    for relative_path in sorted(tracked):
        if not relative_path.startswith(prefixes):
            continue
        if excluded and relative_path.startswith(excluded):
            continue
        if Path(relative_path).suffix.lower() in OPAQUE_SUFFIXES:
            continue
        try:
            parts.append((root / relative_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
    return "\n".join(parts)


def _unexercised_executables(root: Path) -> list[str]:
    """Return committed entry points with no automated exercise and no output.

    Returns an empty list when the tracked-file set is unavailable: an
    unanswerable question is reported as no finding, never as a finding.
    """
    tracked = tracked_relative_paths(root)
    if tracked is None:
        return []
    candidates = [
        relative_path
        for relative_path in sorted(tracked)
        if relative_path.startswith(EXECUTABLE_PREFIXES)
        and relative_path.endswith(".py")
        and not Path(relative_path).name.startswith("__")
    ]
    if not candidates:
        return []
    exercisers = _readable_blob(root, tracked, EXERCISER_PREFIXES)
    recorded = _readable_blob(
        root, tracked, RECORDED_OUTPUT_PREFIXES, RECORDED_OUTPUT_EXCLUDED_PREFIXES
    )
    return [
        relative_path
        for relative_path in candidates
        if not _mentions(exercisers, relative_path) and not _mentions(recorded, relative_path)
    ]


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

    for relative_path in _unexercised_executables(root):
        findings.append(
            {
                "severity": "notice",
                "category": "executable_without_exercise_or_recorded_output",
                "source_path": relative_path,
                "source_id": _tool_id(relative_path),
                "line": 0,
                "message": (
                    "This committed entry point is named by no workflow and no test, and its name "
                    "appears in no recorded result, benchmark, or document. Nothing in the "
                    "repository demonstrates that it has ever run. Review whether it should be "
                    "wired into automation, exercised once and its evidence recorded, or removed."
                ),
                "evidence": {
                    "producer": "P0-health",
                    "producer_schema": SCHEMA_VERSION,
                    "rule": "executable_absent_from_automation_and_from_recorded_output",
                    "exerciser_prefixes": list(EXERCISER_PREFIXES),
                    "recorded_output_prefixes": list(RECORDED_OUTPUT_PREFIXES),
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
