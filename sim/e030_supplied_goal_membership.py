#!/usr/bin/env python3
"""E030 -- does the archive's advantage depend on being handed the future goal?

E024 recorded its own sharpest limitation: "the plausible goals are supplied by
the experimenter rather than learned, and given an informative set of four
plausible goals, including the later goal".  That is literal.  The environment
switches to :data:`emergence_sim.CHANGED_GOAL`, and ``CHANGED_GOAL`` is a member
of :data:`emergence_sim.PLAUSIBLE_GOALS`, which is what the Quality-Diversity
archive optimizes ``robust_quality`` over and what the majority swarm draws its
per-agent belief from.  Both arms are handed the answer before the question is
asked; ``random``, ``scalar`` and ``planner`` are not.

The clean way to test that is not to change the goal set -- changing it changes
its size, its dispersion and its content all at once.  It is to change *which
goal the environment switches to*, leaving the supplied set byte-identical.  The
manipulation is then exactly one bit: is the future goal a member of the set the
arms hold, or is it not?

:data:`UNHELD_GOAL` is matched to ``CHANGED_GOAL`` on every property that could
explain a difference other than membership:

* a comparable distance from ``INITIAL_GOAL``, so the change is the same size;
* a comparable distance to the nearest hypothesis the arms actually hold,
  measured against ``CHANGED_GOAL``'s distance to the nearest *other* member, so
  the substitute is no more isolated from the set than the published goal is
  from the rest of it;
* a comparable attainable ceiling over a fixed pool of viable candidates, so one
  goal is not simply easier to satisfy than the other;
* **a comparable transfer regret** -- how much utility the artifact that is
  optimal under ``INITIAL_GOAL`` gives up under the new goal. This one is not
  optional. The first substitute this experiment tried matched on Euclidean
  distance alone and turned out to be 28% cheaper to transfer to, which handed
  the fixed-objective arms a ``+2.9`` AUC gift and would have been read as the
  archive losing its lead.

The reordering of trait priorities is *not* matched: both goals promote
adaptability to first place, but the substitute promotes reliability where the
published goal promotes security. That is reported as a limitation rather than
forced, because over-constraining the substitute leaves no admissible goal at
all on this simplex.

What it is not is a member.  Everything else in the benchmark is untouched: the
arms, the budget contract, the panel, the seeds, the goal set.

This isolates the *goal-supply* confound only.  The defect channel stays
disarmed by default, because E027 and E028 already cover it and arming both at
once would make an effect unattributable.
"""

from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim import e027_defect_propagation as e027  # noqa: E402
from sim import matched_budget_emergence as mbe  # noqa: E402
import sim.emergence_sim as sim  # noqa: E402

EXPERIMENT_ID = "E030"

# The module `matched_budget_emergence` loads emergence_sim.py by file path, so
# `mbe.sim` is a DIFFERENT module object from `sim.emergence_sim`. Any goal swap
# has to reach both or the arms and the audit disagree inside one run. E028 hit
# exactly this.
_ARENA = mbe.sim

# Matched to CHANGED_GOAL on change size, distance to the nearest held
# hypothesis, and reordering structure; not a member of PLAUSIBLE_GOALS.
# The numbers in GOAL_PROVENANCE are measured by `--mode parity`, not asserted.
UNHELD_GOAL: Tuple[float, ...] = (0.24, 0.43, 0.06, 0.13, 0.14)

CONDITIONS = ("held", "unheld")

# Reused from E027 rather than redefined, so a panel edit cannot silently make
# two experiments disagree about what "the measured panel" means.
PANELS = e027.PANELS
PANEL_ORDER = e027.PANEL_ORDER

DEFAULT_SEEDS = 100
DEFAULT_AGENTS = 64
DEFAULT_GENERATIONS = 50
DEFAULT_CHANGE_AT = 25
DEFAULT_BINS = 8


def _rank(goal: Sequence[float]) -> Tuple[int, ...]:
    """Trait indices ordered by descending weight, ties broken by index."""
    return tuple(sorted(range(len(goal)), key=lambda i: (-goal[i], i)))


def _dispersion(goals: Sequence[Sequence[float]]) -> float:
    pairs = list(itertools.combinations(goals, 2))
    return statistics.fmean(math.dist(a, b) for a, b in pairs)


