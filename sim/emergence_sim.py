#!/usr/bin/env python3
"""Minimal IDKMesh emergence simulator.

Compares three ways of searching under an initially vague objective:
  * random: unconstrained stochastic exploration plus hard viability gates;
  * scalar: evolution against one fixed scalar objective;
  * qd: constraint-guided Quality-Diversity archive over multiple plausible goals.

This is intentionally a small falsifiable model, not evidence that open-ended
collective intelligence will work in production.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple

TRAITS = ("reliability", "adaptability", "efficiency", "simplicity", "security")
BUDGET = 3.2
MIN_RELIABILITY = 0.25
MIN_SECURITY = 0.25

INITIAL_GOAL = (0.30, 0.10, 0.25, 0.20, 0.15)
CHANGED_GOAL = (0.15, 0.35, 0.10, 0.10, 0.30)
PLAUSIBLE_GOALS = (
    INITIAL_GOAL,
    CHANGED_GOAL,
    (0.25, 0.20, 0.15, 0.15, 0.25),
    (0.20, 0.15, 0.30, 0.20, 0.15),
)


@dataclass(frozen=True)
class Candidate:
    traits: Tuple[float, ...]

    @staticmethod
    def random(rng: random.Random) -> "Candidate":
        # Draw a random budget allocation with some slack. This creates genuine
        # trade-offs instead of allowing every trait to independently reach 1.
        raw = [rng.expovariate(1.0) for _ in TRAITS]
        total = sum(raw)
        spend = rng.uniform(BUDGET * 0.55, BUDGET)
        vals = [min(1.0, spend * x / total) for x in raw]
        return Candidate(_renormalize_budget(vals))

    def mutate(self, rng: random.Random, sigma: float = 0.12) -> "Candidate":
        vals = [max(0.0, min(1.0, x + rng.gauss(0.0, sigma))) for x in self.traits]
        return Candidate(_renormalize_budget(vals))


def _renormalize_budget(values: Sequence[float]) -> Tuple[float, ...]:
    vals = list(values)
    total = sum(vals)
    if total > BUDGET:
        scale = BUDGET / total
        vals = [x * scale for x in vals]
    return tuple(max(0.0, min(1.0, x)) for x in vals)


def viable(c: Candidate) -> bool:
    return (
        c.traits[0] >= MIN_RELIABILITY
        and c.traits[4] >= MIN_SECURITY
        and sum(c.traits) <= BUDGET + 1e-9
    )


def utility(c: Candidate, weights: Sequence[float]) -> float:
    if not viable(c):
        return 0.0
    # Interaction reward: reliability and security reinforce one another.
    interaction = 0.08 * math.sqrt(c.traits[0] * c.traits[4])
    return min(1.0, sum(w * x for w, x in zip(weights, c.traits)) + interaction)


def robust_quality(c: Candidate) -> float:
    if not viable(c):
        return 0.0
    scores = [utility(c, w) for w in PLAUSIBLE_GOALS]
    # Mean performance plus a smaller worst-case term rewards useful robustness
    # without collapsing all search onto one current objective.
    return 0.75 * mean(scores) + 0.25 * min(scores)


def niche(c: Candidate, bins: int = 8) -> Tuple[int, int]:
    # Two behavioral descriptors: adaptability and efficiency.
    a = min(bins - 1, int(c.traits[1] * bins))
    e = min(bins - 1, int(c.traits[2] * bins))
    return (a, e)


def _goal_at(generation: int, change_at: int) -> Tuple[float, ...]:
    return INITIAL_GOAL if generation < change_at else CHANGED_GOAL


def _best_actual(population: Iterable[Candidate], goal: Sequence[float]) -> float:
    return max((utility(c, goal) for c in population), default=0.0)


def run_random(rng: random.Random, agents: int, generations: int, change_at: int) -> Dict[str, object]:
    trace: List[float] = []
    viable_evaluations = 0
    for g in range(generations):
        batch = [Candidate.random(rng) for _ in range(agents)]
        viable_batch = [c for c in batch if viable(c)]
        viable_evaluations += len(viable_batch)
        trace.append(_best_actual(viable_batch, _goal_at(g, change_at)))
    return _summary("random", trace, viable_evaluations, archive_size=0, change_at=change_at)


def run_scalar(rng: random.Random, agents: int, generations: int, change_at: int) -> Dict[str, object]:
    population = [Candidate.random(rng) for _ in range(max(8, agents))]
    population = [c for c in population if viable(c)] or [Candidate((0.5, 0.4, 0.7, 0.4, 0.5))]
    trace: List[float] = []
    viable_evaluations = len(population)
    elite_count = max(2, min(32, agents // 4))

    for g in range(generations):
        # Deliberately fixed objective: models premature commitment to one
        # interpretation of an initially vague goal.
        ranked = sorted(population, key=lambda c: utility(c, INITIAL_GOAL), reverse=True)
        elites = ranked[:elite_count]
        offspring: List[Candidate] = []
        while len(offspring) < agents:
            child = rng.choice(elites).mutate(rng)
            if viable(child):
                offspring.append(child)
                viable_evaluations += 1
        population = elites + offspring
        trace.append(_best_actual(population, _goal_at(g, change_at)))
    return _summary("scalar", trace, viable_evaluations, archive_size=0, change_at=change_at)


def run_qd(rng: random.Random, agents: int, generations: int, change_at: int, bins: int = 8) -> Dict[str, object]:
    archive: Dict[Tuple[int, int], Candidate] = {}
    trace: List[float] = []
    viable_evaluations = 0

    def consider(c: Candidate) -> None:
        nonlocal viable_evaluations
        if not viable(c):
            return
        viable_evaluations += 1
        key = niche(c, bins)
        incumbent = archive.get(key)
        if incumbent is None or robust_quality(c) > robust_quality(incumbent):
            archive[key] = c

    for _ in range(max(agents, bins * bins)):
        consider(Candidate.random(rng))

    for g in range(generations):
        parents = list(archive.values())
        for _ in range(agents):
            if parents and rng.random() < 0.85:
                candidate = rng.choice(parents).mutate(rng)
            else:
                candidate = Candidate.random(rng)
            consider(candidate)
        trace.append(_best_actual(archive.values(), _goal_at(g, change_at)))

    return _summary("qd", trace, viable_evaluations, archive_size=len(archive), change_at=change_at)


def _summary(strategy: str, trace: List[float], viable_evaluations: int, archive_size: int, change_at: int) -> Dict[str, object]:
    pre_index = max(0, min(len(trace) - 1, change_at - 1))
    post_index = max(0, min(len(trace) - 1, change_at))
    final = trace[-1] if trace else 0.0
    pre = trace[pre_index] if trace else 0.0
    post = trace[post_index] if trace else 0.0

    # Recovery means reaching 95% of that strategy's eventual post-change level.
    target = 0.95 * final
    recovery = None
    for idx in range(post_index, len(trace)):
        if trace[idx] >= target:
            recovery = idx - post_index
            break

    post_trace = trace[post_index:] if trace else []
    return {
        "strategy": strategy,
        "pre_change_best": round(pre, 6),
        "post_change_immediate": round(post, 6),
        "post_change_mean": round(mean(post_trace), 6) if post_trace else 0.0,
        "final_best": round(final, 6),
        "recovery_generations": recovery,
        "viable_evaluations": viable_evaluations,
        "archive_size": archive_size,
        "trace": [round(x, 6) for x in trace],
    }


def run(strategy: str, seed: int, agents: int, generations: int, change_at: int, bins: int) -> Dict[str, object]:
    runners = {
        "random": lambda r: run_random(r, agents, generations, change_at),
        "scalar": lambda r: run_scalar(r, agents, generations, change_at),
        "qd": lambda r: run_qd(r, agents, generations, change_at, bins),
    }
    if strategy == "all":
        results = []
        for offset, name in enumerate(("random", "scalar", "qd")):
            results.append(runners[name](random.Random(seed + offset * 100003)))
        return {
            "experiment": "emergence-from-vague-goals-v0",
            "seed": seed,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "traits": list(TRAITS),
            "budget": BUDGET,
            "results": results,
        }
    return {
        "experiment": "emergence-from-vague-goals-v0",
        "seed": seed,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "traits": list(TRAITS),
        "budget": BUDGET,
        "results": [runners[strategy](random.Random(seed))],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=("random", "scalar", "qd", "all"), default="all")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--agents", type=int, default=200)
    parser.add_argument("--generations", type=int, default=120)
    parser.add_argument("--change-at", type=int, default=60)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.agents < 1:
        parser.error("--agents must be >= 1")
    if args.generations < 2:
        parser.error("--generations must be >= 2")
    if not 1 <= args.change_at < args.generations:
        parser.error("--change-at must satisfy 1 <= change-at < generations")
    if args.bins < 2:
        parser.error("--bins must be >= 2")
    return args


def main() -> None:
    args = parse_args()
    result = run(args.strategy, args.seed, args.agents, args.generations, args.change_at, args.bins)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
