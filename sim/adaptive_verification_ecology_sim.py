#!/usr/bin/env python3
"""Deterministic synthetic simulator for Adaptive Verification Ecology (AVE).

Research only: this model is not empirical evidence about real agents or reviewers.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

EPS = 1e-12


@dataclass(frozen=True)
class Task:
    name: str
    skill: str
    value: float
    review: float
    compute: float
    risk: float
    success: float
    limit: int


@dataclass(frozen=True)
class Worker:
    name: str
    family: str
    skills: Mapping[str, float]


@dataclass(frozen=True)
class Verifier:
    name: str
    family: str
    specificity: float
    shock_rate: float
    shock_penalty: float
    cost: float


@dataclass(frozen=True)
class Config:
    temp_base: float = 0.42
    temp_min: float = 0.12
    temp_max: float = 1.10
    temp_uncertainty_gain: float = 1.40
    temp_price_cooling: float = 0.16
    niche_pressure: float = 0.85
    price_gain: float = 0.32
    price_max: float = 4.0
    utilization_target: float = 0.82
    capacity_per_worker: float = 0.62
    backpressure: float = 0.55
    min_dispatch: float = 0.32
    repeat_family_penalty: float = 0.28
    verifier_load_penalty: float = 0.12
    probe_interval: int = 4
    probe_cost: float = 0.06


TASKS: Tuple[Task, ...] = (
    Task("schema", "code", 0.72, 0.35, 0.28, 0.25, 0.74, 3),
    Task("validator", "test", 0.76, 0.48, 0.36, 0.34, 0.67, 3),
    Task("security", "security", 0.81, 0.60, 0.25, 0.55, 0.55, 2),
    Task("docs", "docs", 0.55, 0.16, 0.08, 0.08, 0.88, 4),
    Task("benchmark", "research", 0.78, 0.42, 0.33, 0.22, 0.63, 3),
    Task("integration", "code", 0.68, 0.58, 0.47, 0.46, 0.57, 2),
    Task("onboarding", "community", 0.50, 0.18, 0.06, 0.06, 0.90, 4),
    Task("reproduction", "test", 0.66, 0.29, 0.18, 0.13, 0.78, 3),
)
SKILLS = ("code", "test", "security", "docs", "research", "community")
STRATEGIES = ("capability-static", "diversity-static", "ave")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def beta_mean(ab: Sequence[float]) -> float:
    return float(ab[0]) / (float(ab[0]) + float(ab[1]))


def beta_std(ab: Sequence[float]) -> float:
    a, b = float(ab[0]), float(ab[1])
    s = a + b
    return math.sqrt(a * b / (s * s * (s + 1.0)))


def softmax(xs: Sequence[float], temp: float) -> List[float]:
    m = max(xs)
    ws = [math.exp((x - m) / max(temp, EPS)) for x in xs]
    z = sum(ws)
    return [w / z for w in ws]


def choose(items: Sequence[Task], ps: Sequence[float], rng: random.Random) -> Task:
    x, c = rng.random(), 0.0
    for item, p in zip(items, ps):
        c += p
        if x <= c:
            return item
    return items[-1]


def make_workers(n: int, rng: random.Random) -> List[Worker]:
    families = max(3, min(7, n // 4 or 1))
    out = []
    for i in range(n):
        specialty = SKILLS[i % len(SKILLS)]
        skills = {
            s: rng.uniform(0.72, 0.98) if s == specialty else rng.uniform(0.18, 0.70)
            for s in SKILLS
        }
        out.append(Worker(f"worker-{i:03d}", f"worker-family-{i % families}", skills))
    return out


def make_verifiers(n: int, rng: random.Random) -> List[Verifier]:
    families = max(3, min(5, n // 3 or 1))
    return [
        Verifier(
            f"verifier-{i:03d}",
            f"verifier-family-{i % families}",
            rng.uniform(0.76, 0.94),
            0.08 + 0.035 * (i % families),
            rng.uniform(0.30, 0.48),
            rng.uniform(0.82, 1.18),
        )
        for i in range(n)
    ]


def update_price(price: float, utilization: float, cfg: Config) -> float:
    return clamp(
        price + cfg.price_gain * (utilization - cfg.utilization_target),
        0.0,
        cfg.price_max,
    )


def route_temperature(
    posteriors: Mapping[Tuple[str, str], Sequence[float]],
    price: float,
    cfg: Config,
) -> float:
    uncertainty = sum(beta_std(v) for v in posteriors.values()) / len(posteriors)
    return clamp(
        cfg.temp_base
        + cfg.temp_uncertainty_gain * uncertainty
        - cfg.temp_price_cooling * price,
        cfg.temp_min,
        cfg.temp_max,
    )


def route_task(
    strategy: str,
    worker: Worker,
    counts: Mapping[str, int],
    family_counts: Mapping[Tuple[str, str], int],
    posteriors: Mapping[Tuple[str, str], Sequence[float]],
    price: float,
    temp: float,
    cfg: Config,
    rng: random.Random,
) -> Task:
    def base_score(task: Task, learned: float) -> float:
        skill = clamp(float(worker.skills[task.skill]), 0.02, 1.0)
        same = family_counts.get((task.name, worker.family), 0)
        niche = (1.0 + same) ** (-cfg.niche_pressure)
        congestion = (1.0 + counts.get(task.name, 0)) ** (-0.55)
        scarcity = 1.0 + price * task.review
        return max(
            EPS,
            task.value * skill * learned * niche * congestion / scarcity,
        )

    if strategy == "capability-static":
        return max(
            TASKS,
            key=lambda t: (
                worker.skills[t.skill] * t.value / (1 + t.review),
                t.name,
            ),
        )
    if strategy == "diversity-static":
        return max(TASKS, key=lambda t: (base_score(t, 0.5), t.name))

    logits = []
    for task in TASKS:
        ab = posteriors[(worker.family, task.name)]
        sampled = rng.betavariate(float(ab[0]), float(ab[1]))
        logits.append(math.log(base_score(task, sampled)))
    return choose(TASKS, softmax(logits, temp), rng)


def candidate(worker: Worker, task: Task, rng: random.Random) -> Tuple[bool, float]:
    skill = clamp(float(worker.skills[task.skill]), 0.0, 1.0)
    good = rng.random() < clamp(task.success * (0.45 + 0.70 * skill), 0.05, 0.97)
    return good, task.value * (0.60 + 0.40 * skill) if good else 0.0


def verdicts(
    selected: Sequence[Verifier],
    truth_good: bool,
    risk: float,
    rng: random.Random,
) -> Dict[str, bool]:
    shocks = {v.family: rng.random() < v.shock_rate for v in selected}
    out: Dict[str, bool] = {}
    for v in selected:
        if truth_good:
            # The first environment is intentionally partial-test-like: errors
            # are mostly missed defects, as in E017. This is not a universal
            # model of real verifiers.
            accuracy = clamp(
                0.985 - 0.02 * risk - (0.02 if shocks[v.family] else 0.0),
                0.90,
                0.995,
            )
        else:
            accuracy = clamp(
                v.specificity
                - 0.10 * risk
                - (v.shock_penalty if shocks[v.family] else 0.0),
                0.05,
                0.98,
            )
        correct = rng.random() < accuracy
        out[v.name] = truth_good if correct else not truth_good
    return out


def danger(task: Task, posterior: Sequence[float], same_family: int) -> float:
    pressure = min(1.0, same_family / max(1, task.limit))
    uncertainty = min(1.0, beta_std(posterior) / 0.25)
    return clamp(
        0.55 * task.risk
        + 0.25 * (1 - beta_mean(posterior))
        + 0.15 * pressure
        + 0.05 * uncertainty,
        0.0,
        1.0,
    )


def verifier_floor(task: Task, d: float) -> int:
    if task.risk >= 0.50 or d >= 0.65:
        return 3
    if task.risk >= 0.25 or d >= 0.30:
        return 2
    return 1


def select_verifiers(
    verifiers: Sequence[Verifier],
    post: Mapping[str, Sequence[float]],
    loads: Mapping[str, int],
    count: int,
    price: float,
    cfg: Config,
) -> List[Verifier]:
    chosen: List[Verifier] = []
    remaining = list(verifiers)
    while remaining and len(chosen) < count:
        families = {v.family for v in chosen}

        def score(v: Verifier) -> float:
            family = cfg.repeat_family_penalty if v.family in families else 1.0
            load = 1.0 / (1.0 + cfg.verifier_load_penalty * loads.get(v.name, 0))
            return beta_mean(post[v.name]) * family * load / (1.0 + price * v.cost)

        best = max(remaining, key=lambda v: (score(v), v.name))
        chosen.append(best)
        remaining.remove(best)
    return chosen


def aggregate(
    selected: Sequence[Verifier],
    vs: Mapping[str, bool],
    post: Mapping[str, Sequence[float]],
    risk: float,
    strategy: str,
) -> bool:
    weights = [
        beta_mean(post[v.name]) if strategy == "ave" else v.specificity
        for v in selected
    ]
    accepted = (
        sum(w for v, w in zip(selected, weights) if vs[v.name])
        / max(EPS, sum(weights))
    )
    threshold = 0.999999 if strategy == "ave" and risk >= 0.25 else 0.500001
    return accepted >= threshold


def probe(
    verifiers: Sequence[Verifier],
    post: Dict[str, List[float]],
    rng: random.Random,
    cfg: Config,
) -> Tuple[int, int, float]:
    vs = verdicts(verifiers, False, 0.45, rng)
    breaches = 0
    for v in verifiers:
        if vs[v.name]:
            post[v.name][1] += 1.0
            breaches += 1
        else:
            post[v.name][0] += 1.0
    return (
        breaches,
        len(verifiers),
        sum(cfg.probe_cost * v.cost for v in verifiers),
    )


def concentration(counts: Mapping[str, int]) -> float:
    total = sum(counts.values())
    return max(counts.values()) / total if total else 0.0


def run(
    strategy: str,
    seed: int = 7,
    workers: int = 24,
    epochs: int = 50,
    verifier_count: int = 12,
    cfg: Config | None = None,
) -> Dict[str, object]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if min(workers, epochs, verifier_count) <= 0:
        raise ValueError("workers, epochs, and verifier_count must be positive")

    cfg = cfg or Config()
    rng = random.Random(seed)
    ws = make_workers(workers, rng)
    verifiers = make_verifiers(verifier_count, rng)
    route_post = {
        (w.family, t.name): [2.0, 2.0]
        for w in ws
        for t in TASKS
    }
    verifier_post = {v.name: [3.0, 1.0] for v in verifiers}

    fixed = [verifiers[0]]
    diverse: List[Verifier] = []
    for v in verifiers:
        if v.family not in {x.family for x in diverse}:
            diverse.append(v)
        if len(diverse) == min(2, len(verifiers)):
            break

    price = 0.0
    attempts = accepted = useful = escaped = false_rejects = duplicates = 0
    probes = breaches = 0
    utility = review_cost = compute_cost = escaped_risk = 0.0
    high_risk_escaped = 0
    prices: List[float] = []
    temps: List[float] = []
    utils: List[float] = []
    task_good = {t.name: 0 for t in TASKS}
    vf = {v.family: 0 for v in verifiers}
    loads = {v.name: 0 for v in verifiers}

    for epoch in range(epochs):
        counts = {t.name: 0 for t in TASKS}
        family_counts: Dict[Tuple[str, str], int] = {}
        epoch_review = 0.0

        if strategy == "ave" and epoch % cfg.probe_interval == 0:
            b, p, c = probe(verifiers, verifier_post, rng, cfg)
            breaches += b
            probes += p
            review_cost += c
            epoch_review += c

        temp = (
            route_temperature(route_post, price, cfg)
            if strategy == "ave"
            else cfg.temp_min
        )
        temps.append(temp)

        order = list(ws)
        rng.shuffle(order)
        for w in order:
            if strategy == "ave":
                dispatch = max(
                    cfg.min_dispatch,
                    1.0 / (1.0 + cfg.backpressure * price),
                )
                if rng.random() > dispatch:
                    continue

            task = route_task(
                strategy,
                w,
                counts,
                family_counts,
                route_post,
                price if strategy == "ave" else 0.0,
                temp,
                cfg,
                rng,
            )
            same = family_counts.get((task.name, w.family), 0)
            truth, item_utility = candidate(w, task, rng)

            if strategy == "capability-static":
                chosen = fixed
            elif strategy == "diversity-static":
                chosen = diverse
            else:
                d = danger(task, route_post[(w.family, task.name)], same)
                chosen = select_verifiers(
                    verifiers,
                    verifier_post,
                    loads,
                    min(len(verifiers), verifier_floor(task, d)),
                    price,
                    cfg,
                )

            vs = verdicts(chosen, truth, task.risk, rng)
            ok = aggregate(chosen, vs, verifier_post, task.risk, strategy)

            attempts += 1
            counts[task.name] += 1
            family_counts[(task.name, w.family)] = same + 1
            compute_cost += task.compute
            if counts[task.name] > task.limit:
                duplicates += 1

            for v in chosen:
                loads[v.name] += 1
                vf[v.family] += 1
                c = task.review * v.cost
                review_cost += c
                epoch_review += c

            if ok:
                accepted += 1
                if truth:
                    useful += 1
                    utility += item_utility
                    task_good[task.name] += 1
                else:
                    escaped += 1
                    escaped_risk += task.risk
                    if task.risk >= 0.50:
                        high_risk_escaped += 1
            elif truth:
                false_rejects += 1

            if strategy == "ave":
                route_post[(w.family, task.name)][0 if ok else 1] += 1.0

        utilization = epoch_review / max(EPS, workers * cfg.capacity_per_worker)
        utils.append(utilization)
        if strategy == "ave":
            price = update_price(price, utilization, cfg)
        prices.append(price)

    total_cost = review_cost + compute_cost
    return {
        "strategy": strategy,
        "attempts": attempts,
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
        "task_coverage": sum(1 for x in task_good.values() if x > 0),
        "verifier_family_concentration": round(concentration(vf), 6),
        "review_cost": round(review_cost, 6),
        "compute_cost": round(compute_cost, 6),
        "review_utilization_mean": round(sum(utils) / len(utils), 6),
        "review_price_mean": round(sum(prices) / len(prices), 6),
        "temperature_mean": round(sum(temps) / len(temps), 6),
        "probe_breach_rate": round(
            breaches / probes if probes else 0.0,
            6,
        ),
    }


def compare(
    seed_start: int = 1,
    seeds: int = 40,
    workers: int = 24,
    epochs: int = 50,
    verifier_count: int = 12,
    cfg: Config | None = None,
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    cfg = cfg or Config()
    rows = {
        strategy: [
            run(
                strategy,
                seed_start + i,
                workers,
                epochs,
                verifier_count,
                cfg,
            )
            for i in range(seeds)
        ]
        for strategy in STRATEGIES
    }
    metrics = (
        "verified_utility_per_cost",
        "escaped_defects",
        "escaped_defect_rate",
        "escaped_risk_weight",
        "high_risk_escaped_defects",
        "false_reject_rate",
        "duplicate_rate",
        "task_coverage",
        "verifier_family_concentration",
        "review_cost",
        "compute_cost",
        "review_utilization_mean",
    )
    summary = {
        strategy: {
            metric: round(
                sum(float(row[metric]) for row in strategy_rows)
                / len(strategy_rows),
                9,
            )
            for metric in metrics
        }
        for strategy, strategy_rows in rows.items()
    }
    return {
        "experiment": "adaptive-verification-ecology-v0",
        "model_warning": (
            "Synthetic illustrative simulation; not empirical evidence."
        ),
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "verifiers": verifier_count,
        "config": asdict(cfg),
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        choices=("all",) + STRATEGIES,
        default="all",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--verifiers", type=int, default=12)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if min(args.seeds, args.workers, args.epochs, args.verifiers) <= 0:
        parser.error("seeds, workers, epochs, and verifiers must be positive")

    payload = (
        compare(
            args.seed_start,
            args.seeds,
            args.workers,
            args.epochs,
            args.verifiers,
        )
        if args.strategy == "all"
        else run(
            args.strategy,
            args.seed,
            args.workers,
            args.epochs,
            args.verifiers,
        )
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
