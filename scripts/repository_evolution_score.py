#!/usr/bin/env python3
"""Deterministic multi-algorithm repository evolution observer.

This scorer is intentionally recommendation-only. It combines accepted IDKMesh
ideas from ecological carrying capacity, graph coordination, information gain,
replicator-mutator allocation, Shannon diversity, and feedback control. The
quantities are engineering proxies, not claims that the repository literally
obeys biological or physical laws.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

STRATEGIES = ("protect", "verify", "consolidate", "integrate", "onboard", "explore", "maintain")
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
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        raise ValueError("evolution policy version must be 1")
    capacity = policy.get("capacity")
    targets = policy.get("targets")
    replicator = policy.get("replicator")
    weights = policy.get("control_energy_weights")
    if not all(isinstance(value, dict) for value in (capacity, targets, replicator, weights)):
        raise ValueError("policy requires capacity, targets, replicator, and control_energy_weights objects")
    if float(capacity["tau"]) <= 0:
        raise ValueError("capacity.tau must be positive")
    priors = replicator.get("priors")
    if set(priors or {}) != set(STRATEGIES):
        raise ValueError("replicator.priors must define exactly the canonical strategies")
    prior_sum = sum(float(priors[name]) for name in STRATEGIES)
    if abs(prior_sum - 1.0) > 1e-5:
        raise ValueError("replicator priors must sum to 1")
    if not 0 < float(replicator["mu"]) < 1:
        raise ValueError("replicator.mu must be between 0 and 1")


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


def _category(item: dict[str, Any]) -> str:
    labels = set(item.get("labels") or [])
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in labels for keyword in keywords):
            return category
    return "other"


def shannon_diversity(items: list[dict[str, Any]]) -> tuple[float, dict[str, int]]:
    if not items:
        return 0.0, {}
    counts: dict[str, int] = {}
    for item in items:
        category = _category(item)
        counts[category] = counts.get(category, 0) + 1
    if len(counts) <= 1:
        return 0.0, counts
    total = sum(counts.values())
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return round(entropy / math.log(len(counts)), 6), counts


def dependency_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    node_numbers = {int(item["number"]) for item in items}
    indegree = {number: 0 for number in node_numbers}
    edge_count = 0
    sources_with_edges = 0
    for item in items:
        source = int(item["number"])
        targets = {int(value) for value in item.get("references") or [] if int(value) in node_numbers and int(value) != source}
        if targets:
            sources_with_edges += 1
        for target in targets:
            indegree[target] += 1
            edge_count += 1
    ranked = sorted(indegree.items(), key=lambda pair: (-pair[1], pair[0]))
    return {
        "nodes": len(node_numbers),
        "edges": edge_count,
        "dependency_visibility": round(sources_with_edges / max(1, len(node_numbers)), 6),
        "top_unlock_targets": [{"number": number, "incoming_open_references": degree} for number, degree in ranked[:10] if degree > 0],
        "indegree": indegree,
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


def normalized_signals(snapshot: dict[str, Any], policy: dict[str, Any], capacity: dict[str, Any], reviews: dict[str, Any], diversity: float) -> dict[str, float]:
    targets = policy["targets"]
    issues = snapshot.get("open_issues") or []
    starters = sum("good first issue" in set(issue.get("labels") or []) for issue in issues)
    external = int(snapshot.get("external_participant_count", 0))
    pin_ratio = float((snapshot.get("workflow_supply_chain") or {}).get("pin_ratio", 1.0))
    branches = int(snapshot.get("branch_count", 0))
    starter_supply = clamp01(starters / max(1.0, float(targets["minimum_starter_tasks"])))
    external_witness = clamp01(external / max(1.0, float(targets["minimum_external_participants"])))
    branch_soft = max(1.0, float(targets["maximum_branch_count_soft"]))
    branch_pressure = clamp01(max(0.0, branches - branch_soft) / branch_soft)
    return {
        "main_protection": 1.0 if bool((snapshot.get("integration") or {}).get("main_protected")) else 0.0,
        "review_capacity": float(capacity["capacity"]),
        "independent_review_coverage": float(reviews["review_coverage"]),
        "starter_task_supply": starter_supply,
        "external_witness": external_witness,
        "workflow_pin_ratio": clamp01(pin_ratio),
        "work_diversity": clamp01(diversity),
        "branch_pressure": branch_pressure,
    }


def control_energy(signals: dict[str, float], policy: dict[str, Any]) -> tuple[float, dict[str, float]]:
    minimum_capacity = float(policy["targets"]["minimum_capacity"])
    deficits = {
        "protection_deficit": 1.0 - signals["main_protection"],
        "capacity_deficit": clamp01((minimum_capacity - signals["review_capacity"]) / max(minimum_capacity, 1e-9)),
        "review_deficit": 1.0 - signals["independent_review_coverage"],
        "starter_deficit": 1.0 - signals["starter_task_supply"],
        "external_witness_deficit": 1.0 - signals["external_witness"],
        "workflow_pin_deficit": 1.0 - signals["workflow_pin_ratio"],
        "branch_pressure": signals["branch_pressure"],
    }
    weights = policy["control_energy_weights"]
    energy = sum(float(weights[name]) * value * value for name, value in deficits.items())
    return round(energy, 6), {name: round(value, 6) for name, value in deficits.items()}


def strategy_pressures(signals: dict[str, float], capacity: dict[str, Any]) -> dict[str, float]:
    ready_pressure = clamp01(float(capacity["ready_pull_requests"]) / 5.0)
    pressures = {
        "protect": 1.5 * (1.0 - signals["main_protection"]) + 0.05 * signals["main_protection"],
        "verify": ready_pressure * (0.25 + 1.0 * (1.0 - signals["independent_review_coverage"])),
        "consolidate": (1.0 - signals["review_capacity"]) + 0.5 * ready_pressure + 0.3 * signals["branch_pressure"],
        "integrate": signals["review_capacity"] * ready_pressure * (0.2 + 0.8 * signals["independent_review_coverage"]),
        "onboard": 0.55 * (1.0 - signals["starter_task_supply"]) + 0.45 * (1.0 - signals["external_witness"]),
        "explore": signals["review_capacity"] * (1.0 - 0.7 * ready_pressure) * (0.5 + 0.5 * (1.0 - signals["work_diversity"])),
        "maintain": 0.65 * (1.0 - signals["workflow_pin_ratio"]) + 0.35 * signals["branch_pressure"],
    }
    return {name: round(max(0.0, value), 6) for name, value in pressures.items()}


def replicator_response(pressures: dict[str, float], policy: dict[str, Any]) -> dict[str, float]:
    cfg = policy["replicator"]
    priors = {name: float(cfg["priors"][name]) for name in STRATEGIES}
    mean_fitness = sum(priors[name] * pressures[name] for name in STRATEGIES)
    raw = {name: priors[name] * math.exp(float(cfg["eta"]) * (pressures[name] - mean_fitness)) for name in STRATEGIES}
    total = sum(raw.values())
    normalized = {name: raw[name] / total for name in STRATEGIES}
    mu = float(cfg["mu"])
    n = len(STRATEGIES)
    mutated = {name: (1.0 - mu) * normalized[name] + mu / n for name in STRATEGIES}
    total2 = sum(mutated.values())
    return {name: round(mutated[name] / total2, 6) for name in STRATEGIES}


def determine_mode(signals: dict[str, float], capacity: dict[str, Any], reviews: dict[str, Any], policy: dict[str, Any]) -> str:
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


# Priority inputs are not all the same kind of number, and the emitted score does
# not distinguish them on its own. Three kinds exist:
#
#   snapshot_derived            computed from observed repository state;
#   snapshot_conditioned_prior  a hand-authored constant selected by an observed
#                               boolean, so the branch is evidence and the value
#                               is not;
#   hand_authored_prior         a hand-authored constant with no evidence behind
#                               it at all.
#
# Only the first is evidence. The rest are the target list for replacing
# hand-authored evolution priors with derived evidence.
NUMERATOR_PARTS = ("value", "confidence", "unlock", "community", "reversibility")
DENOMINATOR_PARTS = ("review", "complexity", "coordination", "risk")
SNAPSHOT_DERIVED = "snapshot_derived"
SNAPSHOT_CONDITIONED_PRIOR = "snapshot_conditioned_prior"
HAND_AUTHORED_PRIOR = "hand_authored_prior"

# How far an unevidenced constant is perturbed when bounding the score. This
# fraction is itself an authored choice, not a measurement, and it is reported
# alongside the bounds so a reader can reject it.
AUTHORED_SENSITIVITY = 0.25


def _priority(parts: dict[str, float]) -> float:
    numerator = (
        parts["value"]
        * parts["confidence"]
        * (0.5 + parts["unlock"])
        * (0.5 + parts["community"])
        * (0.5 + parts["reversibility"])
    )
    denominator = 1.0 + parts["review"] + parts["complexity"] + parts["coordination"] + parts["risk"]
    return round(numerator / denominator, 6)


def _perturbed(value: float, provenance: str, direction: int) -> float:
    """Move an unevidenced constant by the declared sensitivity fraction.

    Snapshot-derived parts are observations and are never perturbed. A part
    selected by an observed boolean is perturbed too: the branch is evidence,
    the magnitude it selects is not.
    """
    if provenance == SNAPSHOT_DERIVED:
        return value
    return clamp01(value * (1.0 + direction * AUTHORED_SENSITIVITY))


def _priority_bounds(parts: dict[str, float], provenance: dict[str, str]) -> tuple[float, float]:
    """Bound the score against the unevidenced constants that feed it.

    These are worst-case and best-case sensitivity bounds under a declared
    perturbation, not a statistical confidence interval. Nothing here is a
    posterior; there is no sample to form one from.
    """
    bounds: list[float] = []
    for numerator_direction in (-1, 1):
        moved = dict(parts)
        for part in NUMERATOR_PARTS:
            moved[part] = _perturbed(parts[part], provenance[part], numerator_direction)
        for part in DENOMINATOR_PARTS:
            moved[part] = _perturbed(parts[part], provenance[part], -numerator_direction)
        bounds.append(_priority(moved))
    return min(bounds), max(bounds)


def _scored(parts: dict[str, float], provenance: dict[str, str]) -> dict[str, Any]:
    if set(provenance) != set(NUMERATOR_PARTS) | set(DENOMINATOR_PARTS):
        raise ValueError("every priority part must declare a provenance")
    low, high = _priority_bounds(parts, provenance)
    unevidenced = sorted(part for part, kind in provenance.items() if kind != SNAPSHOT_DERIVED)
    return {
        "priority": _priority(parts),
        "priority_bounds": [low, high],
        "priority_input_provenance": dict(sorted(provenance.items())),
        "unevidenced_priority_inputs": unevidenced,
    }


def candidate_actions(snapshot: dict[str, Any], policy: dict[str, Any], capacity: dict[str, Any], signals: dict[str, float], graph: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if signals["main_protection"] < 1.0:
        parts = {"value": 1.0, "confidence": 1.0, "unlock": 1.0, "community": 0.6, "reversibility": 0.8, "review": 0.4, "complexity": 0.3, "coordination": 0.5, "risk": 0.2}
        provenance = dict.fromkeys(parts, HAND_AUTHORED_PRIOR)
        actions.append({"id": "protect-main", "type": "admin_gate", "target": "issue:35", "requires_admin": True, **_scored(parts, provenance), "reason": "Canonical integration is not externally protected; stronger automation must remain blocked."})

    indegree = graph["indegree"]
    for pr in snapshot.get("open_pull_requests") or []:
        number = int(pr["number"])
        unlock = clamp01(float(indegree.get(number, 0)) / 5.0)
        no_review = int(pr.get("independent_review_count", 0)) == 0
        parts = {
            "value": 0.9 if no_review else 0.7,
            "confidence": 0.95,
            "unlock": unlock,
            "community": 0.4,
            "reversibility": 1.0,
            "review": 0.7 if no_review else 0.4,
            "complexity": 0.3,
            "coordination": 0.2,
            "risk": 0.5 if pr.get("draft") else 0.35,
        }
        # `unlock` is computed from the observed dependency graph. `value`,
        # `review`, and `risk` are authored constants selected by an observed
        # boolean: the branch is evidence, the magnitude is not.
        provenance = {
            "value": SNAPSHOT_CONDITIONED_PRIOR,
            "confidence": HAND_AUTHORED_PRIOR,
            "unlock": SNAPSHOT_DERIVED,
            "community": HAND_AUTHORED_PRIOR,
            "reversibility": HAND_AUTHORED_PRIOR,
            "review": SNAPSHOT_CONDITIONED_PRIOR,
            "complexity": HAND_AUTHORED_PRIOR,
            "coordination": HAND_AUTHORED_PRIOR,
            "risk": SNAPSHOT_CONDITIONED_PRIOR,
        }
        actions.append({
            "id": f"review-pr-{number}" if no_review else f"integrate-pr-{number}",
            "type": "independent_review" if no_review else "integration_review",
            "target": f"pr:{number}",
            "requires_admin": False,
            **_scored(parts, provenance),
            "reason": "Independent review is missing." if no_review else "Independent review exists; inspect exact-head evidence and convergence before integration.",
        })

    pin_ratio = float((snapshot.get("workflow_supply_chain") or {}).get("pin_ratio", 1.0))
    if pin_ratio < float(policy["targets"]["minimum_workflow_pin_ratio"]):
        parts = {"value": 0.7, "confidence": 1.0, "unlock": 0.4, "community": 0.2, "reversibility": 0.9, "review": 0.3, "complexity": 0.4, "coordination": 0.2, "risk": 0.2}
        actions.append({"id": "pin-workflow-dependencies", "type": "supply_chain_hardening", "target": "workflows", "requires_admin": False, **_scored(parts, dict.fromkeys(parts, HAND_AUTHORED_PRIOR)), "reason": "One or more external GitHub Actions dependencies use floating refs."})

    if signals["starter_task_supply"] < 1.0 and signals["review_capacity"] >= 0.5:
        starters = sorted(int(issue["number"]) for issue in snapshot.get("open_issues") or [] if "good first issue" in set(issue.get("labels") or []))
        parts = {"value": 0.65, "confidence": 0.8, "unlock": 0.4, "community": 1.0, "reversibility": 1.0, "review": 0.3, "complexity": 0.2, "coordination": 0.2, "risk": 0.1}
        actions.append({"id": "improve-starter-surface", "type": "community_onboarding", "target": f"issue:{starters[0]}" if starters else "new-bounded-starter", "requires_admin": False, **_scored(parts, dict.fromkeys(parts, HAND_AUTHORED_PRIOR)), "reason": "Starter-task supply is below the configured minimum while review capacity is available."})

    if signals["branch_pressure"] > 0:
        parts = {"value": 0.55, "confidence": 0.9, "unlock": 0.3, "community": 0.35, "reversibility": 0.8, "review": 0.4, "complexity": 0.4, "coordination": 0.3, "risk": 0.25}
        actions.append({"id": "converge-stale-branches", "type": "repository_hygiene", "target": "issue:127", "requires_admin": False, **_scored(parts, dict.fromkeys(parts, HAND_AUTHORED_PRIOR)), "reason": "Branch count is above the soft coordination threshold; use the read-only convergence audit rather than bulk merging."})

    actions.sort(key=lambda action: (-float(action["priority"]), str(action["id"])))
    ranked = actions[:10]
    # Two adjacent recommendations whose sensitivity bounds overlap are not
    # ordered by evidence. Saying so is the point: a reader who acts on rank
    # order alone would otherwise not be able to tell.
    for index, action in enumerate(ranked):
        following = ranked[index + 1] if index + 1 < len(ranked) else None
        if following is None:
            action["separated_from_next"] = None
        else:
            action["separated_from_next"] = bool(
                action["priority_bounds"][0] > following["priority_bounds"][1]
            )
    return ranked


def evaluate(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if snapshot.get("version") != 1:
        raise ValueError("snapshot version must be 1")
    items = list(snapshot.get("open_issues") or []) + list(snapshot.get("open_pull_requests") or [])
    capacity = capacity_metrics(snapshot, policy)
    reviews = review_metrics(snapshot)
    diversity, categories = shannon_diversity(items)
    graph = dependency_metrics(items)
    signals = normalized_signals(snapshot, policy, capacity, reviews, diversity)
    energy, deficits = control_energy(signals, policy)
    pressures = strategy_pressures(signals, capacity)
    strategy_weights = replicator_response(pressures, policy)
    mode = determine_mode(signals, capacity, reviews, policy)
    actions = candidate_actions(snapshot, policy, capacity, signals, graph)

    blockers: list[str] = []
    if not signals["main_protection"]:
        blockers.append("main_unprotected")
    if signals["review_capacity"] < float(policy["targets"]["minimum_capacity"]):
        blockers.append("review_capacity_below_target")
    if reviews["ready_prs"] and signals["independent_review_coverage"] < 1.0:
        blockers.append("ready_prs_lack_independent_review")
    if signals["workflow_pin_ratio"] < float(policy["targets"]["minimum_workflow_pin_ratio"]):
        blockers.append("workflow_dependencies_not_fully_pinned")

    graph_public = {key: value for key, value in graph.items() if key != "indegree"}
    return {
        "version": 1,
        "source": snapshot.get("source") or {},
        "mode": mode,
        "control_energy_proxy": energy,
        "control_deficits": deficits,
        "capacity": capacity,
        "review": reviews,
        "signals": {key: round(value, 6) for key, value in signals.items()},
        "work_categories": categories,
        "dependency_graph": graph_public,
        "strategy_pressure": pressures,
        "strategy_weights": strategy_weights,
        "blockers": blockers,
        "recommended_actions": actions,
        "priority_uncertainty": {
            "method": "one-sided-joint-perturbation-of-unevidenced-constants-v1",
            "authored_sensitivity_fraction": AUTHORED_SENSITIVITY,
            "bounds_are_a_confidence_interval": False,
            "unevidenced_in_at_least_one_action": sorted(
                {part for action in actions for part in action["unevidenced_priority_inputs"]}
            ),
            "unevidenced_in_every_action": sorted(
                set.intersection(
                    *(set(action["unevidenced_priority_inputs"]) for action in actions)
                )
            )
            if actions
            else [],
            "adjacent_pairs_not_separated": sum(
                1 for action in actions if action["separated_from_next"] is False
            ),
            "note": (
                "Bounds move every unevidenced constant by the declared fraction in the "
                "direction that helps and the direction that hurts. They are sensitivity "
                "bounds over authored inputs, not a posterior over an observed sample, and "
                "the fraction is itself authored. Overlapping bounds between adjacent "
                "recommendations mean the ordering is not evidence."
            ),
        },
        "project_memory": snapshot.get("project_memory") or {},
        "workflow_supply_chain": snapshot.get("workflow_supply_chain") or {},
        "collection": snapshot.get("collection") or {},
        "anti_goodhart": {
            "excluded_from_fitness": ["stars", "forks", "raw_comments", "raw_commits", "reactions"],
            "principle": "Popularity and activity may be discovery signals but are not correctness or verified-improvement evidence.",
        },
        "authority": {
            "recommendation_only": True,
            "automatic_merge": False,
            "automatic_issue_creation": False,
            "automatic_branch_mutation": False,
            "constitutional_change": False,
            "untrusted_text_executes": False,
        },
        "scientific_status": "engineering proxies inspired by ecology, information theory, graph theory, evolutionary dynamics, and feedback control; not empirical laws",
    }


def render_report(result: dict[str, Any]) -> str:
    signals = result["signals"]
    capacity = result["capacity"]
    reviews = result["review"]
    actions = result["recommended_actions"][:5]
    strategy = sorted(result["strategy_weights"].items(), key=lambda pair: (-pair[1], pair[0]))
    action_lines = "\n".join(
        f"{index}. `{action['type']}` -> `{action['target']}` (priority `{action['priority']:.3f}`, "
        f"authored-input bounds `{action['priority_bounds'][0]:.3f}`-`{action['priority_bounds'][1]:.3f}`)"
        f"{' **[admin]**' if action['requires_admin'] else ''}: {action['reason']}"
        for index, action in enumerate(actions, start=1)
    ) or "No bounded recommendation was produced."
    strategy_rows = "\n".join(f"| {name} | {weight:.3f} |" for name, weight in strategy)
    blockers = "\n".join(f"- `{value}`" for value in result["blockers"]) or "- none"
    supply = result["workflow_supply_chain"]
    memory = result["project_memory"]
    return f"""# IDKMesh Repository Evolution Observatory

