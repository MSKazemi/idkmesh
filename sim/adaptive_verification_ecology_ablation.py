#!/usr/bin/env python3
"""Component ablation harness for Adaptive Verification Ecology (AVE).

The harness compares cumulative AVE components under common review/compute
budget ceilings and several synthetic environments. It is a research model,
not evidence about real agents, reviewers, or organizations.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

import adaptive_verification_ecology_sim as ave


@dataclass(frozen=True)
class Policy:
    name: str
    niche: bool = False
    posterior_routing: bool = False
    temperature: bool = False
    verifier_diversity: bool = False
    probe_memory: bool = False
    risk_adaptive: bool = False
    shadow_backpressure: bool = False
    price_aware_routing: bool = False


@dataclass(frozen=True)
class Environment:
    name: str
    error_mode: str = "one-sided"
    worker_shock_rate: float = 0.12
    worker_shock_penalty: float = 0.22
    verifier_corr_scale: float = 1.0
    review_capacity_scale: float = 1.0
    probe_alignment: float = 1.0
    worker_quality_imbalance: float = 0.0
    workload_shift: bool = False
    worker_outage: bool = False
    verifier_outage: bool = False
    selective_adversary: bool = False
    outage_epoch_fraction: float = 0.50


POLICIES: Tuple[Policy, ...] = (
    Policy("capability-only"),
    Policy("plus-ecology", niche=True),
    Policy("plus-posterior", niche=True, posterior_routing=True),
    Policy(
        "plus-temperature",
        niche=True,
        posterior_routing=True,
        temperature=True,
    ),
    Policy(
        "plus-verifier-diversity",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
    ),
    Policy(
        "plus-probe-memory",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        probe_memory=True,
    ),
    Policy(
        "plus-risk-adaptive",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        probe_memory=True,
        risk_adaptive=True,
    ),
    Policy(
        "plus-shadow-backpressure",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        probe_memory=True,
        risk_adaptive=True,
        shadow_backpressure=True,
    ),
    Policy(
        "full-ave",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        probe_memory=True,
        risk_adaptive=True,
        shadow_backpressure=True,
        price_aware_routing=True,
    ),
)

ENVIRONMENTS: Tuple[Environment, ...] = (
    Environment("one-sided-medium"),
    Environment(
        "two-sided-medium",
        error_mode="two-sided",
    ),
    Environment(
        "high-correlation",
        worker_shock_rate=0.28,
        worker_shock_penalty=0.30,
        verifier_corr_scale=1.75,
    ),
    Environment(
        "scarce-review",
        review_capacity_scale=0.60,
    ),
    Environment(
        "misleading-probes",
        probe_alignment=0.20,
    ),
    Environment(
        "dominant-worker-family",
        worker_quality_imbalance=0.18,
    ),
    Environment(
        "workload-shift",
        workload_shift=True,
    ),
    Environment(
        "worker-family-outage",
        worker_outage=True,
    ),
    Environment(
        "verifier-family-outage",
        verifier_outage=True,
    ),
    Environment(
        "selective-adversarial-verifier",
        selective_adversary=True,
    ),
)


def policy_by_name(name: str) -> Policy:
    for policy in POLICIES:
        if policy.name == name:
            return policy
    raise ValueError(f"unknown policy: {name}")


def environment_by_name(name: str) -> Environment:
    for environment in ENVIRONMENTS:
        if environment.name == name:
            return environment
    raise ValueError(f"unknown environment: {name}")


def route_temperature(
    posteriors: Mapping[Tuple[str, str], Sequence[float]],
    price: float,
    config: ave.Config,
    policy: Policy,
) -> float:
    if not policy.temperature:
        return config.temp_min
    effective_price = price if policy.price_aware_routing else 0.0
    return ave.route_temperature(posteriors, effective_price, config)


def route_task(
    worker: ave.Worker,
    counts: Mapping[str, int],
    family_counts: Mapping[Tuple[str, str], int],
    posteriors: Mapping[Tuple[str, str], Sequence[float]],
    price: float,
    temp: float,
    config: ave.Config,
    policy: Policy,
    rng: random.Random,
    task_weights: Mapping[str, float] | None = None,
) -> ave.Task:
    def score(task: ave.Task, learned: float) -> float:
        skill = ave.clamp(float(worker.skills[task.skill]), 0.02, 1.0)
        same = family_counts.get((task.name, worker.family), 0)
        niche = (
            (1.0 + same) ** (-config.niche_pressure)
            if policy.niche
            else 1.0
        )
        congestion = (
            (1.0 + counts.get(task.name, 0)) ** (-0.55)
            if policy.niche
            else 1.0
        )
        scarcity = (
            1.0 + price * task.review
            if policy.price_aware_routing
            else 1.0
        )
        demand = float((task_weights or {}).get(task.name, 1.0))
        return max(
            ave.EPS,
            task.value * demand * skill * learned * niche * congestion / scarcity,
        )

    if not policy.posterior_routing:
        return max(
            ave.TASKS,
            key=lambda task: (score(task, 1.0), task.name),
        )

    sampled_scores: List[float] = []
    for task in ave.TASKS:
        posterior = posteriors[(worker.family, task.name)]
        learned = rng.betavariate(
            float(posterior[0]),
            float(posterior[1]),
        )
        sampled_scores.append(score(task, learned))

    if not policy.temperature:
        return max(
            zip(ave.TASKS, sampled_scores),
            key=lambda item: (item[1], item[0].name),
        )[0]

    logits = [math.log(max(ave.EPS, value)) for value in sampled_scores]
    return ave.choose(ave.TASKS, ave.softmax(logits, temp), rng)


def apply_worker_quality_imbalance(
    workers: Sequence[ave.Worker],
    amount: float,
) -> List[ave.Worker]:
    """Create a dominant family without changing worker count or identities."""
    if amount <= 0.0:
        return list(workers)
    adjusted: List[ave.Worker] = []
    for worker in workers:
        delta = amount if worker.family == "worker-family-0" else -0.5 * amount
        skills = {
            skill: ave.clamp(float(value) + delta, 0.02, 1.0)
            for skill, value in worker.skills.items()
        }
        adjusted.append(ave.Worker(worker.name, worker.family, skills))
    return adjusted


def workload_weights(
    epoch: int,
    epochs: int,
    environment: Environment,
) -> Dict[str, float]:
    """Model an exogenous mid-run change in task demand."""
    if not environment.workload_shift:
        return {}
    shifted = epoch >= max(1, epochs // 2)
    if not shifted:
        return {
            "docs": 1.8,
            "onboarding": 1.8,
            "reproduction": 1.35,
            "security": 0.60,
            "integration": 0.70,
        }
    return {
        "docs": 0.60,
        "onboarding": 0.60,
        "reproduction": 0.80,
        "security": 1.9,
        "integration": 1.65,
        "validator": 1.30,
    }


def candidate(
    worker: ave.Worker,
    task: ave.Task,
    family_shock: bool,
    environment: Environment,
    rng: random.Random,
) -> Tuple[bool, float]:
    skill = ave.clamp(float(worker.skills[task.skill]), 0.0, 1.0)
    success_probability = ave.clamp(
        task.success * (0.45 + 0.70 * skill),
        0.05,
        0.97,
    )
    if family_shock:
        success_probability = ave.clamp(
            success_probability - environment.worker_shock_penalty,
            0.02,
            0.97,
        )
    good = rng.random() < success_probability
    utility = task.value * (0.60 + 0.40 * skill) if good else 0.0
    return good, utility


def verifier_verdicts(
    selected: Sequence[ave.Verifier],
    truth_good: bool,
    risk: float,
    environment: Environment,
    rng: random.Random,
    *,
    probe: bool = False,
) -> Dict[str, bool]:
    alignment = environment.probe_alignment if probe else 1.0
    shock_scale = environment.verifier_corr_scale * alignment
    shocks = {
        verifier.family: rng.random()
        < ave.clamp(verifier.shock_rate * shock_scale, 0.0, 0.95)
        for verifier in selected
    }
    out: Dict[str, bool] = {}
    for verifier in selected:
        shocked = shocks[verifier.family]
        if environment.selective_adversary and verifier.family == "verifier-family-0":
            if probe:
                accuracy = 0.99
            elif truth_good:
                accuracy = 0.96
            else:
                # Looks excellent on probes but accepts most live defects.
                accuracy = 0.08
        elif truth_good:
            if environment.error_mode == "one-sided":
                accuracy = ave.clamp(
                    0.985
                    - 0.02 * risk
                    - (0.02 * shock_scale if shocked else 0.0),
                    0.90,
                    0.995,
                )
            elif environment.error_mode == "two-sided":
                accuracy = ave.clamp(
                    0.925
                    - 0.08 * risk
                    - (0.10 * shock_scale if shocked else 0.0),
                    0.55,
                    0.98,
                )
            else:
                raise ValueError(
                    f"unknown error_mode: {environment.error_mode}"
                )
        else:
            probe_bonus = 0.12 * (1.0 - alignment) if probe else 0.0
            accuracy = ave.clamp(
                verifier.specificity
                + probe_bonus
                - 0.10 * risk
                - (
                    verifier.shock_penalty * shock_scale
                    if shocked
                    else 0.0
                ),
                0.05,
                0.98,
            )
        correct = rng.random() < accuracy
        out[verifier.name] = truth_good if correct else not truth_good
    return out


def select_verifiers(
    verifiers: Sequence[ave.Verifier],
    posteriors: Mapping[str, Sequence[float]],
    loads: Mapping[str, int],
    count: int,
    price: float,
    config: ave.Config,
    policy: Policy,
) -> List[ave.Verifier]:
    if count <= 0:
        return []
    if not policy.verifier_diversity:
        ranked = sorted(
            verifiers,
            key=lambda verifier: (
                ave.beta_mean(posteriors[verifier.name]),
                verifier.specificity,
                verifier.name,
            ),
            reverse=True,
        )
        return ranked[:count]
    return ave.select_verifiers(
        verifiers,
        posteriors,
        loads,
        count,
        price if policy.price_aware_routing else 0.0,
        config,
    )


def aggregate(
    selected: Sequence[ave.Verifier],
    verdicts: Mapping[str, bool],
    posteriors: Mapping[str, Sequence[float]],
    task: ave.Task,
    policy: Policy,
) -> bool:
    weights = [
        ave.beta_mean(posteriors[verifier.name])
        for verifier in selected
    ]
    acceptance_fraction = (
        sum(
            weight
            for verifier, weight in zip(selected, weights)
            if verdicts[verifier.name]
        )
        / max(ave.EPS, sum(weights))
    )
    if policy.risk_adaptive and task.risk >= 0.25:
        return acceptance_fraction >= 0.999999
    return acceptance_fraction >= 0.500001


def probe_verifiers(
    verifiers: Sequence[ave.Verifier],
    posteriors: Dict[str, List[float]],
    environment: Environment,
    config: ave.Config,
    rng: random.Random,
) -> Tuple[int, int, float]:
    verdicts = verifier_verdicts(
        verifiers,
        False,
        0.45,
        environment,
        rng,
        probe=True,
    )
    breaches = 0
    for verifier in verifiers:
        if verdicts[verifier.name]:
            posteriors[verifier.name][1] += 1.0
            breaches += 1
        else:
            posteriors[verifier.name][0] += 1.0
    cost = sum(config.probe_cost * verifier.cost for verifier in verifiers)
    return breaches, len(verifiers), cost


def task_family_concentration(
    counts: Mapping[Tuple[str, str], int],
) -> float:
    by_task: Dict[str, Dict[str, int]] = {}
    for (task, family), count in counts.items():
        by_task.setdefault(task, {})[family] = count
    weighted = 0.0
    total = 0
    for family_counts in by_task.values():
        task_total = sum(family_counts.values())
        if task_total:
            weighted += max(family_counts.values())
            total += task_total
    return weighted / total if total else 0.0


def run_policy(
    policy: Policy,
    environment: Environment,
    seed: int = 7,
    workers: int = 24,
    epochs: int = 50,
    verifier_count: int = 12,
    config: ave.Config | None = None,
) -> Dict[str, object]:
    if min(workers, epochs, verifier_count) <= 0:
        raise ValueError("workers, epochs, and verifier_count must be positive")

    config = config or ave.Config()
    rng = random.Random(seed)
    worker_pool = apply_worker_quality_imbalance(
        ave.make_workers(workers, rng),
        environment.worker_quality_imbalance,
    )
    verifiers = ave.make_verifiers(verifier_count, rng)
    route_posteriors: Dict[Tuple[str, str], List[float]] = {
        (worker.family, task.name): [2.0, 2.0]
        for worker in worker_pool
        for task in ave.TASKS
    }
    verifier_posteriors: Dict[str, List[float]] = {
        verifier.name: [3.0, 1.0]
        for verifier in verifiers
    }
    verifier_loads = {verifier.name: 0 for verifier in verifiers}
    verifier_family_counts = {verifier.family: 0 for verifier in verifiers}
    global_task_family_counts: Dict[Tuple[str, str], int] = {}
    task_good = {task.name: 0 for task in ave.TASKS}

    review_budget = (
        epochs
        * workers
        * config.capacity_per_worker
        * environment.review_capacity_scale
    )
    compute_budget = epochs * workers * 0.30

    review_cost = compute_cost = utility = escaped_risk = 0.0
    attempts = accepted = useful = escaped = false_rejects = duplicates = 0
    high_risk_escaped = probes = probe_breaches = budget_blocks = 0
    price = 0.0
    prices: List[float] = []
    temperatures: List[float] = []
    utilizations: List[float] = []

    for epoch in range(epochs):
        counts = {task.name: 0 for task in ave.TASKS}
        family_counts: Dict[Tuple[str, str], int] = {}
        outage_start = max(1, int(epochs * environment.outage_epoch_fraction))
        outage_active = epoch >= outage_start
        active_workers = (
            [worker for worker in worker_pool if worker.family != "worker-family-0"]
            if environment.worker_outage and outage_active
            else list(worker_pool)
        )
        active_verifiers = (
            [verifier for verifier in verifiers if verifier.family != "verifier-family-0"]
            if environment.verifier_outage and outage_active
            else list(verifiers)
        )
        worker_shocks = {
            worker.family: rng.random() < environment.worker_shock_rate
            for worker in active_workers
        }
        epoch_review = 0.0
        task_weights = workload_weights(epoch, epochs, environment)

        if (
            policy.probe_memory
            and epoch % config.probe_interval == 0
        ):
            expected_probe_cost = sum(
                config.probe_cost * verifier.cost
                for verifier in active_verifiers
            )
            if review_cost + expected_probe_cost <= review_budget:
                breach_count, probe_count, probe_cost = probe_verifiers(
                    active_verifiers,
                    verifier_posteriors,
                    environment,
                    config,
                    rng,
                )
                probe_breaches += breach_count
                probes += probe_count
                review_cost += probe_cost
                epoch_review += probe_cost

        temperature = route_temperature(
            route_posteriors,
            price,
            config,
            policy,
        )
        temperatures.append(temperature)

        order = list(active_workers)
        rng.shuffle(order)
        for worker in order:
            if policy.shadow_backpressure:
                dispatch_probability = max(
                    config.min_dispatch,
                    1.0 / (1.0 + config.backpressure * price),
                )
                if rng.random() > dispatch_probability:
                    continue

            task = route_task(
                worker,
                counts,
                family_counts,
                route_posteriors,
                price,
                temperature,
                config,
                policy,
                rng,
                task_weights,
            )
            same_family = family_counts.get(
                (task.name, worker.family),
                0,
            )
            if policy.risk_adaptive:
                danger_score = ave.danger(
                    task,
                    route_posteriors[(worker.family, task.name)],
                    same_family,
                )
                verifier_count_for_task = ave.verifier_floor(
                    task,
                    danger_score,
                )
            elif policy.verifier_diversity:
                verifier_count_for_task = 2
            else:
                verifier_count_for_task = 1

            selected = select_verifiers(
                active_verifiers,
                verifier_posteriors,
                verifier_loads,
                min(len(active_verifiers), verifier_count_for_task),
                price,
                config,
                policy,
            )
            estimated_review = sum(
                task.review * verifier.cost
                for verifier in selected
            )
            if (
                compute_cost + task.compute > compute_budget
                or review_cost + estimated_review > review_budget
            ):
                budget_blocks += 1
                continue

            truth_good, item_utility = candidate(
                worker,
                task,
                worker_shocks[worker.family],
                environment,
                rng,
            )
            verdict = verifier_verdicts(
                selected,
                truth_good,
                task.risk,
                environment,
                rng,
            )
            ok = aggregate(
                selected,
                verdict,
                verifier_posteriors,
                task,
                policy,
            )

            attempts += 1
            counts[task.name] += 1
            family_counts[(task.name, worker.family)] = same_family + 1
            global_key = (task.name, worker.family)
            global_task_family_counts[global_key] = (
                global_task_family_counts.get(global_key, 0) + 1
            )
            compute_cost += task.compute
            if counts[task.name] > task.limit:
                duplicates += 1

            for verifier in selected:
                verifier_loads[verifier.name] += 1
                verifier_family_counts[verifier.family] += 1
                cost = task.review * verifier.cost
                review_cost += cost
                epoch_review += cost

            if ok:
                accepted += 1
                if truth_good:
                    useful += 1
                    utility += item_utility
                    task_good[task.name] += 1
                else:
                    escaped += 1
                    escaped_risk += task.risk
                    if task.risk >= 0.50:
                        high_risk_escaped += 1
            elif truth_good:
                false_rejects += 1

            if policy.posterior_routing:
                route_posteriors[
                    (worker.family, task.name)
                ][0 if truth_good else 1] += 1.0

        utilization = epoch_review / max(
            ave.EPS,
            workers
            * config.capacity_per_worker
            * environment.review_capacity_scale,
        )
        utilizations.append(utilization)
        if policy.shadow_backpressure:
            price = ave.update_price(price, utilization, config)
        prices.append(price)

    total_cost = review_cost + compute_cost
    return {
        "policy": policy.name,
        "environment": environment.name,
        "attempts": attempts,
        "accepted": accepted,
        "budget_blocks": budget_blocks,
        "verified_utility_per_cost": round(
            utility / total_cost if total_cost else 0.0,
            9,
        ),
        "escaped_defects": escaped,
        "escaped_defect_rate": round(
            escaped / accepted if accepted else 0.0,
            6,
        ),
        "escaped_risk_weight": round(escaped_risk, 6),
        "high_risk_escaped_defects": high_risk_escaped,
        "false_reject_rate": round(
            false_rejects / (useful + false_rejects)
            if useful + false_rejects
            else 0.0,
            6,
        ),
        "duplicate_rate": round(
            duplicates / attempts if attempts else 0.0,
            6,
        ),
        "task_coverage": sum(
            1 for value in task_good.values() if value > 0
        ),
        "task_family_concentration": round(
            task_family_concentration(global_task_family_counts),
            6,
        ),
        "verifier_family_concentration": round(
            ave.concentration(verifier_family_counts),
            6,
        ),
        "review_cost": round(review_cost, 6),
        "compute_cost": round(compute_cost, 6),
        "review_budget": round(review_budget, 6),
        "compute_budget": round(compute_budget, 6),
        "review_budget_utilization": round(
            review_cost / review_budget if review_budget else 0.0,
            6,
        ),
        "compute_budget_utilization": round(
            compute_cost / compute_budget if compute_budget else 0.0,
            6,
        ),
        "review_utilization_mean": round(
            sum(utilizations) / len(utilizations),
            6,
        ),
        "review_price_mean": round(
            sum(prices) / len(prices),
            6,
        ),
        "temperature_mean": round(
            sum(temperatures) / len(temperatures),
            6,
        ),
        "probe_breach_rate": round(
            probe_breaches / probes if probes else 0.0,
            6,
        ),
    }


SUMMARY_METRICS = (
    "attempts",
    "budget_blocks",
    "verified_utility_per_cost",
    "escaped_defects",
    "escaped_defect_rate",
    "escaped_risk_weight",
    "high_risk_escaped_defects",
    "false_reject_rate",
    "duplicate_rate",
    "task_coverage",
    "task_family_concentration",
    "verifier_family_concentration",
    "review_cost",
    "compute_cost",
    "review_budget_utilization",
    "compute_budget_utilization",
    "review_utilization_mean",
    "review_price_mean",
    "temperature_mean",
    "probe_breach_rate",
)


def summarize(rows: Sequence[Mapping[str, object]]) -> Dict[str, float]:
    return {
        metric: round(
            sum(float(row[metric]) for row in rows) / len(rows),
            9,
        )
        for metric in SUMMARY_METRICS
    }


def sweep(
    seed_start: int = 1,
    seeds: int = 20,
    workers: int = 24,
    epochs: int = 50,
    verifier_count: int = 12,
    environment_names: Sequence[str] | None = None,
    policy_names: Sequence[str] | None = None,
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    environments = (
        [environment_by_name(name) for name in environment_names]
        if environment_names
        else list(ENVIRONMENTS)
    )
    policies = (
        [policy_by_name(name) for name in policy_names]
        if policy_names
        else list(POLICIES)
    )
    summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for environment in environments:
        summary[environment.name] = {}
        for policy in policies:
            rows = [
                run_policy(
                    policy,
                    environment,
                    seed=seed_start + offset,
                    workers=workers,
                    epochs=epochs,
                    verifier_count=verifier_count,
                )
                for offset in range(seeds)
            ]
            summary[environment.name][policy.name] = summarize(rows)

    return {
        "experiment": "adaptive-verification-ecology-ablation-v0",
        "model_warning": (
            "Synthetic matched-ceiling experiment; not empirical evidence."
        ),
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "verifiers": verifier_count,
        "policies": [asdict(policy) for policy in policies],
        "environments": [
            asdict(environment)
            for environment in environments
        ],
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--verifiers", type=int, default=12)
    parser.add_argument(
        "--environment",
        action="append",
        choices=tuple(
            environment.name for environment in ENVIRONMENTS
        ),
    )
    parser.add_argument(
        "--policy",
        action="append",
        choices=tuple(policy.name for policy in POLICIES),
    )
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)
    if min(args.seeds, args.workers, args.epochs, args.verifiers) <= 0:
        parser.error(
            "seeds, workers, epochs, and verifiers must be positive"
        )
    payload = sweep(
        seed_start=args.seed_start,
        seeds=args.seeds,
        workers=args.workers,
        epochs=args.epochs,
        verifier_count=args.verifiers,
        environment_names=args.environment,
        policy_names=args.policy,
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
