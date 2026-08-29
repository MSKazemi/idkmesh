"""Fail-closed readiness audit for a real R1 replay corpus.

This module deliberately does not change :mod:`randomness_lab.r1_replay`.
It checks whether a BenchmarkCohort can be handed to that frozen analysis
without quietly weakening the preregistered real-evidence requirements.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

from randomness_lab.r1_replay import ReplayCandidate, normalize_replay_candidates


@dataclass(frozen=True)
class ReadinessConfig:
    baseline_signature: str
    diversity_signatures: tuple[str, ...]
    swarm_size: int = 2
    minimum_eligible_work_units: int = 20
    require_independent_tests: bool = True
    require_complete_costs: bool = True

    def __post_init__(self) -> None:
        if self.swarm_size < 2:
            raise ValueError("swarm_size must be >= 2")
        if self.minimum_eligible_work_units < 1:
            raise ValueError("minimum_eligible_work_units must be >= 1")
        if len(self.diversity_signatures) != self.swarm_size:
            raise ValueError("diversity_signatures must contain exactly swarm_size entries")
        if len(set(self.diversity_signatures)) != len(self.diversity_signatures):
            raise ValueError("diversity_signatures must be distinct")
        if self.baseline_signature not in self.diversity_signatures:
            raise ValueError("the baseline signature must be one diversity-arm signature")


def _condition(code: str, passed: bool, observed: Any, required: Any) -> dict[str, Any]:
    return {
        "code": code,
        "passed": passed,
        "observed": observed,
        "required": required,
    }


def _expected_signature_counts(config: ReadinessConfig) -> dict[str, int]:
    counts = {signature: 1 for signature in config.diversity_signatures}
    counts[config.baseline_signature] = config.swarm_size
    return counts


def assess_cohort_readiness(
    cohort: dict[str, Any],
    candidates: Sequence[ReplayCandidate],
    normalization: dict[str, Any],
    config: ReadinessConfig,
) -> dict[str, Any]:
    """Return a deterministic audit; never infer that a scaffold is real evidence."""

    expected_counts = _expected_signature_counts(config)
    candidates_by_result = {candidate.result_manifest_id: candidate for candidate in candidates}
    global_conditions = [
        _condition(
            "frozen_or_burned_cohort",
            cohort.get("stage") in {"frozen", "burned"},
            cohort.get("stage"),
            ["frozen", "burned"],
        ),
        _condition(
            "definition_digest_committed",
            isinstance(cohort.get("definition_digest"), str),
            cohort.get("definition_digest"),
            "sha256 commitment present before analyzed outcomes",
        ),
        _condition(
            "taxonomy_frozen_before_outcomes",
            cohort.get("taxonomy_frozen_before_outcomes") is True,
            cohort.get("taxonomy_frozen_before_outcomes"),
            True,
        ),
        _condition(
            "prospective_minimum_target",
            cohort.get("minimum_final_tasks", 0) >= config.minimum_eligible_work_units,
            cohort.get("minimum_final_tasks"),
            config.minimum_eligible_work_units,
        ),
        _condition(
            "non_selecting_authority",
            all(value is False for value in cohort.get("authority", {}).values())
            and set(cohort.get("authority", {}))
            == {"canonical_state_write", "git_push", "merge", "automatic_candidate_selection"},
            cohort.get("authority"),
            "all four authority capabilities false",
        ),
        _condition(
            "normalization_has_no_dropped_candidates",
            sum(normalization.get("excluded", {}).values()) == 0
            and normalization.get("unknown_verification_result_references", 0) == 0,
            {
                "excluded": normalization.get("excluded", {}),
                "unknown_verification_result_references": normalization.get(
                    "unknown_verification_result_references", 0
                ),
            },
            "zero excluded candidates and zero unknown verification references",
        ),
    ]

    task_reports: list[dict[str, Any]] = []
    outcome_counts: Counter[str] = Counter()
    signature_work_units: dict[str, set[str]] = defaultdict(set)

    for task in sorted(cohort.get("tasks", []), key=lambda item: item.get("id", "")):
        evidence = task.get("evidence", {})
        attempts = evidence.get("attempts", [])
        observed_counts = Counter(
            attempt.get("structural_signature") for attempt in attempts
        )
        reasons: list[str] = []

        if task.get("split") != "held_out":
            reasons.append("not_held_out")
        if task.get("_validated_work_unit_kind") != "coding":
            reasons.append("work_unit_is_not_coding")
        if evidence.get("status") != "verified":
            reasons.append("evidence_not_verified")
        if task.get("negative_case", {}).get("evidence_status") != "verified":
            reasons.append("seeded_negative_not_verified")
        if not set(expected_counts).issubset(set(task.get("declared_structural_signatures", []))):
            reasons.append("analysis_signatures_not_predeclared")
        if dict(observed_counts) != expected_counts:
            reasons.append("unequal_or_unexpected_signature_budget")

        required_metrics = set(task.get("accounting", {}).get("required_metrics", []))
        if config.require_complete_costs and not {
            "wall_seconds",
            "compute_units",
            "human_minutes",
        }.issubset(required_metrics):
            reasons.append("cost_metrics_not_predeclared")

        seen_result_ids: set[str] = set()
        for attempt in attempts:
            result_id = attempt.get("result_manifest", {}).get("id")
            if isinstance(result_id, str):
                seen_result_ids.add(result_id)
            candidate = candidates_by_result.get(result_id)
            if candidate is None:
                reasons.append("attempt_not_conclusive_in_frozen_replay")
                continue
            if candidate.work_unit_id != task.get("work_unit", {}).get("id"):
                reasons.append("candidate_work_unit_mismatch")
            if candidate.structural_signature != attempt.get("structural_signature"):
                reasons.append("replay_signature_mismatch")
            if config.require_independent_tests and candidate.independent_test_pass is None:
                reasons.append("independent_test_outcome_missing")
            if config.require_complete_costs and (
                candidate.compute_units is None or candidate.human_minutes is None
            ):
                reasons.append("candidate_cost_measurement_missing")
            outcome_counts["support" if candidate.verified_good else "reject"] += 1

        if len(seen_result_ids) != len(attempts):
            reasons.append("duplicate_or_missing_result_reference")

        reasons = sorted(set(reasons))
        eligible = not reasons
        if eligible:
            for signature in expected_counts:
                signature_work_units[signature].add(task["id"])
        task_reports.append(
            {
                "task_id": task.get("id"),
                "eligible": eligible,
                "split": task.get("split"),
                "evidence_status": evidence.get("status"),
                "observed_signature_counts": dict(sorted(observed_counts.items())),
                "blockers": reasons,
            }
        )

    eligible_count = sum(report["eligible"] for report in task_reports)
    ineligible_analyzed_tasks = [
        report["task_id"]
        for report in task_reports
        if not report["eligible"]
        and (
            report["evidence_status"] == "verified"
            or bool(report["observed_signature_counts"])
        )
    ]
    global_conditions.append(
        _condition(
            "all_analyzed_tasks_eligible",
            not ineligible_analyzed_tasks,
            ineligible_analyzed_tasks,
            "no verified or attempt-bearing task may be ineligible",
        )
    )
    global_conditions.append(
        _condition(
            "minimum_eligible_work_units",
            eligible_count >= config.minimum_eligible_work_units,
            eligible_count,
            config.minimum_eligible_work_units,
        )
    )

    pair_overlap = {}
    baseline_tasks = signature_work_units.get(config.baseline_signature, set())
    for signature in config.diversity_signatures:
        if signature == config.baseline_signature:
            continue
        pair_overlap[f"{config.baseline_signature}::{signature}"] = len(
            baseline_tasks & signature_work_units.get(signature, set())
        )

    ready = all(condition["passed"] for condition in global_conditions)
    return {
        "report_kind": "r1_real_corpus_readiness_audit",
        "evidence_class": "repository_contract_state_not_coding_outcome",
        "supports_empirical_r1_claim": False,
        "status": "ready_for_frozen_replay" if ready else "blocked",
        "cohort_id": cohort.get("id"),
        "cohort_definition_digest": cohort.get("definition_digest"),
        "configuration": {
            "baseline_signature": config.baseline_signature,
            "diversity_signatures": list(config.diversity_signatures),
            "swarm_size": config.swarm_size,
            "minimum_eligible_work_units": config.minimum_eligible_work_units,
            "expected_attempt_signature_counts_per_work_unit": expected_counts,
            "require_independent_tests": config.require_independent_tests,
            "require_complete_costs": config.require_complete_costs,
        },
        "global_conditions": global_conditions,
        "coverage": {
            "cohort_tasks": len(task_reports),
            "eligible_work_units": eligible_count,
            "ineligible_work_units": len(task_reports) - eligible_count,
            "pairwise_signature_overlap": pair_overlap,
            "conclusive_outcomes": dict(sorted(outcome_counts.items())),
        },
        "normalization": normalization,
        "tasks": task_reports,
        "provenance_review_required": [
            "confirm tasks were genuinely held out",
            "confirm the definition was frozen before outcome inspection",
            "confirm no generated attempt was omitted from attached evidence",
        ],
        "interpretation": (
            "Passing this audit establishes mechanical readiness only. It does not prove that "
            "tasks were truly held out, that the temporal freeze preceded outcome inspection, "
            "that all generated attempts were retained, or that diversity helps. The cohort "
            "definition digest excludes attempts/evidence, so those claims require provenance "
            "review and the unchanged randomness_lab.r1_replay output."
        ),
    }


def _load_validated_inputs(cohort_path: str) -> tuple[dict[str, Any], list[ReplayCandidate], dict[str, Any]]:
    # Keep jsonschema out of the dependency-free analysis import path used by tests.
    from tools import benchmark_cohort

    resolved = benchmark_cohort.resolve_repo_file(cohort_path, label="BenchmarkCohort")
    cohort = benchmark_cohort.load_json(resolved)
    benchmark_cohort.validate_cohort(cohort)

    results: list[dict[str, object]] = []
    verifications: list[dict[str, object]] = []
    for task in cohort["tasks"]:
        work_unit_path = benchmark_cohort.resolve_repo_file(
            task["work_unit"]["path"], label="R1 WorkUnit"
        )
        task["_validated_work_unit_kind"] = benchmark_cohort.load_json(work_unit_path)[
            "kind"
        ]
        if task["evidence"]["status"] != "verified":
            continue
        for attempt in task["evidence"]["attempts"]:
            result_path = benchmark_cohort.resolve_repo_file(
                attempt["result_manifest"]["path"], label="R1 ResultManifest"
            )
            verification_path = benchmark_cohort.resolve_repo_file(
                attempt["verification_result"]["path"], label="R1 VerificationResult"
            )
            results.append(benchmark_cohort.load_json(result_path))
            verifications.append(benchmark_cohort.load_json(verification_path))
    candidates, normalization = normalize_replay_candidates(results, verifications)
    return cohort, candidates, normalization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, help="Repository-relative BenchmarkCohort path.")
    parser.add_argument("--baseline-signature", required=True)
    parser.add_argument(
        "--diversity-signature",
        action="append",
        dest="diversity_signatures",
        required=True,
        help="Repeat once per distinct diversity-arm signature, including the baseline.",
    )
    parser.add_argument("--swarm-size", type=int, default=2)
    parser.add_argument("--minimum-work-units", type=int, default=20)
    parser.add_argument("--allow-missing-independent-tests", action="store_true")
    parser.add_argument("--allow-missing-costs", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero when the audit is blocked; otherwise blocked reports are valid output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ReadinessConfig(
        baseline_signature=args.baseline_signature,
        diversity_signatures=tuple(args.diversity_signatures),
        swarm_size=args.swarm_size,
        minimum_eligible_work_units=args.minimum_work_units,
        require_independent_tests=not args.allow_missing_independent_tests,
        require_complete_costs=not args.allow_missing_costs,
    )
    cohort, candidates, normalization = _load_validated_inputs(args.cohort)
    report = assess_cohort_readiness(cohort, candidates, normalization, config)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 2 if args.require_ready and report["status"] != "ready_for_frozen_replay" else 0


if __name__ == "__main__":
    raise SystemExit(main())
