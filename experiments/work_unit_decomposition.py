#!/usr/bin/env python3
"""Validate and aggregate the issue #15 Work Unit decomposition benchmark.

The committed fixture is an infrastructure example, not scientific evidence. The
same interface can aggregate observations from real, independently executed arms
without changing metric definitions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # Generic repository suites omit Phase 0 dependencies.
    Draft202012Validator = None  # type: ignore[assignment,misc]


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCHEMA = REPO_ROOT / "schemas/decomposition-benchmark-v0.1.schema.json"
WORK_UNIT_SCHEMA = REPO_ROOT / "schemas/work-unit-v0.2.schema.json"
REQUIRED_STRATEGIES = (
    "monolithic",
    "human_subtasks",
    "file_module",
    "dependency_dag",
    "formal_work_units",
)
REPORT_SCHEMA_VERSION = "work-unit-decomposition-report-v0.1"
JSONSCHEMA_AVAILABLE = Draft202012Validator is not None


class BenchmarkError(ValueError):
    """Raised when a benchmark fixture is invalid or non-composable."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"{path}: expected a JSON object")
    return value


def _schema_errors(value: Any, schema_path: Path) -> list[str]:
    if Draft202012Validator is None:
        raise BenchmarkError(
            "jsonschema is required; install requirements-phase0.txt"
        )
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]


def _find_cycle(adjacency: dict[str, Iterable[str]]) -> list[str] | None:
    normalized = {node: sorted(set(neighbors)) for node, neighbors in adjacency.items()}
    state = {node: 0 for node in normalized}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        positions[node] = len(stack)
        stack.append(node)
        for prerequisite in normalized[node]:
            if state[prerequisite] == 0:
                witness = visit(prerequisite)
                if witness is not None:
                    return witness
            elif state[prerequisite] == 1:
                return stack[positions[prerequisite] :] + [prerequisite]
        stack.pop()
        positions.pop(node)
        state[node] = 2
        return None

    for node in sorted(normalized):
        if state[node] == 0:
            witness = visit(node)
            if witness is not None:
                return witness
    return None


def _resolve_repository_path(raw_path: str) -> Path:
    resolved = (REPO_ROOT / raw_path).resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise BenchmarkError(f"repository path escapes root: {raw_path}") from exc
    if not resolved.is_file():
        raise BenchmarkError(f"repository file does not exist: {raw_path}")
    return resolved