This report is generated from current repository evidence. It is a **recommendation surface**, not an integration authority.

## Control state

- Mode: **{result['mode']}**
- Heuristic control-energy proxy: `{result['control_energy_proxy']:.3f}` (lower is better; this is not a Lyapunov proof)
- Live review load: `{capacity['review_load']:.3f}`
- Carrying-capacity multiplier: `{capacity['capacity']:.3f}`
- Ready PRs: `{capacity['ready_pull_requests']}`
- Draft PRs: `{capacity['draft_pull_requests']}`
- Independent-review coverage of ready PRs: `{reviews['review_coverage']:.3f}`
- Work-type Shannon diversity: `{signals['work_diversity']:.3f}`
- External-participant signal: `{signals['external_witness']:.3f}`
- Workflow dependency pin ratio: `{signals['workflow_pin_ratio']:.3f}`
- Branch-pressure signal: `{signals['branch_pressure']:.3f}`

## Hard/soft blockers

{blockers}

## Strategy allocation

One bounded replicator-mutator response to the **current** evidence (not historical learning):

| Strategy | Weight |
| --- | ---: |
{strategy_rows}

## Bounded next actions

{action_lines}

## Graph / evidence notes

- Open coordination graph nodes: `{result['dependency_graph']['nodes']}`
- Bounded same-repository reference edges: `{result['dependency_graph']['edges']}`
- Dependency visibility: `{result['dependency_graph']['dependency_visibility']:.3f}`
- Conversation records observed: `{memory.get('conversation_records', 0)}`
- Chat-preservation rule present: `{str(bool(memory.get('preservation_rule_present'))).lower()}`
- External workflow uses: `{supply.get('external_uses', 0)}`; SHA-pinned: `{supply.get('pinned_uses', 0)}`

