from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable


@dataclass(frozen=True)
class Worker:
    """Synthetic worker used by the randomness-lab simulator."""

    name: str
    success_probability: float
    compute_cost: float = 1.0
    latency: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.success_probability <= 1.0:
            raise ValueError("success_probability must be in [0, 1]")
        if self.compute_cost < 0.0:
            raise ValueError("compute_cost must be non-negative")
        if self.latency < 0.0:
            raise ValueError("latency must be non-negative")


def sample_worker_outcomes(
    workers: Iterable[Worker],
    rng: random.Random,
    error_correlation: float,
) -> dict[str, bool]:
    """Sample one latent verified outcome for every worker.

    ``error_correlation`` is implemented as a transparent mixture model. With
    probability ``error_correlation`` all workers are evaluated against the
    same random draw; otherwise each worker gets an independent draw. This is
    not intended as a universal model of correlated failures. It is a simple,
    reproducible control knob for experiments that compare diversity policies.
    """

    if not 0.0 <= error_correlation <= 1.0:
        raise ValueError("error_correlation must be in [0, 1]")

    workers = list(workers)
    use_shared_draw = rng.random() < error_correlation
    shared_draw = rng.random() if use_shared_draw else None

    outcomes: dict[str, bool] = {}
    for worker in workers:
        draw = shared_draw if shared_draw is not None else rng.random()
        outcomes[worker.name] = bool(draw < worker.success_probability)
    return outcomes
