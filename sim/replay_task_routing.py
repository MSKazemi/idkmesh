#!/usr/bin/env python3
"""Read-only historical/shadow replay for IDKMesh task-routing research.

The replay engine intentionally separates routing inputs from retrospective
outcomes. It never calls GitHub, changes repository state, assigns work, or
uses future outcomes to generate recommendations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import aco_stigmergy_sim as aco
import homeostatic_stigmergy_sim as hsr


def load_dataset(path: str | Path) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema_version") != "0.1.0":
        raise ValueError("routing replay dataset must use schema_version 0.1.0")
    return data


def to_task(item: Mapping[str, object]) -> aco.Task:
    return aco.Task(
        name=str(item["id"]),
        skill=str(item["skill"]),
        impact=float(item["impact"]),
        information_gain=float(item["information_gain"]),
        review_cost=float(item["review_cost"]),
        compute_cost=float(item["compute_cost"]),
        risk=float(item["risk"]),
        accessibility=float(item["accessibility"]),
        # Replay ranks tasks; it does not simulate a new outcome.
        base_success=0.5,
        parallel_limit=3,
    )


def to_worker(item: Mapping[str, object]) -> aco.Worker:
    return aco.Worker(
        name=str(item["id"]),
        group=str(item["group"]),
        skills={str(k): float(v) for k, v in dict(item["skills"]).items()},
    )


def apply_known_evidence(
    pheromone: Dict[str, float],
    evidence: Sequence[Mapping[str, object]],
    config: aco.ACOConfig,
) -> None:
    """Evaporate memory, then apply only evidence known at replay time."""
    deposits: Dict[str, float] = {task_id: 0.0 for task_id in pheromone}
    penalties: Dict[str, float] = {task_id: 0.0 for task_id in pheromone}

    for event in evidence:
        task_id = str(event["task_id"])
        if task_id not in pheromone:
            continue
        penalties[task_id] += float(event.get("penalty", 0.0))
        if not bool(event["verified"]):
            continue
        deposits[task_id] += (
            float(event["quality"])
            * float(event["verification_strength"])
            * float(event["diversity"])
            * float(event["descendant_value"])
            / (
                1.0
                + float(event["human_review_cost"])
                + float(event["compute_cost"])
            )
        )

    for task_id in pheromone:
        pheromone[task_id] = aco.update_pheromone(
            pheromone[task_id], deposits[task_id], penalties[task_id], config
        )


def active_state(
    snapshot: Mapping[str, object],
) -> Tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
    counts: Dict[str, int] = {}
    group_counts: Dict[Tuple[str, str], int] = {}
    for attempt in snapshot.get("active_attempts", []):
        task_id = str(attempt["task_id"])
        group = str(attempt["worker_group"])
        counts[task_id] = counts.get(task_id, 0) + 1
        group_counts[(task_id, group)] = group_counts.get((task_id, group), 0) + 1
    return counts, group_counts


def normalized(values: Sequence[float]) -> List[float]:
    total = sum(values)
    if total <= aco.EPS:
        return [1.0 / len(values)] * len(values)
    return [value / total for value in values]


def capability_probabilities(worker: aco.Worker, tasks: Sequence[aco.Task]) -> List[float]:
    weights = [
        max(
            aco.EPS,
            float(worker.skills.get(task.skill, 0.0)) * aco.intrinsic_value(task),
        )
        for task in tasks
    ]
    return normalized(weights)


def deterministic_recommendation(
    tasks: Sequence[aco.Task], probabilities: Sequence[float]
) -> str:
    # Stable tie-break by task ID makes replay deterministic.
    pairs = list(zip(tasks, probabilities))
    best_task, _ = max(pairs, key=lambda pair: (pair[1], pair[0].name))
    return best_task.name


def distribution(tasks: Sequence[aco.Task], probabilities: Sequence[float]) -> Dict[str, float]:
    return {
        task.name: round(probability, 9)
        for task, probability in zip(tasks, probabilities)
    }


def heldout_utility(snapshot: Mapping[str, object], task_id: str) -> float:
    outcomes = dict(snapshot.get("retrospective_outcomes", {}))
    outcome = outcomes.get(task_id, {})
    return float(outcome.get("verified_utility", 0.0))


def replay(dataset: Mapping[str, object]) -> Dict[str, object]:
    tasks_by_id = {
        str(item["id"]): to_task(item)
        for item in dataset["tasks"]
    }
    workers_by_id = {
        str(item["id"]): to_worker(item)
        for item in dataset["workers"]
    }

    aco_config = aco.ACOConfig()
    hsr_config = hsr.HomeostaticConfig()
    pheromone: Dict[str, float] = {task_id: 1.0 for task_id in tasks_by_id}
    regulation = hsr_config.lambda_initial

    snapshots_out: List[Dict[str, object]] = []
    heldout_totals = {"capability": 0.0, "aco": 0.0, "homeostatic": 0.0}
    recommendation_counts: Dict[str, Dict[str, int]] = {
        name: {} for name in heldout_totals
    }
    decisions = 0

    for snapshot in dataset["snapshots"]:
        # Critical anti-hindsight ordering: update from evidence explicitly known at
        # this timestamp, calculate recommendations, and inspect outcomes only after.
        apply_known_evidence(pheromone, snapshot.get("evidence", []), aco_config)

        available_tasks = [
            tasks_by_id[str(task_id)]
            for task_id in snapshot["available_task_ids"]
            if str(task_id) in tasks_by_id
        ]
        available_workers = [
            workers_by_id[str(worker_id)]
            for worker_id in snapshot["available_worker_ids"]
            if str(worker_id) in workers_by_id
        ]
        if not available_tasks:
            raise ValueError(f"snapshot {snapshot['id']} has no known available tasks")

        attempt_counts, group_attempts = active_state(snapshot)
        worker_rows: List[Dict[str, object]] = []

        for worker in available_workers:
            capability_probs = capability_probabilities(worker, available_tasks)
            aco_probs = aco.aco_probabilities(
                worker,
                available_tasks,
                pheromone,
                attempt_counts,
                group_attempts,
                aco_config,
            )
            hsr_probs = hsr.probabilities(
                worker,
                available_tasks,
                pheromone,
                attempt_counts,
                group_attempts,
                regulation,
                hsr_config,
            )

            probabilities_by_strategy = {
                "capability": capability_probs,
                "aco": aco_probs,
                "homeostatic": hsr_probs,
            }
            recommendations: Dict[str, str] = {}
            heldout: Dict[str, float] = {}

            for strategy, probabilities in probabilities_by_strategy.items():
                task_id = deterministic_recommendation(available_tasks, probabilities)
                recommendations[strategy] = task_id
                # Outcomes are consulted only after the recommendation is fixed.
                value = heldout_utility(snapshot, task_id)
                heldout[strategy] = value
                heldout_totals[strategy] += value
                recommendation_counts[strategy][task_id] = (
                    recommendation_counts[strategy].get(task_id, 0) + 1
                )

            decisions += 1
            worker_rows.append(
                {
                    "worker_id": worker.name,
                    "recommendations": recommendations,
                    "distributions": {
                        strategy: distribution(available_tasks, probabilities)
                        for strategy, probabilities in probabilities_by_strategy.items()
                    },
                    "heldout_verified_utility": heldout,
                }
            )

        duplicate_rate = float(snapshot.get("observed_duplicate_rate", 0.0))
        concentration = float(snapshot.get("observed_concentration", 0.0))
        regulation_before = regulation
        regulation = hsr.update_regulation(
            regulation,
            duplicate_rate,
            concentration,
            hsr_config,
        )

        snapshots_out.append(
            {
                "snapshot_id": snapshot["id"],
                "observed_at": snapshot["observed_at"],
                "pheromone": {
                    task_id: round(value, 9)
                    for task_id, value in pheromone.items()
                },
                "homeostatic_regulation_before": round(regulation_before, 9),
                "homeostatic_regulation_after": round(regulation, 9),
                "workers": worker_rows,
            }
        )

    mean_heldout = {
        strategy: round(total / decisions, 9) if decisions else 0.0
        for strategy, total in heldout_totals.items()
    }
    unique_recommended_tasks = {
        strategy: len(counts)
        for strategy, counts in recommendation_counts.items()
    }

    return {
        "experiment": "routing-historical-replay-v0",
        "dataset_id": dataset["dataset_id"],
        "repository": dataset["repository"],
        "annotation_policy": dataset["annotation_policy"],
        "anti_hindsight_invariant": (
            "retrospective_outcomes are read only after each recommendation is fixed"
        ),
        "decisions": decisions,
        "mean_heldout_verified_utility_of_top_recommendation": mean_heldout,
        "unique_recommended_tasks": unique_recommended_tasks,
        "snapshots": snapshots_out,
        "limitations": list(dataset["limitations"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="routing replay JSON dataset")
    parser.add_argument("--output", help="optional output JSON path")
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    result = replay(load_dataset(args.dataset))
    encoded = json.dumps(result, indent=args.indent, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
