from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Iterable, Sequence

from .policies import power_of_d_least_loaded


POLICIES = (
    "random",
    "power-of-two",
    "power-of-three",
    "capability-power-of-two",
    "global-least-loaded-oracle",
)


@dataclass(frozen=True)
class TraceSpec:
    """Compact replayable workload/churn specification.

    Workers, tasks, and availability are derived deterministically from this
    object, so very large traces do not need an O(workers * steps) matrix.
    """

    schema_version: int = 1
    seed: int = 42
    worker_count: int = 100
    steps: int = 100
    base_arrivals_per_step: int = 50
    burst_probability: float = 0.10
    burst_multiplier: int = 4
    churn_probability: float = 0.05

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported trace schema_version")
        if self.worker_count < 1:
            raise ValueError("worker_count must be >= 1")
        if self.steps < 1:
            raise ValueError("steps must be >= 1")
        if self.base_arrivals_per_step < 0:
            raise ValueError("base_arrivals_per_step must be >= 0")
        if self.burst_multiplier < 1:
            raise ValueError("burst_multiplier must be >= 1")
        if not 0.0 <= self.burst_probability <= 1.0:
            raise ValueError("burst_probability must be in [0, 1]")
        if not 0.0 <= self.churn_probability <= 1.0:
            raise ValueError("churn_probability must be in [0, 1]")


@dataclass(frozen=True)
class SchedulerWorker:
    name: str
    capacity: int
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class SchedulingTask:
    task_id: str
    arrival_step: int
    work: int
    capability: str


@dataclass
class QueuedTask:
    task: SchedulingTask
    remaining: int


@dataclass(frozen=True)
class SimulationConfig:
    observation_lag_steps: int = 0
    drain_steps: int = 50

    def validate(self) -> None:
        if self.observation_lag_steps < 0:
            raise ValueError("observation_lag_steps must be >= 0")
        if self.drain_steps < 0:
            raise ValueError("drain_steps must be >= 0")


def _stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def _stable_uniform(*parts: object) -> float:
    return _stable_seed(*parts) / float(0xFFFFFFFFFFFFFFFF)


def trace_digest(spec: TraceSpec) -> str:
    payload = json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_workers(spec: TraceSpec) -> list[SchedulerWorker]:
    spec.validate()
    rng = random.Random(_stable_seed(spec.seed, "workers"))
    workers = []
    for index in range(spec.worker_count):
        draw = rng.random()
        if draw < 0.45:
            capabilities = ("cpu",)
        elif draw < 0.70:
            capabilities = ("gpu",)
        else:
            capabilities = ("cpu", "gpu")
        workers.append(
            SchedulerWorker(
                name=f"worker-{index + 1}",
                capacity=rng.randint(1, 4),
                capabilities=capabilities,
            )
        )
    return workers


def build_tasks(spec: TraceSpec) -> list[SchedulingTask]:
    spec.validate()
    rng = random.Random(_stable_seed(spec.seed, "tasks"))
    tasks = []
    ordinal = 0
    for step in range(spec.steps):
        arrivals = spec.base_arrivals_per_step
        if rng.random() < spec.burst_probability:
            arrivals *= spec.burst_multiplier
        for _ in range(arrivals):
            ordinal += 1
            tasks.append(
                SchedulingTask(
                    task_id=f"task-{ordinal}",
                    arrival_step=step,
                    work=rng.choice((1, 1, 2, 2, 3, 5)),
                    capability="cpu" if rng.random() < 0.70 else "gpu",
                )
            )
    return tasks


def worker_available(spec: TraceSpec, step: int, worker_index: int) -> bool:
    return _stable_uniform(spec.seed, "availability", step, worker_index) >= spec.churn_probability


def _loads(queues: Sequence[deque[QueuedTask]]) -> list[float]:
    return [float(sum(item.remaining for item in queue)) for queue in queues]


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return float(ordered[lo])
    weight = position - lo
    return float(ordered[lo] * (1.0 - weight) + ordered[hi] * weight)


def _jain_fairness(values: Sequence[float]) -> float:
    if not values:
        return 1.0
    total = sum(values)
    squared = sum(value * value for value in values)
    if squared == 0.0:
        return 1.0
    return (total * total) / (len(values) * squared)


