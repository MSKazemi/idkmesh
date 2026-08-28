#!/usr/bin/env python3
"""Deterministic contamination-robust evidence envelopes for IDKMesh.

This module handles a failure mode that correlation discounting does not: some
accepted reports may be arbitrary, faulty, compromised, or strategically false.
Given only scalar reports and an upper bound ``f`` on the number of arbitrary
reports, the core routine returns the *sharp* interval containing the mean of the
honest reports for every corruption pattern of size at most ``f``.

The guarantee is about the reports that remain honest, not about external truth.
It is not a Byzantine consensus protocol and it does not provide Sybil resistance.
All outputs are observation/candidate support only and grant no integration power.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

EPS = 1e-12


def _stable_sum(values: Sequence[float]) -> float:
    """Explicit left-to-right IEEE-754 accumulation for cross-version replay."""
    total = 0.0
    for value in values:
        total += float(value)
    return total


def _stable_mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return _stable_sum(values) / len(values)


def _validate_fault_budget(max_faults: int, n: int) -> int:
    if isinstance(max_faults, bool) or not isinstance(max_faults, int):
        raise ValueError("max_faults must be an integer")
    if max_faults < 0:
        raise ValueError("max_faults must be non-negative")
    if n < 1:
        raise ValueError("at least one report is required")
    if max_faults >= n:
        raise ValueError("max_faults must be smaller than the report count")
    return max_faults


def _validate_reports(
    reports: Sequence[float],
    *,
    lower: float,
    upper: float,
) -> list[float]:
    lo = float(lower)
    hi = float(upper)
    if not math.isfinite(lo) or not math.isfinite(hi):
        raise ValueError("lower and upper must be finite")
    if not hi > lo:
        raise ValueError("upper must be greater than lower")
    if not reports:
        raise ValueError("at least one report is required")
    values = [float(value) for value in reports]
    for index, value in enumerate(values, start=1):
        if not math.isfinite(value):
            raise ValueError(f"report {index} must be finite")
        if value < lo - EPS or value > hi + EPS:
            raise ValueError(f"report {index}={value} is outside [{lo},{hi}]")
    return values


def adversarial_mean_envelope(
    reports: Sequence[float],
    max_faults: int,
    *,
    lower: float = 0.0,
    upper: float = 1.0,
) -> dict[str, Any]:
    """Return the sharp honest-report mean envelope under <= ``max_faults`` faults.

    Let ``n`` reports be observed and suppose at most ``f`` are arbitrary. The
    honest set therefore has size ``h >= n-f``. With sorted reports

        x_(1) <= ... <= x_(n),

    every admissible honest-set mean lies in

        [ mean(x_(1)..x_(n-f)), mean(x_(f+1)..x_(n)) ].

    The interval is sharp given only the report values and the count bound: each
    endpoint is attained by an admissible assignment that marks the opposite
    ``f`` extreme reports faulty. No independence or distributional assumption is
    required for this report-level statement.
    """
    values = _validate_reports(reports, lower=lower, upper=upper)
    n = len(values)
    f = _validate_fault_budget(max_faults, n)
    ordered = sorted(values)
    guaranteed_honest = n - f

    low_values = ordered[:guaranteed_honest]
    high_values = ordered[f:]
    honest_mean_lower = _stable_mean(low_values)
    honest_mean_upper = _stable_mean(high_values)
    naive_mean = _stable_mean(values)

    middle = n // 2
    if n % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2.0

    central = ordered[f : n - f] if n > 2 * f else []
    trimmed_mean = _stable_mean(central) if central else None

    return {
        "method": "sharp-count-contamination-mean-envelope",
        "n": n,
        "max_faults": f,
        "max_fault_fraction": f / n,
        "guaranteed_honest_count": guaranteed_honest,
        "guaranteed_honest_majority": guaranteed_honest > f,
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "naive_mean": naive_mean,
        "median": median,
        "f_trimmed_mean": trimmed_mean,
        "honest_mean_lower": honest_mean_lower,
        "honest_mean_upper": honest_mean_upper,
        "honest_mean_midpoint": (honest_mean_lower + honest_mean_upper) / 2.0,
        "envelope_width": honest_mean_upper - honest_mean_lower,
        "sharp_given_count_bound": True,
        "distribution_free_report_level": True,
        "independence_claim": False,
        "truth_claim": False,
        "sybil_resistance_claim": False,
        "byzantine_consensus_claim": False,
        "authority": "observation_only",
    }


def threshold_certificate(
    reports: Sequence[float],
    max_faults: int,
    *,
    threshold: float = 0.5,
    margin: float = 0.0,
    lower: float = 0.0,
    upper: float = 1.0,
    hard_guard_ok: bool = True,
) -> dict[str, Any]:
    """Certify a threshold direction for every admissible honest subset.

    ``support_certified`` means every possible honest-report mean under the fault
    budget is above ``threshold + margin``. ``reject_certified`` is the symmetric
    statement below ``threshold - margin``. Otherwise the fault model itself is
    too uncertain to certify a direction.
    """
    lo = float(lower)
    hi = float(upper)
    t = float(threshold)
    m = float(margin)
    if not all(math.isfinite(value) for value in (lo, hi, t, m)):
        raise ValueError("threshold, margin, lower, and upper must be finite")
    if not lo <= t <= hi:
        raise ValueError("threshold must lie inside [lower,upper]")
    if m < 0.0:
        raise ValueError("margin must be non-negative")
    if t - m < lo - EPS or t + m > hi + EPS:
        raise ValueError("threshold +/- margin must lie inside [lower,upper]")

    envelope = adversarial_mean_envelope(
        reports,
        max_faults,
        lower=lo,
        upper=hi,
    )
    robust_support = envelope["honest_mean_lower"] > t + m + EPS
    robust_reject = envelope["honest_mean_upper"] < t - m - EPS

    naive = envelope["naive_mean"]
    if naive > t + m + EPS:
        naive_direction = "support"
    elif naive < t - m - EPS:
        naive_direction = "reject"
    else:
        naive_direction = "uncertain"

    if robust_support:
        certificate = "support_certified"
    elif robust_reject:
        certificate = "reject_certified"
    else:
        certificate = "uncertain_under_fault_budget"

    if not hard_guard_ok:
        decision = "guarded"
        reason = "hard governance guard is not satisfied"
    elif certificate == "support_certified":
        decision = "experiment_candidate"
        reason = "every admissible honest-report mean exceeds threshold plus margin"
    elif certificate == "reject_certified":
        decision = "insufficient_support"
        reason = "every admissible honest-report mean is below threshold minus margin"
    else:
        decision = "observe_adversarial_uncertainty"
        reason = "fault-budget envelope overlaps the threshold decision region"

    robust_direction = (
        "support"
        if robust_support
        else "reject"
        if robust_reject
        else "uncertain"
    )
    return {
        "method": "adversarial-threshold-certificate",
        "threshold": t,
        "margin": m,
        "certificate": certificate,
        "naive_direction": naive_direction,
        "robust_direction": robust_direction,
        "naive_decision_fragile": naive_direction in {"support", "reject"}
        and robust_direction == "uncertain",
        "decision": decision,
        "reason": reason,
        "hard_guard_ok": bool(hard_guard_ok),
        "authority": "candidate_only",
        "envelope": envelope,
    }


def binary_vote_certificate(votes: Sequence[int], max_faults: int) -> dict[str, Any]:
    """Specialize the sharp envelope to binary support/reject reports."""
    if not votes:
        raise ValueError("at least one vote is required")
    normalized: list[float] = []
    for vote in votes:
        if isinstance(vote, bool):
            vote = int(vote)
        if vote not in (0, 1):
            raise ValueError("votes must be 0 or 1")
        normalized.append(float(vote))

    result = threshold_certificate(
        normalized,
        max_faults,
        threshold=0.5,
        margin=0.0,
        lower=0.0,
        upper=1.0,
        hard_guard_ok=True,
    )
    supports = sum(1 for vote in votes if int(vote) == 1)
    rejects = len(votes) - supports
    f = int(max_faults)
    result.update(
        {
            "supports": supports,
            "rejects": rejects,
            "at_least_one_honest_support_certified": supports > f,
            "at_least_one_honest_reject_certified": rejects > f,
            "honest_support_majority_certified": result["certificate"]
            == "support_certified",
            "honest_reject_majority_certified": result["certificate"]
            == "reject_certified",
        }
    )
    return result


def fault_budget_sensitivity(
    reports: Sequence[float],
    *,
    max_faults: int | None = None,
    lower: float = 0.0,
    upper: float = 1.0,
) -> list[dict[str, Any]]:
    """Show how adversarial uncertainty expands as the accepted fault budget grows."""
    values = _validate_reports(reports, lower=lower, upper=upper)
    n = len(values)
    limit = n - 1 if max_faults is None else _validate_fault_budget(max_faults, n)
    rows: list[dict[str, Any]] = []
    previous_width = -1.0
    for f in range(limit + 1):
        envelope = adversarial_mean_envelope(values, f, lower=lower, upper=upper)
        width = envelope["envelope_width"]
        monotone = width + EPS >= previous_width
        rows.append(
            {
                "max_faults": f,
                "guaranteed_honest_count": envelope["guaranteed_honest_count"],
                "honest_mean_lower": envelope["honest_mean_lower"],
                "honest_mean_upper": envelope["honest_mean_upper"],
                "envelope_width": width,
                "width_nondecreasing": monotone,
            }
        )
        previous_width = width
    return rows


def build_demo() -> dict[str, Any]:
    robust_support = threshold_certificate(
        [0.0, 0.0] + [0.9] * 7,
        2,
        threshold=0.5,
        margin=0.1,
    )
    fragile_naive = threshold_certificate(
        [0.0] + [0.6] * 6,
        1,
        threshold=0.5,
        margin=0.0,
    )
    binary = binary_vote_certificate([1] * 7 + [0] * 3, 2)
    guarded = threshold_certificate(
        [0.0, 0.0] + [0.9] * 7,
        2,
        threshold=0.5,
        margin=0.1,
        hard_guard_ok=False,
    )
    sensitivity = fault_budget_sensitivity([0.1, 0.2, 0.4, 0.8, 0.9], max_faults=3)
    return {
        "robust_support": robust_support,
        "fragile_naive_support": fragile_naive,
        "binary_vote_certificate": binary,
        "hard_guard_dominates": guarded,
        "fault_budget_sensitivity": sensitivity,
        "invariants": {
            "fault_budget_can_block_naive_support": fragile_naive["naive_decision_fragile"]
            and fragile_naive["decision"] == "observe_adversarial_uncertainty",
            "robust_support_can_be_certified": robust_support["decision"]
            == "experiment_candidate",
            "binary_honest_majority_can_be_certified": binary[
                "honest_support_majority_certified"
            ],
            "hard_guard_non_compensation": guarded["decision"] == "guarded",
            "fault_uncertainty_is_monotone": all(
                row["width_nondecreasing"] for row in sensitivity
            ),
            "truth_claim": False,
            "sybil_resistance_claim": False,
            "byzantine_consensus_claim": False,
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
