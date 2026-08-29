from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import random
from statistics import mean, median, stdev
import sys
import time
import tracemalloc
from typing import Sequence

from .r2 import (
    R2_POLICIES,
    R2Outage,
    R2RunConfig,
    R2Trace,
    R2TraceConfig,
    generate_r2_trace,
    r2_trace_summary,
    run_r2_policy,
)


BENCHMARK_VERSION = "r2-factor-isolation-v0.1"
OBSERVATION_LAGS = (0, 1, 2, 5, 10)
OFFERED_LOAD_TARGETS = (0.25, 0.50, 0.75, 1.00, 1.25)


@dataclass(frozen=True)
class R2FactorSweepConfig:
    trace_seeds: tuple[int, ...] = (41, 42, 43, 44, 45)
    standard_worker_count: int = 100
    ticks: int = 30
    drain_ticks: int = 300
    policy_seed: int = 1_337

    def __post_init__(self) -> None:
        if len(self.trace_seeds) < 1:
            raise ValueError("trace_seeds must not be empty")
        if any(seed < 0 for seed in self.trace_seeds):
            raise ValueError("trace seeds must be >= 0")
        if self.standard_worker_count < 3:
            raise ValueError("worker counts are too small")
        if self.ticks < 12:
            raise ValueError("ticks must be >= 12")
        if self.drain_ticks < 0:
            raise ValueError("drain_ticks must be >= 0")


def _stable_rank(seed: int, label: str, value: str) -> bytes:
    return hashlib.sha256(f"{seed}|{label}|{value}".encode("utf-8")).digest()


def _base_trace(
    *,
    seed: int,
    worker_count: int,
    ticks: int,
    arrivals: int,
    churn_fraction: float = 0.0,
) -> R2Trace:
    return generate_r2_trace(
        R2TraceConfig(
            worker_count=worker_count,
            ticks=ticks,
            base_arrivals_per_tick=arrivals,
            burst_probability=0.0,
            burst_multiplier=1,
            max_work_units=4,
            churn_fraction=churn_fraction,
            outage_min_ticks=6,
            outage_max_ticks=6,
            seed=seed,
        )
    )


def staleness_trace(*, seed: int, config: R2FactorSweepConfig) -> R2Trace:
    worker_only = _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=0,
    )
    capacity = sum(worker.capacity for worker in worker_only.workers)
    return _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=max(1, round(0.85 * capacity / 2.5)),
        churn_fraction=0.20,
    )


def failure_shape_trace(
    *, seed: int, regional: bool, config: R2FactorSweepConfig
) -> R2Trace:
    worker_only = _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=0,
    )
    capacity = sum(worker.capacity for worker in worker_only.workers)
    trace = _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=max(1, round(0.75 * capacity / 2.5)),
    )
    outage_count = max(1, round(len(trace.workers) * 0.20))
    rng = random.Random(seed * 10_003 + (1 if regional else 0))
    if regional:
        by_zone: dict[str, list[int]] = {}
        for index, worker in enumerate(trace.workers):
            by_zone.setdefault(worker.zone, []).append(index)
        zone = max(sorted(by_zone), key=lambda name: len(by_zone[name]))
        selected = sorted(
            by_zone[zone],
            key=lambda index: _stable_rank(seed, "regional-outage", str(index)),
        )[:outage_count]
        start = config.ticks // 3
        outages = tuple(
            R2Outage(worker_index=index, start_tick=start, end_tick=start + 6)
            for index in selected
        )
    else:
        selected = rng.sample(range(len(trace.workers)), k=outage_count)
        latest_start = max(1, config.ticks - 7)
        independent_outages = []
        for index in selected:
            start = rng.randint(1, latest_start)
            independent_outages.append(
                R2Outage(
                    worker_index=index,
                    start_tick=start,
                    end_tick=min(config.ticks, start + 6),
                )
            )
        outages = tuple(independent_outages)
    return replace(
        trace,
        outages=tuple(
            sorted(outages, key=lambda outage: (outage.start_tick, outage.worker_index))
        ),
    )


