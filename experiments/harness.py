#!/usr/bin/env python3
"""Minimal IDKMesh Phase 0 experiment harness.

CI uses only the `validate` subcommand. The `smoke` subcommand executes only
the built-in deterministic_smoke runner and never executes commands from a
manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

HARNESS_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
WORK_UNIT_SCHEMA = SCHEMA_DIR / "work-unit-v0.1.schema.json"
MANIFEST_SCHEMA = SCHEMA_DIR / "experiment-manifest-v0.1.schema.json"
RESULT_SCHEMA = SCHEMA_DIR / "experiment-result-v0.1.schema.json"


class HarnessError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validator_for(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_instance(instance: Any, schema_path: Path, label: str) -> None:
    validator = validator_for(schema_path)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    lines = [f"{label} failed {len(errors)} schema check(s):"]
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        lines.append(f"  - {location}: {error.message}")
    raise HarnessError("\n".join(lines))


def resolve_repo_path(raw: str) -> Path:
    candidate = (ROOT / raw).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise HarnessError(f"path escapes repository root: {raw}") from exc
    return candidate


def validate_manifest_and_work_units(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    validate_instance(manifest, MANIFEST_SCHEMA, str(manifest_path))

    seen_ids: set[str] = set()
    for ref in manifest["work_units"]:
        if ref["id"] in seen_ids:
            raise HarnessError(f"duplicate Work Unit id in manifest: {ref['id']}")
        seen_ids.add(ref["id"])

        work_unit_path = resolve_repo_path(ref["path"])
        work_unit = load_json(work_unit_path)
        validate_instance(work_unit, WORK_UNIT_SCHEMA, str(work_unit_path))
        if work_unit["id"] != ref["id"]:
            raise HarnessError(
                f"Work Unit id mismatch: manifest has {ref['id']!r}, "
                f"document has {work_unit['id']!r}"
            )
    return manifest


def cmd_validate(args: argparse.Namespace) -> int:
    for schema_path in (WORK_UNIT_SCHEMA, MANIFEST_SCHEMA, RESULT_SCHEMA):
        validator_for(schema_path)

    manifest_path = resolve_repo_path(args.manifest)
    manifest = validate_manifest_and_work_units(manifest_path)

    if args.result:
        result_path = resolve_repo_path(args.result)
        result = load_json(result_path)
        validate_instance(result, RESULT_SCHEMA, str(result_path))

    print(
        f"OK: schemas valid; manifest {manifest['id']} and "
        f"{len(manifest['work_units'])} Work Unit(s) validated"
    )
    return 0


def deterministic_score(experiment_id: str, configuration_id: str, seed: int) -> float:
    key = f"{experiment_id}|{configuration_id}|{seed}".encode("utf-8")
    raw = int(hashlib.sha256(key).hexdigest()[:12], 16)
    return raw / float(0xFFFFFFFFFFFF)


def max_runs_from_manifest(manifest: dict[str, Any]) -> int | None:
    limits = [
        int(rule["value"])
        for rule in manifest["stopping_rules"]
        if rule["type"] == "max_runs" and isinstance(rule["value"], (int, float))
    ]
    return min(limits) if limits else None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cmd_smoke(args: argparse.Namespace) -> int:
    manifest_path = resolve_repo_path(args.manifest)
    manifest = validate_manifest_and_work_units(manifest_path)

    unsupported = [
        config["id"]
        for config in manifest["configurations"]
        if config["runner"]["type"] != "deterministic_smoke"
    ]
    if unsupported:
        raise HarnessError(
            "smoke refuses non-built-in runners: " + ", ".join(unsupported)
        )

    planned_runs = (
        len(manifest["configurations"])
        * len(manifest["seeds"])
        * manifest["repetitions"]
    )
    max_runs = max_runs_from_manifest(manifest)
    if max_runs is not None and planned_runs > max_runs:
        raise HarnessError(
            f"planned runs ({planned_runs}) exceed max_runs stopping rule ({max_runs})"
        )

    output_path = resolve_repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_digest = canonical_digest(manifest)

    results: list[dict[str, Any]] = []
    for config in manifest["configurations"]:
        for seed in manifest["seeds"]:
            for repetition in range(1, manifest["repetitions"] + 1):
                started = utc_now()
                timer = time.perf_counter()
                score = deterministic_score(manifest["id"], config["id"], seed)
                elapsed = max(0.0, time.perf_counter() - timer)
                finished = utc_now()

                result = {
                    "schema_version": "0.1",
                    "experiment_id": manifest["id"],
                    "run_id": f"{config['id']}-seed{seed}-r{repetition}",
                    "configuration_id": config["id"],
                    "seed": seed,
                    "status": "passed",
                    "started_at": started,
                    "finished_at": finished,
                    "metrics": {
                        "smoke_score": score,
                        "work_unit_count": len(manifest["work_units"]),
                        "agent_count": config["agent_count"],
                    },
                    "costs": {
                        "wall_seconds": elapsed,
                        "compute_units": 0.0,
                        "human_minutes": 0.0,
                        "tokens": 0,
                    },
                    "verification": {
                        "policy": config["verification_policy"],
                        "passed": True,
                        "checks": [
                            {
                                "id": "deterministic-score",
                                "passed": score
                                == deterministic_score(manifest["id"], config["id"], seed),
                                "detail": "Recomputed built-in score matches.",
                            },
                            {
                                "id": "no-external-runner",
                                "passed": True,
                                "detail": "Only deterministic_smoke runners are executable here.",
                            },
                        ],
                    },
                    "artifacts": [],
                    "provenance": {
                        "harness_version": HARNESS_VERSION,
                        "manifest_digest": manifest_digest,
                    },
                    "notes": "Phase 0 smoke fixture; smoke_score is not scientific evidence.",
                    "extensions": {
                        "org.idkmesh.phase0.repetition": repetition
                    },
                }
                validate_instance(result, RESULT_SCHEMA, result["run_id"])
                results.append(result)

    with output_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, sort_keys=True) + "\n")

    print(f"OK: wrote {len(results)} schema-valid smoke result(s) to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate schemas, a manifest, and referenced Work Units."
    )
    validate_parser.add_argument(
        "--manifest",
        default="examples/experiments/phase0-smoke.manifest.json",
        help="Repository-relative manifest path.",
    )
    validate_parser.add_argument(
        "--result",
        help="Optional repository-relative result JSON file to validate.",
    )
    validate_parser.set_defaults(func=cmd_validate)

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run only the built-in deterministic smoke runner; never manifest commands.",
    )
    smoke_parser.add_argument(
        "--manifest",
        default="examples/experiments/phase0-smoke.manifest.json",
        help="Repository-relative manifest path.",
    )
    smoke_parser.add_argument(
        "--output",
        default="results/phase0-smoke.jsonl",
        help="Repository-relative JSONL output path.",
    )
    smoke_parser.set_defaults(func=cmd_smoke)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (HarnessError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
