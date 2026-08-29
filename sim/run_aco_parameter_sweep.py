#!/usr/bin/env python3
"""Sweep ACO parameters and report non-dominated routing configurations."""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
from typing import Dict, Iterable, List, Sequence, Tuple

import aco_stigmergy_sim as sim


METRICS = (
    "verified_utility_per_cost",
    "duplicate_rate",
    "task_coverage",
    "max_selection_share",
)


def parse_floats(value: str) -> List[float]:
    values = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one comma-separated float")
    return values


def summarize(rows: List[Dict[str, object]]) -> Dict[str, float]:
    return {
        metric: round(statistics.fmean(float(row[metric]) for row in rows), 9)
        for metric in METRICS
    }


def dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """Return True when a is no worse on all objectives and better on at least one."""
    comparisons = (
        a["verified_utility_per_cost"] >= b["verified_utility_per_cost"],
        a["duplicate_rate"] <= b["duplicate_rate"],
        a["task_coverage"] >= b["task_coverage"],
        a["max_selection_share"] <= b["max_selection_share"],
    )
    strict = (
        a["verified_utility_per_cost"] > b["verified_utility_per_cost"]
        or a["duplicate_rate"] < b["duplicate_rate"]
        or a["task_coverage"] > b["task_coverage"]
        or a["max_selection_share"] < b["max_selection_share"]
    )
    return all(comparisons) and strict


def pareto_front(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    front: List[Dict[str, object]] = []
    for candidate in rows:
        candidate_metrics = candidate["mean"]
        if any(
            dominates(other["mean"], candidate_metrics)
            for other in rows
            if other is not candidate
        ):
            continue
        front.append(candidate)
    return sorted(
        front,
        key=lambda row: (
            -float(row["mean"]["verified_utility_per_cost"]),
            float(row["mean"]["duplicate_rate"]),
            float(row["mean"]["max_selection_share"]),
        ),
    )


def run_parameter_sweep(
    seed_start: int,
    seeds: int,
    workers: int,
    epochs: int,
    alphas: Sequence[float],
    betas: Sequence[float],
    rhos: Sequence[float],
    explorations: Sequence[float],
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")

    configurations: List[Dict[str, object]] = []
    for alpha, beta, rho, exploration in itertools.product(
        alphas, betas, rhos, explorations
    ):
        if not (0.0 <= rho < 1.0):
            raise ValueError("rho must be in [0, 1)")
        if not (0.0 <= exploration <= 1.0):
            raise ValueError("exploration must be in [0, 1]")
        if alpha < 0.0 or beta < 0.0:
            raise ValueError("alpha and beta must be non-negative")

        config = sim.ACOConfig(
            alpha=alpha,
            beta=beta,
            rho=rho,
            exploration=exploration,
        )
        runs = [
            sim.run_strategy(
                "aco",
                seed=seed_start + offset,
                workers=workers,
                epochs=epochs,
                config=config,
            )
            for offset in range(seeds)
        ]
        configurations.append(
            {
                "parameters": {
                    "alpha": alpha,
                    "beta": beta,
                    "rho": rho,
                    "exploration": exploration,
                },
                "mean": summarize(runs),
            }
        )

    front = pareto_front(configurations)
    return {
        "experiment": "aco-stigmergic-parameter-sweep-v0",
        "model_warning": "Synthetic illustrative simulation; not empirical evidence about real contributors.",
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "configurations_tested": len(configurations),
        "pareto_configurations": front,
        "all_configurations": configurations,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--alpha", type=parse_floats, default=parse_floats("0.3,0.7,1.1"))
    parser.add_argument("--beta", type=parse_floats, default=parse_floats("1.5,2.5"))
    parser.add_argument("--rho", type=parse_floats, default=parse_floats("0.05,0.15"))
    parser.add_argument("--exploration", type=parse_floats, default=parse_floats("0.03,0.10"))
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if args.seeds <= 0 or args.workers <= 0 or args.epochs <= 0:
        parser.error("seeds, workers, and epochs must be positive")

    payload = run_parameter_sweep(
        seed_start=args.seed_start,
        seeds=args.seeds,
        workers=args.workers,
        epochs=args.epochs,
        alphas=args.alpha,
        betas=args.beta,
        rhos=args.rho,
        explorations=args.exploration,
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