def _choose_worker(
    policy: str,
    task: SchedulingTask,
    workers: Sequence[SchedulerWorker],
    observed_loads: Sequence[float],
    current_loads: Sequence[float],
    available_now: Sequence[bool],
    rng: random.Random,
) -> tuple[int | None, int]:
    """Return (worker index, dynamic metadata-read proxy)."""

    if policy == "random":
        return rng.randrange(len(workers)), 0

    if policy in {"power-of-two", "power-of-three"}:
        d = 2 if policy == "power-of-two" else 3
        return power_of_d_least_loaded(observed_loads, rng, d=d), min(d, len(workers))

    if policy == "capability-power-of-two":
        candidates = [
            index for index, worker in enumerate(workers)
            if task.capability in worker.capabilities
        ]
        if not candidates:
            return None, 0
        sampled = rng.sample(candidates, k=min(2, len(candidates)))
        return min(sampled, key=lambda index: (observed_loads[index], index)), len(sampled)

    if policy == "global-least-loaded-oracle":
        candidates = [
            index for index, worker in enumerate(workers)
            if available_now[index] and task.capability in worker.capabilities
        ]
        if not candidates:
            return None, len(workers)
        selected = min(candidates, key=lambda index: (current_loads[index], index))
        return selected, len(workers)

    raise ValueError(f"unknown policy {policy!r}; choose one of {', '.join(POLICIES)}")


def run_scheduling_simulation(
    spec: TraceSpec,
    policy: str,
    config: SimulationConfig | None = None,
) -> dict[str, object]:
    spec.validate()
    config = config or SimulationConfig()
    config.validate()
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; choose one of {', '.join(POLICIES)}")

    workers = build_workers(spec)
    tasks = build_tasks(spec)
    arrivals: dict[int, list[SchedulingTask]] = {}
    for task in tasks:
        arrivals.setdefault(task.arrival_step, []).append(task)

    queues: list[deque[QueuedTask]] = [deque() for _ in workers]
    pending: deque[SchedulingTask] = deque()
    load_snapshots: list[list[float]] = [[0.0 for _ in workers]]
    rng = random.Random(_stable_seed(spec.seed, "routing", policy, config.observation_lag_steps))

    attempts_by_task = {task.task_id: 0 for task in tasks}
    failed_by_task: set[str] = set()
    completed_after_failure: set[str] = set()
    completed_by_worker = [0 for _ in workers]
    busy_units = [0 for _ in workers]
    available_capacity = [0 for _ in workers]
    waiting_times: list[float] = []
    queue_depth_samples: list[float] = []

    metadata_reads = 0
    failed_assignments = 0
    unreachable_assignments = 0
    capability_mismatches = 0
    no_candidate_assignments = 0

    for step in range(spec.steps + config.drain_steps):
        if step < spec.steps:
            pending.extend(arrivals.get(step, ()))

        current_loads = _loads(queues)
        if config.observation_lag_steps == 0:
            # Live reference: assignments earlier in the same burst immediately
            # change the load seen by later assignments.
            observed_loads = current_loads
        else:
            lag_index = max(0, len(load_snapshots) - 1 - config.observation_lag_steps)
            observed_loads = load_snapshots[lag_index]
        available_now = [worker_available(spec, step, index) for index in range(len(workers))]

        for _ in range(len(pending)):
            task = pending.popleft()
            attempts_by_task[task.task_id] += 1
            selected, reads = _choose_worker(
                policy,
                task,
                workers,
                observed_loads,
                current_loads,
                available_now,
                rng,
            )
            metadata_reads += reads

            if selected is None:
                failed_assignments += 1
                no_candidate_assignments += 1
                failed_by_task.add(task.task_id)
                pending.append(task)
                continue
            if not available_now[selected]:
                failed_assignments += 1
                unreachable_assignments += 1
                failed_by_task.add(task.task_id)
                pending.append(task)
                continue
            if task.capability not in workers[selected].capabilities:
                failed_assignments += 1
                capability_mismatches += 1
                failed_by_task.add(task.task_id)
                pending.append(task)
                continue

            queues[selected].append(QueuedTask(task=task, remaining=task.work))
            current_loads[selected] += task.work

        for worker_index, worker in enumerate(workers):
            if not available_now[worker_index]:
                continue
            capacity = worker.capacity
            available_capacity[worker_index] += capacity
            while capacity > 0 and queues[worker_index]:
                item = queues[worker_index][0]
                consumed = min(capacity, item.remaining)
                item.remaining -= consumed
                capacity -= consumed
                busy_units[worker_index] += consumed
                if item.remaining == 0:
                    queues[worker_index].popleft()
                    completed_by_worker[worker_index] += 1
                    waiting_times.append(float(step + 1 - item.task.arrival_step))
                    if item.task.task_id in failed_by_task:
                        completed_after_failure.add(item.task.task_id)

        queue_depth_samples.extend(float(len(queue)) for queue in queues)
        load_snapshots.append(_loads(queues))

    completed = sum(completed_by_worker)
    unfinished = len(pending) + sum(len(queue) for queue in queues)
    total_tasks = len(tasks)
    retry_tasks = len(failed_by_task)
    utilization_denominator = sum(available_capacity)

    return {
        "schema_version": 1,
        "experiment": "power-of-d-scheduling-under-churn",
        "policy": policy,
        "trace": {**asdict(spec), "digest": trace_digest(spec)},
        "simulation": asdict(config),
        "metrics": {
            "task_count": total_tasks,
            "completed_tasks": completed,
            "unfinished_tasks": unfinished,
            "completion_rate": completed / total_tasks if total_tasks else 1.0,
            "failed_assignments": failed_assignments,
            "unreachable_assignments": unreachable_assignments,
            "capability_mismatches": capability_mismatches,
            "no_candidate_assignments": no_candidate_assignments,
            "tasks_requiring_retry": retry_tasks,
            "retry_recovery_rate": len(completed_after_failure) / retry_tasks if retry_tasks else 1.0,
            "mean_assignment_attempts_per_task": mean(attempts_by_task.values()) if attempts_by_task else 0.0,
            "max_queue_depth": max(queue_depth_samples, default=0.0),
            "p95_queue_depth": _percentile(queue_depth_samples, 0.95),
            "mean_task_system_time_steps": mean(waiting_times) if waiting_times else 0.0,
            "p95_task_system_time_steps": _percentile(waiting_times, 0.95),
            "utilization": sum(busy_units) / utilization_denominator if utilization_denominator else 0.0,
            "jain_completion_fairness": _jain_fairness(completed_by_worker),
            "metadata_reads": metadata_reads,
            "metadata_reads_per_task": metadata_reads / total_tasks if total_tasks else 0.0,
            "completed_by_worker": {
                workers[index].name: count for index, count in enumerate(completed_by_worker)
            },
        },
        "coordination_note": (
            "metadata_reads is a relative dynamic-state lookup proxy, not measured network bytes. "
            "The global oracle pays O(worker_count) reads per assignment; power-of-d pays O(d)."
        ),
        "scientific_guardrail": (
            "This synthetic benchmark compares scheduling regimes under one explicit model. "
            "It does not establish production-scale superiority without real workload evidence."
        ),
    }


