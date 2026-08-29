#!/usr/bin/env python3
"""Current-state homeostatic governor for the persistent evolution kernel.

The Bayesian evolution scorer carries historical soft evidence across trusted
checkpoints. This module adds a separate, recomputed current-state gate.
Historical belief is never allowed to compensate for missing external protection,
exhausted review capacity, or absent independent review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from evolution_math import homeostatic_potential, normalized_entropy

CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("verification", ("verification", "security", "test", "benchmark")),
    ("community", ("good first issue", "help wanted", "growth-seed", "documentation", "community")),
    ("research", ("research", "experiment", "science")),
    ("maintenance", ("maintenance", "dependencies", "refactor", "ci")),
    ("governance", ("governance", "policy")),
    ("product", ("bug", "enhancement", "feature")),
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        raise ValueError("live policy version must be 1")
    if float(policy["capacity"]["tau"]) <= 0:
        raise ValueError("capacity.tau must be positive")
    homeostasis = policy["homeostasis"]
    if (
        set(homeostasis["targets"]) != set(homeostasis["scales"])
        or set(homeostasis["targets"]) != set(homeostasis["weights"])
    ):
        raise ValueError("homeostasis targets/scales/weights must share keys")


def capacity_metrics(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    cfg = policy["capacity"]
    prs = snapshot.get("open_pull_requests") or []
    issues = snapshot.get("open_issues") or []
    ready = sum(not bool(pr.get("draft")) for pr in prs)
    draft = len(prs) - ready
    growth = sum("growth-seed" in set(issue.get("labels") or []) for issue in issues)
    other = max(0, len(issues) - growth)
    capped_other = min(other, int(cfg["other_issue_cap"]))
    load = (
        float(cfg["ready_pr_weight"]) * ready
        + float(cfg["draft_pr_weight"]) * draft
        + float(cfg["growth_seed_weight"]) * growth
        + float(cfg["other_issue_weight"]) * capped_other
    )
    capacity = 1.0 / (1.0 + math.exp((load - float(cfg["K"])) / float(cfg["tau"])))
    return {
        "model": "live-open-work-v1",
        "review_load": round(load, 6),
        "capacity": round(capacity, 6),
        "ready_pull_requests": ready,
        "draft_pull_requests": draft,
        "open_growth_seeds": growth,
        "other_open_issues": other,
        "other_open_issues_capped": capped_other,
    }


def review_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    ready = [pr for pr in snapshot.get("open_pull_requests") or [] if not pr.get("draft")]
    reviewed = sum(int(pr.get("independent_review_count", 0)) > 0 for pr in ready)
    approved = sum(int(pr.get("independent_approval_count", 0)) > 0 for pr in ready)
    return {
        "ready_prs": len(ready),
        "ready_prs_with_independent_review": reviewed,
        "ready_prs_with_independent_approval": approved,
        "review_coverage": round(reviewed / max(1, len(ready)), 6) if ready else 1.0,
        "approval_coverage": round(approved / max(1, len(ready)), 6) if ready else 1.0,
    }


def _category(item: dict[str, Any]) -> str:
    labels = set(item.get("labels") or [])
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in labels for keyword in keywords):
            return category
    return "other"


def work_diversity(snapshot: dict[str, Any]) -> tuple[float, dict[str, int]]:
    items = list(snapshot.get("open_issues") or []) + list(snapshot.get("open_pull_requests") or [])
    counts: dict[str, int] = {}
    for item in items:
        category = _category(item)
        counts[category] = counts.get(category, 0) + 1
    return round(normalized_entropy(counts), 6), counts


def live_signals(
    snapshot: dict[str, Any],
    policy: dict[str, Any],
    capacity: dict[str, Any],
    reviews: dict[str, Any],
) -> dict[str, float]:
    targets = policy["targets"]
    issues = snapshot.get("open_issues") or []
    starters = sum("good first issue" in set(issue.get("labels") or []) for issue in issues)
    external = int(snapshot.get("external_participant_count", 0))
    branch_count = int(snapshot.get("branch_count", 0))
    branch_soft = max(1.0, float(targets["maximum_branch_count_soft"]))
    branch_pressure = clamp01(max(0.0, branch_count - branch_soft) / branch_soft)
    return {
        "main_protection": 1.0 if bool((snapshot.get("integration") or {}).get("main_protected")) else 0.0,
        "review_capacity": float(capacity["capacity"]),
        "independent_review_coverage": float(reviews["review_coverage"]),
        "starter_task_supply": clamp01(starters / max(1.0, float(targets["minimum_starter_tasks"]))),
        "external_witness": clamp01(external / max(1.0, float(targets["minimum_external_participants"]))),
        "workflow_pin_ratio": clamp01(float((snapshot.get("workflow_supply_chain") or {}).get("pin_ratio", 1.0))),
        "branch_health": 1.0 - branch_pressure,
    }


def mode(
    signals: dict[str, float],
    capacity: dict[str, Any],
    reviews: dict[str, Any],
    policy: dict[str, Any],
) -> str:
    targets = policy["targets"]
    if signals["main_protection"] < 1.0:
        return "GUARD"
    if signals["review_capacity"] < 0.35 or capacity["ready_pull_requests"] > int(targets["max_ready_prs"]):
        return "CONSOLIDATE"
    if reviews["ready_prs"] and signals["independent_review_coverage"] < 0.5:
        return "VERIFY"
    if signals["external_witness"] < 1.0 and signals["starter_task_supply"] < 1.0 and signals["review_capacity"] >= 0.5:
        return "ONBOARD"
    if reviews["ready_prs"] and signals["review_capacity"] >= float(targets["minimum_capacity"]):
        return "INTEGRATE"
    return "EXPLORE"


def needs(
    snapshot: dict[str, Any],
    signals: dict[str, float],
    capacity: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if signals["main_protection"] < 1.0:
        result.append({"type": "hard_guard", "target": "issue:35", "reason": "canonical branch is not externally protected"})
    for pr in snapshot.get("open_pull_requests") or []:
        if int(pr.get("independent_review_count", 0)) == 0:
            result.append({"type": "independent_review", "target": f"pr:{int(pr['number'])}", "reason": "no independent reviewer is observed"})
    if signals["review_capacity"] < float(policy["targets"]["minimum_capacity"]):
        result.append({"type": "consolidate", "target": "open-review-queue", "reason": "live carrying capacity is below target"})
    if signals["workflow_pin_ratio"] < float(policy["targets"]["minimum_workflow_pin_ratio"]):
        result.append({"type": "supply_chain", "target": "workflows", "reason": "external Action dependencies are not sufficiently SHA-pinned"})
    if signals["starter_task_supply"] < 1.0 and signals["review_capacity"] >= 0.5:
        result.append({"type": "onboarding", "target": "starter-task-surface", "reason": "bounded newcomer task supply is below target"})
    if signals["branch_health"] < 1.0:
        result.append({"type": "repository_hygiene", "target": "issue:127", "reason": "branch count exceeds the soft coordination threshold"})
    return result[:12]


def evaluate(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if snapshot.get("version") != 1:
        raise ValueError("snapshot version must be 1")
    capacity = capacity_metrics(snapshot, policy)
    reviews = review_metrics(snapshot)
    diversity, categories = work_diversity(snapshot)
    signals = live_signals(snapshot, policy, capacity, reviews)
    homeostasis = policy["homeostasis"]
    potential = homeostatic_potential(signals, homeostasis["targets"], homeostasis["scales"], homeostasis["weights"])
    current_mode = mode(signals, capacity, reviews, policy)
    blockers: list[str] = []
    if signals["main_protection"] < 1.0:
        blockers.append("main_unprotected")
    if signals["review_capacity"] < float(policy["targets"]["minimum_capacity"]):
        blockers.append("review_capacity_below_target")
    if reviews["ready_prs"] and signals["independent_review_coverage"] < 1.0:
        blockers.append("ready_prs_lack_independent_review")
    if signals["workflow_pin_ratio"] < float(policy["targets"]["minimum_workflow_pin_ratio"]):
        blockers.append("workflow_dependencies_not_fully_pinned")
    return {
        "version": 1,
        "mode": current_mode,
        "homeostatic_potential": round(potential, 6),
        "capacity": capacity,
        "review": reviews,
        "signals": {key: round(value, 6) for key, value in signals.items()},
        "work_diversity": diversity,
        "work_categories": categories,
        "blockers": blockers,
        "bounded_needs": needs(snapshot, signals, capacity, policy),
        "conjunctive_rule": "persistent Bayesian/evolutionary evidence may inform recommendations, but current hard guards cannot be compensated by historical fitness",
        "anti_goodhart": {
            "excluded_from_live_fitness": ["stars", "forks", "reactions", "raw_comments", "raw_commits"],
            "principle": "activity/popularity are not correctness or verified-improvement evidence"
        },
        "authority": {
            "recommendation_only": True,
            "automatic_merge": False,
            "automatic_issue_creation": False,
            "automatic_branch_mutation": False,
            "constitutional_change": False
        }
    }


def render(result: dict[str, Any], snapshot: dict[str, Any]) -> str:
    capacity = result["capacity"]
    reviews = result["review"]
    signals = result["signals"]
    needs_lines = "\n".join(f"- `{item['type']}` -> `{item['target']}`: {item['reason']}" for item in result["bounded_needs"]) or "- none"
    blockers = "\n".join(f"- `{value}`" for value in result["blockers"]) or "- none"
    supply = snapshot.get("workflow_supply_chain") or {}
    memory = snapshot.get("project_memory") or {}
    return f"""# Live Repository Governor

