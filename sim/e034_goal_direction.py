"""E034 -- the archive's failures are directional. Which direction?

E033 swept how far the future goal drifts from the supplied set and found the
Quality-Diversity archive's lead decays smoothly, reaching zero by ``0.35``. It
also found something it could not explain: two of its 42 matched goals put the
archive *behind* the arms that hold no hypothesis, one of them at ``100/100``
catastrophic seeds, and both put almost no weight on ``security`` (``0.002`` and
``0.009``). Across the four goals weighting ``security`` under ``0.05`` the mean
lead was ``-1.362``; across the other 38 it was ``+2.741``.

That was n=4, and all four sat at ``0.254`` or further from the box, so the
observation was confounded with the very distance E033 was sweeping. E033
recorded it as a hypothesis and not a finding.

E034 removes the confound by holding the distance still.

The shell
---------

Every goal measured here sits at :data:`SHELL_DISTANCE_TO_SUPPLIED` from the
nearest supplied hypothesis **and** :data:`SHELL_CHANGE_SIZE` from
``INITIAL_GOAL``, both within :data:`SHELL_TOLERANCE`. Distance to the box is
constant, change size is constant, and the only thing that varies is *where on
that shell* the goal sits.

``0.30`` is chosen because it is the E033 ring where per-goal outcomes were most
dispersed -- leads from ``-3.823`` to ``+3.709`` around a mean of ``+1.014``. If
direction explains anything, it has the most to explain there.

The three kinds of trait
------------------------

The arena treats its five traits differently, and the difference is structural
rather than cosmetic:

* :data:`FLOOR_TRAITS` -- ``reliability`` and ``security``. ``sim.viable``
  refuses any candidate scoring under ``0.25`` on either, so **every artifact
  that exists at all has already spent budget on both**, whether the goal values
  them or not.
* :data:`DESCRIPTOR_TRAITS` -- ``adaptability`` and ``efficiency``. ``sim.niche``
  bins the archive on exactly these two, so they are the axes along which the
  archive keeps its diversity.
* :data:`UNCONSTRAINED_TRAITS` -- ``simplicity``, which is none of the above. It
  is the control: an extreme weight on it is just as extreme a direction, with
  no structural story attached.

E034 sweeps the weight the future goal places on each of the five traits in
turn, from :data:`WEIGHT_TARGETS` ``0.02`` to ``0.40``, everywhere on the same
shell.

The prediction, stated before the run
-------------------------------------

If E033's hypothesis is right and the mechanism is the viability floor, the
archive's lead should **rise with the weight on the two floored traits** and be
flat in ``simplicity``. If instead the lead responds to any extreme direction,
``simplicity`` will move too, and the floor story is dead.

What this cannot separate
-------------------------

``sim.unchecked_utility`` adds ``0.08 * sqrt(reliability * security)`` -- an
interaction term over the *same* two traits the floor constrains. The two
floored traits are therefore special in two ways at once, and a result on them
cannot attribute the effect to the floor rather than to the interaction. The
descriptor and control traits carry no such ambiguity, so the design can still
say whether the effect is specific to the floored pair.

Weights also sum to one, so raising one trait's weight lowers the mean of the
other four. Every axis here is one trait against the rest, never one trait in
isolation; the five-axis design is what makes that readable, because a generic
"one weight is extreme" artifact would move every axis alike.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim import e030_supplied_goal_membership as e030  # noqa: E402
from sim import e033_goal_distance as e033  # noqa: E402
from sim import matched_budget_emergence as mbe  # noqa: E402
import sim.emergence_sim as sim  # noqa: E402

EXPERIMENT_ID = "E034"
EXPERIMENT = "goal-direction-at-fixed-distance-v1"

# The E033 ring with the widest per-goal spread, so direction has the most to
# explain, and E033's own matched change size so the two experiments' goals are
# drawn from the same population.
SHELL_DISTANCE_TO_SUPPLIED = 0.30
SHELL_CHANGE_SIZE = e033.MATCHED_CHANGE_SIZE
SHELL_TOLERANCE = 0.015

WEIGHT_TARGETS: Tuple[float, ...] = (0.02, 0.10, 0.20, 0.30, 0.40)
WEIGHT_TOLERANCE = 0.02

# Derived from the arena rather than asserted, so an edit to sim.viable or
# sim.niche shows up here instead of silently invalidating the categories.
FLOOR_TRAITS: Tuple[str, ...] = ("reliability", "security")
DESCRIPTOR_TRAITS: Tuple[str, ...] = ("adaptability", "efficiency")
UNCONSTRAINED_TRAITS: Tuple[str, ...] = ("simplicity",)

GOALS_PER_CELL = 4
POOL_DRAWS = 2_000_000
POOL_SEED = 20260831

DEFAULT_SEEDS = e033.DEFAULT_SEEDS
DEFAULT_SEED_START = e033.DEFAULT_SEED_START
DEFAULT_AGENTS = e033.DEFAULT_AGENTS
DEFAULT_GENERATIONS = e033.DEFAULT_GENERATIONS
DEFAULT_CHANGE_AT = e033.DEFAULT_CHANGE_AT
DEFAULT_BINS = e033.DEFAULT_BINS
DEFAULT_PANEL = e033.DEFAULT_PANEL


def trait_category(trait: str) -> str:
    if trait in FLOOR_TRAITS:
        return "floored"
    if trait in DESCRIPTOR_TRAITS:
        return "descriptor"
    return "unconstrained"


def trait_index(trait: str) -> int:
    return sim.TRAITS.index(trait)


def on_shell(
    goal: Sequence[float],
    *,
    distance: float = SHELL_DISTANCE_TO_SUPPLIED,
    change_size: float = SHELL_CHANGE_SIZE,
    tolerance: float = SHELL_TOLERANCE,
) -> bool:
    return (
        abs(e033.distance_to_supplied(goal) - distance) <= tolerance
        and abs(e033.distance_from_initial(goal) - change_size) <= tolerance
    )


def shell(
    pool: Sequence[Sequence[float]],
    *,
    distance: float = SHELL_DISTANCE_TO_SUPPLIED,
    change_size: float = SHELL_CHANGE_SIZE,
    tolerance: float = SHELL_TOLERANCE,
) -> List[Tuple[float, ...]]:
    """Every pool member at the fixed distance and the fixed change size."""
    return [
        tuple(goal)
        for goal in pool
        if on_shell(
            goal, distance=distance, change_size=change_size, tolerance=tolerance
        )
    ]


def cell_goals(
    members: Sequence[Sequence[float]],
    *,
    trait: str,
    target: float,
    count: int = GOALS_PER_CELL,
    tolerance: float = WEIGHT_TOLERANCE,
) -> List[Tuple[float, ...]]:
    """``count`` shell goals whose weight on ``trait`` is near ``target``.

    Farthest-point selection from the admissible cell, so the goals differ in
    every direction *except* the one being held, and a cell result cannot be one
    corner of the shell sampled repeatedly.
    """
    index = trait_index(trait)
    hits = [tuple(g) for g in members if abs(g[index] - target) <= tolerance]
    if len(hits) < count:
        raise ValueError(
            f"{trait} at {target} admits only {len(hits)} shell goals, need {count}"
        )
    seed_goal = min(hits, key=lambda g: abs(g[index] - target))
    chosen = [seed_goal]
    remaining = [g for g in hits if g != seed_goal]
    while len(chosen) < count:
        far = max(remaining, key=lambda g: min(math.dist(g, c) for c in chosen))
        chosen.append(far)
        remaining = [g for g in remaining if g != far]
    return chosen


def ladder(
    trait: str,
    members: Sequence[Sequence[float]],
    *,
    targets: Sequence[float] = WEIGHT_TARGETS,
    count: int = GOALS_PER_CELL,
    tolerance: float = WEIGHT_TOLERANCE,
) -> List[Dict[str, Any]]:
    if trait not in sim.TRAITS:
        raise ValueError(f"unknown trait: {trait!r}")
    index = trait_index(trait)
    return [
        {
            "target_weight": target,
            "goals": [
                {
                    "goal": [round(w, 9) for w in goal],
                    "weight": round(goal[index], 6),
                    "distance_to_supplied": round(e033.distance_to_supplied(goal), 6),
                    "distance_from_initial": round(e033.distance_from_initial(goal), 6),
                }
                for goal in cell_goals(
                    members,
                    trait=trait,
                    target=target,
                    count=count,
                    tolerance=tolerance,
                )
            ],
        }
        for target in targets
    ]


def classify_response(cells: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Does the lead move with the weight, and which way?

    ``rises``/``falls`` require the two end cells' intervals to be disjoint, so
    a trait is only called responsive when four goals a cell can see it.
    ``unresolved`` is the honest and common outcome, and is not evidence that
    the trait does nothing.
    """
    if len(cells) < 2:
        return {"response": "unresolved", "reason": "fewer than two cells"}
    low, high = cells[0], cells[-1]
    change = high["lead_mean"] - low["lead_mean"]
    separated = e033._disjoint(low, high)
    if not separated:
        response = "unresolved"
    else:
        response = "rises" if change > 0 else "falls"
    means = [cell["lead_mean"] for cell in cells]
    return {
        "response": response,
        "lead_at_lowest_weight": round(low["lead_mean"], 6),
        "lead_at_highest_weight": round(high["lead_mean"], 6),
        "change_across_the_ladder": round(change, 6),
        "endpoints_separate": separated,
        "endpoint_margin": round(
            e033._half_width(low) + e033._half_width(high), 6
        ),
        "monotone": means == sorted(means) or means == sorted(means, reverse=True),
        "cell_means": [round(value, 6) for value in means],
    }


