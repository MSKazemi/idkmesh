#!/usr/bin/env python3
"""Build a deterministic, non-authoritative CI plan for an exact revision.

The v0.1 planner runs only in shadow mode. It classifies changed paths, closes
mandatory check dependencies, and ranks optional checks under a bounded time
budget. It never executes a generated command, skips an existing check, writes
repository state, approves a change, or authorizes integration.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Iterable


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
ZERO_SHA = "0" * 40
PLANNER_VERSION = "0.1"


class CIPlanError(RuntimeError):
    """Raised when planner input is incomplete or unsafe."""


def _reject_unknown_fields(value: dict[str, Any], allowed: set[str], field: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise CIPlanError(f"{field} contains unknown fields: {', '.join(unknown)}")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CIPlanError(f"{path}: expected a JSON object")
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_unit_interval(value: Any, field: str) -> float:
    if not _is_number(value):
        raise CIPlanError(f"{field} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise CIPlanError(f"{field} must be in [0, 1]")
    return result


def _require_non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CIPlanError(f"{field} must be a non-negative integer")
    return value


def _validate_patterns(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CIPlanError(f"{field} must be a non-empty list")
    patterns: list[str] = []
    for pattern in value:
        if not isinstance(pattern, str) or not pattern or pattern.startswith("/"):
            raise CIPlanError(f"{field} contains an invalid repository-relative pattern")
        patterns.append(pattern)
    return tuple(patterns)


def validate_policy(policy: dict[str, Any]) -> None:
    _reject_unknown_fields(
        policy,
        {
            "schema_version",
            "mode",
            "project_spend_usd_max",
            "full_suite_baseline_required",
            "budgets",
            "risk_rules",
            "checks",
        },
        "policy",
    )
    if policy.get("schema_version") != "0.1":
        raise CIPlanError("policy schema_version must be 0.1")
    if policy.get("mode") != "shadow":
        raise CIPlanError("v0.1 policy must remain in shadow mode")
    spend = policy.get("project_spend_usd_max")
    if not _is_number(spend) or float(spend) != 0.0:
        raise CIPlanError("CI planner project spend must remain exactly zero")
    if policy.get("full_suite_baseline_required") is not True:
        raise CIPlanError("shadow mode must require the existing full-suite baseline")

    budgets = policy.get("budgets")
    if not isinstance(budgets, dict):
        raise CIPlanError("policy budgets block is missing")
    _reject_unknown_fields(
        budgets,
        {"optional_seconds", "exploration_slots", "queue_cost_seconds"},
        "policy.budgets",
    )
    _require_non_negative_int(budgets.get("optional_seconds"), "budgets.optional_seconds")
    _require_non_negative_int(budgets.get("exploration_slots"), "budgets.exploration_slots")
    _require_non_negative_int(budgets.get("queue_cost_seconds"), "budgets.queue_cost_seconds")

    risk_rules = policy.get("risk_rules")
    if not isinstance(risk_rules, list) or not risk_rules:
        raise CIPlanError("policy risk_rules must be a non-empty list")
    risk_ids: set[str] = set()
    for index, rule in enumerate(risk_rules):
        if not isinstance(rule, dict):
            raise CIPlanError(f"risk_rules[{index}] must be an object")
        _reject_unknown_fields(rule, {"id", "risk_class", "patterns"}, f"risk_rules[{index}]")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in risk_ids:
            raise CIPlanError(f"risk_rules[{index}].id is missing or duplicated")
        risk_ids.add(rule_id)
        if rule.get("risk_class") not in RISK_ORDER:
            raise CIPlanError(f"risk rule {rule_id} has an invalid risk_class")
        _validate_patterns(rule.get("patterns"), f"risk rule {rule_id}.patterns")
    if "fallback" not in risk_ids:
        raise CIPlanError("policy must define a fallback risk rule")
    fallback_rule = next(rule for rule in risk_rules if rule["id"] == "fallback")
    if RISK_ORDER[fallback_rule["risk_class"]] < RISK_ORDER["R1"]:
        raise CIPlanError("fallback risk rule must be at least R1")

    checks = policy.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CIPlanError("policy checks must be a non-empty list")
    check_ids: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise CIPlanError(f"checks[{index}] must be an object")
        _reject_unknown_fields(
            check,
            {
                "id",
                "description",
                "patterns",
                "always_run",
                "hard_gate",
                "mandatory_at_or_above_risk",
                "dependencies",
                "estimated_seconds",
                "failure_probability_prior",
                "impact",
                "information_gain",
            },
            f"checks[{index}]",
        )
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id or check_id in check_ids:
            raise CIPlanError(f"checks[{index}].id is missing or duplicated")
        check_ids.add(check_id)
        if not isinstance(check.get("description"), str) or not check["description"]:
            raise CIPlanError(f"check {check_id} description is missing")
        _validate_patterns(check.get("patterns"), f"check {check_id}.patterns")
        if not isinstance(check.get("always_run"), bool):
            raise CIPlanError(f"check {check_id}.always_run must be Boolean")
        if not isinstance(check.get("hard_gate"), bool):
            raise CIPlanError(f"check {check_id}.hard_gate must be Boolean")
        if check["always_run"] and not check["hard_gate"]:
            raise CIPlanError(f"always-run check {check_id} must be a hard gate")
        dependencies = check.get("dependencies")
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) or not item for item in dependencies
        ):
            raise CIPlanError(f"check {check_id}.dependencies must contain check IDs")
        if len(set(dependencies)) != len(dependencies):
            raise CIPlanError(f"check {check_id}.dependencies must be unique")
        _require_non_negative_int(check.get("estimated_seconds"), f"check {check_id}.estimated_seconds")
        _require_unit_interval(
            check.get("failure_probability_prior"),
            f"check {check_id}.failure_probability_prior",
        )
        _require_unit_interval(check.get("impact"), f"check {check_id}.impact")
        _require_unit_interval(check.get("information_gain"), f"check {check_id}.information_gain")
        threshold = check.get("mandatory_at_or_above_risk")
        if threshold is not None and threshold not in RISK_ORDER:
            raise CIPlanError(f"check {check_id} has an invalid risk threshold")

    by_id = {check["id"]: check for check in checks}
    if "repository-integrity" not in by_id or not (
        by_id["repository-integrity"]["always_run"]
        and by_id["repository-integrity"]["hard_gate"]
    ):
        raise CIPlanError("policy requires an always-run repository-integrity hard gate")
    if "full-regression" not in by_id or by_id["full-regression"].get(
        "mandatory_at_or_above_risk"
    ) != "R3":
        raise CIPlanError("policy requires full-regression at R3")
    for check_id, check in by_id.items():
        for dependency in check["dependencies"]:
            if dependency not in by_id:
                raise CIPlanError(f"check {check_id} depends on unknown check {dependency}")
            if dependency == check_id:
                raise CIPlanError(f"check {check_id} cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(check_id: str) -> None:
        if check_id in visiting:
            raise CIPlanError(f"check dependency cycle includes {check_id}")
        if check_id in visited:
            return
        visiting.add(check_id)
        for dependency in by_id[check_id]["dependencies"]:
            visit(dependency)
        visiting.remove(check_id)
        visited.add(check_id)

    for check_id in sorted(by_id):
        visit(check_id)


def normalize_changed_files(paths: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for raw in paths:
        if not isinstance(raw, str) or not raw:
            raise CIPlanError("changed paths must be non-empty strings")
        path = raw.replace("\\", "/")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise CIPlanError(f"changed path escapes repository root: {raw}")
        clean = str(pure)
        if clean in {"", "."}:
            raise CIPlanError(f"invalid changed path: {raw}")
        normalized.add(clean)
    return sorted(normalized)


def path_matches(path: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(path, pattern):
        return True
    if pattern.startswith("**/"):
        return fnmatch.fnmatchcase(path, pattern[3:])
    return False


def _matching_files(paths: list[str], patterns: Iterable[str]) -> list[str]:
    return [path for path in paths if any(path_matches(path, pattern) for pattern in patterns)]


def classify_risk(paths: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    matched_rules: set[str] = set()
    unmatched: list[str] = []
    highest = "R0"
    rules = [rule for rule in policy["risk_rules"] if rule["id"] != "fallback"]
    fallback = next((rule for rule in policy["risk_rules"] if rule["id"] == "fallback"), None)

    for path in paths:
        file_rules = [
            rule for rule in rules if any(path_matches(path, pattern) for pattern in rule["patterns"])
        ]
        if not file_rules:
            unmatched.append(path)
            if fallback is not None:
                file_rules = [fallback]
        for rule in file_rules:
            matched_rules.add(rule["id"])
            if RISK_ORDER[rule["risk_class"]] > RISK_ORDER[highest]:
                highest = rule["risk_class"]

    if not paths:
        highest = "R1"
        unmatched.append("<empty-change-set>")
    return {
        "class": highest,
        "matched_rules": sorted(matched_rules),
        "unmatched_files": unmatched,
    }


def _score(check: dict[str, Any], queue_cost: int) -> float:
    numerator = (
        float(check["failure_probability_prior"])
        * float(check["impact"])
        * float(check["information_gain"])
    )
    return round(numerator / (int(check["estimated_seconds"]) + queue_cost or 1), 12)


def _close_mandatory_dependencies(
    mandatory: set[str], checks: dict[str, dict[str, Any]], reasons: dict[str, list[str]]
) -> None:
    changed = True
    while changed:
        changed = False
        for check_id in sorted(tuple(mandatory)):
            for dependency in checks[check_id]["dependencies"]:
                if dependency not in mandatory:
                    mandatory.add(dependency)
                    reasons.setdefault(dependency, []).append(f"dependency-of:{check_id}")
                    changed = True


def _dependency_closure(check_id: str, checks: dict[str, dict[str, Any]]) -> set[str]:
    closure: set[str] = set()

    def visit(current: str) -> None:
        if current in closure:
            return
        closure.add(current)
        for dependency in checks[current]["dependencies"]:
            visit(dependency)

    visit(check_id)
    return closure


def build_plan(
    *,
    repository: str,
    base_sha: str,
    head_sha: str,
    changed_files: Iterable[str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)
    for field, value in (("base_sha", base_sha), ("head_sha", head_sha)):
        if not isinstance(value, str) or len(value) != 40 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise CIPlanError(f"{field} must be a lowercase 40-character Git SHA")
    if not isinstance(repository, str) or not repository:
        raise CIPlanError("repository is required")

    paths = normalize_changed_files(changed_files)
    risk = classify_risk(paths, policy)
    check_map = {check["id"]: check for check in policy["checks"]}
    matched: dict[str, list[str]] = {}
    reasons: dict[str, list[str]] = {}
    mandatory: set[str] = set()
    impacted: set[str] = set()

    for check_id, check in check_map.items():
        matched[check_id] = _matching_files(paths, check["patterns"])
        if check["always_run"]:
            impacted.add(check_id)
            mandatory.add(check_id)
            reasons.setdefault(check_id, []).append("always-run-hard-gate")
        if matched[check_id]:
            impacted.add(check_id)
            reasons.setdefault(check_id, []).append("changed-path-impact")
            if check["hard_gate"]:
                mandatory.add(check_id)
                reasons[check_id].append("impacted-hard-gate")
        threshold = check.get("mandatory_at_or_above_risk")
        if threshold is not None and RISK_ORDER[risk["class"]] >= RISK_ORDER[threshold]:
            impacted.add(check_id)
            mandatory.add(check_id)
            reasons.setdefault(check_id, []).append(f"risk-threshold:{threshold}")

    _close_mandatory_dependencies(mandatory, check_map, reasons)
    impacted.update(mandatory)

    queue_cost = int(policy["budgets"]["queue_cost_seconds"])
    optional_candidates = [
        check_id for check_id in impacted if check_id not in mandatory
    ]
    scores = {check_id: _score(check, queue_cost) for check_id, check in check_map.items()}
    optional_candidates.sort(key=lambda item: (-scores[item], item))

    budget = int(policy["budgets"]["optional_seconds"])
    selected_optional: set[str] = set()
    used = 0
    for check_id in optional_candidates:
        bundle = _dependency_closure(check_id, check_map) - mandatory - selected_optional
        duration = sum(int(check_map[item]["estimated_seconds"]) for item in bundle)
        if used + duration <= budget:
            selected_optional.update(bundle)
            impacted.update(bundle)
            reasons.setdefault(check_id, []).append("budgeted-information-value")
            for dependency in bundle - {check_id}:
                reasons.setdefault(dependency, []).append(f"dependency-of-selected:{check_id}")
            used += duration

    remaining = [check_id for check_id in optional_candidates if check_id not in selected_optional]
    exploration: set[str] = set()
    exploration_slots = int(policy["budgets"]["exploration_slots"])
    remaining.sort(
        key=lambda check_id: hashlib.sha256(
            f"{head_sha}:{check_id}".encode("utf-8")
        ).hexdigest()
    )
    for check_id in remaining:
        if len(exploration) >= exploration_slots:
            break
        bundle = _dependency_closure(check_id, check_map) - mandatory - selected_optional
        duration = sum(int(check_map[item]["estimated_seconds"]) for item in bundle)
        if used + duration <= budget:
            selected_optional.update(bundle)
            impacted.update(bundle)
            exploration.add(check_id)
            reasons.setdefault(check_id, []).append("deterministic-exploration")
            for dependency in bundle - {check_id}:
                reasons.setdefault(dependency, []).append(f"dependency-of-exploration:{check_id}")
            used += duration

    checks_output: list[dict[str, Any]] = []
    for check_id in sorted(check_map):
        check = check_map[check_id]
        if check_id in mandatory:
            lane = "mandatory"
            selected = True
            score: float | None = None
        elif check_id in impacted:
            lane = "optional"
            selected = check_id in selected_optional or check_id in exploration
            score = scores[check_id]
        else:
            lane = "not-impacted"
            selected = False
            score = None
            reasons.setdefault(check_id, []).append("no-matching-change")
        if lane == "optional" and not selected:
            reasons.setdefault(check_id, []).append("outside-optional-budget")
        checks_output.append(
            {
                "id": check_id,
                "lane": lane,
                "selected": selected,
                "exploration": check_id in exploration,
                "reasons": sorted(set(reasons.get(check_id, ["policy-classified"]))),
                "matched_files": matched[check_id],
                "dependencies": sorted(check["dependencies"]),
                "estimated_seconds": int(check["estimated_seconds"]),
                "score": score,
            }
        )

    policy_digest = sha256_digest(policy)
    fingerprint = sha256_digest(
        {
            "repository": repository,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "changed_files": paths,
            "policy_digest": policy_digest,
        }
    ).split(":", 1)[1]
    plan = {
        "schema_version": "0.1",
        "kind": "idkmesh-ci-plan",
        "planner_version": PLANNER_VERSION,
        "mode": "shadow",
        "plan_id": f"ci-plan-{head_sha[:12]}-{fingerprint[:12]}",
        "repository": repository,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "policy_digest": policy_digest,
        "changed_files": paths,
        "risk": risk,
        "budget": {
            "optional_seconds": budget,
            "selected_optional_seconds": used,
            "project_spend_usd_max": 0,
        },
        "checks": checks_output,
        "summary": {
            "mandatory": sorted(mandatory),
            "selected_optional": sorted(selected_optional),
            "exploration": sorted(exploration),
            "not_selected": sorted(
                check["id"] for check in checks_output if not check["selected"]
            ),
            "full_suite_baseline_required": True,
        },
        "authority": {
            "advisory_only": True,
            "execute": False,
            "skip_required_checks": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
        },
    }
    return plan


def build_receipt(plan: dict[str, Any]) -> dict[str, Any]:
    plan_digest = sha256_digest(plan)
    digest_suffix = plan_digest.split(":", 1)[1][:12]
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-ci-receipt",
        "planner_version": plan["planner_version"],
        "receipt_id": f"ci-receipt-{plan['head_sha'][:12]}-{digest_suffix}",
        "stage": "planning",
        "outcome": "shadow_plan_emitted",
        "plan_id": plan["plan_id"],
        "plan_digest": plan_digest,
        "base_sha": plan["base_sha"],
        "head_sha": plan["head_sha"],
        "executed_checks": [],
        "actual_cost": {
            "project_spend_usd": 0,
            "check_execution_seconds": 0,
            "planner_execution_seconds": None,
            "planner_resource_use_measured": False,
            "external_resource_cost_zero_claim": False,
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


def render_markdown(plan: dict[str, Any], receipt: dict[str, Any]) -> str:
    lines = [
        "# CI Shadow Plan",
        "",
        f"- Plan: `{plan['plan_id']}`",
        f"- Exact head: `{plan['head_sha']}`",
        f"- Base: `{plan['base_sha']}`",
        f"- Risk: **{plan['risk']['class']}**",
        f"- Changed files: **{len(plan['changed_files'])}**",
        f"- Optional budget: **{plan['budget']['selected_optional_seconds']} / {plan['budget']['optional_seconds']} seconds**",
        "- Existing full CI baseline still required: **yes**",
        "- Execute/skip/approve/merge authority: **none**",
        "",
        "| Check | Lane | Selected | Exploration | Estimate | Reasons |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for check in plan["checks"]:
        lines.append(
            f"| `{check['id']}` | `{check['lane']}` | "
            f"{str(check['selected']).lower()} | {str(check['exploration']).lower()} | "
            f"{check['estimated_seconds']}s | {', '.join(check['reasons'])} |"
        )
    lines.extend(
        [
            "",
            f"Planning receipt: `{receipt['receipt_id']}`",
            "",
            "> This is shadow evidence. It does not suppress any existing workflow or authorize integration.",
            "",
        ]
    )
    return "\n".join(lines)


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise CIPlanError(message)
    return result.stdout


def changed_files_from_git(repo_root: Path, base_sha: str, head_sha: str) -> list[str]:
    _git(repo_root, "cat-file", "-e", f"{head_sha}^{{commit}}")
    if base_sha == ZERO_SHA:
        output = _git(repo_root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", head_sha)
    else:
        _git(repo_root, "cat-file", "-e", f"{base_sha}^{{commit}}")
        output = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMRDT", f"{base_sha}...{head_sha}")
    return normalize_changed_files(line for line in output.splitlines() if line.strip())


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test(policy_path: str | Path) -> None:
    policy = load_json(policy_path)
    plan = build_plan(
        repository="MSKazemi/idkmesh",
        base_sha="1" * 40,
        head_sha="2" * 40,
        changed_files=[".github/workflows/ci-shadow-planner.yml", "README.md"],
        policy=policy,
    )
    if plan["risk"]["class"] != "R3":
        raise CIPlanError("self-test expected R3 for a workflow change")
    if "full-regression" not in plan["summary"]["mandatory"]:
        raise CIPlanError("self-test expected full regression at R3")
    expected_authority = {
        "advisory_only": True,
        "execute": False,
        "skip_required_checks": False,
        "approve": False,
        "merge": False,
        "repository_write": False,
    }
    if plan["authority"] != expected_authority:
        raise CIPlanError("self-test authority block is malformed")
    if plan["authority"]["execute"] or plan["authority"]["merge"]:
        raise CIPlanError("self-test detected forbidden authority")
    receipt = build_receipt(plan)
    if receipt["executed_checks"] or receipt["authority"]["merge"]:
        raise CIPlanError("self-test receipt crossed the shadow boundary")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="build an exact-revision shadow plan")
    plan_parser.add_argument("--repository", required=True)
    plan_parser.add_argument("--repo-root", default=".")
    plan_parser.add_argument("--base-sha", required=True)
    plan_parser.add_argument("--head-sha", required=True)
    plan_parser.add_argument("--policy", default="config/ci-policy-v0.1.json")
    plan_parser.add_argument("--changed-file", action="append", default=[])
    plan_parser.add_argument("--output-plan", required=True)
    plan_parser.add_argument("--output-receipt", required=True)
    plan_parser.add_argument("--output-md", required=True)

    self_parser = subparsers.add_parser("self-test", help="run built-in authority invariants")
    self_parser.add_argument("--policy", default="config/ci-policy-v0.1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "self-test":
            self_test(args.policy)
            print("ci shadow planner self-test: PASS")
            return 0

        repo_root = Path(args.repo_root).resolve()
        policy_path = Path(args.policy)
        if not policy_path.is_absolute():
            policy_path = repo_root / policy_path
        policy = load_json(policy_path)
        changed = (
            normalize_changed_files(args.changed_file)
            if args.changed_file
            else changed_files_from_git(repo_root, args.base_sha, args.head_sha)
        )
        plan = build_plan(
            repository=args.repository,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
            changed_files=changed,
            policy=policy,
        )
        receipt = build_receipt(plan)
        _write_json(args.output_plan, plan)
        _write_json(args.output_receipt, receipt)
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(plan, receipt), encoding="utf-8")
        print(json.dumps(plan["summary"], sort_keys=True))
        return 0
    except (CIPlanError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
