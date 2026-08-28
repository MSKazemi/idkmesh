from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Sequence


R4_POLICIES = (
    "random",
    "greedy",
    "thompson",
    "stigmergy-no-evap",
    "stigmergy-evap",
    "stigmergy-evap-explore",
)


@dataclass(frozen=True)
class R4Worker:
    id: str
    before_shift: tuple[tuple[str, float], ...]
    after_shift: tuple[tuple[str, float], ...]
    available_from: int = 0
    unavailable_windows: tuple[tuple[int, int], ...] = ()
    newcomer: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("worker id must not be empty")
        if self.available_from < 0:
            raise ValueError("available_from must be >= 0")
        before_names = {name for name, _ in self.before_shift}
        after_names = {name for name, _ in self.after_shift}
        if before_names != after_names:
            raise ValueError("before_shift and after_shift must contain the same task classes")
        for _, probability in self.before_shift + self.after_shift:
            if not 0.0 <= probability <= 1.0:
                raise ValueError("worker success probabilities must be in [0, 1]")
        for start, end in self.unavailable_windows:
            if start < 0 or end <= start:
                raise ValueError("unavailable windows require 0 <= start < end")

    def available(self, step: int) -> bool:
        if step < self.available_from:
            return False
        return not any(start <= step < end for start, end in self.unavailable_windows)

    def success_probability(self, task_class: str, step: int, shift_step: int) -> float:
        pairs = self.before_shift if step < shift_step else self.after_shift
        values = dict(pairs)
        try:
            return values[task_class]
        except KeyError as exc:
            raise ValueError(f"worker {self.id!r} lacks task class {task_class!r}") from exc


