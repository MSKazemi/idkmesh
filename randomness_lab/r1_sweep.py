from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from itertools import product
import json
import math
from pathlib import Path
from statistics import mean, stdev
from typing import Sequence

from .r1 import R1ExperimentConfig, build_r1_conditions, run_r1_condition


@dataclass(frozen=True)
class R1SweepConfig:
    tasks_per_trial: int = 200
    trials: int = 10
    base_seed: int = 42
    base_worker_success_probability: float = 0.68
    worker_correlations: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
    verifier_correlations: tuple[float, ...] = (0.0, 0.5, 1.0)
    quality_penalties: tuple[float, ...] = (0.0, 0.05, 0.10)
    swarm_sizes: tuple[int, ...] = (2, 5)

    def __post_init__(self) -> None:
        if self.tasks_per_trial < 1:
            raise ValueError("tasks_per_trial must be >= 1")
        if self.trials < 2:
            raise ValueError("trials must be >= 2")
        if not 0.0 <= self.base_worker_success_probability <= 1.0:
            raise ValueError("base_worker_success_probability must be in [0, 1]")
        if not self.worker_correlations or not self.verifier_correlations:
            raise ValueError("correlation grids must not be empty")
        if not self.quality_penalties or not self.swarm_sizes:
            raise ValueError("quality_penalties and swarm_sizes must not be empty")
        if any(not 0.0 <= value <= 1.0 for value in self.worker_correlations):
            raise ValueError("worker correlations must be in [0, 1]")
        if any(not 0.0 <= value <= 1.0 for value in self.verifier_correlations):
            raise ValueError("verifier correlations must be in [0, 1]")
        if any(not 0.0 <= value <= 1.0 for value in self.quality_penalties):
            raise ValueError("quality penalties must be in [0, 1]")
        if any(value < 2 for value in self.swarm_sizes):
            raise ValueError("all swarm sizes must be >= 2")


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _normal_95_interval(values: Sequence[float]) -> list[float]:
    center = mean(values)
    standard_error = stdev(values) / math.sqrt(len(values))
    margin = 1.96 * standard_error
    return [center - margin, center + margin]


def _delta_summary(values: Sequence[float]) -> dict[str, object]:
    interval = _normal_95_interval(values)
    if interval[0] > 0.0:
        classification = "helps"
    elif interval[1] < 0.0:
        classification = "hurts"
    else:
        classification = "uncertain"
    return {
        "mean_delta": mean(values),
        "sample_std": stdev(values),
        "normal_approx_95_ci": interval,
        "min_delta": min(values),
        "max_delta": max(values),
        "classification": classification,
    }


def _find_condition(conditions, name: str):
    return next(condition for condition in conditions if condition.name == name)


def _apply_quality_penalty(condition, penalty: float):
    adjusted_profiles = []
    for profile in condition.profiles:
        adjusted_worker = replace(
            profile.worker,
            success_probability=_clip_probability(
                profile.worker.success_probability - penalty
            ),
        )
        adjusted_profiles.append(replace(profile, worker=adjusted_worker))
    return replace(condition, profiles=tuple(adjusted_profiles))