def goal_parity() -> Dict[str, Any]:
    """Measure every property the substitute goal is supposed to match.

    Reported rather than asserted: if a future edit to the goal set breaks the
    match, this shows it instead of hiding it behind a passing test.
    """
    initial = sim.INITIAL_GOAL
    changed = sim.CHANGED_GOAL
    supplied = sim.PLAUSIBLE_GOALS
    others = tuple(goal for goal in supplied if goal != changed)
    return {
        "supplied_goals": [list(goal) for goal in supplied],
        "held_goal": list(changed),
        "unheld_goal": list(UNHELD_GOAL),
        "held_goal_is_a_member": changed in supplied,
        "unheld_goal_is_a_member": UNHELD_GOAL in supplied,
        "unheld_goal_sums_to_one": abs(sum(UNHELD_GOAL) - 1.0) < 1e-9,
        "distance_from_initial": {
            "held": round(math.dist(initial, changed), 6),
            "unheld": round(math.dist(initial, UNHELD_GOAL), 6),
        },
        # For the held goal this is the distance to the nearest OTHER member,
        # which is the only fair comparison: a goal cannot be 0.0 from itself
        # and also be the thing under test.
        "distance_to_nearest_held_hypothesis": {
            "held_excluding_itself": round(min(math.dist(changed, g) for g in others), 6),
            "unheld": round(min(math.dist(UNHELD_GOAL, g) for g in supplied), 6),
        },
        "trait_rank": {
            "initial": list(_rank(initial)),
            "held": list(_rank(changed)),
            "unheld": list(_rank(UNHELD_GOAL)),
        },
        "supplied_set_dispersion": round(_dispersion(supplied), 6),
        # Reported so the substitute cannot quietly be the published goal in
        # disguise: it must not sit closer to it than the set's own spread.
        "distance_between_held_and_unheld": round(math.dist(changed, UNHELD_GOAL), 6),
    }


def _reference_pool(draws: int, seed: int) -> List[Tuple[float, ...]]:
    """One fixed pool of viable candidates, so every goal is judged on the same
    artifacts and a difference between goals cannot be sampling noise."""
    rng = random.Random(seed)
    pool: List[Tuple[float, ...]] = []
    for _ in range(draws):
        candidate = sim.Candidate.random(rng)
        if sim.viable(candidate):
            pool.append(candidate.traits)
    return pool


def goal_difficulty(draws: int = 200_000, seed: int = 20260830) -> Dict[str, Any]:
    """Attainable ceiling and transfer regret for each goal, on one shared pool.

    ``transfer_regret`` is the gap between the best value available under a goal
    and the value the ``INITIAL_GOAL``-optimal artifact achieves under it -- the
    penalty an arm committed to the old objective pays when the world moves. If
    the two goals disagree here, the fixed-objective baselines get a different
    ride under each condition and no comparison of the other arms is readable.
    """
    pool = _reference_pool(draws, seed)
    if not pool:  # pragma: no cover - only with a degenerate draw count
        raise ValueError("reference pool is empty")
    goals = {
        "initial": sim.INITIAL_GOAL,
        "held": sim.CHANGED_GOAL,
        "unheld": UNHELD_GOAL,
    }
    initial_optimum = max(pool, key=lambda traits: sim.unchecked_utility(
        sim.Candidate(traits), sim.INITIAL_GOAL
    ))
    report: Dict[str, Any] = {
        "draws": draws,
        "seed": seed,
        "viable_pool": len(pool),
        "initial_optimal_traits": [round(x, 6) for x in initial_optimum],
        "attainable_ceiling": {},
        "mean_over_viable": {},
        "transfer_regret_from_initial_optimum": {},
    }
    for name, goal in goals.items():
        values = [sim.unchecked_utility(sim.Candidate(t), goal) for t in pool]
        ceiling = max(values)
        report["attainable_ceiling"][name] = round(ceiling, 6)
        report["mean_over_viable"][name] = round(statistics.fmean(values), 6)
        report["transfer_regret_from_initial_optimum"][name] = round(
            ceiling - sim.unchecked_utility(sim.Candidate(initial_optimum), goal), 6
        )
    # The pool's argmax is not the artifact a committed evolutionary arm actually
    # arrives at, and the two transfer differently. Measuring only the first would
    # hide a residual mismatch that lands entirely on the fixed-objective arms.
    report["evolved_initial_elite_utility"] = evolved_initial_transfer()
    return report


