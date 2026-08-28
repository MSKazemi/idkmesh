#!/usr/bin/env python3
"""Deterministic two-attempt orchestration kernel for IDKMesh Phase A0.

This module proves the smallest replayable multi-worker loop without executing
candidate-supplied code or granting integration authority. It dispatches one
bounded Work Unit to exactly two fixture worker attempts, isolates their
candidate roots, emits canonical ResultManifests, routes successful candidates
through the canonical local verifier, and retains per-attempt evidence.

The fixture workers are deliberately replaceable adapters. The real local-node
adapter remains gated on PR #34 and controlled-Docker acceptance #37.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from local_verifier import (
    VerifierError,
    load_json,
    resolve_repo_path,
    sha256_bytes,
    verify_candidate,
)
from provenance_integrity import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_VERSION = "0.1"
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
MARKER_NAME = ".idkmesh-orchestrator-run"
DEFAULT_WORK_UNIT = "examples/work-units/orchestrator-smoke.work-unit.json"
DEFAULT_POLICY = "verification/fixtures/verifier-smoke-policy.json"
DEFAULT_OUTPUT_BASE = "results/orchestrator"


class OrchestratorError(RuntimeError):
    """Raised when orchestration inputs or workspace boundaries are unsafe."""


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_RE.fullmatch(run_id):
        raise OrchestratorError(
            "run_id must match ^[a-z0-9][a-z0-9._-]{2,63}$"
        )


def _logical_timestamp(attempt: int, *, finished: bool) -> str:
    """Return deterministic fixture time for replayable metadata.

    Phase A0 adapters are fixtures, so logical time is preferable to wall-clock
    time. Real worker adapters introduced in Phase A1 should record observed
    timestamps instead.
    """

    second = attempt * 2 + (1 if finished else 0)
    return f"2026-08-28T00:00:{second:02d}Z"


def _ensure_output_base(output_base: Path, *, allow_external: bool) -> Path:
    output_base = output_base.resolve()
    if allow_external:
        output_base.mkdir(parents=True, exist_ok=True)
        return output_base

    required_root = (ROOT / DEFAULT_OUTPUT_BASE).resolve()
    try:
        output_base.relative_to(required_root)
    except ValueError as exc:
        raise OrchestratorError(
            f"CLI output must stay under {required_root.relative_to(ROOT)}"
        ) from exc
    output_base.mkdir(parents=True, exist_ok=True)
    return output_base


def _prepare_run_root(output_base: Path, run_id: str) -> Path:
    """Create a run root and only clean a previous root carrying our marker."""

    run_root = (output_base / run_id).resolve()
    try:
        run_root.relative_to(output_base)
    except ValueError as exc:
        raise OrchestratorError("run workspace escapes output base") from exc

    marker = run_root / MARKER_NAME
    if run_root.exists():
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != run_id:
            raise OrchestratorError(
                f"refusing to clean unowned workspace without matching {MARKER_NAME}: {run_root}"
            )
        shutil.rmtree(run_root)

    run_root.mkdir(parents=True)
    marker.write_text(run_id + "\n", encoding="utf-8")
    return run_root


def _candidate_payload(policy: dict[str, Any], behavior: str) -> dict[str, Any]:
    expected = json.loads(json.dumps(policy["required_json"]))
    if behavior == "good":
        return expected
    if behavior == "bad":
        candidate = expected
        if isinstance(candidate.get("answer"), int):
            candidate["answer"] += 1
        else:
            candidate["status"] = "incorrect"
        return candidate
    raise OrchestratorError(f"unsupported candidate behavior: {behavior}")


def _worker_result(
    *,
    run_id: str,
    attempt: int,
    behavior: str,
    work_unit: dict[str, Any],
    policy: dict[str, Any],
    candidate_bytes: bytes,
) -> dict[str, Any]:
    worker_id = f"fixture-{behavior}-worker-{attempt}"
    worker_config = {
        "adapter": "deterministic-fixture-worker",
        "adapter_version": ORCHESTRATOR_VERSION,
        "behavior": behavior,
        "attempt": attempt,
    }
    required_validator_ids = [
        validator["id"] for validator in work_unit["validators"] if validator["required"]
    ]
    source_revision = work_unit.get("provenance", {}).get(
        "source_revision", "orchestrator-fixture-v1"
    )
    return {
        "schema_version": "0.1",
        "id": f"{work_unit['id']}/run/{run_id}/attempt-{attempt}",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": attempt,
        "worker": {
            "id": worker_id,
            "type": "system",
            "adapter": "deterministic-fixture-worker",
            "adapter_version": ORCHESTRATOR_VERSION,
        },
        "status": "succeeded",
        "started_at": _logical_timestamp(attempt, finished=False),
        "finished_at": _logical_timestamp(attempt, finished=True),
        "produced_artifacts": [
            {
                "id": policy["candidate_artifact_id"],
                "type": "test_result",
                "locator": "candidate.json",
                "digest": sha256_bytes(candidate_bytes),
                "media_type": "application/json",
                "description": (
                    "Deterministic fixture candidate emitted by the Phase A0 orchestration kernel."
                ),
            }
        ],
        "logs": [],
        "metrics": {"candidate_bytes": len(candidate_bytes)},
        "resources": {
            "wall_seconds": 0.0,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": (
                "Fixture worker reports only that it produced a candidate; it does not claim acceptance."
            ),
            "claims": ["Candidate is ready for independent verification."],
            "confidence": {"value": 1.0, "meaning": "uncalibrated"},
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": source_revision,
            "worker_config_digest": canonical_digest(worker_config),
            "environment": {
                "platform": "deterministic-fixture",
                "tool_versions": {
                    "idkmesh-local-orchestrator": ORCHESTRATOR_VERSION,
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids,
            "evidence_artifact_ids": [policy["candidate_artifact_id"]],
            "notes": (
                "Worker success is candidate evidence only; independent verification is required."
            ),
        },
        "extensions": {
            "org.idkmesh.orchestrator.run_id": run_id,
            "org.idkmesh.orchestrator.fixture_behavior": behavior,
        },
    }


def _run_attempt(
    *,
    run_root: Path,
    run_id: str,
    attempt: int,
    behavior: str,
    work_unit: dict[str, Any],
    policy: dict[str, Any],
    policy_path: Path,
) -> dict[str, Any]:
    attempt_root = run_root / f"attempt-{attempt}"
    candidate_root = attempt_root / "candidate-root"
    attempt_root.mkdir()
    candidate_root.mkdir()

    record: dict[str, Any] = {
        "attempt": attempt,
        "attempt_id": f"{run_id}/attempt-{attempt}",
        "workspace": attempt_root.relative_to(run_root).as_posix(),
        "worker": {
            "adapter": "deterministic-fixture-worker",
            "adapter_version": ORCHESTRATOR_VERSION,
            "behavior": behavior,
        },
        "worker_status": "pending",
        "result_manifest": None,
        "verification_result": None,
        "verification_status": "not_run",
        "recommendation": None,
        "error": None,
    }

    if behavior == "error":
        record["worker_status"] = "error"
        record["error"] = "fixture-worker-error"
        return record

    candidate = _candidate_payload(policy, behavior)
    candidate_bytes = (
        json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    candidate_path = candidate_root / "candidate.json"
    candidate_path.write_bytes(candidate_bytes)

    result_manifest = _worker_result(
        run_id=run_id,
        attempt=attempt,
        behavior=behavior,
        work_unit=work_unit,
        policy=policy,
        candidate_bytes=candidate_bytes,
    )
    result_manifest_path = attempt_root / "result-manifest.json"
    result_manifest_path.write_text(
        json.dumps(result_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record["worker_status"] = "succeeded"
    record["result_manifest"] = result_manifest_path.relative_to(run_root).as_posix()

    verification_result = verify_candidate(
        work_unit=work_unit,
        worker_result=result_manifest,
        policy=policy,
        candidate_root=candidate_root,
        policy_path=policy_path,
    )
    verification_path = attempt_root / "verification-result.json"
    verification_path.write_text(
        json.dumps(verification_result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record["verification_result"] = verification_path.relative_to(run_root).as_posix()
    record["verification_status"] = verification_result["status"]
    record["recommendation"] = verification_result["decision_support"]["recommendation"]
    return record


def semantic_signature(report: dict[str, Any]) -> dict[str, Any]:
    """Return the replay-relevant semantic outcome, excluding runtime paths."""

    return {
        "work_unit_id": report["work_unit"]["id"],
        "work_unit_version": report["work_unit"]["version"],
        "attempt_order": report["attempt_order"],
        "attempts": [
            {
                "attempt": item["attempt"],
                "behavior": item["worker"]["behavior"],
                "worker_status": item["worker_status"],
                "verification_status": item["verification_status"],
                "recommendation": item["recommendation"],
                "error": item["error"],
            }
            for item in report["attempts"]
        ],
        "automatic_integration": report["integration"]["automatic_integration"],
    }


def run_orchestration(
    *,
    output_base: Path,
    run_id: str,
    scenario: str,
    work_unit_path: Path,
    policy_path: Path,
    allow_external_output: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Run exactly two fixture attempts and return report plus run root."""

    _validate_run_id(run_id)
    scenarios = {
        "good-bad": ["good", "bad"],
        "good-error": ["good", "error"],
    }
    if scenario not in scenarios:
        raise OrchestratorError(
            "scenario must be one of: " + ", ".join(sorted(scenarios))
        )

    work_unit = load_json(work_unit_path)
    policy = load_json(policy_path)
    output_base = _ensure_output_base(output_base, allow_external=allow_external_output)
    run_root = _prepare_run_root(output_base, run_id)

    attempts: list[dict[str, Any]] = []
    for attempt, behavior in enumerate(scenarios[scenario], start=1):
        try:
            record = _run_attempt(
                run_root=run_root,
                run_id=run_id,
                attempt=attempt,
                behavior=behavior,
                work_unit=work_unit,
                policy=policy,
                policy_path=policy_path,
            )
        except (VerifierError, OSError, ValueError) as exc:
            # Attempt failure is evidence. It must not abort the sibling attempt.
            record = {
                "attempt": attempt,
                "attempt_id": f"{run_id}/attempt-{attempt}",
                "workspace": f"attempt-{attempt}",
                "worker": {
                    "adapter": "deterministic-fixture-worker",
                    "adapter_version": ORCHESTRATOR_VERSION,
                    "behavior": behavior,
                },
                "worker_status": "error",
                "result_manifest": None,
                "verification_result": None,
                "verification_status": "not_run",
                "recommendation": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        attempts.append(record)

    report: dict[str, Any] = {
        "schema_version": "0.1",
        "run_id": run_id,
        "scenario": scenario,
        "orchestrator": {
            "id": "idkmesh-local-orchestrator",
            "version": ORCHESTRATOR_VERSION,
            "dispatch_policy": "fixed-two-attempt-sequential",
        },
        "work_unit": {
            "id": work_unit["id"],
            "version": work_unit["version"],
            "digest": canonical_digest(work_unit),
            "source_revision": work_unit.get("provenance", {}).get(
                "source_revision", "orchestrator-fixture-v1"
            ),
            "locator": work_unit_path.as_posix(),
        },
        "verifier": {
            "adapter": "experiments/local_verifier.py",
            "policy_id": policy["id"],
            "policy_digest": canonical_digest(policy),
            "policy_locator": policy_path.as_posix(),
        },
        "attempt_order": [1, 2],
        "attempts": attempts,
        "integration": {
            "authority": "human",
            "automatic_integration": False,
            "decision": None,
            "reason": (
                "Orchestration and VerificationResults are evidence only; no majority vote or worker claim grants merge authority."
            ),
        },
        "replay": {
            "scenario": scenario,
            "run_id": run_id,
            "work_unit_digest": canonical_digest(work_unit),
            "verifier_policy_digest": canonical_digest(policy),
            "fixture_adapter_version": ORCHESTRATOR_VERSION,
        },
    }
    report["semantic_signature"] = semantic_signature(report)

    report_path = run_root / "orchestration-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report, run_root


def _assert_good_bad(report: dict[str, Any]) -> None:
    if len(report["attempts"]) != 2:
        raise OrchestratorError("good-bad run did not retain exactly two attempt records")
    first, second = report["attempts"]
    if first["worker_status"] != "succeeded" or first["verification_status"] != "passed":
        raise OrchestratorError("known-good attempt did not pass independent verification")
    if first["recommendation"] != "accept_candidate":
        raise OrchestratorError("known-good attempt missing accept_candidate decision support")
    if second["worker_status"] != "succeeded" or second["verification_status"] != "failed":
        raise OrchestratorError("self-consistent bad attempt was not rejected independently")
    if second["recommendation"] != "reject_candidate":
        raise OrchestratorError("known-bad attempt missing reject_candidate decision support")
    if report["integration"]["automatic_integration"]:
        raise OrchestratorError("orchestrator must never auto-integrate candidates")


def _assert_good_error(report: dict[str, Any]) -> None:
    if len(report["attempts"]) != 2:
        raise OrchestratorError("good-error run did not retain exactly two attempt records")
    first, second = report["attempts"]
    if first["verification_status"] != "passed":
        raise OrchestratorError("healthy sibling did not finish after worker-error scenario")
    if second["worker_status"] != "error" or second["verification_status"] != "not_run":
        raise OrchestratorError("worker error was not isolated as its own attempt outcome")


def cmd_run(args: argparse.Namespace) -> int:
    report, run_root = run_orchestration(
        output_base=resolve_repo_path(args.output_base),
        run_id=args.run_id,
        scenario=args.scenario,
        work_unit_path=resolve_repo_path(args.work_unit),
        policy_path=resolve_repo_path(args.policy),
    )
    print(
        f"OK: wrote {run_root.relative_to(ROOT) / 'orchestration-report.json'}; "
        f"outcomes={[(a['worker_status'], a['verification_status']) for a in report['attempts']]}"
    )
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    work_unit_path = resolve_repo_path(args.work_unit)
    policy_path = resolve_repo_path(args.policy)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        first, _ = run_orchestration(
            output_base=base / "replay-a",
            run_id="self-test-good-bad",
            scenario="good-bad",
            work_unit_path=work_unit_path,
            policy_path=policy_path,
            allow_external_output=True,
        )
        replay, _ = run_orchestration(
            output_base=base / "replay-b",
            run_id="self-test-good-bad",
            scenario="good-bad",
            work_unit_path=work_unit_path,
            policy_path=policy_path,
            allow_external_output=True,
        )
        failure_isolation, _ = run_orchestration(
            output_base=base / "failure-isolation",
            run_id="self-test-good-error",
            scenario="good-error",
            work_unit_path=work_unit_path,
            policy_path=policy_path,
            allow_external_output=True,
        )

        _assert_good_bad(first)
        _assert_good_bad(replay)
        _assert_good_error(failure_isolation)
        if semantic_signature(first) != semantic_signature(replay):
            raise OrchestratorError("deterministic replay changed semantic outcomes")

    print(
        "OK: two-attempt kernel preserves pass/reject disagreement, isolates worker failure, "
        "replays semantic outcomes, and performs no automatic integration"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one deterministic two-attempt scenario.")
    run_parser.add_argument("--run-id", default="phase-a0-good-bad")
    run_parser.add_argument("--scenario", choices=["good-bad", "good-error"], default="good-bad")
    run_parser.add_argument("--work-unit", default=DEFAULT_WORK_UNIT)
    run_parser.add_argument("--policy", default=DEFAULT_POLICY)
    run_parser.add_argument("--output-base", default=DEFAULT_OUTPUT_BASE)
    run_parser.set_defaults(func=cmd_run)

    self_test = subparsers.add_parser("self-test", help="Exercise replay and failure isolation.")
    self_test.add_argument("--work-unit", default=DEFAULT_WORK_UNIT)
    self_test.add_argument("--policy", default=DEFAULT_POLICY)
    self_test.set_defaults(func=cmd_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OrchestratorError, VerifierError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
