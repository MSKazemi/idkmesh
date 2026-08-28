#!/usr/bin/env python3
"""Dependency-free mathematical primitives for guarded IDKMesh evolution.

The functions in this module are deliberately small, deterministic, and reusable.
They turn mathematical ideas already present in the architecture documents into
machine-testable building blocks without granting repository or merge authority.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EPS = 1e-12


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def beta_update(alpha: float, beta: float, evidence: float, strength: float = 1.0) -> tuple[float, float]:
    """Apply signed soft evidence to a Beta belief.

    evidence is bounded to [-1, 1]. Positive evidence increases alpha, negative
    evidence increases beta, and zero evidence leaves the belief unchanged.
    """
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    if strength < 0:
        raise ValueError("strength must be non-negative")
    e = max(-1.0, min(1.0, float(evidence)))
    if e >= 0:
        alpha += strength * e
    else:
        beta += strength * (-e)
    return alpha, beta


def beta_mean(alpha: float, beta: float) -> float:
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    return alpha / (alpha + beta)


def beta_variance(alpha: float, beta: float) -> float:
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    s = alpha + beta
    return (alpha * beta) / (s * s * (s + 1.0))


def beta_lower_confidence(alpha: float, beta: float, z: float = 1.96) -> float:
    """Conservative normal-approximation lower bound for a Beta posterior."""
    if z < 0:
        raise ValueError("z must be non-negative")
    mean = beta_mean(alpha, beta)
    return clamp01(mean - z * math.sqrt(beta_variance(alpha, beta)))


def normalized_entropy(counts: Mapping[str, float] | Sequence[float]) -> float:
    """Shannon entropy normalized to [0,1] over the observed support."""
    values = list(counts.values()) if isinstance(counts, Mapping) else list(counts)
    values = [float(v) for v in values if float(v) > 0]
    if len(values) <= 1:
        return 0.0
    total = sum(values)
    probs = [v / total for v in values]
    h = -sum(p * math.log2(p) for p in probs)
    return h / math.log2(len(probs))


def _normalize_distribution(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("distribution must be non-empty")
    if any(v < 0 for v in values):
        raise ValueError("distribution cannot contain negative mass")
    total = float(sum(values))
    if total <= 0:
        raise ValueError("distribution must contain positive mass")
    return [float(v) / total for v in values]


def jensen_shannon_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Base-2 Jensen-Shannon divergence in [0,1]."""
    if len(p) != len(q):
        raise ValueError("distributions must have the same length")
    pp = _normalize_distribution(p)
    qq = _normalize_distribution(q)
    m = [(a + b) / 2.0 for a, b in zip(pp, qq)]

    def kl(a: Sequence[float], b: Sequence[float]) -> float:
        return sum(x * math.log2(x / y) for x, y in zip(a, b) if x > 0 and y > 0)

    return clamp01(0.5 * kl(pp, m) + 0.5 * kl(qq, m))


