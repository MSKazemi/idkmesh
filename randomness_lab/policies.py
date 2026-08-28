from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Protocol, Sequence

from .model import Worker


@dataclass
class WorkerStats:
    attempts: int = 0
    successes: int = 0

    @property
    def mean(self) -> float:
        # Beta(1, 1) posterior mean gives an explicit neutral prior.
        return (self.successes + 1.0) / (self.attempts + 2.0)


@dataclass
class History:
    stats: dict[str, WorkerStats] = field(default_factory=dict)
    total_attempts: int = 0

    def for_worker(self, worker: Worker) -> WorkerStats:
        return self.stats.setdefault(worker.name, WorkerStats())

    def record(self, worker: Worker, success: bool) -> None:
        stats = self.for_worker(worker)
        stats.attempts += 1
        stats.successes += int(success)
        self.total_attempts += 1


class Policy(Protocol):
    name: str

    def select(
        self,
        workers: Sequence[Worker],
        history: History,
        rng: random.Random,
    ) -> Worker: ...


@dataclass
class GreedyPolicy:
    name: str = "greedy"

    def select(self, workers: Sequence[Worker], history: History, rng: random.Random) -> Worker:
        del rng
        return max(workers, key=lambda w: (history.for_worker(w).mean, -workers.index(w)))


@dataclass
class EpsilonGreedyPolicy:
    epsilon: float = 0.1
    name: str = "epsilon-greedy"

    def select(self, workers: Sequence[Worker], history: History, rng: random.Random) -> Worker:
        if not 0.0 <= self.epsilon <= 1.0:
            raise ValueError("epsilon must be in [0, 1]")
        if rng.random() < self.epsilon:
            return rng.choice(list(workers))
        return max(workers, key=lambda w: history.for_worker(w).mean)


@dataclass
class SoftmaxPolicy:
    temperature: float = 0.2
    name: str = "softmax"

    def select(self, workers: Sequence[Worker], history: History, rng: random.Random) -> Worker:
        if self.temperature <= 0.0:
            raise ValueError("temperature must be > 0")
        values = [history.for_worker(worker).mean for worker in workers]
        maximum = max(values)
        weights = [math.exp((value - maximum) / self.temperature) for value in values]
        return rng.choices(list(workers), weights=weights, k=1)[0]


@dataclass
class UCBPolicy:
    exploration: float = 2.0
    name: str = "ucb"

    def select(self, workers: Sequence[Worker], history: History, rng: random.Random) -> Worker:
        del rng
        for worker in workers:
            if history.for_worker(worker).attempts == 0:
                return worker
        t = max(1, history.total_attempts)

        def score(worker: Worker) -> float:
            stats = history.for_worker(worker)
            return stats.mean + self.exploration * math.sqrt(math.log(t + 1.0) / stats.attempts)

        return max(workers, key=score)


@dataclass
class ThompsonSamplingPolicy:
    name: str = "thompson"

    def select(self, workers: Sequence[Worker], history: History, rng: random.Random) -> Worker:
        def sample(worker: Worker) -> float:
            stats = history.for_worker(worker)
            alpha = stats.successes + 1
            beta = stats.attempts - stats.successes + 1
            return rng.betavariate(alpha, beta)

        return max(workers, key=sample)


POLICIES = ("greedy", "epsilon-greedy", "softmax", "ucb", "thompson")


def make_policy(name: str) -> Policy:
    normalized = name.strip().lower()
    if normalized == "greedy":
        return GreedyPolicy()
    if normalized in {"epsilon-greedy", "epsilon_greedy"}:
        return EpsilonGreedyPolicy()
    if normalized in {"softmax", "boltzmann"}:
        return SoftmaxPolicy()
    if normalized == "ucb":
        return UCBPolicy()
    if normalized in {"thompson", "thompson-sampling", "thompson_sampling"}:
        return ThompsonSamplingPolicy()
    raise ValueError(f"unknown policy {name!r}; choose one of {', '.join(POLICIES)}")


def power_of_d_least_loaded(
    loads: Sequence[float],
    rng: random.Random,
    d: int = 2,
) -> int:
    """Return the least-loaded index among ``d`` randomly sampled choices."""

    if not loads:
        raise ValueError("loads must not be empty")
    if d < 1:
        raise ValueError("d must be >= 1")
    sample_size = min(d, len(loads))
    candidates = rng.sample(range(len(loads)), k=sample_size)
    return min(candidates, key=lambda index: (loads[index], index))
