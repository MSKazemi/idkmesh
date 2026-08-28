#!/usr/bin/env python3
"""Anytime-valid bounded drift detection for IDKMesh evidence streams.

The sequential evidence kernel protects against optional stopping while a bounded
common-mean model remains credible. This module protects that assumption by
scanning every admissible prefix/split pair with a globally summable error budget.

A detected change blocks experiment nomination and requests regime review. It
never deletes evidence, rewrites canonical state, approves a patch, or grants
integration authority.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # Package import in tests.
    from scripts.sequential_evidence import paired_experiment_gate
except ModuleNotFoundError:  # Direct CLI execution from scripts/.
    from sequential_evidence import paired_experiment_gate

EPS = 1e-12


def _validate_delta(delta: float) -> float:
    value = float(delta)
    if not 0.0 < value < 1.0:
        raise ValueError("delta must be in (0,1)")
    return value


def reciprocal_square_tail(start: int) -> float:
    """Return sum_{t=start..infinity} 1/t^2 using deterministic accumulation.

    Python 3.12 changed the implementation of built-in ``sum`` for floats. An
    explicit left-to-right accumulator keeps this evidence normalizer identical
    across the supported Python 3.11/3.13 interpreters while still using the
    Basel identity for the infinite tail.
    """
    if start < 1:
        raise ValueError("start must be positive")
    prefix = 0.0
    for t in range(1, start):
        prefix += 1.0 / (t * t)
    tail = (math.pi * math.pi / 6.0) - prefix
    if tail <= 0.0:
        raise ValueError("reciprocal-square tail lost numerical precision")
    return tail


def split_error_budget(delta: float, t: int, k: int, min_window: int) -> float:
    """Allocate family-wise error across all future times and admissible splits.

    For a fixed minimum window m, the scan starts at t=2m. At time t there are
    t-2m+1 admissible splits. The allocation is

        delta_{t,k} = delta / (Z_m * t^2 * (t-2m+1)),

    where Z_m = sum_{s=2m..infinity} 1/s^2.

    Summing over every admissible k cancels the split count, and summing over t
    yields exactly delta (up to floating-point evaluation of Z_m).
    """
    d = _validate_delta(delta)
    if min_window < 1:
        raise ValueError("min_window must be positive")
    if t < 2 * min_window:
        raise ValueError("t is too small for two minimum-size windows")
    if k < min_window or k > t - min_window:
        raise ValueError("k is not an admissible split")
    split_count = t - 2 * min_window + 1
    normalizer = reciprocal_square_tail(2 * min_window)
    return d / (normalizer * t * t * split_count)


def two_window_hoeffding_threshold(
    n_before: int,
    n_after: int,
    delta_pair: float,
    *,
    lower: float = 0.0,
    upper: float = 1.0,
) -> float:
    """Two-sided Hoeffding threshold for the difference of two bounded means."""
    if n_before < 1 or n_after < 1:
        raise ValueError("both window sizes must be positive")
    d = _validate_delta(delta_pair)
    lo = float(lower)
    hi = float(upper)
    if not hi > lo:
        raise ValueError("upper must be greater than lower")
    span = hi - lo
    variance_proxy = (1.0 / n_before) + (1.0 / n_after)
    return span * math.sqrt(0.5 * variance_proxy * math.log(2.0 / d))


def _validate_samples(samples: Sequence[float], lower: float, upper: float) -> list[float]:
    if not samples:
        raise ValueError("at least one sample is required")
    lo = float(lower)
    hi = float(upper)
    if not hi > lo:
        raise ValueError("upper must be greater than lower")
    values = [float(value) for value in samples]
    for index, value in enumerate(values, start=1):
        if value < lo - EPS or value > hi + EPS:
            raise ValueError(f"sample {index}={value} is outside [{lo},{hi}]")
    return values


def anytime_change_scan(
    samples: Sequence[float],
    *,
    delta: float = 0.05,
    lower: float = 0.0,
    upper: float = 1.0,
    min_window: int = 16,
) -> dict[str, Any]:
    """Scan all admissible historical split points with family-wise error <= delta.

    Null model: the bounded observations share a common expectation under an
    independent/common-mean or corresponding bounded martingale model. For each
    fixed (t,k), Hoeffding bounds the before/after mean gap. `split_error_budget`
    makes the sum of all future pairwise error budgets at most delta, so a union
    bound controls the probability of *any* false alarm over indefinite peeking.

    The detector is intentionally conservative and quadratic in the number of
    observations. It is intended for evidence/control streams, not high-rate raw
    telemetry.
    """
    d = _validate_delta(delta)
    if min_window < 1:
        raise ValueError("min_window must be positive")
    values = _validate_samples(samples, lower, upper)
    n = len(values)

    prefix = [0.0]
    for value in values:
        prefix.append(prefix[-1] + value)

    first_alarm: dict[str, Any] | None = None
    strongest: dict[str, Any] | None = None
    tested_splits = 0
    normalizer = reciprocal_square_tail(2 * min_window)

    if n >= 2 * min_window:
        for t in range(2 * min_window, n + 1):
            split_count = t - 2 * min_window + 1
            for k in range(min_window, t - min_window + 1):
                tested_splits += 1
                n_before = k
                n_after = t - k
                mean_before = prefix[k] / n_before
                mean_after = (prefix[t] - prefix[k]) / n_after
                gap = mean_after - mean_before
                pair_delta = d / (normalizer * t * t * split_count)
                threshold = two_window_hoeffding_threshold(
                    n_before,
                    n_after,
                    pair_delta,
                    lower=lower,
                    upper=upper,
                )
                ratio = abs(gap) / threshold if threshold > EPS else math.inf
                record = {
                    "t": t,
                    "split": k,
                    "n_before": n_before,
                    "n_after": n_after,
                    "mean_before": mean_before,
                    "mean_after": mean_after,
                    "gap_after_minus_before": gap,
                    "absolute_gap": abs(gap),
                    "threshold": threshold,
                    "threshold_ratio": ratio,
                    "pair_error_budget": pair_delta,
                    "direction": "increase" if gap > 0.0 else "decrease" if gap < 0.0 else "flat",
                }
                if strongest is None or ratio > strongest["threshold_ratio"]:
                    strongest = record
                if abs(gap) > threshold + EPS and first_alarm is None:
                    first_alarm = record

    return {
        "method": "anytime-two-window-union-hoeffding",
        "n": n,
        "delta": d,
        "lower": float(lower),
        "upper": float(upper),
        "min_window": min_window,
        "tested_splits": tested_splits,
        "detected_change": first_alarm is not None,
        "first_alarm": first_alarm,
        "strongest_scan": strongest,
        "interpretation": (
            "bounded change detected; review regime boundary before pooling evidence"
            if first_alarm is not None
            else "no bounded change detected at this sensitivity; stationarity is not proven"
        ),
        "authority": "observation_only",
        "automatic_history_deletion": False,
    }


def multi_metric_change_scan(
    series_by_metric: Mapping[str, Sequence[float]],
    *,
    delta: float = 0.05,
    lower: float = 0.0,
    upper: float = 1.0,
    min_window: int = 16,
) -> dict[str, Any]:
    """Control family-wise drift error across multiple named metrics.

    The total delta is divided equally across metrics; each metric then spends its
    share across all times and splits using `anytime_change_scan`.
    """
    d = _validate_delta(delta)
    if not series_by_metric:
        raise ValueError("at least one metric is required")
    names = sorted(series_by_metric)
    per_metric_delta = d / len(names)
    metrics: dict[str, Any] = {}
    detected: list[str] = []
    for name in names:
        result = anytime_change_scan(
            series_by_metric[name],
            delta=per_metric_delta,
            lower=lower,
            upper=upper,
            min_window=min_window,
        )
        metrics[name] = result
        if result["detected_change"]:
            detected.append(name)
    return {
        "method": "multi-metric-anytime-union-hoeffding",
        "delta": d,
        "per_metric_delta": per_metric_delta,
        "metric_count": len(names),
        "detected_change": bool(detected),
        "detected_metrics": detected,
        "metrics": metrics,
        "authority": "observation_only",
    }


def drift_guarded_paired_experiment_gate(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    min_effect: float = 0.0,
    total_delta: float = 0.05,
    drift_fraction: float = 0.20,
    min_samples: int = 32,
    min_window: int = 16,
    hard_guard_ok: bool = True,
) -> dict[str, Any]:
    """Compose drift detection with the paired sequential evidence gate.

    Ordering is deliberately conjunctive:

        hard governance guard > detected regime change > effect evidence.

    Absence of a drift alarm is not treated as proof of stationarity. A drift
    alarm preserves all evidence and blocks nomination pending regime review.
    """
    d = _validate_delta(total_delta)
    if not 0.0 < float(drift_fraction) < 1.0:
        raise ValueError("drift_fraction must be in (0,1)")
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("candidate and baseline must have the same non-zero length")

    differences: list[float] = []
    for index, (cand, base) in enumerate(zip(candidate, baseline), start=1):
        c = float(cand)
        b = float(base)
        if not 0.0 <= c <= 1.0 or not 0.0 <= b <= 1.0:
            raise ValueError(f"paired scores at index {index} must be in [0,1]")
        differences.append(c - b)

    drift_delta = d * float(drift_fraction)
    effect_delta = d - drift_delta
    drift = anytime_change_scan(
        differences,
        delta=drift_delta,
        lower=-1.0,
        upper=1.0,
        min_window=min_window,
    )
    effect = paired_experiment_gate(
        candidate,
        baseline,
        min_effect=min_effect,
        delta=effect_delta,
        min_samples=min_samples,
        hard_guard_ok=hard_guard_ok,
    )

    if not hard_guard_ok:
        decision = "guarded"
        reason = "hard governance guard is not satisfied"
    elif drift["detected_change"]:
        decision = "observe_drift"
        reason = "paired effect stream shows an anytime-valid bounded regime-change alarm"
    else:
        decision = effect["decision"]
        reason = effect["reason"]

    return {
        "method": "drift-guarded-paired-sequential-evidence",
        "n": len(candidate),
        "total_delta": d,
        "drift_delta": drift_delta,
        "effect_delta": effect_delta,
        "decision": decision,
        "reason": reason,
        "authority": "candidate_only",
        "hard_guard_ok": bool(hard_guard_ok),
        "drift": drift,
        "effect_evidence": effect,
        "history_policy": "preserve_all_evidence_and_review_regime_boundary",
        "automatic_history_deletion": False,
    }


def build_demo() -> dict[str, Any]:
    stable = [0.50] * 128
    shifted = [0.20] * 256 + [0.90] * 256

    stable_scan = anytime_change_scan(stable, delta=0.05, min_window=16)
    shifted_scan = anytime_change_scan(shifted, delta=0.05, min_window=32)

    stable_gate = drift_guarded_paired_experiment_gate(
        [0.90] * 128,
        [0.10] * 128,
        min_effect=0.10,
        min_samples=32,
        min_window=16,
    )
    changing_candidate = [0.60] * 256 + [1.00] * 256
    changing_baseline = [0.50] * 256 + [0.10] * 256
    drift_gate = drift_guarded_paired_experiment_gate(
        changing_candidate,
        changing_baseline,
        min_effect=0.05,
        min_samples=32,
        min_window=32,
    )
    hard_guard = drift_guarded_paired_experiment_gate(
        [0.90] * 128,
        [0.10] * 128,
        min_effect=0.10,
        min_samples=32,
        min_window=16,
        hard_guard_ok=False,
    )
    multi = multi_metric_change_scan(
        {"quality": stable, "risk": [0.10] * 256 + [0.80] * 256},
        delta=0.05,
        min_window=32,
    )

    return {
        "stable_scan": stable_scan,
        "shifted_scan": shifted_scan,
        "stable_effect_gate": stable_gate,
        "drift_blocked_effect_gate": drift_gate,
        "hard_guard_dominates": hard_guard,
        "multi_metric_scan": multi,
        "invariants": {
            "stable_constant_has_no_alarm": not stable_scan["detected_change"],
            "persistent_shift_is_detected": shifted_scan["detected_change"],
            "drift_blocks_nomination": drift_gate["decision"] == "observe_drift",
            "hard_guard_non_compensation": hard_guard["decision"] == "guarded",
            "history_is_preserved": not drift_gate["automatic_history_deletion"],
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
