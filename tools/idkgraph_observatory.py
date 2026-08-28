#!/usr/bin/env python3
"""Unified read-only IDKGraph P0 observatory.

T5 composes the canonical deterministic boundaries that landed before it:

- T1 Markdown identity (consumed transitively by T2/T3);
- T2 local Markdown link integrity;
- T3 repository -> typed IDKGraph mapping;
- T4 executable WorkUnit dependency-cycle checking.

One run emits three deterministic artifacts:

- ``idkgraph.json`` -- schema-compatible T3 graph;
- ``observatory.json`` -- normalized P0 evidence/provenance summary;
- ``repository-health.md`` -- human-readable report.

No automatic repair, repository mutation, GitHub mutation, semantic inference,
approval, push, or merge authority is present.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.idkgraph_link_check import check_links
from tools.idkgraph_repository_mapping import (
    SCHEMA_VERSION as T3_SCHEMA_VERSION,
    build_repository_graph,
    serialize_graph,
)
from tools.idkgraph_workunit_cycles import (
    SCHEMA_VERSION as T4_SCHEMA_VERSION,
    check_graph,
)

SCHEMA_VERSION = "idkgraph-observatory-v0.1"
REPORT_FILENAME = "repository-health.md"
GRAPH_FILENAME = "idkgraph.json"
SUMMARY_FILENAME = "observatory.json"
SEVERITY_ORDER = {"error": 0, "warning": 1}


def detect_git_revision(root: Path) -> str | None:
    """Return HEAD only when ``root`` itself is the Git worktree root."""
    root = root.resolve()
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        if Path(top).resolve() != root:
            return None
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return head if head else None


def _sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _graph_indexes(graph: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    path_to_id: dict[str, str] = {}
    id_to_path: dict[str, str] = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        attributes = node.get("attributes")
        if not isinstance(node_id, str) or not isinstance(attributes, dict):
            continue
        path = attributes.get("repository_path")
        if isinstance(path, str):
            path_to_id[path] = node_id
            id_to_path[node_id] = path
    return path_to_id, id_to_path


def _normalize_findings(
    link_report: dict[str, Any],
    cycle_report: dict[str, Any],
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    path_to_id, id_to_path = _graph_indexes(graph)
    findings: list[dict[str, Any]] = []

    for finding in link_report.get("findings", []):
        source_path = finding.get("source_path")
        findings.append(
            {
                "severity": finding.get("severity", "warning"),
                "category": finding.get("category", "unknown_navigation_finding"),
                "source_path": source_path,
                "source_id": path_to_id.get(source_path) if isinstance(source_path, str) else None,
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
                "evidence": {
                    "producer": "T2",
                    "producer_schema": link_report.get("schema_version"),
                    "raw_target": finding.get("raw_target"),
                },
            }
        )

    if cycle_report.get("cycle_detected"):
        witness = cycle_report.get("cycle_witness") or []
        first_id = witness[0] if witness else None
        findings.append(
            {
                "severity": "error",
                "category": "executable_workunit_cycle",
                "source_path": id_to_path.get(first_id) if isinstance(first_id, str) else None,
                "source_id": first_id,
                "line": 0,
                "message": "Executable WorkUnit dependency projection contains a cycle.",
                "evidence": {
                    "producer": "T4",
                    "producer_schema": cycle_report.get("schema_version"),
                    "cycle_witness": witness,
                },
            }
        )

    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item["severity"]), 99),
            str(item["category"]),
            str(item.get("source_path") or ""),
            int(item.get("line") or 0),
            str(item.get("source_id") or ""),
            str(item.get("message") or ""),
        )
    )
    return findings


def _count_node_types(graph: dict[str, Any]) -> dict[str, int]:
    counts = Counter(
        node.get("type", "unknown")
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
    )
    return dict(sorted(counts.items()))


def _finding_counts(findings: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    severity = Counter(str(item["severity"]) for item in findings)
    category = Counter(str(item["category"]) for item in findings)
    return dict(sorted(severity.items())), dict(sorted(category.items()))


def build_observatory(
    root: Path,
    *,
    source_revision: str | None = None,
    revision_method: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compose T2/T3/T4 evidence for one fixed repository tree."""
    root = root.resolve()
    graph = build_repository_graph(root)
    link_report = check_links(root)
    cycle_report = check_graph(graph)

    if source_revision is None:
        source_revision = detect_git_revision(root)
        revision_method = "git_head" if source_revision else "unavailable"
    elif revision_method is None:
        revision_method = "explicit"

    graph_payload = serialize_graph(graph)
    findings = _normalize_findings(link_report, cycle_report, graph)
    severity_counts, category_counts = _finding_counts(findings)

    research_hypotheses: list[dict[str, Any]] = []
    observatory = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": SCHEMA_VERSION,
        "root": ".",
        "source_revision": source_revision,
        "source_revision_method": revision_method,
        "contracts": {
            "t1_identity": link_report.get("identity_contract"),
            "t2_navigation": link_report.get("schema_version"),
            "t3_repository_mapping": T3_SCHEMA_VERSION,
            "t4_executable_cycles": T4_SCHEMA_VERSION,
        },
        "artifacts": {
            "graph": GRAPH_FILENAME,
            "summary": SUMMARY_FILENAME,
            "report": REPORT_FILENAME,
        },
        "graph": {
            "graph_id": graph.get("graph_id"),
            "nodes": len(graph.get("nodes", [])),
            "hyperedges": len(graph.get("hyperedges", [])),
            "node_types": _count_node_types(graph),
            "sha256": _sha256_text(graph_payload),
        },
        "navigation": link_report.get("summary", {}),
        "execution": {
            "work_units": len(cycle_report["projection"]["work_unit_ids"]),
            "dependency_edges": cycle_report["projection"]["edge_count"],
            "included_hyperedge_ids": cycle_report["projection"]["included_hyperedge_ids"],
            "ignored_hyperedges": cycle_report["projection"]["ignored_hyperedges"],
            "cycle_detected": cycle_report.get("cycle_detected", False),
            "cycle_witness": cycle_report.get("cycle_witness"),
        },
        "finding_counts": {
            "by_severity": severity_counts,
            "by_category": category_counts,
        },
        "findings": findings,
        "research_hypotheses": research_hypotheses,
        "authority": {
            "repository_write": False,
            "github_mutation": False,
            "semantic_inference": False,
            "automatic_repair": False,
            "integration": False,
        },
    }
    return graph, observatory