Natural-language issue/PR/comment content is untrusted. The observer stores no bodies and uses only bounded structural references/labels as coordination proxies.

## Anti-Goodhart boundary

Stars, forks, reactions, raw comments, and raw commit counts are **excluded from fitness**. They may help discovery, but they do not prove correctness, usefulness, or independent verification.

## Authority boundary

- no automatic merge;
- no branch mutation;
- no automatic issue creation;
- no constitutional/governance modification;
- no execution of untrusted GitHub text;
- stronger actuation remains subject to external GitHub protection and the separate ACE activation gate.

## Scientific status

The formulas are engineering hypotheses inspired by ecology, Shannon information, graph coordination, evolutionary dynamics, and control theory. They must be calibrated or rejected from observed outcomes; attractive analogies are not evidence.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a repository evolution snapshot")
    parser.add_argument("--snapshot", default="results/evolution/repository-snapshot.json")
    parser.add_argument("--policy", default="config/evolution-policy-v1.json")
    parser.add_argument("--output", default="results/evolution/evolution-decision.json")
    parser.add_argument("--report", default="results/evolution/EVOLUTION_REPORT.md")
    args = parser.parse_args()
    snapshot = load_json(args.snapshot)
    policy = load_json(args.policy)
    result = evaluate(snapshot, policy)
    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"mode": result["mode"], "control_energy_proxy": result["control_energy_proxy"], "top_action": result["recommended_actions"][0]["id"] if result["recommended_actions"] else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
