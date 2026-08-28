#!/usr/bin/env python3
"""Sweep verifier error correlation for the IDKMesh emergence simulator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List

HERE = Path(__file__).resolve().parent
SWEEP_PATH = HERE / "run_emergence_sweep.py"

spec = importlib.util.spec_from_file_location("run_emergence_sweep", SWEEP_PATH)
sweep_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sweep_mod
assert spec.loader is not None
spec.loader.exec_module(sweep_mod)

REPORT_METRICS = (
    "post_change_mean",
    "final_best",
    "false_accept_rate",
    "false_reject_rate",
    "panel_disagreement_rate",
)


def parse_correlations(raw: str) -> List[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("at least one correlation value is required")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("correlations must be between 0.0 and 1.0")
    return values


def compact_level(correlation: float, sweep_result: Dict[str, object]) -> Dict[str, object]:
    aggregate = sweep_result["aggregate"]
    compact = {
        strategy: {metric: aggregate[strategy][metric] for metric in REPORT_METRICS}
        for strategy in ("random", "scalar", "qd")
    }
    return {
        "correlation": correlation,
        "aggregate": compact,
        "pairwise_wins": sweep_result["pairwise_wins"],
    }


def correlation_sweep(correlations: Iterable[float], seeds: int, seed_start: int, agents: int, generations: int, change_at: int, bins: int, verifiers: int, verifier_accuracy: float, verification_quorum: float) -> Dict[str, object]:
    levels = []
    correlations = list(correlations)
    for correlation in correlations:
        sweep_result = sweep_mod.sweep(
            seeds=seeds,
            seed_start=seed_start,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verifiers=verifiers,
            verifier_accuracy=verifier_accuracy,
            verifier_correlation=correlation,
            verification_quorum=verification_quorum,
        )
        levels.append(compact_level(correlation, sweep_result))

    return {
        "experiment": "correlated-verifier-sweep-v0",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "verifiers": verifiers,
            "verifier_accuracy": verifier_accuracy,
            "verification_quorum": verification_quorum,
            "correlations": correlations,
        },
        "levels": levels,
        "interpretation_limits": [
            "Synthetic viability classification only; not a real code-review benchmark.",
            "Correlation is implemented as a shared correctness shock mixture, not fitted to real verifier behavior.",
            "Search strategies still do not have strictly matched total proposal/evaluation cost.",
        ],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correlations", default="0,0.25,0.5,0.75,1")
    p.add_argument("--seeds", type=int, default=50)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--agents", type=int, default=40)
    p.add_argument("--generations", type=int, default=30)
    p.add_argument("--change-at", type=int, default=15)
    p.add_argument("--bins", type=int, default=6)
    p.add_argument("--verifiers", type=int, default=5)
    p.add_argument("--verifier-accuracy", type=float, default=0.75)
    p.add_argument("--verification-quorum", type=float, default=0.5)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    try:
        args.correlations = parse_correlations(args.correlations)
    except ValueError as exc:
        p.error(str(exc))
    if args.seeds < 2:
        p.error("--seeds must be >= 2")
    if args.verifiers < 1:
        p.error("--verifiers must be >= 1")
    if not 0.5 <= args.verifier_accuracy <= 1.0:
        p.error("--verifier-accuracy must be between 0.5 and 1.0")
    if not 0.0 <= args.verification_quorum < 1.0:
        p.error("--verification-quorum must be in [0.0, 1.0)")
    return args


def main() -> None:
    args = parse_args()
    output = correlation_sweep(
        correlations=args.correlations,
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        verifiers=args.verifiers,
        verifier_accuracy=args.verifier_accuracy,
        verification_quorum=args.verification_quorum,
    )
    print(json.dumps(output, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
