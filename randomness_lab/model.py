from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Protocol, Sequence


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


class OutcomeEnvironment(Protocol):
    """Minimal interface for a synthetic verified-outcome environment."""

    name: str

    def sample(
        self,
        workers: Sequence[Worker],
        rng: random.Random,
    ) -> dict[str, bool]: ...

    def describe(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class CorrelatedBernoulliEnvironment:
    """Simple Bernoulli worker model with a transparent shared-draw mixture."""

    error_correlation: float = 0.0
    name: str = "correlated-bernoulli"

    def __post_init__(self) -> None:
        if not 0.0 <= self.error_correlation <= 1.0:
            raise ValueError("error_correlation must be in [0, 1]")

    def sample(
        self,
        workers: Sequence[Worker],
        rng: random.Random,
    ) -> dict[str, bool]:
        use_shared_draw = rng.random() < self.error_correlation
        shared_draw = rng.random() if use_shared_draw else None

        outcomes: dict[str, bool] = {}
        for worker in workers:
            draw = shared_draw if shared_draw is not None else rng.random()
            outcomes[worker.name] = bool(draw < worker.success_probability)
        return outcomes

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "error_correlation": self.error_correlation,
            "model": "shared-draw mixture plus independent Bernoulli draws",
        }


def sample_worker_outcomes(
    workers: Iterable[Worker],
    rng: random.Random,
    error_correlation: float,
) -> dict[str, bool]:
    """Backward-compatible helper using ``CorrelatedBernoulliEnvironment``."""

    worker_list = list(workers)
    return CorrelatedBernoulliEnvironment(error_correlation).sample(worker_list, rng)
