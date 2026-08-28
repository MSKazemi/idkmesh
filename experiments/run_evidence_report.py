#!/usr/bin/env python3
"""Build a non-selecting evidence view over one replayable orchestration run.

This module is an aggregation/presentation layer. It does not replace the
canonical ResultManifest or VerificationResult contracts, does not execute
candidate code, and has no integration/merge authority.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from local_verifier import VerifierError, load_json, resolve_repo_path
from provenance_integrity import canonical_digest
from two_attempt_orchestrator import OrchestratorError, resolve_output_path, run_config

REPORT_VERSION = "0.1"
REPORT_KIND = "idkmesh-run-evidence-report"
SOURCE_RUN_KIND = "idkmesh-two-attempt-run"
ERROR_STATES = {"worker_error", "result_manifest_error", "verification_error"}
KNOWN_ATTEMPT_STATES = {"verified", *ERROR_STATES}
KNOWN_RECOMMENDATIONS = {
    "accept_candidate",
    "reject_candidate",
    "escalate",
    "insufficient_evidence",
}


class EvidenceReportError(RuntimeError):
    """Raised when a run record/report violates the evidence-view invariants."""


def _require_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise EvidenceReportError(f"{field} must be a sha256:<64 hex> digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise EvidenceReportError(f"{field} must contain hexadecimal SHA-256 bytes") from exc
    return value


def validate_run_record(record: dict[str, Any]) -> None:
    """Fail closed on inconsistent orchestration evidence before rendering it."""

    if record.get("schema_version") != "0.1" or record.get("kind") != SOURCE_RUN_KIND:
        raise EvidenceReportError("unsupported orchestration run record")
    if not isinstance(record.get("run_id"), str) or not record["run_id"]:
        raise EvidenceReportError("run record requires a non-empty run_id")

    work_unit = record.get("work_unit")
    if not isinstance(work_unit, dict):
        raise EvidenceReportError("run record requires a work_unit object")
    if not isinstance(work_unit.get("id"), str) or not work_unit["id"]:
        raise EvidenceReportError("run record work_unit.id must be non-empty")
    if not isinstance(work_unit.get("version"), int) or work_unit["version"] < 1:
        raise EvidenceReportError("run record work_unit.version must be a positive integer")
    work_unit_digest = _require_digest(work_unit.get("digest"), "work_unit.digest")
    _require_digest(record.get("config_digest"), "config_digest")
    _require_digest(record.get("verifier_policy_digest"), "verifier_policy_digest")

    authority = record.get("authority")
    expected_authority = {
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
        "automatic_candidate_selection": False,
    }
    if authority != expected_authority:
        raise EvidenceReportError(
            "run record authority is outside the read-only/non-selecting evidence boundary"
        )

    attempts = record.get("attempts")
    order = record.get("attempt_order")
    if not isinstance(attempts, list) or not attempts:
        raise EvidenceReportError("run record requires at least one attempt")
    if not isinstance(order, list):
        raise EvidenceReportError("run record requires attempt_order")

    attempt_ids: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise EvidenceReportError("every attempt must be an object")
        attempt_id = attempt.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise EvidenceReportError("every attempt requires a non-empty attempt_id")
        attempt_ids.append(attempt_id)

        state = attempt.get("state")
        if state not in KNOWN_ATTEMPT_STATES:
            raise EvidenceReportError(f"attempt {attempt_id} has unsupported state {state!r}")

        result_manifest = attempt.get("result_manifest")
        verification = attempt.get("verification")
        if state == "worker_error":
            if result_manifest is not None or verification is not None:
                raise EvidenceReportError(
                    f"attempt {attempt_id} worker_error must not claim result/verification evidence"
                )
            continue

        if result_manifest is None:
            if state != "result_manifest_error":
                raise EvidenceReportError(
                    f"attempt {attempt_id} has no ResultManifest outside result_manifest_error"
                )
            if verification is not None:
                raise EvidenceReportError(
                    f"attempt {attempt_id} cannot have verification without a ResultManifest"
                )
            continue

        if not isinstance(result_manifest, dict):
            raise EvidenceReportError(f"attempt {attempt_id} ResultManifest summary must be an object")
        result_digest = _require_digest(
            result_manifest.get("digest"), f"attempt {attempt_id} result_manifest.digest"
        )
        if not isinstance(result_manifest.get("id"), str) or not result_manifest["id"]:
            raise EvidenceReportError(f"attempt {attempt_id} ResultManifest id is missing")
        if not isinstance(result_manifest.get("worker_id"), str) or not result_manifest["worker_id"]:
            raise EvidenceReportError(f"attempt {attempt_id} worker id is missing")

        if state == "result_manifest_error":
            raise EvidenceReportError(
                f"attempt {attempt_id} result_manifest_error cannot contain a parsed ResultManifest"
            )
        if state == "verification_error":
            if verification is not None:
                raise EvidenceReportError(
                    f"attempt {attempt_id} verification_error must not claim a VerificationResult"
                )
            continue

        if state != "verified" or not isinstance(verification, dict):
            raise EvidenceReportError(
                f"attempt {attempt_id} verified state requires independent verification evidence"
            )
        recommendation = verification.get("recommendation")
        if recommendation not in KNOWN_RECOMMENDATIONS:
            raise EvidenceReportError(
                f"attempt {attempt_id} has unsupported verifier recommendation {recommendation!r}"
            )
        _require_digest(
            verification.get("semantic_digest"),
            f"attempt {attempt_id} verification.semantic_digest",
        )
        observed_result_digest = _require_digest(
            verification.get("result_manifest_digest"),
            f"attempt {attempt_id} verification.result_manifest_digest",
        )
        observed_work_unit_digest = _require_digest(
            verification.get("work_unit_digest"),
            f"attempt {attempt_id} verification.work_unit_digest",
        )
        if observed_result_digest != result_digest:
            raise EvidenceReportError(
                f"attempt {attempt_id} verification is not bound to the summarized ResultManifest"
            )
        if observed_work_unit_digest != work_unit_digest:
            raise EvidenceReportError(
                f"attempt {attempt_id} verification is not bound to the run WorkUnit"
            )

    if len(set(attempt_ids)) != len(attempt_ids):
        raise EvidenceReportError("attempt IDs must be unique")
    if order != attempt_ids:
        raise EvidenceReportError("attempt_order must exactly match the recorded attempt sequence")


def _evidence_state(attempt: dict[str, Any]) -> str:
    if attempt["state"] in ERROR_STATES:
        return attempt["state"]
    verification = attempt.get("verification")
    if verification is None:
        return "inconclusive"
    recommendation = verification["recommendation"]
    if recommendation == "accept_candidate":
        return "supported"
    if recommendation == "reject_candidate":
        return "rejected"
    return "inconclusive"


def build_report(record: dict[str, Any]) -> dict[str, Any]:
    """Produce a deterministic run-level report without selecting a candidate."""

    validate_run_record(record)
    report_attempts: list[dict[str, Any]] = []
    recommendations: list[str] = []

    for attempt in record["attempts"]:
        result_manifest = attempt.get("result_manifest")
        verification = attempt.get("verification")
        evidence_state = _evidence_state(attempt)

        worker = None
        if result_manifest is not None:
            worker = {
                "id": result_manifest["worker_id"],
                "status": result_manifest["worker_status"],
                "result_manifest_id": result_manifest["id"],
                "result_manifest_digest": result_manifest["digest"],
            }

        verifier = None
        if verification is not None:
            recommendations.append(verification["recommendation"])
            verifier = {
                "id": verification["verifier_id"],
                "status": verification["status"],
                "recommendation": verification["recommendation"],
                "verification_semantic_digest": verification["semantic_digest"],
                "checks": deepcopy(verification["checks"]),
            }

        report_attempts.append(
            {
                "attempt_id": attempt["attempt_id"],
                "order": attempt["order"],
                "worker_adapter": attempt["worker_adapter"],
                "state": attempt["state"],
                "evidence_state": evidence_state,
                "worker": worker,
                "verifier": verifier,
                "error": attempt.get("error"),
            }
        )

    counts = Counter(attempt["evidence_state"] for attempt in report_attempts)
    verification_disagreement = len(set(recommendations)) > 1
    control_failure_present = any(attempt["state"] in ERROR_STATES for attempt in report_attempts)

    warnings = [
        "Generated evidence is decision support only; this report does not select, accept, merge, or integrate a candidate."
    ]
    if verification_disagreement:
        warnings.append(
            "Independent verification recommendations disagree; preserve the disagreement for human/governance review."
        )
    if control_failure_present:
        warnings.append(
            "At least one worker/verifier control-path failure occurred; peer evidence is preserved but the failed attempt is not silently dropped."
        )
    if not recommendations:
        warnings.append("No independent VerificationResult recommendation is present in this run.")

    report = {
        "schema_version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "run_id": record["run_id"],
        "source_run_kind": record["kind"],
        "source_run_digest": canonical_digest(record),
        "source_config_digest": record["config_digest"],
        "orchestrator_version": record["orchestrator_version"],
        "work_unit": deepcopy(record["work_unit"]),
        "verifier_policy_digest": record["verifier_policy_digest"],
        "attempts": report_attempts,
        "summary": {
            "attempt_count": len(report_attempts),
            "supported": counts["supported"],
            "rejected": counts["rejected"],
            "inconclusive": counts["inconclusive"],
            "control_errors": sum(counts[state] for state in ERROR_STATES),
            "verification_disagreement": verification_disagreement,
            "control_failure_present": control_failure_present,
        },
        "warnings": warnings,
        "human_decision": {
            "status": "pending",
            "selected_attempt_id": None,
            "integration_authority": "external_human_or_governance",
        },
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    validate_report(report, record)
    return report


def validate_report(report: dict[str, Any], source_record: dict[str, Any] | None = None) -> None:
    if report.get("schema_version") != REPORT_VERSION or report.get("kind") != REPORT_KIND:
        raise EvidenceReportError("unsupported run evidence report")
    _require_digest(report.get("source_run_digest"), "source_run_digest")
    _require_digest(report.get("source_config_digest"), "source_config_digest")
    _require_digest(report.get("verifier_policy_digest"), "verifier_policy_digest")

    attempts = report.get("attempts")
    summary = report.get("summary")
    if not isinstance(attempts, list) or not attempts or not isinstance(summary, dict):
        raise EvidenceReportError("report attempts/summary are missing")
    if summary.get("attempt_count") != len(attempts):
        raise EvidenceReportError("report attempt_count does not match attempts")

    counted = (
        int(summary.get("supported", -1))
        + int(summary.get("rejected", -1))
        + int(summary.get("inconclusive", -1))
        + int(summary.get("control_errors", -1))
    )
    if counted != len(attempts):
        raise EvidenceReportError("report evidence-state counts do not cover every attempt exactly once")

    expected_authority = {
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
        "automatic_candidate_selection": False,
    }
    if report.get("authority") != expected_authority:
        raise EvidenceReportError("run evidence report cannot carry write/select/merge authority")
    decision = report.get("human_decision")
    if decision != {
        "status": "pending",
        "selected_attempt_id": None,
        "integration_authority": "external_human_or_governance",
    }:
        raise EvidenceReportError("generated report must leave the integration decision pending")

    if source_record is not None:
        validate_run_record(source_record)
        if report["source_run_digest"] != canonical_digest(source_record):
            raise EvidenceReportError("report is not bound to the supplied source run record")
        if report["run_id"] != source_record["run_id"]:
            raise EvidenceReportError("report run_id does not match source run")
        if report["work_unit"] != source_record["work_unit"]:
            raise EvidenceReportError("report WorkUnit summary does not match source run")


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    validate_report(report)
    summary = report["summary"]
    lines = [
        "# IDKMesh Run Evidence Report",
        "",
        f"- **Run:** `{report['run_id']}`",
        f"- **Work Unit:** `{report['work_unit']['id']}` v{report['work_unit']['version']}",
        f"- **Source run digest:** `{report['source_run_digest']}`",
        f"- **Supported attempts:** {summary['supported']}",
        f"- **Rejected attempts:** {summary['rejected']}",
        f"- **Inconclusive attempts:** {summary['inconclusive']}",
        f"- **Control errors:** {summary['control_errors']}",
        f"- **Verification disagreement:** {'yes' if summary['verification_disagreement'] else 'no'}",
        "- **Human integration decision:** **pending**",
        "",
        "## Attempts",
        "",
        "| Attempt | Worker state | Worker | Verifier | Recommendation | Evidence state | Required checks |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for attempt in report["attempts"]:
        worker = attempt["worker"] or {}
        verifier = attempt["verifier"] or {}
        checks = verifier.get("checks", [])
        required_checks = ", ".join(
            f"{check['id']}={check['status']}" for check in checks if check.get("required")
        )
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    attempt["attempt_id"],
                    attempt["state"],
                    worker.get("id", "-"),
                    verifier.get("id", "-"),
                    verifier.get("recommendation", "-"),
                    attempt["evidence_state"],
                    required_checks or "-",
                )
            )
            + " |"
        )
        if attempt.get("error"):
            lines.extend(["", f"> `{attempt['attempt_id']}` error: {_md_cell(attempt['error'])}"])

    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "This generated report is a read-only aggregation of worker and verifier evidence. ",
            "It deliberately contains **no selected candidate** and cannot approve, merge, push, or modify canonical project state.",
            "",
        ]
    )
    return "\n".join(lines)


def compare_replay(config_path: Path, saved_record: dict[str, Any]) -> dict[str, Any]:
    """Replay one config and compare the complete deterministic run digest."""

    validate_run_record(saved_record)
    replayed = run_config(config_path)
    validate_run_record(replayed)
    saved_digest = canonical_digest(saved_record)
    replay_digest = canonical_digest(replayed)
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-run-replay-check",
        "run_id": saved_record["run_id"],
        "config": config_path.relative_to(Path(__file__).resolve().parents[1]).as_posix(),
        "saved_run_digest": saved_digest,
        "replayed_run_digest": replay_digest,
        "match": saved_digest == replay_digest,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def cmd_generate(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    run_output = resolve_output_path(args.run_output)
    report_json = resolve_output_path(args.report_json)
    report_markdown = resolve_output_path(args.report_markdown)
    if len({run_output, report_json, report_markdown}) != 3:
        raise EvidenceReportError("run/report output paths must be distinct")

    record = run_config(config_path)
    report = build_report(record)
    _write_json(run_output, record)
    _write_json(report_json, report)
    _write_text(report_markdown, render_markdown(report))
    print(
        f"{record['run_state']}: wrote run record, non-selecting evidence JSON, and Markdown report under results/"
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    run_record_path = resolve_repo_path(args.run_record)
    report_json = resolve_output_path(args.report_json)
    report_markdown = resolve_output_path(args.report_markdown)
    if report_json == report_markdown:
        raise EvidenceReportError("JSON and Markdown report outputs must be distinct")
    record = load_json(run_record_path)
    report = build_report(record)
    _write_json(report_json, report)
    _write_text(report_markdown, render_markdown(report))
    print(f"wrote evidence report for {record['run_id']}")
    return 0


def cmd_replay_check(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    run_record_path = resolve_repo_path(args.run_record)
    result = compare_replay(config_path, load_json(run_record_path))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["match"] else 1


def cmd_self_test(_: argparse.Namespace) -> int:
    comparison_path = resolve_repo_path("examples/orchestration/two-attempt-good-vs-bad.json")
    failure_path = resolve_repo_path("examples/orchestration/two-attempt-worker-failure.json")

    record = run_config(comparison_path)
    report = build_report(record)
    if report["summary"]["supported"] != 1 or report["summary"]["rejected"] != 1:
        raise EvidenceReportError("good-vs-bad report did not preserve one support and one rejection")
    if not report["summary"]["verification_disagreement"]:
        raise EvidenceReportError("support/reject disagreement was not surfaced")
    if report["human_decision"]["selected_attempt_id"] is not None:
        raise EvidenceReportError("generated report selected a candidate")
    if report["authority"]["automatic_candidate_selection"]:
        raise EvidenceReportError("generated report gained automatic selection authority")

    markdown = render_markdown(report)
    for required_text in (
        "attempt-001",
        "attempt-002",
        "accept_candidate",
        "reject_candidate",
        "Human integration decision:** **pending",
    ):
        if required_text not in markdown:
            raise EvidenceReportError(f"Markdown report omitted {required_text!r}")

    failure_report = build_report(run_config(failure_path))
    if failure_report["summary"]["control_errors"] != 1:
        raise EvidenceReportError("worker failure was not retained in the run evidence report")
    if failure_report["summary"]["supported"] != 1:
        raise EvidenceReportError("peer worker failure erased surviving supported evidence")

    replay = compare_replay(comparison_path, record)
    if not replay["match"]:
        raise EvidenceReportError("same config did not replay to the same complete run digest")
    tampered_replay = deepcopy(record)
    tampered_replay["run_id"] += "-tampered"
    if compare_replay(comparison_path, tampered_replay)["match"]:
        raise EvidenceReportError("tampered saved run unexpectedly passed replay equality")

    inconsistent = deepcopy(record)
    inconsistent["attempts"][0]["result_manifest"]["digest"] = "sha256:" + "0" * 64
    try:
        build_report(inconsistent)
    except EvidenceReportError:
        pass
    else:
        raise EvidenceReportError(
            "report accepted ResultManifest/VerificationResult digest binding drift"
        )

    print(
        "OK: run evidence report preserves support/reject/error/disagreement, binds verifier evidence "
        "to exact WorkUnit/ResultManifest digests, leaves human integration pending, and replay detects "
        "saved-run drift without gaining selection/write/merge authority"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser("self-test", help="Exercise evidence and replay invariants.")
    self_test.set_defaults(func=cmd_self_test)

    generate = subparsers.add_parser(
        "generate", help="Run one orchestration config and emit run + evidence artifacts."
    )
    generate.add_argument("--config", required=True)
    generate.add_argument("--run-output", required=True, help="Repository-relative path under results/.")
    generate.add_argument("--report-json", required=True, help="Repository-relative path under results/.")
    generate.add_argument("--report-markdown", required=True, help="Repository-relative path under results/.")
    generate.set_defaults(func=cmd_generate)

    report = subparsers.add_parser("report", help="Render a saved orchestration run record.")
    report.add_argument("--run-record", required=True)
    report.add_argument("--report-json", required=True, help="Repository-relative path under results/.")
    report.add_argument("--report-markdown", required=True, help="Repository-relative path under results/.")
    report.set_defaults(func=cmd_report)

    replay = subparsers.add_parser(
        "replay-check", help="Re-run a config and compare the complete deterministic run digest."
    )
    replay.add_argument("--config", required=True)
    replay.add_argument("--run-record", required=True)
    replay.set_defaults(func=cmd_replay_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (
        EvidenceReportError,
        OrchestratorError,
        VerifierError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
