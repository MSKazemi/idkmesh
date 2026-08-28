from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Sequence


R2_POLICIES = (
    "one-random",
    "power-two",
    "power-three",
    "capability-power-two",
    "global-least-loaded",
)


@dataclass(frozen=True)
class R2Worker:
    id: str
    capacity: int
    capabilities: tuple[str, ...]
    zone: str

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("worker capacity must be >= 1")
        if not self.capabilities:
            raise ValueError("worker capabilities must not be empty")


@dataclass(frozen=True)
class R2Task:
    id: str
    arrival_tick: int
    work_units: int
    required_capability: str
    preferred_zone: str

    def __post_init__(self) -> None:
        if self.arrival_tick < 0:
            raise ValueError("task arrival_tick must be >= 0")
        if self.work_units < 1:
            raise ValueError("task work_units must be >= 1")
        if not self.required_capability:
            raise ValueError("task required_capability must not be empty")


@dataclass(frozen=True)
class R2Outage:
    worker_index: int
    start_tick: int
    end_tick: int

    def __post_init__(self) -> None:
        if self.worker_index < 0:
            raise ValueError("outage worker_index must be >= 0")
        if self.start_tick < 0:
            raise ValueError("outage start_tick must be >= 0")
        if self.end_tick <= self.start_tick:
            raise ValueError("outage end_tick must be greater than start_tick")


