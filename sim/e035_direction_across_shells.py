"""E035 -- does E034's direction result hold at more than one distance?

E034 held the distance to the supplied set fixed at ``0.30`` and swept the
*direction* of the future goal, and reported three things:

1. direction matters as much as distance -- the archive's lead spanned ``9.365``
   on one shell, against the ``3.309`` E033's whole distance sweep moved;
2. the preregistered viability-floor hypothesis is falsified, because the
   control trait ``simplicity`` was predicted flat and instead fell and inverted,
   and because the two identically-floored traits behaved differently;
3. the arena's structural trait categories are not a valid grouping, because the
   two ``niche``-descriptor traits move in opposite directions and cancel.

Every one of those rested on a single shell, which E034 recorded as its first
limitation, and it conjectured that the spread would widen with distance. E035
repeats the identical ladder at two further distances and asks which of the
three survive.

The feasibility window
----------------------

The shells cannot be placed anywhere. E034's design holds *both* the distance to
the supplied set and the size of the change, and those two constraints interact:
``PLAUSIBLE_GOALS`` contains ``INITIAL_GOAL``, so a goal near the box is also a
small change, and a small change cannot put an extreme weight on a single trait.
Below :data:`WINDOW_LOW` at least one trait-by-weight cell is *empty* -- not
sparse, empty -- and above :data:`WINDOW_HIGH` the shell runs into
``d_set <= d_initial``. :func:`feasible_shells` measures this rather than
asserting it, so an arena change moves the window instead of silently producing
unfillable cells.

The comparison
--------------

:data:`SHELLS` are three distances inside that window, E034's own ``0.30``
included so its committed artifact is reused rather than recomputed. For each
trait, :func:`ladder_change` is the ``w=0.40`` cell minus the ``w=0.02`` cell
with Welch's t; :func:`replication` then classifies each trait across the
shells as ``replicates`` (same sign and resolved everywhere), ``consistent``
(same sign, not resolved everywhere) or ``sign_flips``.

A finding that flips sign across the window is a property of one shell, not of
the arena, and E035 exists to say which of E034's are which.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import sim.emergence_sim as sim
import sim.e033_goal_distance as e033
import sim.e034_goal_direction as e034

EXPERIMENT_ID = "E035"
EXPERIMENT = "goal-direction-across-shells-v1"

#: Distances measured. ``0.30`` is E034's shell and is read from its artifact.
SHELLS: Tuple[float, ...] = (0.30, 0.35, 0.375)
E034_SHELL = 0.30

#: Every shell compared here was run at 16 goals per cell, not the module
#: default, so the feasibility test must ask for 16 rather than ``GOALS_PER_CELL``.
SHELL_GOALS_PER_CELL = 16

#: The measured feasibility window; see :func:`feasible_shells`.
WINDOW_LOW = 0.28
WINDOW_HIGH = 0.385
WINDOW_STEP = 0.005

#: A ladder is resolved when Welch's t clears this. Five preregistered ladders
#: put the Bonferroni bar at 0.05/5 = 0.010; the smallest df seen is ~18, where
#: the two-sided 0.01 critical value is 2.878, so this is the conservative one.
RESOLVED_T = 2.878

REPLICATES = "replicates"
CONSISTENT = "consistent"
SIGN_FLIPS = "sign_flips"


def _leads(report: Dict[str, Any], trait: str, index: int) -> List[float]:
    cell = report["traits"][trait]["cells"][index]
    return [g["lead_over_hypothesis_free"]["qd"] for g in cell["goal_results"]]


def welch(sample_a: Sequence[float], sample_b: Sequence[float]) -> Dict[str, float]:
    """Welch's t for two independent samples: high cell minus low cell."""
    mean_a, mean_b = statistics.fmean(sample_a), statistics.fmean(sample_b)
    var_a = statistics.variance(sample_a) / len(sample_a)
    var_b = statistics.variance(sample_b) / len(sample_b)
    error = math.sqrt(var_a + var_b)
    degrees = (var_a + var_b) ** 2 / (
        var_a ** 2 / (len(sample_a) - 1) + var_b ** 2 / (len(sample_b) - 1)
    )
    difference = mean_a - mean_b
    return {
        "change": round(difference, 6),
        "standard_error": round(error, 6),
        "t": round(difference / error, 6),
        "degrees_of_freedom": round(degrees, 6),
        "resolved": abs(difference / error) > RESOLVED_T,
    }