def evolved_initial_transfer(seeds: int = 60, agents: int = 64, generations: int = 24) -> Dict[str, Any]:
    """Score the artifact an INITIAL-committed run converges to under each goal.

    Reproduces the fixed-scalar arm's pre-change elite with a perfect panel, then
    reads it under both future goals. Any gap here is a cost paid only by arms
    committed to the old objective, which is why the lead statistic is measured
    against an arm that commits to nothing.
    """
    scores = {"held": [], "unheld": []}
    elite_count = max(2, min(32, agents // 4))
    for seed in range(1, seeds + 1):
        rng = random.Random(seed)
        population = [
            candidate
            for candidate in (sim.Candidate.random(rng) for _ in range(max(8, agents)))
            if sim.viable(candidate)
        ] or [sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5))]
        for _ in range(generations):
            ranked = sorted(
                population, key=lambda c: sim.utility(c, sim.INITIAL_GOAL), reverse=True
            )
            elites = ranked[:elite_count]
            offspring: List["sim.Candidate"] = []
            while len(offspring) < agents:
                child = rng.choice(elites).mutate(rng)
                if sim.viable(child):
                    offspring.append(child)
            population = elites + offspring
        elite = max(population, key=lambda c: sim.utility(c, sim.INITIAL_GOAL))
        scores["held"].append(sim.unchecked_utility(elite, sim.CHANGED_GOAL))
        scores["unheld"].append(sim.unchecked_utility(elite, UNHELD_GOAL))
    held = statistics.fmean(scores["held"])
    unheld = statistics.fmean(scores["unheld"])
    return {
        "seeds": seeds,
        "held": round(held, 6),
        "unheld": round(unheld, 6),
        "unheld_minus_held": round(unheld - held, 6),
        "note": "A negative gap means the substitute goal is harder for an arm "
        "committed to the old objective. It does not affect the reference arm, "
        "which commits to nothing.",
    }


@contextlib.contextmanager
def future_goal(goal: Sequence[float]):
    """Point the environment's post-change goal at ``goal`` in every module.

    ``PLAUSIBLE_GOALS`` is deliberately NOT touched. The arms keep holding
    exactly the hypotheses they published with; only what the environment
    becomes changes. Restored on the way out even if the block raises.
    """
    modules = [sim] if _ARENA is sim else [sim, _ARENA]
    saved = [(module, module.CHANGED_GOAL) for module in modules]
    try:
        for module in modules:
            module.CHANGED_GOAL = tuple(goal)
        yield tuple(goal)
    finally:
        for module, original in saved:
            module.CHANGED_GOAL = original


def _goal_for(condition: str) -> Tuple[float, ...]:
    if condition == "held":
        return sim.CHANGED_GOAL
    if condition == "unheld":
        return UNHELD_GOAL
    raise ValueError(f"unknown condition: {condition!r}")


def per_seed_auc(
    *,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None",
    goal: Sequence[float],
) -> Dict[str, List[float]]:
    """Post-change utility AUC per seed per arm, with the environment at ``goal``.

    Per seed rather than aggregated, because the comparison that matters is
    paired: the same seed under a held and an unheld future goal.
    """
    values: Dict[str, List[float]] = {arm: [] for arm in mbe.STRATEGIES}
    with future_goal(goal):
        for offset in range(seeds):
            record = mbe.run_seed(
                seed=seed_start + offset,
                agents=agents,
                generations=generations,
                change_at=change_at,
                bins=bins,
                verification=verification,
            )
            for arm_result in record["results"]:
                values[arm_result["strategy"]].append(
                    arm_result["post_change_utility_auc"]
                )
    return values


def paired_sweep(
    *,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = 1,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    verification: "sim.VerificationConfig | None" = None,
) -> Dict[str, Dict[str, List[float]]]:
    """The same seeds run twice, once per condition."""
    return {
        condition: per_seed_auc(
            seeds=seeds,
            seed_start=seed_start,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verification=verification,
            goal=_goal_for(condition),
        )
        for condition in CONDITIONS
    }


def _catastrophe_threshold(generations: int, change_at: int) -> float:
    """E024's absolute cutoff, reused so counts here compare to E027's and E028's."""
    return mbe.CATASTROPHE_FRACTION * (generations - change_at)


