#!/usr/bin/env python3
"""Anytime-valid sequential evidence primitives for guarded IDKMesh experiments.

This module addresses a specific failure mode in adaptive repositories: repeatedly
peeking at fixed-horizon confidence intervals can turn noise into apparent evidence.
The confidence sequence below spends a summable error budget across all observation
times, so a caller may stop at a data-dependent time without silently inflating the
nominal error probability under the stated bounded common-mean assumptions.

The module is deliberately read-only mathematics. A positive result can nominate a
bounded experiment; it never grants repository write, approval, or merge authority.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

EPS = 1e-12


def _validate_delta(delta: float) -> float:
    value = float(delta)
    if not 0.0 < value < 1.0:
        raise ValueError("delta must be in (0,1)")
    return value


def error_budget(delta: float, t: int) -> float:
    """Return the time-t error allocation delta/[t(t+1)].

    The telescoping identity sum_{t>=1} 1/[t(t+1)] = 1 means the allocations
    sum to delta. Combined with a fixed-time Hoeffding bound and a union bound,
    this yields simultaneous coverage over every positive integer t.
    """
    d = _validate_delta(delta)
    if t < 1:
        raise ValueError("t must be positive")
    return d / (t * (t + 1.0))


def hoeffding_radius(t: int, delta: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Two-sided union-Hoeffding radius for a bounded common mean."""
    if t < 1:
        raise ValueError("t must be positive")
    lo = float(lower)
    hi = float(upper)
    if not hi > lo:
        raise ValueError("upper must be greater than lower")
    dt = error_budget(delta, t)
    span = hi - lo
    return span * math.sqrt(math.log(2.0 / dt) / (2.0 * t))


def confidence_sequence(
    samples: Sequence[float],
    *,
    delta: float = 0.05,
    lower: float = 0.0,
    upper: float = 1.0,
) -> list[dict[str, float]]:
    """Return an anytime-valid Hoeffding confidence sequence.

    Assumption: observations are bounded in [lower, upper] and share a common
    expectation under an independent/common-mean or corresponding martingale
    model. Unknown dependence is not made safe by this function; callers should
    model or test that dependence separately.
    """
    _validate_delta(delta)
    lo = float(lower)
    hi = float(upper)
    if not hi > lo:
        raise ValueError("upper must be greater than lower")
    if not samples:
        raise ValueError("at least one sample is required")

    running = 0.0
    rows: list[dict[str, float]] = []
    for t, raw in enumerate(samples, start=1):
        value = float(raw)
        if value < lo - EPS or value > hi + EPS:
            raise ValueError(f"sample {t}={value} is outside [{lo},{hi}]")
        running += value
        mean = running / t
        radius = hoeffding_radius(t, delta, lo, hi)
        rows.append(
            {
                "t": float(t),
                "mean": mean,
                "radius": radius,
                "lower": max(lo, mean - radius),
                "upper": min(hi, mean + radius),
                "error_budget": error_budget(delta, t),
            }
        )
    return rows


def paired_effect_sequence(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    delta: float = 0.05,
) -> list[dict[str, float]]:
    """Anytime-valid sequence for paired candidate-minus-baseline effects.

    Candidate and baseline scores must be in [0,1] and paired on the same task,
    seed, or evaluation unit. Pairing removes shared nuisance variation before
    the sequential bound is constructed.
    """
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("candidate and baseline must have the same non-zero length")
    differences: list[float] = []
    for index, (cand, base) in enumerate(zip(candidate, baseline), start=1):
        c = float(cand)
        b = float(base)
        if not 0.0 <= c <= 1.0 or not 0.0 <= b <= 1.0:
            raise ValueError(f"paired scores at index {index} must be in [0,1]")
        differences.append(c - b)
    return confidence_sequence(differences, delta=delta, lower=-1.0, upper=1.0)


