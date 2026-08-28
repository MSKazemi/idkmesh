#!/usr/bin/env python3
"""IDKMesh randomness-lab v0.

A small, standard-library simulator for testing exploration policies under
heterogeneous worker quality, positive error dependence, latency/cost, and
worker churn. Randomness changes *which worker is explored*; acceptance is
always mediated by an independent verifier model.

This simulator is illustrative research infrastructure, not empirical proof
about real humans, agents, or production systems.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "0.1"
POLICY_NAMES = ("greedy", "epsilon_greedy", "softmax", "ucb", "thompson", "power_of_two")


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: int
    quality: float
    cost: float
    latency: float


@dataclass(frozen=True)
class TaskOutcome:
    available: tuple[bool, ...]
    success: tuple[bool, ...]
    cost: tuple[float, ...]
    latency: tuple[float, ...]


@dataclass
class PolicyState:
    successes: list[int]
    attempts: list[int]
    total_cost: list[float]

    @classmethod
    def for_workers(cls, count: int) -> "PolicyState":
        return cls([0] * count, [0] * count, [0.0] * count)

    def mean(self, index: int) -> float:
        # Beta(1,1) posterior mean. New workers start uncertain at 0.5.
        return (self.successes[index] + 1.0) / (self.attempts[index] + 2.0)


class Policy:
    name = "base"

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        raise NotImplementedError


class GreedyPolicy(Policy):
    name = "greedy"

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        return max(available, key=lambda i: (state.mean(i), -state.total_cost[i], -i))


class EpsilonGreedyPolicy(Policy):
    name = "epsilon_greedy"

    def __init__(self, epsilon: float = 0.1) -> None:
        self.epsilon = epsilon

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        if rng.random() < self.epsilon:
            return rng.choice(list(available))
        return max(available, key=lambda i: (state.mean(i), -state.total_cost[i], -i))


class SoftmaxPolicy(Policy):
    name = "softmax"

    def __init__(self, temperature: float = 0.15) -> None:
        self.temperature = temperature

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        temp = max(self.temperature, 1e-9)
        values = [state.mean(i) for i in available]
        pivot = max(values)
        weights = [math.exp((value - pivot) / temp) for value in values]
        return rng.choices(list(available), weights=weights, k=1)[0]


class UCBPolicy(Policy):
    name = "ucb"

    def __init__(self, exploration: float = math.sqrt(2.0)) -> None:
        self.exploration = exploration

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        untried = [i for i in available if state.attempts[i] == 0]
        if untried:
            return min(untried)
        total = max(1, sum(state.attempts))
        return max(
            available,
            key=lambda i: state.mean(i)
            + self.exploration * math.sqrt(math.log(total + 1.0) / state.attempts[i]),
        )


class ThompsonPolicy(Policy):
    name = "thompson"

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        return max(
            available,
            key=lambda i: rng.betavariate(
                state.successes[i] + 1,
                state.attempts[i] - state.successes[i] + 1,
            ),
        )


class PowerOfTwoPolicy(Policy):
    name = "power_of_two"

    def select(self, available: Sequence[int], state: PolicyState, rng: random.Random) -> int:
        if len(available) == 1:
            return available[0]
        choices = rng.sample(list(available), 2)
        return max(choices, key=lambda i: (state.mean(i), -state.total_cost[i], -i))


def policy_factory(name: str) -> Policy:
    table = {
        "greedy": GreedyPolicy,
        "epsilon_greedy": EpsilonGreedyPolicy,
        "softmax": SoftmaxPolicy,
        "ucb": UCBPolicy,
        "thompson": ThompsonPolicy,
        "power_of_two": PowerOfTwoPolicy,
    }
    return table[name]()


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def build_workers(count: int, seed: int) -> list[WorkerSpec]:
    rng = random.Random(stable_seed(seed, "workers"))
    workers: list[WorkerSpec] = []
    for index in range(count):
        quality = min(0.95, max(0.52, rng.gauss(0.70, 0.10)))
        cost = max(0.1, rng.lognormvariate(-0.15, 0.35))
        latency = max(0.05, rng.lognormvariate(-0.2, 0.45))
        workers.append(WorkerSpec(index, quality, cost, latency))
    return workers


def generate_workload(
    workers: Sequence[WorkerSpec],
    tasks: int,
    seed: int,
    shared_outcome_probability: float,
    churn_probability: float,
) -> list[TaskOutcome]:
    """Generate a common workload reused by every policy.

    `shared_outcome_probability` is a dependence control, not an exact Pearson
    correlation coefficient. With that probability, all workers are evaluated
    against the same uniform draw for the task; otherwise they receive
    independent draws. This creates configurable positive dependence while
    preserving heterogeneous worker qualities.
    """
    rng = random.Random(stable_seed(seed, "workload"))
    outcomes: list[TaskOutcome] = []
    for _ in range(tasks):
        shared = rng.random() < shared_outcome_probability
        common_draw = rng.random()
        available: list[bool] = []
        success: list[bool] = []
        costs: list[float] = []
        latencies: list[float] = []
        for worker in workers:
            is_available = rng.random() >= churn_probability
            available.append(is_available)
            draw = common_draw if shared else rng.random()
            success.append(is_available and draw < worker.quality)
            costs.append(worker.cost * rng.uniform(0.9, 1.1))
            latencies.append(worker.latency * rng.uniform(0.8, 1.25))
        outcomes.append(TaskOutcome(tuple(available), tuple(success), tuple(costs), tuple(latencies)))
    return outcomes


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denom = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denom == 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def pairwise_error_correlation(workload: Sequence[TaskOutcome], worker_count: int) -> float | None:
    errors = [[1.0 if not task.success[i] else 0.0 for task in workload] for i in range(worker_count)]
    values: list[float] = []
    for i in range(worker_count):
        for j in range(i + 1, worker_count):
            value = pearson(errors[i], errors[j])
            if value is not None and math.isfinite(value):
                values.append(value)
    return statistics.fmean(values) if values else None


def verifier_accepts(truth: bool, accuracy: float, rng: random.Random) -> bool:
    # Symmetric verifier model: accuracy is P(verdict == truth).
    correct_verdict = rng.random() < accuracy
    return truth if correct_verdict else not truth


def run_policy(
    policy_name: str,
    workers: Sequence[WorkerSpec],
    workload: Sequence[TaskOutcome],
    seed: int,
    verifier_accuracy: float,
) -> dict[str, object]:
    policy = policy_factory(policy_name)
    state = PolicyState.for_workers(len(workers))
    rng = random.Random(stable_seed(seed, "policy", policy_name))
    verify_rng = random.Random(stable_seed(seed, "verifier", policy_name))

    attempts = 0
    accepted = 0
    verified_successes = 0
    escaped_failures = 0
    rejected_correct = 0
    failed_assignments = 0
    total_cost = 0.0
    total_latency = 0.0
    selection_counts = [0] * len(workers)

    for task in workload:
        available = [i for i, flag in enumerate(task.available) if flag]
        if not available:
            failed_assignments += 1
            continue
        worker_index = policy.select(available, state, rng)
        truth = task.success[worker_index]
        verdict = verifier_accepts(truth, verifier_accuracy, verify_rng)

        attempts += 1
        selection_counts[worker_index] += 1
        state.attempts[worker_index] += 1
        state.successes[worker_index] += int(truth)
        state.total_cost[worker_index] += task.cost[worker_index]
        total_cost += task.cost[worker_index]
        total_latency += task.latency[worker_index]

        if verdict:
            accepted += 1
            if truth:
                verified_successes += 1
            else:
                escaped_failures += 1
        elif truth:
            rejected_correct += 1

    if attempts:
        shares = [count / attempts for count in selection_counts if count]
        selection_entropy = -sum(share * math.log(share) for share in shares)
        max_entropy = math.log(len(workers)) if len(workers) > 1 else 1.0
        normalized_entropy = selection_entropy / max_entropy if max_entropy else 0.0
    else:
        normalized_entropy = 0.0

    return {
        "policy": policy_name,
        "attempts": attempts,
        "accepted": accepted,
        "verified_successes": verified_successes,
        "escaped_failures": escaped_failures,
        "rejected_correct": rejected_correct,
        "failed_assignments": failed_assignments,
        "verified_success_rate": verified_successes / attempts if attempts else 0.0,
        "escaped_failure_rate": escaped_failures / accepted if accepted else 0.0,
        "total_compute_cost": total_cost,
        "mean_latency": total_latency / attempts if attempts else 0.0,
        "human_attention_proxy_minutes": 0.05 * (rejected_correct + escaped_failures),
        "selection_diversity": normalized_entropy,
        "selection_counts": selection_counts,
    }


def ci95(values: Sequence[float]) -> dict[str, float]:
    mean = statistics.fmean(values) if values else 0.0
    if len(values) < 2:
        return {"mean": mean, "lower": mean, "upper": mean, "stdev": 0.0}
    stdev = statistics.stdev(values)
    margin = 1.96 * stdev / math.sqrt(len(values))
    return {"mean": mean, "lower": mean - margin, "upper": mean + margin, "stdev": stdev}


def aggregate(records: Sequence[dict[str, object]]) -> dict[str, object]:
    by_policy: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_policy.setdefault(str(record["policy"]), []).append(record)

    summary: dict[str, object] = {}
    for policy, items in sorted(by_policy.items()):
        summary[policy] = {
            "trials": len(items),
            "verified_success_rate": ci95([float(item["verified_success_rate"]) for item in items]),
            "escaped_failure_rate": ci95([float(item["escaped_failure_rate"]) for item in items]),
            "total_compute_cost": ci95([float(item["total_compute_cost"]) for item in items]),
            "mean_latency": ci95([float(item["mean_latency"]) for item in items]),
            "human_attention_proxy_minutes": ci95(
                [float(item["human_attention_proxy_minutes"]) for item in items]
            ),
            "selection_diversity": ci95([float(item["selection_diversity"]) for item in items]),
            "pairwise_error_correlation": ci95(
                [float(item["pairwise_error_correlation"]) for item in items]
            ),
        }
    return summary


def run_experiment(args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    policies = list(POLICY_NAMES) if args.policy == "all" else [args.policy]
    workers = build_workers(args.workers, args.seed)
    records: list[dict[str, object]] = []

    for trial in range(args.trials):
        trial_seed = stable_seed(args.seed, "trial", trial)
        workload = generate_workload(
            workers,
            args.tasks,
            trial_seed,
            args.shared_outcome_probability,
            args.churn_probability,
        )
        correlation = pairwise_error_correlation(workload, len(workers))
        corr_value = 0.0 if correlation is None else correlation
        for policy_name in policies:
            result = run_policy(
                policy_name,
                workers,
                workload,
                trial_seed,
                args.verifier_accuracy,
            )
            result.update(
                {
                    "schema_version": "randomness-lab-v0.1",
                    "simulator_version": VERSION,
                    "seed": args.seed,
                    "trial": trial,
                    "trial_seed": trial_seed,
                    "worker_count": len(workers),
                    "tasks": args.tasks,
                    "shared_outcome_probability": args.shared_outcome_probability,
                    "churn_probability": args.churn_probability,
                    "verifier_accuracy": args.verifier_accuracy,
                    "pairwise_error_correlation": corr_value,
                    "notes": "Illustrative simulation; shared_outcome_probability controls dependence but is not an exact target correlation.",
                }
            )
            records.append(result)

    envelope = {
        "schema_version": "randomness-lab-summary-v0.1",
        "simulator_version": VERSION,
        "parameters": {
            "seed": args.seed,
            "trials": args.trials,
            "tasks_per_trial": args.tasks,
            "workers": args.workers,
            "policy": args.policy,
            "shared_outcome_probability": args.shared_outcome_probability,
            "churn_probability": args.churn_probability,
            "verifier_accuracy": args.verifier_accuracy,
        },
        "worker_specs": [worker.__dict__ for worker in workers],
        "summary": aggregate(records),
        "interpretation_guardrail": (
            "Randomness controls exploration only. A simulated worker result is accepted only through the "
            "independent verifier model; this output is research evidence about the simulator, not proof "
            "about real-world IDKMesh performance."
        ),
    }
    return records, envelope


def write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("all",) + POLICY_NAMES, default="all")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--shared-outcome-probability", type=float, default=0.25)
    parser.add_argument("--churn-probability", type=float, default=0.05)
    parser.add_argument("--verifier-accuracy", type=float, default=0.98)
    parser.add_argument("--output", type=Path, default=Path("results/randomness-lab.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("results/randomness-lab-summary.json"))
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.workers < 2:
        raise ValueError("--workers must be >= 2")
    if args.tasks < 1 or args.trials < 1:
        raise ValueError("--tasks and --trials must be >= 1")
    for name in ("shared_outcome_probability", "churn_probability"):
        value = getattr(args, name)
        if not 0.0 <= value < 1.0:
            raise ValueError(f"--{name.replace('_', '-')} must be in [0, 1)")
    if not 0.5 <= args.verifier_accuracy <= 1.0:
        raise ValueError("--verifier-accuracy must be in [0.5, 1.0]")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        validate_args(args)
        records, summary = run_experiment(args)
        write_jsonl(args.output, records)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"OK: wrote {len(records)} trial-policy records to {args.output} and summary to {args.summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
