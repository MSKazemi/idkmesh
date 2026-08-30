#!/usr/bin/env python3
"""E032: at a fixed budget, when is another agent worth adding?

Issue 13 states its success criterion as a question -- "For a fixed budget and
task class, when is another agent worth adding, and why?" -- and its first
falsifiable hypothesis as "increasing N with low diversity produces diminishing
or negative returns after a measurable threshold".

Both halves of that are easy to answer wrongly with this simulator, because
E024's budget contract is

    evaluation_budget = agents * generations

so sweeping ``agents`` at a fixed ``generations`` also multiplies the budget.
An arm that improves across such a sweep has been handed 16x more evaluations
at N=256 than at N=16, and "more agents helped" is then indistinguishable from
"more compute helped".  That is exactly the confound the issue names, so this
module runs the sweep both ways:

``--mode unmatched``
    ``generations`` fixed, budget grows with N.  Returns to *budget*.

``--mode matched``
    ``agents * generations`` fixed, so adding agents buys fewer generations.
    Returns to *population size alone*.  This is the arm issue 13 asks for.

``--mode capacity``
    Archive resolution ``bins`` swept at a fixed cell, because the archive
    capacity is ``bins ** 2`` and does not depend on N at all.  A Quality-
    Diversity result that moved with capacity would be a result about the grid
    rather than about diversity.

The post-change horizon is held at exactly ``POST_CHANGE_HORIZON`` generations
in *every* cell of *every* mode, so ``post_change_utility_auc`` is on one scale
throughout and the catastrophe threshold is the same absolute 16.0 that E024,
E027, E028, E030 and E031 published.  In the matched mode the budget therefore
trades population size against *pre-change* generations: N=16 gets 775
generations to converge before the goal moves, N=256 gets 25.

Two statistical choices are deliberate, and both were made before the sweep ran:

* **Paired comparisons.**  A seed indexes a partially shared environment across
  cells -- measured correlation between the N=64 and N=128 per-seed AUC is
  +0.44 for ``majority`` and +0.19 for ``random`` -- so consecutive cells are
  compared as paired differences.  On ``majority``, the arm with by far the
  widest spread, pairing shrinks the standard error 1.34x.
* **A catastrophic-seed test as well as a mean test.**  ``majority`` is bimodal:
  a seed either locks onto the dead objective or does not.  Its per-seed AUC
  standard deviation is roughly 40x ``qd``'s, which makes the mean a
  low-power statistic.  The catastrophic-seed count is the statistic E024 leads
  with for that reason, and McNemar's exact paired test is applied to it.

A step is only called a gain or a loss when the 95% paired interval excludes
zero.  Anything else is reported as ``indistinguishable`` -- a measurement that
this design at this seed count cannot resolve, not a measured absence.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import json
import math
from statistics import mean, stdev
from typing import Dict, List, Sequence, Tuple

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe

EXPERIMENT_ID = "E032"
EXPERIMENT = "population-scaling-at-matched-budget-v1"

# Held identical in every cell so that post_change_utility_auc is one scale and
# the catastrophe threshold stays the published absolute number.
POST_CHANGE_HORIZON = 25
CATASTROPHE_THRESHOLD = mbe.CATASTROPHE_FRACTION * POST_CHANGE_HORIZON

DEFAULT_AGENTS: Tuple[int, ...] = (16, 32, 64, 128, 256)
DEFAULT_BIN_GRID: Tuple[int, ...] = (4, 8, 16, 32)
DEFAULT_SEEDS = 100
DEFAULT_SEED_START = 1
DEFAULT_BINS = 8

# 256 * 50 -- the largest cell of the unmatched sweep, so the matched sweep is
# run at the most generous budget the unmatched sweep ever reaches rather than
# at a budget chosen to make the matched arm look bad.
DEFAULT_MATCHED_BUDGET = 12800
# The published E024 shape, which is the unmatched sweep's N=256 cell.
DEFAULT_UNMATCHED_GENERATIONS = 50

MODES = ("matched", "unmatched", "capacity")


class Cell:
    """One (agents, generations, change_at, bins) point of a sweep."""

    __slots__ = ("agents", "generations", "change_at", "bins")

    def __init__(self, agents: int, generations: int, change_at: int, bins: int) -> None:
        if generations - change_at != POST_CHANGE_HORIZON:
            raise ValueError(
                f"every cell must hold the post-change horizon at "
                f"{POST_CHANGE_HORIZON}; got {generations - change_at}"
            )
        if change_at < 1:
            raise ValueError("change_at must be >= 1")
        self.agents = agents
        self.generations = generations
        self.change_at = change_at
        self.bins = bins

    @property
    def evaluation_budget(self) -> int:
        return self.agents * self.generations

    @property
    def pre_change_generations(self) -> int:
        return self.change_at

    @property
    def archive_capacity(self) -> int:
        return self.bins * self.bins

    def as_dict(self) -> Dict[str, int]:
        return {
            "agents": self.agents,
            "generations": self.generations,
            "change_at": self.change_at,
            "bins": self.bins,
            "evaluation_budget": self.evaluation_budget,
            "pre_change_generations": self.pre_change_generations,
            "post_change_horizon": POST_CHANGE_HORIZON,
            "archive_capacity": self.archive_capacity,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Cell(agents={self.agents}, generations={self.generations}, "
            f"change_at={self.change_at}, bins={self.bins})"
        )


def matched_cells(
    budget: int = DEFAULT_MATCHED_BUDGET,
    agents: Sequence[int] = DEFAULT_AGENTS,
    bins: int = DEFAULT_BINS,
) -> Tuple[Cell, ...]:
    """Cells whose evaluation budget is identical and whose horizon is fixed.

    Adding agents buys fewer pre-change generations and nothing else.
    """
    cells = []
    for n in agents:
        if budget % n:
            raise ValueError(f"budget {budget} is not divisible by agents {n}")
        generations = budget // n
        change_at = generations - POST_CHANGE_HORIZON
        if change_at < 1:
            raise ValueError(
                f"budget {budget} leaves no pre-change generations at agents={n}"
            )
        cells.append(Cell(n, generations, change_at, bins))
    return tuple(cells)


def unmatched_cells(
    generations: int = DEFAULT_UNMATCHED_GENERATIONS,
    agents: Sequence[int] = DEFAULT_AGENTS,
    bins: int = DEFAULT_BINS,
) -> Tuple[Cell, ...]:
    """Cells at a fixed generation count, so the budget grows with N."""
    change_at = generations - POST_CHANGE_HORIZON
    return tuple(Cell(n, generations, change_at, bins) for n in agents)


def capacity_cells(
    agents: int = 64,
    generations: int = DEFAULT_UNMATCHED_GENERATIONS,
    bin_grid: Sequence[int] = DEFAULT_BIN_GRID,
) -> Tuple[Cell, ...]:
    """Cells that vary only the archive resolution, at one fixed population."""
    change_at = generations - POST_CHANGE_HORIZON
    return tuple(Cell(agents, generations, change_at, b) for b in bin_grid)


def cells_for_mode(mode: str, **kwargs: object) -> Tuple[Cell, ...]:
    if mode == "matched":
        return matched_cells(**kwargs)  # type: ignore[arg-type]
    if mode == "unmatched":
        return unmatched_cells(**kwargs)  # type: ignore[arg-type]
    if mode == "capacity":
        return capacity_cells(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")


def _summarise(values: Sequence[float]) -> Dict[str, object]:
    n = len(values)
    average = mean(values)
    spread = stdev(values) if n > 1 else 0.0
    sem = spread / math.sqrt(n) if n else 0.0
    catastrophic = sum(1 for v in values if v < CATASTROPHE_THRESHOLD)
    return {
        "n": n,
        "mean": round(average, 6),
        "stdev": round(spread, 6),
        "sem": round(sem, 6),
        "ci95_low": round(average - 1.96 * sem, 6),
        "ci95_high": round(average + 1.96 * sem, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "catastrophic_seeds": catastrophic,
        "catastrophic_rate": round(catastrophic / n, 6) if n else 0.0,
    }


def run_cell(
    cell: Cell,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = DEFAULT_SEED_START,
    verification: "sim.VerificationConfig | None" = None,
) -> Dict[str, object]:
    """Run one cell and keep the per-seed AUC for every arm.

    ``mbe.sweep`` deliberately withholds ``catastrophic_seeds`` on a perfect
    panel so its published artifact schema stays frozen, and it never exposes
    per-seed values at all.  Both are needed here -- the catastrophic count
    because ``majority`` is bimodal, the per-seed values because consecutive
    cells are compared pairwise -- so this walks ``mbe.run_seed`` directly and
    changes nothing about how a seed is executed.
    """
    if seeds < 2:
        raise ValueError("seeds must be >= 2")
    verification = verification or sim.VerificationConfig()
    per_seed: Dict[str, List[float]] = {s: [] for s in mbe.STRATEGIES}
    archive_sizes: List[float] = []
    for seed in range(seed_start, seed_start + seeds):
        result = mbe.run_seed(
            seed,
            cell.agents,
            cell.generations,
            cell.change_at,
            cell.bins,
            verification,
        )
        for row in result["results"]:
            per_seed[row["strategy"]].append(float(row["post_change_utility_auc"]))
            if row["strategy"] == "qd":
                archive_sizes.append(float(row["archive_size"]))
    return {
        "cell": cell.as_dict(),
        "seeds": seeds,
        "seed_start": seed_start,
        "archive_size_mean": round(mean(archive_sizes), 6),
        "archive_fill_fraction": round(
            mean(archive_sizes) / cell.archive_capacity, 6
        ),
        "per_seed_post_change_utility_auc": {
            strategy: [round(v, 6) for v in values]
            for strategy, values in per_seed.items()
        },
        "summary": {
            strategy: _summarise(values) for strategy, values in per_seed.items()
        },
    }


def _mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value for paired binary outcomes.

    ``only_a`` seeds are catastrophic in the first cell alone, ``only_b`` in the
    second alone.  Concordant seeds carry no information about a change and are
    excluded, which is what makes this the right test for an arm whose spread is
    dominated by which seeds are catastrophic at all.
    """
    discordant = only_a + only_b
    if discordant == 0:
        return 1.0
    smaller = min(only_a, only_b)
    tail = sum(math.comb(discordant, k) for k in range(smaller + 1))
    return min(1.0, 2.0 * tail / (2.0**discordant))