def _validate_arm(arm: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    unit_ids = [unit["id"] for unit in arm["units"]]
    if len(unit_ids) != len(set(unit_ids)):
        raise BenchmarkError(f"{arm['strategy']}: duplicate unit id")
    unit_set = set(unit_ids)
    adjacency: dict[str, list[str]] = {}
    task_edges: list[dict[str, str]] = []
    evidence_edges: list[dict[str, str]] = []

    for unit in arm["units"]:
        unknown = sorted(set(unit["dependencies"]) - unit_set)
        if unknown:
            raise BenchmarkError(
                f"{arm['strategy']}/{unit['id']}: unknown dependencies: {', '.join(unknown)}"
            )
        adjacency[unit["id"]] = unit["dependencies"]
        task_edges.extend(
            {"source": unit["id"], "target": dependency, "relation": "requires"}
            for dependency in sorted(unit["dependencies"])
        )

        work_unit_path = unit.get("formal_work_unit_path")
        if arm["strategy"] == "formal_work_units" and not work_unit_path:
            raise BenchmarkError(f"formal_work_units/{unit['id']}: missing formal_work_unit_path")
        if not work_unit_path:
            continue
        work_unit = _load_json(_resolve_repository_path(work_unit_path))
        errors = _schema_errors(work_unit, WORK_UNIT_SCHEMA)
        if errors:
            raise BenchmarkError(f"{work_unit_path}: " + "; ".join(errors))
        if work_unit["id"] != unit["id"]:
            raise BenchmarkError(
                f"{work_unit_path}: id {work_unit['id']!r} does not match {unit['id']!r}"
            )
        declared = sorted(
            dependency["work_unit_id"]
            for dependency in work_unit["dependencies"]
            if dependency["relationship"] == "requires"
        )
        if declared != sorted(unit["dependencies"]):
            raise BenchmarkError(
                f"{work_unit_path}: requires dependencies do not match benchmark arm"
            )
        if sorted(work_unit["constraints"]["allowed_paths"]) != sorted(
            unit["allowed_paths"]
        ):
            raise BenchmarkError(
                f"{work_unit_path}: allowed paths do not match benchmark arm"
            )
        if (
            not unit["global_context_required"]
            and "max_context_bytes" not in work_unit.get("context", {})
        ):
            raise BenchmarkError(
                f"{work_unit_path}: bounded-context unit has no max_context_bytes"
            )
        for index, requirement in enumerate(work_unit["evidence_requirements"]):
            evidence_edges.append(
                {
                    "source": unit["id"],
                    "target": f"evidence:{unit['id']}:{index}:{requirement['type']}",
                    "relation": "requires_evidence",
                }
            )

    witness = _find_cycle(adjacency)
    if witness is not None:
        raise BenchmarkError(f"{arm['strategy']}: dependency cycle: {' -> '.join(witness)}")

    observed_ids = {observation["unit_id"] for observation in arm["observations"]}
    if observed_ids != unit_set:
        missing = sorted(unit_set - observed_ids)
        unknown = sorted(observed_ids - unit_set)
        raise BenchmarkError(
            f"{arm['strategy']}: observations must cover every unit exactly; "
            f"missing={missing}, unknown={unknown}"
        )
    if len(arm["observations"]) != len(unit_set):
        raise BenchmarkError(f"{arm['strategy']}: duplicate unit observation")
    for observation in arm["observations"]:
        if observation["hidden_tests_passed"] > observation["hidden_tests_total"]:
            raise BenchmarkError(
                f"{arm['strategy']}/{observation['unit_id']}: hidden tests passed "
                "cannot exceed hidden tests total"
            )
    return task_edges, evidence_edges


def validate_benchmark(benchmark: dict[str, Any]) -> dict[str, Any]:
    """Validate schema, five-arm coverage, DAGs, and formal WorkUnit bindings."""
    errors = _schema_errors(benchmark, BENCHMARK_SCHEMA)
    if errors:
        raise BenchmarkError("benchmark schema validation failed: " + "; ".join(errors))

    worker_ids = [worker["id"] for worker in benchmark["workers"]]
    if len(worker_ids) != len(set(worker_ids)):
        raise BenchmarkError("benchmark contains duplicate worker id")
    known_workers = set(worker_ids)
    observations = [
        observation
        for arm in benchmark["arms"]
        for observation in arm["observations"]
    ]
    attempt_ids = [observation["attempt_id"] for observation in observations]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise BenchmarkError("benchmark contains duplicate attempt id")
    unknown_workers = sorted(
        {observation["worker_id"] for observation in observations} - known_workers
    )
    if unknown_workers:
        raise BenchmarkError(
            "observations reference unknown workers: " + ", ".join(unknown_workers)
        )

    strategies = [arm["strategy"] for arm in benchmark["arms"]]
    if sorted(strategies) != sorted(REQUIRED_STRATEGIES) or len(strategies) != len(
        REQUIRED_STRATEGIES
    ):
        raise BenchmarkError(
            "benchmark must contain each required strategy exactly once: "
            + ", ".join(REQUIRED_STRATEGIES)
        )

    all_task_edges: list[dict[str, str]] = []
    all_evidence_edges: list[dict[str, str]] = []
    for arm in sorted(benchmark["arms"], key=lambda item: item["strategy"]):
        task_edges, evidence_edges = _validate_arm(arm)
        if arm["strategy"] == "formal_work_units":
            all_task_edges.extend(task_edges)
            all_evidence_edges.extend(evidence_edges)
    return {
        "nodes": sorted(
            {edge["source"] for edge in all_task_edges + all_evidence_edges}
            | {edge["target"] for edge in all_task_edges + all_evidence_edges}
        ),
        "edges": sorted(
            all_task_edges + all_evidence_edges,
            key=lambda edge: (edge["source"], edge["target"], edge["relation"]),
        ),
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _aggregate_arm(arm: dict[str, Any]) -> dict[str, Any]:
    observations = arm["observations"]
    hidden_total = sum(item["hidden_tests_total"] for item in observations)
    units_by_id = {unit["id"]: unit for unit in arm["units"]}
    return {
        "unit_count": len(observations),
        "completion_success_rate": _ratio(
            sum(bool(item["completed"]) for item in observations), len(observations)
        ),
        "integration_failure_rate": _ratio(
            sum(bool(item["integration_failed"]) for item in observations), len(observations)
        ),
        "merge_conflicts": sum(item["merge_conflicts"] for item in observations),
        "rework_cycles": sum(item["rework_cycles"] for item in observations),
        "context_bytes": sum(item["context_bytes"] for item in observations),
        "cross_worker_messages": sum(item["cross_worker_messages"] for item in observations),
        "hidden_test_success_rate": _ratio(
            sum(item["hidden_tests_passed"] for item in observations), hidden_total
        ),
        "assumption_mismatches": sum(item["assumption_mismatches"] for item in observations),
        "dependency_violations": sum(item["dependency_violations"] for item in observations),
        "verification_seconds": round(
            sum(item["verification_seconds"] for item in observations), 6
        ),
        "human_integration_minutes": round(
            sum(item["human_integration_minutes"] for item in observations), 6
        ),
        "executable_without_global_context_rate": _ratio(
            sum(
                not units_by_id[item["unit_id"]]["global_context_required"]
                for item in observations
            ),
            len(observations),
        ),
    }


def run_benchmark(benchmark: dict[str, Any]) -> dict[str, Any]:
    graph = validate_benchmark(benchmark)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "benchmark_id": benchmark["benchmark_id"],
        "evidence_class": benchmark["evidence_class"],
        "metric_definitions_version": "0.1",
        "arms": {
            arm["strategy"]: _aggregate_arm(arm)
            for arm in sorted(benchmark["arms"], key=lambda item: item["strategy"])
        },
        "formal_task_evidence_dag": graph,
    }


def serialize_report(report: dict[str, Any], pretty: bool = False) -> str:
    separators = None if pretty else (",", ":")
    return json.dumps(
        report,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=separators,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(_load_json(args.benchmark))
    except (OSError, UnicodeError, json.JSONDecodeError, BenchmarkError) as exc:
        parser.error(str(exc))
    payload = serialize_report(report, args.pretty)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