def paired_experiment_gate(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    min_effect: float = 0.0,
    delta: float = 0.05,
    min_samples: int = 32,
    hard_guard_ok: bool = True,
) -> dict[str, Any]:
    """Nominate, reject, or continue observing a paired experiment.

    A hard governance failure is conjunctive: statistical evidence cannot
    compensate for it. `experiment_candidate` remains a recommendation only.
    """
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    if min_effect < 0.0:
        raise ValueError("min_effect must be non-negative")
    sequence = paired_effect_sequence(candidate, baseline, delta=delta)
    final = sequence[-1]
    n = len(candidate)

    if not hard_guard_ok:
        decision = "guarded"
        reason = "hard governance guard is not satisfied"
    elif n < min_samples:
        decision = "observe"
        reason = "minimum paired sample count not reached"
    elif final["lower"] > float(min_effect):
        decision = "experiment_candidate"
        reason = "anytime lower confidence bound exceeds minimum effect"
    elif final["upper"] < float(min_effect):
        decision = "insufficient_effect"
        reason = "anytime upper confidence bound is below minimum effect"
    else:
        decision = "observe"
        reason = "confidence sequence still overlaps the minimum effect"

    return {
        "method": "paired-union-hoeffding",
        "n": n,
        "delta": float(delta),
        "min_effect": float(min_effect),
        "mean_effect": final["mean"],
        "lower_confidence": final["lower"],
        "upper_confidence": final["upper"],
        "decision": decision,
        "reason": reason,
        "authority": "candidate_only",
        "hard_guard_ok": bool(hard_guard_ok),
    }


def importance_weight_effective_sample_size(weights: Sequence[float]) -> float:
    """Kish effective sample size for non-negative importance weights."""
    if not weights:
        return 0.0
    values = [float(weight) for weight in weights]
    if any(weight < 0.0 for weight in values):
        raise ValueError("importance weights must be non-negative")
    total = sum(values)
    squared = sum(weight * weight for weight in values)
    if squared <= EPS:
        return 0.0
    return (total * total) / squared


def ips_sequence(
    rewards: Sequence[float],
    behavior_probability: Sequence[float],
    target_probability: Sequence[float],
    *,
    delta: float = 0.05,
    max_weight: float = 10.0,
) -> dict[str, Any]:
    """Build a bounded inverse-propensity evidence sequence.

    When no importance ratio is clipped, the Horvitz-Thompson contributions are
    suitable for the bounded confidence sequence under the usual logged-bandit
    overlap/common-mean assumptions. If clipping occurs, the sequence describes
    the clipped observable only and is explicitly *not* promoted as a target
    policy confidence interval.
    """
    if not rewards or len(rewards) != len(behavior_probability) or len(rewards) != len(target_probability):
        raise ValueError("reward, behavior probability, and target probability arrays must have the same non-zero length")
    if max_weight <= 0.0:
        raise ValueError("max_weight must be positive")

    raw_weights: list[float] = []
    bounded_weights: list[float] = []
    contributions: list[float] = []
    clipped_count = 0
    overlap_behavior: list[float] = []

    for index, (reward, behavior, target) in enumerate(
        zip(rewards, behavior_probability, target_probability), start=1
    ):
        r = float(reward)
        b = float(behavior)
        p = float(target)
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"reward {index} must be in [0,1]")
        if not 0.0 < b <= 1.0:
            raise ValueError(f"behavior probability {index} must be in (0,1]")
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"target probability {index} must be in [0,1]")
        if p > 0.0:
            overlap_behavior.append(b)
        raw = p / b
        bounded = min(raw, float(max_weight))
        if raw > float(max_weight) + EPS:
            clipped_count += 1
        raw_weights.append(raw)
        bounded_weights.append(bounded)
        contributions.append(bounded * r)

    sequence = confidence_sequence(
        contributions,
        delta=delta,
        lower=0.0,
        upper=float(max_weight),
    )
    final = sequence[-1]
    any_clipped = clipped_count > 0
    return {
        "method": "bounded-ips-union-hoeffding",
        "n": len(rewards),
        "estimate": final["mean"],
        "lower_confidence": final["lower"],
        "upper_confidence": final["upper"],
        "effective_sample_size": importance_weight_effective_sample_size(bounded_weights),
        "max_raw_weight": max(raw_weights),
        "max_weight": float(max_weight),
        "clipped_count": clipped_count,
        "clipped_fraction": clipped_count / len(rewards),
        "minimum_behavior_overlap": min(overlap_behavior) if overlap_behavior else 0.0,
        "valid_target_confidence_sequence": not any_clipped,
        "sequence": sequence,
    }


