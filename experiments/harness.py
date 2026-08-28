#!/usr/bin/env python3
"""Minimal IDKMesh Phase 0 experiment and contract harness.

The `validate` command checks schemas, Work Unit coverage, worker ResultManifest
contracts, and independent Evidence Report contracts. The `smoke` command
executes only the built-in deterministic_smoke runner and never executes
commands supplied by a manifest.
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

HARNESS_VERSION = "0.3"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
WORK_UNIT_SCHEMA = SCHEMA_DIR / "work-unit-v0.2.schema.json"
MANIFEST_SCHEMA = SCHEMA_DIR / "experiment-manifest-v0.1.schema.json"
RESULT_SCHEMA = SCHEMA_DIR / "experiment-result-v0.1.schema.json"
WORKER_RESULT_SCHEMA = SCHEMA_DIR / "result-manifest-v0.1.schema.json"
EVIDENCE_REPORT_SCHEMA = SCHEMA_DIR / "evidence-report-v0.1.schema.json"

REQUIRED_WORK_UNIT_KINDS = {
    "coding",
    "testing",
    "review",
    "benchmarking",
    "documentation",
}
REQUIRED_WORK_UNIT_CONTRACT_FIELDS = {
    "dependencies",
    "requirements",
    "security",
    "permissions",
    "verification_policy",
    "validators",
    "evidence_requirements",
    "provenance",
}


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


def validation_errors(instance: Any, schema_path: Path) -> list[Any]:
    validator = validator_for(schema_path)
    return sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))


def validate_instance(instance: Any, schema_path: Path, label: str) -> None:
    errors = validation_errors(instance, schema_path)
    if not errors:
        return
    lines = [f"{label} failed {len(errors)} schema check(s):"]
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        lines.append(f"  - {location}: {error.message}")
    raise HarnessError("\n".join(lines))


def assert_invalid_instance(instance: Any, schema_path: Path, label: str) -> None:
    if not validation_errors(instance, schema_path):
        raise HarnessError(f"{label} was expected to be invalid but passed schema validation")


def assert_work_unit_contract_coverage() -> None:
    schema = load_json(WORK_UNIT_SCHEMA)
    kinds = set(schema["properties"]["kind"]["enum"])
    missing_kinds = sorted(REQUIRED_WORK_UNIT_KINDS - kinds)
    if missing_kinds:
        raise HarnessError(
            "Work Unit schema is missing required work kind(s): " + ", ".join(missing_kinds)
        )

    required_fields = set(schema["required"])
    missing_fields = sorted(REQUIRED_WORK_UNIT_CONTRACT_FIELDS - required_fields)
    if missing_fields:
        raise HarnessError(
            "Work Unit schema is missing required contract field(s): "
            + ", ".join(missing_fields)
        )


def resolve_repo_path(raw: str) -> Path:
    candidate = (ROOT / raw).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise HarnessError(f"path escapes repository root: {raw}") from exc
    return candidate


def validate_manifest_and_work_units(
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(manifest_path)
    validate_instance(manifest, MANIFEST_SCHEMA, str(manifest_path))

    work_units: dict[str, dict[str, Any]] = {}
    for ref in manifest["work_units"]:
        if ref["id"] in work_units:
            raise HarnessError(f"duplicate Work Unit id in manifest: {ref['id']}")

        work_unit_path = resolve_repo_path(ref["path"])
        work_unit = load_json(work_unit_path)
        validate_instance(work_unit, WORK_UNIT_SCHEMA, str(work_unit_path))
        if work_unit["id"] != ref["id"]:
            raise HarnessError(
                f"Work Unit id mismatch: manifest has {ref['id']!r}, "
                f"document has {work_unit['id']!r}"
            )
        work_units[ref["id"]] = work_unit
    return manifest, work_units


def validate_worker_result_contract(
    worker_result_path: Path,
    work_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    worker_result = load_json(worker_result_path)
    validate_instance(worker_result, WORKER_RESULT_SCHEMA, str(worker_result_path))

    work_unit_id = worker_result["work_unit_id"]
    if work_unit_id not in work_units:
        raise HarnessError(
            f"worker ResultManifest references Work Unit {work_unit_id!r}, "
            "which is not present in the experiment manifest"
        )
    expected_version = work_units[work_unit_id]["version"]
    if worker_result["work_unit_version"] != expected_version:
        raise HarnessError(
            f"worker ResultManifest version mismatch for {work_unit_id!r}: "
            f"result has {worker_result['work_unit_version']}, "
            f"Work Unit has {expected_version}"
        )

    artifact_ids = {artifact["id"] for artifact in worker_result["produced_artifacts"]}
    requested_ids = set(worker_result["verification_request"]["evidence_artifact_ids"])
    missing = sorted(requested_ids - artifact_ids)
    if missing:
        raise HarnessError(
            "worker ResultManifest requests verification of unknown artifact id(s): "
            + ", ".join(missing)
        )
    return worker_result


def validate_evidence_report_contract(
    evidence_report_path: Path,
    worker_result: dict[str, Any],
) -> dict[str, Any]:
    report = load_json(evidence_report_path)
    validate_instance(report, EVIDENCE_REPORT_SCHEMA, str(evidence_report_path))

    if report["work_unit_id"] != worker_result["work_unit_id"]:
        raise HarnessError("Evidence Report work_unit_id does not match the worker ResultManifest")
    if report["work_unit_version"] != worker_result["work_unit_version"]:
        raise HarnessError("Evidence Report work_unit_version does not match the worker ResultManifest")

    result_ref = report["result_manifest"]
    if result_ref["id"] != worker_result["id"]:
        raise HarnessError("Evidence Report references a different ResultManifest id")
    if result_ref["worker_id"] != worker_result["worker"]["id"]:
        raise HarnessError("Evidence Report result_manifest.worker_id does not match the worker")
    expected_result_digest = canonical_digest(worker_result)
    if result_ref["digest"] != expected_result_digest:
        raise HarnessError(
            "Evidence Report ResultManifest digest mismatch: "
            f"expected {expected_result_digest}, got {result_ref['digest']}"
        )

    expected_validators = set(worker_result["verification_request"]["expected_validator_ids"])
    if report["validator_id"] not in expected_validators:
        raise HarnessError(
            f"Evidence Report validator_id {report['validator_id']!r} was not requested "
            "by the worker ResultManifest"
        )

    worker_artifacts = {
        artifact["id"]: artifact["digest"]
        for artifact in worker_result["produced_artifacts"]
    }
    for artifact in report["evaluated_artifacts"]:
        artifact_id = artifact["id"]
        if artifact_id not in worker_artifacts:
            raise HarnessError(
                f"Evidence Report evaluates unknown worker artifact {artifact_id!r}"
            )
        if artifact["digest"] != worker_artifacts[artifact_id]:
            raise HarnessError(
                f"Evidence Report digest mismatch for worker artifact {artifact_id!r}"
            )

    evidence_artifact_ids = {artifact["id"] for artifact in report["evidence_artifacts"]}
    for check in report["checks"]:
        unknown = sorted(set(check.get("evidence_artifact_ids", [])) - evidence_artifact_ids)
        if unknown:
            raise HarnessError(
                f"Evidence check {check['id']!r} references unknown evidence artifact(s): "
                + ", ".join(unknown)
            )

    if report["independence"]["relationship"] == "independent":
        if report["verifier"]["id"] == worker_result["worker"]["id"]:
            raise HarnessError(
                "Evidence Report claims independence but verifier.id equals worker.id"
            )

    if report["provenance"]["work_unit_digest"] != worker_result["provenance"]["work_unit_digest"]:
        raise HarnessError("Evidence Report work_unit_digest does not match worker provenance")

    if report["verdict"] == "supports_candidate":
        failed_required = [
            check["id"]
            for check in report["checks"]
            if check["required"] and check["status"] != "pass"
        ]
        if failed_required:
            raise HarnessError(
                "Evidence Report supports_candidate despite required check(s) not passing: "
                + ", ".join(failed_required)
            )

    return report


def assert_invalid_evidence_contract(
    evidence_report_path: Path,
    worker_result: dict[str, Any],
) -> None:
    try:
        validate_evidence_report_contract(evidence_report_path, worker_result)
    except HarnessError:
        return
    raise HarnessError(
        f"{evidence_report_path} was expected to violate Evidence Report semantic rules"
    )


def cmd_validate(args: argparse.Namespace) -> int:
    for schema_path in (
        WORK_UNIT_SCHEMA,
        MANIFEST_SCHEMA,
        RESULT_SCHEMA,
        WORKER_RESULT_SCHEMA,
        EVIDENCE_REPORT_SCHEMA,
    ):
        validator_for(schema_path)

    assert_work_unit_contract_coverage()

    manifest_path = resolve_repo_path(args.manifest)
    manifest, work_units = validate_manifest_and_work_units(manifest_path)

    invalid_work_unit_path = resolve_repo_path(args.invalid_work_unit)
    invalid_work_unit = load_json(invalid_work_unit_path)
    assert_invalid_instance(
        invalid_work_unit,
        WORK_UNIT_SCHEMA,
        str(invalid_work_unit_path),
    )

    worker_result_path = resolve_repo_path(args.worker_result)
    worker_result = validate_worker_result_contract(worker_result_path, work_units)

    invalid_worker_result_path = resolve_repo_path(args.invalid_worker_result)
    invalid_worker_result = load_json(invalid_worker_result_path)
    assert_invalid_instance(
        invalid_worker_result,
        WORKER_RESULT_SCHEMA,
        str(invalid_worker_result_path),
    )

    evidence_report_path = resolve_repo_path(args.evidence_report)
    validate_evidence_report_contract(evidence_report_path, worker_result)

    invalid_evidence_report_path = resolve_repo_path(args.invalid_evidence_report)
    assert_invalid_evidence_contract(invalid_evidence_report_path, worker_result)

    if args.result:
        result_path = resolve_repo_path(args.result)
        result = load_json(result_path)
        validate_instance(result, RESULT_SCHEMA, str(result_path))

    print(
        f"OK: schemas valid; WorkUnit v0.2 contract coverage enforced; manifest {manifest['id']}, "
        f"{len(manifest['work_units'])} Work Unit(s), worker ResultManifest, and independent "
        "Evidence Report validated; negative WorkUnit/security, worker self-acceptance, and "
        "verifier self-independence fixtures rejected as expected"
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
    manifest, _ = validate_manifest_and_work_units(manifest_path)

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
        "validate",
        help="Validate schemas, WorkUnit coverage, worker ResultManifest, and independent Evidence Report contracts.",
    )
    validate_parser.add_argument(
        "--manifest",
        default="examples/experiments/phase0-smoke.manifest.json",
        help="Repository-relative manifest path.",
    )
    validate_parser.add_argument(
        "--invalid-work-unit",
        default="examples/work-units/invalid-missing-security.work-unit.json",
        help="Repository-relative WorkUnit fixture that must be rejected.",
    )
    validate_parser.add_argument(
        "--worker-result",
        default="examples/results/phase0-smoke.result-manifest.json",
        help="Repository-relative valid worker ResultManifest fixture.",
    )
    validate_parser.add_argument(
        "--invalid-worker-result",
        default="examples/results/invalid-self-acceptance.result-manifest.json",
        help="Repository-relative fixture that must be rejected by the worker ResultManifest schema.",
    )
    validate_parser.add_argument(
        "--evidence-report",
        default="examples/results/phase0-smoke.evidence-report.json",
        help="Repository-relative valid independent Evidence Report fixture.",
    )
    validate_parser.add_argument(
        "--invalid-evidence-report",
        default="examples/results/invalid-self-verification.evidence-report.json",
        help="Repository-relative schema-valid Evidence Report that must fail semantic independence checks.",
    )
    validate_parser.add_argument(
        "--result",
        help="Optional repository-relative experiment result JSON file to validate.",
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