def ladder_change(report: Dict[str, Any], trait: str) -> Dict[str, float]:
    """The trait's ladder endpoint change on one shell."""
    return welch(_leads(report, trait, -1), _leads(report, trait, 0))


def direction_spread(report: Dict[str, Any]) -> Dict[str, float]:
    """How wide the archive's lead runs across the directions on one shell."""
    distinct = {
        tuple(g["goal"]): g["lead_over_hypothesis_free"]["qd"]
        for trait in report["traits"].values()
        for cell in trait["cells"]
        for g in cell["goal_results"]
    }
    leads = list(distinct.values())
    negative = sum(1 for value in leads if value < 0)
    return {
        "goals": len(leads),
        "lead_min": round(min(leads), 6),
        "lead_max": round(max(leads), 6),
        "spread": round(max(leads) - min(leads), 6),
        "lead_mean": round(statistics.fmean(leads), 6),
        "lead_sd": round(statistics.stdev(leads), 6),
        "negative_goals": negative,
        "negative_share": round(negative / len(leads), 6),
    }


def goals_of(report: Dict[str, Any]) -> set:
    """Every distinct goal measured on one shell."""
    return {
        tuple(g["goal"])
        for trait in report["traits"].values()
        for cell in trait["cells"]
        for g in cell["goal_results"]
    }


