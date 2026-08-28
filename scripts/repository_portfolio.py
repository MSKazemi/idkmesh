#!/usr/bin/env python3
"""Build a read-only mathematical portfolio from public repository metadata.

The portfolio is an advisory control surface over open issues and pull requests.
It applies transparent proxy features, explicit dependency parsing, Pareto/NSGA
ranking, diversity diagnostics, multiplicative attention weights, and UCB
exploration. It never mutates GitHub and never treats a rank as correctness or
integration authority.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # Package import under unittest / module execution.
    from .evolution_math import (
        clamp01,
        dag_unlock_values,
        jensen_shannon_divergence,
        multiplicative_weights,
        normalized_entropy,
        rank_pareto,
        select_ucb,
    )
except ImportError:  # Direct CLI execution: python scripts/repository_portfolio.py
    from evolution_math import (
        clamp01,
        dag_unlock_values,
        jensen_shannon_divergence,
        multiplicative_weights,
        normalized_entropy,
        rank_pareto,
        select_ucb,
    )

BLOCKED_BY_RE = re.compile(r"\b(?:blocked\s+by|depends\s+on|requires)\s+#(\d+)\b", re.IGNORECASE)
BLOCKS_RE = re.compile(r"\bblocks\s+#(\d+)\b", re.IGNORECASE)


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _parse_time(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _labels(item: Mapping[str, Any]) -> set[str]:
    return {str(value).strip().lower() for value in item.get("labels", []) if str(value).strip()}


def _combined_text(item: Mapping[str, Any]) -> str:
    labels = " ".join(sorted(_labels(item)))
    return f"{item.get('title', '')}\n{item.get('body', '')}\n{labels}".lower()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(str(keyword).lower() in text for keyword in keywords)


def _label_signal(labels: set[str], policy: Mapping[str, Any], key: str) -> bool:
    configured = {str(value).lower() for value in policy["label_signals"].get(key, [])}
    return bool(labels & configured)


def classify_strategy(item: Mapping[str, Any], policy: Mapping[str, Any]) -> str:
    """Classify using transparent keyword counts; tie-break lexically."""
    text = _combined_text(item)
    scores: dict[str, int] = {}
    for name, config in policy["strategy_arms"].items():
        scores[name] = sum(1 for keyword in config.get("keywords", []) if str(keyword).lower() in text)
    best = max(scores.values(), default=0)
    if best <= 0:
        return str(policy.get("default_strategy", "product"))
    return sorted(name for name, score in scores.items() if score == best)[0]


def explicit_dependency_edges(issues: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Parse only unambiguous dependency phrases; generic #N mentions are ignored."""
    known = {int(issue["number"]) for issue in issues}
    edges: set[tuple[str, str]] = set()
    for issue in issues:
        current = int(issue["number"])
        body = str(issue.get("body") or "")
        for match in BLOCKED_BY_RE.finditer(body):
            dependency = int(match.group(1))
            if dependency in known and dependency != current:
                edges.add((str(dependency), str(current)))
        for match in BLOCKS_RE.finditer(body):
            blocked = int(match.group(1))
            if blocked in known and blocked != current:
                edges.add((str(current), str(blocked)))
    return sorted(edges, key=lambda edge: (int(edge[0]), int(edge[1])))


def _health_means(evolution_state: Mapping[str, Any]) -> dict[str, float]:
    fitness = evolution_state.get("fitness", {})
    beliefs = evolution_state.get("beliefs", {})
    result: dict[str, float] = {}
    for dimension in set(fitness) | set(beliefs):
        belief = beliefs.get(dimension)
        if isinstance(belief, Mapping):
            alpha = float(belief.get("alpha", 0.0))
            beta = float(belief.get("beta", 0.0))
            if alpha > 0 and beta > 0:
                result[dimension] = alpha / (alpha + beta)
                continue
        result[dimension] = float(fitness.get(dimension, 0.5))
    return result


