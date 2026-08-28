#!/usr/bin/env python3
"""Run the IDKMesh vague-goal simulator across many random seeds."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List

HERE = Path(__file__).resolve().parent
SIM_PATH = HERE / "emergence_sim.py"

spec = importlib.util.spec_from_file_location("emergence_sim", SIM_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)

SUMMARY_METRICS = (
    "pre_change_best",
    "post_change_immediate",
    "post_change_mean",
    "final_best",
    "viable_evaluations",
    "archive_size",
)


def stats(values: List[float]) -> Dict[str, float]:
    n = len(values)
    mu = mean(values)
    sd = stdev(values) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n else 0.0
    return {
        "n": n,
        "mean": round(mu, 6),
        "stdev": round(sd, 6),
        "ci95_low": round(mu - half, 6),
        "ci95_high": round(mu + half, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def sweep(seeds: int, seed_start: int, agents: int, generations: int, change_at: int, bins: int) -> Dict[str, object]:
    rows = {name: {metric: [] for metric in SUMMARY_METRICS} for name in ("random", "scalar", "qd")}
    pairwise = {
        "qd_gt_scalar_post_change_mean": 0,
        "qd_gt_random_post_change_mean": 0,
        "qd_gt_scalar_final_best": 0,
        "qd_gt_random_final_best": 0,
    }

    for seed in range(seed_start, seed_start + seeds):
        result = sim.run("all", seed=seed, agents=agents, generations=generations, change_at=change_at, bins=bins)
        by_name = {r["strategy"]: r for r in result["results"]}
        for name, row in by_name.items():
            for metric in SUMMARY_METRICS:
                rows[name][metric].append(float(row[metric]))

        pairwise["qd_gt_scalar_post_change_mean"] += int(by_name["qd"]["post_change_mean"] > by_name["scalar"]["post_change_mean"])
        pairwise["qd_gt_random_post_change_mean"] += int(by_name["qd"]["post_change_mean"] > by_name["random"]["post_change_mean"])
        pairwise["qd_gt_scalar_final_best"] += int(by_name["qd"]["final_best"] > by_name["scalar"]["final_best"])
        pairwise["qd_gt_random_final_best"] += int(by_name["qd"]["final_best"] > by_name["random"]["final_best"])

    aggregate = {
        name: {metric: stats(values) for metric, values in metrics.items()}
        for name, metrics in rows.items()
    }
    wins = {
        key: {"wins": value, "trials": seeds, "rate": round(value / seeds, 6)}
        for key, value in pairwise.items()
    }
    return {
        "experiment": "emergence-from-vague-goals-sweep-v0",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
        },
        "aggregate": aggregate,
        "pairwise_wins": wins,
        "limitations": [
            "Confidence intervals are normal approximations over synthetic random seeds, not uncertainty over real-world tasks.",
            "Strategies do not yet use strictly matched total proposal/evaluation cost.",
            "The QD strategy is explicitly designed around multiple plausible goals, while the scalar baseline is intentionally fixed to the initial goal."
        ]
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=int, default=100)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--agents", type=int, default=100)
    p.add_argument("--generations", type=int, default=80)
    p.add_argument("--change-at", type=int, default=40)
    p.add_argument("--bins", type=int, default=8)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    if args.seeds < 2:
        p.error("--seeds must be >= 2")
    if args.agents < 1:
        p.error("--agents must be >= 1")
    if args.generations < 2:
        p.error("--generations must be >= 2")
    if not 1 <= args.change_at < args.generations:
        p.error("--change-at must satisfy 1 <= change-at < generations")
    return args


def main() -> None:
    args = parse_args()
    result = sweep(args.seeds, args.seed_start, args.agents, args.generations, args.change_at, args.bins)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