def run_policy_comparison(
    spec: TraceSpec,
    policies: Iterable[str] = POLICIES,
    config: SimulationConfig | None = None,
) -> dict[str, object]:
    selected = list(policies)
    return {
        "schema_version": 1,
        "experiment": "power-of-d-scheduling-under-churn-comparison",
        "trace": {**asdict(spec), "digest": trace_digest(spec)},
        "policies": selected,
        "results": [run_scheduling_simulation(spec, policy, config) for policy in selected],
    }


def save_trace_spec(path: Path, spec: TraceSpec) -> None:
    spec.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(spec), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_trace_spec(path: Path) -> TraceSpec:
    spec = TraceSpec(**json.loads(path.read_text(encoding="utf-8")))
    spec.validate()
    return spec


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.scheduling",
        description="Replayable power-of-d scheduling benchmark under heterogeneous churn.",
    )
    parser.add_argument("--policy", choices=("all",) + POLICIES, default="all")
    parser.add_argument("--workers", type=int, default=100)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--arrivals", type=int, help="base arrivals per step; default scales with workers")
    parser.add_argument("--burst-probability", type=float, default=0.10)
    parser.add_argument("--burst-multiplier", type=int, default=4)
    parser.add_argument("--churn-probability", type=float, default=0.05)
    parser.add_argument("--observation-lag", type=int, default=0)
    parser.add_argument("--drain-steps", type=int, default=50)
    parser.add_argument("--trace-input", type=Path)
    parser.add_argument("--trace-output", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.trace_input:
        spec = load_trace_spec(args.trace_input)
    else:
        spec = TraceSpec(
            seed=args.seed,
            worker_count=args.workers,
            steps=args.steps,
            base_arrivals_per_step=(
                args.arrivals if args.arrivals is not None else max(1, args.workers // 2)
            ),
            burst_probability=args.burst_probability,
            burst_multiplier=args.burst_multiplier,
            churn_probability=args.churn_probability,
        )
        spec.validate()

    if args.trace_output:
        save_trace_spec(args.trace_output, spec)

    config = SimulationConfig(
        observation_lag_steps=args.observation_lag,
        drain_steps=args.drain_steps,
    )
    policies = POLICIES if args.policy == "all" else (args.policy,)
    result = run_policy_comparison(spec, policies, config)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
