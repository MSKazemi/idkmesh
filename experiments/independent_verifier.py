#!/usr/bin/env python3
"""Executable Phase 0 independent verifier for IDKMesh.

This MVP verifies the built-in deterministic Phase 0 smoke candidate. It does
not execute candidate-supplied commands, provider calls, network requests, or
paid compute. The verifier owns the evaluation logic and emits the canonical
VerificationResult v0.1 contract from observed evidence.

The intentionally narrow first path is:

    Work Unit + worker ResultManifest + candidate NDJSON
        -> artifact digest check
        -> independent schema validation
        -> independent deterministic reproduction
        -> VerificationResult v0.1

Future verifier adapters can add bounded test/security/review check types without
changing the canonical VerificationResult contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # package import for tests
    from .harness import (
        RESULT_SCHEMA,
        VERIFICATION_RESULT_SCHEMA,
        HarnessError,
        canonical_digest,
        deterministic_score,
        load_json,
        validate_instance,
        validate_manifest_and_work_units,
        validate_worker_result_contract,
    )
except ImportError:  # direct script execution: python experiments/independent_verifier.py
    from harness import (  # type: ignore
        RESULT_SCHEMA,
        VERIFICATION_RESULT_SCHEMA,
        HarnessError,
        canonical_digest,
        deterministic_score,
        load_json,
        validate_instance,
        validate_manifest_and_work_units,
        validate_worker_result_contract,
    )

VERIFIER_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_REQUIRED_VALIDATORS = {"schema", "reproduction"}


class VerifierError(RuntimeError):
    """Raised when the verifier cannot safely evaluate the requested candidate."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise VerifierError(f"path escapes repository root: {raw}") from exc
    return path


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def evidence_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise VerifierError(
                        f"candidate line {line_number} is not a JSON object"
                    )
                rows.append(value)
    except json.JSONDecodeError as exc:
        raise VerifierError(
            f"candidate artifact is not valid NDJSON at line {exc.lineno}: {exc.msg}"
        ) from exc

    if not rows:
        raise VerifierError("candidate artifact contains no result rows")
    return rows


def expected_smoke_runs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    for configuration in manifest["configurations"]:
        runner_type = configuration["runner"]["type"]
        if runner_type != "deterministic_smoke":
            raise VerifierError(
                "Phase 0 verifier refuses non-built-in runner type: "
                f"{runner_type!r}"
            )
        for seed in manifest["seeds"]:
            for repetition in range(1, manifest["repetitions"] + 1):
                run_id = f"{configuration['id']}-seed{seed}-r{repetition}"
                if run_id in expected:
                    raise VerifierError(f"duplicate expected run id: {run_id}")
                expected[run_id] = {
                    "configuration_id": configuration["id"],
                    "seed": seed,
                    "repetition": repetition,
                    "agent_count": configuration["agent_count"],
                    "smoke_score": deterministic_score(
                        manifest["id"], configuration["id"], seed
                    ),
                }
    return expected