CATEGORY_ORDER = ("floored", "descriptor", "unconstrained")


def category_rows(traits: Dict[str, Any], targets: Sequence[float]) -> Dict[str, Any]:
    """The same ladders pooled by trait category.

    The hypothesis is about categories -- traits the viability floor forces,
    traits the archive bins on, and traits that are neither -- so this is the
    test that matches it, and pooling doubles the sample for the two-trait
    categories. Derived from the per-goal results already in the report, so it
    is a view of the measurement rather than a second one.
    """
    rows: Dict[str, Any] = {}
    for category in CATEGORY_ORDER:
        names = [t for t, row in traits.items() if row["category"] == category]
        if not names:
            continue
        cells = []
        for position, target in enumerate(targets):
            pooled: List[Dict[str, Any]] = []
            for name in names:
                pooled.extend(traits[name]["cells"][position]["goal_results"])
            cell: Dict[str, Any] = {
                "target_weight": target,
                "goals": len(pooled),
                "mean_catastrophic_seeds": {
                    arm: round(
                        statistics.fmean(g["catastrophic_seeds"][arm] for g in pooled), 3
                    )
                    for arm in mbe.STRATEGIES
                },
            }
            for arm in e033.HYPOTHESIS_HOLDING:
                cell[arm] = e033._ring_statistic(pooled, arm)
            cells.append(cell)
        rows[category] = {
            "traits": sorted(names),
            "cells": cells,
            "response": {
                arm: classify_response(
                    [{"target_weight": c["target_weight"], **c[arm]} for c in cells]
                )
                for arm in e033.HYPOTHESIS_HOLDING
            },
        }
    return rows


