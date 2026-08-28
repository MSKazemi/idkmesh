#!/usr/bin/env python3
"""Join an exact-SHA shadow CI plan to observed GitHub check outcomes.

The evaluator produces evidence only. It cannot execute or suppress checks,
approve a change, write repository state, or authorize a merge.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


EVALUATOR_VERSION = "0.1"
TERMINAL_STATUS = "completed"


class CIEvaluationError(RuntimeError):
    """Raised when observation or evaluation input is incomplete or unsafe."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CIEvaluationError(f"{path}: expected a JSON object")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _reject_unknown(value: dict[str, Any], allowed: set[str], field: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise CIEvaluationError(f"{field} contains unknown fields: {', '.join(unknown)}")


def _require_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise CIEvaluationError(f"{field} must be a lowercase 40-character Git SHA")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CIEvaluationError(f"{field} must be a non-empty string")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    _reject_unknown(
        policy,
        {
            "schema_version",
            "mode",
            "required_contexts",
            "ignored_checks",
            "failure_conclusions",
            "success_conclusions",
            "check_mappings",
        },
        "policy",
    )
    if policy.get("schema_version") != "0.1" or policy.get("mode") != "shadow":
        raise CIEvaluationError("observation policy must be shadow schema_version 0.1")

    for field in ("failure_conclusions", "success_conclusions"):
        values = policy.get(field)
        if not isinstance(values, list) or not values or any(
            not isinstance(item, str) or not item for item in values
        ):
            raise CIEvaluationError(f"policy.{field} must contain strings")
        if len(set(values)) != len(values):
            raise CIEvaluationError(f"policy.{field} must be unique")
    if set(policy["failure_conclusions"]) & set(policy["success_conclusions"]):
        raise CIEvaluationError("success and failure conclusions must not overlap")

    required = policy.get("required_contexts")
    if not isinstance(required, list) or not required:
        raise CIEvaluationError("policy.required_contexts must be a non-empty list")
    required_keys: set[tuple[str, str]] = set()
    for index, context in enumerate(required):
        if not isinstance(context, dict):
            raise CIEvaluationError(f"required_contexts[{index}] must be an object")
        _reject_unknown(context, {"workflow_name", "check_name"}, f"required_contexts[{index}]")
        key = (
            _require_string(context.get("workflow_name"), f"required_contexts[{index}].workflow_name"),
            _require_string(context.get("check_name"), f"required_contexts[{index}].check_name"),
        )
        if key in required_keys:
            raise CIEvaluationError("policy.required_contexts must be unique")
        required_keys.add(key)

    ignored = policy.get("ignored_checks")
    if not isinstance(ignored, list):
        raise CIEvaluationError("policy.ignored_checks must be a list")
    for index, item in enumerate(ignored):
        if not isinstance(item, dict):
            raise CIEvaluationError(f"ignored_checks[{index}] must be an object")
        _reject_unknown(item, {"workflow_name", "check_name_pattern"}, f"ignored_checks[{index}]")
        _require_string(item.get("workflow_name"), f"ignored_checks[{index}].workflow_name")
        _require_string(item.get("check_name_pattern"), f"ignored_checks[{index}].check_name_pattern")

    mappings = policy.get("check_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise CIEvaluationError("policy.check_mappings must be a non-empty list")
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise CIEvaluationError(f"check_mappings[{index}] must be an object")
        _reject_unknown(
            mapping,
            {"logical_check_id", "workflow_name", "check_name_patterns"},
            f"check_mappings[{index}]",
        )
        _require_string(mapping.get("logical_check_id"), f"check_mappings[{index}].logical_check_id")
        _require_string(mapping.get("workflow_name"), f"check_mappings[{index}].workflow_name")
        patterns = mapping.get("check_name_patterns")
        if not isinstance(patterns, list) or not patterns or any(
            not isinstance(pattern, str) or not pattern for pattern in patterns
        ):
            raise CIEvaluationError(f"check_mappings[{index}].check_name_patterns must contain strings")


def _raw_array(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = payload.get(key)
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        raise CIEvaluationError(f"GitHub payload must contain a {key} array")
    return values


def _ignored(workflow_name: str | None, check_name: str, policy: dict[str, Any]) -> bool:
    return any(
        workflow_name == item["workflow_name"]
        and fnmatch.fnmatchcase(check_name, item["check_name_pattern"])
        for item in policy["ignored_checks"]
    )


def collect_observation(
    *,
    check_runs_payload: dict[str, Any],
    workflow_runs_payload: dict[str, Any],
    head_sha: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)
    _require_sha(head_sha, "head_sha")

    workflow_by_suite: dict[int, str] = {}
    for index, run in enumerate(_raw_array(workflow_runs_payload, "workflow_runs")):
        if run.get("head_sha") != head_sha:
            continue
        suite_id = run.get("check_suite_id")
        name = run.get("name")
        if isinstance(suite_id, int) and not isinstance(suite_id, bool) and isinstance(name, str) and name:
            workflow_by_suite[suite_id] = name

    latest: dict[tuple[str | None, str, str], dict[str, Any]] = {}
    for index, run in enumerate(_raw_array(check_runs_payload, "check_runs")):
        run_id = run.get("id")
        name = run.get("name")
        status = run.get("status")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 0:
            raise CIEvaluationError(f"check_runs[{index}].id must be a non-negative integer")
        _require_string(name, f"check_runs[{index}].name")
        _require_string(status, f"check_runs[{index}].status")
        suite = run.get("check_suite")
        if isinstance(suite, dict):
            suite_head = suite.get("head_sha")
            if suite_head is not None and suite_head != head_sha:
                raise CIEvaluationError(f"check_runs[{index}] is not bound to head_sha")
            suite_id = suite.get("id")
        else:
            suite_id = None
        workflow_name = workflow_by_suite.get(suite_id) if isinstance(suite_id, int) else None
        app = run.get("app")
        app_slug = app.get("slug") if isinstance(app, dict) else None
        if not isinstance(app_slug, str) or not app_slug:
            app_slug = "unknown"
        if _ignored(workflow_name, name, policy):
            continue
        conclusion = run.get("conclusion")
        if conclusion is not None and not isinstance(conclusion, str):
            raise CIEvaluationError(f"check_runs[{index}].conclusion must be a string or null")
        normalized = {
            "check_run_id": run_id,
            "workflow_name": workflow_name,
            "name": name,
            "app_slug": app_slug,
            "status": status,
            "conclusion": conclusion,
            "started_at": run.get("started_at") if isinstance(run.get("started_at"), str) else None,
            "completed_at": run.get("completed_at") if isinstance(run.get("completed_at"), str) else None,
            "details_url": run.get("details_url") if isinstance(run.get("details_url"), str) else None,
        }
        key = (workflow_name, name, app_slug)
        if key not in latest or run_id > latest[key]["check_run_id"]:
            latest[key] = normalized

    checks = sorted(
        latest.values(),
        key=lambda item: (item["workflow_name"] or "", item["name"], item["app_slug"]),
    )
    required_results: list[dict[str, Any]] = []
    successes = set(policy["success_conclusions"])
    for context in policy["required_contexts"]:
        matches = [
            check
            for check in checks
            if check["workflow_name"] == context["workflow_name"]
            and check["name"] == context["check_name"]
        ]
        present = bool(matches)
        terminal = present and all(check["status"] == TERMINAL_STATUS for check in matches)
        successful = terminal and all(check["conclusion"] in successes for check in matches)
        required_results.append({**context, "present": present, "terminal": terminal, "successful": successful})

    pending_count = sum(check["status"] != TERMINAL_STATUS for check in checks)
    baseline_complete = all(item["present"] and item["terminal"] for item in required_results)
    observation = {
        "schema_version": "0.1",
        "kind": "idkmesh-ci-observation",
        "evaluator_version": EVALUATOR_VERSION,
        "source": "github-check-runs",
        "head_sha": head_sha,
        "policy_digest": sha256_digest(policy),
        "checks": checks,
        "completeness": {
            "baseline_complete": baseline_complete,
            "baseline_successful": baseline_complete and all(item["successful"] for item in required_results),
            "pending_observed_checks": pending_count,
            "required_contexts": required_results,
        },
        "authority": {
            "evidence_only": True,
            "execute": False,
            "skip_required_checks": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
        },
    }
    return observation


def _validate_authority(value: Any, *, advisory_key: str) -> None:
    expected = {
        advisory_key: True,
        "execute": False,
        "skip_required_checks": False,
        "approve": False,
        "merge": False,
        "repository_write": False,
    }
    if value != expected:
        raise CIEvaluationError("input authority block crossed the shadow boundary")


def _mapped_logical_ids(check: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    return sorted(
        {
            mapping["logical_check_id"]
            for mapping in policy["check_mappings"]
            if check["workflow_name"] == mapping["workflow_name"]
            and any(fnmatch.fnmatchcase(check["name"], pattern) for pattern in mapping["check_name_patterns"])
        }
    )


def evaluate(
    *,
    plan: dict[str, Any],
    receipt: dict[str, Any],
    observation: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)
    if plan.get("kind") != "idkmesh-ci-plan" or plan.get("mode") != "shadow":
        raise CIEvaluationError("plan must be an idkmesh shadow CI plan")
    if receipt.get("kind") != "idkmesh-ci-receipt" or receipt.get("stage") != "planning":
        raise CIEvaluationError("receipt must be an idkmesh planning receipt")
    if observation.get("kind") != "idkmesh-ci-observation":
        raise CIEvaluationError("observation kind is invalid")
    _validate_authority(plan.get("authority"), advisory_key="advisory_only")
    _validate_authority(receipt.get("authority"), advisory_key="evidence_only")
    _validate_authority(observation.get("authority"), advisory_key="evidence_only")

    head_sha = _require_sha(plan.get("head_sha"), "plan.head_sha")
    if receipt.get("head_sha") != head_sha or observation.get("head_sha") != head_sha:
        raise CIEvaluationError("plan, receipt, and observation head_sha values must match")
    if receipt.get("plan_id") != plan.get("plan_id"):
        raise CIEvaluationError("receipt plan_id does not match the plan")
    plan_digest = sha256_digest(plan)
    if receipt.get("plan_digest") != plan_digest:
        raise CIEvaluationError("receipt plan_digest does not match the plan")
    if observation.get("policy_digest") != sha256_digest(policy):
        raise CIEvaluationError("observation policy_digest does not match the policy")
    if receipt.get("executed_checks") != []:
        raise CIEvaluationError("planning receipt must not claim executed checks")

    checks = plan.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CIEvaluationError("plan.checks must be a non-empty list")
    logical: dict[str, dict[str, Any]] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise CIEvaluationError(f"plan.checks[{index}] must be an object")
        check_id = _require_string(check.get("id"), f"plan.checks[{index}].id")
        if check_id in logical:
            raise CIEvaluationError("plan check IDs must be unique")
        if not isinstance(check.get("selected"), bool):
            raise CIEvaluationError(f"plan.checks[{index}].selected must be Boolean")
        seconds = check.get("estimated_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
            raise CIEvaluationError(f"plan.checks[{index}].estimated_seconds must be non-negative")
        logical[check_id] = check
    unknown_mappings = sorted(
        {mapping["logical_check_id"] for mapping in policy["check_mappings"]} - set(logical)
    )
    if unknown_mappings:
        raise CIEvaluationError(f"policy maps unknown logical checks: {', '.join(unknown_mappings)}")

    observed = observation.get("checks")
    completeness = observation.get("completeness")
    if not isinstance(observed, list) or not isinstance(completeness, dict):
        raise CIEvaluationError("observation checks or completeness block is invalid")
    if not isinstance(completeness.get("baseline_complete"), bool):
        raise CIEvaluationError("observation baseline_complete must be Boolean")
    selected = {check_id for check_id, check in logical.items() if check["selected"]}
    failures: list[dict[str, Any]] = []
    failure_conclusions = set(policy["failure_conclusions"])
    for index, check in enumerate(observed):
        if not isinstance(check, dict):
            raise CIEvaluationError(f"observation.checks[{index}] must be an object")
        if check.get("status") != TERMINAL_STATUS or check.get("conclusion") not in failure_conclusions:
            continue
        mapped = _mapped_logical_ids(check, policy)
        covered = sorted(set(mapped) & selected)
        failures.append(
            {
                "check_run_id": check.get("check_run_id"),
                "workflow_name": check.get("workflow_name"),
                "name": check.get("name"),
                "conclusion": check.get("conclusion"),
                "mapped_logical_check_ids": mapped,
                "covered_by_selected": covered,
            }
        )

    mapped_failures = [failure for failure in failures if failure["mapped_logical_check_ids"]]
    missed = [failure for failure in mapped_failures if not failure["covered_by_selected"]]
    unattributed = [failure for failure in failures if not failure["mapped_logical_check_ids"]]
    covered_count = len(mapped_failures) - len(missed)
    recall = covered_count / len(mapped_failures) if mapped_failures else None
    full_seconds = sum(check["estimated_seconds"] for check in logical.values())
    selected_seconds = sum(check["estimated_seconds"] for check in logical.values() if check["selected"])
    avoided_seconds = full_seconds - selected_seconds
    reasons = ["shadow_mode", "single_observation_not_a_cohort"]
    if not completeness["baseline_complete"]:
        reasons.append("required_baseline_incomplete")
    if missed:
        reasons.append("mapped_failure_missed")
    if unattributed:
        reasons.append("failure_attribution_incomplete")

    evaluation_core = {
        "schema_version": "0.1",
        "kind": "idkmesh-ci-evaluation",
        "evaluator_version": EVALUATOR_VERSION,
        "mode": "shadow",
        "head_sha": head_sha,
        "plan_id": plan["plan_id"],
        "plan_digest": plan_digest,
        "observation_digest": sha256_digest(observation),
        "policy_digest": sha256_digest(policy),
        "status": "complete" if completeness["baseline_complete"] else "provisional",
        "selected_logical_checks": sorted(selected),
        "failed_checks": failures,
        "missed_mapped_failures": missed,
        "unattributed_failures": unattributed,
        "metrics": {
            "observed_check_count": len(observed),
            "observed_failure_count": len(failures),
            "mapped_failure_count": len(mapped_failures),
            "covered_mapped_failure_count": covered_count,
            "missed_mapped_failure_count": len(missed),
            "unattributed_failure_count": len(unattributed),
            "mapped_failure_recall": recall,
            "modeled_full_portfolio_seconds": full_seconds,
            "modeled_selected_seconds": selected_seconds,
            "modeled_avoided_seconds": avoided_seconds,
            "modeled_savings_ratio": avoided_seconds / full_seconds if full_seconds else 0.0,
        },
        "promotion": {"eligible": False, "reasons": reasons},
        "authority": {
            "evidence_only": True,
            "execute": False,
            "skip_required_checks": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
        },
    }
    evaluation_core["evaluation_id"] = "ci-evaluation-" + sha256_digest(evaluation_core).split(":", 1)[1][:20]
    return evaluation_core


def render_markdown(evaluation: dict[str, Any]) -> str:
    metrics = evaluation["metrics"]
    recall = metrics["mapped_failure_recall"]
    recall_text = "not applicable" if recall is None else f"{recall:.3f}"
    return "\n".join(
        [
            "# CI Shadow Outcome Evaluation",
            "",
            f"- Evaluation: `{evaluation['evaluation_id']}`",
            f"- Exact head: `{evaluation['head_sha']}`",
            f"- Status: **{evaluation['status']}**",
            f"- Observed failures: **{metrics['observed_failure_count']}**",
            f"- Missed mapped failures: **{metrics['missed_mapped_failure_count']}**",
            f"- Unattributed failures: **{metrics['unattributed_failure_count']}**",
            f"- Mapped-failure recall: **{recall_text}**",
            f"- Modeled savings: **{metrics['modeled_savings_ratio']:.1%}**",
            "- Eligible to promote selective CI: **no**",
            "- Execute/skip/approve/merge authority: **none**",
            "",
            "> Modeled seconds are planner estimates, not measured GitHub Actions usage.",
            "",
        ]
    )


def self_test(policy_path: str | Path) -> None:
    policy = load_json(policy_path)
    observation = collect_observation(
        check_runs_payload={
            "check_runs": [
                {
                    "id": 10,
                    "name": "gate (3.11)",
                    "status": "completed",
                    "conclusion": "success",
                    "check_suite": {"id": 1, "head_sha": "2" * 40},
                    "app": {"slug": "github-actions"},
                },
                {
                    "id": 11,
                    "name": "gate (3.13)",
                    "status": "completed",
                    "conclusion": "success",
                    "check_suite": {"id": 1, "head_sha": "2" * 40},
                    "app": {"slug": "github-actions"},
                },
            ]
        },
        workflow_runs_payload={"workflow_runs": [{"check_suite_id": 1, "head_sha": "2" * 40, "name": "PR Gate"}]},
        head_sha="2" * 40,
        policy=policy,
    )
    if not observation["completeness"]["baseline_complete"]:
        raise CIEvaluationError("self-test expected a complete required baseline")
    _validate_authority(observation["authority"], advisory_key="evidence_only")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect", help="normalize GitHub check evidence")
    collect.add_argument("--check-runs", required=True)
    collect.add_argument("--workflow-runs", required=True)
    collect.add_argument("--head-sha", required=True)
    collect.add_argument("--policy", default="config/ci-observation-policy-v0.1.json")
    collect.add_argument("--output", required=True)
    evaluate_parser = subparsers.add_parser("evaluate", help="join a plan to an observation")
    evaluate_parser.add_argument("--plan", required=True)
    evaluate_parser.add_argument("--receipt", required=True)
    evaluate_parser.add_argument("--observation", required=True)
    evaluate_parser.add_argument("--policy", default="config/ci-observation-policy-v0.1.json")
    evaluate_parser.add_argument("--output", required=True)
    evaluate_parser.add_argument("--output-md", required=True)
    self_parser = subparsers.add_parser("self-test", help="run built-in authority invariants")
    self_parser.add_argument("--policy", default="config/ci-observation-policy-v0.1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "self-test":
            self_test(args.policy)
            print("ci shadow evaluator self-test: PASS")
            return 0
        policy = load_json(args.policy)
        if args.command == "collect":
            observation = collect_observation(
                check_runs_payload=load_json(args.check_runs),
                workflow_runs_payload=load_json(args.workflow_runs),
                head_sha=args.head_sha,
                policy=policy,
            )
            _write_json(args.output, observation)
            print(json.dumps(observation["completeness"], sort_keys=True))
            return 0
        evaluation = evaluate(
            plan=load_json(args.plan),
            receipt=load_json(args.receipt),
            observation=load_json(args.observation),
            policy=policy,
        )
        _write_json(args.output, evaluation)
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(evaluation), encoding="utf-8")
        print(json.dumps(evaluation["metrics"], sort_keys=True))
        return 0
    except (CIEvaluationError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
