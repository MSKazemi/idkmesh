from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import math
from pathlib import Path
import json
from statistics import mean, stdev
from typing import Sequence

from .r2 import (
    R2_POLICIES,
    R2RunConfig,
    R2Trace,
    R2TraceConfig,
    R2Worker,
    generate_r2_trace,
    r2_trace_summary,
    run_r2_policy,
)


@dataclass(frozen=True)
class R2ScaleRegime:
    name: str
    churn_fraction: float
    availability_lag: int
    load_lag: int
    burst_probability: float
    burst_multiplier: int


R2_SCALE_REGIMES = {
    "fresh": R2ScaleRegime(
        name="fresh",
        churn_fraction=0.0,
        availability_lag=0,
        load_lag=0,
        burst_probability=0.05,
        burst_multiplier=3,
    ),
    "moderate": R2ScaleRegime(
        name="moderate",
        churn_fraction=0.10,
        availability_lag=2,
        load_lag=2,
        burst_probability=0.10,
        burst_multiplier=5,
    ),
    "stale": R2ScaleRegime(
        name="stale",
        churn_fraction=0.20,
        availability_lag=5,
        load_lag=5,
        burst_probability=0.20,
        burst_multiplier=8,
    ),
}


@dataclass(frozen=True)
class R2ScaleConfig:
    worker_counts: tuple[int, ...] = (1, 10, 100, 1_000, 10_000, 100_000)
    trace_seeds: tuple[int, ...] = (42,)
    regimes: tuple[str, ...] = ("fresh", "moderate", "stale")
    ticks: int = 30
    arrival_divisor: int = 1_000
    max_arrivals_per_tick: int = 100
    max_work_units: int = 8
    outage_min_ticks: int = 3
    outage_max_ticks: int = 15
    drain_ticks: int = 250
    policy_seed: int = 1_337
    oracle_max_workers: int = 10_000

    def __post_init__(self) -> None:
        if not self.worker_counts or any(value < 1 for value in self.worker_counts):
            raise ValueError("worker_counts must contain positive integers")
        if not self.trace_seeds:
            raise ValueError("trace_seeds must not be empty")
        unknown = [name for name in self.regimes if name not in R2_SCALE_REGIMES]
        if unknown:
            raise ValueError(f"unknown R2 scale regimes: {', '.join(unknown)}")
        if self.ticks < 1:
            raise ValueError("ticks must be >= 1")
        if self.arrival_divisor < 1:
            raise ValueError("arrival_divisor must be >= 1")
        if self.max_arrivals_per_tick < 1:
            raise ValueError("max_arrivals_per_tick must be >= 1")
        if self.max_work_units < 1:
            raise ValueError("max_work_units must be >= 1")
        if self.drain_ticks < 0:
            raise ValueError("drain_ticks must be >= 0")
        if self.oracle_max_workers < 1:
            raise ValueError("oracle_max_workers must be >= 1")


def _arrivals_for_scale(worker_count: int, config: R2ScaleConfig) -> int:
    return max(
        1,
        min(
            config.max_arrivals_per_tick,
            math.ceil(worker_count / config.arrival_divisor),
        ),
    )


def _make_single_worker_fully_capable(trace: R2Trace) -> R2Trace:
    if len(trace.workers) != 1:
        return trace
    required = {task.required_capability for task in trace.tasks}
    worker = trace.workers[0]
    capabilities = tuple(sorted(set(worker.capabilities) | required))
    if capabilities == worker.capabilities:
        return trace
    return replace(trace, workers=(replace(worker, capabilities=capabilities),))


def _metric_summary(values: Sequence[float]) -> dict[str, object]:
    count = len(values)
    average = mean(values) if values else None
    sample_stddev = stdev(values) if count >= 2 else None
    ci95 = None
    if average is not None and sample_stddev is not None:
        # Two-sided 95% Student-t critical values. Small repeated-seed cohorts
        # should not silently use the narrower large-sample normal interval.
        t95_by_df = {
            1: 12.706,
            2: 4.303,
            3: 3.182,
            4: 2.776,
            5: 2.571,
            6: 2.447,
            7: 2.365,
            8: 2.306,
            9: 2.262,
            10: 2.228,
            11: 2.201,
            12: 2.179,
            13: 2.160,
            14: 2.145,
            15: 2.131,
            16: 2.120,
            17: 2.110,
            18: 2.101,
            19: 2.093,
            20: 2.086,
            21: 2.080,
            22: 2.074,
            23: 2.069,
            24: 2.064,
            25: 2.060,
            26: 2.056,
            27: 2.052,
            28: 2.048,
            29: 2.045,
            30: 2.042,
        }
        critical = t95_by_df.get(count - 1, 1.96)
        half_width = critical * sample_stddev / math.sqrt(count)
        ci95 = {
            "low": average - half_width,
            "high": average + half_width,
            "method": "student_t_95",
        }
    return {
        "count": count,
        "mean": average,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "sample_standard_deviation": sample_stddev,
        "mean_ci95": ci95,
    }