@dataclass(frozen=True)
class R4Environment:
    name: str
    steps: int
    shift_step: int
    task_classes: tuple[str, ...]
    task_weights: tuple[float, ...]
    workers: tuple[R4Worker, ...]
    task_seed: int = 42
    outcome_seed: int = 4242
    snapshot_interval: int = 50

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("environment name must not be empty")
        if self.steps < 1:
            raise ValueError("steps must be >= 1")
        if not 0 <= self.shift_step < self.steps:
            raise ValueError("shift_step must be inside the run")
        if not self.task_classes:
            raise ValueError("task_classes must not be empty")
        if len(self.task_classes) != len(self.task_weights):
            raise ValueError("task_classes and task_weights must have equal length")
        if any(weight < 0.0 for weight in self.task_weights) or sum(self.task_weights) <= 0.0:
            raise ValueError("task weights must be non-negative with positive total")
        if not self.workers:
            raise ValueError("workers must not be empty")
        if len({worker.id for worker in self.workers}) != len(self.workers):
            raise ValueError("worker ids must be unique")
        required = set(self.task_classes)
        for worker in self.workers:
            if {name for name, _ in worker.before_shift} != required:
                raise ValueError("every worker must define every environment task class")
        if self.snapshot_interval < 1:
            raise ValueError("snapshot_interval must be >= 1")
        for step in range(self.steps):
            if not any(worker.available(step) for worker in self.workers):
                raise ValueError(f"no available worker at step {step}")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_r4_environment(
    *,
    steps: int = 800,
    shift_step: int = 400,
    task_seed: int = 42,
    outcome_seed: int = 4242,
) -> R4Environment:
    if steps < 20:
        raise ValueError("default R4 environment requires at least 20 steps")
    if not 1 <= shift_step < steps - 1:
        raise ValueError("default shift_step must leave work on both sides")
    newcomer_step = min(steps - 1, shift_step + max(1, (steps - shift_step) // 4))
    classes = ("code", "test", "security")

    def rates(code: float, test: float, security: float) -> tuple[tuple[str, float], ...]:
        return (("code", code), ("test", test), ("security", security))

    workers = (
        R4Worker(
            "code-specialist",
            rates(0.88, 0.45, 0.35),
            rates(0.40, 0.83, 0.40),
        ),
        R4Worker(
            "test-specialist",
            rates(0.45, 0.88, 0.40),
            rates(0.84, 0.40, 0.45),
        ),
        R4Worker(
            "security-specialist",
            rates(0.35, 0.40, 0.90),
            rates(0.55, 0.55, 0.55),
        ),
        R4Worker(
            "generalist",
            rates(0.67, 0.67, 0.67),
            rates(0.67, 0.67, 0.67),
            unavailable_windows=((max(1, shift_step - 100), max(2, shift_step - 60)),),
        ),
        R4Worker(
            "newcomer-strong",
            rates(0.72, 0.72, 0.92),
            rates(0.72, 0.72, 0.92),
            available_from=newcomer_step,
            newcomer=True,
        ),
        R4Worker(
            "newcomer-weak",
            rates(0.30, 0.30, 0.30),
            rates(0.30, 0.30, 0.30),
            available_from=newcomer_step,
            newcomer=True,
        ),
    )
    return R4Environment(
        name="specialization-shift-newcomers",
        steps=steps,
        shift_step=shift_step,
        task_classes=classes,
        task_weights=(0.45, 0.35, 0.20),
        workers=workers,
        task_seed=task_seed,
        outcome_seed=outcome_seed,
        snapshot_interval=max(10, steps // 16),
    )


def lockin_r4_environment(
    *,
    steps: int = 500,
    shift_step: int = 100,
    task_seed: int = 11,
    outcome_seed: int = 1111,
) -> R4Environment:
    """Construct a deliberate early-incumbent trap for lock-in experiments."""

    task = (("work", 1.0),)
    workers = (
        R4Worker(
            "early-incumbent",
            task,
            (("work", 0.05),),
        ),
        R4Worker(
            "steady-backup",
            (("work", 0.55),),
            (("work", 0.55),),
        ),
        R4Worker(
            "late-expert",
            (("work", 0.95),),
            (("work", 0.95),),
            available_from=shift_step,
            newcomer=True,
        ),
    )
    return R4Environment(
        name="early-incumbent-lockin-trap",
        steps=steps,
        shift_step=shift_step,
        task_classes=("work",),
        task_weights=(1.0,),
        workers=workers,
        task_seed=task_seed,
        outcome_seed=outcome_seed,
        snapshot_interval=max(10, steps // 20),
    )


def generate_r4_task_trace(environment: R4Environment) -> tuple[str, ...]:
    rng = random.Random(environment.task_seed)
    return tuple(
        rng.choices(
            environment.task_classes,
            weights=environment.task_weights,
            k=1,
        )[0]
        for _ in range(environment.steps)
    )


def r4_trace_digest(environment: R4Environment, task_trace: Sequence[str]) -> str:
    payload = {
        "environment": environment.to_dict(),
        "task_trace": list(task_trace),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _uniform_from_hash(*parts: object) -> float:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")
    return integer / float(2**64)


def verified_outcome(
    environment: R4Environment,
    worker: R4Worker,
    task_class: str,
    step: int,
) -> bool:
    probability = worker.success_probability(task_class, step, environment.shift_step)
    draw = _uniform_from_hash(
        environment.outcome_seed,
        step,
        worker.id,
        task_class,
    )
    return draw < probability


class R4Policy:
    name = "base"

    def before_step(self, step: int) -> None:
        del step

    def select(
        self,
        task_class: str,
        eligible_worker_ids: Sequence[str],
        step: int,
        rng: random.Random,
    ) -> str:
        raise NotImplementedError

    def record_activity(self, task_class: str, worker_id: str, step: int) -> None:
        """Record an unverified activity event.

        The base behavior is intentionally a no-op. Stigmergic routing must not
        reward activity until a separate verified outcome is observed.
        """

        del task_class, worker_id, step

    def record_verified(
        self,
        task_class: str,
        worker_id: str,
        verified_success: bool,
        step: int,
    ) -> None:
        del task_class, worker_id, verified_success, step

    def route_diagnostics(
        self,
        task_class: str,
        eligible_worker_ids: Sequence[str],
        selected_worker_id: str,
    ) -> dict[str, object]:
        del task_class, eligible_worker_ids, selected_worker_id
        return {}

    def snapshot(self) -> dict[str, object] | None:
        return None


class RandomRoutingPolicy(R4Policy):
    name = "random"

    def select(self, task_class, eligible_worker_ids, step, rng):
        del task_class, step
        return rng.choice(list(eligible_worker_ids))


class GreedyRoutingPolicy(R4Policy):
    name = "greedy"

    def __init__(self) -> None:
        self.attempts: dict[tuple[str, str], int] = {}
        self.successes: dict[tuple[str, str], int] = {}

    def _mean(self, task_class: str, worker_id: str) -> float:
        key = (task_class, worker_id)
        attempts = self.attempts.get(key, 0)
        successes = self.successes.get(key, 0)
        return (successes + 1.0) / (attempts + 2.0)

    def select(self, task_class, eligible_worker_ids, step, rng):
        del step, rng
        return max(
            eligible_worker_ids,
            key=lambda worker_id: (self._mean(task_class, worker_id), worker_id),
        )

    def record_verified(self, task_class, worker_id, verified_success, step):
        del step
        key = (task_class, worker_id)
        self.attempts[key] = self.attempts.get(key, 0) + 1
        self.successes[key] = self.successes.get(key, 0) + int(verified_success)

    def route_diagnostics(self, task_class, eligible_worker_ids, selected_worker_id):
        scores = {worker_id: self._mean(task_class, worker_id) for worker_id in eligible_worker_ids}
        return {
            "selected_score": scores[selected_worker_id],
            "score_distribution": scores,
        }


class ThompsonRoutingPolicy(R4Policy):
    name = "thompson"

    def __init__(self) -> None:
        self.attempts: dict[tuple[str, str], int] = {}
        self.successes: dict[tuple[str, str], int] = {}

    def select(self, task_class, eligible_worker_ids, step, rng):
        del step
        samples = {}
        for worker_id in eligible_worker_ids:
            key = (task_class, worker_id)
            attempts = self.attempts.get(key, 0)
            successes = self.successes.get(key, 0)
            samples[worker_id] = rng.betavariate(
                successes + 1,
                attempts - successes + 1,
            )
        return max(samples, key=lambda worker_id: (samples[worker_id], worker_id))

    def record_verified(self, task_class, worker_id, verified_success, step):
        del step
        key = (task_class, worker_id)
        self.attempts[key] = self.attempts.get(key, 0) + 1
        self.successes[key] = self.successes.get(key, 0) + int(verified_success)

    def route_diagnostics(self, task_class, eligible_worker_ids, selected_worker_id):
        posterior_means = {}
        for worker_id in eligible_worker_ids:
            key = (task_class, worker_id)
            attempts = self.attempts.get(key, 0)
            successes = self.successes.get(key, 0)
            posterior_means[worker_id] = (successes + 1.0) / (attempts + 2.0)
        return {
            "selected_posterior_mean": posterior_means[selected_worker_id],
            "posterior_means": posterior_means,
        }


class StigmergicRoutingPolicy(R4Policy):
    """Verified-outcome pheromone routing with optional evaporation/exploration."""

    def __init__(
        self,
        *,
        name: str,
        evaporation_rate: float,
        exploration_floor: float,
        alpha: float = 1.5,
        initial_pheromone: float = 1.0,
        success_deposit: float = 1.0,
        failure_penalty: float = 0.10,
        newcomer_bonus: float = 1.0,
        min_pheromone: float = 1e-6,
    ) -> None:
        if not 0.0 <= evaporation_rate < 1.0:
            raise ValueError("evaporation_rate must be in [0, 1)")
        if not 0.0 <= exploration_floor <= 1.0:
            raise ValueError("exploration_floor must be in [0, 1]")
        if alpha <= 0.0:
            raise ValueError("alpha must be > 0")
        if initial_pheromone <= 0.0 or min_pheromone <= 0.0:
            raise ValueError("pheromone values must be > 0")
        if success_deposit < 0.0 or failure_penalty < 0.0:
            raise ValueError("deposit/penalty must be non-negative")
        if newcomer_bonus < 1.0:
            raise ValueError("newcomer_bonus must be >= 1")
        self.name = name
        self.evaporation_rate = evaporation_rate
        self.exploration_floor = exploration_floor
        self.alpha = alpha
        self.initial_pheromone = initial_pheromone
        self.success_deposit = success_deposit
        self.failure_penalty = failure_penalty
        self.newcomer_bonus = newcomer_bonus
        self.min_pheromone = min_pheromone
        self.pheromone: dict[tuple[str, str], float] = {}
        self.attempts: dict[tuple[str, str], int] = {}
        self.verified_success_deposit_events = 0
        self.verified_success_deposit_total = 0.0
        self.verified_failure_penalty_events = 0
        self.verified_failure_penalty_total = 0.0
        self.unverified_activity_events = 0
        self.unverified_activity_pheromone_increase = 0.0

    def _ensure(self, task_class: str, worker_id: str) -> tuple[str, str]:
        key = (task_class, worker_id)
        self.pheromone.setdefault(key, self.initial_pheromone)
        self.attempts.setdefault(key, 0)
        return key

    def before_step(self, step: int) -> None:
        del step
        if self.evaporation_rate == 0.0:
            return
        retain = 1.0 - self.evaporation_rate
        for key in list(self.pheromone):
            self.pheromone[key] = max(
                self.min_pheromone,
                self.pheromone[key] * retain,
            )

    def _weights(
        self,
        task_class: str,
        eligible_worker_ids: Sequence[str],
    ) -> dict[str, float]:
        weights = {}
        for worker_id in eligible_worker_ids:
            key = self._ensure(task_class, worker_id)
            novelty_multiplier = self.newcomer_bonus if self.attempts[key] == 0 else 1.0
            weights[worker_id] = (
                max(self.min_pheromone, self.pheromone[key]) ** self.alpha
            ) * novelty_multiplier
        return weights

    def select(self, task_class, eligible_worker_ids, step, rng):
        del step
        if rng.random() < self.exploration_floor:
            return rng.choice(list(eligible_worker_ids))
        weights = self._weights(task_class, eligible_worker_ids)
        return rng.choices(
            list(eligible_worker_ids),
            weights=[weights[worker_id] for worker_id in eligible_worker_ids],
            k=1,
        )[0]

    def record_activity(self, task_class, worker_id, step):
        del step
        key = self._ensure(task_class, worker_id)
        before = self.pheromone[key]
        # Deliberately do nothing to pheromone. Activity is not evidence.
        self.unverified_activity_events += 1
        after = self.pheromone[key]
        self.unverified_activity_pheromone_increase += max(0.0, after - before)

    def record_verified(self, task_class, worker_id, verified_success, step):
        del step
        key = self._ensure(task_class, worker_id)
        self.attempts[key] += 1
        if verified_success:
            self.pheromone[key] += self.success_deposit
            self.verified_success_deposit_events += 1
            self.verified_success_deposit_total += self.success_deposit
        else:
            before = self.pheromone[key]
            self.pheromone[key] = max(
                self.min_pheromone,
                self.pheromone[key] - self.failure_penalty,
            )
            penalty = before - self.pheromone[key]
            if penalty > 0.0:
                self.verified_failure_penalty_events += 1
                self.verified_failure_penalty_total += penalty

    def route_diagnostics(self, task_class, eligible_worker_ids, selected_worker_id):
        weights = self._weights(task_class, eligible_worker_ids)
        total = sum(weights.values())
        probabilities = {
            worker_id: (weight / total if total > 0.0 else 0.0)
            for worker_id, weight in weights.items()
        }
        entropy = _normalized_entropy(list(probabilities.values()))
        selected_key = self._ensure(task_class, selected_worker_id)
        return {
            "selected_pheromone": self.pheromone[selected_key],
            "selected_attempts": self.attempts[selected_key],
            "routing_probabilities": probabilities,
            "routing_entropy": entropy,
            "evaporation_rate": self.evaporation_rate,
            "exploration_floor": self.exploration_floor,
        }

    def snapshot(self) -> dict[str, object]:
        nested: dict[str, dict[str, float]] = {}
        for (task_class, worker_id), value in sorted(self.pheromone.items()):
            nested.setdefault(task_class, {})[worker_id] = value
        return {
            "pheromone": nested,
            "verified_success_deposit_events": self.verified_success_deposit_events,
            "verified_success_deposit_total": self.verified_success_deposit_total,
            "verified_failure_penalty_events": self.verified_failure_penalty_events,
            "verified_failure_penalty_total": self.verified_failure_penalty_total,
            "unverified_activity_events": self.unverified_activity_events,
            "unverified_activity_pheromone_increase": self.unverified_activity_pheromone_increase,
        }


def make_r4_policy(name: str) -> R4Policy:
    if name == "random":
        return RandomRoutingPolicy()
    if name == "greedy":
        return GreedyRoutingPolicy()
    if name == "thompson":
        return ThompsonRoutingPolicy()
    if name == "stigmergy-no-evap":
        return StigmergicRoutingPolicy(
            name=name,
            evaporation_rate=0.0,
            exploration_floor=0.0,
            alpha=1.5,
            failure_penalty=0.10,
        )
    if name == "stigmergy-evap":
        return StigmergicRoutingPolicy(
            name=name,
            evaporation_rate=0.02,
            exploration_floor=0.0,
            alpha=1.5,
            failure_penalty=0.10,
        )
    if name == "stigmergy-evap-explore":
        return StigmergicRoutingPolicy(
            name=name,
            evaporation_rate=0.02,
            exploration_floor=0.08,
            alpha=1.5,
            failure_penalty=0.10,
            newcomer_bonus=2.0,
        )
    raise ValueError(f"unknown R4 policy {name!r}; choose one of {', '.join(R4_POLICIES)}")


def _normalized_entropy(probabilities: Sequence[float]) -> float:
    positive = [probability for probability in probabilities if probability > 0.0]
    if len(positive) <= 1:
        return 0.0
    entropy = -sum(probability * math.log(probability) for probability in positive)
    return entropy / math.log(len(positive))


def _assignment_entropy(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probabilities = [count / total for count in counts.values() if count > 0]
    return _normalized_entropy(probabilities)


def _longest_worker_streak(events: Sequence[dict[str, object]]) -> int:
    longest = 0
    current = 0
    previous = None
    for event in events:
        worker_id = event["selected_worker"]
        if worker_id == previous:
            current += 1
        else:
            current = 1
            previous = worker_id
        longest = max(longest, current)
    return longest


def _longest_failure_lockin(events: Sequence[dict[str, object]]) -> int:
    longest = 0
    current = 0
    previous_worker = None
    for event in events:
        worker_id = event["selected_worker"]
        if not event["verified_success"]:
            if worker_id == previous_worker:
                current += 1
            else:
                current = 1
            previous_worker = worker_id
            longest = max(longest, current)
        else:
            current = 0
            previous_worker = None
    return longest


def _recovery_time(
    events: Sequence[dict[str, object]],
    shift_step: int,
    *,
    window: int = 25,
    threshold: float = 0.90,
) -> int | None:
    post = [event for event in events if int(event["step"]) >= shift_step]
    if len(post) < window:
        return None
    ratios = [
        float(event["selected_success_probability"])
        / max(1e-12, float(event["oracle_success_probability"]))
        for event in post
    ]
    for index in range(0, len(ratios) - window + 1):
        if mean(ratios[index : index + window]) >= threshold:
            return int(post[index]["step"]) - shift_step
    return None


def _pre_shift_best_workers(environment: R4Environment) -> dict[str, str]:
    reference_step = max(0, environment.shift_step - 1)
    output = {}
    for task_class in environment.task_classes:
        eligible = [
            worker
            for worker in environment.workers
            if worker.available(reference_step)
        ]
        output[task_class] = max(
            eligible,
            key=lambda worker: (
                worker.success_probability(task_class, reference_step, environment.shift_step),
                worker.id,
            ),
        ).id
    return output


def _post_shift_best_workers(environment: R4Environment) -> dict[str, str]:
    reference_step = min(environment.steps - 1, environment.shift_step + 1)
    output = {}
    for task_class in environment.task_classes:
        eligible = [
            worker
            for worker in environment.workers
            if worker.available(reference_step)
        ]
        output[task_class] = max(
            eligible,
            key=lambda worker: (
                worker.success_probability(task_class, reference_step, environment.shift_step),
                worker.id,
            ),
        ).id
    return output


def _stale_route_fraction(
    environment: R4Environment,
    events: Sequence[dict[str, object]],
    *,
    window: int = 100,
) -> float | None:
    before = _pre_shift_best_workers(environment)
    after = _post_shift_best_workers(environment)
    changed = {task for task in environment.task_classes if before[task] != after[task]}
    if not changed:
        return None
    end = min(environment.steps, environment.shift_step + window)
    relevant = [
        event
        for event in events
        if environment.shift_step <= int(event["step"]) < end
        and event["task_class"] in changed
    ]
    if not relevant:
        return None
    stale = sum(
        int(event["selected_worker"] == before[str(event["task_class"])])
        for event in relevant
    )
    return stale / len(relevant)


def run_r4_policy(
    environment: R4Environment,
    policy_name: str,
    *,
    policy_seed: int = 1337,
    include_events: bool = True,
) -> dict[str, object]:
    policy = make_r4_policy(policy_name)
    rng = random.Random(policy_seed)
    task_trace = generate_r4_task_trace(environment)
    digest = r4_trace_digest(environment, task_trace)
    worker_by_id = {worker.id: worker for worker in environment.workers}
    newcomer_ids = {worker.id for worker in environment.workers if worker.newcomer}
    assignment_counts = {worker.id: 0 for worker in environment.workers}
    newcomer_first_assignment: dict[str, int | None] = {
        worker_id: None for worker_id in newcomer_ids
    }
    events: list[dict[str, object]] = []
    pheromone_snapshots: list[dict[str, object]] = []
    verified_successes = 0
    expected_regret = 0.0
    optimal_assignments = 0
    pre_shift_successes = 0
    post_shift_successes = 0
    pre_shift_count = 0
    post_shift_count = 0

    snapshot_steps = {
        0,
        environment.shift_step,
        environment.steps - 1,
        *(
            worker.available_from
            for worker in environment.workers
            if worker.available_from > 0
        ),
    }

    for step, task_class in enumerate(task_trace):
        policy.before_step(step)
        eligible = [worker for worker in environment.workers if worker.available(step)]
        eligible_ids = [worker.id for worker in eligible]
        selected_id = policy.select(task_class, eligible_ids, step, rng)
        if selected_id not in eligible_ids:
            raise ValueError("policy selected an ineligible worker")
        selected_worker = worker_by_id[selected_id]
        probabilities = {
            worker.id: worker.success_probability(task_class, step, environment.shift_step)
            for worker in eligible
        }
        selected_probability = probabilities[selected_id]
        oracle_probability = max(probabilities.values())
        expected_regret += oracle_probability - selected_probability
        optimal_assignments += int(abs(selected_probability - oracle_probability) < 1e-12)

        route_before = policy.route_diagnostics(task_class, eligible_ids, selected_id)
        # Simulate a raw activity event before verification. Stigmergic policy
        # explicitly ignores it, which makes the invariant auditable in traces.
        policy.record_activity(task_class, selected_id, step)
        success = verified_outcome(environment, selected_worker, task_class, step)
        policy.record_verified(task_class, selected_id, success, step)
        route_after = policy.route_diagnostics(task_class, eligible_ids, selected_id)

        verified_successes += int(success)
        assignment_counts[selected_id] += 1
        if selected_id in newcomer_ids and newcomer_first_assignment[selected_id] is None:
            newcomer_first_assignment[selected_id] = step
        if step < environment.shift_step:
            pre_shift_count += 1
            pre_shift_successes += int(success)
        else:
            post_shift_count += 1
            post_shift_successes += int(success)

        event = {
            "step": step,
            "task_class": task_class,
            "selected_worker": selected_id,
            "verified_success": success,
            "selected_success_probability": selected_probability,
            "oracle_success_probability": oracle_probability,
            "expected_regret": oracle_probability - selected_probability,
            "eligible_worker_count": len(eligible_ids),
            "selected_is_newcomer": selected_id in newcomer_ids,
            "route_before_verification": route_before,
            "route_after_verification": route_after,
        }
        events.append(event)

        if (
            step in snapshot_steps
            or step % environment.snapshot_interval == 0
        ):
            snapshot = policy.snapshot()
            if snapshot is not None:
                pheromone_snapshots.append(
                    {
                        "step": step,
                        "task_class": task_class,
                        "state": snapshot,
                    }
                )

    newcomer_assignments = sum(assignment_counts[worker_id] for worker_id in newcomer_ids)
    newcomer_available_opportunities = sum(
        sum(int(worker.available(step)) for worker in environment.workers if worker.newcomer)
        for step in range(environment.steps)
    )
    final_snapshot = policy.snapshot()

    metrics = {
        "verified_successes": verified_successes,
        "verified_success_rate": verified_successes / environment.steps,
        "pre_shift_verified_success_rate": (
            pre_shift_successes / pre_shift_count if pre_shift_count else None
        ),
        "post_shift_verified_success_rate": (
            post_shift_successes / post_shift_count if post_shift_count else None
        ),
        "cumulative_expected_regret": expected_regret,
        "mean_expected_regret": expected_regret / environment.steps,
        "optimal_assignment_rate": optimal_assignments / environment.steps,
        "adaptation_recovery_steps": _recovery_time(events, environment.shift_step),
        "stale_route_fraction_first_100_post_shift": _stale_route_fraction(
            environment, events
        ),
        "assignment_entropy": _assignment_entropy(assignment_counts),
        "assignment_hhi": sum(
            (count / environment.steps) ** 2 for count in assignment_counts.values()
        ),
        "longest_same_worker_streak": _longest_worker_streak(events),
        "longest_failed_same_worker_lockin": _longest_failure_lockin(events),
        "assignment_counts": assignment_counts,
        "newcomer_first_assignment_step": newcomer_first_assignment,
        "newcomer_assignment_share": newcomer_assignments / environment.steps,
        "newcomer_assignments": newcomer_assignments,
        "newcomer_available_opportunities": newcomer_available_opportunities,
        "verified_success_deposit_events": (
            final_snapshot["verified_success_deposit_events"]
            if final_snapshot is not None
            else None
        ),
        "verified_success_deposit_total": (
            final_snapshot["verified_success_deposit_total"]
            if final_snapshot is not None
            else None
        ),
        "verified_failure_penalty_events": (
            final_snapshot["verified_failure_penalty_events"]
            if final_snapshot is not None
            else None
        ),
        "unverified_activity_events": (
            final_snapshot["unverified_activity_events"]
            if final_snapshot is not None
            else None
        ),
        "unverified_activity_pheromone_increase": (
            final_snapshot["unverified_activity_pheromone_increase"]
            if final_snapshot is not None
            else None
        ),
    }

    return {
        "schema_version": 1,
        "experiment": "R4-verified-stigmergic-routing",
        "environment": environment.to_dict(),
        "trace_digest": digest,
        "policy": policy_name,
        "policy_seed": policy_seed,
        "metrics": metrics,
        "pheromone_snapshots": pheromone_snapshots,
        "events": events if include_events else [],
        "integrity": {
            "activity_can_increase_pheromone": False,
            "pheromone_updates_require_verified_outcome": True,
            "routing_weight_can_accept_unverified_result": False,
            "governance_authority_from_pheromone": False,
        },
    }


def run_r4_benchmark(
    environment: R4Environment,
    *,
    policy_seed: int = 1337,
    policies: Sequence[str] = R4_POLICIES,
    include_events: bool = True,
) -> dict[str, object]:
    results = {
        policy_name: run_r4_policy(
            environment,
            policy_name,
            policy_seed=policy_seed,
            include_events=include_events,
        )
        for policy_name in policies
    }
    digests = {result["trace_digest"] for result in results.values()}
    if len(digests) != 1:
        raise AssertionError("all R4 policies must replay the same task/environment trace")
    return {
        "schema_version": 1,
        "experiment": "R4-verified-stigmergic-routing",
        "trace_digest": next(iter(digests)),
        "environment": environment.to_dict(),
        "policy_seed": policy_seed,
        "policies": results,
        "comparison_guardrail": (
            "Pheromone affects routing only. Synthetic verified outcomes remain independent "
            "of routing weight, and unverified activity cannot create positive pheromone."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r4",
        description="Compare verified-outcome stigmergic routing with random/greedy/Thompson baselines.",
    )
    parser.add_argument("--scenario", choices=("default", "lockin"), default="default")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--shift-step", type=int)
    parser.add_argument("--task-seed", type=int, default=42)
    parser.add_argument("--outcome-seed", type=int, default=4242)
    parser.add_argument("--policy-seed", type=int, default=1337)
    parser.add_argument("--no-events", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.scenario == "default":
        steps = args.steps if args.steps is not None else 800
        shift = args.shift_step if args.shift_step is not None else steps // 2
        environment = default_r4_environment(
            steps=steps,
            shift_step=shift,
            task_seed=args.task_seed,
            outcome_seed=args.outcome_seed,
        )
    else:
        steps = args.steps if args.steps is not None else 500
        shift = args.shift_step if args.shift_step is not None else max(1, steps // 5)
        environment = lockin_r4_environment(
            steps=steps,
            shift_step=shift,
            task_seed=args.task_seed,
            outcome_seed=args.outcome_seed,
        )

    result = run_r4_benchmark(
        environment,
        policy_seed=args.policy_seed,
        include_events=not args.no_events,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