def _paired_step(
    lower: Sequence[float], upper: Sequence[float]
) -> Dict[str, object]:
    """Compare two cells on the same seeds, on the mean and on catastrophe."""
    if len(lower) != len(upper):
        raise ValueError("paired comparison needs the same seeds in both cells")
    differences = [b - a for a, b in zip(lower, upper)]
    n = len(differences)
    delta = mean(differences)
    spread = stdev(differences) if n > 1 else 0.0
    sem = spread / math.sqrt(n) if n else 0.0
    half_width = 1.96 * sem
    low, high = delta - half_width, delta + half_width
    if low > 0:
        verdict = "gain"
    elif high < 0:
        verdict = "loss"
    else:
        verdict = "indistinguishable"

    cat_lower = [v < CATASTROPHE_THRESHOLD for v in lower]
    cat_upper = [v < CATASTROPHE_THRESHOLD for v in upper]
    only_lower = sum(1 for a, b in zip(cat_lower, cat_upper) if a and not b)
    only_upper = sum(1 for a, b in zip(cat_lower, cat_upper) if b and not a)
    p_value = _mcnemar_exact(only_lower, only_upper)

    return {
        "mean_delta": round(delta, 6),
        "paired_stdev": round(spread, 6),
        "paired_sem": round(sem, 6),
        "ci95_low": round(low, 6),
        "ci95_high": round(high, 6),
        "verdict": verdict,
        "catastrophic_only_in_lower": only_lower,
        "catastrophic_only_in_upper": only_upper,
        "catastrophic_delta": sum(cat_upper) - sum(cat_lower),
        "catastrophic_mcnemar_p": round(p_value, 6),
        "catastrophic_verdict": (
            "changed" if p_value < 0.05 else "indistinguishable"
        ),
    }