def effective_sample_size(n: int, correlation: float) -> float:
    """Equicorrelation effective sample size n/(1+(n-1)rho)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0.0
    rho = clamp01(correlation)
    return n / (1.0 + (n - 1) * rho)


def bayesian_vote_posterior(
    votes: Sequence[int],
    reliabilities: Sequence[float],
    groups: Sequence[str] | None = None,
    within_group_correlation: float = 0.0,
    prior_probability: float = 0.5,
) -> dict[str, float]:
    """Aggregate binary votes as reliability-weighted log-odds evidence.

    Reviewers in a declared group are discounted by the equicorrelation effective
    sample-size factor. This is a model, not proof of independence; callers must
    retain the uncertainty in the group/correlation assumptions.
    """
    if len(votes) != len(reliabilities):
        raise ValueError("votes and reliabilities must have equal length")
    if not votes:
        raise ValueError("at least one vote is required")
    if groups is None:
        groups = [f"independent-{i}" for i in range(len(votes))]
    if len(groups) != len(votes):
        raise ValueError("groups and votes must have equal length")
    prior = min(1.0 - EPS, max(EPS, float(prior_probability)))
    sizes: dict[str, int] = {}
    for group in groups:
        sizes[group] = sizes.get(group, 0) + 1
    rho = clamp01(within_group_correlation)
    log_odds = math.log(prior / (1.0 - prior))
    effective_votes = 0.0
    for vote, reliability, group in zip(votes, reliabilities, groups):
        if vote not in (0, 1):
            raise ValueError("votes must be 0 or 1")
        r = min(1.0 - EPS, max(EPS, float(reliability)))
        group_size = sizes[group]
        weight = 1.0 / (1.0 + (group_size - 1) * rho)
        evidence = math.log(r / (1.0 - r))
        log_odds += weight * (evidence if vote == 1 else -evidence)
        effective_votes += weight
    if log_odds >= 0:
        probability = 1.0 / (1.0 + math.exp(-log_odds))
    else:
        e = math.exp(log_odds)
        probability = e / (1.0 + e)
    return {
        "posterior_probability": probability,
        "log_odds": log_odds,
        "effective_votes": effective_votes,
    }


def _dominates(a: Mapping[str, float], b: Mapping[str, float], directions: Mapping[str, int]) -> bool:
    no_worse = True
    strictly_better = False
    for metric, direction in directions.items():
        if direction not in (-1, 1):
            raise ValueError("direction must be +1 for maximize or -1 for minimize")
        av = direction * float(a[metric])
        bv = direction * float(b[metric])
        if av < bv - EPS:
            no_worse = False
            break
        if av > bv + EPS:
            strictly_better = True
    return no_worse and strictly_better


def nondominated_sort(points: Sequence[Mapping[str, float]], directions: Mapping[str, int]) -> list[list[int]]:
    """NSGA-style fast non-dominated sorting; returns fronts of point indices."""
    n = len(points)
    dominates_sets: list[list[int]] = [[] for _ in range(n)]
    dominated_count = [0] * n
    fronts: list[list[int]] = [[]]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if _dominates(points[i], points[j], directions):
                dominates_sets[i].append(j)
            elif _dominates(points[j], points[i], directions):
                dominated_count[i] += 1
        if dominated_count[i] == 0:
            fronts[0].append(i)
    current = 0
    while current < len(fronts) and fronts[current]:
        nxt: list[int] = []
        for i in fronts[current]:
            for j in dominates_sets[i]:
                dominated_count[j] -= 1
                if dominated_count[j] == 0:
                    nxt.append(j)
        if nxt:
            fronts.append(sorted(set(nxt)))
        current += 1
    return [sorted(front) for front in fronts if front]


def crowding_distance(front: Sequence[int], points: Sequence[Mapping[str, float]], directions: Mapping[str, int]) -> dict[int, float]:
    """NSGA-II crowding distance for diversity preservation within one front."""
    if not front:
        return {}
    distance = {idx: 0.0 for idx in front}
    if len(front) <= 2:
        return {idx: math.inf for idx in front}
    for metric, direction in directions.items():
        ordered = sorted(front, key=lambda idx: direction * float(points[idx][metric]))
        distance[ordered[0]] = math.inf
        distance[ordered[-1]] = math.inf
        values = [direction * float(points[idx][metric]) for idx in ordered]
        span = values[-1] - values[0]
        if abs(span) <= EPS:
            continue
        for pos in range(1, len(ordered) - 1):
            idx = ordered[pos]
            if math.isinf(distance[idx]):
                continue
            distance[idx] += (values[pos + 1] - values[pos - 1]) / span
    return distance


def rank_pareto(points: Sequence[Mapping[str, float]], directions: Mapping[str, int]) -> list[dict[str, Any]]:
    """Return deterministic Pareto rank + crowding ordering."""
    fronts = nondominated_sort(points, directions)
    ranked: list[dict[str, Any]] = []
    for rank, front in enumerate(fronts):
        crowding = crowding_distance(front, points, directions)
        for idx in front:
            ranked.append({"index": idx, "front": rank, "crowding": crowding[idx]})
    ranked.sort(key=lambda row: (row["front"], -row["crowding"] if math.isfinite(row["crowding"]) else -math.inf, row["index"]))
    return ranked


def multiplicative_weights(
    weights: Mapping[str, float],
    rewards: Mapping[str, float],
    eta: float = 0.2,
    exploration_floor: float = 0.05,
) -> dict[str, float]:
    """Exponentiated-gradient / discrete replicator update with exploration floor."""
    if eta < 0:
        raise ValueError("eta must be non-negative")
    if not (0.0 <= exploration_floor < 1.0):
        raise ValueError("exploration_floor must be in [0,1)")
    keys = sorted(weights)
    if not keys or set(keys) != set(rewards):
        raise ValueError("weights and rewards must have the same non-empty keys")
    if any(float(weights[k]) <= 0 for k in keys):
        raise ValueError("all weights must be positive")
    logs = {k: math.log(float(weights[k])) + eta * float(rewards[k]) for k in keys}
    offset = max(logs.values())
    raw = {k: math.exp(logs[k] - offset) for k in keys}
    total = sum(raw.values())
    base = {k: raw[k] / total for k in keys}
    uniform = 1.0 / len(keys)
    return {k: (1.0 - exploration_floor) * base[k] + exploration_floor * uniform for k in keys}


def ucb_score(mean_reward: float, pulls: int, total_pulls: int, exploration: float = math.sqrt(2.0)) -> float:
    if pulls < 0 or total_pulls < 0:
        raise ValueError("pull counts must be non-negative")
    if exploration < 0:
        raise ValueError("exploration must be non-negative")
    if pulls == 0:
        return math.inf
    return float(mean_reward) + exploration * math.sqrt(math.log(max(total_pulls, 1) + 1.0) / pulls)


def select_ucb(arms: Mapping[str, Mapping[str, float]], exploration: float = math.sqrt(2.0)) -> str:
    """Select an arm deterministically; unseen arms receive infinite exploration bonus."""
    if not arms:
        raise ValueError("at least one arm is required")
    total = sum(int(arms[name].get("pulls", 0)) for name in arms)
    scores = {
        name: ucb_score(float(arms[name].get("mean_reward", 0.0)), int(arms[name].get("pulls", 0)), total, exploration)
        for name in sorted(arms)
    }
    return max(sorted(scores), key=lambda name: scores[name])


def dag_unlock_values(
    nodes: Iterable[str],
    edges: Iterable[tuple[str, str]],
    values: Mapping[str, float],
    decay: float = 0.5,
) -> dict[str, float]:
    """Discounted downstream unlock value using shortest directed distance."""
    if decay < 0:
        raise ValueError("decay must be non-negative")
    node_set = set(nodes)
    adjacency = {node: [] for node in node_set}
    for src, dst in edges:
        if src not in node_set or dst not in node_set:
            raise ValueError("edge references unknown node")
        adjacency[src].append(dst)
    result: dict[str, float] = {}
    for root in sorted(node_set):
        q: deque[tuple[str, int]] = deque([(root, 0)])
        best_distance = {root: 0}
        while q:
            current, distance = q.popleft()
            for nxt in adjacency[current]:
                nd = distance + 1
                if nxt not in best_distance or nd < best_distance[nxt]:
                    best_distance[nxt] = nd
                    q.append((nxt, nd))
        result[root] = sum(
            float(values.get(node, 0.0)) * math.exp(-decay * distance)
            for node, distance in best_distance.items()
            if node != root
        )
    return result


def homeostatic_potential(
    values: Mapping[str, float],
    targets: Mapping[str, float],
    scales: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> float:
    """Quadratic Lyapunov-style potential around healthy target bands."""
    if set(values) != set(targets) or set(values) != set(scales):
        raise ValueError("values, targets, and scales must have identical keys")
    if weights is not None and set(weights) != set(values):
        raise ValueError("weights must have identical keys")
    total = 0.0
    for key in values:
        scale = float(scales[key])
        if scale <= 0:
            raise ValueError("all scales must be positive")
        weight = 1.0 if weights is None else float(weights[key])
        err = (float(values[key]) - float(targets[key])) / scale
        total += weight * err * err
    return total


def lyapunov_accept(before: float, after: float, tolerance: float = 0.0) -> bool:
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    return float(after) <= float(before) + tolerance


def build_demo() -> dict[str, Any]:
    alpha, beta = beta_update(4.0, 4.0, 0.8, strength=1.5)
    vote = bayesian_vote_posterior(
        [1, 1, 0],
        [0.8, 0.8, 0.7],
        groups=["worker-a", "worker-a", "worker-b"],
        within_group_correlation=0.6,
    )
    points = [
        {"impact": 0.9, "risk": 0.7, "cost": 0.2},
        {"impact": 0.7, "risk": 0.2, "cost": 0.3},
        {"impact": 0.6, "risk": 0.3, "cost": 0.5},
    ]
    ranks = rank_pareto(points, {"impact": 1, "risk": -1, "cost": -1})
    mw = multiplicative_weights(
        {"stability": 1 / 3, "exploration": 1 / 3, "community": 1 / 3},
        {"stability": 0.4, "exploration": 0.8, "community": 0.2},
    )
    arms = {
        "stability": {"mean_reward": 0.65, "pulls": 8},
        "exploration": {"mean_reward": 0.70, "pulls": 2},
        "community": {"mean_reward": 0.55, "pulls": 0},
    }
    unlock = dag_unlock_values(
        ["A", "B", "C", "D"],
        [("A", "B"), ("A", "C"), ("B", "D")],
        {"A": 1.0, "B": 2.0, "C": 1.5, "D": 4.0},
    )
    before = homeostatic_potential(
        {"verification": 0.45, "risk": 0.55},
        {"verification": 0.75, "risk": 0.20},
        {"verification": 0.20, "risk": 0.20},
    )
    after = homeostatic_potential(
        {"verification": 0.60, "risk": 0.40},
        {"verification": 0.75, "risk": 0.20},
        {"verification": 0.20, "risk": 0.20},
    )
    return {
        "bayesian": {
            "alpha": alpha,
            "beta": beta,
            "mean": beta_mean(alpha, beta),
            "lower_confidence": beta_lower_confidence(alpha, beta),
        },
        "vote_aggregation": vote,
        "diversity": {
            "entropy": normalized_entropy([5, 3, 2]),
            "js_divergence": jensen_shannon_divergence([9, 1], [1, 9]),
            "effective_sample_size_n5_rho08": effective_sample_size(5, 0.8),
        },
        "pareto_ranking": ranks,
        "multiplicative_weights": mw,
        "ucb_selected_arm": select_ucb(arms),
        "graph_unlock": unlock,
        "homeostasis": {
            "before": before,
            "after": after,
            "lyapunov_accept": lyapunov_accept(before, after),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="emit a deterministic kernel demonstration")
    parser.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args()
    if not args.demo:
        parser.error("currently --demo is required")
    data = build_demo()
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
