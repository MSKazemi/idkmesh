#!/usr/bin/env python3
"""Deterministic simulator for biology-inspired stigmergic task routing.

This is an experimental model, not a claim about real contributor behavior.
It compares four routing policies on the same synthetic task/worker ecology:
random, greedy, capability-only, and ACO-style stigmergic routing.

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


EPS = 1e-12


@dataclass(frozen=True)
class Task:
    name: str
    skill: str
    impact: float
    information_gain: float
    review_cost: float
    compute_cost: float
    risk: float
    accessibility: float
    base_success: float
    parallel_limit: int = 3


@dataclass(frozen=True)
class Worker:
    name: str
    group: str
    skills: Mapping[str, float]


@dataclass(frozen=True)
class ACOConfig:
    alpha: float = 0.70
    beta: float = 2.00
    rho: float = 0.12
    gamma: float = 0.75
    tau_min: float = 0.10
    tau_max: float = 4.00
    exploration: float = 0.08
    overload_penalty: float = 0.035
    correlation_penalty: float = 0.025


TASKS: Tuple[Task, ...] = (
    Task("schema", "code", 0.90, 0.72, 0.35, 0.28, 0.25, 0.62, 0.74, 3),
    Task("validator", "test", 0.95, 0.80, 0.48, 0.36, 0.34, 0.52, 0.67, 3),
    Task("security", "security", 0.92, 0.88, 0.60, 0.25, 0.55, 0.42, 0.55, 2),
    Task("docs", "docs", 0.62, 0.52, 0.16, 0.08, 0.08, 0.96, 0.88, 4),
    Task("benchmark", "research", 0.84, 0.93, 0.42, 0.33, 0.22, 0.70, 0.63, 3),
    Task("integration", "code", 0.89, 0.68, 0.58, 0.47, 0.46, 0.44, 0.57, 2),
    Task("onboarding", "community", 0.67, 0.74, 0.18, 0.06, 0.06, 1.00, 0.90, 4),
    Task("reproduction", "test", 0.76, 0.86, 0.29, 0.18, 0.13, 0.82, 0.78, 3),
)

SKILLS = ("code", "test", "security", "docs", "research", "community")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def make_workers(count: int, rng: random.Random) -> List[Worker]:
    """Create heterogeneous workers with repeated groups to model correlation."""
    workers: List[Worker] = []
    for i in range(count):
        specialty = SKILLS[i % len(SKILLS)]
        group = f"family-{i % max(3, min(7, count // 4 or 1))}"
        skills: Dict[str, float] = {}
        for skill in SKILLS:
            if skill == specialty:
                value = rng.uniform(0.72, 0.98)
            else:
                value = rng.uniform(0.18, 0.70)
            skills[skill] = value
        workers.append(Worker(f"worker-{i:03d}", group, skills))
    return workers


def intrinsic_value(task: Task) -> float:
    """Task value without worker-specific capability or historical signal."""
    return (
        task.impact
        * task.information_gain
        * task.accessibility
        / ((1.0 + task.review_cost) * (1.0 + task.risk))
    )


def heuristic(
    worker: Worker,
    task: Task,
    attempt_count: int,
    same_group_attempts: int,
    config: ACOConfig,
) -> float:
    """Local desirability eta(a,j) with diversity and congestion discounts."""
    skill_match = clamp(float(worker.skills.get(task.skill, 0.0)), 0.02, 1.0)
    diversity = 1.0 / (1.0 + same_group_attempts)
    congestion = 1.0 / math.pow(1.0 + attempt_count, config.gamma)
    numerator = (
        task.impact
        * task.information_gain
        * skill_match
        * diversity
        * task.accessibility
        * congestion
    )
    denominator = (1.0 + task.review_cost) * (1.0 + task.risk)
    return max(EPS, numerator / denominator)


def aco_probabilities(
    worker: Worker,
    tasks: Sequence[Task],
    pheromone: Mapping[str, float],
    attempt_counts: Mapping[str, int],
    group_attempts: Mapping[Tuple[str, str], int],
    config: ACOConfig,
) -> List[float]:
    """Return normalized ACO selection probabilities for one worker."""
    weights: List[float] = []
    for task in tasks:
        eta = heuristic(
            worker,
            task,
            attempt_counts.get(task.name, 0),
            group_attempts.get((task.name, worker.group), 0),
            config,
        )
        tau = clamp(pheromone.get(task.name, config.tau_min), config.tau_min, config.tau_max)
        weights.append(math.pow(tau, config.alpha) * math.pow(eta, config.beta))

    total = sum(weights)
    if total <= EPS:
        return [1.0 / len(tasks)] * len(tasks)
    return [weight / total for weight in weights]


def weighted_choice(items: Sequence[Task], probabilities: Sequence[float], rng: random.Random) -> Task:
    needle = rng.random()
    cumulative = 0.0
    for item, probability in zip(items, probabilities):
        cumulative += probability
        if needle <= cumulative:
            return item
    return items[-1]


def choose_task(
    strategy: str,
    worker: Worker,
    tasks: Sequence[Task],
    pheromone: Mapping[str, float],
    attempt_counts: Mapping[str, int],
    group_attempts: Mapping[Tuple[str, str], int],
    config: ACOConfig,
    rng: random.Random,
) -> Task:
    if strategy == "random":
        return rng.choice(list(tasks))

    if strategy == "greedy":
        return max(tasks, key=lambda task: (intrinsic_value(task), task.name))

    if strategy == "capability":
        return max(
            tasks,
            key=lambda task: (
                worker.skills.get(task.skill, 0.0) * intrinsic_value(task),
                task.name,
            ),
        )

    if strategy != "aco":
        raise ValueError(f"unknown strategy: {strategy}")

    if rng.random() < config.exploration:
        return rng.choice(list(tasks))

    probabilities = aco_probabilities(
        worker, tasks, pheromone, attempt_counts, group_attempts, config
    )
    return weighted_choice(tasks, probabilities, rng)


def update_pheromone(
    old_tau: float,
    deposit: float,
    penalty: float,
    config: ACOConfig,
) -> float:
    """Apply evaporation, evidence deposit, penalty, and pheromone bounds."""
    updated = (1.0 - config.rho) * old_tau + deposit - penalty
    return clamp(updated, config.tau_min, config.tau_max)


def attempt(
    worker: Worker,
    task: Task,
    same_group_attempts: int,
    rng: random.Random,
) -> Dict[str, float | bool]:
    """Sample one synthetic work attempt and independent-verification result."""
    skill = clamp(float(worker.skills.get(task.skill, 0.0)), 0.0, 1.0)
    success_probability = clamp(task.base_success * (0.45 + 0.70 * skill), 0.05, 0.97)
    useful = rng.random() < success_probability

    verification_strength = clamp(0.94 - 0.22 * task.risk, 0.65, 0.96)
    verified = useful and rng.random() < verification_strength

    diversity = 1.0 / (1.0 + same_group_attempts)
    quality = task.impact * (0.55 + 0.45 * skill)
    descendant_value = 0.45 + 0.55 * task.accessibility
    utility = task.impact * task.information_gain * (0.60 + 0.40 * skill) if verified else 0.0

    deposit = 0.0
    if verified:
        deposit = (
            quality
            * verification_strength
            * diversity
            * descendant_value
            / (1.0 + task.review_cost + task.compute_cost)
        )

    return {
        "useful": useful,
        "verified": verified,
        "utility": utility,
        "deposit": deposit,
        "verification_strength": verification_strength,
    }


def run_strategy(
    strategy: str,
    seed: int = 7,
    workers: int = 24,
    epochs: int = 50,
    config: ACOConfig | None = None,
) -> Dict[str, object]:
    config = config or ACOConfig()
    rng = random.Random(seed)
    population = make_workers(workers, rng)
    pheromone: Dict[str, float] = {task.name: 1.0 for task in TASKS}

    total_attempts = 0
    verified_count = 0
    verified_utility = 0.0
    review_cost = 0.0
    compute_cost = 0.0
    duplicate_attempts = 0
    selections: Dict[str, int] = {task.name: 0 for task in TASKS}
    verified_by_task: Dict[str, int] = {task.name: 0 for task in TASKS}

    for _epoch in range(epochs):
        attempt_counts: Dict[str, int] = {task.name: 0 for task in TASKS}
        group_attempts: Dict[Tuple[str, str], int] = {}
        deposits: Dict[str, float] = {task.name: 0.0 for task in TASKS}
        penalties: Dict[str, float] = {task.name: 0.0 for task in TASKS}

        order = list(population)
        rng.shuffle(order)

        for worker in order:
            task = choose_task(
                strategy,
                worker,
                TASKS,
                pheromone,
                attempt_counts,
                group_attempts,
                config,
                rng,
            )
            same_group = group_attempts.get((task.name, worker.group), 0)
            result = attempt(worker, task, same_group, rng)

            total_attempts += 1
            selections[task.name] += 1
            attempt_counts[task.name] += 1
            group_attempts[(task.name, worker.group)] = same_group + 1
            review_cost += task.review_cost
            compute_cost += task.compute_cost

            if attempt_counts[task.name] > task.parallel_limit:
                duplicate_attempts += 1
                penalties[task.name] += config.overload_penalty
            if same_group > 0:
                penalties[task.name] += config.correlation_penalty * same_group

            if bool(result["verified"]):
                verified_count += 1
                verified_by_task[task.name] += 1
                verified_utility += float(result["utility"])
                deposits[task.name] += float(result["deposit"])

        if strategy == "aco":
            for task in TASKS:
                pheromone[task.name] = update_pheromone(
                    pheromone[task.name],
                    deposits[task.name],
                    penalties[task.name],
                    config,
                )

    denominator = review_cost + compute_cost
    efficiency = verified_utility / denominator if denominator else 0.0
    coverage = sum(1 for value in verified_by_task.values() if value > 0)
    max_selection_share = max(selections.values()) / total_attempts if total_attempts else 0.0
    duplicate_rate = duplicate_attempts / total_attempts if total_attempts else 0.0

    ranked = sorted(TASKS, key=intrinsic_value, reverse=True)
    high_value = ranked[: max(2, len(ranked) // 4)]
    neglected_high_value = sum(1 for task in high_value if verified_by_task[task.name] == 0)

    return {
        "strategy": strategy,
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
    }


def run(
    strategy: str = "all",
    seed: int = 7,
    workers: int = 24,
    epochs: int = 50,
    config: ACOConfig | None = None,
) -> Dict[str, object]:
    strategies = ("random", "greedy", "capability", "aco") if strategy == "all" else (strategy,)
    results = [
        run_strategy(name, seed=seed + index * 100003, workers=workers, epochs=epochs, config=config)
        for index, name in enumerate(strategies)
    ]
    return {
        "experiment": "aco-stigmergic-task-routing-v0",
        "model_warning": "Synthetic illustrative simulation; not empirical evidence about real contributors.",
        "config": asdict(config or ACOConfig()),
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=("all", "random", "greedy", "capability", "aco"), default="all")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if args.workers <= 0 or args.epochs <= 0:
        parser.error("workers and epochs must be positive")

    payload = run(args.strategy, args.seed, args.workers, args.epochs)
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
