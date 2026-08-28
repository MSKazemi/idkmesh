#!/usr/bin/env python3
"""Deterministic two-attempt IDKMesh orchestration kernel.

This is a control-plane MVP, not a worker runtime. It uses replayable worker
adapters to exercise attempt isolation, ResultManifest collection, independent
verification routing, failure isolation, and deterministic run metadata.

Verification control is backward-compatible: existing legacy verifier-policy
configs remain valid, while new configs may select one canonical EvaluatorPlan.
The orchestrator executes no candidate code and has no canonical write/merge
authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Protocol

import evaluator_plan_runner
from local_verifier import (
    VerifierError,
    load_json,
    resolve_repo_path,
    run_fixture as run_legacy_fixture,
    semantic_signature,
)
from provenance_integrity import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_VERSION = "0.2"


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


class ResultBundleAdapter:
    """Collect an already-produced canonical candidate bundle.

    This adapter is intentionally execution-neutral. It can consume fixture or
    real worker bundles placed under the repository evidence/results boundary,
    while the producer remains outside coordinator core.
    """

    name = "result-bundle"

    def collect(self, spec: dict[str, Any]) -> CollectedCandidate:
        if "result_manifest" not in spec or "candidate_root" not in spec:
            raise WorkerAttemptError(
                "result-bundle requires result_manifest and candidate_root"
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
    ResultBundleAdapter.name: ResultBundleAdapter(),
    FixtureFailureAdapter.name: FixtureFailureAdapter(),
}


def validate_config(config: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "work_unit", "attempts"}
    missing = sorted(required - set(config))
    if missing:
        raise OrchestratorError(
            "orchestration config missing field(s): " + ", ".join(missing)
        )
    if config["schema_version"] != "0.1":
        raise OrchestratorError("unsupported orchestration config schema_version")
    if not isinstance(config["run_id"], str) or not config["run_id"]:
        raise OrchestratorError("run_id must be a non-empty string")
    if not isinstance(config["work_unit"], str):
        raise OrchestratorError("work_unit must be a repository-relative path")

    controls = [
        field
        for field in ("verifier_policy", "evaluator_plan")
        if field in config
    ]
    if len(controls) != 1:
        raise OrchestratorError(
            "orchestration config requires exactly one verification control: "
            "verifier_policy or evaluator_plan"
        )
    control_value = config[controls[0]]
    if not isinstance(control_value, str) or not control_value:
        raise OrchestratorError(
            f"{controls[0]} must be a non-empty repository-relative path"
        )

    attempts = config["attempts"]
    if not isinstance(attempts, list) or len(attempts) != 2:
        raise OrchestratorError(
            "two-attempt MVP requires exactly two attempt specifications"
        )
    ids: list[str] = []
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            raise OrchestratorError(f"attempt {index} must be an object")
        attempt_id = attempt.get("attempt_id")
        adapter_name = attempt.get("worker_adapter")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise OrchestratorError(
                f"attempt {index} requires a non-empty attempt_id"
            )
        if adapter_name not in ADAPTERS:
            raise OrchestratorError(
                f"attempt {attempt_id} uses unsupported worker_adapter {adapter_name!r}"
            )
        ids.append(attempt_id)
    if len(set(ids)) != len(ids):
        raise OrchestratorError("attempt_id values must be unique")


def resolve_output_path(raw: str) -> Path:
    """Restrict CLI output to the repository's non-canonical results/ subtree."""

    path = resolve_repo_path(raw)
    relative = path.relative_to(ROOT)
    if not relative.parts or relative.parts[0] != "results":
        raise OrchestratorError(
            "orchestrator output must be under results/; canonical repository files are not writable"
        )
    return path


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


def _result_manifest_record(worker_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": worker_result["id"],
        "attempt": worker_result["attempt"],
        "worker_id": worker_result["worker"]["id"],
        "worker_status": worker_result["status"],
        "digest": canonical_digest(worker_result),
    }


