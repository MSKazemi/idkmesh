#!/usr/bin/env python3
"""Record an accountable human integration decision against one Run Evidence Report.

``experiments/run_evidence_report.py`` already renders a machine-suggested
recommendation inside every generated report's ``human_decision`` object --
a ``selected_attempt_id`` and a recommendation from
``{accept_candidate, reject_candidate, escalate, insufficient_evidence}``.
That object is read-only decision support: nothing in the pipeline lets a
human actually *record* their own decision -- who decided, what they
decided, when, and why -- back into a persisted, evidenced artifact.

This module closes that gap without granting any new authority. It:

* validates the referenced evidence report is a well-formed, non-selecting
  ``idkmesh-run-evidence-report`` before a decision can be recorded against it;
* requires an explicit human decision from ``{accept, reject, escalate}`` --
  a distinct vocabulary from the machine recommendation, so recording a
  decision is never satisfied by echoing the advisory recommendation;
* binds the decision to the evidence report by content digest
  (``provenance_integrity.canonical_digest``), not by filename, so a
  swapped or corrupted evidence report is detectable before the decision
  record is trusted;
* writes a companion ``idkmesh-human-decision-record`` document under
  ``results/`` and never mutates the evidence report it decides on.

The written record itself carries no canonical-state-write, git-push, or
merge authority: it documents that a decision was made, it does not execute it.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from local_verifier import VerifierError, load_json, resolve_repo_path, utc_now, validate_schema
from provenance_integrity import canonical_digest
from run_evidence_report import EvidenceReportError, resolve_output_path, validate_report

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "human-decision-record-v0.1.schema.json"
RECORD_VERSION = "0.1"
RECORD_KIND = "idkmesh-human-decision-record"
KNOWN_DECISIONS = {"accept", "reject", "escalate"}
KNOWN_DECIDER_TYPES = {"human", "governance_body"}


class HumanDecisionError(RuntimeError):
    """Raised when a decision cannot be validly recorded or verified."""


def _load_evidence_report(path: Path) -> dict[str, Any]:
    report = load_json(path)
    try:
        validate_report(report)
    except EvidenceReportError as exc:
        raise HumanDecisionError(f"{path} is not a valid run evidence report: {exc}") from exc
    return report


def _require_known_attempt(report: dict[str, Any], selected_attempt_id: str | None) -> None:
    if selected_attempt_id is None:
        return
    attempt_ids = {attempt["attempt_id"] for attempt in report["attempts"]}
    if selected_attempt_id not in attempt_ids:
        raise HumanDecisionError(
            f"selected_attempt_id {selected_attempt_id!r} is not an attempt in this evidence report "
            f"(known attempt ids: {sorted(attempt_ids)})"
        )


def build_decision_record(
    *,
    report: dict[str, Any],
    decision_id: str,
    decision: str,
    rationale: str,
    decider_id: str,
    decider_type: str,
    decider_display_name: str | None,
    selected_attempt_id: str | None,
    decided_at: str,
) -> dict[str, Any]:
    """Build and schema-validate one human decision record for ``report``."""

    if decision not in KNOWN_DECISIONS:
        raise HumanDecisionError(
            f"decision must be one of {sorted(KNOWN_DECISIONS)}, got {decision!r}"
        )
    if decider_type not in KNOWN_DECIDER_TYPES:
        raise HumanDecisionError(
            f"decider type must be one of {sorted(KNOWN_DECIDER_TYPES)}, got {decider_type!r}"
        )
    if not rationale.strip():
        raise HumanDecisionError("rationale must not be empty")
    if not decider_id.strip():
        raise HumanDecisionError("decider id must not be empty")

    _require_known_attempt(report, selected_attempt_id)

    decider: dict[str, Any] = {"id": decider_id, "type": decider_type}
    if decider_display_name:
        decider["display_name"] = decider_display_name

    record = {
        "schema_version": RECORD_VERSION,
        "kind": RECORD_KIND,
        "decision_id": decision_id,
        "evidence_report": {
            "kind": report["kind"],
            "schema_version": report["schema_version"],
            "run_id": report["run_id"],
            "digest": canonical_digest(report),
        },
        "selected_attempt_id": selected_attempt_id,
        "decision": decision,
        "rationale": rationale,
        "decider": decider,
        "decided_at": decided_at,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        },
    }
    validate_decision_record(record)
    return record


def validate_decision_record(record: dict[str, Any]) -> None:
    """Schema-validate a human decision record document."""

    try:
        validate_schema(record, SCHEMA_PATH, "human decision record")
    except VerifierError as exc:
        raise HumanDecisionError(str(exc)) from exc


def verify_binding(record: dict[str, Any], report: dict[str, Any]) -> None:
    """Fail closed if a decision record's digest no longer matches its report.

    This is the actual security-relevant property of this contract: a
    decision record is only meaningful evidence if it is verified against
    the *exact* evidence report it names, by content, not by trusting that
    whatever file currently sits at a given path is the same report a human
    once reviewed.
    """

    validate_decision_record(record)
    try:
        validate_report(report)
    except EvidenceReportError as exc:
        raise HumanDecisionError(f"referenced evidence report is not valid: {exc}") from exc

    observed_digest = canonical_digest(report)
    if record["evidence_report"]["digest"] != observed_digest:
        raise HumanDecisionError(
            "decision record is not bound to the supplied evidence report: digest mismatch "
            f"(record expects {record['evidence_report']['digest']}, supplied report is {observed_digest}); "
            "the evidence report may have been swapped, edited, or corrupted after the decision was recorded"
        )
    if record["evidence_report"]["run_id"] != report["run_id"]:
        raise HumanDecisionError("decision record run_id does not match the supplied evidence report")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_record(args: argparse.Namespace) -> int:
    report_path = resolve_repo_path(args.evidence_report)
    output_path = resolve_output_path(args.output)
    if output_path.resolve() == report_path.resolve():
        raise HumanDecisionError(
            "decision record output must not overwrite the evidence report it decides on"
        )

    report = _load_evidence_report(report_path)
    record = build_decision_record(
        report=report,
        decision_id=args.decision_id,
        decision=args.decision,
        rationale=args.rationale,
        decider_id=args.decider_id,
        decider_type=args.decider_type,
        decider_display_name=args.decider_display_name,
        selected_attempt_id=args.selected_attempt_id,
        decided_at=args.decided_at or utc_now(),
    )
    _write_json(output_path, record)
    print(
        f"recorded {record['decision']} decision {record['decision_id']!r} for run "
        f"{report['run_id']!r} (evidence_report_digest={record['evidence_report']['digest']})"
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    record = load_json(resolve_repo_path(args.decision_record))
    report = load_json(resolve_repo_path(args.evidence_report))
    verify_binding(record, report)
    print(
        f"OK: decision record {record['decision_id']!r} is bound to evidence report "
        f"{record['evidence_report']['run_id']!r} (digest={record['evidence_report']['digest']})"
    )
    return 0


def cmd_self_test(_: argparse.Namespace) -> int:
    from run_evidence_report import build_report
    from two_attempt_orchestrator import run_config

    config_path = resolve_repo_path("examples/orchestration/two-attempt-good-vs-bad.json")
    run_record = run_config(config_path)
    report = build_report(run_record)

    decision = build_decision_record(
        report=report,
        decision_id="self-test.decision.001",
        decision="accept",
        rationale="self-test: attempt-001 was independently verified as accept_candidate.",
        decider_id="self-test-reviewer",
        decider_type="human",
        decider_display_name="Self-Test Reviewer",
        selected_attempt_id=report["attempts"][0]["attempt_id"],
        decided_at="2026-01-01T00:00:00Z",
    )
    verify_binding(decision, report)

    tampered_report = deepcopy(report)
    tampered_report["run_id"] += "-tampered"
    try:
        verify_binding(decision, tampered_report)
    except HumanDecisionError:
        pass
    else:
        raise HumanDecisionError("decision record did not detect a swapped/tampered evidence report")

    try:
        build_decision_record(
            report=report,
            decision_id="self-test.decision.002",
            decision="accept",
            rationale="x",
            decider_id="self-test-reviewer",
            decider_type="human",
            decider_display_name=None,
            selected_attempt_id="attempt-does-not-exist",
            decided_at="2026-01-01T00:00:00Z",
        )
    except HumanDecisionError:
        pass
    else:
        raise HumanDecisionError("decision record accepted an attempt_id absent from the evidence report")

    try:
        build_decision_record(
            report=report,
            decision_id="self-test.decision.003",
            decision="accept_candidate",
            rationale="x",
            decider_id="self-test-reviewer",
            decider_type="human",
            decider_display_name=None,
            selected_attempt_id=None,
            decided_at="2026-01-01T00:00:00Z",
        )
    except HumanDecisionError:
        pass
    else:
        raise HumanDecisionError(
            "decision record accepted a machine-recommendation value instead of an explicit human decision"
        )

    print(
        "OK: human decision record binds to the exact evidence-report digest, rejects an "
        "out-of-report attempt selection and a machine-recommendation-shaped decision value, "
        "and detects a swapped/tampered evidence report at verify time"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser("self-test", help="Exercise decision-recording and binding invariants.")
    self_test.set_defaults(func=cmd_self_test)

    record = subparsers.add_parser(
        "record", help="Record one human integration decision against an existing evidence report."
    )
    record.add_argument("--evidence-report", required=True, help="Repository-relative path to an existing run evidence report.")
    record.add_argument("--output", required=True, help="Repository-relative path under results/ for the new decision record.")
    record.add_argument("--decision-id", required=True, help="Stable id for this decision record, e.g. run-id.decision.001.")
    record.add_argument("--decision", required=True, choices=sorted(KNOWN_DECISIONS))
    record.add_argument("--rationale", required=True, help="Free-text explanation of why this decision was made.")
    record.add_argument("--decider-id", required=True, help="Stable identity of the person or body deciding.")
    record.add_argument("--decider-type", default="human", choices=sorted(KNOWN_DECIDER_TYPES))
    record.add_argument("--decider-display-name", default=None)
    record.add_argument(
        "--selected-attempt-id",
        default=None,
        help="attempt_id from the evidence report this decision concerns, or omit for a run-level decision.",
    )
    record.add_argument(
        "--decided-at",
        default=None,
        help="ISO-8601 UTC timestamp; defaults to the current time when omitted.",
    )
    record.set_defaults(func=cmd_record)

    verify = subparsers.add_parser(
        "verify", help="Verify a decision record is still bound to the exact evidence report it names."
    )
    verify.add_argument("--decision-record", required=True)
    verify.add_argument("--evidence-report", required=True)
    verify.set_defaults(func=cmd_verify)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (
        HumanDecisionError,
        EvidenceReportError,
        VerifierError,
        OSError,
        json.JSONDecodeError,
        ValueError,
        KeyError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