def _aggregate_policy_runs(runs: Sequence[dict[str, object]]) -> dict[str, object]:
    metric_names = (
        "completion_rate",
        "p95_wait_ticks",
        "p95_response_ticks",
        "max_worker_queue_depth",
        "p95_tick_max_queue_depth",
        "failed_assignments",
        "failed_unreachable",
        "failed_capability_mismatch",
        "mean_metadata_probes_per_routing_attempt",
        "capacity_utilization",
        "jain_worker_utilization_fairness",
        "mean_churn_recovery_ticks",
    )
    output: dict[str, object] = {}
    for metric_name in metric_names:
        values = []
        for run in runs:
            value = run["metrics"].get(metric_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        output[metric_name] = _metric_summary(values)
    return output


def _oracle_comparison(
    local_metrics: dict[str, object],
    oracle_metrics: dict[str, object],
) -> dict[str, object]:
    local_completion = float(local_metrics["completion_rate"])
    oracle_completion = float(oracle_metrics["completion_rate"])
    completion_gap = oracle_completion - local_completion

    local_response = local_metrics.get("p95_response_ticks")
    oracle_response = oracle_metrics.get("p95_response_ticks")
    response_ratio = None
    if (
        isinstance(local_response, (int, float))
        and isinstance(oracle_response, (int, float))
        and float(oracle_response) > 0.0
    ):
        response_ratio = float(local_response) / float(oracle_response)

    local_probes = float(local_metrics["mean_metadata_probes_per_routing_attempt"])
    oracle_probes = float(oracle_metrics["mean_metadata_probes_per_routing_attempt"])
    metadata_ratio = local_probes / oracle_probes if oracle_probes > 0.0 else None

    loses_badly = completion_gap >= 0.10 or (
        response_ratio is not None and response_ratio >= 2.0
    )
    return {
        "oracle_minus_local_completion_rate": completion_gap,
        "local_to_oracle_p95_response_ratio": response_ratio,
        "local_to_oracle_metadata_probe_ratio": metadata_ratio,
        "loses_badly": loses_badly,
        "loses_badly_rule": (
            "oracle completion advantage >= 0.10 OR local p95 response >= 2x oracle"
        ),
    }


def _run_scale_seed(
    worker_count: int,
    regime: R2ScaleRegime,
    trace_seed: int,
    config: R2ScaleConfig,
) -> dict[str, object]:
    arrivals = _arrivals_for_scale(worker_count, config)
    trace = generate_r2_trace(
        R2TraceConfig(
            worker_count=worker_count,
            ticks=config.ticks,
            base_arrivals_per_tick=arrivals,
            burst_probability=regime.burst_probability,
            burst_multiplier=regime.burst_multiplier,
            max_work_units=config.max_work_units,
            churn_fraction=regime.churn_fraction,
            outage_min_ticks=config.outage_min_ticks,
            outage_max_ticks=config.outage_max_ticks,
            seed=trace_seed,
        )
    )
    trace = _make_single_worker_fully_capable(trace)
    run_config = R2RunConfig(
        availability_observation_lag=regime.availability_lag,
        load_observation_lag=regime.load_lag,
        drain_ticks=config.drain_ticks,
        policy_seed=config.policy_seed + trace_seed,
    )

    policy_results: dict[str, object] = {}
    for policy in R2_POLICIES:
        if policy == "global-least-loaded" and worker_count > config.oracle_max_workers:
            policy_results[policy] = {
                "status": "skipped",
                "reason": (
                    f"worker_count {worker_count} exceeds oracle_max_workers "
                    f"{config.oracle_max_workers}; full O(n) metadata scan omitted"
                ),
            }
            continue
        result = run_r2_policy(trace, policy, run_config)
        policy_results[policy] = {
            "status": "ok",
            "trace_digest": result["trace_digest"],
            "metrics": result["metrics"],
        }

    oracle = policy_results["global-least-loaded"]
    comparisons: dict[str, object] = {}
    if oracle["status"] == "ok":
        oracle_metrics = oracle["metrics"]
        for policy in R2_POLICIES:
            if policy == "global-least-loaded":
                continue
            local = policy_results[policy]
            if local["status"] == "ok":
                comparisons[policy] = _oracle_comparison(
                    local["metrics"], oracle_metrics
                )
    else:
        comparisons["oracle"] = {
            "status": "unavailable",
            "reason": oracle["reason"],
        }

    return {
        "trace_seed": trace_seed,
        "trace_config": {
            "worker_count": worker_count,
            "ticks": config.ticks,
            "base_arrivals_per_tick": arrivals,
            "burst_probability": regime.burst_probability,
            "burst_multiplier": regime.burst_multiplier,
            "max_work_units": config.max_work_units,
            "churn_fraction": regime.churn_fraction,
            "outage_min_ticks": config.outage_min_ticks,
            "outage_max_ticks": config.outage_max_ticks,
        },
        "trace": r2_trace_summary(trace),
        "run_config": asdict(run_config),
        "policies": policy_results,
        "oracle_comparisons": comparisons,
    }


def run_r2_scale_sweep(config: R2ScaleConfig) -> dict[str, object]:
    cells = []
    for regime_name in config.regimes:
        regime = R2_SCALE_REGIMES[regime_name]
        for worker_count in config.worker_counts:
            raw_runs = [
                _run_scale_seed(worker_count, regime, seed, config)
                for seed in config.trace_seeds
            ]

            aggregate: dict[str, object] = {}
            for policy in R2_POLICIES:
                successful = [
                    run["policies"][policy]
                    for run in raw_runs
                    if run["policies"][policy]["status"] == "ok"
                ]
                aggregate[policy] = (
                    {
                        "status": "ok",
                        "runs": len(successful),
                        "metrics": _aggregate_policy_runs(successful),
                    }
                    if successful
                    else {
                        "status": "skipped",
                        "runs": 0,
                        "reason": raw_runs[0]["policies"][policy].get(
                            "reason", "no successful runs"
                        ),
                    }
                )

            bad_counts: dict[str, int] = {}
            for policy in R2_POLICIES:
                if policy == "global-least-loaded":
                    continue
                comparisons = [
                    run["oracle_comparisons"].get(policy)
                    for run in raw_runs
                ]
                usable = [
                    value for value in comparisons if isinstance(value, dict)
                ]
                bad_counts[policy] = sum(
                    int(bool(value.get("loses_badly"))) for value in usable
                )

            cells.append(
                {
                    "regime": asdict(regime),
                    "worker_count": worker_count,
                    "raw_runs": raw_runs,
                    "aggregate": aggregate,
                    "loses_badly_vs_oracle_count": bad_counts,
                }
            )

    return {
        "schema_version": 1,
        "experiment": "R2-scale-regime-sweep",
        "config": asdict(config),
        "cell_count": len(cells),
        "cells": cells,
        "scale_guardrail": (
            "The 100,000-worker cells are intended to exercise O(1)-sample local schedulers. "
            "The full global oracle is intentionally skipped above oracle_max_workers because "
            "its full-pool scan is exactly the coordination pattern R2 is testing against."
        ),
        "regime_guardrail": (
            "fresh/moderate/stale presets change several stressors together and are descriptive "
            "regimes, not causal one-factor experiments."
        ),
    }


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not parsed:
        raise argparse.ArgumentTypeError("provide at least one integer")
    return parsed


def _parse_regimes(value: str) -> tuple[str, ...]:
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = [item for item in parsed if item not in R2_SCALE_REGIMES]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown regimes: {', '.join(unknown)}; choose from {', '.join(R2_SCALE_REGIMES)}"
        )
    if not parsed:
        raise argparse.ArgumentTypeError("provide at least one regime")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r2_scale",
        description="Run R2 scheduling policies across worker-count and stress-regime cells.",
    )
    parser.add_argument(
        "--worker-counts",
        type=_parse_int_tuple,
        default=(1, 10, 100, 1_000, 10_000, 100_000),
    )
    parser.add_argument("--seeds", type=_parse_int_tuple, default=(42,))
    parser.add_argument(
        "--regimes", type=_parse_regimes, default=("fresh", "moderate", "stale")
    )
    parser.add_argument("--ticks", type=int, default=30)
    parser.add_argument("--arrival-divisor", type=int, default=1_000)
    parser.add_argument("--max-arrivals", type=int, default=100)
    parser.add_argument("--max-work", type=int, default=8)
    parser.add_argument("--outage-min", type=int, default=3)
    parser.add_argument("--outage-max", type=int, default=15)
    parser.add_argument("--drain-ticks", type=int, default=250)
    parser.add_argument("--policy-seed", type=int, default=1_337)
    parser.add_argument("--oracle-max-workers", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r2_scale_sweep(
        R2ScaleConfig(
            worker_counts=args.worker_counts,
            trace_seeds=args.seeds,
            regimes=args.regimes,
            ticks=args.ticks,
            arrival_divisor=args.arrival_divisor,
            max_arrivals_per_tick=args.max_arrivals,
            max_work_units=args.max_work,
            outage_min_ticks=args.outage_min,
            outage_max_ticks=args.outage_max,
            drain_ticks=args.drain_ticks,
            policy_seed=args.policy_seed,
            oracle_max_workers=args.oracle_max_workers,
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