def marginal_returns(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """The marginal value of each step along the swept axis, per arm."""
    steps: Dict[str, List[Dict[str, object]]] = {s: [] for s in mbe.STRATEGIES}
    for lower, upper in zip(rows, rows[1:]):
        for strategy in mbe.STRATEGIES:
            step = _paired_step(
                lower["per_seed_post_change_utility_auc"][strategy],  # type: ignore[index]
                upper["per_seed_post_change_utility_auc"][strategy],  # type: ignore[index]
            )
            step["from"] = lower["cell"]  # type: ignore[index]
            step["to"] = upper["cell"]  # type: ignore[index]
            steps[strategy].append(step)
    return steps


def classify_returns(steps: Sequence[Dict[str, object]]) -> str:
    """Name the shape issue 13 asks to be reported, from the step verdicts.

    The vocabulary is the issue's own: "sublinear, near-linear, superlinear,
    saturated, or negative".  ``superlinear`` is reachable only if a later step
    is resolvably larger than an earlier one, and ``unresolved`` is a first-class
    answer rather than a silent fallback to ``saturated``.
    """
    verdicts = [s["verdict"] for s in steps]
    deltas = [s["mean_delta"] for s in steps]
    if not verdicts:
        return "unresolved"
    if all(v == "indistinguishable" for v in verdicts):
        return "unresolved"
    if any(v == "loss" for v in verdicts):
        return "negative"
    if verdicts[-1] == "indistinguishable":
        return "saturated"
    gains = [s for s, v in zip(steps, verdicts) if v == "gain"]
    if len(gains) < 2:
        return "near-linear"
    first, last = gains[0], gains[-1]
    # Only call the trend when the two end gains are resolvably different.
    # Reading "sublinear" off a difference smaller than the intervals it sits
    # inside is the same over-reading this module exists to avoid.
    margin = _half_width(first) + _half_width(last)
    difference = last["mean_delta"] - first["mean_delta"]
    if abs(difference) <= margin:
        return "near-linear"
    return "superlinear" if difference > 0 else "sublinear"


def _half_width(step: Dict[str, object]) -> float:
    low, high = step.get("ci95_low"), step.get("ci95_high")
    if low is None or high is None:
        return 0.0
    return (float(high) - float(low)) / 2.0


def sweep(
    mode: str,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = DEFAULT_SEED_START,
    verification: "sim.VerificationConfig | None" = None,
    **cell_kwargs: object,
) -> Dict[str, object]:
    cells = cells_for_mode(mode, **cell_kwargs)
    verification = verification or sim.VerificationConfig()
    rows = [run_cell(cell, seeds, seed_start, verification) for cell in cells]
    steps = marginal_returns(rows)
    budgets = sorted({c.evaluation_budget for c in cells})
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "mode": mode,
        "configuration": {
            "seeds": seeds,
            "seed_start": seed_start,
            "post_change_horizon": POST_CHANGE_HORIZON,
            "catastrophe_fraction": mbe.CATASTROPHE_FRACTION,
            "catastrophe_utility_auc_threshold": round(CATASTROPHE_THRESHOLD, 6),
            "evaluation_budget_is_constant": len(budgets) == 1,
            "evaluation_budgets": budgets,
            "verification": verification.as_dict(),
            "swept_axis": "bins" if mode == "capacity" else "agents",
        },
        "cells": rows,
        "marginal_returns": steps,
        "returns_shape": {
            strategy: classify_returns(strategy_steps)
            for strategy, strategy_steps in steps.items()
        },
        "limitations": _limitations(mode),
    }