def find_candidate_artifact(
    worker_result: dict[str, Any], artifact_id: str
) -> dict[str, Any]:
    matches = [
        artifact
        for artifact in worker_result["produced_artifacts"]
        if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise VerifierError(
            f"expected exactly one produced artifact with id {artifact_id!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def evaluate_schema(rows: list[dict[str, Any]]) -> tuple[bool, str, dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        try:
            validate_instance(row, RESULT_SCHEMA, f"candidate row {index + 1}")
        except HarnessError as exc:
            failures.append({"row": index + 1, "error": str(exc)})

    passed = not failures
    summary = (
        f"All {len(rows)} candidate result row(s) satisfy ExperimentResult v0.1."
        if passed
        else f"{len(failures)} of {len(rows)} candidate result row(s) failed schema validation."
    )
    return passed, summary, {"rows": len(rows), "failures": failures}


def evaluate_reproduction(
    manifest: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[bool, str, dict[str, Any]]:
    expected = expected_smoke_runs(manifest)
    manifest_digest = canonical_digest(manifest)

    observed: dict[str, dict[str, Any]] = {}
    duplicate_ids: list[str] = []
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if run_id in observed:
            duplicate_ids.append(run_id)
        observed[run_id] = row

    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    mismatches: list[dict[str, Any]] = []

    for run_id in sorted(set(expected) & set(observed)):
        exp = expected[run_id]
        row = observed[run_id]
        metrics = row.get("metrics", {})
        provenance = row.get("provenance", {})

        comparisons: list[tuple[str, Any, Any]] = [
            ("experiment_id", manifest["id"], row.get("experiment_id")),
            ("configuration_id", exp["configuration_id"], row.get("configuration_id")),
            ("seed", exp["seed"], row.get("seed")),
            ("agent_count", exp["agent_count"], metrics.get("agent_count")),
            ("work_unit_count", len(manifest["work_units"]), metrics.get("work_unit_count")),
            ("manifest_digest", manifest_digest, provenance.get("manifest_digest")),
        ]
        for field, expected_value, observed_value in comparisons:
            if observed_value != expected_value:
                mismatches.append(
                    {
                        "run_id": run_id,
                        "field": field,
                        "expected": expected_value,
                        "observed": observed_value,
                    }
                )

        observed_score = metrics.get("smoke_score")
        if not isinstance(observed_score, (int, float)) or not math.isclose(
            float(observed_score),
            float(exp["smoke_score"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            mismatches.append(
                {
                    "run_id": run_id,
                    "field": "smoke_score",
                    "expected": exp["smoke_score"],
                    "observed": observed_score,
                }
            )

    passed = not (missing or unexpected or duplicate_ids or mismatches)
    if passed:
        summary = (
            f"Recomputed all {len(expected)} deterministic smoke run(s); "
            "configuration, seed, manifest digest, and smoke_score match."
        )
    else:
        summary = (
            "Independent reproduction mismatch: "
            f"missing={len(missing)}, unexpected={len(unexpected)}, "
            f"duplicates={len(duplicate_ids)}, field_mismatches={len(mismatches)}."
        )

    details = {
        "expected_run_count": len(expected),
        "observed_run_count": len(rows),
        "missing_run_ids": missing,
        "unexpected_run_ids": unexpected,
        "duplicate_run_ids": sorted(set(duplicate_ids)),
        "mismatches": mismatches,
    }
    return passed, summary, details


def make_check(
    *,
    check_id: str,
    check_type: str,
    required: bool,
    passed: bool,
    summary: str,
    evidence_id: str,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    check: dict[str, Any] = {
        "id": check_id,
        "type": check_type,
        "required": required,
        "status": "passed" if passed else "failed",
        "summary": summary,
        "evidence_ids": [evidence_id],
    }
    if diagnostics:
        check["diagnostics"] = json.dumps(
            diagnostics, sort_keys=True, separators=(",", ":")
        )
    return check


def verify_candidate(
    *,
    manifest_path: Path,
    worker_result_path: Path,
    candidate_path: Path,
    artifact_id: str = "candidate-result",
    verifier_id: str = "phase0-independent-verifier",
) -> dict[str, Any]:
    started_at = utc_now()
    timer = time.perf_counter()

    manifest, work_units = validate_manifest_and_work_units(manifest_path)
    worker_result = validate_worker_result_contract(worker_result_path, work_units)
    work_unit = work_units[worker_result["work_unit_id"]]

    if verifier_id == worker_result["worker"]["id"]:
        raise VerifierError("verifier id must differ from worker id")

    required_validator_ids = {
        validator["id"] for validator in work_unit["validators"] if validator["required"]
    }
    unsupported = sorted(required_validator_ids - SUPPORTED_REQUIRED_VALIDATORS)
    if unsupported:
        raise VerifierError(
            "Phase 0 verifier fails closed on unsupported required validator(s): "
            + ", ".join(unsupported)
        )

    artifact = find_candidate_artifact(worker_result, artifact_id)
    declared_digest = artifact["digest"]
    actual_digest = sha256_file(candidate_path)
    integrity_passed = actual_digest == declared_digest
    integrity_summary = (
        "Candidate artifact SHA-256 matches the worker ResultManifest declaration."
        if integrity_passed
        else "Candidate artifact SHA-256 does not match the worker ResultManifest declaration."
    )
    integrity_details = {
        "artifact_id": artifact_id,
        "declared_digest": declared_digest,
        "actual_digest": actual_digest,
        "declared_locator": artifact["locator"],
        "verified_path": str(candidate_path),
    }

    rows: list[dict[str, Any]] = []
    parse_error: str | None = None
    try:
        rows = load_jsonl(candidate_path)
    except (VerifierError, OSError) as exc:
        parse_error = str(exc)

    if parse_error is None:
        schema_passed, schema_summary, schema_details = evaluate_schema(rows)
        reproduction_passed, reproduction_summary, reproduction_details = evaluate_reproduction(
            manifest, rows
        )
    else:
        schema_passed = False
        schema_summary = "Candidate artifact could not be parsed as NDJSON."
        schema_details = {"parse_error": parse_error}
        reproduction_passed = False
        reproduction_summary = "Reproduction could not run because candidate parsing failed."
        reproduction_details = {"blocked_by": "candidate-parse"}

    evidence_payloads = {
        "artifact-integrity-evidence": integrity_details,
        "schema-evidence": schema_details,
        "reproduction-evidence": reproduction_details,
    }
    evidence = [
        {
            "id": "artifact-integrity-evidence",
            "type": "artifact_hash",
            "locator": str(candidate_path),
            "digest": actual_digest,
            "media_type": artifact.get("media_type", "application/octet-stream"),
            "description": "Verifier-computed digest of the exact candidate artifact.",
        },
        {
            "id": "schema-evidence",
            "type": "test_output",
            "locator": "inline:phase0-independent-verifier/schema",
            "digest": evidence_digest(evidence_payloads["schema-evidence"]),
            "media_type": "application/json",
            "description": "Independent ExperimentResult schema-validation summary.",
        },
        {
            "id": "reproduction-evidence",
            "type": "test_output",
            "locator": "inline:phase0-independent-verifier/reproduction",
            "digest": evidence_digest(evidence_payloads["reproduction-evidence"]),
            "media_type": "application/json",
            "description": "Independent deterministic-smoke reproduction summary.",
        },
    ]

    checks = [
        make_check(
            check_id="artifact-integrity",
            check_type="policy",
            required=True,
            passed=integrity_passed,
            summary=integrity_summary,
            evidence_id="artifact-integrity-evidence",
            diagnostics=integrity_details if not integrity_passed else None,
        ),
        make_check(
            check_id="schema",
            check_type="schema",
            required=True,
            passed=schema_passed,
            summary=schema_summary,
            evidence_id="schema-evidence",
            diagnostics=schema_details if not schema_passed else None,
        ),
        make_check(
            check_id="reproduction",
            check_type="reproduction",
            required=True,
            passed=reproduction_passed,
            summary=reproduction_summary,
            evidence_id="reproduction-evidence",
            diagnostics=reproduction_details if not reproduction_passed else None,
        ),
    ]

    all_required_passed = all(
        check["status"] == "passed" for check in checks if check["required"]
    )
    status = "passed" if all_required_passed else "failed"
    recommendation = "accept_candidate" if all_required_passed else "reject_candidate"

    findings: list[dict[str, Any]] = []
    if not integrity_passed:
        findings.append(
            {
                "severity": "high",
                "category": "provenance",
                "summary": "Candidate artifact digest differs from the worker declaration.",
            }
        )
    if not schema_passed:
        findings.append(
            {
                "severity": "medium",
                "category": "correctness",
                "summary": "Candidate result artifact does not satisfy the required result schema.",
            }
        )
    if not reproduction_passed:
        findings.append(
            {
                "severity": "medium",
                "category": "correctness",
                "summary": "Independent deterministic reproduction did not match the candidate result.",
            }
        )

    elapsed = max(0.0, time.perf_counter() - timer)
    finished_at = utc_now()
    verifier_config = {
        "version": VERIFIER_VERSION,
        "verifier_id": verifier_id,
        "supported_required_validators": sorted(SUPPORTED_REQUIRED_VALIDATORS),
        "artifact_id": artifact_id,
        "runner": "deterministic_smoke_only",
    }

    verification_result: dict[str, Any] = {
        "schema_version": "0.1",
        "id": f"{worker_result['id']}/verification/{verifier_id}",
        "result_manifest_id": worker_result["id"],
        "work_unit_id": worker_result["work_unit_id"],
        "work_unit_version": worker_result["work_unit_version"],
        "attempt": worker_result["attempt"],
        "verifier": {
            "id": verifier_id,
            "type": "system",
            "adapter": "phase0-independent-verifier",
            "adapter_version": VERIFIER_VERSION,
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": worker_result["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": True,
            "correlation_notes": (
                "Verifier code/config is separate from worker self-report. The Phase 0 MVP "
                "may share the same host/runtime, so runtime independence is not claimed."
            ),
        },
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "candidate_rows": len(rows),
            "required_checks": sum(1 for check in checks if check["required"]),
            "required_checks_passed": sum(
                1
                for check in checks
                if check["required"] and check["status"] == "passed"
            ),
            "required_checks_failed": sum(
                1
                for check in checks
                if check["required"] and check["status"] != "passed"
            ),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(worker_result),
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": worker_result["provenance"]["source_revision"],
            "verifier_config_digest": canonical_digest(verifier_config),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {
                    "phase0-independent-verifier": VERIFIER_VERSION,
                },
            },
        },
        "decision_support": {
            "recommendation": recommendation,
            "confidence": 1.0,
            "rationale": (
                "All verifier-owned required checks passed. This is decision support, not merge authority."
                if all_required_passed
                else "At least one verifier-owned required check failed; candidate should not be accepted."
            ),
        },
        "extensions": {
            "org.idkmesh.phase0.verifier": {
                "candidate_artifact_id": artifact_id,
                "candidate_artifact_digest": actual_digest,
                "verifier_config": verifier_config,
            }
        },
    }

    validate_instance(
        verification_result,
        VERIFICATION_RESULT_SCHEMA,
        "generated VerificationResult",
    )
    return verification_result


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="examples/experiments/phase0-smoke.manifest.json",
        help="Repository-relative Phase 0 experiment manifest.",
    )
    parser.add_argument(
        "--worker-result",
        required=True,
        help="Repository-relative worker ResultManifest to verify.",
    )
    parser.add_argument(
        "--candidate-result",
        required=True,
        help="Repository-relative candidate NDJSON artifact to verify.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Repository-relative output path for generated VerificationResult JSON.",
    )
    parser.add_argument(
        "--artifact-id",
        default="candidate-result",
        help="Produced artifact id from the worker ResultManifest.",
    )
    parser.add_argument(
        "--verifier-id",
        default="phase0-independent-verifier",
        help="Verifier identity; must differ from the worker id.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = verify_candidate(
            manifest_path=resolve_repo_path(args.manifest),
            worker_result_path=resolve_repo_path(args.worker_result),
            candidate_path=resolve_repo_path(args.candidate_result),
            artifact_id=args.artifact_id,
            verifier_id=args.verifier_id,
        )
        output_path = resolve_repo_path(args.output)
        write_result(output_path, result)
        print(
            "OK: independent VerificationResult written to "
            f"{output_path}; status={result['status']} "
            f"recommendation={result['decision_support']['recommendation']}"
        )
        return 0 if result["status"] == "passed" else 1
    except (VerifierError, HarnessError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
