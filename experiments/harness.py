#!/usr/bin/env python3
"""Minimal IDKMesh Phase 0 experiment harness.

The `validate` command checks schemas and fixtures only. The `smoke` command
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
VERIFICATION_RESULT_SCHEMA = SCHEMA_DIR / "verification-result-v0.1.schema.json"

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


def validate_verification_result_contract(
    verification_result_path: Path,
    worker_result: dict[str, Any],
    work_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    verification_result = load_json(verification_result_path)
    validate_instance(
        verification_result,
        VERIFICATION_RESULT_SCHEMA,
        str(verification_result_path),
    )

    if verification_result["result_manifest_id"] != worker_result["id"]:
        raise HarnessError(
            "VerificationResult references a different ResultManifest: "
            f"{verification_result['result_manifest_id']!r} != {worker_result['id']!r}"
        )

    for field in ("work_unit_id", "work_unit_version", "attempt"):
        if verification_result[field] != worker_result[field]:
            raise HarnessError(
                f"VerificationResult {field} mismatch: "
                f"{verification_result[field]!r} != {worker_result[field]!r}"
            )

    work_unit_id = verification_result["work_unit_id"]
    if work_unit_id not in work_units:
        raise HarnessError(
            f"VerificationResult references unknown Work Unit {work_unit_id!r}"
        )
    work_unit = work_units[work_unit_id]

    evidence_ids = {evidence["id"] for evidence in verification_result["evidence"]}
    for check in verification_result["checks"]:
        missing_evidence = sorted(set(check["evidence_ids"]) - evidence_ids)
        if missing_evidence:
            raise HarnessError(
                f"Verification check {check['id']!r} references unknown evidence id(s): "
                + ", ".join(missing_evidence)
            )

    check_by_id = {check["id"]: check for check in verification_result["checks"]}
    required_validator_ids = {
        validator["id"] for validator in work_unit["validators"] if validator["required"]
    }
    missing_required = sorted(required_validator_ids - set(check_by_id))
    if missing_required:
        raise HarnessError(
            "VerificationResult is missing required WorkUnit validator check(s): "
            + ", ".join(missing_required)
        )

    requested_validator_ids = set(
        worker_result["verification_request"]["expected_validator_ids"]
    )
    missing_requested = sorted(requested_validator_ids - set(check_by_id))
    if missing_requested:
        raise HarnessError(
            "VerificationResult is missing validator check(s) requested by worker result: "
            + ", ".join(missing_requested)
        )

    policy = work_unit["verification_policy"]
    independence = verification_result["independence"]
    worker_id = worker_result["worker"]["id"]
    verifier_id = verification_result["verifier"]["id"]
    if independence["worker_id_observed"] != worker_id:
        raise HarnessError(
            "VerificationResult independence.worker_id_observed does not match worker id"
        )
    if policy["independent_from_worker"]:
        if not independence["independent_from_worker"]:
            raise HarnessError("WorkUnit requires an independent verifier")
        if verifier_id == worker_id:
            raise HarnessError("Verifier id must differ from worker id for independent verification")

    required_failures = [
        check["id"]
        for check in verification_result["checks"]
        if check["id"] in required_validator_ids and check["status"] != "passed"
    ]
    if verification_result["status"] == "passed" and required_failures:
        raise HarnessError(
            "VerificationResult cannot be passed while required checks are not passed: "
            + ", ".join(sorted(required_failures))
        )

    recommendation = verification_result["decision_support"]["recommendation"]
    if recommendation == "accept_candidate":
        if verification_result["status"] != "passed":
            raise HarnessError(
                "accept_candidate recommendation requires verification status=passed"
            )
        if required_failures:
            raise HarnessError(
                "accept_candidate recommendation requires all required checks to pass"
            )

    return verification_result


def assert_invalid_verification_contract(
    path: Path,
    worker_result: dict[str, Any],
    work_units: dict[str, dict[str, Any]],
) -> None:
    try:
        validate_verification_result_contract(path, worker_result, work_units)
    except HarnessError:
        return
    raise HarnessError(
        f"{path} was expected to violate the cross-object verification contract but passed"
    )


def cmd_validate(args: argparse.Namespace) -> int:
    for schema_path in (
        WORK_UNIT_SCHEMA,
        MANIFEST_SCHEMA,
        RESULT_SCHEMA,
        WORKER_RESULT_SCHEMA,
        VERIFICATION_RESULT_SCHEMA,
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

    verification_result_path = resolve_repo_path(args.verification_result)
    validate_verification_result_contract(
        verification_result_path,
        worker_result,
        work_units,
    )

    invalid_verification_result_path = resolve_repo_path(
        args.invalid_verification_result
    )
    assert_invalid_verification_contract(
        invalid_verification_result_path,
        worker_result,
        work_units,
    )

    if args.result:
        result_path = resolve_repo_path(args.result)
        result = load_json(result_path)
        validate_instance(result, RESULT_SCHEMA, str(result_path))

    print(
        f"OK: schemas valid; WorkUnit v0.2 contract coverage enforced; manifest {manifest['id']}, "
        f"{len(manifest['work_units'])} Work Unit(s), worker ResultManifest, and independent "
        "VerificationResult validated; negative security/self-acceptance/non-independent fixtures "
        "rejected as expected"
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
        help=(
            "Validate schemas, WorkUnit contract coverage, worker ResultManifest, "
            "and independent VerificationResult contracts."
        ),
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
        "--verification-result",
        default="examples/results/phase0-smoke.verification-result.json",
        help="Repository-relative valid independent VerificationResult fixture.",
    )
    validate_parser.add_argument(
        "--invalid-verification-result",
        default="examples/results/invalid-non-independent.verification-result.json",
        help="Repository-relative schema-valid fixture that must fail the cross-object independence contract.",
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
