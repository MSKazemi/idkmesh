#!/usr/bin/env python3
"""Deterministic two-attempt IDKMesh orchestration kernel.

This is a control-plane MVP, not a worker runtime. It uses replayable fixture
worker adapters to exercise attempt isolation, ResultManifest collection,
independent verification routing, failure isolation, and deterministic run
metadata. It executes no candidate code and has no canonical write/merge authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Protocol

from local_verifier import (
    load_json,
    resolve_repo_path,
    run_fixture,
    semantic_signature,
)
from provenance_integrity import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_VERSION = "0.1"


class OrchestratorError(RuntimeError):
    """Raised for invalid replay configuration or coordinator invariants."""


class WorkerAttemptError(RuntimeError):
    """A worker adapter failed before returning a usable ResultManifest."""


@dataclass(frozen=True)
class CollectedCandidate:
    result_manifest_path: Path
    candidate_root: Path


class WorkerAdapter(Protocol):
    name: str

    def collect(self, spec: dict[str, Any]) -> CollectedCandidate:
        """Return a candidate bundle or raise WorkerAttemptError."""


class FixtureResultAdapter:
    name = "fixture-result"

    def collect(self, spec: dict[str, Any]) -> CollectedCandidate:
        if "result_manifest" not in spec or "candidate_root" not in spec:
            raise WorkerAttemptError(
                "fixture-result requires result_manifest and candidate_root"
            )
        return CollectedCandidate(
            result_manifest_path=resolve_repo_path(spec["result_manifest"]),
            candidate_root=resolve_repo_path(spec["candidate_root"]),
        )


class FixtureFailureAdapter:
    name = "fixture-failure"

    def collect(self, spec: dict[str, Any]) -> CollectedCandidate:
        raise WorkerAttemptError(
            str(spec.get("failure", "simulated worker failure before ResultManifest"))
        )


ADAPTERS: dict[str, WorkerAdapter] = {
    FixtureResultAdapter.name: FixtureResultAdapter(),
    FixtureFailureAdapter.name: FixtureFailureAdapter(),
}


def validate_config(config: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "work_unit", "verifier_policy", "attempts"}
    missing = sorted(required - set(config))
    if missing:
        raise OrchestratorError("orchestration config missing field(s): " + ", ".join(missing))
    if config["schema_version"] != "0.1":
        raise OrchestratorError("unsupported orchestration config schema_version")
    if not isinstance(config["run_id"], str) or not config["run_id"]:
        raise OrchestratorError("run_id must be a non-empty string")
    if not isinstance(config["work_unit"], str) or not isinstance(config["verifier_policy"], str):
        raise OrchestratorError("work_unit and verifier_policy must be repository-relative paths")
    attempts = config["attempts"]
    if not isinstance(attempts, list) or len(attempts) != 2:
        raise OrchestratorError("two-attempt MVP requires exactly two attempt specifications")
    ids: list[str] = []
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            raise OrchestratorError(f"attempt {index} must be an object")
        attempt_id = attempt.get("attempt_id")
        adapter_name = attempt.get("worker_adapter")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise OrchestratorError(f"attempt {index} requires a non-empty attempt_id")
        if adapter_name not in ADAPTERS:
            raise OrchestratorError(
                f"attempt {attempt_id} uses unsupported worker_adapter {adapter_name!r}"
            )
        ids.append(attempt_id)
    if len(set(ids)) != len(ids):
        raise OrchestratorError("attempt_id values must be unique")


def _verification_record(verification: dict[str, Any]) -> dict[str, Any]:
    signature = semantic_signature(verification)
    return {
        "id": verification["id"],
        "verifier_id": verification["verifier"]["id"],
        "status": verification["status"],
        "recommendation": verification["decision_support"]["recommendation"],
        "checks": [
            {
                "id": check["id"],
                "status": check["status"],
                "required": check["required"],
            }
            for check in verification["checks"]
        ],
        "semantic_digest": canonical_digest(signature),
        "work_unit_digest": verification["provenance"]["work_unit_digest"],
        "result_manifest_digest": verification["provenance"]["result_manifest_digest"],
    }


def orchestrate(config: dict[str, Any]) -> dict[str, Any]:
    """Execute the deterministic two-attempt coordination flow."""

    validate_config(config)
    work_unit_path = resolve_repo_path(config["work_unit"])
    policy_path = resolve_repo_path(config["verifier_policy"])
    work_unit = load_json(work_unit_path)
    policy = load_json(policy_path)

    attempt_records: list[dict[str, Any]] = []
    for order, spec in enumerate(config["attempts"], start=1):
        attempt_id = spec["attempt_id"]
        adapter_name = spec["worker_adapter"]
        adapter = ADAPTERS[adapter_name]
        base_record: dict[str, Any] = {
            "attempt_id": attempt_id,
            "order": order,
            "worker_adapter": adapter_name,
        }

        try:
            candidate = adapter.collect(spec)
        except WorkerAttemptError as exc:
            attempt_records.append(
                {
                    **base_record,
                    "state": "worker_error",
                    "error": str(exc),
                    "result_manifest": None,
                    "verification": None,
                }
            )
            continue

        try:
            worker_result = load_json(candidate.result_manifest_path)
            verification = run_fixture(
                work_unit_path=work_unit_path,
                result_manifest_path=candidate.result_manifest_path,
                candidate_root=candidate.candidate_root,
                policy_path=policy_path,
            )
        except Exception as exc:  # fail one attempt without aborting the peer attempt
            attempt_records.append(
                {
                    **base_record,
                    "state": "verification_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "result_manifest": None,
                    "verification": None,
                }
            )
            continue

        attempt_records.append(
            {
                **base_record,
                "state": "verified",
                "error": None,
                "candidate_root": candidate.candidate_root.relative_to(ROOT).as_posix(),
                "result_manifest": {
                    "id": worker_result["id"],
                    "worker_id": worker_result["worker"]["id"],
                    "worker_status": worker_result["status"],
                    "digest": canonical_digest(worker_result),
                },
                "verification": _verification_record(verification),
            }
        )

    control_failures = sum(
        record["state"] in {"worker_error", "verification_error"}
        for record in attempt_records
    )
    supported = sum(
        record.get("verification", {}).get("recommendation") == "accept_candidate"
        for record in attempt_records
        if record.get("verification") is not None
    )
    rejected = sum(
        record.get("verification", {}).get("recommendation") == "reject_candidate"
        for record in attempt_records
        if record.get("verification") is not None
    )

    return {
        "schema_version": "0.1",
        "kind": "idkmesh-two-attempt-run",
        "run_id": config["run_id"],
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "config_digest": canonical_digest(config),
        "work_unit": {
            "id": work_unit["id"],
            "version": work_unit["version"],
            "digest": canonical_digest(work_unit),
        },
        "verifier_policy_digest": canonical_digest(policy),
        "attempt_order": [record["attempt_id"] for record in attempt_records],
        "attempts": attempt_records,
        "summary": {
            "attempt_count": len(attempt_records),
            "control_failures": control_failures,
            "candidates_supported": supported,
            "candidates_rejected": rejected,
        },
        "run_state": "completed_with_failures" if control_failures else "completed",
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }


def run_config(path: Path) -> dict[str, Any]:
    return orchestrate(load_json(path))


def _attempt_by_id(record: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    matches = [attempt for attempt in record["attempts"] if attempt["attempt_id"] == attempt_id]
    if len(matches) != 1:
        raise OrchestratorError(f"run record does not contain exactly one {attempt_id}")
    return matches[0]


def cmd_self_test(args: argparse.Namespace) -> int:
    comparison_path = resolve_repo_path(args.comparison_config)
    failure_path = resolve_repo_path(args.failure_config)

    first = run_config(comparison_path)
    replay = run_config(comparison_path)
    failure = run_config(failure_path)

    if first != replay:
        raise OrchestratorError("same replay config did not produce the same deterministic run record")
    if first["attempt_order"] != ["attempt-001", "attempt-002"]:
        raise OrchestratorError("attempt ordering is not deterministic")
    if first["authority"] != {
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
        "automatic_candidate_selection": False,
    }:
        raise OrchestratorError("orchestrator authority invariant changed")

    good = _attempt_by_id(first, "attempt-001")
    bad = _attempt_by_id(first, "attempt-002")
    if good["state"] != "verified" or good["verification"]["recommendation"] != "accept_candidate":
        raise OrchestratorError("known-good attempt was not independently supported")
    if bad["state"] != "verified" or bad["verification"]["recommendation"] != "reject_candidate":
        raise OrchestratorError("known-bad attempt was not independently rejected")
    if first["summary"]["candidates_supported"] != 1 or first["summary"]["candidates_rejected"] != 1:
        raise OrchestratorError("candidate summary does not preserve independent outcomes")

    surviving = _attempt_by_id(failure, "attempt-001")
    failed = _attempt_by_id(failure, "attempt-002")
    if surviving["state"] != "verified" or surviving["verification"]["recommendation"] != "accept_candidate":
        raise OrchestratorError("peer worker failure prevented surviving attempt verification")
    if failed["state"] != "worker_error" or failed["result_manifest"] is not None:
        raise OrchestratorError("worker failure fixture did not remain isolated")
    if failure["run_state"] != "completed_with_failures":
        raise OrchestratorError("worker failure was not represented explicitly in run state")

    print(
        "OK: two-attempt coordinator is deterministic, keeps attempts isolated, collects separate "
        "ResultManifests, routes each candidate to independent verification, preserves support/reject "
        "outcomes, survives one worker failure, and has no canonical write/merge authority"
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    output_path = resolve_repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = run_config(config_path)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{record['run_state']}: wrote {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser("self-test", help="Run deterministic comparison and worker-failure fixtures.")
    self_test.add_argument(
        "--comparison-config",
        default="examples/orchestration/two-attempt-good-vs-bad.json",
    )
    self_test.add_argument(
        "--failure-config",
        default="examples/orchestration/two-attempt-worker-failure.json",
    )
    self_test.set_defaults(func=cmd_self_test)

    run = subparsers.add_parser("run", help="Replay one two-attempt orchestration configuration.")
    run.add_argument("--config", required=True)
    run.add_argument("--output", required=True)
    run.set_defaults(func=cmd_run)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OrchestratorError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
