#!/usr/bin/env python3
"""Matched synthetic matrix for the seven verification modes in issue #14.

The experiment separates candidate generation, hidden defect truth, evidence
channels, scheduling, and integration authority. It is synthetic mechanism
evidence: an ``accepted`` outcome is a simulator measurement and never grants
repository authority.

Run from the repository root:

    python experiments/verification_scaling_matrix.py --self-test
    python experiments/verification_scaling_matrix.py --benchmark \
      --seeds 20 --steps 100 --fanouts 2,4,8,12 --capacity 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

try:
    from .verification_backpressure import (
        Candidate as DebtCandidate,
        ControllerConfig,
        next_generation_fanout,
        schedule_verification,
        total_verification_debt,
    )
except ImportError:  # Direct script execution from the repository root.
    from verification_backpressure import (  # type: ignore
        Candidate as DebtCandidate,
        ControllerConfig,
        next_generation_fanout,
        schedule_verification,
        total_verification_debt,
    )


BENCHMARK_VERSION = "verification-scaling-matrix-v0.1"
CANDIDATE_GENERATOR_VERSION = "matched-hidden-defect-stream-v0.1"
MODES = (
    "no-independent-verification",
    "one-reviewer",
    "fixed-three-reviewer-quorum",
    "independent-tests",
    "tests-plus-adversarial-reviewer",
    "risk-adaptive",
    "risk-adaptive-backpressure",
)
DEFECT_CLASSES = ("correctness", "regression", "security")


@dataclass(frozen=True)
class ScalingCandidate:
    id: str
    index: int
    risk: float
    uncertainty: float
    impact: float
    defective: bool
    defect_class: str | None
    age_steps: int = 0

    def aged(self) -> "ScalingCandidate":
        return replace(self, age_steps=self.age_steps + 1)


def _unit_interval(seed: int, index: int, label: str) -> float:
    digest = hashlib.sha256(f"{seed}|{index}|{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def make_candidate(seed: int, index: int) -> ScalingCandidate:
    """Return one deterministic candidate and its hidden seeded-defect truth."""

    if seed < 0 or index < 0:
        raise ValueError("seed and index must be >= 0")
    risk = round(0.05 + 0.90 * _unit_interval(seed, index, "risk"), 6)
    uncertainty = round(0.10 + 0.85 * _unit_interval(seed, index, "uncertainty"), 6)
    impact = (0.25, 0.50, 1.00, 1.50, 2.00)[
        min(4, int(_unit_interval(seed, index, "impact") * 5))
    ]
    defect_probability = min(0.70, 0.04 + 0.58 * risk + 0.08 * uncertainty)
    defective = _unit_interval(seed, index, "defect") < defect_probability
    defect_class = None
    if defective:
        defect_class = DEFECT_CLASSES[
            min(2, int(_unit_interval(seed, index, "defect-class") * 3))
        ]
    return ScalingCandidate(
        id=f"candidate-{index:06d}",
        index=index,
        risk=risk,
        uncertainty=uncertainty,
        impact=impact,
        defective=defective,
        defect_class=defect_class,
    )


def _channel_rejects(candidate: ScalingCandidate, seed: int, channel: str) -> bool:
    """Return a deterministic evidence-channel vote to reject a candidate."""

    draw = _unit_interval(seed, candidate.index, channel)
    if channel == "independent-test":
        sensitivity = {
            "correctness": 0.86,
            "regression": 0.80,
            "security": 0.62,
        }
        return (
            draw < sensitivity[candidate.defect_class]
            if candidate.defective
            else draw < 0.01
        )
    if channel == "adversarial-reviewer":
        sensitivity = {
            "correctness": 0.90,
            "regression": 0.91,
            "security": 0.96,
        }
        return (
            draw < sensitivity[candidate.defect_class]
            if candidate.defective
            else draw < 0.04
        )
    if channel.startswith("reviewer-"):
        shared_error = _unit_interval(seed, candidate.index, "reviewer-shared-error") < 0.25
        reviewer_error = shared_error or draw < 0.18
        return candidate.defective != reviewer_error
    raise ValueError(f"unknown evidence channel: {channel}")


def evidence_bundle(mode: str, candidate: ScalingCandidate) -> tuple[str, ...]:
    if mode == "no-independent-verification":
        return ()
    if mode == "one-reviewer":
        return ("reviewer-0",)
    if mode == "fixed-three-reviewer-quorum":
        return ("reviewer-0", "reviewer-1", "reviewer-2")
    if mode == "independent-tests":
        return ("independent-test",)
    if mode == "tests-plus-adversarial-reviewer":
        return ("independent-test", "adversarial-reviewer")
    if mode in {"risk-adaptive", "risk-adaptive-backpressure"}:
        if candidate.risk >= 0.70:
            return ("independent-test", "adversarial-reviewer")
        if candidate.risk >= 0.35:
            return ("independent-test", "reviewer-0")
        return ("independent-test",)
    raise ValueError(f"unknown verification mode: {mode}")


def bundle_cost(bundle: Sequence[str]) -> float:
    return float(
        sum(2 if channel == "adversarial-reviewer" else 1 for channel in bundle)
    )


def _human_attention_units(bundle: Sequence[str]) -> float:
    return float(
        sum(
            2 if channel == "adversarial-reviewer" else 1
            for channel in bundle
            if channel.startswith("reviewer-") or channel == "adversarial-reviewer"
        )
    )


def _accepted(mode: str, candidate: ScalingCandidate, seed: int) -> bool:
    bundle = evidence_bundle(mode, candidate)
    if not bundle:
        return True
    rejections = sum(_channel_rejects(candidate, seed, channel) for channel in bundle)
    if mode == "fixed-three-reviewer-quorum":
        return rejections < 2
    return rejections == 0


def _debt_candidate(candidate: ScalingCandidate, mode: str) -> DebtCandidate:
    return DebtCandidate(
        id=candidate.id,
        risk=candidate.risk,
        uncertainty=candidate.uncertainty,
        impact=candidate.impact,
        estimated_verification_cost=bundle_cost(evidence_bundle(mode, candidate)),
        evidence_diversity=0.75 if candidate.risk >= 0.70 else 0.45,
        age_steps=candidate.age_steps,
    )


def _select_for_window(
    queue: Sequence[ScalingCandidate],
    mode: str,
    capacity: float,
) -> list[ScalingCandidate]:
    if mode == "no-independent-verification":
        return list(queue)
    if mode in {"risk-adaptive", "risk-adaptive-backpressure"}:
        selected_ids = {
            candidate.id
            for candidate in schedule_verification(
                [_debt_candidate(candidate, mode) for candidate in queue],
                capacity,
                ControllerConfig(),
            )
        }
        return sorted(
            (candidate for candidate in queue if candidate.id in selected_ids),
            key=lambda candidate: candidate.id,
        )

    ordered = sorted(queue, key=lambda item: (-item.age_steps, item.id))

    selected: list[ScalingCandidate] = []
    used = 0.0
    for item in ordered:
        cost = bundle_cost(evidence_bundle(mode, item))
        if used + cost <= capacity + 1e-9:
            selected.append(item)
            used += cost
    return selected


def _stream_record(candidate: ScalingCandidate) -> str:
    return "|".join(
        (
            candidate.id,
            f"{candidate.risk:.6f}",
            f"{candidate.uncertainty:.6f}",
            f"{candidate.impact:.2f}",
            "1" if candidate.defective else "0",
            candidate.defect_class or "none",
        )
    )


def simulate(
    *,
    mode: str,
    seed: int,
    steps: int,
    initial_fanout: int,
    verification_capacity_per_window: float,
) -> dict[str, object]:
    """Run one matched candidate-generation and verification simulation."""

    if mode not in MODES:
        raise ValueError(f"unknown verification mode: {mode}")
    if seed < 0:
        raise ValueError("seed must be >= 0")
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if verification_capacity_per_window <= 0.0:
        raise ValueError("verification capacity must be > 0")
    config = ControllerConfig()
    if not config.min_fanout <= initial_fanout <= config.max_fanout:
        raise ValueError("initial_fanout must fit controller fanout bounds")

    queue: list[ScalingCandidate] = []
    next_index = 0
    fanout = initial_fanout
    generated = 0
    examined = 0
    accepted = 0
    verified_useful = 0
    escaped_defects = 0
    detected_defects = 0
    false_rejections = 0
    verification_cost = 0.0
    human_attention = 0.0
    test_executions = 0
    queue_lengths: list[int] = []
    wait_steps: list[int] = []
    fanout_history: list[int] = []
    stream_hasher = hashlib.sha256()
    escaped_by_class = {name: 0 for name in DEFECT_CLASSES}
    detected_by_class = {name: 0 for name in DEFECT_CLASSES}

    for _step in range(steps):
        queue = [candidate.aged() for candidate in queue]
        for _ in range(fanout):
            candidate = make_candidate(seed, next_index)
            next_index += 1
            generated += 1
            stream_hasher.update((_stream_record(candidate) + "\n").encode("utf-8"))
            queue.append(candidate)

        selected = _select_for_window(
            queue,
            mode,
            verification_capacity_per_window,
        )
        selected_ids = {candidate.id for candidate in selected}
        for candidate in selected:
            bundle = evidence_bundle(mode, candidate)
            decision = _accepted(mode, candidate, seed)
            if bundle:
                examined += 1
                verification_cost += bundle_cost(bundle)
                human_attention += _human_attention_units(bundle)
                test_executions += int("independent-test" in bundle)
            if decision:
                accepted += 1
                if candidate.defective:
                    escaped_defects += 1
                    escaped_by_class[candidate.defect_class] += 1
                elif bundle:
                    verified_useful += 1
            elif candidate.defective:
                detected_defects += 1
                detected_by_class[candidate.defect_class] += 1
            else:
                false_rejections += 1
            wait_steps.append(candidate.age_steps)

        queue = [candidate for candidate in queue if candidate.id not in selected_ids]
        if mode == "risk-adaptive-backpressure":
            debt = total_verification_debt(
                [_debt_candidate(candidate, mode) for candidate in queue],
                config,
            )
            fanout = next_generation_fanout(
                current_fanout=fanout,
                debt=debt,
                verification_capacity_per_window=verification_capacity_per_window,
                config=config,
            )
        else:
            fanout = initial_fanout
        queue_lengths.append(len(queue))
        fanout_history.append(fanout)

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "candidate_generator_version": CANDIDATE_GENERATOR_VERSION,
        "mode": mode,
        "seed": seed,
        "steps": steps,
        "initial_fanout": initial_fanout,
        "verification_capacity_per_window": verification_capacity_per_window,
        "generated_candidates": generated,
        "generated_stream_sha256": stream_hasher.hexdigest(),
        "independently_examined_candidates": examined,
        "simulated_accepted_candidates": accepted,
        "verified_useful_accepted_candidates": verified_useful,
        "verified_useful_throughput_per_window": round(verified_useful / steps, 6),
        "escaped_defects": escaped_defects,
        "escaped_defect_rate": round(escaped_defects / accepted, 6) if accepted else 0.0,
        "detected_defects": detected_defects,
        "false_rejections": false_rejections,
        "escaped_defects_by_class": escaped_by_class,
        "detected_defects_by_class": detected_by_class,
        "verification_cost_consumed": round(verification_cost, 6),
        "human_attention_units": round(human_attention, 6),
        "independent_test_executions": test_executions,
        "pending_candidates": len(queue),
        "peak_queue_length": max(queue_lengths, default=0),
        "mean_queue_length": round(statistics.fmean(queue_lengths), 6),
        "mean_wait_steps": round(statistics.fmean(wait_steps), 6) if wait_steps else 0.0,
        "final_fanout": fanout,
        "min_fanout": min(fanout_history, default=initial_fanout),
        "max_fanout": max(fanout_history, default=initial_fanout),
        "reviewer_shared_error_rate": 0.25,
        "integration_authority": "none",
    }


SUMMARY_METRICS = (
    "generated_candidates",
    "independently_examined_candidates",
    "simulated_accepted_candidates",
    "verified_useful_accepted_candidates",
    "verified_useful_throughput_per_window",
    "escaped_defects",
    "escaped_defect_rate",
    "detected_defects",
    "false_rejections",
    "verification_cost_consumed",
    "human_attention_units",
    "independent_test_executions",
    "pending_candidates",
    "peak_queue_length",
    "mean_queue_length",
    "mean_wait_steps",
    "final_fanout",
)


def _aggregate(runs: Sequence[dict[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {"runs": len(runs)}
    for metric in SUMMARY_METRICS:
        values = [float(run[metric]) for run in runs]
        output[metric] = {
            "mean": round(statistics.fmean(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }
    return output


def benchmark(
    *,
    seeds: int,
    steps: int,
    fanouts: Sequence[int],
    verification_capacity_per_window: float,
    include_runs: bool = True,
) -> dict[str, object]:
    if seeds < 1:
        raise ValueError("seeds must be >= 1")
    if not fanouts:
        raise ValueError("at least one fanout is required")
    normalized_fanouts = sorted(set(fanouts))
    runs = [
        simulate(
            mode=mode,
            seed=seed,
            steps=steps,
            initial_fanout=fanout,
            verification_capacity_per_window=verification_capacity_per_window,
        )
        for fanout in normalized_fanouts
        for seed in range(seeds)
        for mode in MODES
    ]
    summaries = [
        {
            "initial_fanout": fanout,
            "mode": mode,
            **_aggregate(
                [
                    run
                    for run in runs
                    if run["initial_fanout"] == fanout and run["mode"] == mode
                ]
            ),
        }
        for fanout in normalized_fanouts
        for mode in MODES
    ]
    payload: dict[str, object] = {
        "benchmark_version": BENCHMARK_VERSION,
        "candidate_generator_version": CANDIDATE_GENERATOR_VERSION,
        "experiment": "issue-14-seven-mode-verification-scaling",
        "seeds": list(range(seeds)),
        "steps": steps,
        "initial_fanouts": normalized_fanouts,
        "verification_capacity_per_window": verification_capacity_per_window,
        "modes": list(MODES),
        "evidence_channel_model": {
            "reviewer_independent_error_rate": 0.18,
            "reviewer_shared_error_rate": 0.25,
            "independent_test_sensitivity_by_defect_class": {
                "correctness": 0.86,
                "regression": 0.80,
                "security": 0.62,
            },
            "adversarial_reviewer_sensitivity_by_defect_class": {
                "correctness": 0.90,
                "regression": 0.91,
                "security": 0.96,
            },
        },
        "fairness": (
            "At fixed fanout and seed all non-adaptive modes receive the same "
            "candidate stream. Backpressure receives a deterministic prefix "
            "because it changes future generation volume."
        ),
        "authority": {
            "integration_authority": "none",
            "simulated_acceptance_is_canonical_acceptance": False,
        },
        "summaries": summaries,
    }
    if include_runs:
        payload["runs"] = runs
    return payload


def _parse_fanouts(raw: str) -> list[int]:
    try:
        values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("fanouts must be comma-separated integers") from exc
    if not values:
        raise argparse.ArgumentTypeError("fanouts cannot be empty")
    return values


def self_test() -> None:
    assert make_candidate(3, 7) == make_candidate(3, 7)
    assert set(MODES) == {
        "no-independent-verification",
        "one-reviewer",
        "fixed-three-reviewer-quorum",
        "independent-tests",
        "tests-plus-adversarial-reviewer",
        "risk-adaptive",
        "risk-adaptive-backpressure",
    }
    fixed = simulate(
        mode="risk-adaptive",
        seed=5,
        steps=60,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    adaptive = simulate(
        mode="risk-adaptive-backpressure",
        seed=5,
        steps=60,
        initial_fanout=12,
        verification_capacity_per_window=8.0,
    )
    assert adaptive["pending_candidates"] < fixed["pending_candidates"]
    assert adaptive["final_fanout"] < 12
    unsafe = simulate(
        mode="no-independent-verification",
        seed=5,
        steps=20,
        initial_fanout=4,
        verification_capacity_per_window=8.0,
    )
    assert unsafe["independently_examined_candidates"] == 0
    assert unsafe["verified_useful_accepted_candidates"] == 0
    assert unsafe["escaped_defects"] > 0
    assert all(
        simulate(
            mode=mode,
            seed=2,
            steps=10,
            initial_fanout=2,
            verification_capacity_per_window=8.0,
        )["integration_authority"]
        == "none"
        for mode in MODES
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--benchmark", action="store_true")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--fanouts", type=_parse_fanouts, default=[2, 4, 8, 12])
    parser.add_argument("--capacity", type=float, default=8.0)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        print("OK: verification scaling matrix self-test passed")
        return 0
    result = benchmark(
        seeds=args.seeds,
        steps=args.steps,
        fanouts=args.fanouts,
        verification_capacity_per_window=args.capacity,
        include_runs=not args.summary_only,
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