def shell_overlap(reports: Dict[float, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """How far the shells are from being independent samples.

    Two shells whose tolerance bands intersect can draw the same goal, which
    would make part of a "replication" the same measurement twice. The bands are
    ``+/- tolerance`` wide, so they intersect when the distances are closer than
    ``2 * tolerance``. This reports the predicted intersection alongside the
    goals actually shared, so a comparison is never quietly self-confirming.
    """
    rows = []
    for lower, upper in itertools.combinations(sorted(reports), 2):
        left, right = reports[lower], reports[upper]
        band = left["shell"]["tolerance"] + right["shell"]["tolerance"]
        shared = goals_of(left) & goals_of(right)
        smaller = min(len(goals_of(left)), len(goals_of(right)))
        rows.append(
            {
                "distances": [lower, upper],
                "separation": round(upper - lower, 6),
                "band_intersection": round(max(band - (upper - lower), 0.0), 6),
                "shared_goals": len(shared),
                "shared_share": round(len(shared) / smaller, 6),
                "disjoint": not shared,
            }
        )
    return rows


def contrast(first: Dict[str, float], second: Dict[str, float]) -> Dict[str, float]:
    """The difference between two ladders' changes, with a pooled error."""
    difference = first["change"] - second["change"]
    error = math.hypot(first["standard_error"], second["standard_error"])
    return {
        "contrast": round(difference, 6),
        "standard_error": round(error, 6),
        "t": round(difference / error, 6),
        "resolved": abs(difference / error) > RESOLVED_T,
    }


def replication(changes: Sequence[Dict[str, float]]) -> Dict[str, Any]:
    """Classify one trait's behaviour across the shells.

    ``sign_flips`` is the verdict that matters: a trait whose ladder points one
    way on one shell and the other way on another is telling us about that
    shell, not about the arena.
    """
    signs = {math.copysign(1.0, c["change"]) for c in changes}
    resolved = [c["resolved"] for c in changes]
    if len(signs) > 1:
        verdict = SIGN_FLIPS
    elif all(resolved):
        verdict = REPLICATES
    else:
        verdict = CONSISTENT
    return {
        "verdict": verdict,
        "changes": [c["change"] for c in changes],
        "resolved": resolved,
        "resolved_count": sum(resolved),
    }


def feasible_shells(
    pool: Sequence[Sequence[float]],
    *,
    low: float = WINDOW_LOW - 0.04,
    high: float = WINDOW_HIGH + 0.02,
    step: float = WINDOW_STEP,
    count: int = SHELL_GOALS_PER_CELL,
) -> List[Dict[str, Any]]:
    """Which distances admit a full ladder, measured rather than assumed.

    A distance is feasible when every trait-by-weight cell holds at least
    ``count`` shell members. Returns one row per distance so the window's edges
    are visible instead of appearing as a crash inside a sweep.
    """
    rows: List[Dict[str, Any]] = []
    steps = int(round((high - low) / step))
    for index in range(steps + 1):
        distance = round(low + index * step, 6)
        members = e034.shell(pool, distance=distance)
        thinnest = None
        for trait in sim.TRAITS:
            position = e034.trait_index(trait)
            for target in e034.WEIGHT_TARGETS:
                available = sum(
                    1
                    for goal in members
                    if abs(goal[position] - target) <= e034.WEIGHT_TOLERANCE
                )
                if thinnest is None or available < thinnest[0]:
                    thinnest = (available, trait, target)
        rows.append(
            {
                "distance_to_supplied": distance,
                "members": len(members),
                "thinnest_cell_goals": thinnest[0],
                "thinnest_cell_trait": thinnest[1],
                "thinnest_cell_weight": thinnest[2],
                "feasible": thinnest[0] >= count,
            }
        )
    return rows


def window(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The contiguous feasible span of a :func:`feasible_shells` table."""
    feasible = [row["distance_to_supplied"] for row in rows if row["feasible"]]
    return {
        "low": min(feasible) if feasible else None,
        "high": max(feasible) if feasible else None,
        "width": round(max(feasible) - min(feasible), 6) if feasible else None,
    }


def compare(reports: Dict[float, Dict[str, Any]]) -> Dict[str, Any]:
    """The cross-shell comparison: spread, per-trait ladders, replication."""
    distances = sorted(reports)
    traits = sorted(reports[distances[0]]["traits"])
    per_shell = {
        distance: {
            "shell": reports[distance]["shell"],
            "direction_spread": direction_spread(reports[distance]),
            "ladders": {
                trait: ladder_change(reports[distance], trait) for trait in traits
            },
        }
        for distance in distances
    }
    trait_replication = {
        trait: replication([per_shell[d]["ladders"][trait] for d in distances])
        for trait in traits
    }
    descriptor = {
        distance: contrast(
            per_shell[distance]["ladders"]["adaptability"],
            per_shell[distance]["ladders"]["efficiency"],
        )
        for distance in distances
    }
    floored = {
        distance: contrast(
            per_shell[distance]["ladders"]["reliability"],
            per_shell[distance]["ladders"]["security"],
        )
        for distance in distances
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "distances": distances,
        "resolved_t": RESOLVED_T,
        "per_shell": {str(d): per_shell[d] for d in distances},
        "shell_overlap": shell_overlap(reports),
        "trait_replication": trait_replication,
        "descriptor_contrast": {str(d): descriptor[d] for d in distances},
        "floored_contrast": {str(d): floored[d] for d in distances},
        "descriptor_cancellation_replicates": all(
            descriptor[d]["resolved"] for d in distances
        ),
        "floored_pair_asymmetry_replicates": all(
            per_shell[d]["ladders"]["reliability"]["change"]
            > per_shell[d]["ladders"]["security"]["change"]
            and not per_shell[d]["ladders"]["security"]["resolved"]
            for d in distances
        ),
        "sign_flip_shells_are_disjoint": all(
            row["disjoint"]
            for trait, block in trait_replication.items()
            if block["verdict"] == SIGN_FLIPS
            for row in shell_overlap(reports)
            if row["distances"]
            == [
                distances[block["changes"].index(min(block["changes"]))],
                distances[block["changes"].index(max(block["changes"]))],
            ]
        ),
        "spread_grows_with_distance": (
            per_shell[distances[-1]]["direction_spread"]["spread"]
            > per_shell[distances[0]]["direction_spread"]["spread"] * 1.1
        ),
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E035 direction across shells")
    parser.add_argument(
        "--shell",
        action="append",
        default=None,
        metavar="DISTANCE=PATH",
        help="an E034-shaped artifact to include, e.g. 0.35=results/E035-shell-0.350.json",
    )
    parser.add_argument("--window", action="store_true", help="measure the feasible window")
    parser.add_argument("--pool-draws", type=int, default=e034.POOL_DRAWS)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    report: Dict[str, Any]
    if args.window:
        pool = e033.simplex_pool(draws=args.pool_draws, seed=e034.POOL_SEED)
        rows = feasible_shells(pool)
        report = {
            "experiment_id": EXPERIMENT_ID,
            "feasibility": rows,
            "window": window(rows),
            "change_size": e034.SHELL_CHANGE_SIZE,
            "shell_tolerance": e034.SHELL_TOLERANCE,
            "weight_tolerance": e034.WEIGHT_TOLERANCE,
            "goals_per_cell": SHELL_GOALS_PER_CELL,
        }
    else:
        if not args.shell:
            raise SystemExit("--shell DISTANCE=PATH is required (or pass --window)")
        reports = {}
        for item in args.shell:
            distance, _, path = item.partition("=")
            reports[float(distance)] = json.loads(Path(path).read_text(encoding="utf-8"))
        report = compare(reports)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
