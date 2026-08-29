from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path

from .r2 import (
    R2_POLICIES,
    R2RunConfig,
    R2Trace,
    R2TraceConfig,
    generate_r2_trace,
    r2_trace_digest,
    r2_trace_summary,
    run_r2_policy,
)
from .r2_scale import _aggregate_policy_runs, _oracle_comparison


@dataclass(frozen=True)
class R2CapabilityRarityConfig:
    worker_count: int = 1_000
    capability_fractions: tuple[float, ...] = (0.50, 0.20, 0.10, 0.05, 0.01, 0.001)
    trace_seeds: tuple[int, ...] = (41, 42, 43, 44, 45)
    ticks: int = 100
    arrivals_per_tick: int = 1
    drain_ticks: int = 250
    policy_seed: int = 1_337
    rare_capability: str = "rare-capability"

    def __post_init__(self) -> None:
        if self.worker_count < 2:
            raise ValueError("worker_count must be >= 2")
        if not self.capability_fractions:
            raise ValueError("capability_fractions must not be empty")
        if len(set(self.capability_fractions)) != len(self.capability_fractions):
            raise ValueError("capability_fractions must be unique")
        if any(not 0.0 < value <= 1.0 for value in self.capability_fractions):
            raise ValueError("capability_fractions must be in (0, 1]")
        if not self.trace_seeds:
            raise ValueError("trace_seeds must not be empty")
        if self.ticks < 1 or self.arrivals_per_tick < 1 or self.drain_ticks < 0:
            raise ValueError("ticks/arrivals must be positive and drain_ticks non-negative")
        if not self.rare_capability:
            raise ValueError("rare_capability must not be empty")
        if self.rare_capability in {"python", "cpu", "gpu"}:
            raise ValueError("rare_capability must not reuse a baseline capability")


def _capable_count(worker_count: int, fraction: float) -> int:
    return max(1, min(worker_count, math.ceil(worker_count * fraction)))


def _worker_order(trace: R2Trace, capability: str) -> tuple[int, ...]:
    return tuple(sorted(
        range(len(trace.workers)),
        key=lambda index: hashlib.sha256(
            f"{trace.seed}|{capability}|{trace.workers[index].id}".encode()
        ).digest(),
    ))


def _base_trace(config: R2CapabilityRarityConfig, seed: int) -> R2Trace:
    generated = generate_r2_trace(R2TraceConfig(
        worker_count=config.worker_count,
        ticks=config.ticks,
        base_arrivals_per_tick=config.arrivals_per_tick,
        burst_probability=0.0,
        burst_multiplier=1,
        max_work_units=1,
        churn_fraction=0.0,
        seed=seed,
    ))
    return replace(generated, tasks=tuple(
        replace(task, required_capability=config.rare_capability)
        for task in generated.tasks
    ))


def _project_capability(
    base: R2Trace,
    capability: str,
    fraction: float,
) -> tuple[R2Trace, tuple[str, ...]]:
    selected = set(
        _worker_order(base, capability)[:_capable_count(len(base.workers), fraction)]
    )
    workers = tuple(replace(
        worker,
        capabilities=tuple(sorted(
            (set(worker.capabilities) - {capability})
            | ({capability} if index in selected else set())
        )),
    ) for index, worker in enumerate(base.workers))
    capable_ids = tuple(worker.id for worker in workers if capability in worker.capabilities)
    return replace(base, workers=workers), capable_ids