def saturation_trace(
    *, seed: int, target: float, config: R2FactorSweepConfig
) -> R2Trace:
    if target <= 0.0:
        raise ValueError("offered-load target must be > 0")
    worker_only = _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=0,
    )
    capacity = sum(worker.capacity for worker in worker_only.workers)
    expected_work = 2.5
    arrivals = max(1, round(target * capacity / expected_work))
    max_arrivals = max(
        arrivals,
        math.ceil(max(OFFERED_LOAD_TARGETS) * capacity / expected_work),
    )
    full_trace = _base_trace(
        seed=seed,
        worker_count=config.standard_worker_count,
        ticks=config.ticks,
        arrivals=max_arrivals,
    )
    tasks = []
    for tick in range(config.ticks):
        tick_tasks = [task for task in full_trace.tasks if task.arrival_tick == tick]
        tasks.extend(tick_tasks[:arrivals])
    return replace(full_trace, tasks=tuple(tasks))


def _coordination_cost(
    trace: R2Trace, policy: str, metrics: dict[str, object]
) -> dict[str, object]:
    routing_attempts = int(metrics["routing_attempts"])
    metadata_probes = int(metrics["metadata_probes"])
    assignments = int(metrics["successful_assignments"])
    capability_memberships = sum(len(worker.capabilities) for worker in trace.workers)
    directory_policy = policy in {"capability-power-two", "global-least-loaded"}
    directory_initialization = capability_memberships if directory_policy else 0
    directory_churn_updates = (
        sum(2 * len(trace.workers[outage.worker_index].capabilities) for outage in trace.outages)
        if directory_policy
        else 0
    )
    routing_messages = routing_attempts + metadata_probes + assignments
    directory_messages = directory_initialization + directory_churn_updates
    modeled_messages = routing_messages + directory_messages
    modeled_bytes = (
        routing_attempts * 64
        + metadata_probes * 48
        + assignments * 96
        + directory_messages * 80
    )
    scheduler_state_entries = (
        2 * len(trace.workers)
        + len(trace.tasks)
        + len(trace.outages)
        + directory_initialization
    )
    return {
        "metadata_probe_operations": metadata_probes,
        "routing_request_messages": routing_attempts,
        "assignment_messages": assignments,
        "modeled_routing_messages": routing_messages,
        "modeled_directory_messages": directory_messages,
        "modeled_total_messages": modeled_messages,
        "modeled_wire_bytes": modeled_bytes,
        "capability_directory_initialization_operations": directory_initialization,
        "capability_directory_churn_update_operations": directory_churn_updates,
        "scheduler_state_entries": scheduler_state_entries,
        "cost_model": {
            "routing_request_bytes": 64,
            "metadata_probe_bytes": 48,
            "assignment_bytes": 96,
            "directory_operation_bytes": 80,
            "scope": "deterministic protocol-cost proxy, not a packet capture",
        },
    }


def _run_policies(
    trace: R2Trace,
    *,
    availability_lag: int,
    load_lag: int,
    config: R2FactorSweepConfig,
) -> dict[str, object]:
    policies: dict[str, object] = {}
    for policy in R2_POLICIES:
        result = run_r2_policy(
            trace,
            policy,
            R2RunConfig(
                availability_observation_lag=availability_lag,
                load_observation_lag=load_lag,
                drain_ticks=config.drain_ticks,
                policy_seed=config.policy_seed + trace.seed,
            ),
        )
        result["coordination_cost"] = _coordination_cost(
            trace, policy, result["metrics"]
        )
        policies[policy] = result
    return policies


def _offered_load(trace: R2Trace) -> float:
    capacity = sum(worker.capacity for worker in trace.workers) * trace.ticks
    work = sum(task.work_units for task in trace.tasks)
    return work / capacity if capacity else 0.0


def _raw_run(
    *,
    factor: str,
    level: str,
    value: float | int | str,
    trace: R2Trace,
    availability_lag: int,
    load_lag: int,
    config: R2FactorSweepConfig,
) -> dict[str, object]:
    return {
        "factor": factor,
        "level": level,
        "value": value,
        "trace_seed": trace.seed,
        "trace": r2_trace_summary(trace),
        "offered_work_per_capacity_tick": _offered_load(trace),
        "availability_observation_lag": availability_lag,
        "load_observation_lag": load_lag,
        "policies": _run_policies(
            trace,
            availability_lag=availability_lag,
            load_lag=load_lag,
            config=config,
        ),
    }


