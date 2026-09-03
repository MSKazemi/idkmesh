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


@dataclass(frozen=True)
class ItemDifficultyEnvironment:
    """The same two parameters as ``CorrelatedBernoulliEnvironment``, other shape.

    ``CorrelatedBernoulliEnvironment`` is a flat shared shock: with probability
    ``rho`` every worker shares one correctness state, otherwise they are
    independent. E017 measured a real panel and found that shape wrong — it puts
    almost no probability on a task that *some* of the panel gets right, which is
    what most real joint failures look like. E018 recomputed E015's phase diagram
    under both shapes in closed form; this is the sampling counterpart of its
    ``item_difficulty_error``, so the two agree by construction.

    Each task draws a difficulty ``d ~ Beta(a, b)`` and every worker then fails
    independently with probability ``d``. Writing ``mu`` for the common error
    rate, ``a = mu * (1 - rho) / rho`` and ``b = (1 - mu) * (1 - rho) / rho``
    give marginal error ``E[d] = mu`` and pairwise error correlation
    ``Var(d) / (mu * (1 - mu)) = 1 / (a + b + 1) = rho``. So both shapes are
    parameterized by the same two numbers and coincide at ``rho = 0``
    (independent) and ``rho = 1`` (all-or-nothing); every difference between
    them in between is attributable to shape alone.

    **Equal success probabilities only.** A single task difficulty is only a
    correlation-matched reparameterization when the workers share one ``mu``.
    With heterogeneous workers there is no unique way to split one draw among
    them, so this raises rather than silently approximating. In the R1 lab that
    excludes exactly one arm, ``bandit_selected``.
    """

    error_correlation: float = 0.0
    name: str = "item-difficulty"

    def __post_init__(self) -> None:
        if not 0.0 <= self.error_correlation <= 1.0:
            raise ValueError("error_correlation must be in [0, 1]")

    def sample(
        self,
        workers: Sequence[Worker],
        rng: random.Random,
    ) -> dict[str, bool]:
        probabilities = {worker.success_probability for worker in workers}
        if len(probabilities) > 1:
            raise ValueError(
                "ItemDifficultyEnvironment needs one shared success probability; "
                f"got {sorted(probabilities)}. A single task difficulty cannot be "
                "split among heterogeneous workers without inventing a rule."
            )
        success_probability = next(iter(probabilities)) if probabilities else 0.0
        mu = 1.0 - success_probability

        rho = self.error_correlation
        if rho <= 0.0 or mu <= 0.0 or mu >= 1.0:
            difficulty = mu
        elif rho >= 1.0:
            # a, b -> 0, so the Beta degenerates to its endpoints: the whole
            # panel fails together with probability mu. This is the shared shock
            # at rho = 1, which is the agreement the docstring claims.
            difficulty = 1.0 if rng.random() < mu else 0.0
        else:
            scale = (1.0 - rho) / rho
            difficulty = rng.betavariate(mu * scale, (1.0 - mu) * scale)

        return {
            worker.name: bool(rng.random() >= difficulty) for worker in workers
        }

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "error_correlation": self.error_correlation,
            "model": "beta-binomial item difficulty, matched marginal and correlation",
        }


def sample_worker_outcomes(
    workers: Iterable[Worker],
    rng: random.Random,
    error_correlation: float,
) -> dict[str, bool]:
    """Backward-compatible helper using ``CorrelatedBernoulliEnvironment``."""

    worker_list = list(workers)
    return CorrelatedBernoulliEnvironment(error_correlation).sample(worker_list, rng)
