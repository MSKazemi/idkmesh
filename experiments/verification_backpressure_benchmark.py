#!/usr/bin/env python3
"""Temporal benchmark for Risk-Weighted Verification Backpressure (RWVB).

This synthetic experiment advances issue #14 from a one-window controller to a
multi-window queue benchmark. It compares four fixed-generation verifier
schedulers with RWVB plus adaptive generation backpressure.

The benchmark is deliberately conservative:

* seeded defects are synthetic hidden truth, not real repository defects;
* a verifier false negative is recorded as evidence-model failure, not merge;
* no candidate is granted integration authority;
* fixed policies at the same fan-out consume the same deterministic workload
  trace, while adaptive RWVB consumes a prefix of that trace as it throttles.

Run:

    python experiments/verification_backpressure_benchmark.py --self-test
    python experiments/verification_backpressure_benchmark.py --benchmark \
      --seeds 20 --steps 100 --fanouts 2,4,8,12 --capacity 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence

try:
    from .verification_backpressure import (
        EPSILON,
        Candidate,
        ControllerConfig,
        next_generation_fanout,
        schedule_verification,
        total_verification_debt,
    )
except ImportError:  # Direct script execution from repository root.
    from verification_backpressure import (  # type: ignore
        EPSILON,
        Candidate,
        ControllerConfig,
        next_generation_fanout,
        schedule_verification,
        total_verification_debt,
    )


POLICIES = (
    "fifo",
    "highest-risk-first",
    "cheapest-first",
    "rwvb-fixed",
    "rwvb-adaptive",
)
GENERATOR_VERSION = "seeded-risk-stream-v0.1"
BENCHMARK_VERSION = "verification-backpressure-temporal-v0.1"


@dataclass(frozen=True)
class SyntheticCandidate:
    candidate: Candidate
    defective: bool
    detected_if_verified: bool
    defect_exposure: float

    def aged(self) -> "SyntheticCandidate":
        return replace(
            self,
            candidate=replace(
                self.candidate,
                age_steps=self.candidate.age_steps + 1,
            ),
        )


def _rng(seed: int, index: int) -> random.Random:
    return random.Random((seed + 1) * 1_000_003 + index * 97_409)


def make_synthetic_candidate(seed: int, index: int) -> SyntheticCandidate:
    """Create one deterministic candidate with hidden synthetic defect truth."""

    rng = _rng(seed, index)
    risk = round(rng.uniform(0.05, 1.0), 6)
    uncertainty = round(rng.uniform(0.15, 1.0), 6)
    impact = rng.choice((0.10, 0.25, 0.50, 1.00, 1.50, 2.00))
    verification_cost = rng.choice((0.50, 1.00, 1.50, 2.00, 3.00))
    evidence_diversity = round(rng.uniform(0.05, 1.0), 6)

    defect_probability = min(0.55, 0.08 + 0.30 * risk + 0.08 * uncertainty)
    defective = rng.random() < defect_probability

    detection_probability = min(
        0.99,
        0.76 + 0.18 * evidence_diversity + 0.05 * risk,
    )
    detected_if_verified = defective and rng.random() < detection_probability

    candidate = Candidate(
        id=f"candidate-{index:06d}",
        risk=risk,
        uncertainty=uncertainty,
        impact=impact,
        estimated_verification_cost=verification_cost,
        evidence_diversity=evidence_diversity,
        age_steps=0,
    )
    return SyntheticCandidate(
        candidate=candidate,
        defective=defective,
        detected_if_verified=detected_if_verified,
        defect_exposure=(risk * (1.0 + impact)) if defective else 0.0,
    )


def _stream_record(item: SyntheticCandidate) -> str:
    c = item.candidate
    return "|".join(
        (
            c.id,
            f"{c.risk:.6f}",
            f"{c.uncertainty:.6f}",
            f"{c.impact:.6f}",
            f"{c.estimated_verification_cost:.6f}",
            f"{c.evidence_diversity:.6f}",
            "1" if item.defective else "0",
            "1" if item.detected_if_verified else "0",
        )
    )


def _greedy_capacity_select(
    ordered: Iterable[SyntheticCandidate],
    capacity: float,
) -> list[SyntheticCandidate]:
    selected: list[SyntheticCandidate] = []
    used = 0.0
    for item in ordered:
        cost = item.candidate.estimated_verification_cost
        if used + cost <= capacity + EPSILON:
            selected.append(item)
            used += cost
    return selected


def schedule_policy(
    queue: Sequence[SyntheticCandidate],
    capacity: float,
    policy: str,
    config: ControllerConfig,
) -> list[SyntheticCandidate]:
    """Select one verification window under a named scheduling policy."""

    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if capacity < 0.0:
        raise ValueError("capacity must be >= 0")

    if policy in {"rwvb-fixed", "rwvb-adaptive"}:
        selected = schedule_verification(
            [item.candidate for item in queue],
            capacity=capacity,
            config=config,
        )
        selected_ids = {candidate.id for candidate in selected}
        return [item for item in queue if item.candidate.id in selected_ids]

    if policy == "fifo":
        ordered = sorted(
            queue,
            key=lambda item: (-item.candidate.age_steps, item.candidate.id),
        )
    elif policy == "highest-risk-first":
        ordered = sorted(
            queue,
            key=lambda item: (
                -(item.candidate.risk * (1.0 + item.candidate.impact)),
                -item.candidate.age_steps,
                item.candidate.id,
            ),
        )
    else:
        ordered = sorted(
            queue,
            key=lambda item: (
                item.candidate.estimated_verification_cost,
                -item.candidate.age_steps,
                item.candidate.id,
            ),
        )
    return _greedy_capacity_select(ordered, capacity)


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def simulate(
    *,
    policy: str,
    seed: int,
    steps: int,
    initial_fanout: int,
    verification_capacity_per_window: float,
    controller_config: ControllerConfig | None = None,
) -> dict[str, object]:
    """Run one deterministic temporal verification-queue experiment."""

    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if seed < 0:
        raise ValueError("seed must be >= 0")
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if verification_capacity_per_window <= 0.0:
        raise ValueError("verification capacity must be > 0")

    config = controller_config or ControllerConfig()
    config.validate()
    if not config.min_fanout <= initial_fanout <= config.max_fanout:
        raise ValueError("initial_fanout must fit controller fanout bounds")

    queue: list[SyntheticCandidate] = []
    next_index = 0
    fanout = initial_fanout
    generated = 0
    verified = 0
    detected_defects = 0
    verifier_false_negatives = 0
    verification_cost_consumed = 0.0
    wait_steps: list[float] = []
    queue_lengths: list[float] = []
    debt_history: list[float] = []
    pending_exposure_history: list[float] = []
    fanout_history: list[int] = []
    stream_hasher = hashlib.sha256()

    for _step in range(steps):
        queue = [item.aged() for item in queue]

        for _ in range(fanout):
            item = make_synthetic_candidate(seed, next_index)
            next_index += 1
            generated += 1
            stream_hasher.update((_stream_record(item) + "\n").encode("utf-8"))
            queue.append(item)

        selected = schedule_policy(
            queue,
            capacity=verification_capacity_per_window,
            policy=policy,
            config=config,
        )
        selected_ids = {item.candidate.id for item in selected}

        for item in selected:
            verified += 1
            wait_steps.append(float(item.candidate.age_steps))
            verification_cost_consumed += item.candidate.estimated_verification_cost
            if item.defective:
                if item.detected_if_verified:
                    detected_defects += 1
                else:
                    verifier_false_negatives += 1

        queue = [item for item in queue if item.candidate.id not in selected_ids]
        debt = total_verification_debt(
            [item.candidate for item in queue],
            config,
        )
        pending_exposure = sum(item.defect_exposure for item in queue)
        queue_lengths.append(float(len(queue)))
        debt_history.append(debt)
        pending_exposure_history.append(pending_exposure)

        if policy == "rwvb-adaptive":
            fanout = next_generation_fanout(
                current_fanout=fanout,
                debt=debt,
                verification_capacity_per_window=verification_capacity_per_window,
                config=config,
            )
        else:
            fanout = initial_fanout
        fanout_history.append(fanout)

    pending_defects = sum(1 for item in queue if item.defective)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "candidate_generator_version": GENERATOR_VERSION,
        "policy": policy,
        "seed": seed,
        "steps": steps,
        "initial_fanout": initial_fanout,
        "verification_capacity_per_window": verification_capacity_per_window,
        "generated_candidates": generated,
        "generated_stream_sha256": stream_hasher.hexdigest(),
        "verified_candidates": verified,
        "verified_throughput_per_window": round(verified / steps, 6),
        "pending_candidates": len(queue),
        "detected_seeded_defects": detected_defects,
        "verifier_false_negatives": verifier_false_negatives,
        "pending_seeded_defects": pending_defects,
        "pending_defect_exposure": round(pending_exposure_history[-1], 6),
        "peak_queue_length": int(max(queue_lengths, default=0.0)),
        "mean_queue_length": round(_mean(queue_lengths), 6),
        "peak_verification_debt": round(max(debt_history, default=0.0), 6),
        "final_verification_debt": round(debt_history[-1] if debt_history else 0.0, 6),
        "mean_wait_steps": round(_mean(wait_steps), 6),
        "max_wait_steps_observed": int(max(wait_steps, default=0.0)),
        "verification_cost_consumed": round(verification_cost_consumed, 6),
        "final_fanout": fanout,
        "min_fanout": min(fanout_history, default=initial_fanout),
        "max_fanout": max(fanout_history, default=initial_fanout),
        "integration_authority": "none",
    }


SUMMARY_METRICS = (
    "generated_candidates",
    "verified_candidates",
    "verified_throughput_per_window",
    "pending_candidates",
    "detected_seeded_defects",
    "verifier_false_negatives",
    "pending_seeded_defects",
    "pending_defect_exposure",
    "peak_queue_length",
    "mean_queue_length",
    "peak_verification_debt",
    "final_verification_debt",
    "mean_wait_steps",
    "max_wait_steps_observed",
    "verification_cost_consumed",
    "final_fanout",
)


def _aggregate(group: Sequence[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {"runs": len(group)}
    for metric in SUMMARY_METRICS:
        values = [float(run[metric]) for run in group]
        summary[metric] = {
            "mean": round(statistics.fmean(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }
    return summary


def benchmark(
    *,
    seeds: int,
    steps: int,
    fanouts: Sequence[int],
    verification_capacity_per_window: float,
    include_runs: bool = True,
) -> dict[str, object]:
    """Run the same seeded experiment matrix across all policies."""

    if seeds < 1:
        raise ValueError("seeds must be >= 1")
    if not fanouts:
        raise ValueError("at least one fanout is required")

    config = ControllerConfig()
    config.validate()
    normalized_fanouts = sorted(set(int(value) for value in fanouts))
    for fanout in normalized_fanouts:
        if not config.min_fanout <= fanout <= config.max_fanout:
            raise ValueError(
                f"fanout {fanout} must be within "
                f"[{config.min_fanout}, {config.max_fanout}]"
            )

    runs: list[dict[str, object]] = []
    for fanout in normalized_fanouts:
        for seed in range(seeds):
            for policy in POLICIES:
                runs.append(
                    simulate(
                        policy=policy,
                        seed=seed,
                        steps=steps,
                        initial_fanout=fanout,
                        verification_capacity_per_window=verification_capacity_per_window,
                        controller_config=config,
                    )
                )

    summaries: list[dict[str, object]] = []
    for fanout in normalized_fanouts:
        for policy in POLICIES:
            group = [
                run
                for run in runs
                if run["initial_fanout"] == fanout and run["policy"] == policy
            ]
            summaries.append(
                {
                    "initial_fanout": fanout,
                    "policy": policy,
                    **_aggregate(group),
                }
            )

    payload: dict[str, object] = {
        "benchmark_version": BENCHMARK_VERSION,
        "candidate_generator_version": GENERATOR_VERSION,
        "experiment": "issue-14-verification-scaling",
        "seeds": list(range(seeds)),
        "steps": steps,
        "fanouts": normalized_fanouts,
        "verification_capacity_per_window": verification_capacity_per_window,
        "policies": list(POLICIES),
        "controller_config": asdict(config),
        "fairness": (
            "At equal fixed fanout and seed, fixed policies receive the same "
            "candidate stream. Adaptive RWVB receives a deterministic prefix "
            "because backpressure changes how many candidates are generated."
        ),
        "safety": (
            "Synthetic verifier outcomes provide evidence metrics only. "
            "No merge, acceptance, or integration authority is modeled."
        ),
        "summaries": summaries,
    }
    if include_runs:
        payload["runs"] = runs
    return payload


def _parse_fanouts(raw: str) -> list[int]:
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("fanouts cannot be empty")
    try:
        return [int(value) for value in values]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("fanouts must be comma-separated integers") from exc


def self_test() -> None:
    config = ControllerConfig()
    assert make_synthetic_candidate(seed=3, index=11) == make_synthetic_candidate(seed=3, index=11)

    sample = [make_synthetic_candidate(5, index) for index in range(25)]
    for policy in POLICIES:
        selected = schedule_policy(sample, 5.0, policy, config)
        assert sum(item.candidate.estimated_verification_cost for item in selected) <= 5.0 + EPSILON

    run_a = simulate(
        policy="rwvb-adaptive",
        seed=7,
        steps=40,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    run_b = simulate(
        policy="rwvb-adaptive",
        seed=7,
        steps=40,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    assert run_a == run_b

    fixed = simulate(
        policy="rwvb-fixed",
        seed=7,
        steps=80,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    adaptive = simulate(
        policy="rwvb-adaptive",
        seed=7,
        steps=80,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    assert adaptive["pending_candidates"] < fixed["pending_candidates"]
    assert adaptive["final_verification_debt"] < fixed["final_verification_debt"]
    assert adaptive["peak_queue_length"] < fixed["peak_queue_length"]
    assert config.min_fanout <= int(adaptive["final_fanout"]) <= config.max_fanout

    fifo = simulate(
        policy="fifo",
        seed=2,
        steps=20,
        initial_fanout=4,
        verification_capacity_per_window=8.0,
    )
    risk = simulate(
        policy="highest-risk-first",
        seed=2,
        steps=20,
        initial_fanout=4,
        verification_capacity_per_window=8.0,
    )
    assert fifo["generated_stream_sha256"] == risk["generated_stream_sha256"]
    assert fifo["generated_candidates"] == risk["generated_candidates"]
    assert fifo["integration_authority"] == "none"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="Run deterministic regression assertions.")
    mode.add_argument("--benchmark", action="store_true", help="Run the seeded policy/fanout benchmark.")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument(
        "--fanouts",
        type=_parse_fanouts,
        default=[2, 4, 8, 12],
        help="Comma-separated initial fanouts (default: 2,4,8,12).",
    )
    parser.add_argument("--capacity", type=float, default=8.0)
    parser.add_argument("--summary-only", action="store_true", help="Omit per-run records from benchmark output.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path; otherwise print to stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        print("OK: temporal verification backpressure benchmark self-test passed")
        return 0

    payload = benchmark(
        seeds=args.seeds,
        steps=args.steps,
        fanouts=args.fanouts,
        verification_capacity_per_window=args.capacity,
        include_runs=not args.summary_only,
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