def _verification_control(
    config: dict[str, Any],
) -> tuple[str, Path, dict[str, Any], dict[str, Any]]:
    """Resolve one verifier control while preserving legacy replay compatibility."""

    if "evaluator_plan" in config:
        path = resolve_repo_path(config["evaluator_plan"])
        plan = evaluator_plan_runner.load_plan(path)
        metadata = {
            "kind": "evaluator_plan",
            "id": plan["id"],
            "schema_version": str(plan["schema_version"]),
            "backend": evaluator_plan_runner.backend_name(plan),
            "digest": canonical_digest(plan),
        }
        return "evaluator_plan", path, plan, metadata

    path = resolve_repo_path(config["verifier_policy"])
    policy = load_json(path)
    metadata = {
        "kind": "verifier_policy",
        "id": policy.get("id"),
        "schema_version": str(policy.get("schema_version", "unknown")),
        "backend": "legacy_fixture_policy",
        "digest": canonical_digest(policy),
    }
    return "verifier_policy", path, policy, metadata


def orchestrate(config: dict[str, Any]) -> dict[str, Any]:
    """Execute the deterministic two-attempt coordination flow."""

    validate_config(config)
    work_unit_path = resolve_repo_path(config["work_unit"])
    work_unit = load_json(work_unit_path)
    control_kind, control_path, control, control_metadata = _verification_control(config)

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
        except (VerifierError, OSError) as exc:
            attempt_records.append(
                {
                    **base_record,
                    "state": "result_manifest_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "result_manifest": None,
                    "verification": None,
                }
            )
            continue

        result_record = _result_manifest_record(worker_result)
        try:
            if control_kind == "evaluator_plan":
                verification = evaluator_plan_runner.run_fixture(
                    work_unit_path=work_unit_path,
                    result_manifest_path=candidate.result_manifest_path,
                    candidate_root=candidate.candidate_root,
                    plan_path=control_path,
                )
            else:
                verification = run_legacy_fixture(
                    work_unit_path=work_unit_path,
                    result_manifest_path=candidate.result_manifest_path,
                    candidate_root=candidate.candidate_root,
                    policy_path=control_path,
                )
        except (
            VerifierError,
            evaluator_plan_runner.EvaluatorPlanError,
            OSError,
        ) as exc:
            attempt_records.append(
                {
                    **base_record,
                    "state": "verification_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "candidate_root": candidate.candidate_root.relative_to(ROOT).as_posix(),
                    "result_manifest": result_record,
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
                "result_manifest": result_record,
                "verification": _verification_record(verification),
            }
        )

    control_failures = sum(
        record["state"]
        in {"worker_error", "result_manifest_error", "verification_error"}
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

    # `verifier_policy_digest` is retained for run-report v0.1 compatibility.
    # For EvaluatorPlan runs it contains the exact plan digest; the explicit
    # verification_control object removes ambiguity for new consumers.
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
        "verifier_policy_digest": control_metadata["digest"],
        "verification_control": control_metadata,
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
    matches = [
        attempt
        for attempt in record["attempts"]
        if attempt["attempt_id"] == attempt_id
    ]
    if len(matches) != 1:
        raise OrchestratorError(
            f"run record does not contain exactly one {attempt_id}"
        )
    return matches[0]


def _assert_good_vs_bad(record: dict[str, Any], label: str) -> None:
    good = _attempt_by_id(record, "attempt-001")
    bad = _attempt_by_id(record, "attempt-002")
    if (
        good["state"] != "verified"
        or good["verification"]["recommendation"] != "accept_candidate"
    ):
        raise OrchestratorError(f"{label}: known-good attempt was not independently supported")
    if (
        bad["state"] != "verified"
        or bad["verification"]["recommendation"] != "reject_candidate"
    ):
        raise OrchestratorError(f"{label}: known-bad attempt was not independently rejected")
    if (
        record["summary"]["candidates_supported"] != 1
        or record["summary"]["candidates_rejected"] != 1
    ):
        raise OrchestratorError(f"{label}: candidate summary lost independent outcomes")


def cmd_self_test(args: argparse.Namespace) -> int:
    comparison_path = resolve_repo_path(args.comparison_config)
    failure_path = resolve_repo_path(args.failure_config)
    evaluator_plan_path = resolve_repo_path(args.evaluator_plan_config)

    first = run_config(comparison_path)
    replay = run_config(comparison_path)
    failure = run_config(failure_path)
    plan_first = run_config(evaluator_plan_path)
    plan_replay = run_config(evaluator_plan_path)

    if first != replay:
        raise OrchestratorError(
            "same legacy replay config did not produce the same deterministic run record"
        )
    if plan_first != plan_replay:
        raise OrchestratorError(
            "same EvaluatorPlan replay config did not produce the same deterministic run record"
        )
    if first["attempt_order"] != ["attempt-001", "attempt-002"]:
        raise OrchestratorError("attempt ordering is not deterministic")
    if first["authority"] != {
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
        "automatic_candidate_selection": False,
    }:
        raise OrchestratorError("orchestrator authority invariant changed")

    try:
        resolve_output_path("README.md")
    except OrchestratorError:
        pass
    else:
        raise OrchestratorError(
            "canonical repository path was accepted as orchestrator output"
        )
    allowed_output = resolve_output_path("results/orchestration/self-test.json")
    if allowed_output.relative_to(ROOT).parts[0] != "results":
        raise OrchestratorError("results/ output path guard rejected its own invariant")

    _assert_good_vs_bad(first, "legacy verifier-policy replay")
    if first["verification_control"]["kind"] != "verifier_policy":
        raise OrchestratorError("legacy replay lost verifier-policy control identity")
    if first["verifier_policy_digest"] != first["verification_control"]["digest"]:
        raise OrchestratorError("legacy compatibility digest drifted from explicit control digest")

    _assert_good_vs_bad(plan_first, "EvaluatorPlan replay")
    if plan_first["verification_control"]["kind"] != "evaluator_plan":
        raise OrchestratorError("EvaluatorPlan replay did not record bound control kind")
    if plan_first["verification_control"]["backend"] != "unified_diff":
        raise OrchestratorError("EvaluatorPlan replay did not record unified_diff backend")
    if plan_first["verifier_policy_digest"] != plan_first["verification_control"]["digest"]:
        raise OrchestratorError("run-report compatibility digest differs from EvaluatorPlan digest")

    surviving = _attempt_by_id(failure, "attempt-001")
    failed = _attempt_by_id(failure, "attempt-002")
    if (
        surviving["state"] != "verified"
        or surviving["verification"]["recommendation"] != "accept_candidate"
    ):
        raise OrchestratorError(
            "peer worker failure prevented surviving attempt verification"
        )
    if failed["state"] != "worker_error" or failed["result_manifest"] is not None:
        raise OrchestratorError(
            "worker failure fixture did not remain isolated"
        )
    if failure["run_state"] != "completed_with_failures":
        raise OrchestratorError(
            "worker failure was not represented explicitly in run state"
        )

    print(
        "OK: two-attempt coordinator preserves legacy verifier-policy replay, routes bound "
        "EvaluatorPlan v0.2 candidates through the canonical backend, records exact verification "
        "control provenance, keeps attempts isolated, preserves support/reject outcomes, survives "
        "one worker failure, restricts output to results/, and has no canonical write/merge authority"
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    output_path = resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = run_config(config_path)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{record['run_state']}: wrote {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser(
        "self-test",
        help="Run deterministic legacy, EvaluatorPlan, and worker-failure fixtures.",
    )
    self_test.add_argument(
        "--comparison-config",
        default="examples/orchestration/two-attempt-good-vs-bad.json",
    )
    self_test.add_argument(
        "--failure-config",
        default="examples/orchestration/two-attempt-worker-failure.json",
    )
    self_test.add_argument(
        "--evaluator-plan-config",
        default="examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json",
    )
    self_test.set_defaults(func=cmd_self_test)

    run = subparsers.add_parser(
        "run",
        help="Replay one two-attempt orchestration configuration.",
    )
    run.add_argument("--config", required=True)
    run.add_argument(
        "--output",
        required=True,
        help="Repository-relative path under results/.",
    )
    run.set_defaults(func=cmd_run)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (
        OrchestratorError,
        WorkerAttemptError,
        VerifierError,
        evaluator_plan_runner.EvaluatorPlanError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