def _advantage_table(
    paired: Dict[str, Dict[str, List[float]]], threshold: float
) -> Dict[str, Any]:
    """Each arm's mean, and its lead over the best arm that holds no hypothesis.

    The raw mean is NOT comparable across conditions: the environment's goal
    itself changed, so every arm moves and part of that movement is only the new
    goal being slightly easier or harder. What is comparable is how far an arm
    that consults the supplied set gets ahead of the arms that never consult it.
    """
    hypothesis_free = ("random", "scalar", "planner")
    hypothesis_holding = ("qd", "majority")
    table: Dict[str, Any] = {"metric": "post_change_utility_auc"}
    for condition in CONDITIONS:
        values = paired[condition]
        means = {arm: statistics.fmean(values[arm]) for arm in mbe.STRATEGIES}
        reference = max(means[arm] for arm in hypothesis_free)
        table[condition] = {
            "means": {arm: round(means[arm], 6) for arm in mbe.STRATEGIES},
            "best_hypothesis_free_arm": round(reference, 6),
            "lead_over_hypothesis_free": {
                arm: round(means[arm] - reference, 6) for arm in hypothesis_holding
            },
            # Named, not just valued: if the reference ever switches arms between
            # conditions the lead is comparing two different things.
            "reference_arm": max(hypothesis_free, key=lambda arm: means[arm]),
            "catastrophic_seeds": {
                arm: sum(1 for value in values[arm] if value < threshold)
                for arm in mbe.STRATEGIES
            },
        }
    table["delta_unheld_minus_held"] = {
        arm: round(table["unheld"]["means"][arm] - table["held"]["means"][arm], 6)
        for arm in mbe.STRATEGIES
    }
    table["lead_delta_unheld_minus_held"] = {
        arm: round(
            table["unheld"]["lead_over_hypothesis_free"][arm]
            - table["held"]["lead_over_hypothesis_free"][arm],
            6,
        )
        for arm in hypothesis_holding
    }
    # Paired over seeds: how often the same seed does better without the answer.
    table["paired_seed_wins_unheld_over_held"] = {
        arm: sum(
            1
            for without, with_answer in zip(paired["unheld"][arm], paired["held"][arm])
            if without > with_answer
        )
        for arm in mbe.STRATEGIES
    }
    table["hypothesis_free_arms"] = list(hypothesis_free)
    table["hypothesis_holding_arms"] = list(hypothesis_holding)
    table["catastrophe_utility_auc_threshold"] = round(threshold, 6)
    return table


def matrix(
    *,
    panels: Dict[str, "sim.VerificationConfig"],
    panel_order: Sequence[str],
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = 1,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    difficulty_draws: int = 200_000,
) -> Dict[str, Any]:
    threshold = _catastrophe_threshold(generations, change_at)
    cells: List[Dict[str, Any]] = []
    for name in panel_order:
        paired = paired_sweep(
            seeds=seeds,
            seed_start=seed_start,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verification=panels[name],
        )
        cells.append({"panel": name, "advantage": _advantage_table(paired, threshold)})
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "supplied-goal-membership-v1",
        "metric": "post_change_utility_auc",
        "seeds": seeds,
        "seed_start": seed_start,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "bins": bins,
        "catastrophe_utility_auc_threshold": round(threshold, 6),
        "goal_parity": goal_parity(),
        "goal_difficulty": goal_difficulty(draws=difficulty_draws),
        "cells": cells,
        "limitations": [
            "The defect channel is disarmed. E027 and E028 cover it; arming both "
            "confounds at once would make an effect unattributable to either.",
            "The substitute goal is one point, not a distribution over unheld "
            "goals. It is matched on change size, isolation from the held set "
            "and reordering structure, but a single direction cannot rule out "
            "that this particular one is unusual.",
            "Only the environment's post-change goal moves. An arm that could "
            "UPDATE its hypotheses from evidence is not modelled here, so this "
            "measures the value of being handed the answer, not the cost of "
            "having to learn it.",
            "Raw means are not comparable across conditions -- the goal itself "
            "changed -- which is why the reported statistic is the lead over the "
            "arms that hold no hypothesis. The goal_difficulty block is what "
            "makes that lead readable, and it must be checked before the lead is.",
            "The two goals reorder trait priorities differently: both promote "
            "adaptability to first, but the substitute promotes reliability "
            "where the published goal promotes security. Matching that as well "
            "leaves no admissible goal on this simplex.",
        ],
    }


def _resolve_panels(
    selected: Sequence[str] | None,
) -> Tuple[Dict[str, "sim.VerificationConfig"], Tuple[str, ...]]:
    """Resolve --panel names, preserving the canonical order rather than argv's."""
    if not selected:
        return PANELS, PANEL_ORDER
    unknown = sorted(set(selected) - set(PANELS))
    if unknown:
        raise SystemExit(f"unknown panel(s): {', '.join(unknown)}")
    order = tuple(name for name in PANEL_ORDER if name in set(selected))
    return {name: PANELS[name] for name in order}, order


def _json_default(value: Any) -> Any:  # pragma: no cover - defensive
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("parity", "matrix"), default="parity")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--change-at", type=int, default=DEFAULT_CHANGE_AT)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--draws", type=int, default=200_000)
    parser.add_argument("--panel", action="append", default=None)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    if args.mode == "parity":
        payload = {
            "experiment_id": EXPERIMENT_ID,
            "goal_parity": goal_parity(),
            "goal_difficulty": goal_difficulty(draws=args.draws),
        }
    else:
        panels, order = _resolve_panels(args.panel)
        payload = matrix(
            panels=panels,
            panel_order=order,
            seeds=args.seeds,
            seed_start=args.seed_start,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            difficulty_draws=args.draws,
        )

    text = json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
