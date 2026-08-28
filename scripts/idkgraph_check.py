#!/usr/bin/env python3
"""Deterministic invariant checker for IDKGraph v0.

Checks structural invariants that do not require semantic AI interpretation:
- unique node / hyperedge / event identifiers;
- all edge endpoints reference existing nodes;
- supersedes edges point to an existing prior object;
- executable WorkUnit dependency projection is acyclic.

This tool is intentionally read-only and standard-library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

EXEC_RELATIONS = {"depends_on", "requires", "blocks", "decomposes_into"}


def load_graph(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("graph root must be an object")
    return data


def duplicate_ids(items: list[dict[str, Any]], kind: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            duplicates.append(f"{kind}:<missing-id>")
            continue
        if ident in seen:
            duplicates.append(f"{kind}:{ident}")
        seen.add(ident)
    return duplicates


def executable_cycle(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str] | None:
    work_units = {n["id"] for n in nodes if n.get("type") == "work_unit" and isinstance(n.get("id"), str)}
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in work_units}

    for edge in edges:
        if edge.get("relation") not in EXEC_RELATIONS:
            continue
        sources = [x for x in edge.get("sources", []) if x in work_units]
        targets = [x for x in edge.get("targets", []) if x in work_units]
        for source in sources:
            for target in targets:
                if target not in adjacency[source]:
                    adjacency[source].add(target)
                    indegree[target] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    while queue:
        node = queue.popleft()
        visited.append(node)
        for nxt in sorted(adjacency.get(node, ())):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(visited) == len(work_units):
        return None
    return sorted(node_id for node_id, degree in indegree.items() if degree > 0)


def check_graph(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("hyperedges", [])
    events = graph.get("events", [])

    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(nodes, list):
        return {"ok": False, "errors": ["nodes must be an array"], "warnings": []}
    if not isinstance(edges, list):
        return {"ok": False, "errors": ["hyperedges must be an array"], "warnings": []}
    if not isinstance(events, list):
        return {"ok": False, "errors": ["events must be an array"], "warnings": []}

    errors.extend(f"duplicate-or-invalid-id:{x}" for x in duplicate_ids(nodes, "node"))
    errors.extend(f"duplicate-or-invalid-id:{x}" for x in duplicate_ids(edges, "hyperedge"))
    errors.extend(f"duplicate-or-invalid-id:{x}" for x in duplicate_ids(events, "event"))

    node_ids = {n.get("id") for n in nodes if isinstance(n.get("id"), str)}

    for edge in edges:
        edge_id = edge.get("id", "<missing-id>")
        for endpoint_kind in ("sources", "targets"):
            endpoints = edge.get(endpoint_kind, [])
            if not isinstance(endpoints, list):
                errors.append(f"edge:{edge_id}:{endpoint_kind}-must-be-array")
                continue
            for endpoint in endpoints:
                if endpoint not in node_ids:
                    errors.append(f"edge:{edge_id}:missing-node-reference:{endpoint}")

        if edge.get("relation") == "supersedes":
            for target in edge.get("targets", []):
                if target not in node_ids:
                    errors.append(f"edge:{edge_id}:supersedes-missing-target:{target}")

    cycle_nodes = executable_cycle(nodes, edges)
    if cycle_nodes:
        errors.append("executable-workunit-cycle:" + ",".join(cycle_nodes))

    referenced = set()
    for edge in edges:
        referenced.update(x for x in edge.get("sources", []) if isinstance(x, str))
        referenced.update(x for x in edge.get("targets", []) if isinstance(x, str))
    isolated = sorted(node_id for node_id in node_ids if node_id not in referenced)
    if isolated:
        warnings.append("isolated-nodes:" + ",".join(isolated[:50]))

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "nodes": len(nodes),
            "hyperedges": len(edges),
            "events": len(events),
            "work_units": sum(1 for n in nodes if n.get("type") == "work_unit"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deterministic IDKGraph invariants")
    parser.add_argument("graph", help="Path to IDKGraph JSON file")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    try:
        result = check_graph(load_graph(Path(args.graph)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [f"load-error:{exc}"], "warnings": []}

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("IDKGraph invariant check:", "PASS" if result["ok"] else "FAIL")
        for error in result.get("errors", []):
            print("ERROR:", error)
        for warning in result.get("warnings", []):
            print("WARN:", warning)
        if "counts" in result:
            print("Counts:", json.dumps(result["counts"], sort_keys=True))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