def _run_cell(
    *,
    config: R1SweepConfig,
    swarm_size: int,
    worker_correlation: float,
    verifier_correlation: float,
    quality_penalty: float,
    cell_index: int,
) -> dict[str, object]:
    r1_config = R1ExperimentConfig(
        tasks_per_trial=config.tasks_per_trial,
        trials=config.trials,
        swarm_size=swarm_size,
        base_seed=config.base_seed,
        base_worker_success_probability=config.base_worker_success_probability,
        structural_error_correlation=worker_correlation,
        verifier_error_correlation=verifier_correlation,
        retain_task_records=False,
    )
    conditions = build_r1_conditions(r1_config)
    replication = _find_condition(conditions, "identical_replication")
    structural = _apply_quality_penalty(
        _find_condition(conditions, "structural_diversity"),
        quality_penalty,
    )

    trial_pairs: list[dict[str, object]] = []
    success_deltas: list[float] = []
    utility_deltas: list[float] = []
    correlation_values: list[float] = []

    for trial_index in range(config.trials):
        seed = config.base_seed + trial_index
        baseline_result = run_r1_condition(
            replication,
            tasks=config.tasks_per_trial,
            seed=seed,
            retain_task_records=False,
        )
        structural_result = run_r1_condition(
            structural,
            tasks=config.tasks_per_trial,
            seed=seed,
            retain_task_records=False,
        )
        baseline_metrics = baseline_result["metrics"]
        structural_metrics = structural_result["metrics"]
        success_delta = (
            float(structural_metrics["verified_success_rate"])
            - float(baseline_metrics["verified_success_rate"])
        )
        utility_delta = (
            float(structural_metrics["verified_utility_per_unit_cost"])
            - float(baseline_metrics["verified_utility_per_unit_cost"])
        )
        success_deltas.append(success_delta)
        utility_deltas.append(utility_delta)
        realized_correlation = structural_metrics["mean_pairwise_base_error_correlation"]
        if realized_correlation is not None:
            correlation_values.append(float(realized_correlation))

        trial_pairs.append(
            {
                "seed": seed,
                "replication": {
                    "verified_success_rate": baseline_metrics["verified_success_rate"],
                    "verified_utility_per_unit_cost": baseline_metrics[
                        "verified_utility_per_unit_cost"
                    ],
                },
                "structural_diversity": {
                    "verified_success_rate": structural_metrics["verified_success_rate"],
                    "verified_utility_per_unit_cost": structural_metrics[
                        "verified_utility_per_unit_cost"
                    ],
                    "realized_pairwise_base_error_correlation": realized_correlation,
                },
                "delta": {
                    "verified_success_rate": success_delta,
                    "verified_utility_per_unit_cost": utility_delta,
                },
            }
        )

    adjusted_quality = _clip_probability(
        config.base_worker_success_probability - quality_penalty
    )
    return {
        "cell_index": cell_index,
        "parameters": {
            "swarm_size": swarm_size,
            "configured_worker_error_correlation": worker_correlation,
            "configured_verifier_error_correlation": verifier_correlation,
            "structural_worker_quality_penalty": quality_penalty,
            "replication_worker_success_probability": config.base_worker_success_probability,
            "structural_worker_success_probability": adjusted_quality,
        },
        "success_delta": _delta_summary(success_deltas),
        "utility_delta": _delta_summary(utility_deltas),
        "mean_realized_structural_pairwise_base_error_correlation": (
            mean(correlation_values) if correlation_values else None
        ),
        "raw_trial_pairs": trial_pairs,
    }


def run_r1_sweep(config: R1SweepConfig) -> dict[str, object]:
    cells = []
    grid = product(
        config.swarm_sizes,
        config.worker_correlations,
        config.verifier_correlations,
        config.quality_penalties,
    )
    for cell_index, (
        swarm_size,
        worker_correlation,
        verifier_correlation,
        quality_penalty,
    ) in enumerate(grid):
        cells.append(
            _run_cell(
                config=config,
                swarm_size=swarm_size,
                worker_correlation=worker_correlation,
                verifier_correlation=verifier_correlation,
                quality_penalty=quality_penalty,
                cell_index=cell_index,
            )
        )

    success_counts = {"helps": 0, "hurts": 0, "uncertain": 0}
    utility_counts = {"helps": 0, "hurts": 0, "uncertain": 0}
    for cell in cells:
        success_counts[cell["success_delta"]["classification"]] += 1
        utility_counts[cell["utility_delta"]["classification"]] += 1

    return {
        "schema_version": 1,
        "experiment": "R1-help-hurt-sweep",
        "config": asdict(config),
        "cell_count": len(cells),
        "classification_counts": {
            "verified_success": success_counts,
            "verified_utility_per_unit_cost": utility_counts,
        },
        "cells": cells,
        "classification_rule": (
            "helps if the descriptive paired-delta 95% interval is entirely above zero; "
            "hurts if entirely below zero; otherwise uncertain"
        ),
        "interpretation_guardrail": (
            "This sweep maps synthetic assumptions, not real coding-agent performance. "
            "A help/hurt classification must be re-estimated from independent real task data."
        ),
    }


def _parse_float_tuple(value: str) -> tuple[float, ...]:
    try:
        parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not parsed:
        raise argparse.ArgumentTypeError("provide at least one number")
    return parsed


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not parsed:
        raise argparse.ArgumentTypeError("provide at least one integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_sweep",
        description="Map synthetic R1 regimes where structural diversity helps, hurts, or is uncertain.",
    )
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--worker-success", type=float, default=0.68)
    parser.add_argument(
        "--worker-correlations",
        type=_parse_float_tuple,
        default=_parse_float_tuple("0,0.25,0.5,0.75,1"),
    )
    parser.add_argument(
        "--verifier-correlations",
        type=_parse_float_tuple,
        default=_parse_float_tuple("0,0.5,1"),
    )
    parser.add_argument(
        "--quality-penalties",
        type=_parse_float_tuple,
        default=_parse_float_tuple("0,0.05,0.10"),
    )
    parser.add_argument(
        "--swarm-sizes",
        type=_parse_int_tuple,
        default=_parse_int_tuple("2,5"),
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r1_sweep(
        R1SweepConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            base_seed=args.seed,
            base_worker_success_probability=args.worker_success,
            worker_correlations=args.worker_correlations,
            verifier_correlations=args.verifier_correlations,
            quality_penalties=args.quality_penalties,
            swarm_sizes=args.swarm_sizes,
        )
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