def ips_experiment_gate(
    rewards: Sequence[float],
    behavior_probability: Sequence[float],
    target_probability: Sequence[float],
    *,
    baseline_value: float,
    min_effect: float = 0.0,
    delta: float = 0.05,
    max_weight: float = 10.0,
    min_effective_samples: float = 32.0,
    hard_guard_ok: bool = True,
) -> dict[str, Any]:
    """Use off-policy evidence only when overlap and weight stability are adequate."""
    if not 0.0 <= float(baseline_value) <= 1.0:
        raise ValueError("baseline_value must be in [0,1]")
    if min_effect < 0.0:
        raise ValueError("min_effect must be non-negative")
    if min_effective_samples <= 0.0:
        raise ValueError("min_effective_samples must be positive")

    evidence = ips_sequence(
        rewards,
        behavior_probability,
        target_probability,
        delta=delta,
        max_weight=max_weight,
    )
    threshold = float(baseline_value) + float(min_effect)

    if not hard_guard_ok:
        decision = "guarded"
        reason = "hard governance guard is not satisfied"
    elif not evidence["valid_target_confidence_sequence"]:
        decision = "observe_clipped"
        reason = "importance clipping occurred; target-policy confidence claim is withheld"
    elif evidence["effective_sample_size"] < float(min_effective_samples):
        decision = "observe_low_ess"
        reason = "importance-weight effective sample size is too small"
    elif evidence["lower_confidence"] > threshold:
        decision = "experiment_candidate"
        reason = "anytime off-policy lower bound exceeds baseline plus minimum effect"
    elif evidence["upper_confidence"] < threshold:
        decision = "insufficient_effect"
        reason = "anytime off-policy upper bound is below baseline plus minimum effect"
    else:
        decision = "observe"
        reason = "off-policy confidence sequence still overlaps the target threshold"

    result = dict(evidence)
    result.pop("sequence")
    result.update(
        {
            "baseline_value": float(baseline_value),
            "min_effect": float(min_effect),
            "decision": decision,
            "reason": reason,
            "authority": "candidate_only",
            "hard_guard_ok": bool(hard_guard_ok),
        }
    )
    return result


def build_demo() -> dict[str, Any]:
    candidate = [1.0] * 128
    baseline = [0.0] * 128
    paired = paired_experiment_gate(
        candidate,
        baseline,
        min_effect=0.10,
        delta=0.05,
        min_samples=32,
        hard_guard_ok=True,
    )
    guarded = paired_experiment_gate(
        candidate,
        baseline,
        min_effect=0.10,
        delta=0.05,
        min_samples=32,
        hard_guard_ok=False,
    )
    ips = ips_experiment_gate(
        [0.9] * 128,
        [0.5] * 128,
        [0.5] * 128,
        baseline_value=0.30,
        min_effect=0.10,
        delta=0.05,
        max_weight=1.0,
        min_effective_samples=32.0,
        hard_guard_ok=True,
    )
    clipped = ips_experiment_gate(
        [1.0] * 64,
        [0.01] * 64,
        [0.90] * 64,
        baseline_value=0.20,
        max_weight=10.0,
        min_effective_samples=16.0,
    )
    return {
        "paired": paired,
        "paired_with_hard_guard_failure": guarded,
        "off_policy": ips,
        "off_policy_with_clipping": clipped,
        "invariants": {
            "optional_stopping_aware": True,
            "clipped_ips_cannot_nominate": clipped["decision"] == "observe_clipped",
            "hard_guard_non_compensation": guarded["decision"] == "guarded",
            "integration_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="emit a deterministic demonstration")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    if not args.demo:
        parser.error("--demo is currently required")
    payload = build_demo()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
