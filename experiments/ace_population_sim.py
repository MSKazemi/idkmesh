#!/usr/bin/env python3
"""Illustrative ACE population simulation.

This is not an empirical model of GitHub communities. It is a small,
deterministic-by-seed sandbox for testing ACE intuitions before granting
more automation authority.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    spawn_rate: float
    verification_probability: float
    review_capacity: float
    carrying_capacity: float
    tau: float
    decay: float
    review_cost_per_seed: float
    governed_spawning: bool
    description: str


@dataclass
class State:
    generation: int = 0
    active_parents: int = 1
    total_parent_opportunities: int = 0
    seeds_created: int = 0
    verified_descendants: int = 0
    review_load: float = 0.0
    credit: float = 0.0
    peak_review_load: float = 0.0


SCENARIOS = {
    "under-reproduction": Scenario(
        name="under-reproduction",
        spawn_rate=0.75,
        verification_probability=0.55,
        review_capacity=3.0,
        carrying_capacity=6.0,
        tau=1.5,
        decay=0.92,
        review_cost_per_seed=1.0,
        governed_spawning=True,
        description="Too little verified reproduction; the lineage tends to die out.",
    ),
    "healthy-reproduction": Scenario(
        name="healthy-reproduction",
        spawn_rate=1.85,
        verification_probability=0.82,
        review_capacity=7.0,
        carrying_capacity=10.0,
        tau=2.0,
        decay=0.94,
        review_cost_per_seed=1.0,
        governed_spawning=True,
        description=(
            "Capacity-governed spawning supports growth while keeping review load bounded."
        ),
    ),
    "overload": Scenario(
        name="overload",
        spawn_rate=3.6,
        verification_probability=0.82,
        review_capacity=2.5,
        carrying_capacity=8.0,
        tau=1.5,
        decay=0.96,
        review_cost_per_seed=1.0,
        governed_spawning=False,
        description=(
            "Raw activity is maximized without a carrying-capacity gate; review debt dominates."
        ),
    ),
}


def capacity_multiplier(load: float, k: float, tau: float) -> float:
    """Logistic carrying-capacity gate used by ACE."""
    return 1.0 / (1.0 + math.exp((load - k) / tau))


def draw_count(expected: float, rng: random.Random) -> int:
    """Small standard-library count sampler with E[X] approximately expected."""
    if expected <= 0:
        return 0
    whole = int(expected)
    return whole + int(rng.random() < (expected - whole))


def run_scenario(scenario: Scenario, *, steps: int, seed: int) -> dict:
    """Run one branching/review-capacity scenario and return inspectable evidence."""
    rng = random.Random(seed)
    state = State()
    history = []

    for generation in range(1, steps + 1):
        state.generation = generation

        # Existing verified descendants are the parents eligible to reproduce
        # in the next generation.
        parents = state.active_parents
        state.total_parent_opportunities += parents

        before_capacity = capacity_multiplier(
            state.review_load, scenario.carrying_capacity, scenario.tau
        )
        spawn_gate = before_capacity if scenario.governed_spawning else 1.0
        expected_seeds = parents * scenario.spawn_rate * spawn_gate
        new_seeds = draw_count(expected_seeds, rng)
        state.seeds_created += new_seeds
        state.review_load += new_seeds * scenario.review_cost_per_seed
        state.peak_review_load = max(state.peak_review_load, state.review_load)

        # Verification quality falls when the review system is overloaded.
        after_capacity = capacity_multiplier(
            state.review_load, scenario.carrying_capacity, scenario.tau
        )
        effective_verify_p = min(
            1.0, scenario.verification_probability * after_capacity
        )
        verified = sum(
            1 for _ in range(new_seeds) if rng.random() < effective_verify_p
        )
        state.verified_descendants += verified

        # Reviewer capacity removes bounded work from the queue each generation.
        state.review_load = max(0.0, state.review_load - scenario.review_capacity)

        novelty = 1.0 / math.sqrt(1.0 + state.seeds_created)
        state.credit = (
            scenario.decay * state.credit
            + new_seeds * novelty * before_capacity
        )

        # A verified descendant can itself become a parent. Keep extinct
        # populations extinct rather than injecting artificial new activity.
        state.active_parents = verified

        r_community = (
            state.verified_descendants / state.total_parent_opportunities
            if state.total_parent_opportunities
            else 0.0
        )
        useful_per_seed = (
            state.verified_descendants / state.seeds_created
            if state.seeds_created
            else 0.0
        )

        history.append(
            {
                "generation": generation,
                "parents": parents,
                "new_seeds": new_seeds,
                "verified": verified,
                "capacity_before": round(before_capacity, 6),
                "review_load": round(state.review_load, 6),
                "credit": round(state.credit, 6),
                "r_community_cumulative": round(r_community, 6),
                "verified_per_seed_cumulative": round(useful_per_seed, 6),
            }
        )

        if state.active_parents == 0 and state.review_load == 0:
            break

    final_r = (
        state.verified_descendants / state.total_parent_opportunities
        if state.total_parent_opportunities
        else 0.0
    )
    efficiency = (
        state.verified_descendants
        / (state.seeds_created + state.review_load + 1.0)
    )

    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "seed": seed,
        "requested_steps": steps,
        "completed_generations": state.generation,
        "parameters": asdict(scenario),
        "summary": {
            "parents_observed": state.total_parent_opportunities,
            "seeds_created": state.seeds_created,
            "verified_descendants": state.verified_descendants,
            "r_community": round(final_r, 6),
            "final_review_load": round(state.review_load, 6),
            "peak_review_load": round(state.peak_review_load, 6),
            "final_credit": round(state.credit, 6),
            "verified_value_per_total_burden": round(efficiency, 6),
        },
        "history": history,
    }


def print_table(results: list[dict]) -> None:
    headers = (
        "scenario",
        "gens",
        "seeds",
        "verified",
        "R_community",
        "peak_load",
        "value/burden",
    )
    print(" | ".join(headers))
    print("-" * 100)
    for result in results:
        summary = result["summary"]
        print(
            f'{result["scenario"]} | '
            f'{result["completed_generations"]} | '
            f'{summary["seeds_created"]} | '
            f'{summary["verified_descendants"]} | '
            f'{summary["r_community"]:.3f} | '
            f'{summary["peak_review_load"]:.2f} | '
            f'{summary["verified_value_per_total_burden"]:.3f}'
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS.keys()],
        default="all",
        help="Scenario to run (default: all).",
    )
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the compact comparison table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.steps <= 0:
        raise SystemExit("--steps must be positive")

    selected = (
        list(SCENARIOS.values())
        if args.scenario == "all"
        else [SCENARIOS[args.scenario]]
    )
    results = [
        run_scenario(scenario, steps=args.steps, seed=args.seed)
        for scenario in selected
    ]

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