def _numeric_summary(values: Sequence[float]) -> dict[str, object]:
    average = mean(values)
    deviation = stdev(values) if len(values) >= 2 else None
    return {
        "count": len(values),
        "mean": average,
        "min": min(values),
        "max": max(values),
        "sample_standard_deviation": deviation,
    }


def _aggregate(raw_runs: Sequence[dict[str, object]]) -> dict[str, object]:
    metric_names = (
        "completion_rate",
        "mean_wait_ticks",
        "p95_wait_ticks",
        "mean_response_ticks",
        "p95_response_ticks",
        "max_pending_tasks",
        "routing_attempts",
        "failed_assignments",
        "failed_unreachable",
        "failed_capability_mismatch",
        "lost_work_units_due_churn",
        "churn_requeues",
        "mean_churn_recovery_ticks",
        "p95_churn_recovery_ticks",
        "capacity_utilization",
        "jain_worker_utilization_fairness",
        "workers_used_fraction",
        "locality_mismatch_rate_per_successful_assignment",
        "simulated_ticks",
    )
    cost_names = (
        "metadata_probe_operations",
        "modeled_total_messages",
        "modeled_wire_bytes",
        "capability_directory_initialization_operations",
        "capability_directory_churn_update_operations",
        "scheduler_state_entries",
    )
    output: dict[str, object] = {}
    for policy in R2_POLICIES:
        metrics: dict[str, object] = {}
        costs: dict[str, object] = {}
        for name in metric_names:
            values = [
                float(run["policies"][policy]["metrics"][name])
                for run in raw_runs
                if run["policies"][policy]["metrics"][name] is not None
            ]
            metrics[name] = _numeric_summary(values) if values else None
        for name in cost_names:
            values = [
                float(run["policies"][policy]["coordination_cost"][name])
                for run in raw_runs
            ]
            costs[name] = _numeric_summary(values)
        output[policy] = {"metrics": metrics, "coordination_cost": costs}
    return output