def _run_seed(
    base: R2Trace,
    fraction: float,
    config: R2CapabilityRarityConfig,
) -> dict[str, object]:
    trace, capable_ids = _project_capability(base, config.rare_capability, fraction)
    run_config = R2RunConfig(
        availability_observation_lag=0,
        load_observation_lag=0,
        drain_ticks=config.drain_ticks,
        policy_seed=config.policy_seed + base.seed,
    )
    policies: dict[str, dict[str, object]] = {}
    for policy in R2_POLICIES:
        result = run_r2_policy(trace, policy, run_config)
        policies[policy] = {
            "status": "ok",
            "trace_digest": result["trace_digest"],
            "metrics": result["metrics"],
        }
    oracle = policies["global-least-loaded"]["metrics"]
    return {
        "trace_seed": base.seed,
        "base_trace_digest": r2_trace_digest(base),
        "projected_trace_digest": r2_trace_digest(trace),
        "capable_worker_count": len(capable_ids),
        "actual_capability_fraction": len(capable_ids) / len(base.workers),
        "capable_worker_ids": list(capable_ids),
        "capable_worker_ids_digest": "sha256:"
        + hashlib.sha256("\n".join(capable_ids).encode()).hexdigest(),
        "capable_worker_capacity": sum(
            worker.capacity
            for worker in trace.workers
            if config.rare_capability in worker.capabilities
        ),
        "trace": r2_trace_summary(trace),
        "run_config": asdict(run_config),
        "policies": policies,
        "oracle_comparisons": {
            policy: _oracle_comparison(policies[policy]["metrics"], oracle)
            for policy in R2_POLICIES if policy != "global-least-loaded"
        },
    }


def run_r2_capability_rarity_sweep(config: R2CapabilityRarityConfig) -> dict[str, object]:
    bases = {seed: _base_trace(config, seed) for seed in config.trace_seeds}
    cells = []
    for fraction in config.capability_fractions:
        raw_runs = [_run_seed(bases[seed], fraction, config) for seed in config.trace_seeds]
        cells.append({
            "requested_capability_fraction": fraction,
            "capable_worker_count": _capable_count(config.worker_count, fraction),
            "actual_capability_fraction": (
                _capable_count(config.worker_count, fraction) / config.worker_count
            ),
            "raw_runs": raw_runs,
            "aggregate": {
                policy: {
                    "status": "ok",
                    "runs": len(raw_runs),
                    "metrics": _aggregate_policy_runs(
                        [run["policies"][policy] for run in raw_runs]
                    ),
                }
                for policy in R2_POLICIES
            },
            "loses_badly_vs_oracle_count": {
                policy: sum(
                    int(bool(run["oracle_comparisons"][policy]["loses_badly"]))
                    for run in raw_runs
                )
                for policy in R2_POLICIES
                if policy != "global-least-loaded"
            },
        })
    return {
        "schema_version": 1,
        "experiment": "R2-factor-isolated-capability-rarity",
        "config": asdict(config),
        "cell_count": len(cells),
        "controls": {
            "churn_fraction": 0.0,
            "availability_observation_lag": 0,
            "load_observation_lag": 0,
            "burst_probability": 0.0,
            "work_units_per_task": 1,
            "matched_base_trace_across_fractions": True,
            "nested_capable_worker_sets": True,
        },
        "cells": cells,
        "interpretation_guardrail": (
            "This isolates synthetic capability prevalence under fixed offered load; "
            "it does not establish optimality under churn, stale state, regional failure, "
            "heterogeneous requirements, or workload saturation."
        ),
    }


def _parse_tuple(raw: str, cast: type) -> tuple:
    try:
        values = tuple(cast(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not values:
        raise argparse.ArgumentTypeError("provide at least one value")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the factor-isolated R2 capability-rarity sweep."
    )
    parser.add_argument("--workers", type=int, default=1_000)
    parser.add_argument(
        "--fractions",
        type=lambda value: _parse_tuple(value, float),
        default=(0.50, 0.20, 0.10, 0.05, 0.01, 0.001),
    )
    parser.add_argument(
        "--seeds",
        type=lambda value: _parse_tuple(value, int),
        default=(41, 42, 43, 44, 45),
    )
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--arrivals", type=int, default=1)
    parser.add_argument("--drain-ticks", type=int, default=250)
    parser.add_argument("--policy-seed", type=int, default=1_337)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r2_capability_rarity_sweep(R2CapabilityRarityConfig(
        worker_count=args.workers,
        capability_fractions=args.fractions,
        trace_seeds=args.seeds,
        ticks=args.ticks,
        arrivals_per_tick=args.arrivals,
        drain_ticks=args.drain_ticks,
        policy_seed=args.policy_seed,
    ))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
