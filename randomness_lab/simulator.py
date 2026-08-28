from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from statistics import mean
from typing import Sequence

from .model import CorrelatedBernoulliEnvironment, OutcomeEnvironment, Worker
from .policies import History, Policy


@dataclass(frozen=True)
class SimulationConfig:
    rounds: int = 1000
    seed: int = 42
    error_correlation: float = 0.0

    def __post_init__(self) -> None:
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if not 0.0 <= self.error_correlation <= 1.0:
            raise ValueError("error_correlation must be in [0, 1]")


def _pearson_binary(xs: Sequence[int], ys: Sequence[int]) -> float | None:
    if len(xs) != len(ys) or not xs:
        return None
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denominator = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denominator == 0.0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / denominator


def _mean_pairwise_error_correlation(
    workers: Sequence[Worker],
    latent_outcomes: dict[str, list[int]],
) -> float | None:
    correlations: list[float] = []
    for i, left in enumerate(workers):
        left_errors = [1 - outcome for outcome in latent_outcomes[left.name]]
        for right in workers[i + 1 :]:
            right_errors = [1 - outcome for outcome in latent_outcomes[right.name]]
            corr = _pearson_binary(left_errors, right_errors)
            if corr is not None:
                correlations.append(corr)
    return mean(correlations) if correlations else None


def run_simulation(
    workers: Sequence[Worker],
    policy: Policy,
    config: SimulationConfig,
    *,
    environment: OutcomeEnvironment | None = None,
) -> dict[str, object]:
    """Run one reproducible worker-selection experiment.

    The simulator samples latent outcomes for all workers each round so it can
    measure the environment's realized pairwise error correlation. Only the
    selected worker is charged compute/latency and contributes to the observed
    verified success metric.

    A custom ``OutcomeEnvironment`` can be supplied for alternative synthetic
    failure models. If omitted, the config's ``error_correlation`` selects the
    built-in correlated-Bernoulli mixture environment.
    """

    if not workers:
        raise ValueError("workers must not be empty")
    if len({worker.name for worker in workers}) != len(workers):
        raise ValueError("worker names must be unique")

    active_environment = environment or CorrelatedBernoulliEnvironment(
        config.error_correlation
    )
    rng = random.Random(config.seed)
    history = History()
    selected_counts = {worker.name: 0 for worker in workers}
    latent_outcomes = {worker.name: [] for worker in workers}
    successes = 0
    total_compute = 0.0
    total_latency = 0.0

    for _ in range(config.rounds):
        outcomes = active_environment.sample(workers, rng)
        if set(outcomes) != set(latent_outcomes):
            raise ValueError("environment must return exactly one outcome for every worker")
        for worker in workers:
            latent_outcomes[worker.name].append(int(outcomes[worker.name]))

        selected = policy.select(workers, history, rng)
        success = outcomes[selected.name]
        history.record(selected, success)
        selected_counts[selected.name] += 1
        successes += int(success)
        total_compute += selected.compute_cost
        total_latency += selected.latency

    empirical_rates = {
        worker.name: mean(latent_outcomes[worker.name]) for worker in workers
    }

    return {
        "schema_version": 1,
        "policy": policy.name,
        "environment": active_environment.describe(),
        "config": asdict(config),
        "workers": [asdict(worker) for worker in workers],
        "metrics": {
            "verified_successes": successes,
            "verified_success_rate": successes / config.rounds,
            "total_compute": total_compute,
            "total_latency": total_latency,
            "mean_compute_per_round": total_compute / config.rounds,
            "mean_latency_per_round": total_latency / config.rounds,
            "selected_counts": selected_counts,
            "empirical_worker_success_rates": empirical_rates,
            "mean_pairwise_error_correlation": _mean_pairwise_error_correlation(
                workers, latent_outcomes
            ),
        },
        "reproducibility": {
            "random_seed": config.seed,
            "randomness_source": "python.random.Random / Mersenne Twister",
            "note": "Scientific simulation only; not suitable for security-sensitive randomness.",
        },
    }
