from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import gzip
import json
import math
from pathlib import Path
import random
from statistics import mean, stdev
from typing import Sequence

from .model import CorrelatedBernoulliEnvironment
from .r1 import (
    CandidateProfile,
    R1Condition,
    R1ExperimentConfig,
    Verifier,
    _mean_pairwise_error_correlation,
    _verifier_accepts,
    build_r1_conditions,
    run_r1_condition,
)


FAMILIES = ("homogeneous", "structural_diversity", "diverse_verifiers")
METRICS = (
    "verified_success_rate",
    "selected_regression_rate",
    "selected_security_failure_rate",
    "false_acceptance_rate",
    "mean_compute_per_task",
    "mean_parallel_latency_per_task",
    "mean_human_attention_proxy_per_task",
    "verified_utility_per_unit_cost",
)

FLAT = "flat"
ROLE_SPECIALIZED = "role_specialized"
TASK_DAG = "task_dag"
TOPOLOGIES = (FLAT, ROLE_SPECIALIZED, TASK_DAG)
ROLE_SPECIALIZED_STAGES = 2
TASK_DAG_DEPTH = 2
EXPONENT_METRICS = ("verified_success_rate", "verified_utility_per_unit_cost")

# The gap ledger a run publishes is a statement about that run. A flat-only run
# genuinely does not represent the two team topologies, so the baseline keeps
# both entries; a run that executes the topology arms drops exactly those two.
NOT_REPRESENTED_BASELINE = (
    "measured strong-model versus small-model quality",
    "planner plus implementer plus tester plus reviewer topology",
    "task-DAG team topology",
    "real held-out software tasks",
    "measured inference cost, reviewer minutes, communication bytes, and duplication",
)

TOPOLOGY_CLOSES_GAP = {
    ROLE_SPECIALIZED: "planner plus implementer plus tester plus reviewer topology",
    TASK_DAG: "task-DAG team topology",
}

TOPOLOGY_REPRESENTED_AS = {
    ROLE_SPECIALIZED: (
        "planner plus implementers plus tester plus reviewer topology at "
        "budget-matched N=2,5,10"
    ),
    TASK_DAG: (
        "task-DAG team topology with downstream subtasks blocked until a parent "
        "is accepted, at budget-matched N=2,5,10"
    ),
}


