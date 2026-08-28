#!/usr/bin/env python3
"""Deterministic repository -> IDKGraph P0 observatory.

The observatory is intentionally conservative. It extracts only facts that can be
established from repository structure or explicit metadata. It does not use an
LLM, make semantic-duplication claims, rewrite files, or mutate GitHub state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlsplit

TOOL_VERSION = "0.1.0"
GRAPH_VERSION = "0.1"
EXECUTABLE_RELATIONS = {"depends_on", "requires"}
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "__pycache__"}

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE_RE = re.compile(r"^[ \t]*(```+|~~~+)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

NODE_TYPES = {
    "goal",
    "question",
    "hypothesis",
    "constraint",
    "work_unit",
    "artifact",
    "evidence",
    "decision",
    "metric",
    "contributor",
    "agent",
    "compute_resource",
    "document",
    "concept",
    "policy",
    "experiment",
}
RELATION_TYPES = {
    "decomposes_into",
    "depends_on",
    "requires",
    "produces",
    "blocks",
    "supports",
    "contradicts",
    "verifies",
    "invalidates",
    "derived_from",
    "supersedes",
    "implements",
    "documents",
    "defines",
    "mentions",
    "duplicates",
    "assigned_to",
    "reviewed_by",
    "generated_by",
    "uses_compute",
    "measured_by",
    "governed_by",
    "bridges",
}


@dataclass(frozen=True)
class Heading:
    id: str
    text: str
    level: int
    anchor: str
    line: int


@dataclass(frozen=True)
class RawLink:
    source_path: str
    raw_target: str
    line: int


@dataclass(frozen=True)
class Document:
    id: str
    path: str
    title: str
    headings: tuple[Heading, ...]
    links: tuple[RawLink, ...]


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    source: str
    message: str
    target: str = ""
    line: int | None = None


@dataclass(frozen=True)
class ResolvedLink:
    source_path: str
    target_path: str
    anchor: str
    line: int


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:20]}"


def _repo_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda p: _repo_rel(p, root))


def github_anchor_base(text: str) -> str:
    """A conservative GitHub-style heading slug for local diagnostics.

    This deliberately covers common GFM heading anchors without claiming to be a
    complete Markdown renderer. Unicode letters/numbers are preserved, ASCII
    punctuation is removed, whitespace becomes '-'. Duplicate headings receive
    '-1', '-2', ... in parse_markdown().
    """

    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    chars: list[str] = []
    for char in text:
        if char.isspace():
            chars.append("-")
        elif char.isalnum() or char in "-_":
            chars.append(char)
    return "".join(chars)


def _clean_link_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")].strip()

    # Markdown permits an optional title after whitespace. Keep escaped spaces in
    # a bare destination; otherwise take the first token. This is intentionally
    # conservative and deterministic rather than a full CommonMark parser.
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char.isspace():
            return value[:index]
    return value


def parse_markdown(path: Path, root: Path) -> Document:
    rel = _repo_rel(path, root)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    headings: list[Heading] = []
    links: list[RawLink] = []
    slug_counts: dict[str, int] = {}
    fence_marker: str | None = None

    for number, line in enumerate(lines, 1):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if fence_marker is None:
                fence_marker = marker
            elif fence_marker == marker:
                fence_marker = None
            continue
        if fence_marker is not None:
            continue

        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            base = github_anchor_base(text)
            occurrence = slug_counts.get(base, 0)
            slug_counts[base] = occurrence + 1
            anchor = base if occurrence == 0 else f"{base}-{occurrence}"
            headings.append(
                Heading(
                    id=_stable_id("heading", rel, anchor),
                    text=text,
                    level=level,
                    anchor=anchor,
                    line=number,
                )
            )

        for link_match in LINK_RE.finditer(line):
            links.append(
                RawLink(
                    source_path=rel,
                    raw_target=_clean_link_destination(link_match.group(1)),
                    line=number,
                )
            )

    title = headings[0].text if headings else PurePosixPath(rel).name
    return Document(
        id=_stable_id("document", rel),
        path=rel,
        title=title,
        headings=tuple(headings),
        links=tuple(links),
    )


def extract_documents(root: Path) -> list[Document]:
    return [
        parse_markdown(path, root)
        for path in _iter_files(root)
        if path.suffix.lower() == ".md"
    ]


def _is_external(destination: str) -> bool:
    parsed = urlsplit(destination)
    return bool(parsed.scheme or parsed.netloc) or destination.startswith("//")


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_internal_links(
    root: Path, documents: list[Document]
) -> tuple[list[ResolvedLink], list[Finding]]:
    root = root.resolve()
    by_path = {doc.path: doc for doc in documents}
    anchors = {doc.path: {h.anchor for h in doc.headings} for doc in documents}
    resolved: list[ResolvedLink] = []
    findings: list[Finding] = []

    for doc in documents:
        source_abs = root / doc.path
        for link in doc.links:
            destination = link.raw_target
            if not destination or _is_external(destination):
                continue
            if destination.startswith("/"):
                findings.append(
                    Finding(
                        "warning",
                        "unsupported_absolute_link",
                        doc.path,
                        "Repository-absolute link was not resolved by the P0 local-link checker.",
                        destination,
                        link.line,
                    )
                )
                continue

            parsed = urlsplit(destination)
            target_part = unquote(parsed.path)
            anchor = unquote(parsed.fragment)
            if target_part:
                target_abs = (source_abs.parent / target_part).resolve()
            else:
                target_abs = source_abs.resolve()

            if not _within_root(target_abs, root):
                findings.append(
                    Finding(
                        "warning",
                        "out_of_repository_link",
                        doc.path,
                        "Relative link resolves outside the repository root and was not followed.",
                        destination,
                        link.line,
                    )
                )
                continue

            if target_abs.is_dir() and (target_abs / "README.md").is_file():
                target_abs = target_abs / "README.md"

            if not target_abs.is_file():
                findings.append(
                    Finding(
                        "error",
                        "missing_target_file",
                        doc.path,
                        "Internal Markdown link points to a missing repository file.",
                        destination,
                        link.line,
                    )
                )
                continue

            target_rel = _repo_rel(target_abs, root)
            if anchor and target_rel.lower().endswith(".md"):
                if target_rel not in by_path:
                    # The file exists but was not a scanned Markdown document.
                    findings.append(
                        Finding(
                            "warning",
                            "unindexed_markdown_target",
                            doc.path,
                            "Markdown target exists but is outside the scanned document index.",
                            destination,
                            link.line,
                        )
                    )
                    continue
                if anchor not in anchors[target_rel]:
                    findings.append(
                        Finding(
                            "error",
                            "missing_target_anchor",
                            doc.path,
                            "Internal Markdown link points to a missing heading anchor.",
                            destination,
                            link.line,
                        )
                    )
                    continue

            resolved.append(
                ResolvedLink(doc.path, target_rel, anchor, link.line)
            )

    findings.sort(key=lambda f: (f.severity, f.category, f.source, f.line or 0, f.target))
    resolved.sort(key=lambda r: (r.source_path, r.line, r.target_path, r.anchor))
    return resolved, findings


def _git_commit(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return proc.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _artifact_paths(root: Path) -> list[str]:
    result: list[str] = []
    for path in _iter_files(root):
        rel = _repo_rel(path, root)
        if rel.startswith("schemas/") or rel.startswith("examples/"):
            result.append(rel)
    return result


def _load_explicit_work_units(root: Path) -> tuple[list[dict], list[dict], list[Finding]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    findings: list[Finding] = []
    seen_ids: dict[str, str] = {}

    for path in _iter_files(root):
        if not path.name.endswith(".workunit.json"):
            continue
        rel = _repo_rel(path, root)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding("error", "invalid_work_unit_json", rel, str(exc)))
            continue
        if not isinstance(data, dict) or data.get("type") != "work_unit":
            findings.append(
                Finding(
                    "error",
                    "invalid_work_unit_shape",
                    rel,
                    "*.workunit.json must be an object with type='work_unit'.",
                )
            )
            continue
        explicit_id = data.get("id")
        title = data.get("title")
        if not isinstance(explicit_id, str) or not explicit_id or not isinstance(title, str) or not title:
            findings.append(
                Finding(
                    "error",
                    "invalid_work_unit_shape",
                    rel,
                    "Explicit WorkUnit requires non-empty string id and title.",
                )
            )
            continue
        node_id = f"work_unit:{explicit_id}"
        if node_id in seen_ids:
            findings.append(
                Finding(
                    "error",
                    "duplicate_stable_id",
                    rel,
                    f"WorkUnit id duplicates {seen_ids[node_id]}: {node_id}",
                )
            )
            continue
        seen_ids[node_id] = rel
        nodes.append(
            {
                "id": node_id,
                "type": "work_unit",
                "title": title,
                "state": str(data.get("state", "specified")),
                "attributes": {"source_path": rel},
                "provenance": {"source": rel, "tool": f"idkgraph-observatory/{TOOL_VERSION}"},
            }
        )
        dependencies: list[str] = []
        for key in ("depends_on", "requires_all"):
            raw = data.get(key, [])
            if isinstance(raw, list):
                dependencies.extend(item for item in raw if isinstance(item, str) and item)
        for dependency in sorted(set(dependencies)):
            edges.append(
                {
                    "id": _stable_id("edge", node_id, "depends_on", f"work_unit:{dependency}"),
                    "relation": "depends_on",
                    "sources": [node_id],
                    "targets": [f"work_unit:{dependency}"],
                    "attributes": {"source_path": rel},
                    "provenance": {"source": rel, "tool": f"idkgraph-observatory/{TOOL_VERSION}"},
                }
            )

    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: e["id"])
    return nodes, edges, findings


def build_graph(
    root: Path,
    documents: list[Document],
    resolved_links: list[ResolvedLink],
) -> tuple[dict, list[Finding]]:
    root = root.resolve()
    commit = _git_commit(root)
    tool = f"idkgraph-observatory/{TOOL_VERSION}"
    nodes: list[dict] = []
    edges: list[dict] = []
    findings: list[Finding] = []
    doc_ids = {doc.path: doc.id for doc in documents}

    for doc in documents:
        nodes.append(
            {
                "id": doc.id,
                "type": "document",
                "title": doc.title,
                "attributes": {
                    "path": doc.path,
                    "headings": [asdict(heading) for heading in doc.headings],
                },
                "provenance": {"source": doc.path, "commit": commit, "tool": tool},
            }
        )
        if doc.path.startswith("docs/decisions/") and PurePosixPath(doc.path).name.startswith("ADR-"):
            decision_id = _stable_id("decision", doc.path)
            nodes.append(
                {
                    "id": decision_id,
                    "type": "decision",
                    "title": doc.title,
                    "attributes": {"source_path": doc.path},
                    "provenance": {"source": doc.path, "commit": commit, "tool": tool},
                }
            )
            edges.append(
                {
                    "id": _stable_id("edge", doc.id, "documents", decision_id),
                    "relation": "documents",
                    "sources": [doc.id],
                    "targets": [decision_id],
                    "provenance": {"source": doc.path, "commit": commit, "tool": tool},
                }
            )

    artifact_ids: dict[str, str] = {}
    for rel in _artifact_paths(root):
        artifact_id = _stable_id("artifact", rel)
        artifact_ids[rel] = artifact_id
        nodes.append(
            {
                "id": artifact_id,
                "type": "artifact",
                "title": PurePosixPath(rel).name,
                "attributes": {"path": rel},
                "provenance": {"source": rel, "commit": commit, "tool": tool},
            }
        )

    for link in resolved_links:
        if link.source_path == link.target_path:
            continue
        source_id = doc_ids.get(link.source_path)
        target_id = doc_ids.get(link.target_path) or artifact_ids.get(link.target_path)
        if not source_id or not target_id:
            continue
        edges.append(
            {
                "id": _stable_id("edge", source_id, "mentions", target_id, str(link.line)),
                "relation": "mentions",
                "sources": [source_id],
                "targets": [target_id],
                "attributes": {"source_line": link.line, "anchor": link.anchor},
                "provenance": {"source": link.source_path, "commit": commit, "tool": tool},
            }
        )

    work_nodes, work_edges, work_findings = _load_explicit_work_units(root)
    nodes.extend(work_nodes)
    edges.extend(work_edges)
    findings.extend(work_findings)

    node_ids: set[str] = set()
    for node in sorted(nodes, key=lambda n: (n["id"], n["type"])):
        if node["id"] in node_ids:
            findings.append(
                Finding(
                    "error",
                    "duplicate_stable_id",
                    str(node.get("provenance", {}).get("source", "")),
                    f"Generated duplicate graph node id: {node['id']}",
                )
            )
        node_ids.add(node["id"])

    graph = {
        "graph_id": _stable_id("graph", commit if commit != "unknown" else "working-tree"),
        "version": GRAPH_VERSION,
        "nodes": sorted(nodes, key=lambda n: (n["id"], n["type"])),
        "hyperedges": sorted(edges, key=lambda e: e["id"]),
        "events": [],
    }
    return graph, findings


def executable_cycle_witness(graph: dict) -> list[str] | None:
    work_units = {
        node["id"]
        for node in graph.get("nodes", [])
        if node.get("type") == "work_unit" and isinstance(node.get("id"), str)
    }
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in work_units}
    for edge in graph.get("hyperedges", []):
        if edge.get("relation") not in EXECUTABLE_RELATIONS:
            continue
        for source in edge.get("sources", []):
            for target in edge.get("targets", []):
                if source in work_units and target in work_units:
                    adjacency[source].add(target)

    state: dict[str, int] = {node_id: 0 for node_id in work_units}
    stack: list[str] = []

    def visit(node_id: str) -> list[str] | None:
        state[node_id] = 1
        stack.append(node_id)
        for target in sorted(adjacency[node_id]):
            if state[target] == 0:
                witness = visit(target)
                if witness:
                    return witness
            elif state[target] == 1:
                start = stack.index(target)
                return stack[start:] + [target]
        stack.pop()
        state[node_id] = 2
        return None

    for node_id in sorted(work_units):
        if state[node_id] == 0:
            witness = visit(node_id)
            if witness:
                return witness
    return None


def orphan_findings(documents: list[Document], resolved_links: list[ResolvedLink]) -> list[Finding]:
    incoming = {doc.path: 0 for doc in documents}
    for link in resolved_links:
        if link.source_path != link.target_path and link.target_path in incoming:
            incoming[link.target_path] += 1
    findings: list[Finding] = []
    for path, count in sorted(incoming.items()):
        if count:
            continue
        if path == "README.md" or path.startswith(".github/"):
            continue
        findings.append(
            Finding(
                "warning",
                "orphan_document",
                path,
                "Markdown document has no incoming repository-local Markdown link.",
            )
        )
    return findings


def validate_graph_shape(graph: dict) -> list[str]:
    """Small fail-closed shape check; JSON Schema validation is optional in CLI."""

    errors: list[str] = []
    for key in ("graph_id", "version", "nodes", "hyperedges"):
        if key not in graph:
            errors.append(f"missing required graph key: {key}")
    node_ids: set[str] = set()
    for index, node in enumerate(graph.get("nodes", [])):
        if node.get("type") not in NODE_TYPES:
            errors.append(f"nodes[{index}] has unsupported type {node.get('type')!r}")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"nodes[{index}] has invalid id")
        elif node_id in node_ids:
            errors.append(f"duplicate graph node id: {node_id}")
        else:
            node_ids.add(node_id)
        if not isinstance(node.get("title"), str) or not node.get("title"):
            errors.append(f"nodes[{index}] has invalid title")
    for index, edge in enumerate(graph.get("hyperedges", [])):
        if edge.get("relation") not in RELATION_TYPES:
            errors.append(f"hyperedges[{index}] has unsupported relation {edge.get('relation')!r}")
        if not edge.get("sources") or not edge.get("targets"):
            errors.append(f"hyperedges[{index}] requires non-empty sources and targets")
    return errors


def validate_against_schema(graph: dict, schema_path: Path) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return ["jsonschema is not installed; install requirements-phase0.txt for schema validation"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(graph), key=lambda e: list(e.path))]


def build_report(root: Path, graph: dict, findings: list[Finding]) -> str:
    counts: dict[tuple[str, str], int] = {}
    for finding in findings:
        key = (finding.severity, finding.category)
        counts[key] = counts.get(key, 0) + 1

    commit = _git_commit(root)
    lines = [
        "# IDKGraph Repository Observatory Report",
        "",
        f"- Tool: `idkgraph-observatory/{TOOL_VERSION}`",
        f"- Source commit: `{commit}`",
        f"- Nodes: **{len(graph.get('nodes', []))}**",
        f"- Hyperedges: **{len(graph.get('hyperedges', []))}**",
        f"- Deterministic errors: **{sum(1 for f in findings if f.severity == 'error')}**",
        f"- Warnings: **{sum(1 for f in findings if f.severity == 'warning')}**",
        "",
        "## Findings by category",
        "",
        "| Severity | Category | Count |",
        "| --- | --- | ---: |",
    ]
    if counts:
        for (severity, category), count in sorted(counts.items()):
            lines.append(f"| {severity} | `{category}` | {count} |")
    else:
        lines.append("| - | none | 0 |")

    lines.extend(["", "## Detailed findings", ""])
    if findings:
        for finding in findings:
            location = finding.source
            if finding.line is not None:
                location += f":{finding.line}"
            target = f" -> `{finding.target}`" if finding.target else ""
            lines.append(
                f"- **{finding.severity.upper()} `{finding.category}`** `{location}`{target}: {finding.message}"
            )
    else:
        lines.append("No deterministic repository-health findings.")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Errors above are deterministic structural defects according to this P0 parser. Warnings are observations that require review. The observatory does not infer semantic contradiction, duplication, importance, or correctness from prose.",
            "",
            "## Replay",
            "",
            "```bash",
            "python tools/idkgraph_observatory.py --root . --graph-out results/idkgraph/graph.json --report-out results/idkgraph/report.md --schema schemas/idkgraph.schema.json",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def observe(root: Path) -> tuple[dict, list[Finding], str]:
    root = root.resolve()
    documents = extract_documents(root)
    resolved_links, link_findings = resolve_internal_links(root, documents)
    graph, mapping_findings = build_graph(root, documents, resolved_links)
    findings = list(link_findings)
    findings.extend(mapping_findings)
    findings.extend(orphan_findings(documents, resolved_links))

    cycle = executable_cycle_witness(graph)
    if cycle:
        findings.append(
            Finding(
                "error",
                "executable_dependency_cycle",
                "IDKGraph",
                "Executable WorkUnit dependency projection contains a cycle: " + " -> ".join(cycle),
            )
        )

    for error in validate_graph_shape(graph):
        findings.append(Finding("error", "invalid_graph_shape", "IDKGraph", error))

    findings.sort(key=lambda f: (f.severity, f.category, f.source, f.line or 0, f.target, f.message))
    report = build_report(root, graph, findings)
    return graph, findings, report


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root")
    parser.add_argument("--graph-out", type=Path, default=Path("results/idkgraph/graph.json"))
    parser.add_argument("--report-out", type=Path, default=Path("results/idkgraph/report.md"))
    parser.add_argument("--schema", type=Path, help="Optional JSON Schema path for strict validation")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero when deterministic errors exist")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    graph, findings, report = observe(root)

    if args.schema:
        schema_path = args.schema if args.schema.is_absolute() else root / args.schema
        schema_errors = validate_against_schema(graph, schema_path)
        for message in schema_errors:
            findings.append(Finding("error", "schema_validation", str(args.schema), message))
        if schema_errors:
            findings.sort(key=lambda f: (f.severity, f.category, f.source, f.message))
            report = build_report(root, graph, findings)

    graph_out = args.graph_out if args.graph_out.is_absolute() else root / args.graph_out
    report_out = args.report_out if args.report_out.is_absolute() else root / args.report_out
    _write_text(graph_out, json.dumps(graph, indent=2, sort_keys=True) + "\n")
    _write_text(report_out, report)

    error_count = sum(1 for finding in findings if finding.severity == "error")
    print(f"IDKGraph observatory: {len(graph['nodes'])} nodes, {len(graph['hyperedges'])} edges, {error_count} errors")
    return 1 if args.fail_on_error and error_count else 0


if __name__ == "__main__":
    sys.exit(main())
