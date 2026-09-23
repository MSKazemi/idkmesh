#!/usr/bin/env python3
"""Stress matrix for Physarum-inspired admitted compute routing.

Research only. Every edge is assumed to have already passed IDKMesh hard
resource/compute admission. This module compares adaptive routing policies under
stationarity, drift, outages, correlated shocks, asymmetric donor burden, and
noisy failure attribution.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import physarum_compute_routing_sim as base


@dataclass(frozen=True)
class Environment:
    name: str
    mode: str
    event_start: float = 0.50
    event_end: float = 0.65
    regional_shock_rate: float = 0.0
    attribution_noise: float = 0.0
    c_burden_multiplier: float = 1.0


ENVIRONMENTS: Tuple[Environment, ...] = (
    Environment("stationary", "stationary"),
    Environment("abrupt-shift", "abrupt"),
    Environment("gradual-shift", "gradual", event_start=0.25, event_end=0.75),
    Environment("transient-a-outage", "transient"),
    Environment("permanent-a-node-loss", "node-loss"),
    Environment(
        "correlated-ab-region-shocks",
        "regional-shock",
        regional_shock_rate=0.18,
    ),
    Environment(
        "donor-burden-asymmetry",
        "abrupt",
        c_burden_multiplier=2.0,
    ),
    Environment(
        "noisy-failure-attribution",
        "abrupt",
        attribution_noise=0.30,
    ),
)

STRATEGIES = (
    "shortest-static",
    "discounted-thompson",
    "multipath-failover",
    "physarum",
)


def environment_by_name(name: str) -> Environment:
    for environment in ENVIRONMENTS:
        if environment.name == name:
            return environment
    raise ValueError(f"unknown environment: {name}")


def event_bounds(
    environment: Environment,
    epochs: int,
) -> Tuple[int, int]:
    start = max(0, min(epochs - 1, int(epochs * environment.event_start)))
    end = max(start + 1, min(epochs, int(epochs * environment.event_end)))
    return start, end


def edge_burden(
    edge_key: Tuple[str, str],
    environment: Environment,
) -> float:
    edge = base.EDGE_BY_KEY[edge_key]
    multiplier = (
        environment.c_burden_multiplier
        if "c" in edge_key
        else 1.0
    )
    return edge.length * multiplier


def path_burden(
    path: Sequence[str],
    environment: Environment,
) -> float:
    return sum(
        edge_burden(edge_key, environment)
        for edge_key in base.path_edges(path)
    )


def reliability_for(
    edge_key: Tuple[str, str],
    epoch: int,
    epochs: int,
    environment: Environment,
    regional_shock: bool = False,
) -> float:
    edge = base.EDGE_BY_KEY[edge_key]
    start, end = event_bounds(environment, epochs)

    if environment.mode == "stationary":
        reliability = edge.reliability_before
    elif environment.mode == "abrupt":
        reliability = (
            edge.reliability_before
            if epoch < start
            else edge.reliability_after
        )
    elif environment.mode == "gradual":
        if epoch <= start:
            mix = 0.0
        elif epoch >= end:
            mix = 1.0
        else:
            mix = (epoch - start) / max(1, end - start)
        reliability = (
            (1.0 - mix) * edge.reliability_before
            + mix * edge.reliability_after
        )
    elif environment.mode == "transient":
        reliability = edge.reliability_before
        if start <= epoch < end and "a" in edge_key:
            reliability = 0.05
    elif environment.mode == "node-loss":
        reliability = edge.reliability_before
        if epoch >= start and "a" in edge_key:
            reliability = 0.001
    elif environment.mode == "regional-shock":
        reliability = edge.reliability_before
    else:
        raise ValueError(f"unknown environment mode: {environment.mode}")

    if (
        regional_shock
        and environment.regional_shock_rate > 0.0
        and ("a" in edge_key or "b" in edge_key)
    ):
        reliability *= 0.42

    return max(0.001, min(0.999, reliability))


def beta_mean(values: Sequence[float]) -> float:
    return float(values[0]) / (float(values[0]) + float(values[1]))


def path_reliability(
    path: Sequence[str],
    edge_posteriors: Mapping[Tuple[str, str], Sequence[float]],
) -> float:
    result = 1.0
    for edge_key in base.path_edges(path):
        result *= beta_mean(edge_posteriors[edge_key])
    return result


def adaptive_conductance(
    path: Sequence[str],
    conductance: Mapping[Tuple[str, str], float],
    environment: Environment,
) -> float:
    resistance = 0.0
    for edge_key in base.path_edges(path):
        resistance += edge_burden(edge_key, environment) / max(
            base.EPS,
            conductance[edge_key],
        )
    return 1.0 / max(base.EPS, resistance)


def update_conductance(
    conductance: Dict[Tuple[str, str], float],
    path: Sequence[str],
    success: bool,
    failed_edges: Iterable[Tuple[str, str]],
    config: base.Config,
    environment: Environment,
) -> None:
    used = set(base.path_edges(path))
    failed = set(failed_edges)
    reward = (
        1.0 / (1.0 + path_burden(path, environment))
        if success
        else 0.0
    )
    for edge_key in conductance:
        value = (1.0 - config.evaporation) * conductance[edge_key]
        if edge_key in used:
            value += config.deposit_gain * reward
        if edge_key in failed:
            value -= config.failure_penalty
        conductance[edge_key] = max(
            config.d_min,
            min(config.d_max, value),
        )


def discount_path_posteriors(
    posteriors: Dict[str, List[float]],
    factor: float = 0.94,
) -> None:
    for values in posteriors.values():
        values[0] = 1.0 + (values[0] - 1.0) * factor
        values[1] = 1.0 + (values[1] - 1.0) * factor


def physarum_choice(
    paths: Sequence[Tuple[str, ...]],
    conductance: Mapping[Tuple[str, str], float],
    edge_posteriors: Mapping[Tuple[str, str], Sequence[float]],
    environment: Environment,
    config: base.Config,
    rng: random.Random,
) -> Tuple[str, ...]:
    if rng.random() < config.exploration:
        return rng.choice(list(paths))

    weights = []
    for path in paths:
        value = (
            adaptive_conductance(path, conductance, environment)
            * path_reliability(path, edge_posteriors)
            / path_burden(path, environment)
        )
        weights.append(math.pow(max(base.EPS, value), config.beta))
    return base.weighted_choice(paths, base.normalize(weights), rng)


def discounted_thompson_choice(
    paths: Sequence[Tuple[str, ...]],
    path_posteriors: Mapping[str, Sequence[float]],
    environment: Environment,
    rng: random.Random,
) -> Tuple[str, ...]:
    return max(
        paths,
        key=lambda path: (
            rng.betavariate(
                float(path_posteriors[">".join(path)][0]),
                float(path_posteriors[">".join(path)][1]),
            )
            / path_burden(path, environment),
            tuple(path),
        ),
    )


def greedy_path_order(
    paths: Sequence[Tuple[str, ...]],
    path_posteriors: Mapping[str, Sequence[float]],
    environment: Environment,
) -> List[Tuple[str, ...]]:
    return sorted(
        paths,
        key=lambda path: (
            beta_mean(path_posteriors[">".join(path)])
            / path_burden(path, environment),
            -path_burden(path, environment),
            tuple(path),
        ),
        reverse=True,
    )


def fallback_for(
    primary: Tuple[str, ...],
    ordered: Sequence[Tuple[str, ...]],
) -> Tuple[str, ...]:
    primary_edges = set(base.path_edges(primary))
    alternatives = [path for path in ordered if path != primary]
    return min(
        alternatives,
        key=lambda path: (
            len(primary_edges.intersection(base.path_edges(path))),
            ordered.index(path),
        ),
    )


def observe(
    path: Sequence[str],
    epoch: int,
    epochs: int,
    environment: Environment,
    edge_posteriors: Dict[Tuple[str, str], List[float]],
    regional_shock: bool,
    rng: random.Random,
) -> Tuple[bool, Tuple[Tuple[str, str], ...]]:
    failed: List[Tuple[str, str]] = []
    for edge_key in base.path_edges(path):
        probability = reliability_for(
            edge_key,
            epoch,
            epochs,
            environment,
            regional_shock,
        )
        ok = rng.random() < probability
        edge_posteriors[edge_key][0 if ok else 1] += 1.0
        if not ok:
            failed.append(edge_key)
    return not failed, tuple(failed)


def attributed_failures(
    path: Sequence[str],
    failed_edges: Sequence[Tuple[str, str]],
    environment: Environment,
    rng: random.Random,
) -> Tuple[Tuple[str, str], ...]:
    if not failed_edges or environment.attribution_noise <= 0.0:
        return tuple(failed_edges)
    used = list(base.path_edges(path))
    result: List[Tuple[str, str]] = []
    for edge_key in failed_edges:
        if rng.random() < environment.attribution_noise:
            result.append(rng.choice(used))
        else:
            result.append(edge_key)
    return tuple(result)


def entropy(counts: Mapping[str, int]) -> float:
    return base.entropy(counts)


def run_strategy(
    strategy: str,
    environment: Environment,
    seed: int = 7,
    epochs: int = 80,
    tasks_per_epoch: int = 20,
    config: base.Config | None = None,
) -> Dict[str, object]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if epochs <= 0 or tasks_per_epoch <= 0:
        raise ValueError("epochs and tasks_per_epoch must be positive")

    config = config or base.Config()
    rng = random.Random(seed)
    paths = base.enumerate_paths(max_hops=config.max_hops)
    shortest = min(
        paths,
        key=lambda path: (path_burden(path, environment), path),
    )
    conductance = {
        base.key(edge.a, edge.b): 1.0
        for edge in base.EDGES
    }
    edge_posteriors: Dict[Tuple[str, str], List[float]] = {
        base.key(edge.a, edge.b): [8.0, 2.0]
        for edge in base.EDGES
    }
    path_posteriors: Dict[str, List[float]] = {
        ">".join(path): [4.0, 1.0]
        for path in paths
    }
    primary_counts = {">".join(path): 0 for path in paths}

    attempts = successes = retries = 0
    route_attempts = 0
    total_burden = successful_burden = 0.0
    start, _ = event_bounds(environment, epochs)
    pre_attempts = pre_successes = post_attempts = post_successes = 0

    for epoch in range(epochs):
        if strategy == "discounted-thompson":
            discount_path_posteriors(path_posteriors)

        regional_shock = (
            environment.regional_shock_rate > 0.0
            and rng.random() < environment.regional_shock_rate
        )

        for _ in range(tasks_per_epoch):
            if strategy == "shortest-static":
                primary = shortest
            elif strategy == "discounted-thompson":
                primary = discounted_thompson_choice(
                    paths,
                    path_posteriors,
                    environment,
                    rng,
                )
            elif strategy == "multipath-failover":
                ordered = greedy_path_order(
                    paths,
                    path_posteriors,
                    environment,
                )
                primary = ordered[0]
            else:
                primary = physarum_choice(
                    paths,
                    conductance,
                    edge_posteriors,
                    environment,
                    config,
                    rng,
                )

            primary_id = ">".join(primary)
            primary_counts[primary_id] += 1
            attempts += 1

            success, failed_edges = observe(
                primary,
                epoch,
                epochs,
                environment,
                edge_posteriors,
                regional_shock,
                rng,
            )
            route_attempts += 1
            primary_cost = path_burden(primary, environment)
            total_burden += primary_cost
            path_posteriors[primary_id][0 if success else 1] += 1.0

            if strategy == "physarum":
                update_conductance(
                    conductance,
                    primary,
                    success,
                    attributed_failures(
                        primary,
                        failed_edges,
                        environment,
                        rng,
                    ),
                    config,
                    environment,
                )

            final_success = success
            task_burden = primary_cost

            if strategy == "multipath-failover" and not success:
                ordered = greedy_path_order(
                    paths,
                    path_posteriors,
                    environment,
                )
                backup = fallback_for(primary, ordered)
                backup_id = ">".join(backup)
                retry_success, retry_failed = observe(
                    backup,
                    epoch,
                    epochs,
                    environment,
                    edge_posteriors,
                    regional_shock,
                    rng,
                )
                retries += 1
                route_attempts += 1
                backup_cost = path_burden(backup, environment)
                total_burden += backup_cost
                task_burden += backup_cost
                path_posteriors[backup_id][0 if retry_success else 1] += 1.0
                final_success = retry_success

            if final_success:
                successes += 1
                successful_burden += task_burden

            if epoch < start:
                pre_attempts += 1
                pre_successes += int(final_success)
            else:
                post_attempts += 1
                post_successes += int(final_success)

    return {
        "strategy": strategy,
        "environment": environment.name,
        "attempts": attempts,
        "route_attempts": route_attempts,
        "retry_rate": round(retries / attempts if attempts else 0.0, 6),
        "success_rate": round(successes / attempts, 6),
        "pre_event_success_rate": round(
            pre_successes / pre_attempts if pre_attempts else 0.0,
            6,
        ),
        "post_event_success_rate": round(
            post_successes / post_attempts if post_attempts else 0.0,
            6,
        ),
        "mean_route_burden_per_task": round(
            total_burden / attempts if attempts else 0.0,
            6,
        ),
        "mean_success_burden": round(
            successful_burden / successes if successes else 0.0,
            6,
        ),
        "path_entropy": round(entropy(primary_counts), 6),
        "max_primary_path_share": round(
            max(primary_counts.values()) / attempts if attempts else 0.0,
            6,
        ),
    }


SUMMARY_METRICS = (
    "retry_rate",
    "success_rate",
    "pre_event_success_rate",
    "post_event_success_rate",
    "mean_route_burden_per_task",
    "mean_success_burden",
    "path_entropy",
    "max_primary_path_share",
)


def compare(
    seed_start: int = 1,
    seeds: int = 20,
    epochs: int = 80,
    tasks_per_epoch: int = 20,
    environment_names: Sequence[str] | None = None,
    strategy_names: Sequence[str] | None = None,
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    environments = (
        [environment_by_name(name) for name in environment_names]
        if environment_names
        else list(ENVIRONMENTS)
    )
    strategies = list(strategy_names) if strategy_names else list(STRATEGIES)
    summary: Dict[str, Dict[str, Dict[str, float]]] = {}

    for environment in environments:
        summary[environment.name] = {}
        for strategy in strategies:
            rows = [
                run_strategy(
                    strategy,
                    environment,
                    seed=seed_start + offset,
                    epochs=epochs,
                    tasks_per_epoch=tasks_per_epoch,
                )
                for offset in range(seeds)
            ]
            summary[environment.name][strategy] = {
                metric: round(
                    sum(float(row[metric]) for row in rows) / len(rows),
                    9,
                )
                for metric in SUMMARY_METRICS
            }

    return {
        "experiment": "physarum-adaptive-compute-routing-stress-v0",
        "model_warning": (
            "Synthetic admitted-network stress matrix; not empirical evidence."
        ),
        "seed_start": seed_start,
        "seeds": seeds,
        "epochs": epochs,
        "tasks_per_epoch": tasks_per_epoch,
        "environments": [asdict(environment) for environment in environments],
        "strategies": strategies,
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--tasks-per-epoch", type=int, default=20)
    parser.add_argument(
        "--environment",
        action="append",
        choices=tuple(environment.name for environment in ENVIRONMENTS),
    )
    parser.add_argument(
        "--strategy",
        action="append",
        choices=STRATEGIES,
    )
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if min(args.seeds, args.epochs, args.tasks_per_epoch) <= 0:
        parser.error("seeds, epochs, and tasks-per-epoch must be positive")

    payload = compare(
        seed_start=args.seed_start,
        seeds=args.seeds,
        epochs=args.epochs,
        tasks_per_epoch=args.tasks_per_epoch,
        environment_names=args.environment,
        strategy_names=args.strategy,
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