def sweep(
    *,
    traits: Sequence[str] = sim.TRAITS,
    targets: Sequence[float] = WEIGHT_TARGETS,
    jobs: int = 1,
    count: int = GOALS_PER_CELL,
    tolerance: float = WEIGHT_TOLERANCE,
    shell_tolerance: float = SHELL_TOLERANCE,
    pool_draws: int = POOL_DRAWS,
    distance: float = SHELL_DISTANCE_TO_SUPPLIED,
    change_size: float = SHELL_CHANGE_SIZE,
    **kwargs: Any,
) -> Dict[str, Any]:
    settings = e033._settings(**kwargs)
    pool = e033.simplex_pool(draws=pool_draws, seed=POOL_SEED)
    members = shell(
        pool, distance=distance, change_size=change_size, tolerance=shell_tolerance
    )
    if not members:
        raise ValueError("the shell is empty; widen the tolerance or the pool")

    ladders = {
        trait: ladder(
            trait, members, targets=targets, count=count, tolerance=tolerance
        )
        for trait in traits
    }
    queue: List[Dict[str, Any]] = []
    for trait in traits:
        for cell in ladders[trait]:
            for entry in cell["goals"]:
                queue.append({**settings, "goal": tuple(entry["goal"])})
    measured = e033._run_jobs(queue, jobs)

    cursor = 0
    rows: Dict[str, Any] = {}
    for trait in traits:
        index = trait_index(trait)
        cells = []
        for cell in ladders[trait]:
            chunk = measured[cursor : cursor + len(cell["goals"])]
            cursor += len(cell["goals"])
            row: Dict[str, Any] = {
                "target_weight": cell["target_weight"],
                "mean_weight": round(
                    statistics.fmean(g["goal"][index] for g in chunk), 6
                ),
                "mean_distance_to_supplied": round(
                    statistics.fmean(g["distance_to_supplied"] for g in chunk), 6
                ),
                "mean_distance_from_initial": round(
                    statistics.fmean(g["distance_from_initial"] for g in chunk), 6
                ),
                "reference_arms": sorted({g["reference_arm"] for g in chunk}),
                "mean_catastrophic_seeds": {
                    arm: round(
                        statistics.fmean(g["catastrophic_seeds"][arm] for g in chunk), 3
                    )
                    for arm in mbe.STRATEGIES
                },
                "goal_results": chunk,
            }
            for arm in e033.HYPOTHESIS_HOLDING:
                row[arm] = e033._ring_statistic(chunk, arm)
            cells.append(row)
        rows[trait] = {
            "category": trait_category(trait),
            "cells": cells,
            "response": {
                arm: classify_response(
                    [{"target_weight": c["target_weight"], **c[arm]} for c in cells]
                )
                for arm in e033.HYPOTHESIS_HOLDING
            },
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "metric": "post_change_utility_auc",
        "catastrophe_utility_auc_threshold": round(
            mbe.CATASTROPHE_FRACTION
            * (settings["generations"] - settings["change_at"]),
            6,
        ),
        "shell": {
            "distance_to_supplied": distance,
            "change_size": change_size,
            "tolerance": shell_tolerance,
            "members": len(members),
            "pool_draws": pool_draws,
            "pool_seed": POOL_SEED,
        },
        "weight_targets": list(targets),
        "weight_tolerance": tolerance,
        "goals_per_cell": count,
        "trait_categories": {trait: trait_category(trait) for trait in sim.TRAITS},
        "floor_traits": list(FLOOR_TRAITS),
        "descriptor_traits": list(DESCRIPTOR_TRAITS),
        "unconstrained_traits": list(UNCONSTRAINED_TRAITS),
        "minimum_reliability": sim.MIN_RELIABILITY,
        "minimum_security": sim.MIN_SECURITY,
        "hypothesis_free_arms": list(e033.HYPOTHESIS_FREE),
        "hypothesis_holding_arms": list(e033.HYPOTHESIS_HOLDING),
        "traits": rows,
        "categories": category_rows(rows, targets),
        "category_order": list(CATEGORY_ORDER),
        **settings,
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E034 goal-direction sweep")
    parser.add_argument("--trait", action="append", default=None)
    parser.add_argument("--weight", action="append", type=float, default=None)
    parser.add_argument("--seeds", type=int, default=None)
    parser.add_argument("--seed-start", type=int, default=None)
    parser.add_argument("--agents", type=int, default=None)
    parser.add_argument("--generations", type=int, default=None)
    parser.add_argument("--change-at", type=int, default=None)
    parser.add_argument("--bins", type=int, default=None)
    parser.add_argument("--panel", default=None)
    parser.add_argument("--goals-per-cell", type=int, default=GOALS_PER_CELL)
    parser.add_argument("--weight-tolerance", type=float, default=WEIGHT_TOLERANCE)
    parser.add_argument("--shell-tolerance", type=float, default=SHELL_TOLERANCE)
    parser.add_argument("--distance", type=float, default=SHELL_DISTANCE_TO_SUPPLIED)
    parser.add_argument("--pool-draws", type=int, default=POOL_DRAWS)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    report = sweep(
        traits=tuple(args.trait) if args.trait else sim.TRAITS,
        targets=tuple(args.weight) if args.weight else WEIGHT_TARGETS,
        jobs=args.jobs,
        count=args.goals_per_cell,
        tolerance=args.weight_tolerance,
        shell_tolerance=args.shell_tolerance,
        pool_draws=args.pool_draws,
        distance=args.distance,
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        panel=args.panel,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
