from __future__ import annotations

import math
from statistics import mean, stdev
from typing import Callable, Sequence

from .model import Worker
from .policies import Policy
from .simulator import SimulationConfig, run_simulation


def _normal_95_interval(values: Sequence[float]) -> list[float] | None:
    """Return a simple descriptive 95% normal-approximation interval for the mean."""

    if len(values) < 2:
        return None
    center = mean(values)
    standard_error = stdev(values) / math.sqrt(len(values))
    margin = 1.96 * standard_error
    return [center - margin, center + margin]


def run_trials(
    workers: Sequence[Worker],
    policy_factory: Callable[[], Policy],
    *,
    rounds: int,
    trials: int,
    base_seed: int = 42,
    error_correlation: float = 0.0,
) -> dict[str, object]:
    """Run repeated seeded simulations and retain raw results plus summaries.

    Each trial receives seed ``base_seed + trial_index`` and a fresh policy
    instance. The full raw simulation output is retained to avoid hiding
    distributions behind one composite score.
    """

    if trials < 1:
        raise ValueError("trials must be >= 1")

    results = []
    for trial_index in range(trials):
        config = SimulationConfig(
            rounds=rounds,
            seed=base_seed + trial_index,
            error_correlation=error_correlation,
        )
        results.append(run_simulation(workers, policy_factory(), config))

    success_rates = [float(result["metrics"]["verified_success_rate"]) for result in results]
    correlations = [
        result["metrics"]["mean_pairwise_error_correlation"] for result in results
    ]
    defined_correlations = [float(value) for value in correlations if value is not None]

    success_std = stdev(success_rates) if len(success_rates) > 1 else 0.0
    correlation_mean = mean(defined_correlations) if defined_correlations else None

    return {
        "schema_version": 1,
        "experiment": "repeated-worker-selection",
        "policy": results[0]["policy"],
        "trial_count": trials,
        "rounds_per_trial": rounds,
        "base_seed": base_seed,
        "error_correlation": error_correlation,
        "summary": {
            "mean_verified_success_rate": mean(success_rates),
            "sample_std_verified_success_rate": success_std,
            "normal_approx_95_ci_verified_success_rate": _normal_95_interval(success_rates),
            "min_verified_success_rate": min(success_rates),
            "max_verified_success_rate": max(success_rates),
            "mean_realized_pairwise_error_correlation": correlation_mean,
        },
        "trials": results,
        "uncertainty_note": (
            "The 95% interval is a descriptive normal approximation across seeded trial means; "
            "retain and inspect raw trial distributions, especially for small trial counts."
        ),
    }
