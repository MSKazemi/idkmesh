#!/usr/bin/env python3
"""Compose two independently verified real-node attempts into canonical run evidence.

This is an integration bridge, not a new worker, verifier, or selection protocol.
Each input attempt must already contain the canonical artifacts emitted by
``tools/real_node_verifier_e2e.py``. The bridge validates their cryptographic
bindings, emits the existing ``idkmesh-two-attempt-run`` record shape, and then
uses the existing non-selecting Evidence Report layer.

No candidate is selected. No canonical project file is modified by generated
run evidence. Human/governance integration remains external.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from local_verifier import semantic_signature  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402
from run_evidence_report import (  # noqa: E402
    build_report,
    render_markdown,
    validate_report,
    validate_run_record,
)

BRIDGE_VERSION = "0.1"
RUN_KIND = "idkmesh-two-attempt-run"
EXPECTED_AUTHORITY = {
    "canonical_state_write": False,
    "git_push": False,
    "merge": False,
    "automatic_candidate_selection": False,
}


class RealTwoAttemptError(RuntimeError):
    """Raised when real-attempt evidence is incomplete, inconsistent, or unsafe."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RealTwoAttemptError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealTwoAttemptError(f"cannot load JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RealTwoAttemptError(f"expected JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_results_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    try:
        relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise RealTwoAttemptError("output path escapes repository root") from exc
    require(bool(relative.parts) and relative.parts[0] == "results", "output must be under results/")
    return path


def _result_manifest_summary(result: dict[str, Any]) -> dict[str, Any]:
    worker = result.get("worker")
    require(isinstance(worker, dict) and isinstance(worker.get("id"), str), "ResultManifest worker.id missing")
    require(result.get("status") in {"succeeded", "failed", "partial", "cancelled"}, "unsupported worker status")
    return {
        "id": result["id"],
        "attempt": result["attempt"],
        "worker_id": worker["id"],
        "worker_status": result["status"],
        "digest": canonical_digest(result),
    }


def _verification_summary(verification: dict[str, Any]) -> dict[str, Any]:
    verifier = verification.get("verifier")
    decision = verification.get("decision_support")
    checks = verification.get("checks")
    require(isinstance(verifier, dict) and isinstance(verifier.get("id"), str), "VerificationResult verifier.id missing")
    require(isinstance(decision, dict), "VerificationResult decision_support missing")
    require(isinstance(checks, list) and checks, "VerificationResult checks missing")
    recommendation = decision.get("recommendation")
    require(
        recommendation in {"accept_candidate", "reject_candidate", "escalate", "insufficient_evidence"},
        "unsupported verifier recommendation",
    )
    return {
        "id": verification["id"],
        "verifier_id": verifier["id"],
        "status": verification["status"],
        "recommendation": recommendation,
        "checks": [
            {
                "id": check["id"],
                "status": check["status"],
                "required": check["required"],
            }
            for check in checks
        ],
        "semantic_digest": canonical_digest(semantic_signature(verification)),
        "work_unit_digest": verification["provenance"]["work_unit_digest"],
        "result_manifest_digest": verification["provenance"]["result_manifest_digest"],
    }


def load_attempt(attempt_root: Path, *, attempt_id: str, order: int) -> dict[str, Any]:
    root = attempt_root.resolve()
    work_unit = load_json(root / "work-unit.json")
    plan = load_json(root / "evaluator-plan.json")
    result = load_json(root / "candidate-bundle" / "result-manifest.json")
    verification = load_json(root / "verification-result.json")

    work_unit_digest = canonical_digest(work_unit)
    plan_digest = canonical_digest(plan)
    result_digest = canonical_digest(result)

    require(result["work_unit_id"] == work_unit["id"], f"{attempt_id}: ResultManifest WorkUnit id drift")
    require(result["work_unit_version"] == work_unit["version"], f"{attempt_id}: ResultManifest WorkUnit version drift")
    require(
        result["provenance"]["work_unit_digest"] == work_unit_digest,
        f"{attempt_id}: ResultManifest WorkUnit digest drift",
    )
    require(
        verification["result_manifest_id"] == result["id"],
        f"{attempt_id}: VerificationResult ResultManifest id drift",
    )
    require(
        verification["work_unit_id"] == work_unit["id"]
        and verification["work_unit_version"] == work_unit["version"],
        f"{attempt_id}: VerificationResult WorkUnit identity drift",
    )
    require(
        verification["provenance"]["work_unit_digest"] == work_unit_digest,
        f"{attempt_id}: VerificationResult WorkUnit digest drift",
    )
    require(
        verification["provenance"]["result_manifest_digest"] == result_digest,
        f"{attempt_id}: VerificationResult ResultManifest digest drift",
    )
    require(
        verification["provenance"]["verifier_config_digest"] == plan_digest,
        f"{attempt_id}: VerificationResult EvaluatorPlan digest drift",
    )
    require(
        verification.get("independence", {}).get("independent_from_worker") is True,
        f"{attempt_id}: verification is not marked independent from worker",
    )

    return {
        "attempt_id": attempt_id,
        "order": order,
        "root": root,
        "work_unit": work_unit,
        "work_unit_digest": work_unit_digest,
        "plan": plan,
        "plan_digest": plan_digest,
        "result": result,
        "result_digest": result_digest,
        "verification": verification,
    }


def build_run(*, run_id: str, attempt_roots: list[Path]) -> dict[str, Any]:
    require(len(attempt_roots) == 2, "real two-attempt bridge requires exactly two attempts")
    attempts = [
        load_attempt(attempt_roots[0], attempt_id="attempt-001", order=1),
        load_attempt(attempt_roots[1], attempt_id="attempt-002", order=2),
    ]

    first = attempts[0]
    for attempt in attempts[1:]:
        require(
            attempt["work_unit"] == first["work_unit"],
            "real attempts do not share the exact same WorkUnit",
        )
        require(
            attempt["plan"] == first["plan"],
            "real attempts do not share the exact same verifier-owned EvaluatorPlan",
        )

    attempt_records: list[dict[str, Any]] = []
    for attempt in attempts:
        verification = attempt["verification"]
        attempt_records.append(
            {
                "attempt_id": attempt["attempt_id"],
                "order": attempt["order"],
                "worker_adapter": "idkmesh-node-exact-sha",
                "state": "verified",
                "error": None,
                "candidate_root": attempt["root"].relative_to(ROOT).as_posix(),
                "result_manifest": _result_manifest_summary(attempt["result"]),
                "verification": _verification_summary(verification),
            }
        )

    supported = sum(
        item["verification"]["recommendation"] == "accept_candidate" for item in attempt_records
    )
    rejected = sum(
        item["verification"]["recommendation"] == "reject_candidate" for item in attempt_records
    )

    bridge_config = {
        "schema_version": "0.1",
        "kind": "idkmesh-real-two-attempt-bridge-config",
        "run_id": run_id,
        "worker_adapter": "idkmesh-node-exact-sha",
        "attempt_count": 2,
        "work_unit_digest": first["work_unit_digest"],
        "evaluator_plan_digest": first["plan_digest"],
    }

    record = {
        "schema_version": "0.1",
        "kind": RUN_KIND,
        "run_id": run_id,
        "orchestrator_version": f"real-bridge/{BRIDGE_VERSION}",
        "config_digest": canonical_digest(bridge_config),
        "work_unit": {
            "id": first["work_unit"]["id"],
            "version": first["work_unit"]["version"],
            "digest": first["work_unit_digest"],
        },
        "verifier_policy_digest": first["plan_digest"],
        "attempt_order": ["attempt-001", "attempt-002"],
        "attempts": attempt_records,
        "summary": {
            "attempt_count": 2,
            "control_failures": 0,
            "candidates_supported": supported,
            "candidates_rejected": rejected,
        },
        "run_state": "completed",
        "authority": dict(EXPECTED_AUTHORITY),
        "extensions": {
            "org.idkmesh.real_two_attempt": {
                "bridge_version": BRIDGE_VERSION,
                "same_work_unit_required": True,
                "same_evaluator_plan_required": True,
                "candidate_selection_performed": False,
                "human_integration_decision_required": True,
            }
        },
    }
    validate_run_record(record)
    return record


def cmd_compose(args: argparse.Namespace) -> int:
    run_output = resolve_results_path(args.run_output)
    report_json = resolve_results_path(args.report_json)
    report_markdown = resolve_results_path(args.report_markdown)
    require(len({run_output, report_json, report_markdown}) == 3, "generated outputs must be distinct")

    record = build_run(
        run_id=args.run_id,
        attempt_roots=[(ROOT / args.attempt_one).resolve(), (ROOT / args.attempt_two).resolve()],
    )
    report = build_report(record)
    validate_report(report, record)

    write_json(run_output, record)
    write_json(report_json, report)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.write_text(render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": record["run_id"],
                "run_digest": canonical_digest(record),
                "attempt_count": record["summary"]["attempt_count"],
                "supported": report["summary"]["supported"],
                "rejected": report["summary"]["rejected"],
                "human_decision": report["human_decision"]["status"],
                "automatic_candidate_selection": record["authority"]["automatic_candidate_selection"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_replay_check(args: argparse.Namespace) -> int:
    run_record = load_json((ROOT / args.run_record).resolve())
    saved_report = load_json((ROOT / args.report_json).resolve())
    validate_run_record(run_record)
    rebuilt = build_report(run_record)
    validate_report(rebuilt, run_record)
    match = canonical_digest(rebuilt) == canonical_digest(saved_report)
    result = {
        "schema_version": "0.1",
        "kind": "idkmesh-real-run-evidence-replay-check",
        "run_id": run_record["run_id"],
        "saved_report_digest": canonical_digest(saved_report),
        "rebuilt_report_digest": canonical_digest(rebuilt),
        "semantic_report_match": match,
        "candidate_reexecution_required": False,
        "human_integration_decision": rebuilt["human_decision"]["status"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if match else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compose = subparsers.add_parser("compose", help="Compose two real verified attempt roots.")
    compose.add_argument("--attempt-one", required=True, help="Repository-relative evaluator-owned attempt root.")
    compose.add_argument("--attempt-two", required=True, help="Repository-relative evaluator-owned attempt root.")
    compose.add_argument("--run-id", required=True)
    compose.add_argument("--run-output", required=True, help="Repository-relative output under results/.")
    compose.add_argument("--report-json", required=True, help="Repository-relative output under results/.")
    compose.add_argument("--report-markdown", required=True, help="Repository-relative output under results/.")
    compose.set_defaults(func=cmd_compose)

    replay = subparsers.add_parser("replay-check", help="Rebuild the non-selecting report from saved real run metadata.")
    replay.add_argument("--run-record", required=True)
    replay.add_argument("--report-json", required=True)
    replay.set_defaults(func=cmd_replay_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (RealTwoAttemptError, KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