def _group_runs(raw_runs: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    keys = sorted({(str(run["factor"]), str(run["level"])) for run in raw_runs})
    cells = []
    for factor, level in keys:
        matching = [
            run
            for run in raw_runs
            if run["factor"] == factor and run["level"] == level
        ]
        cells.append(
            {
                "factor": factor,
                "level": level,
                "value": matching[0]["value"],
                "runs": len(matching),
                "aggregate": _aggregate(matching),
            }
        )
    return cells


def run_factor_sweep(config: R2FactorSweepConfig) -> dict[str, object]:
    raw_runs: list[dict[str, object]] = []
    for seed in config.trace_seeds:
        stale_trace = staleness_trace(seed=seed, config=config)
        for lag in OBSERVATION_LAGS:
            raw_runs.append(
                _raw_run(
                    factor="availability_lag",
                    level=str(lag),
                    value=lag,
                    trace=stale_trace,
                    availability_lag=lag,
                    load_lag=0,
                    config=config,
                )
            )
            if lag:
                raw_runs.append(
                    _raw_run(
                        factor="load_lag",
                        level=str(lag),
                        value=lag,
                        trace=stale_trace,
                        availability_lag=0,
                        load_lag=lag,
                        config=config,
                    )
                )

        for regional in (False, True):
            trace = failure_shape_trace(seed=seed, regional=regional, config=config)
            raw_runs.append(
                _raw_run(
                    factor="failure_shape",
                    level="regional" if regional else "independent",
                    value="regional" if regional else "independent",
                    trace=trace,
                    availability_lag=0,
                    load_lag=0,
                    config=config,
                )
            )

        for target in OFFERED_LOAD_TARGETS:
            trace = saturation_trace(seed=seed, target=target, config=config)
            raw_runs.append(
                _raw_run(
                    factor="offered_load",
                    level=f"{target:.2f}",
                    value=target,
                    trace=trace,
                    availability_lag=0,
                    load_lag=0,
                    config=config,
                )
            )

    return {
        "schema_version": 1,
        "benchmark_version": BENCHMARK_VERSION,
        "config": asdict(config),
        "policies": list(R2_POLICIES),
        "factor_controls": {
            "availability_lag": "one churn trace; load lag fixed at zero",
            "load_lag": "the same churn trace; availability lag fixed at zero",
            "failure_shape": (
                "worker/task attributes and outage count/duration are matched; "
                "independent start times are compared with one simultaneous zone outage"
            ),
            "offered_load": (
                "worker generator, tick horizon, task generator, and policy are fixed; "
                "only requested arrivals per tick change"
            ),
        },
        "authority": {
            "integration_authority": "none",
            "synthetic_results_are_real_fleet_evidence": False,
        },
        "raw_runs": raw_runs,
        "cells": _group_runs(raw_runs),
    }


def run_profile(
    config: R2FactorSweepConfig,
    *,
    repetitions: int,
) -> dict[str, object]:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    trace = saturation_trace(seed=config.trace_seeds[0], target=0.75, config=config)
    profiles: dict[str, object] = {}
    for policy in R2_POLICIES:
        cpu_ms: list[float] = []
        peak_bytes: list[float] = []
        for _ in range(repetitions):
            gc.collect()
            tracemalloc.start()
            start = time.process_time_ns()
            run_r2_policy(
                trace,
                policy,
                R2RunConfig(
                    availability_observation_lag=0,
                    load_observation_lag=0,
                    drain_ticks=config.drain_ticks,
                    policy_seed=config.policy_seed + trace.seed,
                ),
            )
            elapsed = time.process_time_ns() - start
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            cpu_ms.append(elapsed / 1_000_000)
            peak_bytes.append(float(peak))
        profiles[policy] = {
            "cpu_time_ms_samples": cpu_ms,
            "cpu_time_ms_median": median(cpu_ms),
            "peak_traced_bytes_samples": peak_bytes,
            "peak_traced_bytes_median": median(peak_bytes),
        }
    return {
        "schema_version": 1,
        "benchmark_version": BENCHMARK_VERSION,
        "profile": "single-process scheduler CPU and Python traced peak allocation",
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "repetitions": repetitions,
        "trace": r2_trace_summary(trace),
        "offered_work_per_capacity_tick": _offered_load(trace),
        "policies": profiles,
        "guardrail": (
            "Measured timings and allocations are host-specific observations, not "
            "deterministic protocol costs or distributed-network measurements."
        ),
    }


def self_test() -> None:
    config = R2FactorSweepConfig(
        trace_seeds=(3,),
        standard_worker_count=30,
        ticks=12,
        drain_ticks=40,
    )
    independent = failure_shape_trace(seed=3, regional=False, config=config)
    regional = failure_shape_trace(seed=3, regional=True, config=config)
    assert len(independent.outages) == len(regional.outages)
    assert len({outage.start_tick for outage in regional.outages}) == 1
    assert len({independent.workers[outage.worker_index].zone for outage in regional.outages}) == 1
    low = saturation_trace(seed=3, target=0.25, config=config)
    high = saturation_trace(seed=3, target=1.25, config=config)
    assert _offered_load(high) > _offered_load(low)
    first = run_factor_sweep(config)
    second = run_factor_sweep(config)
    assert first == second
    assert first["authority"]["integration_authority"] == "none"


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
        prog="python -m randomness_lab.r2_factor_sweep",
        description="Run factor-isolated R2 scaling experiments.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--benchmark", action="store_true")
    mode.add_argument("--profile", action="store_true")
    parser.add_argument("--seeds", type=_parse_int_tuple, default=(41, 42, 43, 44, 45))
    parser.add_argument("--workers", type=int, default=100)
    parser.add_argument("--ticks", type=int, default=30)
    parser.add_argument("--drain-ticks", type=int, default=300)
    parser.add_argument("--policy-seed", type=int, default=1_337)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        print("OK: R2 factor-isolation self-test passed")
        return 0
    config = R2FactorSweepConfig(
        trace_seeds=args.seeds,
        standard_worker_count=args.workers,
        ticks=args.ticks,
        drain_ticks=args.drain_ticks,
        policy_seed=args.policy_seed,
    )
    report = (
        run_profile(config, repetitions=args.repetitions)
        if args.profile
        else run_factor_sweep(config)
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
