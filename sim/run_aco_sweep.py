#!/usr/bin/env python3
"""Run repeated-seed comparisons for ACO stigmergic task routing."""

from __future__ import annotations

import argparse
import json
import statistics
from typing import Dict, List, Sequence

import aco_stigmergy_sim as sim


STRATEGIES = ("random", "greedy", "capability", "aco")
METRICS = (
    "verified_utility_per_cost",
    "duplicate_rate",
    "task_coverage",
    "max_selection_share",
    "neglected_high_value_tasks",
)


def aggregate(rows: List[Dict[str, object]]) -> Dict[str, object]:
    output: Dict[str, object] = {"runs": len(rows)}
    for metric in METRICS:
        values = [float(row[metric]) for row in rows]
        output[metric] = {
            "mean": round(statistics.fmean(values), 9),
            "min": round(min(values), 9),
            "max": round(max(values), 9),
        }
    return output


def run_sweep(seed_start: int, seeds: int, workers: int, epochs: int) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")

    by_strategy: Dict[str, List[Dict[str, object]]] = {name: [] for name in STRATEGIES}
    per_seed: List[Dict[str, object]] = []

    for offset in range(seeds):
        seed = seed_start + offset
        seed_rows: Dict[str, object] = {"seed": seed, "strategies": {}}
        for strategy in STRATEGIES:
            # The same seed gives every strategy the same generated worker population.
            # Routing then changes the subsequent stochastic path, which is intentional.
            row = sim.run_strategy(strategy, seed=seed, workers=workers, epochs=epochs)
            by_strategy[strategy].append(row)
            seed_rows["strategies"][strategy] = {
                metric: row[metric] for metric in METRICS
            }
        per_seed.append(seed_rows)

    summary = {strategy: aggregate(rows) for strategy, rows in by_strategy.items()}
    return {
        "experiment": "aco-stigmergic-task-routing-sweep-v0",
        "model_warning": "Synthetic illustrative simulation; not empirical evidence about real contributors.",
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "summary": summary,
        "per_seed": per_seed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if args.seeds <= 0 or args.workers <= 0 or args.epochs <= 0:
        parser.error("seeds, workers, and epochs must be positive")

    payload = run_sweep(args.seed_start, args.seeds, args.workers, args.epochs)
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
