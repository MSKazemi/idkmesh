#!/usr/bin/env python3
"""Synthetic Physarum-inspired adaptive compute-path routing for IDKMesh.

This is a research simulator only. It operates *after* hard compute admission:
all nodes/edges in the graph are assumed already authorized and zero-project-cost.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

EPS = 1e-12


@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    length: float
    reliability_before: float
    reliability_after: float


@dataclass(frozen=True)
class Config:
    evaporation: float = 0.10
    deposit_gain: float = 0.85
    failure_penalty: float = 0.30
    d_min: float = 0.08
    d_max: float = 4.0
    beta: float = 2.2
    exploration: float = 0.06
    shift_epoch: int = 40
    max_hops: int = 5


EDGES: Tuple[Edge, ...] = (
    Edge("coordinator", "a", 1.00, 0.985, 0.78),
    Edge("a", "worker", 1.00, 0.985, 0.78),
    Edge("coordinator", "b", 1.25, 0.955, 0.990),
    Edge("b", "worker", 1.15, 0.955, 0.990),
    Edge("coordinator", "c", 1.55, 0.995, 0.995),
    Edge("c", "worker", 1.45, 0.995, 0.995),
    Edge("a", "b", 0.85, 0.970, 0.960),
    Edge("b", "c", 0.90, 0.985, 0.985),
    Edge("a", "c", 1.20, 0.990, 0.990),
)


def key(a: str, b: str) -> Tuple[str, str]:
    return tuple(sorted((a, b)))


EDGE_BY_KEY = {key(edge.a, edge.b): edge for edge in EDGES}


def adjacency() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for edge in EDGES:
        out.setdefault(edge.a, []).append(edge.b)
        out.setdefault(edge.b, []).append(edge.a)
    return out


def enumerate_paths(
    source: str = "coordinator",
    sink: str = "worker",
    max_hops: int = 5,
) -> Tuple[Tuple[str, ...], ...]:
    adj = adjacency()
    found: List[Tuple[str, ...]] = []

    def dfs(node: str, path: Tuple[str, ...]) -> None:
        if len(path) - 1 > max_hops:
            return
        if node == sink:
            found.append(path)
            return
        for nxt in sorted(adj.get(node, [])):
            if nxt in path:
                continue
            dfs(nxt, path + (nxt,))

    dfs(source, (source,))
    return tuple(sorted(found, key=lambda p: (path_length(p), p)))


def path_edges(path: Sequence[str]) -> Tuple[Tuple[str, str], ...]:
    return tuple(key(path[i], path[i + 1]) for i in range(len(path) - 1))


def path_length(path: Sequence[str]) -> float:
    return sum(EDGE_BY_KEY[e].length for e in path_edges(path))


def beta_mean(ab: Sequence[float]) -> float:
    return float(ab[0]) / (float(ab[0]) + float(ab[1]))


def true_reliability(edge: Edge, epoch: int, cfg: Config) -> float:
    return (
        edge.reliability_before
        if epoch < cfg.shift_epoch
        else edge.reliability_after
    )


def path_reliability_estimate(
    path: Sequence[str],
    reliability_posteriors: Mapping[Tuple[str, str], Sequence[float]],
) -> float:
    out = 1.0
    for edge_key in path_edges(path):
        out *= beta_mean(reliability_posteriors[edge_key])
    return out


def path_conductance(
    path: Sequence[str],
    conductance: Mapping[Tuple[str, str], float],
) -> float:
    resistance = 0.0
    for edge_key in path_edges(path):
        edge = EDGE_BY_KEY[edge_key]
        resistance += edge.length / max(EPS, conductance[edge_key])
    return 1.0 / max(EPS, resistance)


def normalize(weights: Sequence[float]) -> List[float]:
    total = sum(weights)
    if total <= EPS:
        return [1.0 / len(weights)] * len(weights)
    return [weight / total for weight in weights]


def weighted_choice(
    paths: Sequence[Tuple[str, ...]],
    probabilities: Sequence[float],
    rng: random.Random,
) -> Tuple[str, ...]:
    needle = rng.random()
    cumulative = 0.0
    for path, probability in zip(paths, probabilities):
        cumulative += probability
        if needle <= cumulative:
            return path
    return paths[-1]


def choose_path(
    strategy: str,
    paths: Sequence[Tuple[str, ...]],
    conductance: Mapping[Tuple[str, str], float],
    reliability_posteriors: Mapping[Tuple[str, str], Sequence[float]],
    path_posteriors: Mapping[str, Sequence[float]],
    cfg: Config,
    rng: random.Random,
    static_shortest: Tuple[str, ...],
) -> Tuple[str, ...]:
    if strategy == "shortest-static":
        return static_shortest

    if strategy in {"reliability-greedy", "epsilon-greedy"}:
        if strategy == "epsilon-greedy" and rng.random() < 0.10:
            return rng.choice(list(paths))
        return max(
            paths,
            key=lambda path: (
                path_reliability_estimate(path, reliability_posteriors)
                / path_length(path),
                tuple(path),
            ),
        )

    if strategy == "thompson-path":
        return max(
            paths,
            key=lambda path: (
                rng.betavariate(
                    float(path_posteriors[">".join(path)][0]),
                    float(path_posteriors[">".join(path)][1]),
                )
                / path_length(path),
                tuple(path),
            ),
        )

    if strategy != "physarum":
        raise ValueError(f"unknown strategy: {strategy}")

    if rng.random() < cfg.exploration:
        return rng.choice(list(paths))

    weights = []
    for path in paths:
        learned_reliability = path_reliability_estimate(
            path,
            reliability_posteriors,
        )
        network_conductance = path_conductance(path, conductance)
        efficiency = 1.0 / path_length(path)
        weights.append(
            math.pow(
                max(
                    EPS,
                    network_conductance
                    * learned_reliability
                    * efficiency,
                ),
                cfg.beta,
            )
        )
    return weighted_choice(paths, normalize(weights), rng)


def observe_path(
    path: Sequence[str],
    epoch: int,
    reliability_posteriors: Dict[Tuple[str, str], List[float]],
    cfg: Config,
    rng: random.Random,
) -> Tuple[bool, Tuple[Tuple[str, str], ...]]:
    failed: List[Tuple[str, str]] = []
    for edge_key in path_edges(path):
        edge = EDGE_BY_KEY[edge_key]
        ok = rng.random() < true_reliability(edge, epoch, cfg)
        reliability_posteriors[edge_key][0 if ok else 1] += 1.0
        if not ok:
            failed.append(edge_key)
    return not failed, tuple(failed)


def update_conductance(
    conductance: Dict[Tuple[str, str], float],
    path: Sequence[str],
    success: bool,
    failed_edges: Iterable[Tuple[str, str]],
    cfg: Config,
) -> None:
    used = set(path_edges(path))
    failed = set(failed_edges)
    reward = (
        1.0 / (1.0 + path_length(path))
        if success
        else 0.0
    )
    for edge_key in conductance:
        value = (1.0 - cfg.evaporation) * conductance[edge_key]
        if edge_key in used:
            value += cfg.deposit_gain * reward
        if edge_key in failed:
            value -= cfg.failure_penalty
        conductance[edge_key] = max(
            cfg.d_min,
            min(cfg.d_max, value),
        )


def entropy(counts: Mapping[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    active = 0
    for count in counts.values():
        if count <= 0:
            continue
        active += 1
        p = count / total
        h -= p * math.log(p)
    if active <= 1:
        return 0.0
    return h / math.log(active)


def run_strategy(
    strategy: str,
    seed: int = 7,
    epochs: int = 80,
    tasks_per_epoch: int = 20,
    cfg: Config | None = None,
) -> Dict[str, object]:
    cfg = cfg or Config()
    if epochs <= 0 or tasks_per_epoch <= 0:
        raise ValueError("epochs and tasks_per_epoch must be positive")

    rng = random.Random(seed)
    paths = enumerate_paths(max_hops=cfg.max_hops)
    shortest = min(paths, key=lambda path: (path_length(path), path))
    conductance = {key(edge.a, edge.b): 1.0 for edge in EDGES}
    reliability_posteriors: Dict[Tuple[str, str], List[float]] = {
        key(edge.a, edge.b): [8.0, 2.0]
        for edge in EDGES
    }
    path_posteriors: Dict[str, List[float]] = {
        ">".join(path): [4.0, 1.0]
        for path in paths
    }

    attempts = successes = 0
    total_latency = 0.0
    total_burden = 0.0
    path_counts = {">".join(path): 0 for path in paths}
    pre_successes = pre_attempts = post_successes = post_attempts = 0
    post_window_success: List[float] = []

    for epoch in range(epochs):
        epoch_successes = 0
        for _ in range(tasks_per_epoch):
            path = choose_path(
                strategy,
                paths,
                conductance,
                reliability_posteriors,
                path_posteriors,
                cfg,
                rng,
                shortest,
            )
            success, failed_edges = observe_path(
                path,
                epoch,
                reliability_posteriors,
                cfg,
                rng,
            )
            attempts += 1
            path_id = ">".join(path)
            path_counts[path_id] += 1
            path_posteriors[path_id][0 if success else 1] += 1.0
            burden = path_length(path)
            total_burden += burden
            if success:
                successes += 1
                epoch_successes += 1
                total_latency += burden
            if epoch < cfg.shift_epoch:
                pre_attempts += 1
                pre_successes += int(success)
            else:
                post_attempts += 1
                post_successes += int(success)

            if strategy == "physarum":
                update_conductance(
                    conductance,
                    path,
                    success,
                    failed_edges,
                    cfg,
                )

        if epoch >= cfg.shift_epoch:
            post_window_success.append(epoch_successes / tasks_per_epoch)

    target = 0.90
    recovery_epochs = None
    if post_window_success:
        for index in range(max(0, len(post_window_success) - 2)):
            if min(post_window_success[index:index + 3]) >= target:
                recovery_epochs = index
                break

    return {
        "strategy": strategy,
        "attempts": attempts,
        "success_rate": round(successes / attempts, 6),
        "pre_shift_success_rate": round(
            pre_successes / pre_attempts if pre_attempts else 0.0,
            6,
        ),
        "post_shift_success_rate": round(
            post_successes / post_attempts if post_attempts else 0.0,
            6,
        ),
        "mean_success_latency": round(
            total_latency / successes if successes else 0.0,
            6,
        ),
        "mean_route_burden": round(total_burden / attempts, 6),
        "path_entropy": round(entropy(path_counts), 6),
        "max_path_share": round(
            max(path_counts.values()) / attempts if attempts else 0.0,
            6,
        ),
        "recovery_epochs_to_90pct": recovery_epochs,
        "path_counts": path_counts,
        "conductance": {
            "|".join(edge_key): round(value, 6)
            for edge_key, value in sorted(conductance.items())
        },
    }


STRATEGIES = (
    "shortest-static",
    "reliability-greedy",
    "epsilon-greedy",
    "thompson-path",
    "physarum",
)


def compare(
    seed_start: int = 1,
    seeds: int = 40,
    epochs: int = 80,
    tasks_per_epoch: int = 20,
    cfg: Config | None = None,
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    cfg = cfg or Config()
    rows = {
        strategy: [
            run_strategy(
                strategy,
                seed=seed_start + offset,
                epochs=epochs,
                tasks_per_epoch=tasks_per_epoch,
                cfg=cfg,
            )
            for offset in range(seeds)
        ]
        for strategy in STRATEGIES
    }
    metrics = (
        "success_rate",
        "pre_shift_success_rate",
        "post_shift_success_rate",
        "mean_success_latency",
        "mean_route_burden",
        "path_entropy",
        "max_path_share",
    )
    summary = {
        strategy: {
            metric: round(
                sum(float(row[metric]) for row in strategy_rows)
                / len(strategy_rows),
                9,
            )
            for metric in metrics
        }
        for strategy, strategy_rows in rows.items()
    }
    return {
        "experiment": "physarum-adaptive-compute-routing-v0",
        "model_warning": (
            "Synthetic admitted-network routing model; not empirical evidence."
        ),
        "seed_start": seed_start,
        "seeds": seeds,
        "epochs": epochs,
        "tasks_per_epoch": tasks_per_epoch,
        "config": asdict(cfg),
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        choices=("all",) + STRATEGIES,
        default="all",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--tasks-per-epoch", type=int, default=20)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if min(args.seeds, args.epochs, args.tasks_per_epoch) <= 0:
        parser.error("seeds, epochs, and tasks-per-epoch must be positive")

    payload = (
        compare(
            seed_start=args.seed_start,
            seeds=args.seeds,
            epochs=args.epochs,
            tasks_per_epoch=args.tasks_per_epoch,
        )
        if args.strategy == "all"
        else run_strategy(
            args.strategy,
            seed=args.seed,
            epochs=args.epochs,
            tasks_per_epoch=args.tasks_per_epoch,
        )
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
