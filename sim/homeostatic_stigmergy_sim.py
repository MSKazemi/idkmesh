#!/usr/bin/env python3
"""Capacity-governed hybrid of capability routing and ACO-style stigmergy.

The controller increases diversity/congestion pressure only when observed
crowding exceeds target levels. It remains a synthetic research model.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

import aco_stigmergy_sim as base


@dataclass(frozen=True)
class HomeostaticConfig:
    alpha: float = 0.70
    beta: float = 2.50
    rho: float = 0.12
    exploration: float = 0.03
    tau_min: float = 0.10
    tau_max: float = 4.00
    lambda_initial: float = 0.45
    lambda_min: float = 0.05
    lambda_max: float = 2.50
    duplicate_target: float = 0.20
    concentration_target: float = 0.35
    duplicate_gain: float = 1.40
    concentration_gain: float = 0.90
    relaxation: float = 0.08
    overload_penalty: float = 0.035
    correlation_penalty: float = 0.025


def update_regulation(
    value: float,
    duplicate_rate: float,
    concentration: float,
    config: HomeostaticConfig,
) -> float:
    """Feedback law for density-dependent diversity/congestion pressure."""
    duplicate_error = duplicate_rate - config.duplicate_target
    concentration_error = concentration - config.concentration_target
    pressure = (
        config.duplicate_gain * duplicate_error
        + config.concentration_gain * concentration_error
    )
    # Relax toward lambda_min when pressure is absent, analogous to a controller
    # avoiding permanent defensive activation after congestion disappears.
    relaxed = value + pressure - config.relaxation * (value - config.lambda_min)
    return base.clamp(relaxed, config.lambda_min, config.lambda_max)


def hybrid_score(
    worker: base.Worker,
    task: base.Task,
    pheromone: Mapping[str, float],
    attempt_count: int,
    same_group_attempts: int,
    regulation: float,
    config: HomeostaticConfig,
) -> float:
    """Capability exploitation multiplied by adaptive ecological regulation."""
    skill = base.clamp(float(worker.skills.get(task.skill, 0.0)), 0.02, 1.0)
    capability_value = skill * base.intrinsic_value(task)
    tau = base.clamp(pheromone.get(task.name, config.tau_min), config.tau_min, config.tau_max)
    diversity = 1.0 / (1.0 + same_group_attempts)
    congestion = 1.0 / (1.0 + attempt_count)

    regulated = math.pow(diversity * congestion, regulation)
    return max(
        base.EPS,
        capability_value
        * math.pow(tau, config.alpha)
        * regulated,
    )


def probabilities(
    worker: base.Worker,
    tasks: Sequence[base.Task],
    pheromone: Mapping[str, float],
    attempt_counts: Mapping[str, int],
    group_attempts: Mapping[Tuple[str, str], int],
    regulation: float,
    config: HomeostaticConfig,
) -> List[float]:
    weights = [
        math.pow(
            hybrid_score(
                worker,
                task,
                pheromone,
                attempt_counts.get(task.name, 0),
                group_attempts.get((task.name, worker.group), 0),
                regulation,
                config,
            ),
            config.beta,
        )
        for task in tasks
    ]
    total = sum(weights)
    if total <= base.EPS:
        return [1.0 / len(tasks)] * len(tasks)
    return [weight / total for weight in weights]


def choose_task(
    worker: base.Worker,
    pheromone: Mapping[str, float],
    attempt_counts: Mapping[str, int],
    group_attempts: Mapping[Tuple[str, str], int],
    regulation: float,
    config: HomeostaticConfig,
    rng: random.Random,
) -> base.Task:
    if rng.random() < config.exploration:
        return rng.choice(list(base.TASKS))
    probs = probabilities(
        worker,
        base.TASKS,
        pheromone,
        attempt_counts,
        group_attempts,
        regulation,
        config,
    )
    return base.weighted_choice(base.TASKS, probs, rng)


def run_hybrid(
    seed: int = 7,
    workers: int = 24,
    epochs: int = 50,
    config: HomeostaticConfig | None = None,
) -> Dict[str, object]:
    config = config or HomeostaticConfig()
    rng = random.Random(seed)
    population = base.make_workers(workers, rng)
    pheromone: Dict[str, float] = {task.name: 1.0 for task in base.TASKS}
    regulation = config.lambda_initial
    regulation_history: List[float] = []

    total_attempts = 0
    verified_count = 0
    verified_utility = 0.0
    review_cost = 0.0
    compute_cost = 0.0
    duplicate_attempts = 0
    selections: Dict[str, int] = {task.name: 0 for task in base.TASKS}
    verified_by_task: Dict[str, int] = {task.name: 0 for task in base.TASKS}

    for _epoch in range(epochs):
        attempt_counts: Dict[str, int] = {task.name: 0 for task in base.TASKS}
        group_attempts: Dict[Tuple[str, str], int] = {}
        deposits: Dict[str, float] = {task.name: 0.0 for task in base.TASKS}
        penalties: Dict[str, float] = {task.name: 0.0 for task in base.TASKS}
        epoch_duplicates = 0

        order = list(population)
        rng.shuffle(order)

        for worker in order:
            task = choose_task(
                worker,
                pheromone,
                attempt_counts,
                group_attempts,
                regulation,
                config,
                rng,
            )
            same_group = group_attempts.get((task.name, worker.group), 0)
            result = base.attempt(worker, task, same_group, rng)

            total_attempts += 1
            selections[task.name] += 1
            attempt_counts[task.name] += 1
            group_attempts[(task.name, worker.group)] = same_group + 1
            review_cost += task.review_cost
            compute_cost += task.compute_cost

            if attempt_counts[task.name] > task.parallel_limit:
                duplicate_attempts += 1
                epoch_duplicates += 1
                penalties[task.name] += config.overload_penalty
            if same_group > 0:
                penalties[task.name] += config.correlation_penalty * same_group

            if bool(result["verified"]):
                verified_count += 1
                verified_by_task[task.name] += 1
                verified_utility += float(result["utility"])
                deposits[task.name] += float(result["deposit"])

        aco_config = base.ACOConfig(
            alpha=config.alpha,
            beta=config.beta,
            rho=config.rho,
            tau_min=config.tau_min,
            tau_max=config.tau_max,
            exploration=config.exploration,
            overload_penalty=config.overload_penalty,
            correlation_penalty=config.correlation_penalty,
        )
        for task in base.TASKS:
            pheromone[task.name] = base.update_pheromone(
                pheromone[task.name],
                deposits[task.name],
                penalties[task.name],
                aco_config,
            )

        epoch_duplicate_rate = epoch_duplicates / workers
        epoch_concentration = max(attempt_counts.values()) / workers
        regulation = update_regulation(
            regulation,
            epoch_duplicate_rate,
            epoch_concentration,
            config,
        )
        regulation_history.append(regulation)

    denominator = review_cost + compute_cost
    efficiency = verified_utility / denominator if denominator else 0.0
    coverage = sum(1 for value in verified_by_task.values() if value > 0)
    max_selection_share = max(selections.values()) / total_attempts if total_attempts else 0.0
    duplicate_rate = duplicate_attempts / total_attempts if total_attempts else 0.0

    ranked = sorted(base.TASKS, key=base.intrinsic_value, reverse=True)
    high_value = ranked[: max(2, len(ranked) // 4)]
    neglected_high_value = sum(1 for task in high_value if verified_by_task[task.name] == 0)

    return {
        "strategy": "homeostatic-hybrid",
        "seed": seed,
        "workers": workers,
        "epochs": epochs,
        "attempts": total_attempts,
        "verified_count": verified_count,
        "verified_utility": round(verified_utility, 6),
        "review_cost": round(review_cost, 6),
        "compute_cost": round(compute_cost, 6),
        "verified_utility_per_cost": round(efficiency, 9),
        "duplicate_rate": round(duplicate_rate, 6),
        "task_coverage": coverage,
        "max_selection_share": round(max_selection_share, 6),
        "neglected_high_value_tasks": neglected_high_value,
        "selections": selections,
        "verified_by_task": verified_by_task,
        "pheromone": {name: round(value, 6) for name, value in pheromone.items()},
        "regulation_initial": config.lambda_initial,
        "regulation_final": round(regulation, 6),
        "regulation_mean": round(sum(regulation_history) / len(regulation_history), 6),
    }


def run_comparison(seed_start: int = 1, seeds: int = 40, workers: int = 24, epochs: int = 50) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")

    strategies = ("capability", "aco", "homeostatic-hybrid")
    rows: Dict[str, List[Dict[str, object]]] = {name: [] for name in strategies}
    for offset in range(seeds):
        seed = seed_start + offset
        rows["capability"].append(base.run_strategy("capability", seed, workers, epochs))
        rows["aco"].append(base.run_strategy("aco", seed, workers, epochs))
        rows["homeostatic-hybrid"].append(run_hybrid(seed, workers, epochs))

    metrics = (
        "verified_utility_per_cost",
        "duplicate_rate",
        "task_coverage",
        "max_selection_share",
    )
    summary: Dict[str, Dict[str, float]] = {}
    for strategy, strategy_rows in rows.items():
        summary[strategy] = {
            metric: round(
                sum(float(row[metric]) for row in strategy_rows) / len(strategy_rows),
                9,
            )
            for metric in metrics
        }

    return {
        "experiment": "homeostatic-stigmergy-hybrid-v0",
        "model_warning": "Synthetic illustrative simulation; not empirical evidence about real contributors.",
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "config": asdict(HomeostaticConfig()),
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if args.seeds <= 0 or args.workers <= 0 or args.epochs <= 0:
        parser.error("seeds, workers, and epochs must be positive")

    print(json.dumps(
        run_comparison(args.seed_start, args.seeds, args.workers, args.epochs),
        indent=args.indent,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
