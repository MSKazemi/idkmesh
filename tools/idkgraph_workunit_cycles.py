#!/usr/bin/env python3
"""Deterministic cycle checking for the executable IDKGraph WorkUnit projection.

T4 intentionally checks only explicit ``depends_on`` hyperedges whose sources
and targets are all nodes of type ``work_unit``. The global knowledge graph may
contain legitimate cycles; those relations do not enter this executable DAG
projection.

For ``depends_on`` hyperedges, the semantic direction is:

    source WorkUnit -> target prerequisite WorkUnit

Cycle existence is independent of reversing every edge, so this direction is
also suitable for deterministic deadlock diagnostics.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "idkgraph-workunit-cycle-check-v0.1"
SUPPORTED_EXECUTABLE_RELATIONS = ("depends_on",)


def _canonical_cycle(path: list[str]) -> list[str]:
    """Rotate a closed directed cycle to its lexicographically smallest start."""
    if len(path) < 2 or path[0] != path[-1]:
        raise ValueError("cycle witness must be closed")
    nodes = path[:-1]
    rotations = [nodes[index:] + nodes[:index] for index in range(len(nodes))]
    canonical = min(rotations)
    return canonical + [canonical[0]]


def build_executable_projection(graph: dict[str, Any]) -> dict[str, Any]:
    """Project explicit WorkUnit dependencies into a deterministic adjacency map."""
    node_types = {
        node["id"]: node.get("type")
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    work_units = sorted(node_id for node_id, node_type in node_types.items() if node_type == "work_unit")
    work_unit_set = set(work_units)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in work_units}
    included_hyperedges: list[str] = []
    ignored_hyperedges: list[dict[str, str]] = []

    edges = sorted(
        (edge for edge in graph.get("hyperedges", []) if isinstance(edge, dict)),
        key=lambda edge: str(edge.get("id", "")),
    )

    for edge in edges:
        edge_id = str(edge.get("id", ""))
        relation = edge.get("relation")
        if relation not in SUPPORTED_EXECUTABLE_RELATIONS:
            ignored_hyperedges.append({"id": edge_id, "reason": "non_executable_relation"})
            continue

        sources = edge.get("sources", [])
        targets = edge.get("targets", [])
        endpoints = list(sources) + list(targets)
        if not sources or not targets or not all(endpoint in work_unit_set for endpoint in endpoints):
            ignored_hyperedges.append({"id": edge_id, "reason": "non_workunit_or_mixed_dependency"})
            continue

        included_hyperedges.append(edge_id)
        for source in sources:
            for target in targets:
                adjacency[source].add(target)

    normalized_adjacency = {
        node_id: sorted(adjacency[node_id])
        for node_id in sorted(adjacency)
    }
    edge_count = sum(len(neighbors) for neighbors in normalized_adjacency.values())

    return {
        "work_unit_ids": work_units,
        "adjacency": normalized_adjacency,
        "edge_count": edge_count,
        "included_hyperedge_ids": sorted(included_hyperedges),
        "ignored_hyperedges": sorted(
            ignored_hyperedges,
            key=lambda item: (item["id"], item["reason"]),
        ),
    }


def find_cycle(adjacency: dict[str, Iterable[str]]) -> list[str] | None:
    """Return one stable closed cycle witness, or ``None`` for a DAG."""
    normalized = {
        node: sorted(set(neighbors))
        for node, neighbors in adjacency.items()
    }
    for neighbors in list(normalized.values()):
        for neighbor in neighbors:
            normalized.setdefault(neighbor, [])

    state: dict[str, int] = {node: 0 for node in normalized}  # 0 unseen, 1 active, 2 done
    stack: list[str] = []
    stack_index: dict[str, int] = {}

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack_index[node] = len(stack)
        stack.append(node)

        for neighbor in normalized[node]:
            if state[neighbor] == 0:
                witness = visit(neighbor)
                if witness is not None:
                    return witness
            elif state[neighbor] == 1:
                start = stack_index[neighbor]
                return _canonical_cycle(stack[start:] + [neighbor])

        stack.pop()
        stack_index.pop(node, None)
        state[node] = 2
        return None

    for node in sorted(normalized):
        if state[node] == 0:
            witness = visit(node)
            if witness is not None:
                return witness
    return None


def check_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Check the executable WorkUnit projection without mutating ``graph``."""
    projection = build_executable_projection(graph)
    witness = find_cycle(projection["adjacency"])
    return {
        "schema_version": SCHEMA_VERSION,
        "graph_id": graph.get("graph_id"),
        "supported_executable_relations": list(SUPPORTED_EXECUTABLE_RELATIONS),
        "projection": projection,
        "cycle_detected": witness is not None,
        "cycle_witness": witness,
    }


def serialize_result(result: dict[str, Any], pretty: bool = False) -> str:
    if pretty:
        return json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def load_graph(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("IDKGraph fixture must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check executable IDKGraph WorkUnit dependencies for cycles.")
    parser.add_argument("graph", help="Path to an IDKGraph JSON fixture/artifact.")
    parser.add_argument("--output", help="Write the result JSON to this path instead of stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--fail-on-cycle", action="store_true", help="Exit non-zero when an executable cycle is found.")
    args = parser.parse_args(argv)

    graph_path = Path(args.graph)
    if not graph_path.is_file():
        parser.error(f"graph file does not exist: {graph_path}")

    try:
        result = check_graph(load_graph(graph_path))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    payload = serialize_result(result, pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 1 if args.fail_on_cycle and result["cycle_detected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