@dataclass(frozen=True)
class R1ScalingConfig:
    tasks_per_trial: int = 200
    trials: int = 10
    base_seed: int = 42
    swarm_sizes: tuple[int, ...] = (1, 2, 5, 10)
    difficulty_levels: tuple[tuple[str, float], ...] = (
        ("easy", 0.82),
        ("medium", 0.65),
        ("hard", 0.45),
    )
    structural_error_correlation: float = 0.25
    verifier_error_correlation: float = 0.60

    def __post_init__(self) -> None:
        if self.tasks_per_trial < 1:
            raise ValueError("tasks_per_trial must be >= 1")
        if self.trials < 2:
            raise ValueError("trials must be >= 2")
        if not self.swarm_sizes or self.swarm_sizes[0] != 1:
            raise ValueError("swarm_sizes must start with the one-worker baseline")
        if tuple(sorted(set(self.swarm_sizes))) != self.swarm_sizes:
            raise ValueError("swarm_sizes must be unique and strictly increasing")
        if not self.difficulty_levels:
            raise ValueError("difficulty_levels must not be empty")
        names = [name for name, _ in self.difficulty_levels]
        if len(set(names)) != len(names) or any(not name for name in names):
            raise ValueError("difficulty names must be non-empty and unique")
        if any(not 0.0 <= quality <= 1.0 for _, quality in self.difficulty_levels):
            raise ValueError("difficulty quality values must be in [0, 1]")
        for value in (
            self.structural_error_correlation,
            self.verifier_error_correlation,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("correlations must be in [0, 1]")


def _normal_interval(values: Sequence[float]) -> list[float]:
    center = mean(values)
    margin = 1.96 * stdev(values) / math.sqrt(len(values))
    return [center - margin, center + margin]


def _summary(values: Sequence[float]) -> dict[str, object]:
    return {
        "mean": mean(values),
        "sample_std": stdev(values),
        "normal_approx_95_ci": _normal_interval(values),
        "min": min(values),
        "max": max(values),
    }


def _delta_summary(values: Sequence[float]) -> dict[str, object]:
    result = _summary(values)
    lower, upper = result["normal_approx_95_ci"]
    if lower > 0.0:
        classification = "positive"
    elif upper < 0.0:
        classification = "negative"
    else:
        classification = "uncertain"
    result["classification"] = classification
    return result


def _condition_name(family: str, swarm_size: int) -> str:
    if swarm_size == 1:
        return "single_deterministic"
    return {
        "homogeneous": "identical_replication",
        "structural_diversity": "structural_diversity",
        "diverse_verifiers": "diverse_random_verifiers",
    }[family]


def _run_cell(
    config: R1ScalingConfig,
    *,
    difficulty: str,
    worker_quality: float,
    family: str,
    swarm_size: int,
) -> dict[str, object]:
    r1_config = R1ExperimentConfig(
        tasks_per_trial=config.tasks_per_trial,
        trials=config.trials,
        swarm_size=max(2, swarm_size),
        base_seed=config.base_seed,
        base_worker_success_probability=worker_quality,
        structural_error_correlation=config.structural_error_correlation,
        verifier_error_correlation=config.verifier_error_correlation,
        retain_task_records=False,
    )
    name = _condition_name(family, swarm_size)
    condition = next(item for item in build_r1_conditions(r1_config) if item.name == name)
    trials = []
    for trial_index in range(config.trials):
        seed = config.base_seed + trial_index
        result = run_r1_condition(
            condition,
            tasks=config.tasks_per_trial,
            seed=seed,
            retain_task_records=False,
        )
        trials.append({"seed": seed, "metrics": result["metrics"]})
    return {
        "difficulty": difficulty,
        "worker_quality_assumption": worker_quality,
        "family": family,
        "swarm_size": swarm_size,
        "condition": name,
        "summary": {
            metric: _summary([float(row["metrics"][metric]) for row in trials])
            for metric in METRICS
        },
        "raw_trials": trials,
    }


def _stage_success_probability(value: float, stages: int) -> float:
    """Per-stage success probability whose ``stages``-fold product is ``value``."""

    return value ** (1.0 / stages)


def _stage_defect_probability(value: float, stages: int) -> float:
    """Per-stage defect probability whose ``stages``-fold union is ``value``."""

    return 1.0 - (1.0 - value) ** (1.0 / stages)


def _topology_condition(
    config: R1ScalingConfig,
    *,
    worker_quality: float,
    family: str,
    swarm_size: int,
    topology: str,
) -> R1Condition:
    defaults = R1ExperimentConfig()
    shared = {
        "tasks_per_trial": config.tasks_per_trial,
        "trials": config.trials,
        "swarm_size": max(2, swarm_size),
        "base_seed": config.base_seed,
        "structural_error_correlation": config.structural_error_correlation,
        "verifier_error_correlation": config.verifier_error_correlation,
        "retain_task_records": False,
    }
    if topology == ROLE_SPECIALIZED:
        # A planner and an implementer form a two-stage chain, so each stage is
        # calibrated to reproduce the flat single-worker candidate exactly.
        # Defect draws stay on the implementer, who is the only role that writes
        # the artifact.
        r1_config = R1ExperimentConfig(
            base_worker_success_probability=_stage_success_probability(
                worker_quality, ROLE_SPECIALIZED_STAGES
            ),
            **shared,
        )
    elif topology == TASK_DAG:
        # Every subtask is one stage of a depth-``TASK_DAG_DEPTH`` chain, so
        # quality, hidden-test, regression, and security draws are all split so
        # that a clean serial execution reproduces the flat monolithic task.
        r1_config = R1ExperimentConfig(
            base_worker_success_probability=_stage_success_probability(
                worker_quality, TASK_DAG_DEPTH
            ),
            hidden_test_pass_probability=_stage_success_probability(
                defaults.hidden_test_pass_probability, TASK_DAG_DEPTH
            ),
            regression_probability=_stage_defect_probability(
                defaults.regression_probability, TASK_DAG_DEPTH
            ),
            security_failure_probability=_stage_defect_probability(
                defaults.security_failure_probability, TASK_DAG_DEPTH
            ),
            **shared,
        )
    else:
        raise ValueError(f"unknown coordination topology: {topology}")
    name = _condition_name(family, swarm_size)
    return next(item for item in build_r1_conditions(r1_config) if item.name == name)


def _draw_candidate(
    profile: CandidateProfile,
    base_success: bool,
    rng: random.Random,
) -> dict[str, object]:
    hidden_test_pass = bool(
        base_success and rng.random() < profile.hidden_test_pass_probability
    )
    regression = rng.random() < profile.regression_probability
    security_failure = rng.random() < profile.security_failure_probability
    return {
        "worker": profile.worker.name,
        "diversity_label": profile.diversity_label,
        "base_success": base_success,
        "hidden_test_pass": hidden_test_pass,
        "regression": regression,
        "security_failure": security_failure,
        "is_good": bool(
            base_success
            and hidden_test_pass
            and not regression
            and not security_failure
        ),
    }


def _pick_verifier(condition: R1Condition, rng: random.Random) -> Verifier:
    if condition.verifier_assignment == "fixed":
        return condition.verifiers[0]
    return rng.choice(condition.verifiers)


@dataclass(frozen=True)
class _TaskOutcome:
    used_profiles: tuple[CandidateProfile, ...]
    verifiers_used: tuple[Verifier, ...]
    any_good: bool
    integrated: dict[str, object] | None


def _role_specialized_task(
    condition: R1Condition,
    profiles: Sequence[CandidateProfile],
    environment: CorrelatedBernoulliEnvironment,
    rng: random.Random,
    latent_outcomes: dict[str, list[int]],
) -> _TaskOutcome:
    workers = [profile.worker for profile in profiles]
    plan_sample = environment.sample(workers, rng)
    implementation_sample = environment.sample(workers, rng)
    for worker in workers:
        latent_outcomes[worker.name].append(int(implementation_sample[worker.name]))

    planner = profiles[0]
    implementers = profiles[1:]
    plan_is_sound = bool(plan_sample[planner.worker.name])

    candidates = [
        _draw_candidate(
            profile,
            bool(plan_is_sound and implementation_sample[profile.worker.name]),
            rng,
        )
        for profile in implementers
    ]

    shared_draws = {verifier.name: rng.random() for verifier in condition.verifiers}
    verifiers_used: list[Verifier] = []
    for candidate in candidates:
        tester = _pick_verifier(condition, rng)
        verifiers_used.append(tester)
        candidate["accepted"] = _verifier_accepts(
            bool(candidate["is_good"]),
            tester,
            rng,
            shared_draws[tester.name],
            condition.verifier_error_correlation,
        )

    tested = next(
        (candidate for candidate in candidates if bool(candidate["accepted"])), None
    )
    # The reviewer is consulted once per task whether or not the tester passed
    # anything through, so the verification budget matches the flat arm exactly.
    reviewer = _pick_verifier(condition, rng)
    verifiers_used.append(reviewer)
    reviewer_accepts = _verifier_accepts(
        bool(tested is not None and tested["is_good"]),
        reviewer,
        rng,
        shared_draws[reviewer.name],
        condition.verifier_error_correlation,
    )

    return _TaskOutcome(
        used_profiles=tuple(profiles),
        verifiers_used=tuple(verifiers_used),
        any_good=any(bool(candidate["is_good"]) for candidate in candidates),
        integrated=tested if (tested is not None and reviewer_accepts) else None,
    )


def _task_dag_task(
    condition: R1Condition,
    profiles: Sequence[CandidateProfile],
    environment: CorrelatedBernoulliEnvironment,
    rng: random.Random,
    latent_outcomes: dict[str, list[int]],
) -> _TaskOutcome:
    workers = [profile.worker for profile in profiles]
    level_samples = [
        environment.sample(workers, rng) for _ in range(TASK_DAG_DEPTH)
    ]
    for worker in workers:
        latent_outcomes[worker.name].append(int(level_samples[0][worker.name]))

    total_budget = len(profiles)
    parent_budget = total_budget - total_budget // 2
    child_budget = total_budget // 2

    shared_draws = {verifier.name: rng.random() for verifier in condition.verifiers}
    verifiers_used: list[Verifier] = []
    used_profiles: list[CandidateProfile] = []

    def attempt(level: int, index: int) -> dict[str, object]:
        profile = profiles[index]
        used_profiles.append(profile)
        candidate = _draw_candidate(
            profile, bool(level_samples[level][profile.worker.name]), rng
        )
        verifier = _pick_verifier(condition, rng)
        verifiers_used.append(verifier)
        candidate["accepted"] = _verifier_accepts(
            bool(candidate["is_good"]),
            verifier,
            rng,
            shared_draws[verifier.name],
            condition.verifier_error_correlation,
        )
        return candidate

    parents = [attempt(0, index) for index in range(parent_budget)]
    accepted_parent = next(
        (candidate for candidate in parents if bool(candidate["accepted"])), None
    )
    children: list[dict[str, object]] = []
    if accepted_parent is None:
        # The downstream subtask is blocked, so the idle downstream budget is
        # re-spent upstream. Total attempts and verifications stay at N.
        parents.extend(
            attempt(0, parent_budget + index) for index in range(child_budget)
        )
        accepted_parent = next(
            (candidate for candidate in parents if bool(candidate["accepted"])), None
        )
    else:
        children = [
            attempt(1, parent_budget + index) for index in range(child_budget)
        ]
    accepted_child = next(
        (candidate for candidate in children if bool(candidate["accepted"])), None
    )

    integrated: dict[str, object] | None = None
    if accepted_parent is not None and accepted_child is not None:
        integrated = {
            "worker": f"{accepted_parent['worker']}+{accepted_child['worker']}",
            "hidden_test_pass": bool(
                accepted_parent["hidden_test_pass"]
                and accepted_child["hidden_test_pass"]
            ),
            "regression": bool(
                accepted_parent["regression"] or accepted_child["regression"]
            ),
            "security_failure": bool(
                accepted_parent["security_failure"]
                or accepted_child["security_failure"]
            ),
            "is_good": bool(
                accepted_parent["is_good"] and accepted_child["is_good"]
            ),
        }

    any_good = bool(
        any(bool(candidate["is_good"]) for candidate in parents)
        and any(bool(candidate["is_good"]) for candidate in children)
    )
    return _TaskOutcome(
        used_profiles=tuple(used_profiles),
        verifiers_used=tuple(verifiers_used),
        any_good=any_good,
        integrated=integrated,
    )


def run_topology_condition(
    condition: R1Condition,
    *,
    topology: str,
    tasks: int,
    seed: int,
) -> dict[str, object]:
    """Run one coordination-topology arm at a matched attempt budget."""

    if tasks < 1:
        raise ValueError("tasks must be >= 1")
    task_runner = {
        ROLE_SPECIALIZED: _role_specialized_task,
        TASK_DAG: _task_dag_task,
    }.get(topology)
    if task_runner is None:
        raise ValueError(f"unknown coordination topology: {topology}")

    rng = random.Random(seed)
    environment = CorrelatedBernoulliEnvironment(condition.worker_error_correlation)
    profiles = list(condition.profiles)
    latent_outcomes = {profile.worker.name: [] for profile in profiles}
    totals = {
        "verified_successes": 0,
        "candidate_any_good": 0,
        "selected_hidden_test_pass": 0,
        "selected_regressions": 0,
        "selected_security_failures": 0,
        "false_acceptances": 0,
        "abstentions": 0,
        "missed_good_candidates": 0,
        "compute": 0.0,
        "parallel_latency": 0.0,
        "human_attention": 0.0,
        "structural_diversity": 0.0,
        "attempt_units": 0,
        "verification_units": 0,
    }

    for _ in range(tasks):
        outcome = task_runner(condition, profiles, environment, rng, latent_outcomes)
        used = outcome.used_profiles
        totals["attempt_units"] += len(used)
        totals["verification_units"] += len(outcome.verifiers_used)
        totals["candidate_any_good"] += int(outcome.any_good)
        totals["compute"] += sum(profile.worker.compute_cost for profile in used)
        totals["parallel_latency"] += max(profile.worker.latency for profile in used)
        totals["structural_diversity"] += len(
            {profile.diversity_label for profile in used}
        ) / len(used)
        totals["human_attention"] += sum(
            verifier.attention_cost for verifier in outcome.verifiers_used
        )

        integrated = outcome.integrated
        if integrated is None:
            totals["abstentions"] += 1
            totals["missed_good_candidates"] += int(outcome.any_good)
        else:
            is_good = bool(integrated["is_good"])
            totals["verified_successes"] += int(is_good)
            totals["false_acceptances"] += int(not is_good)
            totals["selected_hidden_test_pass"] += int(
                bool(integrated["hidden_test_pass"])
            )
            totals["selected_regressions"] += int(bool(integrated["regression"]))
            totals["selected_security_failures"] += int(
                bool(integrated["security_failure"])
            )

    resource_cost = float(totals["compute"]) + float(totals["human_attention"])
    metrics = {
        "verified_successes": totals["verified_successes"],
        "verified_success_rate": totals["verified_successes"] / tasks,
        "candidate_any_good_rate": totals["candidate_any_good"] / tasks,
        "selected_hidden_test_pass_rate": totals["selected_hidden_test_pass"] / tasks,
        "selected_regression_rate": totals["selected_regressions"] / tasks,
        "selected_security_failure_rate": totals["selected_security_failures"] / tasks,
        "false_acceptance_rate": totals["false_acceptances"] / tasks,
        "abstention_rate": totals["abstentions"] / tasks,
        "missed_good_candidate_rate": totals["missed_good_candidates"] / tasks,
        "total_compute": totals["compute"],
        "mean_compute_per_task": totals["compute"] / tasks,
        "mean_parallel_latency_per_task": totals["parallel_latency"] / tasks,
        "total_human_attention_proxy": totals["human_attention"],
        "mean_human_attention_proxy_per_task": totals["human_attention"] / tasks,
        "mean_structural_diversity": totals["structural_diversity"] / tasks,
        "mean_pairwise_base_error_correlation": _mean_pairwise_error_correlation(
            condition.profiles, latent_outcomes
        ),
        "verified_utility_per_unit_cost": (
            totals["verified_successes"] / resource_cost if resource_cost else None
        ),
        "mean_attempt_units_per_task": totals["attempt_units"] / tasks,
        "mean_verification_units_per_task": totals["verification_units"] / tasks,
    }
    return {
        "schema_version": 1,
        "experiment": "R1-coordination-topology",
        "topology": topology,
        "condition": condition.name,
        "tasks": tasks,
        "seed": seed,
        "metrics": metrics,
    }


def _run_topology_cell(
    config: R1ScalingConfig,
    *,
    difficulty: str,
    worker_quality: float,
    family: str,
    swarm_size: int,
    topology: str,
) -> dict[str, object]:
    condition = _topology_condition(
        config,
        worker_quality=worker_quality,
        family=family,
        swarm_size=swarm_size,
        topology=topology,
    )
    trials = []
    for trial_index in range(config.trials):
        seed = config.base_seed + trial_index
        result = run_topology_condition(
            condition,
            topology=topology,
            tasks=config.tasks_per_trial,
            seed=seed,
        )
        trials.append({"seed": seed, "metrics": result["metrics"]})
    return {
        "difficulty": difficulty,
        "worker_quality_assumption": worker_quality,
        "family": family,
        "swarm_size": swarm_size,
        "topology": topology,
        "condition": f"{topology}:{condition.name}",
        "attempt_budget_per_task": swarm_size,
        "verification_budget_per_task": swarm_size,
        "summary": {
            metric: _summary([float(row["metrics"][metric]) for row in trials])
            for metric in METRICS
        },
        "raw_trials": trials,
    }


def _log_log_slope(
    sizes: Sequence[int], values: Sequence[float]
) -> float | None:
    """Ordinary-least-squares exponent of ``values`` against ``sizes``."""

    if len(sizes) != len(values) or len(sizes) < 2:
        return None
    if any(value <= 0.0 for value in values):
        return None
    xs = [math.log(size) for size in sizes]
    ys = [math.log(value) for value in values]
    mean_x = mean(xs)
    mean_y = mean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0.0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def _seed_exponents(
    by_key: dict[tuple[str, str, int, str], dict[str, object]],
    config: R1ScalingConfig,
    *,
    difficulty: str,
    family: str,
    topology: str,
    metric: str,
) -> dict[int, float]:
    exponents: dict[int, float] = {}
    for trial_index in range(config.trials):
        seed = config.base_seed + trial_index
        values = []
        for swarm_size in config.swarm_sizes:
            cell = by_key[(difficulty, family, swarm_size, topology)]
            row = cell["raw_trials"][trial_index]
            if row["seed"] != seed:
                raise ValueError("topology cells must use identical seeds")
            values.append(float(row["metrics"][metric]))
        slope = _log_log_slope(config.swarm_sizes, values)
        if slope is not None:
            exponents[seed] = slope
    return exponents


def _paired_deltas(
    left: dict[str, object],
    right: dict[str, object],
    metric: str,
) -> list[float]:
    left_rows = left["raw_trials"]
    right_rows = right["raw_trials"]
    if [row["seed"] for row in left_rows] != [row["seed"] for row in right_rows]:
        raise ValueError("paired cells must use identical seeds")
    return [
        float(rrow["metrics"][metric]) - float(lrow["metrics"][metric])
        for lrow, rrow in zip(left_rows, right_rows)
    ]


def _validate_topologies(topologies: tuple[str, ...]) -> None:
    if not topologies or topologies[0] != FLAT:
        raise ValueError("topologies must start with the flat baseline")
    if len(set(topologies)) != len(topologies):
        raise ValueError("topologies must be unique")
    unknown = [name for name in topologies if name not in TOPOLOGIES]
    if unknown:
        raise ValueError(f"unknown coordination topologies: {sorted(unknown)}")


def _topology_sections(
    config: R1ScalingConfig,
    topologies: tuple[str, ...],
    by_key: dict[tuple[str, str, int, str], dict[str, object]],
) -> dict[str, object]:
    exponents: list[dict[str, object]] = []
    contrasts: list[dict[str, object]] = []
    for difficulty, _ in config.difficulty_levels:
        for family in FAMILIES:
            for metric in EXPONENT_METRICS:
                per_topology = {
                    topology: _seed_exponents(
                        by_key,
                        config,
                        difficulty=difficulty,
                        family=family,
                        topology=topology,
                        metric=metric,
                    )
                    for topology in topologies
                }
                for topology in topologies:
                    values = list(per_topology[topology].values())
                    exponents.append(
                        {
                            "difficulty": difficulty,
                            "family": family,
                            "topology": topology,
                            "metric": metric,
                            "fit": "ordinary least squares on log(metric) versus log(N)",
                            "swarm_sizes": list(config.swarm_sizes),
                            "seeds_used": sorted(per_topology[topology]),
                            "exponent": _delta_summary(values)
                            if len(values) > 1
                            else None,
                        }
                    )
                baseline = per_topology[FLAT]
                for topology in topologies:
                    if topology == FLAT:
                        continue
                    candidate = per_topology[topology]
                    shared_seeds = sorted(set(baseline) & set(candidate))
                    deltas = [
                        candidate[seed] - baseline[seed] for seed in shared_seeds
                    ]
                    summary = _delta_summary(deltas) if len(deltas) > 1 else None
                    contrasts.append(
                        {
                            "difficulty": difficulty,
                            "family": family,
                            "metric": metric,
                            "baseline_topology": FLAT,
                            "candidate_topology": topology,
                            "seeds_used": shared_seeds,
                            "exponent_delta": summary,
                            "changes_exponent": bool(
                                summary is not None
                                and summary["classification"] != "uncertain"
                            ),
                        }
                    )

    parity: list[dict[str, object]] = []
    for difficulty, _ in config.difficulty_levels:
        for family in FAMILIES:
            for swarm_size in config.swarm_sizes:
                baseline = by_key[(difficulty, family, swarm_size, FLAT)]
                for topology in topologies:
                    if topology == FLAT:
                        continue
                    candidate = by_key[(difficulty, family, swarm_size, topology)]
                    compute = _paired_deltas(
                        baseline, candidate, "mean_compute_per_task"
                    )
                    attention = _paired_deltas(
                        baseline, candidate, "mean_human_attention_proxy_per_task"
                    )
                    latency = _paired_deltas(
                        baseline, candidate, "mean_parallel_latency_per_task"
                    )
                    parity.append(
                        {
                            "difficulty": difficulty,
                            "family": family,
                            "swarm_size": swarm_size,
                            "baseline_topology": FLAT,
                            "candidate_topology": topology,
                            "equal_attempt_budget_per_task": (
                                baseline["attempt_budget_per_task"]
                                == candidate["attempt_budget_per_task"]
                            ),
                            "equal_verification_budget_per_task": (
                                baseline["verification_budget_per_task"]
                                == candidate["verification_budget_per_task"]
                            ),
                            "equal_mean_compute_per_task": all(
                                abs(value) < 1e-12 for value in compute
                            ),
                            "equal_mean_human_attention_per_task": all(
                                abs(value) < 1e-12 for value in attention
                            ),
                            "equal_mean_parallel_latency_per_task": all(
                                abs(value) < 1e-12 for value in latency
                            ),
                        }
                    )

    return {
        "topology_scaling_exponents": exponents,
        "topology_exponent_contrasts": contrasts,
        "topology_budget_parity": parity,
    }


def run_r1_scaling(
    config: R1ScalingConfig,
    *,
    topologies: Sequence[str] = (FLAT,),
) -> dict[str, object]:
    topologies = tuple(topologies)
    _validate_topologies(topologies)
    cells = []
    for difficulty, quality in config.difficulty_levels:
        for family in FAMILIES:
            for swarm_size in config.swarm_sizes:
                cells.append(
                    _run_cell(
                        config,
                        difficulty=difficulty,
                        worker_quality=quality,
                        family=family,
                        swarm_size=swarm_size,
                    )
                )

    by_key = {
        (cell["difficulty"], cell["family"], cell["swarm_size"]): cell
        for cell in cells
    }
    marginals = []
    for difficulty, _ in config.difficulty_levels:
        for family in FAMILIES:
            for lower_n, upper_n in zip(config.swarm_sizes, config.swarm_sizes[1:]):
                lower = by_key[(difficulty, family, lower_n)]
                upper = by_key[(difficulty, family, upper_n)]
                success = _paired_deltas(lower, upper, "verified_success_rate")
                utility = _paired_deltas(
                    lower, upper, "verified_utility_per_unit_cost"
                )
                regressions = _paired_deltas(
                    lower, upper, "selected_regression_rate"
                )
                security = _paired_deltas(
                    lower, upper, "selected_security_failure_rate"
                )
                compute = _paired_deltas(lower, upper, "mean_compute_per_task")
                attention = _paired_deltas(
                    lower, upper, "mean_human_attention_proxy_per_task"
                )
                marginals.append(
                    {
                        "difficulty": difficulty,
                        "family": family,
                        "from_n": lower_n,
                        "to_n": upper_n,
                        "additional_workers": upper_n - lower_n,
                        "verified_success_rate_delta": _delta_summary(success),
                        "verified_utility_per_unit_cost_delta": _delta_summary(
                            utility
                        ),
                        "selected_regression_rate_delta": _delta_summary(regressions),
                        "selected_security_failure_rate_delta": _delta_summary(
                            security
                        ),
                        "mean_compute_per_task_delta": _delta_summary(compute),
                        "mean_human_attention_per_task_delta": _delta_summary(attention),
                        "mean_success_rate_points_per_additional_compute": (
                            mean(success) / mean(compute) if mean(compute) else None
                        ),
                        "mean_success_rate_points_per_additional_worker": (
                            mean(success) / (upper_n - lower_n)
                        ),
                    }
                )

    equal_budget = []
    for difficulty, _ in config.difficulty_levels:
        for swarm_size in config.swarm_sizes[1:]:
            baseline = by_key[(difficulty, "homogeneous", swarm_size)]
            for family in ("structural_diversity", "diverse_verifiers"):
                candidate = by_key[(difficulty, family, swarm_size)]
                compute = _paired_deltas(
                    baseline, candidate, "mean_compute_per_task"
                )
                attention = _paired_deltas(
                    baseline,
                    candidate,
                    "mean_human_attention_proxy_per_task",
                )
                equal_budget.append(
                    {
                        "difficulty": difficulty,
                        "swarm_size": swarm_size,
                        "candidate_family": family,
                        "baseline_family": "homogeneous",
                        "verified_success_rate_delta": _delta_summary(
                            _paired_deltas(
                                baseline, candidate, "verified_success_rate"
                            )
                        ),
                        "verified_utility_per_unit_cost_delta": _delta_summary(
                            _paired_deltas(
                                baseline,
                                candidate,
                                "verified_utility_per_unit_cost",
                            )
                        ),
                        "equal_attempt_count": True,
                        "equal_mean_compute_per_task": all(
                            abs(value) < 1e-12 for value in compute
                        ),
                        "equal_mean_human_attention_per_task": all(
                            abs(value) < 1e-12 for value in attention
                        ),
                    }
                )

    represented = [
        "one worker",
        "homogeneous groups at N=2,5,10",
        "structurally diverse groups at N=2,5,10",
        "diverse verifier assignment at N=2,5,10",
        "three controlled task-difficulty assumptions",
        "repeated deterministic seeds",
    ]
    not_represented = list(NOT_REPRESENTED_BASELINE)
    result = {
        "schema_version": 1,
        "experiment": "R1-collective-capability-scaling",
        "generator": "randomness_lab.r1_scaling.v1",
        "evidence_level": "synthetic_mechanism",
        "config": asdict(config),
        "cells": cells,
        "marginal_curves": marginals,
        "equal_attempt_budget_comparisons": equal_budget,
        "issue_13_coverage": {
            "represented_as_synthetic_proxies": represented,
            "not_represented": not_represented,
        },
        "interpretation_guardrail": (
            "All worker quality, correlation, defects, and verifier behavior are synthetic. "
            "These curves test analysis mechanics and expose negative regimes; they are not "
            "empirical scaling laws for coding agents and cannot close issue #13."
        ),
    }
    if topologies == (FLAT,):
        return result

    for cell in cells:
        cell["topology"] = FLAT
        cell["attempt_budget_per_task"] = cell["swarm_size"]
        cell["verification_budget_per_task"] = cell["swarm_size"]

    by_topology_key = {
        (cell["difficulty"], cell["family"], cell["swarm_size"], FLAT): cell
        for cell in cells
    }
    for difficulty, quality in config.difficulty_levels:
        for topology in topologies:
            if topology == FLAT:
                continue
            for family in FAMILIES:
                for swarm_size in config.swarm_sizes:
                    if swarm_size == 1:
                        # A team of one has no coordination structure, so every
                        # topology shares the flat single-worker baseline.
                        cell = _run_cell(
                            config,
                            difficulty=difficulty,
                            worker_quality=quality,
                            family=family,
                            swarm_size=swarm_size,
                        )
                        cell["topology"] = topology
                        cell["attempt_budget_per_task"] = swarm_size
                        cell["verification_budget_per_task"] = swarm_size
                        cell["degenerate_single_worker_baseline"] = True
                    else:
                        cell = _run_topology_cell(
                            config,
                            difficulty=difficulty,
                            worker_quality=quality,
                            family=family,
                            swarm_size=swarm_size,
                            topology=topology,
                        )
                    cells.append(cell)
                    by_topology_key[(difficulty, family, swarm_size, topology)] = cell

    result["schema_version"] = 2
    result["generator"] = "randomness_lab.r1_scaling.v2"
    result["topologies"] = list(topologies)
    result["topology_mechanism"] = {
        FLAT: (
            "N independent attempts on the whole task, one verification each, "
            "first accepted candidate integrated"
        ),
        ROLE_SPECIALIZED: (
            "one planner attempt gates N-1 implementer attempts; a tester "
            "verifies each implementer candidate and a reviewer verifies the "
            "tester's pick, so attempts and verifications both stay at N"
        ),
        TASK_DAG: (
            "ceil(N/2) attempts on a parent subtask and floor(N/2) on a child "
            "subtask that is blocked until a parent is accepted; blocked "
            "downstream budget is re-spent upstream, so attempts and "
            "verifications both stay at N"
        ),
        "neutral_calibration": (
            "Per-stage success, hidden-test, regression, and security "
            "probabilities are split so that a single clean serial chain "
            "reproduces the flat single-worker candidate distribution exactly. "
            "No topology is given an assumed quality advantage."
        ),
    }
    # ``represented`` and ``not_represented`` are the very lists the result
    # already holds, so the gap ledger now describes the arms this run executed.
    for topology in topologies:
        if topology == FLAT:
            continue
        represented.append(TOPOLOGY_REPRESENTED_AS[topology])
        not_represented.remove(TOPOLOGY_CLOSES_GAP[topology])
    result.update(_topology_sections(config, topologies, by_topology_key))
    return result


def render_markdown(result: dict[str, object]) -> str:
    lines = [
        "# R1 collective-capability scaling reference",
        "",
        "Evidence level: **synthetic mechanism only**.",
        "",
        "## Marginal verified-success changes",
        "",
        "| Difficulty | Family | N | Mean delta | 95% interval | Class |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in result["marginal_curves"]:
        summary = row["verified_success_rate_delta"]
        interval = summary["normal_approx_95_ci"]
        lines.append(
            f"| {row['difficulty']} | {row['family']} | {row['from_n']}→{row['to_n']} "
            f"| {summary['mean']:.4f} | [{interval[0]:.4f}, {interval[1]:.4f}] "
            f"| {summary['classification']} |"
        )
    if "topology_scaling_exponents" in result:
        lines.extend(
            [
                "",
                "## Scaling exponent by coordination topology",
                "",
                "Ordinary least squares on log(metric) against log(N), fitted per seed.",
                "",
                "| Difficulty | Family | Topology | Metric | Exponent | 95% interval | Class |",
                "| --- | --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for row in result["topology_scaling_exponents"]:
            summary = row["exponent"]
            if summary is None:
                continue
            interval = summary["normal_approx_95_ci"]
            lines.append(
                f"| {row['difficulty']} | {row['family']} | {row['topology']} "
                f"| {row['metric']} | {summary['mean']:.4f} "
                f"| [{interval[0]:.4f}, {interval[1]:.4f}] "
                f"| {summary['classification']} |"
            )
        lines.extend(
            [
                "",
                "## Coordination-topology exponent contrast versus flat",
                "",
                "Paired per-seed exponent differences at a matched attempt and "
                "verification budget.",
                "",
                "| Difficulty | Family | Topology | Metric | Exponent delta | 95% interval | Changes exponent |",
                "| --- | --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for row in result["topology_exponent_contrasts"]:
            summary = row["exponent_delta"]
            if summary is None:
                continue
            interval = summary["normal_approx_95_ci"]
            lines.append(
                f"| {row['difficulty']} | {row['family']} "
                f"| {row['candidate_topology']} | {row['metric']} "
                f"| {summary['mean']:.4f} "
                f"| [{interval[0]:.4f}, {interval[1]:.4f}] "
                f"| {'yes' if row['changes_exponent'] else 'no'} |"
            )
    lines.extend(
        [
            "",
            "## Scope boundary",
            "",
            result["interpretation_guardrail"],
            "",
            "The machine-readable companion retains every seeded trial, equal-attempt "
            "comparison, cost delta, and the explicit issue #13 coverage gaps.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_ints(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parse_difficulties(value: str) -> tuple[tuple[str, float], ...]:
    parsed = []
    try:
        for item in value.split(","):
            name, quality = item.strip().split(":", 1)
            parsed.append((name, float(quality)))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use name:quality comma-separated pairs") from exc
    return tuple(parsed)


def _parse_topologies(value: str) -> tuple[str, ...]:
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    try:
        _validate_topologies(parsed)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_scaling",
        description="Run the synthetic R1 collective-capability N-scaling experiment.",
    )
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--swarm-sizes", type=_parse_ints, default=(1, 2, 5, 10))
    parser.add_argument(
        "--difficulties",
        type=_parse_difficulties,
        default=(("easy", 0.82), ("medium", 0.65), ("hard", 0.45)),
    )
    parser.add_argument(
        "--topologies",
        type=_parse_topologies,
        default=(FLAT,),
        help=(
            "comma-separated coordination topologies, starting with flat; "
            f"choices: {','.join(TOPOLOGIES)}"
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r1_scaling(
        R1ScalingConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            base_seed=args.seed,
            swarm_sizes=args.swarm_sizes,
            difficulty_levels=args.difficulties,
        ),
        topologies=args.topologies,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == ".gz":
            args.output.write_bytes(
                gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0)
            )
        else:
            args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
