from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import gzip
import json
import math
from pathlib import Path
from statistics import mean, stdev
from typing import Sequence

from .r1 import R1ExperimentConfig, build_r1_conditions, run_r1_condition


FAMILIES = ("homogeneous", "structural_diversity", "diverse_verifiers")
METRICS = (
    "verified_success_rate",
    "selected_regression_rate",
    "selected_security_failure_rate",
    "false_acceptance_rate",
    "mean_compute_per_task",
    "mean_parallel_latency_per_task",
    "mean_human_attention_proxy_per_task",
    "verified_utility_per_unit_cost",
)


@dataclass(frozen=True)
class R1ScalingConfig:
    tasks_per_trial: int = 200
    trials: int = 10
    base_seed: int = 42
    swarm_sizes: tuple[int, ...] = (1, 2, 5, 10)
    difficulty_levels: tuple[tuple[str, float], ...] = (
        ("easy", 0.82),
        ("medium", 0.65),
        ("hard", 0.45),
    )
    structural_error_correlation: float = 0.25
    verifier_error_correlation: float = 0.60

    def __post_init__(self) -> None:
        if self.tasks_per_trial < 1:
            raise ValueError("tasks_per_trial must be >= 1")
        if self.trials < 2:
            raise ValueError("trials must be >= 2")
        if not self.swarm_sizes or self.swarm_sizes[0] != 1:
            raise ValueError("swarm_sizes must start with the one-worker baseline")
        if tuple(sorted(set(self.swarm_sizes))) != self.swarm_sizes:
            raise ValueError("swarm_sizes must be unique and strictly increasing")
        if not self.difficulty_levels:
            raise ValueError("difficulty_levels must not be empty")
        names = [name for name, _ in self.difficulty_levels]
        if len(set(names)) != len(names) or any(not name for name in names):
            raise ValueError("difficulty names must be non-empty and unique")
        if any(not 0.0 <= quality <= 1.0 for _, quality in self.difficulty_levels):
            raise ValueError("difficulty quality values must be in [0, 1]")
        for value in (
            self.structural_error_correlation,
            self.verifier_error_correlation,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("correlations must be in [0, 1]")


def _normal_interval(values: Sequence[float]) -> list[float]:
    center = mean(values)
    margin = 1.96 * stdev(values) / math.sqrt(len(values))
    return [center - margin, center + margin]


def _summary(values: Sequence[float]) -> dict[str, object]:
    return {
        "mean": mean(values),
        "sample_std": stdev(values),
        "normal_approx_95_ci": _normal_interval(values),
        "min": min(values),
        "max": max(values),
    }


def _delta_summary(values: Sequence[float]) -> dict[str, object]:
    result = _summary(values)
    lower, upper = result["normal_approx_95_ci"]
    if lower > 0.0:
        classification = "positive"
    elif upper < 0.0:
        classification = "negative"
    else:
        classification = "uncertain"
    result["classification"] = classification
    return result


def _condition_name(family: str, swarm_size: int) -> str:
    if swarm_size == 1:
        return "single_deterministic"
    return {
        "homogeneous": "identical_replication",
        "structural_diversity": "structural_diversity",
        "diverse_verifiers": "diverse_random_verifiers",
    }[family]


def _run_cell(
    config: R1ScalingConfig,
    *,
    difficulty: str,
    worker_quality: float,
    family: str,
    swarm_size: int,
) -> dict[str, object]:
    r1_config = R1ExperimentConfig(
        tasks_per_trial=config.tasks_per_trial,
        trials=config.trials,
        swarm_size=max(2, swarm_size),
        base_seed=config.base_seed,
        base_worker_success_probability=worker_quality,
        structural_error_correlation=config.structural_error_correlation,
        verifier_error_correlation=config.verifier_error_correlation,
        retain_task_records=False,
    )
    name = _condition_name(family, swarm_size)
    condition = next(item for item in build_r1_conditions(r1_config) if item.name == name)
    trials = []
    for trial_index in range(config.trials):
        seed = config.base_seed + trial_index
        result = run_r1_condition(
            condition,
            tasks=config.tasks_per_trial,
            seed=seed,
            retain_task_records=False,
        )
        trials.append({"seed": seed, "metrics": result["metrics"]})
    return {
        "difficulty": difficulty,
        "worker_quality_assumption": worker_quality,
        "family": family,
        "swarm_size": swarm_size,
        "condition": name,
        "summary": {
            metric: _summary([float(row["metrics"][metric]) for row in trials])
            for metric in METRICS
        },
        "raw_trials": trials,
    }


def _paired_deltas(
    left: dict[str, object],
    right: dict[str, object],
    metric: str,
) -> list[float]:
    left_rows = left["raw_trials"]
    right_rows = right["raw_trials"]
    if [row["seed"] for row in left_rows] != [row["seed"] for row in right_rows]:
        raise ValueError("paired cells must use identical seeds")
    return [
        float(rrow["metrics"][metric]) - float(lrow["metrics"][metric])
        for lrow, rrow in zip(left_rows, right_rows)
    ]


def run_r1_scaling(config: R1ScalingConfig) -> dict[str, object]:
    cells = []
    for difficulty, quality in config.difficulty_levels:
        for family in FAMILIES:
            for swarm_size in config.swarm_sizes:
                cells.append(
                    _run_cell(
                        config,
                        difficulty=difficulty,
                        worker_quality=quality,
                        family=family,
                        swarm_size=swarm_size,
                    )
                )

    by_key = {
        (cell["difficulty"], cell["family"], cell["swarm_size"]): cell
        for cell in cells
    }
    marginals = []
    for difficulty, _ in config.difficulty_levels:
        for family in FAMILIES:
            for lower_n, upper_n in zip(config.swarm_sizes, config.swarm_sizes[1:]):
                lower = by_key[(difficulty, family, lower_n)]
                upper = by_key[(difficulty, family, upper_n)]
                success = _paired_deltas(lower, upper, "verified_success_rate")
                utility = _paired_deltas(
                    lower, upper, "verified_utility_per_unit_cost"
                )
                regressions = _paired_deltas(
                    lower, upper, "selected_regression_rate"
                )
                security = _paired_deltas(
                    lower, upper, "selected_security_failure_rate"
                )
                compute = _paired_deltas(lower, upper, "mean_compute_per_task")
                attention = _paired_deltas(
                    lower, upper, "mean_human_attention_proxy_per_task"
                )
                marginals.append(
                    {
                        "difficulty": difficulty,
                        "family": family,
                        "from_n": lower_n,
                        "to_n": upper_n,
                        "additional_workers": upper_n - lower_n,
                        "verified_success_rate_delta": _delta_summary(success),
                        "verified_utility_per_unit_cost_delta": _delta_summary(
                            utility
                        ),
                        "selected_regression_rate_delta": _delta_summary(regressions),
                        "selected_security_failure_rate_delta": _delta_summary(
                            security
                        ),
                        "mean_compute_per_task_delta": _delta_summary(compute),
                        "mean_human_attention_per_task_delta": _delta_summary(attention),
                        "mean_success_rate_points_per_additional_compute": (
                            mean(success) / mean(compute) if mean(compute) else None
                        ),
                        "mean_success_rate_points_per_additional_worker": (
                            mean(success) / (upper_n - lower_n)
                        ),
                    }
                )

    equal_budget = []
    for difficulty, _ in config.difficulty_levels:
        for swarm_size in config.swarm_sizes[1:]:
            baseline = by_key[(difficulty, "homogeneous", swarm_size)]
            for family in ("structural_diversity", "diverse_verifiers"):
                candidate = by_key[(difficulty, family, swarm_size)]
                compute = _paired_deltas(
                    baseline, candidate, "mean_compute_per_task"
                )
                attention = _paired_deltas(
                    baseline,
                    candidate,
                    "mean_human_attention_proxy_per_task",
                )
                equal_budget.append(
                    {
                        "difficulty": difficulty,
                        "swarm_size": swarm_size,
                        "candidate_family": family,
                        "baseline_family": "homogeneous",
                        "verified_success_rate_delta": _delta_summary(
                            _paired_deltas(
                                baseline, candidate, "verified_success_rate"
                            )
                        ),
                        "verified_utility_per_unit_cost_delta": _delta_summary(
                            _paired_deltas(
                                baseline,
                                candidate,
                                "verified_utility_per_unit_cost",
                            )
                        ),
                        "equal_attempt_count": True,
                        "equal_mean_compute_per_task": all(
                            abs(value) < 1e-12 for value in compute
                        ),
                        "equal_mean_human_attention_per_task": all(
                            abs(value) < 1e-12 for value in attention
                        ),
                    }
                )

    return {
        "schema_version": 1,
        "experiment": "R1-collective-capability-scaling",
        "generator": "randomness_lab.r1_scaling.v1",
        "evidence_level": "synthetic_mechanism",
        "config": asdict(config),
        "cells": cells,
        "marginal_curves": marginals,
        "equal_attempt_budget_comparisons": equal_budget,
        "issue_13_coverage": {
            "represented_as_synthetic_proxies": [
                "one worker",
                "homogeneous groups at N=2,5,10",
                "structurally diverse groups at N=2,5,10",
                "diverse verifier assignment at N=2,5,10",
                "three controlled task-difficulty assumptions",
                "repeated deterministic seeds",
            ],
            "not_represented": [
                "measured strong-model versus small-model quality",
                "planner plus implementer plus tester plus reviewer topology",
                "task-DAG team topology",
                "real held-out software tasks",
                "measured inference cost, reviewer minutes, communication bytes, and duplication",
            ],
        },
        "interpretation_guardrail": (
            "All worker quality, correlation, defects, and verifier behavior are synthetic. "
            "These curves test analysis mechanics and expose negative regimes; they are not "
            "empirical scaling laws for coding agents and cannot close issue #13."
        ),
    }


def render_markdown(result: dict[str, object]) -> str:
    lines = [
        "# R1 collective-capability scaling reference",
        "",
        "Evidence level: **synthetic mechanism only**.",
        "",
        "## Marginal verified-success changes",
        "",
        "| Difficulty | Family | N | Mean delta | 95% interval | Class |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in result["marginal_curves"]:
        summary = row["verified_success_rate_delta"]
        interval = summary["normal_approx_95_ci"]
        lines.append(
            f"| {row['difficulty']} | {row['family']} | {row['from_n']}→{row['to_n']} "
            f"| {summary['mean']:.4f} | [{interval[0]:.4f}, {interval[1]:.4f}] "
            f"| {summary['classification']} |"
        )
    lines.extend(
        [
            "",
            "## Scope boundary",
            "",
            result["interpretation_guardrail"],
            "",
            "The machine-readable companion retains every seeded trial, equal-attempt "
            "comparison, cost delta, and the explicit issue #13 coverage gaps.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_ints(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parse_difficulties(value: str) -> tuple[tuple[str, float], ...]:
    parsed = []
    try:
        for item in value.split(","):
            name, quality = item.strip().split(":", 1)
            parsed.append((name, float(quality)))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use name:quality comma-separated pairs") from exc
    return tuple(parsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_scaling",
        description="Run the synthetic R1 collective-capability N-scaling experiment.",
    )
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--swarm-sizes", type=_parse_ints, default=(1, 2, 5, 10))
    parser.add_argument(
        "--difficulties",
        type=_parse_difficulties,
        default=(("easy", 0.82), ("medium", 0.65), ("hard", 0.45)),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r1_scaling(
        R1ScalingConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            base_seed=args.seed,
            swarm_sizes=args.swarm_sizes,
            difficulty_levels=args.difficulties,
        )
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == ".gz":
            args.output.write_bytes(
                gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0)
            )
        else:
            args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