def serialize_observatory(observatory: dict[str, Any], *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(observatory, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(observatory, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_health_report(observatory: dict[str, Any]) -> str:
    """Render deterministic human-readable evidence from ``observatory``."""
    graph = observatory["graph"]
    navigation = observatory["navigation"]
    execution = observatory["execution"]
    counts = observatory["finding_counts"]["by_severity"]
    findings = observatory["findings"]
    revision = observatory.get("source_revision") or "unavailable"

    lines = [
        "# IDKGraph P0 Repository Health Report",
        "",
        "This report is deterministic observation evidence. Lower or higher counts are not, by themselves, proof of project quality.",
        "",
        "## Provenance",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Tool | `{_md(observatory['tool_version'])}` |",
        f"| Source revision | `{_md(revision)}` |",
        f"| Revision method | `{_md(observatory['source_revision_method'])}` |",
        f"| Graph SHA-256 | `{_md(graph['sha256'])}` |",
        "",
        "## Deterministic summary",
        "",
        "| Observation | Count / value |",
        "| --- | ---: |",
        f"| Typed graph nodes | {graph['nodes']} |",
        f"| Typed graph hyperedges | {graph['hyperedges']} |",
        f"| Markdown documents scanned | {navigation.get('documents_scanned', 0)} |",
        f"| Local Markdown links | {navigation.get('local_markdown_links', 0)} |",
        f"| Resolved local Markdown links | {navigation.get('resolved_local_markdown_links', 0)} |",
        f"| Executable WorkUnits | {execution['work_units']} |",
        f"| Executable dependency edges | {execution['dependency_edges']} |",
        f"| Executable cycle detected | {'yes' if execution['cycle_detected'] else 'no'} |",
        f"| Deterministic errors | {counts.get('error', 0)} |",
        f"| Deterministic warnings | {counts.get('warning', 0)} |",
        "",
        "### Node types",
        "",
    ]

    if graph["node_types"]:
        lines.extend(["| Type | Count |", "| --- | ---: |"])
        for node_type, count in graph["node_types"].items():
            lines.append(f"| `{_md(node_type)}` | {count} |")
    else:
        lines.append("No deterministic repository nodes were mapped.")

    lines.extend(["", "## Deterministic errors", ""])
    errors = [item for item in findings if item["severity"] == "error"]
    if errors:
        lines.extend(["| Category | Source | Line | ID | Message |", "| --- | --- | ---: | --- | --- |"])
        for item in errors:
            lines.append(
                f"| `{_md(item['category'])}` | `{_md(item.get('source_path') or '-')}` | "
                f"{item.get('line') or 0} | `{_md(item.get('source_id') or '-')}` | {_md(item['message'])} |"
            )
    else:
        lines.append("No deterministic P0 errors were observed.")

    lines.extend(["", "## Deterministic warnings", ""])
    warnings = [item for item in findings if item["severity"] == "warning"]
    if warnings:
        lines.extend(["| Category | Source | Line | ID | Message |", "| --- | --- | ---: | --- | --- |"])
        for item in warnings:
            lines.append(
                f"| `{_md(item['category'])}` | `{_md(item.get('source_path') or '-')}` | "
                f"{item.get('line') or 0} | `{_md(item.get('source_id') or '-')}` | {_md(item['message'])} |"
            )
    else:
        lines.append("No deterministic P0 warnings were observed.")

    lines.extend(
        [
            "",
            "## Research hypotheses",
            "",
            "None are emitted automatically by the deterministic P0 observatory. Semantic contradiction, duplication, importance, and health-value judgments require a separately reviewed evidence/inference layer.",
            "",
            "## Replay",
            "",
            "From the repository root, run:",
            "",
            "```bash",
            "python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-observatory --pretty",
            "```",
            "",
            "The same repository bytes, tool version, and source revision should produce semantically identical graph/findings. No timestamp is injected into P0 output.",
            "",
            "## Authority",
            "",
            "This observatory is read-only. It cannot repair files, change the graph source, mutate GitHub, approve changes, push, merge, or infer semantic truth.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    root: Path,
    output_dir: Path,
    *,
    source_revision: str | None = None,
    revision_method: str | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir == root or root in output_dir.parents:
        raise ValueError("output directory must be outside the scanned repository tree")

    graph, observatory = build_observatory(
        root,
        source_revision=source_revision,
        revision_method=revision_method,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / GRAPH_FILENAME).write_text(serialize_graph(graph, pretty=pretty), encoding="utf-8")
    (output_dir / SUMMARY_FILENAME).write_text(
        serialize_observatory(observatory, pretty=pretty),
        encoding="utf-8",
    )
    (output_dir / REPORT_FILENAME).write_text(render_health_report(observatory), encoding="utf-8")
    return observatory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repository or fixture root to inspect.")
    parser.add_argument("--output-dir", required=True, help="Output directory; must be outside the scanned tree.")
    parser.add_argument("--source-revision", help="Explicit immutable source revision for non-Git snapshots.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON artifacts.")
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit 1 after writing evidence if deterministic P0 errors are present.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    try:
        observatory = write_outputs(
            root,
            Path(args.output_dir),
            source_revision=args.source_revision,
            revision_method="explicit" if args.source_revision else None,
            pretty=args.pretty,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))

    errors = observatory["finding_counts"]["by_severity"].get("error", 0)
    return 1 if args.fail_on_errors and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
