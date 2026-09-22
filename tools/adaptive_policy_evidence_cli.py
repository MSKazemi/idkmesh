#!/usr/bin/env python3
"""CLI for capturing adaptive-policy shadow evidence without executing policy actions.

The CLI has three commands:

plan     Build and print a frozen shadow plan from a JSON request.
outcome  Join an observed real-process outcome to a frozen plan.
cohort   Summarize frozen plans plus later outcomes descriptively.

It writes only the requested output file (or stdout). It never dispatches work,
executes a recommendation, mutates GitHub, approves, merges, or authorizes spend.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

try:
    from tools.adaptive_policy_cohort import (
        AdaptivePolicyCohortError,
        summarize_cohort,
    )
    from tools.adaptive_policy_outcome import (
        AdaptivePolicyOutcomeError,
        build_outcome_record,
    )
    from tools.adaptive_policy_shadow import (
        AdaptivePolicyPlanError,
        build_shadow_plan,
    )
except ModuleNotFoundError:  # direct: python tools/adaptive_policy_evidence_cli.py
    from adaptive_policy_cohort import (
        AdaptivePolicyCohortError,
        summarize_cohort,
    )
    from adaptive_policy_outcome import (
        AdaptivePolicyOutcomeError,
        build_outcome_record,
    )
    from adaptive_policy_shadow import (
        AdaptivePolicyPlanError,
        build_shadow_plan,
    )


class EvidenceCLIError(RuntimeError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceCLIError(f"{path}: expected a JSON object")
    return value


def write_json(value: Any, output: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(text)
        return
    path = Path(output)
    if path.exists():
        raise EvidenceCLIError(
            f"refusing to overwrite existing evidence file: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_plan_from_request(request: dict[str, Any]) -> dict[str, Any]:
    policy = request.get("policy", {})
    recommendation = request.get("recommendation", {})
    expected_cost = recommendation.get("expected_cost", {})
    return build_shadow_plan(
        repository=request["repository"],
        source_revision_sha=request["source_revision_sha"],
        subsystem=request["subsystem"],
        policy_id=policy["id"],
        policy_version=policy["version"],
        maturity=policy["maturity"],
        input_state=request["input_state"],
        input_refs=request.get("input_refs", []),
        hard_gates=request["hard_gates"],
        eligible_choices=request.get("eligible_choices", []),
        selected_choice_id=recommendation.get("selected_choice_id"),
        baseline_choice_id=recommendation.get("baseline_choice_id"),
        selection_reasons=recommendation.get("reasons", []),
        exploration=bool(recommendation.get("exploration", False)),
        uncertainty=recommendation.get("uncertainty"),
        compute_units=expected_cost.get("compute_units"),
        review_units=expected_cost.get("review_units"),
        human_attention_units=expected_cost.get(
            "human_attention_units"
        ),
        evidence_refs=request.get("evidence_refs", []),
        limitations=request["limitations"],
    )


def build_outcome_from_request(
    plan: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    actual_cost = observation.get("actual_cost", {})
    return build_outcome_record(
        plan=plan,
        actual_choice_id=observation.get("actual_choice_id"),
        outcome=observation["outcome"],
        verified_utility=observation.get("verified_utility"),
        escaped_defect=observation.get("escaped_defect"),
        high_risk_escape=observation.get("high_risk_escape"),
        project_spend_usd=actual_cost.get("project_spend_usd"),
        compute_units=actual_cost.get("compute_units"),
        review_units=actual_cost.get("review_units"),
        human_attention_units=actual_cost.get(
            "human_attention_units"
        ),
        evidence_refs=observation.get("evidence_refs", []),
        limitations=observation["limitations"],
    )


def cmd_plan(args: argparse.Namespace) -> int:
    request = load_json(args.request)
    plan = build_plan_from_request(request)
    write_json(plan, args.output)
    return 0


def cmd_outcome(args: argparse.Namespace) -> int:
    plan = load_json(args.plan)
    observation = load_json(args.observation)
    outcome = build_outcome_from_request(plan, observation)
    write_json(outcome, args.output)
    return 0


def _load_many(paths: Sequence[str]) -> list[dict[str, Any]]:
    return [load_json(path) for path in paths]


def cmd_cohort(args: argparse.Namespace) -> int:
    request = load_json(args.request)
    plan_paths = request.get("plans", [])
    outcome_paths = request.get("outcomes", [])
    if not isinstance(plan_paths, list) or not all(
        isinstance(path, str) and path for path in plan_paths
    ):
        raise EvidenceCLIError("cohort.plans must be a list of paths")
    if not isinstance(outcome_paths, list) or not all(
        isinstance(path, str) and path for path in outcome_paths
    ):
        raise EvidenceCLIError(
            "cohort.outcomes must be a list of paths"
        )
    limitations = request.get("limitations", [])
    summary = summarize_cohort(
        plans=_load_many(plan_paths),
        outcomes=_load_many(outcome_paths),
        limitations=limitations,
    )
    write_json(summary, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--request", required=True)
    plan.add_argument("--output")
    plan.set_defaults(func=cmd_plan)

    outcome = sub.add_parser("outcome")
    outcome.add_argument("--plan", required=True)
    outcome.add_argument("--observation", required=True)
    outcome.add_argument("--output")
    outcome.set_defaults(func=cmd_outcome)

    cohort = sub.add_parser("cohort")
    cohort.add_argument("--request", required=True)
    cohort.add_argument("--output")
    cohort.set_defaults(func=cmd_cohort)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (
        OSError,
        KeyError,
        json.JSONDecodeError,
        EvidenceCLIError,
        AdaptivePolicyPlanError,
        AdaptivePolicyOutcomeError,
        AdaptivePolicyCohortError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