def strategy_needs(
    evolution_state: Mapping[str, Any],
    math_policy: Mapping[str, Any],
    portfolio_policy: Mapping[str, Any],
) -> dict[str, float]:
    """Map distance from health targets into normalized strategy attention needs."""
    means = _health_means(evolution_state)
    homeostasis = math_policy["homeostasis"]
    dimension_need: dict[str, float] = {}
    for dimension, target_raw in homeostasis["targets"].items():
        target = float(target_raw)
        scale = float(homeostasis["scales"][dimension])
        current = float(means.get(dimension, 0.5))
        if dimension == "risk_debt":
            raw = max(0.0, (current - target) / scale)
        else:
            raw = max(0.0, (target - current) / scale)
        dimension_need[dimension] = clamp01(raw)

    needs: dict[str, float] = {}
    for strategy, config in portfolio_policy["strategy_arms"].items():
        weights = config.get("health_dimensions", {})
        numerator = sum(float(weight) * dimension_need.get(dimension, 0.0) for dimension, weight in weights.items())
        denominator = sum(abs(float(weight)) for weight in weights.values()) or 1.0
        needs[strategy] = clamp01(numerator / denominator)
    return needs


def _safe_fraction(value: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("feature scale must be positive")
    return clamp01(float(value) / scale)


def _base_features(
    item: Mapping[str, Any],
    strategy: str,
    strategy_need: float,
    policy: Mapping[str, Any],
    now: datetime,
) -> dict[str, float]:
    labels = _labels(item)
    scales = policy["feature_scales"]
    comments = int(item.get("comments_count", 0) or 0)
    body = str(item.get("body") or "")
    body_fraction = _safe_fraction(len(body), float(scales["body_characters"]))
    comment_fraction = _safe_fraction(comments, float(scales["comment_count"]))
    created = _parse_time(str(item.get("created_at") or now.isoformat()))
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    age_fraction = _safe_fraction(age_days, float(scales["age_days"]))

    priority_high = _label_signal(labels, policy, "priority_high")
    priority_medium = _label_signal(labels, policy, "priority_medium")
    risk_signal = _label_signal(labels, policy, "risk")
    large_cost = _label_signal(labels, policy, "large_cost")
    verification = _label_signal(labels, policy, "verification")

    impact = clamp01(
        0.25
        + 0.30 * float(priority_high)
        + 0.16 * float(priority_medium)
        + 0.12 * float(verification)
        + 0.10 * float(risk_signal)
        + 0.22 * strategy_need
        + 0.05 * age_fraction
    )
    information_gain = clamp01(1.0 - 0.55 * comment_fraction - 0.35 * body_fraction + 0.05 * age_fraction)
    risk = clamp01(0.06 + 0.72 * float(risk_signal) + 0.12 * float(priority_high) + (0.08 if strategy == "safety" else 0.0))
    cost = clamp01(0.10 + 0.34 * body_fraction + 0.22 * comment_fraction + 0.28 * float(large_cost) + 0.08 * age_fraction)
    review_burden = clamp01(0.08 + 0.42 * comment_fraction + 0.20 * risk + 0.15 * body_fraction + 0.10 * age_fraction)
    return {
        "impact": impact,
        "information_gain": information_gain,
        "risk": risk,
        "cost": cost,
        "review_burden": review_burden,
        "age_days": age_days,
    }


def _diversity_scores(items: Sequence[Mapping[str, Any]], strategies: Sequence[str]) -> list[float]:
    n = max(len(items), 1)
    strategy_counts = Counter(strategies)
    author_counts = Counter(str(item.get("author") or "unknown") for item in items)
    result: list[float] = []
    for item, strategy in zip(items, strategies):
        strategy_rarity = 1.0 - (strategy_counts[strategy] - 1) / n
        author = str(item.get("author") or "unknown")
        author_rarity = 1.0 - (author_counts[author] - 1) / n
        result.append(clamp01(0.55 * strategy_rarity + 0.45 * author_rarity))
    return result


def _diagnostic_opportunity(features: Mapping[str, float]) -> float:
    return clamp01(
        0.42 * float(features["impact"])
        + 0.25 * float(features["information_gain"])
        + 0.18 * float(features["unlock"])
        + 0.15 * float(features["diversity"])
        - 0.22 * float(features["risk"])
        - 0.12 * float(features["cost"])
        - 0.08 * float(features["review_burden"])
    )


def _rank_items(
    items: Sequence[Mapping[str, Any]],
    needs: Mapping[str, float],
    policy: Mapping[str, Any],
    now: datetime,
    issue_mode: bool,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    strategies = [classify_strategy(item, policy) for item in items]
    diversities = _diversity_scores(items, strategies)
    records: list[dict[str, Any]] = []
    for item, strategy, diversity in zip(items, strategies, diversities):
        features = _base_features(item, strategy, float(needs.get(strategy, 0.0)), policy, now)
        features["diversity"] = diversity
        features["unlock"] = 0.0
        records.append({
            "number": int(item["number"]),
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "author": str(item.get("author") or "unknown"),
            "strategy": strategy,
            "features": features,
        })

    edges: list[tuple[str, str]] = []
    if issue_mode and records:
        edges = explicit_dependency_edges(items)
        values = {str(record["number"]): record["features"]["impact"] for record in records}
        raw_unlock = dag_unlock_values(values.keys(), edges, values, float(policy["graph"]["unlock_decay"]))
        maximum = max(raw_unlock.values(), default=0.0)
        for record in records:
            raw = raw_unlock.get(str(record["number"]), 0.0)
            record["features"]["unlock"] = 0.0 if maximum <= 0 else clamp01(raw / maximum)

    directions = {key: int(value) for key, value in policy["pareto"]["directions"].items()}
    point_vectors = [{key: float(record["features"][key]) for key in directions} for record in records]
    ranks = rank_pareto(point_vectors, directions) if records else []
    rank_by_index = {int(row["index"]): row for row in ranks}
    for index, record in enumerate(records):
        row = rank_by_index[index]
        record["pareto_front"] = int(row["front"])
        record["crowding"] = None if math.isinf(float(row["crowding"])) else float(row["crowding"])
        record["diagnostic_opportunity"] = _diagnostic_opportunity(record["features"])
        record["why"] = _why(record)

    records.sort(
        key=lambda record: (
            record["pareto_front"],
            -(record["crowding"] if record["crowding"] is not None else float("inf")),
            -record["diagnostic_opportunity"],
            record["number"],
        )
    )
    return records, edges


def _why(record: Mapping[str, Any]) -> list[str]:
    features = record["features"]
    reasons = [f"strategy={record['strategy']}", f"Pareto front={record.get('pareto_front', '?')}"]
    for key in ("impact", "information_gain", "unlock", "diversity"):
        if float(features[key]) >= 0.65:
            reasons.append(f"high {key.replace('_', ' ')}={float(features[key]):.2f}")
    for key in ("risk", "cost", "review_burden"):
        if float(features[key]) >= 0.65:
            reasons.append(f"high {key.replace('_', ' ')}={float(features[key]):.2f}")
    return reasons


def _strategy_distribution(strategies: Sequence[str], ordered: Sequence[str]) -> list[float]:
    counts = Counter(strategies)
    if not strategies:
        return [1.0 for _ in ordered]
    return [float(counts.get(name, 0)) for name in ordered]


def update_strategy_controller(
    state: dict[str, Any],
    needs: Mapping[str, float],
    candidates: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[dict[str, float], str, dict[str, float]]:
    strategies = sorted(policy["strategy_arms"])
    weights = {name: float(state.get("strategy_weights", {}).get(name, 1.0 / len(strategies))) for name in strategies}
    rewards = {name: float(needs.get(name, 0.0)) for name in strategies}
    updated_weights = multiplicative_weights(
        weights,
        rewards,
        eta=float(policy["multiplicative_weights"]["eta"]),
        exploration_floor=float(policy["multiplicative_weights"]["exploration_floor"]),
    )

    opportunities: dict[str, list[float]] = {name: [] for name in strategies}
    for candidate in candidates:
        opportunities[candidate["strategy"]].append(float(candidate["diagnostic_opportunity"]))
    current_opportunity = {
        name: (max(opportunities[name]) if opportunities[name] else 0.0)
        for name in strategies
    }
    state.setdefault("arms", {})
    arms_for_ucb: dict[str, dict[str, float]] = {}
    for name in strategies:
        arm = state["arms"].setdefault(name, {"pulls": 0, "last_opportunity": 0.5})
        arms_for_ucb[name] = {
            "pulls": int(arm.get("pulls", 0)),
            "mean_reward": current_opportunity[name],
        }
    selected = select_ucb(arms_for_ucb, float(policy["ucb"]["exploration"]))
    state["arms"][selected]["pulls"] = int(state["arms"][selected].get("pulls", 0)) + 1
    for name in strategies:
        state["arms"][name]["last_opportunity"] = current_opportunity[name]
    state["strategy_weights"] = updated_weights
    state["last_selected_arm"] = selected
    return updated_weights, selected, current_opportunity


def build_portfolio(
    snapshot: Mapping[str, Any],
    state: dict[str, Any],
    evolution_state: Mapping[str, Any],
    math_policy: Mapping[str, Any],
    policy: Mapping[str, Any],
    checkpoint_source: str,
) -> dict[str, Any]:
    issues = list(snapshot.get("issues", []))
    prs = list(snapshot.get("pull_requests", []))
    generated_at = str(snapshot.get("generated_at") or datetime.now(timezone.utc).isoformat())
    now = _parse_time(generated_at)
    needs = strategy_needs(evolution_state, math_policy, policy)
    issue_ranking, dependency_edges = _rank_items(issues, needs, policy, now, issue_mode=True)
    pr_ranking, _ = _rank_items(prs, needs, policy, now, issue_mode=False)

    strategies = sorted(policy["strategy_arms"])
    issue_strategy_names = [classify_strategy(issue, policy) for issue in issues]
    issue_distribution = _strategy_distribution(issue_strategy_names, strategies)
    strategy_entropy = normalized_entropy(issue_distribution)
    current_mass = [value if value > 0 else 0.0 for value in issue_distribution]
    desired = [float(state.get("strategy_weights", {}).get(name, 1.0 / len(strategies))) for name in strategies]
    if sum(current_mass) <= 0:
        current_mass = [1.0 for _ in strategies]
    strategy_jsd = jensen_shannon_divergence(current_mass, desired)

    all_candidates = issue_ranking + pr_ranking
    updated_weights, selected_arm, opportunities = update_strategy_controller(state, needs, all_candidates, policy)
    state["version"] = 1
    state["updated_at"] = generated_at
    state["last_strategy_entropy"] = strategy_entropy
    state["last_strategy_jsd"] = strategy_jsd
    state["checkpoint_source"] = checkpoint_source

    top_issues = issue_ranking[: int(policy["top_issue_candidates"])]
    top_prs = pr_ranking[: int(policy["top_review_candidates"])]
    return {
        "version": 1,
        "repository": snapshot.get("repository", "unknown"),
        "generated_at": generated_at,
        "checkpoint_source": checkpoint_source,
        "authority": {
            "advisory_only": True,
            "repository_write": False,
            "issue_write": False,
            "pull_request_write": False,
            "approval": False,
            "merge": False,
        },
        "strategy_health_need": needs,
        "strategy_attention_weights": updated_weights,
        "strategy_current_opportunity": opportunities,
        "ucb_exploration_focus": selected_arm,
        "diversity": {
            "ordered_strategies": strategies,
            "open_issue_distribution": issue_distribution,
            "normalized_entropy": strategy_entropy,
            "jensen_shannon_vs_previous_attention": strategy_jsd,
        },
        "explicit_dependency_edges": [list(edge) for edge in dependency_edges],
        "top_issue_candidates": top_issues,
        "top_review_attention_candidates": top_prs,
        "population": {
            "open_issues": len(issues),
            "open_pull_requests": len(prs),
        },
        "method_limits": [
            "feature values are transparent proxies, not causal truth",
            "only explicit blocked-by/depends-on/requires/blocks phrases create dependency edges",
            "Pareto rank and UCB focus allocate attention, not correctness or integration authority",
            "multiplicative weights respond to configured health need, not measured causal reward",
        ],
    }


def render_markdown(portfolio: Mapping[str, Any]) -> str:
    lines = [
        "# Repository Mathematical Portfolio",
        "",
        f"Generated: `{portfolio['generated_at']}`",
        f"Checkpoint: `{portfolio['checkpoint_source']}`",
        "",
        "This is an advisory mathematical attention map. It cannot write, approve, or merge.",
        "",
        "## System signals",
        "",
        f"- Open issues: **{portfolio['population']['open_issues']}**",
        f"- Open pull requests: **{portfolio['population']['open_pull_requests']}**",
        f"- Open-issue strategy entropy: **{portfolio['diversity']['normalized_entropy']:.3f}**",
        f"- JSD vs previous attention distribution: **{portfolio['diversity']['jensen_shannon_vs_previous_attention']:.3f}**",
        f"- UCB exploration focus: **{portfolio['ucb_exploration_focus']}**",
        "",
        "### Strategy controller",
        "",
        "| Strategy | Health need | Attention weight | Current opportunity |",
        "| --- | ---: | ---: | ---: |",
    ]
    for strategy in portfolio["diversity"]["ordered_strategies"]:
        lines.append(
            f"| {strategy} | {portfolio['strategy_health_need'][strategy]:.3f} | "
            f"{portfolio['strategy_attention_weights'][strategy]:.3f} | "
            f"{portfolio['strategy_current_opportunity'][strategy]:.3f} |"
        )

    lines += ["", "## Pareto issue attention candidates", ""]
    if not portfolio["top_issue_candidates"]:
        lines.append("No open issues in the snapshot.")
    else:
        lines += [
            "| # | Strategy | Front | Opportunity | Impact | Info gain | Unlock | Diversity | Risk | Cost | Review burden |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for candidate in portfolio["top_issue_candidates"]:
            f = candidate["features"]
            lines.append(
                f"| {candidate['number']} | {candidate['strategy']} | {candidate['pareto_front']} | "
                f"{candidate['diagnostic_opportunity']:.3f} | {f['impact']:.3f} | {f['information_gain']:.3f} | "
                f"{f['unlock']:.3f} | {f['diversity']:.3f} | {f['risk']:.3f} | {f['cost']:.3f} | {f['review_burden']:.3f} |"
            )
            lines.append(f"\n**#{candidate['number']} — {candidate['title']}**: " + "; ".join(candidate["why"]))

    lines += ["", "## Pull-request review attention candidates", ""]
    if not portfolio["top_review_attention_candidates"]:
        lines.append("No open pull requests in the snapshot.")
    else:
        lines += [
            "| PR | Strategy | Front | Opportunity | Impact | Info gain | Diversity | Risk | Review burden |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for candidate in portfolio["top_review_attention_candidates"]:
            f = candidate["features"]
            lines.append(
                f"| {candidate['number']} | {candidate['strategy']} | {candidate['pareto_front']} | "
                f"{candidate['diagnostic_opportunity']:.3f} | {f['impact']:.3f} | {f['information_gain']:.3f} | "
                f"{f['diversity']:.3f} | {f['risk']:.3f} | {f['review_burden']:.3f} |"
            )

    lines += ["", "## Explicit dependency graph", ""]
    edges = portfolio["explicit_dependency_edges"]
    if edges:
        for source, target in edges:
            lines.append(f"- `#{source} -> #{target}`")
    else:
        lines.append("No explicit dependency phrases were found among open issues.")

    lines += ["", "## Limits and authority", ""]
    for limit in portfolio["method_limits"]:
        lines.append(f"- {limit}.")
    lines += [
        "- GitHub workflow permissions are read-only.",
        "- A high rank does not approve, close, label, assign, merge, or otherwise mutate repository state.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--evolution-state", required=True)
    parser.add_argument("--math-policy", default="state/evolution-math-policy.json")
    parser.add_argument("--policy", default="state/repository-portfolio-policy.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--checkpoint-source", default="repository-seed")
    args = parser.parse_args()

    snapshot = load_json(args.snapshot)
    state = load_json(args.state)
    evolution_state = load_json(args.evolution_state)
    math_policy = load_json(args.math_policy)
    policy = load_json(args.policy)
    portfolio = build_portfolio(snapshot, state, evolution_state, math_policy, policy, args.checkpoint_source)
    Path(args.output).write_text(json.dumps(portfolio, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.state).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(render_markdown(portfolio), encoding="utf-8")
    print(json.dumps(portfolio, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