@dataclass(frozen=True)
class R2Trace:
    seed: int
    ticks: int
    workers: tuple[R2Worker, ...]
    tasks: tuple[R2Task, ...]
    outages: tuple[R2Outage, ...]

    def __post_init__(self) -> None:
        if self.ticks < 1:
            raise ValueError("trace ticks must be >= 1")
        if not self.workers:
            raise ValueError("trace workers must not be empty")
        _validate_trace(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "seed": self.seed,
            "ticks": self.ticks,
            "workers": [asdict(worker) for worker in self.workers],
            "tasks": [asdict(task) for task in self.tasks],
            "outages": [asdict(outage) for outage in self.outages],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "R2Trace":
        if value.get("schema_version") != 1:
            raise ValueError("R2 trace schema_version must be 1")
        workers_raw = value.get("workers")
        tasks_raw = value.get("tasks")
        outages_raw = value.get("outages")
        if not isinstance(workers_raw, list):
            raise ValueError("trace workers must be an array")
        if not isinstance(tasks_raw, list):
            raise ValueError("trace tasks must be an array")
        if not isinstance(outages_raw, list):
            raise ValueError("trace outages must be an array")

        workers = []
        for raw in workers_raw:
            if not isinstance(raw, dict):
                raise ValueError("every worker must be an object")
            capabilities = raw.get("capabilities")
            if not isinstance(capabilities, (list, tuple)):
                raise ValueError("worker capabilities must be an array")
            workers.append(
                R2Worker(
                    id=str(raw["id"]),
                    capacity=int(raw["capacity"]),
                    capabilities=tuple(str(item) for item in capabilities),
                    zone=str(raw["zone"]),
                )
            )

        tasks = []
        for raw in tasks_raw:
            if not isinstance(raw, dict):
                raise ValueError("every task must be an object")
            tasks.append(
                R2Task(
                    id=str(raw["id"]),
                    arrival_tick=int(raw["arrival_tick"]),
                    work_units=int(raw["work_units"]),
                    required_capability=str(raw["required_capability"]),
                    preferred_zone=str(raw["preferred_zone"]),
                )
            )

        outages = []
        for raw in outages_raw:
            if not isinstance(raw, dict):
                raise ValueError("every outage must be an object")
            outages.append(
                R2Outage(
                    worker_index=int(raw["worker_index"]),
                    start_tick=int(raw["start_tick"]),
                    end_tick=int(raw["end_tick"]),
                )
            )

        return cls(
            seed=int(value["seed"]),
            ticks=int(value["ticks"]),
            workers=tuple(workers),
            tasks=tuple(tasks),
            outages=tuple(outages),
        )


@dataclass(frozen=True)
class R2TraceConfig:
    worker_count: int = 100
    ticks: int = 200
    base_arrivals_per_tick: int = 4
    burst_probability: float = 0.10
    burst_multiplier: int = 5
    max_work_units: int = 8
    churn_fraction: float = 0.10
    outage_min_ticks: int = 3
    outage_max_ticks: int = 20
    seed: int = 42

    def __post_init__(self) -> None:
        if self.worker_count < 1:
            raise ValueError("worker_count must be >= 1")
        if self.ticks < 1:
            raise ValueError("ticks must be >= 1")
        if self.base_arrivals_per_tick < 0:
            raise ValueError("base_arrivals_per_tick must be >= 0")
        if not 0.0 <= self.burst_probability <= 1.0:
            raise ValueError("burst_probability must be in [0, 1]")
        if self.burst_multiplier < 1:
            raise ValueError("burst_multiplier must be >= 1")
        if self.max_work_units < 1:
            raise ValueError("max_work_units must be >= 1")
        if not 0.0 <= self.churn_fraction <= 1.0:
            raise ValueError("churn_fraction must be in [0, 1]")
        if self.outage_min_ticks < 1:
            raise ValueError("outage_min_ticks must be >= 1")
        if self.outage_max_ticks < self.outage_min_ticks:
            raise ValueError("outage_max_ticks must be >= outage_min_ticks")


@dataclass(frozen=True)
class R2RunConfig:
    availability_observation_lag: int = 2
    load_observation_lag: int = 2
    drain_ticks: int = 200
    policy_seed: int = 1337
    restart_work_on_churn: bool = True

    def __post_init__(self) -> None:
        if self.availability_observation_lag < 0:
            raise ValueError("availability_observation_lag must be >= 0")
        if self.load_observation_lag < 0:
            raise ValueError("load_observation_lag must be >= 0")
        if self.drain_ticks < 0:
            raise ValueError("drain_ticks must be >= 0")


@dataclass
class _TaskState:
    spec: R2Task
    remaining_work: int
    first_start_tick: int | None = None
    completion_tick: int | None = None
    assigned_worker: int | None = None
    routing_attempts: int = 0
    restart_count: int = 0
    lost_work_units: int = 0


def _validate_trace(trace: R2Trace) -> None:
    worker_ids = [worker.id for worker in trace.workers]
    if len(set(worker_ids)) != len(worker_ids):
        raise ValueError("worker ids must be unique")
    task_ids = [task.id for task in trace.tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task ids must be unique")
    for task in trace.tasks:
        if task.arrival_tick >= trace.ticks:
            raise ValueError("task arrival_tick must be less than trace ticks")

    by_worker: dict[int, list[R2Outage]] = {}
    for outage in trace.outages:
        if outage.worker_index >= len(trace.workers):
            raise ValueError("outage worker_index is outside worker array")
        by_worker.setdefault(outage.worker_index, []).append(outage)
    for worker_outages in by_worker.values():
        ordered = sorted(worker_outages, key=lambda outage: outage.start_tick)
        for left, right in zip(ordered, ordered[1:]):
            if right.start_tick < left.end_tick:
                raise ValueError("overlapping outages for one worker are not supported")


def generate_r2_trace(config: R2TraceConfig) -> R2Trace:
    rng = random.Random(config.seed)
    capability_names = ("python", "cpu", "gpu")
    capability_weights = (0.50, 0.35, 0.15)
    zones = ("zone-a", "zone-b", "zone-c")

    workers: list[R2Worker] = []
    for index in range(config.worker_count):
        capacity = rng.choices((1, 2, 4), weights=(0.50, 0.35, 0.15), k=1)[0]
        primary = rng.choices(capability_names, weights=capability_weights, k=1)[0]
        capabilities = {primary}
        if rng.random() < 0.25:
            capabilities.add(rng.choice(capability_names))
        # Seed the beginning of sufficiently large populations so every
        # capability has at least one discoverable worker.
        if index < min(len(capability_names), config.worker_count):
            capabilities.add(capability_names[index])
        workers.append(
            R2Worker(
                id=f"worker-{index + 1:06d}",
                capacity=capacity,
                capabilities=tuple(sorted(capabilities)),
                zone=rng.choice(zones),
            )
        )

    tasks: list[R2Task] = []
    task_index = 0
    for tick in range(config.ticks):
        arrivals = config.base_arrivals_per_tick
        if arrivals and rng.random() < config.burst_probability:
            arrivals *= config.burst_multiplier
        for _ in range(arrivals):
            task_index += 1
            tasks.append(
                R2Task(
                    id=f"task-{task_index:08d}",
                    arrival_tick=tick,
                    work_units=rng.randint(1, config.max_work_units),
                    required_capability=rng.choices(
                        capability_names, weights=capability_weights, k=1
                    )[0],
                    preferred_zone=rng.choice(zones),
                )
            )

    outage_count = int(round(config.worker_count * config.churn_fraction))
    if config.churn_fraction > 0.0 and config.worker_count > 0:
        outage_count = max(1, outage_count)
    outage_count = min(config.worker_count, outage_count)
    outage_workers = rng.sample(range(config.worker_count), k=outage_count)
    outages: list[R2Outage] = []
    for worker_index in outage_workers:
        if config.ticks == 1:
            start_tick = 0
        else:
            start_tick = rng.randint(1, max(1, config.ticks - 1))
        duration = rng.randint(config.outage_min_ticks, config.outage_max_ticks)
        end_tick = min(config.ticks, start_tick + duration)
        if end_tick <= start_tick:
            end_tick = start_tick + 1
        outages.append(
            R2Outage(
                worker_index=worker_index,
                start_tick=start_tick,
                end_tick=end_tick,
            )
        )

    return R2Trace(
        seed=config.seed,
        ticks=config.ticks,
        workers=tuple(workers),
        tasks=tuple(tasks),
        outages=tuple(sorted(outages, key=lambda outage: (outage.start_tick, outage.worker_index))),
    )


def r2_trace_digest(trace: R2Trace) -> str:
    rendered = json.dumps(
        trace.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(rendered).hexdigest()


def save_r2_trace(trace: R2Trace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_r2_trace(path: Path) -> R2Trace:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("R2 trace file must contain a JSON object")
    return R2Trace.from_dict(value)


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _jain_index(values: Sequence[float]) -> float | None:
    if not values:
        return None
    denominator = len(values) * sum(value * value for value in values)
    if denominator == 0.0:
        return None
    return (sum(values) ** 2) / denominator


def _outage_maps(
    trace: R2Trace,
) -> tuple[dict[int, list[R2Outage]], dict[int, list[R2Outage]], dict[int, int]]:
    by_worker: dict[int, list[R2Outage]] = {}
    starts: dict[int, list[R2Outage]] = {}
    capacity_delta: dict[int, int] = {}
    for outage in trace.outages:
        by_worker.setdefault(outage.worker_index, []).append(outage)
        starts.setdefault(outage.start_tick, []).append(outage)
        capacity = trace.workers[outage.worker_index].capacity
        capacity_delta[outage.start_tick] = capacity_delta.get(outage.start_tick, 0) + capacity
        capacity_delta[outage.end_tick] = capacity_delta.get(outage.end_tick, 0) - capacity
    return by_worker, starts, capacity_delta


def _is_online(
    outages_by_worker: dict[int, list[R2Outage]],
    worker_index: int,
    tick: int,
) -> bool:
    if tick < 0:
        return True
    for outage in outages_by_worker.get(worker_index, ()):
        if outage.start_tick <= tick < outage.end_tick:
            return False
    return True


def _record_load_event(
    load_event_ticks: dict[int, list[int]],
    load_event_values: dict[int, list[int]],
    worker_index: int,
    tick: int,
    load: int,
) -> None:
    ticks = load_event_ticks.setdefault(worker_index, [])
    values = load_event_values.setdefault(worker_index, [])
    if ticks and ticks[-1] == tick:
        values[-1] = load
    else:
        ticks.append(tick)
        values.append(load)


def _observed_load(
    load_event_ticks: dict[int, list[int]],
    load_event_values: dict[int, list[int]],
    worker_index: int,
    target_tick: int,
) -> int:
    ticks = load_event_ticks.get(worker_index)
    if not ticks:
        return 0
    position = bisect_right(ticks, target_tick) - 1
    if position < 0:
        return 0
    return load_event_values[worker_index][position]


def _select_worker(
    *,
    policy: str,
    task: R2Task,
    tick: int,
    workers: Sequence[R2Worker],
    capability_index: dict[str, tuple[int, ...]],
    outages_by_worker: dict[int, list[R2Outage]],
    actual_loads: Sequence[int],
    load_event_ticks: dict[int, list[int]],
    load_event_values: dict[int, list[int]],
    config: R2RunConfig,
    rng: random.Random,
) -> tuple[int | None, int]:
    worker_count = len(workers)
    availability_tick = max(0, tick - config.availability_observation_lag)
    load_tick = max(0, tick - config.load_observation_lag)

    if policy == "global-least-loaded":
        pool = capability_index.get(task.required_capability, ())
        probes = len(pool)
        candidates = [
            index
            for index in pool
            if _is_online(outages_by_worker, index, tick)
        ]
        if not candidates:
            return None, probes
        return (
            min(
                candidates,
                key=lambda index: (
                    actual_loads[index] / workers[index].capacity,
                    actual_loads[index],
                    index,
                ),
            ),
            probes,
        )

    if policy == "capability-power-two":
        pool = capability_index.get(task.required_capability, ())
        if not pool:
            return None, 0
        sample_size = min(2, len(pool))
        sampled = rng.sample(pool, k=sample_size)
    elif policy == "one-random":
        sampled = [rng.randrange(worker_count)]
    elif policy in {"power-two", "power-three"}:
        d = 2 if policy == "power-two" else 3
        sample_size = min(d, worker_count)
        sampled = rng.sample(range(worker_count), k=sample_size)
    else:
        raise ValueError(f"unknown R2 policy: {policy}")

    probes = len(sampled)
    observed_online = [
        index
        for index in sampled
        if _is_online(outages_by_worker, index, availability_tick)
    ]
    if not observed_online:
        return None, probes
    if policy == "one-random":
        return observed_online[0], probes

    return (
        min(
            observed_online,
            key=lambda index: (
                _observed_load(
                    load_event_ticks,
                    load_event_values,
                    index,
                    load_tick,
                )
                / workers[index].capacity,
                _observed_load(
                    load_event_ticks,
                    load_event_values,
                    index,
                    load_tick,
                ),
                index,
            ),
        ),
        probes,
    )


def run_r2_policy(
    trace: R2Trace,
    policy: str,
    config: R2RunConfig,
) -> dict[str, object]:
    if policy not in R2_POLICIES:
        raise ValueError(f"unknown policy {policy!r}; choose one of {', '.join(R2_POLICIES)}")

    rng = random.Random(config.policy_seed)
    workers = trace.workers
    worker_count = len(workers)
    queues = [deque() for _ in workers]
    actual_loads = [0 for _ in workers]
    busy_workers: set[int] = set()
    processed_by_worker = [0 for _ in workers]
    load_event_ticks: dict[int, list[int]] = {}
    load_event_values: dict[int, list[int]] = {}

    states = {
        task.id: _TaskState(spec=task, remaining_work=task.work_units)
        for task in trace.tasks
    }
    arrivals: dict[int, list[str]] = {}
    for task in trace.tasks:
        arrivals.setdefault(task.arrival_tick, []).append(task.id)

    capability_index: dict[str, list[int]] = {}
    for index, worker in enumerate(workers):
        for capability in worker.capabilities:
            capability_index.setdefault(capability, []).append(index)
    capability_index_frozen = {
        capability: tuple(indices)
        for capability, indices in capability_index.items()
    }

    outages_by_worker, outage_starts, offline_capacity_delta = _outage_maps(trace)
    pending: deque[str] = deque()
    total_capacity = sum(worker.capacity for worker in workers)
    offline_capacity = 0
    potential_capacity = 0
    processed_work = 0
    successful_assignments = 0
    routing_attempts = 0
    metadata_probes = 0
    failed_no_candidate = 0
    failed_unreachable = 0
    failed_capability = 0
    locality_mismatches = 0
    churn_requeues = 0
    lost_work_due_churn = 0
    tick_max_queue_depths: list[float] = []
    pending_depths: list[float] = []
    recovery_events: list[dict[str, object]] = []

    horizon = trace.ticks + config.drain_ticks
    simulated_ticks = 0

    for tick in range(horizon):
        simulated_ticks = tick + 1
        offline_capacity += offline_capacity_delta.get(tick, 0)
        potential_capacity += max(0, total_capacity - offline_capacity)

        # A worker loss evicts in-flight/queued tasks. In the default model,
        # progress on that worker is lost because there is no checkpoint.
        for outage in outage_starts.get(tick, ()):
            worker_index = outage.worker_index
            affected: list[str] = []
            queue = queues[worker_index]
            while queue:
                task_id = queue.popleft()
                state = states[task_id]
                affected.append(task_id)
                if config.restart_work_on_churn:
                    progress = state.spec.work_units - state.remaining_work
                    state.lost_work_units += progress
                    lost_work_due_churn += progress
                    state.remaining_work = state.spec.work_units
                state.assigned_worker = None
                state.restart_count += 1
                pending.append(task_id)
                churn_requeues += 1
            actual_loads[worker_index] = 0
            _record_load_event(
                load_event_ticks,
                load_event_values,
                worker_index,
                tick,
                0,
            )
            busy_workers.discard(worker_index)
            if affected:
                recovery_events.append(
                    {
                        "worker_index": worker_index,
                        "outage_start_tick": tick,
                        "task_ids": affected,
                    }
                )

        # Existing assignments consume capacity before new arrivals are routed.
        for worker_index in list(busy_workers):
            if not _is_online(outages_by_worker, worker_index, tick):
                continue
            capacity = workers[worker_index].capacity
            queue = queues[worker_index]
            while capacity > 0 and queue:
                task_id = queue[0]
                state = states[task_id]
                if state.first_start_tick is None:
                    state.first_start_tick = tick
                work = min(capacity, state.remaining_work)
                state.remaining_work -= work
                actual_loads[worker_index] -= work
                processed_by_worker[worker_index] += work
                processed_work += work
                capacity -= work
                if state.remaining_work == 0:
                    queue.popleft()
                    state.completion_tick = tick + 1
                    state.assigned_worker = None
            _record_load_event(
                load_event_ticks,
                load_event_values,
                worker_index,
                tick,
                actual_loads[worker_index],
            )
            if not queue:
                busy_workers.discard(worker_index)

        for task_id in arrivals.get(tick, ()):
            pending.append(task_id)

        # Each pending task receives at most one routing attempt per tick.
        attempts_this_tick = len(pending)
        for _ in range(attempts_this_tick):
            task_id = pending.popleft()
            state = states[task_id]
            task = state.spec
            state.routing_attempts += 1
            routing_attempts += 1
            selected, probes = _select_worker(
                policy=policy,
                task=task,
                tick=tick,
                workers=workers,
                capability_index=capability_index_frozen,
                outages_by_worker=outages_by_worker,
                actual_loads=actual_loads,
                load_event_ticks=load_event_ticks,
                load_event_values=load_event_values,
                config=config,
                rng=rng,
            )
            metadata_probes += probes
            if selected is None:
                failed_no_candidate += 1
                pending.append(task_id)
                continue
            if not _is_online(outages_by_worker, selected, tick):
                failed_unreachable += 1
                pending.append(task_id)
                continue
            if task.required_capability not in workers[selected].capabilities:
                failed_capability += 1
                pending.append(task_id)
                continue

            queues[selected].append(task_id)
            state.assigned_worker = selected
            actual_loads[selected] += state.remaining_work
            _record_load_event(
                load_event_ticks,
                load_event_values,
                selected,
                tick,
                actual_loads[selected],
            )
            busy_workers.add(selected)
            successful_assignments += 1
            if workers[selected].zone != task.preferred_zone:
                locality_mismatches += 1

        max_depth = max((len(queues[index]) for index in busy_workers), default=0)
        tick_max_queue_depths.append(float(max_depth))
        pending_depths.append(float(len(pending)))

        if tick + 1 >= trace.ticks and not pending and not busy_workers:
            break

    completed_states = [
        state for state in states.values() if state.completion_tick is not None
    ]
    wait_times = [
        float(state.first_start_tick - state.spec.arrival_tick)
        for state in completed_states
        if state.first_start_tick is not None
    ]
    response_times = [
        float(state.completion_tick - state.spec.arrival_tick)
        for state in completed_states
        if state.completion_tick is not None
    ]

    recovery_times: list[float] = []
    unrecovered_events = 0
    for event in recovery_events:
        completion_ticks = [states[task_id].completion_tick for task_id in event["task_ids"]]
        if any(value is None for value in completion_ticks):
            unrecovered_events += 1
            continue
        recovery_times.append(
            float(max(int(value) for value in completion_ticks if value is not None) - int(event["outage_start_tick"]))
        )

    utilization_rates = []
    workers_used = 0
    for index, worker in enumerate(workers):
        offline_ticks = 0
        for outage in outages_by_worker.get(index, ()):
            start = max(0, outage.start_tick)
            end = min(simulated_ticks, outage.end_tick)
            if end > start:
                offline_ticks += end - start
        online_ticks = max(0, simulated_ticks - offline_ticks)
        opportunity = worker.capacity * online_ticks
        rate = processed_by_worker[index] / opportunity if opportunity > 0 else 0.0
        utilization_rates.append(rate)
        if processed_by_worker[index] > 0:
            workers_used += 1

    failed_assignments = failed_no_candidate + failed_unreachable + failed_capability
    completed_count = len(completed_states)

    return {
        "schema_version": 1,
        "experiment": "R2-scheduling-under-churn",
        "trace_digest": r2_trace_digest(trace),
        "policy": policy,
        "run_config": asdict(config),
        "metrics": {
            "tasks_total": len(trace.tasks),
            "tasks_completed": completed_count,
            "tasks_unfinished": len(trace.tasks) - completed_count,
            "completion_rate": completed_count / len(trace.tasks) if trace.tasks else 1.0,
            "mean_wait_ticks": mean(wait_times) if wait_times else None,
            "p95_wait_ticks": _percentile(wait_times, 0.95),
            "mean_response_ticks": mean(response_times) if response_times else None,
            "p95_response_ticks": _percentile(response_times, 0.95),
            "max_worker_queue_depth": max(tick_max_queue_depths, default=0.0),
            "p95_tick_max_queue_depth": _percentile(tick_max_queue_depths, 0.95),
            "mean_tick_max_queue_depth": mean(tick_max_queue_depths) if tick_max_queue_depths else 0.0,
            "max_pending_tasks": max(pending_depths, default=0.0),
            "routing_attempts": routing_attempts,
            "successful_assignments": successful_assignments,
            "failed_assignments": failed_assignments,
            "failed_no_observed_candidate": failed_no_candidate,
            "failed_unreachable": failed_unreachable,
            "failed_capability_mismatch": failed_capability,
            "metadata_probes": metadata_probes,
            "mean_metadata_probes_per_routing_attempt": (
                metadata_probes / routing_attempts if routing_attempts else 0.0
            ),
            "capability_mismatch_rate_per_routing_attempt": (
                failed_capability / routing_attempts if routing_attempts else 0.0
            ),
            "unreachable_rate_per_routing_attempt": (
                failed_unreachable / routing_attempts if routing_attempts else 0.0
            ),
            "locality_mismatch_rate_per_successful_assignment": (
                locality_mismatches / successful_assignments
                if successful_assignments
                else 0.0
            ),
            "processed_work_units": processed_work,
            "lost_work_units_due_churn": lost_work_due_churn,
            "churn_requeues": churn_requeues,
            "capacity_utilization": (
                processed_work / potential_capacity if potential_capacity else None
            ),
            "jain_worker_utilization_fairness": _jain_index(utilization_rates),
            "workers_used_fraction": workers_used / worker_count,
            "churn_recovery_events": len(recovery_events),
            "recovered_churn_events": len(recovery_times),
            "unrecovered_churn_events": unrecovered_events,
            "mean_churn_recovery_ticks": mean(recovery_times) if recovery_times else None,
            "p95_churn_recovery_ticks": _percentile(recovery_times, 0.95),
            "simulated_ticks": simulated_ticks,
        },
        "metric_notes": {
            "queue_depth_percentile": "p95 is over the maximum worker queue depth observed at each simulated tick",
            "metadata_probes": "one probe is one worker availability/load metadata inspection; global oracle probes its full capability pool",
            "capacity_utilization": "processed work, including repeated work after restart, divided by total online worker capacity over simulated ticks",
            "fairness": "Jain index over each worker's processed-work / online-capacity opportunity",
            "churn_recovery": "time until every task evicted by an outage completes; events with unfinished tasks are reported as unrecovered",
        },
    }


def r2_trace_summary(trace: R2Trace) -> dict[str, object]:
    capability_counts: dict[str, int] = {}
    for worker in trace.workers:
        for capability in worker.capabilities:
            capability_counts[capability] = capability_counts.get(capability, 0) + 1
    return {
        "seed": trace.seed,
        "ticks": trace.ticks,
        "worker_count": len(trace.workers),
        "task_count": len(trace.tasks),
        "outage_count": len(trace.outages),
        "total_worker_capacity": sum(worker.capacity for worker in trace.workers),
        "capability_worker_counts": capability_counts,
        "trace_digest": r2_trace_digest(trace),
    }


def run_r2_benchmark(
    trace: R2Trace,
    config: R2RunConfig,
    policies: Sequence[str] = R2_POLICIES,
) -> dict[str, object]:
    results = {
        policy: run_r2_policy(trace, policy, config)
        for policy in policies
    }
    return {
        "schema_version": 1,
        "experiment": "R2-scheduling-under-churn",
        "trace": r2_trace_summary(trace),
        "run_config": asdict(config),
        "policies": results,
        "comparison_guardrail": (
            "The global oracle is a high-information reference, not a decentralized implementation. "
            "Metadata probes expose part of the coordination cost that raw queue latency alone hides."
        ),
    }


def _parse_policy_list(value: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = [item for item in items if item not in R2_POLICIES]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown policies: {', '.join(unknown)}; choose from {', '.join(R2_POLICIES)}"
        )
    if not items:
        raise argparse.ArgumentTypeError("provide at least one policy")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r2",
        description="Benchmark decentralized scheduling policies on one replayable workload/churn trace.",
    )
    parser.add_argument("--trace", type=Path, help="load an existing R2 trace instead of generating one")
    parser.add_argument("--trace-output", type=Path, help="write the exact generated/loaded trace as JSON")
    parser.add_argument("--workers", type=int, default=100)
    parser.add_argument("--ticks", type=int, default=200)
    parser.add_argument("--arrivals", type=int, default=4)
    parser.add_argument("--burst-probability", type=float, default=0.10)
    parser.add_argument("--burst-multiplier", type=int, default=5)
    parser.add_argument("--max-work", type=int, default=8)
    parser.add_argument("--churn-fraction", type=float, default=0.10)
    parser.add_argument("--outage-min", type=int, default=3)
    parser.add_argument("--outage-max", type=int, default=20)
    parser.add_argument("--trace-seed", type=int, default=42)
    parser.add_argument("--policy-seed", type=int, default=1337)
    parser.add_argument("--availability-lag", type=int, default=2)
    parser.add_argument("--load-lag", type=int, default=2)
    parser.add_argument("--drain-ticks", type=int, default=200)
    parser.add_argument(
        "--policies",
        type=_parse_policy_list,
        default=R2_POLICIES,
        help="comma-separated subset of policies",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.trace:
        trace = load_r2_trace(args.trace)
    else:
        trace = generate_r2_trace(
            R2TraceConfig(
                worker_count=args.workers,
                ticks=args.ticks,
                base_arrivals_per_tick=args.arrivals,
                burst_probability=args.burst_probability,
                burst_multiplier=args.burst_multiplier,
                max_work_units=args.max_work,
                churn_fraction=args.churn_fraction,
                outage_min_ticks=args.outage_min,
                outage_max_ticks=args.outage_max,
                seed=args.trace_seed,
            )
        )

    if args.trace_output:
        save_r2_trace(trace, args.trace_output)

    report = run_r2_benchmark(
        trace,
        R2RunConfig(
            availability_observation_lag=args.availability_lag,
            load_observation_lag=args.load_lag,
            drain_ticks=args.drain_ticks,
            policy_seed=args.policy_seed,
        ),
        policies=args.policies,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
