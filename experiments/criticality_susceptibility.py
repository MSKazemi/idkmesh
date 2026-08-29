#!/usr/bin/env python3
"""Matched-seed susceptibility probes for a synthetic coordination queue.

The model is deliberately small: generator slots create tasks, bounded workers
turn tasks into candidates, and bounded verifiers inspect those candidates.
Control, pulse, and sustained-stress variants consume the same latent random
draws, so differences are caused by the load schedule rather than by unrelated
workloads.

This is an engineering queue experiment, not a thermodynamic model and not an
acceptance or integration mechanism.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


EXPERIMENT_VERSION = "coordination-criticality-v0.1"
MODES = ("control", "pulse", "stress")
RESPONSE_METRICS = (
    "mean_total_backlog",
    "peak_total_backlog",
    "backlog_variance",
    "mean_latency_ticks",
    "verified_throughput_per_tick",
    "escaped_failures",
)


@dataclass(frozen=True)
class QueueConfig:
    steps: int = 240
    probe_start: int = 80
    probe_steps: int = 40
    generator_slots: int = 20
    worker_capacity: int = 12
    verifier_capacity: int = 8
    defect_probability: float = 0.18
    detection_probability: float = 0.90
    perturbation_fraction: float = 0.05
    recovery_stability_steps: int = 5

    @property
    def probe_end(self) -> int:
        return self.probe_start + self.probe_steps

    def validate(self) -> None:
        if self.steps <= self.probe_end:
            raise ValueError("steps must leave time for post-probe recovery")
        if self.probe_start < 1 or self.probe_steps < 1:
            raise ValueError("probe_start and probe_steps must be >= 1")
        if self.generator_slots < 1:
            raise ValueError("generator_slots must be >= 1")
        if self.worker_capacity < 1 or self.verifier_capacity < 1:
            raise ValueError("worker and verifier capacity must be >= 1")
        for name, value in (
            ("defect_probability", self.defect_probability),
            ("detection_probability", self.detection_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        if not 0.0 < self.perturbation_fraction <= 1.0:
            raise ValueError("perturbation_fraction must be within (0, 1]")
        if self.recovery_stability_steps < 1:
            raise ValueError("recovery_stability_steps must be >= 1")


@dataclass(frozen=True)
class Task:
    task_id: str
    created_tick: int
    defective: bool
    detected_if_verified: bool


def _latent_draws(
    seed: int,
    config: QueueConfig,
) -> tuple[list[list[tuple[float, float, float]]], str]:
    """Return a fixed draw table shared by every variant of one seed."""

    rng = random.Random(seed)
    rows: list[list[tuple[float, float, float]]] = []
    digest = hashlib.sha256()
    for _tick in range(config.steps):
        row: list[tuple[float, float, float]] = []
        for _slot in range(config.generator_slots):
            draws = (rng.random(), rng.random(), rng.random())
            row.append(draws)
            digest.update(struct.pack("!ddd", *draws))
        rows.append(row)
    return rows, digest.hexdigest()


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return float(ordered[index])


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _load_for_tick(
    *,
    base_load: float,
    tick: int,
    mode: str,
    config: QueueConfig,
) -> float:
    perturbed = min(1.0, base_load * (1.0 + config.perturbation_fraction))
    if mode == "pulse" and config.probe_start <= tick < config.probe_end:
        return perturbed
    if mode == "stress" and tick >= config.probe_start:
        return perturbed
    return base_load


def simulate(
    *,
    seed: int,
    base_load: float,
    mode: str,
    config: QueueConfig | None = None,
) -> dict[str, object]:
    """Run one deterministic control, pulse, or sustained-stress trial."""

    cfg = config or QueueConfig()
    cfg.validate()
    if seed < 0:
        raise ValueError("seed must be >= 0")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if not 0.0 < base_load < 1.0:
        raise ValueError("base_load must be within (0, 1)")
    if base_load * (1.0 + cfg.perturbation_fraction) > 1.0:
        raise ValueError("perturbed load must not exceed 1")

    latent, latent_digest = _latent_draws(seed, cfg)
    worker_queue: list[Task] = []
    verifier_queue: list[Task] = []
    backlog_history: list[int] = []
    worker_backlog_history: list[int] = []
    verifier_backlog_history: list[int] = []
    latency_history: list[float] = []
    arrivals_by_phase = {"pre_probe": 0, "probe": 0, "post_probe": 0}
    verified = 0
    escaped_failures = 0
    detected_failures = 0

    for tick, row in enumerate(latent):
        load = _load_for_tick(
            base_load=base_load,
            tick=tick,
            mode=mode,
            config=cfg,
        )
        if tick < cfg.probe_start:
            phase = "pre_probe"
        elif tick < cfg.probe_end:
            phase = "probe"
        else:
            phase = "post_probe"

        for slot, (arrival_draw, defect_draw, detection_draw) in enumerate(row):
            if arrival_draw >= load:
                continue
            arrivals_by_phase[phase] += 1
            worker_queue.append(
                Task(
                    task_id=f"s{seed}-t{tick}-g{slot}",
                    created_tick=tick,
                    defective=defect_draw < cfg.defect_probability,
                    detected_if_verified=detection_draw < cfg.detection_probability,
                )
            )

        completed_work = worker_queue[: cfg.worker_capacity]
        del worker_queue[: cfg.worker_capacity]
        verifier_queue.extend(completed_work)

        completed_verification = verifier_queue[: cfg.verifier_capacity]
        del verifier_queue[: cfg.verifier_capacity]
        for task in completed_verification:
            verified += 1
            if tick >= cfg.probe_start:
                latency_history.append(float(tick - task.created_tick + 1))
            if task.defective:
                if task.detected_if_verified:
                    detected_failures += 1
                else:
                    escaped_failures += 1

        worker_backlog_history.append(len(worker_queue))
        verifier_backlog_history.append(len(verifier_queue))
        backlog_history.append(len(worker_queue) + len(verifier_queue))

    evaluation_backlog = backlog_history[cfg.probe_start :]
    evaluation_latencies = latency_history
    post_probe_backlog = backlog_history[cfg.probe_end :]
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "seed": seed,
        "mode": mode,
        "base_load": base_load,
        "perturbed_load": round(
            base_load * (1.0 + cfg.perturbation_fraction), 10
        ),
        "latent_workload_sha256": latent_digest,
        "arrivals_by_phase": arrivals_by_phase,
        "generated_tasks": sum(arrivals_by_phase.values()),
        "verified_candidates": verified,
        "verified_throughput_per_tick": round(verified / cfg.steps, 8),
        "detected_failures": detected_failures,
        "escaped_failures": escaped_failures,
        "escaped_failure_rate": round(escaped_failures / max(1, verified), 8),
        "final_total_backlog": backlog_history[-1],
        "mean_total_backlog": round(_mean(evaluation_backlog), 8),
        "peak_total_backlog": max(evaluation_backlog, default=0),
        "backlog_variance": round(
            statistics.pvariance(evaluation_backlog)
            if len(evaluation_backlog) > 1
            else 0.0,
            8,
        ),
        "pre_probe_mean_total_backlog": round(
            _mean(backlog_history[: cfg.probe_start]), 8
        ),
        "post_probe_backlog_growth": (
            post_probe_backlog[-1] - post_probe_backlog[0]
            if post_probe_backlog
            else 0
        ),
        "mean_latency_ticks": round(_mean(evaluation_latencies), 8),
        "p95_latency_ticks": round(_percentile(evaluation_latencies, 0.95), 8),
        "backlog_history": backlog_history,
        "worker_backlog_history": worker_backlog_history,
        "verifier_backlog_history": verifier_backlog_history,
        "integration_authority": "none",
    }


def _recovery_steps(
    control: dict[str, object],
    pulse: dict[str, object],
    config: QueueConfig,
) -> int | None:
    control_history = control["backlog_history"]
    pulse_history = pulse["backlog_history"]
    assert isinstance(control_history, list)
    assert isinstance(pulse_history, list)
    last_start = config.steps - config.recovery_stability_steps + 1
    for tick in range(config.probe_end, last_start):
        if all(
            pulse_history[index] <= control_history[index]
            for index in range(tick, tick + config.recovery_stability_steps)
        ):
            return tick - config.probe_end
    return None


def paired_trial(
    *,
    seed: int,
    base_load: float,
    config: QueueConfig | None = None,
) -> dict[str, object]:
    """Run matched control/pulse/stress variants and calculate responses."""

    cfg = config or QueueConfig()
    control = simulate(seed=seed, base_load=base_load, mode="control", config=cfg)
    pulse = simulate(seed=seed, base_load=base_load, mode="pulse", config=cfg)
    stress = simulate(seed=seed, base_load=base_load, mode="stress", config=cfg)
    digests = {
        control["latent_workload_sha256"],
        pulse["latent_workload_sha256"],
        stress["latent_workload_sha256"],
    }
    if len(digests) != 1:
        raise AssertionError("matched variants must share one latent workload")

    delta_load = float(pulse["perturbed_load"]) - base_load
    responses = {
        metric: round(
            (float(pulse[metric]) - float(control[metric])) / delta_load,
            8,
        )
        for metric in RESPONSE_METRICS
    }
    recovery = _recovery_steps(control, pulse, cfg)
    stress_overloaded = (
        int(stress["final_total_backlog"]) >= cfg.verifier_capacity
        and int(stress["post_probe_backlog_growth"]) > 0
    )
    return {
        "seed": seed,
        "base_load": base_load,
        "delta_load": round(delta_load, 10),
        "control": control,
        "pulse": pulse,
        "stress": stress,
        "susceptibility": responses,
        "recovery_steps": recovery,
        "recovery_censored": recovery is None,
        "future_stress_overloaded": stress_overloaded,
    }


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0, "mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}
    mean = statistics.fmean(values)
    standard_error = (
        statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    )
    margin = 1.96 * standard_error
    return {
        "n": len(values),
        "mean": round(mean, 8),
        "ci95_low": round(mean - margin, 8),
        "ci95_high": round(mean + margin, 8),
    }


def _first_alert(cells: Sequence[dict[str, object]], signal: str) -> int | None:
    for index, cell in enumerate(cells):
        signals = cell["signals"]
        assert isinstance(signals, dict)
        if bool(signals[signal]):
            return index
    return None


def benchmark(
    *,
    seeds: int,
    loads: Sequence[float],
    config: QueueConfig | None = None,
    include_trials: bool = True,
) -> dict[str, object]:
    """Sweep load toward overload and compare three early-warning signals."""

    cfg = config or QueueConfig()
    cfg.validate()
    if seeds < 2:
        raise ValueError("seeds must be >= 2 for uncertainty estimates")
    normalized_loads = sorted(set(float(load) for load in loads))
    if not normalized_loads:
        raise ValueError("at least one load is required")

    cells: list[dict[str, object]] = []
    for base_load in normalized_loads:
        trials = [
            paired_trial(seed=seed, base_load=base_load, config=cfg)
            for seed in range(seeds)
        ]
        response_summary = {
            metric: _summary(
                [float(trial["susceptibility"][metric]) for trial in trials]  # type: ignore[index]
            )
            for metric in RESPONSE_METRICS
        }
        baseline_backlog = _summary(
            [float(trial["control"]["mean_total_backlog"]) for trial in trials]  # type: ignore[index]
        )
        recovery_values = [
            float(trial["recovery_steps"])
            for trial in trials
            if trial["recovery_steps"] is not None
        ]
        overload_rate = _mean(
            [1.0 if trial["future_stress_overloaded"] else 0.0 for trial in trials]
        )
        offered_load_ratio = (
            base_load * cfg.generator_slots / cfg.verifier_capacity
        )
        backlog_response = response_summary["mean_total_backlog"]
        response_elasticity_low = (
            float(backlog_response["ci95_low"])
            * base_load
            / max(1.0, float(baseline_backlog["mean"]))
        )
        cell: dict[str, object] = {
            "base_load": base_load,
            "perturbed_load": round(
                base_load * (1.0 + cfg.perturbation_fraction), 10
            ),
            "offered_load_ratio": round(offered_load_ratio, 8),
            "baseline_mean_backlog": baseline_backlog,
            "susceptibility": response_summary,
            "recovery": {
                **_summary(recovery_values),
                "observed": len(recovery_values),
                "censored": seeds - len(recovery_values),
            },
            "future_stress_overload_rate": round(overload_rate, 8),
            "signals": {
                "utilization_threshold": offered_load_ratio >= 0.90,
                "absolute_backlog_threshold": (
                    float(baseline_backlog["mean"]) >= cfg.verifier_capacity
                ),
                "susceptibility_superlinear": response_elasticity_low > 1.0,
            },
            "susceptibility_backlog_elasticity_ci95_low": round(
                response_elasticity_low, 8
            ),
        }
        if include_trials:
            cell["trials"] = trials
        cells.append(cell)

    overload_index = next(
        (
            index
            for index, cell in enumerate(cells)
            if float(cell["future_stress_overload_rate"]) >= 0.5
        ),
        None,
    )
    comparisons: dict[str, object] = {
        "ground_truth": (
            "First load cell where at least half of sustained +5% matched "
            "runs end with verifier-capacity-sized backlog and positive "
            "post-probe growth."
        ),
        "overload_onset_load": (
            cells[overload_index]["base_load"] if overload_index is not None else None
        ),
        "signals": {},
    }
    signal_rows = comparisons["signals"]
    assert isinstance(signal_rows, dict)
    for signal in (
        "utilization_threshold",
        "absolute_backlog_threshold",
        "susceptibility_superlinear",
    ):
        first_index = _first_alert(cells, signal)
        signal_rows[signal] = {
            "first_alert_load": (
                cells[first_index]["base_load"] if first_index is not None else None
            ),
            "lead_load": (
                round(
                    float(cells[overload_index]["base_load"])
                    - float(cells[first_index]["base_load"]),
                    8,
                )
                if first_index is not None and overload_index is not None
                else None
            ),
            "false_alarm_cells_before_onset": (
                sum(
                    1
                    for cell in cells[:overload_index]
                    if bool(cell["signals"][signal])  # type: ignore[index]
                )
                if overload_index is not None
                else None
            ),
        }

    payload = {
        "experiment_version": EXPERIMENT_VERSION,
        "experiment": "issue-49-coordination-criticality",
        "interpretation_boundary": (
            "Finite-difference engineering response in a synthetic queue; "
            "not evidence of equilibrium or a thermodynamic phase transition."
        ),
        "config": asdict(cfg),
        "seeds": list(range(seeds)),
        "loads": normalized_loads,
        "uncertainty": "Two-sided normal-approximation 95% interval over matched-seed trial responses.",
        "matching": (
            "Control, +5% pulse, and sustained +5% stress use identical "
            "per-seed latent arrival, defect, and detection draws."
        ),
        "signal_definitions": {
            "utilization_threshold": "base offered load / verifier capacity >= 0.90",
            "absolute_backlog_threshold": "baseline mean backlog >= one verifier window",
            "susceptibility_superlinear": (
                "lower 95% CI of backlog response elasticity > 1, with a "
                "one-task noise floor"
            ),
        },
        "cells": cells,
        "comparison": comparisons,
        "integration_authority": "none",
    }
    return payload


def _parse_loads(raw: str) -> list[float]:
    try:
        values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("loads must be comma-separated numbers") from exc
    if not values:
        raise argparse.ArgumentTypeError("loads cannot be empty")
    return values


def self_test() -> None:
    cfg = QueueConfig(steps=80, probe_start=20, probe_steps=20)
    first = paired_trial(seed=7, base_load=0.38, config=cfg)
    second = paired_trial(seed=7, base_load=0.38, config=cfg)
    assert first == second
    assert first["control"]["latent_workload_sha256"] == first["pulse"]["latent_workload_sha256"]  # type: ignore[index]
    assert first["control"]["arrivals_by_phase"]["pre_probe"] == first["pulse"]["arrivals_by_phase"]["pre_probe"]  # type: ignore[index]
    assert first["control"]["arrivals_by_phase"]["post_probe"] == first["pulse"]["arrivals_by_phase"]["post_probe"]  # type: ignore[index]
    assert first["control"]["integration_authority"] == "none"  # type: ignore[index]
    result = benchmark(seeds=3, loads=[0.34, 0.40], config=cfg, include_trials=False)
    assert len(result["cells"]) == 2
    assert result["integration_authority"] == "none"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--benchmark", action="store_true")
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument(
        "--loads",
        type=_parse_loads,
        default=[0.30, 0.34, 0.36, 0.38, 0.39, 0.40],
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        print("OK: coordination criticality susceptibility self-test passed")
        return 0
    result = benchmark(
        seeds=args.seeds,
        loads=args.loads,
        include_trials=not args.summary_only,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
