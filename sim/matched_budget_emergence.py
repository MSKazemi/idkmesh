#!/usr/bin/env python3
"""Matched-evaluation-budget emergence benchmark for E024.

This module reuses the E011 landscape and candidate/verifier mechanics while
giving random, fixed-scalar, and Quality-Diversity search exactly the same
number of proposals and verification attempts.  It is a synthetic mechanism
test, not evidence of real-world system emergence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Callable, Dict, List, Sequence, Tuple

HERE = Path(__file__).resolve().parent
SIM_PATH = HERE / "emergence_sim.py"

spec = importlib.util.spec_from_file_location("emergence_sim", SIM_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)

STRATEGIES = ("random", "scalar", "qd")
EXPERIMENT_ID = "E024"
SUMMARY_METRICS = (
    "pre_change_best",
    "post_change_immediate",
    "post_change_mean",
    "post_change_utility_auc",
    "post_change_regret_auc",
    "final_best",
    "verification_accepts",
    "false_accept_rate",
    "false_reject_rate",
    "panel_disagreement_rate",
    "archive_size",
)


def _summary(
    strategy: str,
    trace: List[float],
    stats: "sim.VerificationStats",
    archive_size: int,
    change_at: int,
    evaluation_budget: int,
) -> Dict[str, object]:
    result = sim._summary(strategy, trace, stats, archive_size, change_at)
    post_trace = trace[change_at:]
    result.update(
        {
            "proposal_attempts": stats.attempts,
            "matched_evaluation_budget": evaluation_budget,
            "post_change_utility_auc": round(sum(post_trace), 6),
            "post_change_regret_auc": round(sum(1.0 - value for value in post_trace), 6),
        }
    )
    return result


def _random_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
) -> Dict[str, object]:
    del bins
    trace: List[float] = []
    stats = sim.VerificationStats()
    for generation in range(generations):
        proposals = [sim.Candidate.random(rng) for _ in range(agents)]
        accepted = [
            candidate
            for candidate in proposals
            if sim.verify_candidate(candidate, verifier_rng, verification, stats)
        ]
        trace.append(sim._best_actual(accepted, sim._goal_at(generation, change_at)))
    return _summary("random", trace, stats, 0, change_at, agents * generations)


def _scalar_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
) -> Dict[str, object]:
    del bins
    population: List["sim.Candidate"] = []
    trace: List[float] = []
    stats = sim.VerificationStats()
    elite_count = max(2, min(32, agents // 4))

    for generation in range(generations):
        ranked = sorted(
            population,
            key=lambda candidate: sim.utility(candidate, sim.INITIAL_GOAL),
            reverse=True,
        )
        elites = ranked[:elite_count]
        proposals = [
            rng.choice(elites).mutate(rng) if elites else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        accepted = [
            candidate
            for candidate in proposals
            if sim.verify_candidate(candidate, verifier_rng, verification, stats)
        ]
        population = elites + accepted
        trace.append(sim._best_actual(population, sim._goal_at(generation, change_at)))

    return _summary("scalar", trace, stats, 0, change_at, agents * generations)


def _qd_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
) -> Dict[str, object]:
    archive: Dict[Tuple[int, int], "sim.Candidate"] = {}
    trace: List[float] = []
    stats = sim.VerificationStats()

    for generation in range(generations):
        parents = list(archive.values())
        proposals = [
            rng.choice(parents).mutate(rng)
            if parents and rng.random() < 0.85
            else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            key = sim.niche(candidate, bins)
            incumbent = archive.get(key)
            if incumbent is None or sim.robust_quality(candidate) > sim.robust_quality(incumbent):
                archive[key] = candidate
        trace.append(sim._best_actual(archive.values(), sim._goal_at(generation, change_at)))

    return _summary("qd", trace, stats, len(archive), change_at, agents * generations)


RUNNERS: Dict[str, Callable[..., Dict[str, object]]] = {
    "random": _random_search,
    "scalar": _scalar_search,
    "qd": _qd_search,
}


def run_seed(
    seed: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None" = None,
) -> Dict[str, object]:
    if agents < 2:
        raise ValueError("agents must be >= 2")
    if generations < 2:
        raise ValueError("generations must be >= 2")
    if not 1 <= change_at < generations:
        raise ValueError("change_at must satisfy 1 <= change_at < generations")
    if bins < 2:
        raise ValueError("bins must be >= 2")

    verification = verification or sim.VerificationConfig()
    evaluation_budget = agents * generations
    results = []
    for offset, strategy in enumerate(STRATEGIES):
        strategy_seed = seed + offset * 100003
        result = RUNNERS[strategy](
            random.Random(strategy_seed),
            random.Random(strategy_seed ^ 0x5EED5EED),
            agents,
            generations,
            change_at,
            verification,
            bins,
        )
        if result["verification_attempts"] != evaluation_budget:
            raise RuntimeError(f"{strategy} violated the matched evaluation budget")
        results.append(result)

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "matched-budget-emergence-v1",
        "seed": seed,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "bins": bins,
        "budget_contract": {
            "unit": "candidate proposal plus one panel-verification attempt",
            "per_strategy": evaluation_budget,
            "includes_initialization": True,
            "retry_until_acceptance": False,
        },
        "verification": verification.as_dict(),
        "results": results,
    }


def _stats(values: Sequence[float]) -> Dict[str, float | int]:
    n = len(values)
    average = mean(values)
    standard_deviation = stdev(values) if n > 1 else 0.0
    half_width = 1.96 * standard_deviation / math.sqrt(n)
    return {
        "n": n,
        "mean": round(average, 6),
        "stdev": round(standard_deviation, 6),
        "ci95_low": round(average - half_width, 6),
        "ci95_high": round(average + half_width, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def sweep(
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None" = None,
) -> Dict[str, object]:
    if seeds < 2:
        raise ValueError("seeds must be >= 2")

    rows = {
        strategy: {metric: [] for metric in SUMMARY_METRICS}
        for strategy in STRATEGIES
    }
    qd_wins = {
        "qd_gt_random_post_change_utility_auc": 0,
        "qd_gt_scalar_post_change_utility_auc": 0,
    }

    for seed in range(seed_start, seed_start + seeds):
        result = run_seed(seed, agents, generations, change_at, bins, verification)
        by_strategy = {row["strategy"]: row for row in result["results"]}
        for strategy, row in by_strategy.items():
            for metric in SUMMARY_METRICS:
                rows[strategy][metric].append(float(row[metric]))

        qd_wins["qd_gt_random_post_change_utility_auc"] += int(
            by_strategy["qd"]["post_change_utility_auc"]
            > by_strategy["random"]["post_change_utility_auc"]
        )
        qd_wins["qd_gt_scalar_post_change_utility_auc"] += int(
            by_strategy["qd"]["post_change_utility_auc"]
            > by_strategy["scalar"]["post_change_utility_auc"]
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "matched-budget-emergence-sweep-v1",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "evaluation_budget_per_strategy_per_seed": agents * generations,
            "verification": (verification or sim.VerificationConfig()).as_dict(),
        },
        "aggregate": {
            strategy: {
                metric: _stats(values)
                for metric, values in metrics.items()
            }
            for strategy, metrics in rows.items()
        },
        "pairwise_wins": {
            key: {
                "wins": wins,
                "trials": seeds,
                "rate": round(wins / seeds, 6),
            }
            for key, wins in qd_wins.items()
        },
        "limitations": [
            "All candidates, goals, and verification outcomes are synthetic.",
            "One evaluation unit is a simulator proposal plus panel decision, not measured compute, energy, or human attention.",
            "Quality-Diversity is given the four predefined plausible goals; the Goal Graph does not yet learn from evidence.",
            "The three strategies receive equal evaluation counts, but their internal bookkeeping costs are not measured.",
            "The benchmark does not model churn, malicious workers, task dependencies, stigmergic traces, or post-integration defects.",
            "The legacy strategy-relative recovery_generations field remains in per-seed rows but is not aggregated; post-change utility/regret AUC is the comparable adaptation measure.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be >= 2")
    if args.agents < 2:
        parser.error("--agents must be >= 2")
    if args.generations < 2:
        parser.error("--generations must be >= 2")
    if not 1 <= args.change_at < args.generations:
        parser.error("--change-at must satisfy 1 <= change-at < generations")
    if args.bins < 2:
        parser.error("--bins must be >= 2")
    return args


def main() -> None:
    args = parse_args()
    result = sweep(
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