def _limitations(mode: str) -> List[str]:
    shared = [
        "All candidates, goals, and verification outcomes are synthetic; no real model, task, or reviewer is involved.",
        "One evaluation unit is a simulator proposal plus panel decision, not measured compute, energy, or human attention.",
        "The verifier panel is perfect here, so this measures returns to population size with verification held out of the way; E026 and E027 measure what an imperfect panel does at one population size.",
        "Quality-Diversity is handed the four predefined plausible goals, so its diversity is supplied rather than discovered; E030 and E031 measure what happens when the new goal is outside that set.",
        "'Agents' is a population size in a synthetic evolutionary search, not a count of language-model workers; nothing here estimates the scaling law for real coding agents.",
        "A step is called indistinguishable when its 95% paired interval contains zero. That is a limit of this design at this seed count, not evidence that the true effect is zero.",
    ]
    if mode == "matched":
        return shared + [
            "Holding agents * generations constant means more agents also buys fewer pre-change generations, so the matched sweep measures the population-versus-time trade rather than population size in isolation. Nothing here separates the two.",
            "The post-change horizon is fixed at 25 generations, so the largest population is evaluated after the shortest pre-change convergence; an arm that needs many generations to converge is penalised at large N by construction.",
        ]
    if mode == "unmatched":
        return shared + [
            "The evaluation budget grows with the population here, so any gain along this axis is a return to budget and population jointly. Only the matched mode separates them.",
        ]
    return shared + [
        "The archive capacity is bins ** 2 and is swept at one population size, so this bounds the grid's influence at that cell only.",
    ]


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E032: returns to population size at a matched evaluation budget."
    )
    parser.add_argument("--mode", choices=MODES, default="matched")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument(
        "--agents",
        type=int,
        action="append",
        default=None,
        help="repeatable; population sizes to sweep (ignored by --mode capacity)",
    )
    parser.add_argument("--budget", type=int, default=DEFAULT_MATCHED_BUDGET)
    parser.add_argument(
        "--generations", type=int, default=DEFAULT_UNMATCHED_GENERATIONS
    )
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument(
        "--bin-grid",
        type=int,
        action="append",
        default=None,
        help="repeatable; archive resolutions to sweep under --mode capacity",
    )
    parser.add_argument(
        "--capacity-agents",
        type=int,
        default=64,
        help="population size held fixed under --mode capacity",
    )
    parser.add_argument("--output", default=None)
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> None:
    args = parse_args(argv)
    agents = tuple(args.agents) if args.agents else DEFAULT_AGENTS
    if args.mode == "matched":
        kwargs: Dict[str, object] = {
            "budget": args.budget,
            "agents": agents,
            "bins": args.bins,
        }
    elif args.mode == "unmatched":
        kwargs = {
            "generations": args.generations,
            "agents": agents,
            "bins": args.bins,
        }
    else:
        kwargs = {
            "agents": args.capacity_agents,
            "generations": args.generations,
            "bin_grid": tuple(args.bin_grid) if args.bin_grid else DEFAULT_BIN_GRID,
        }
    report = sweep(
        args.mode, seeds=args.seeds, seed_start=args.seed_start, **kwargs
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