This section complements the persistent Bayesian Mathematical Evolution Kernel with recomputed current-state guards. Historical belief cannot override current hard constraints.

## Current state

- Mode: **{result['mode']}**
- Live review load: `{capacity['review_load']:.3f}`
- Carrying capacity: `{capacity['capacity']:.3f}`
- Ready/draft PRs: `{capacity['ready_pull_requests']}` / `{capacity['draft_pull_requests']}`
- Independent-review coverage of ready PRs: `{reviews['review_coverage']:.3f}`
- Open-work Shannon diversity: `{result['work_diversity']:.3f}`
- Main protection signal: `{signals['main_protection']:.3f}`
- External-witness signal: `{signals['external_witness']:.3f}`
- Workflow SHA-pin ratio: `{signals['workflow_pin_ratio']:.3f}`
- Branch-health signal: `{signals['branch_health']:.3f}`
- Live homeostatic potential: `{result['homeostatic_potential']:.3f}`

## Current blockers

{blockers}

## Bounded needs

{needs_lines}

## Evidence hygiene

- External workflow uses: `{supply.get('external_uses', 0)}`; SHA-pinned: `{supply.get('pinned_uses', 0)}`
- Conversation records observed: `{memory.get('conversation_records', 0)}`
- Chat-preservation rule present: `{str(bool(memory.get('preservation_rule_present'))).lower()}`
- Natural-language bodies retained by snapshot: **false**

## Authority

This governor has no write, merge, approval, branch-mutation, issue-creation, or constitutional-change authority. It is a conjunctive safety/current-state surface for the persistent mathematical evolution observer.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="results/evolution/repository-snapshot.json")
    parser.add_argument("--policy", default="state/evolution-live-policy.json")
    parser.add_argument("--output", default="results/evolution/live-governor.json")
    parser.add_argument("--report", default="results/evolution/LIVE_GOVERNOR_REPORT.md")
    args = parser.parse_args()
    snapshot = load_json(args.snapshot)
    policy = load_json(args.policy)
    result = evaluate(snapshot, policy)
    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render(result, snapshot), encoding="utf-8")
    print(json.dumps({"mode": result["mode"], "homeostatic_potential": result["homeostatic_potential"], "blockers": result["blockers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
