#!/usr/bin/env python3
"""Tiny deterministic simulator for IDKMesh ACE community reproduction.

This program is intentionally illustrative, not an empirical model of GitHub
communities. It turns a few equations from COMMUNITY_GROWTH_ENGINE.md into a
small executable experiment so assumptions can be challenged before more
repository automation is added.

The simulator compares two policies:

* governed: reproductive credit and spawning are suppressed by review load;
* raw:      spawning follows activity without the carrying-capacity gate.

With a fixed seed, output is reproducible. No network or third-party packages
are required.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
from collections import deque
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    initial_seeds: int
    steps: int
    review_capacity: int
    capacity_k: float
    tau: float
    decay: float
    spawn_rate: float
    verification_probability: float
    novelty_scale: float = 12.0


SCENARIOS: dict[str, Scenario] = {
    "under-reproduction": Scenario(
        name="under-reproduction",
        description="Low verification and reproduction cause useful activity to die out.",
        initial_seeds=8,
        steps=30,
        review_capacity=8,
        capacity_k=8.0,
        tau=2.0,
        decay=0.80,
        spawn_rate=0.55,
        verification_probability=0.48,
        novelty_scale=12.0,
    ),
    "healthy-reproduction": Scenario(
        name="healthy-reproduction",
        description="Useful activity reproduces while review load remains bounded.",
        initial_seeds=8,
        steps=30,
        review_capacity=8,
        capacity_k=8.0,
        tau=2.0,
        decay=0.90,
        spawn_rate=1.55,
        verification_probability=0.90,
        novelty_scale=160.0,
    ),
    "overload": Scenario(
        name="overload",
        description="Aggressive spawning can outrun verification capacity.",
        initial_seeds=12,
        steps=30,
        review_capacity=4,
        capacity_k=6.0,
        tau=1.5,
        decay=0.96,
        spawn_rate=2.00,
        verification_probability=0.86,
        novelty_scale=500.0,
    ),
}


@dataclass
class StepRecord:
    step: int
    policy: str
    open_seeds: int
    activity: int
    reviewed: int
    verified: int
    verified_descendants: int
    spawned: int
    review_load: int
    capacity: float
    novelty: float
    credit: float


@dataclass
class Summary:
    scenario: str
    policy: str
    seed: int
    steps: int
    total_activity: int
    total_reviewed: int
    total_verified: int
    verified_descendants: int
    eligible_verified_parents: int
    total_spawned: int
    final_open_seeds: int
    final_review_load: int
    peak_review_load: int
    mean_capacity: float
    r_community: float
    verified_per_activity: float
    verified_per_committed_work: float
    stable_review_load: bool


def capacity(review_load: int, k: float, tau: float) -> float:
    """Return the ACE logistic carrying-capacity gate."""
    if tau <= 0:
        raise ValueError("tau must be positive")
    z = (review_load - k) / tau
    if z > 60:
        return 0.0
    if z < -60:
        return 1.0
    return 1.0 / (1.0 + math.exp(z))


def stochastic_round(value: float, rng: random.Random) -> int:
    """Round a non-negative expectation without systematic floor bias."""
    if value <= 0:
        return 0
    base = math.floor(value)
    return base + (1 if rng.random() < value - base else 0)


def verified_count(reviewed: int, probability: float, rng: random.Random) -> int:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("verification_probability must be between 0 and 1")
    return sum(1 for _ in range(reviewed) if rng.random() < probability)


def run_scenario(
    scenario: Scenario, *, policy: str, seed: int
) -> tuple[list[StepRecord], Summary]:
    """Run one scenario/policy pair and return its step trace plus summary."""
    if policy not in {"governed", "raw"}:
        raise ValueError(f"unknown policy: {policy}")
    if scenario.initial_seeds < 0 or scenario.steps <= 0:
        raise ValueError("initial_seeds must be non-negative and steps must be positive")
    if scenario.review_capacity <= 0:
        raise ValueError("review_capacity must be positive")
    if scenario.spawn_rate <= 0 or scenario.novelty_scale <= 0:
        raise ValueError("spawn_rate and novelty_scale must be positive")
    if not 0.0 <= scenario.decay <= 1.0:
        raise ValueError("decay must be between 0 and 1")

    rng = random.Random(seed)
    open_root_seeds = scenario.initial_seeds
    open_descendant_seeds = 0
    # Queue entries are [count, is_descendant]. Batching keeps the model small
    # even if an override creates a large backlog.
    review_queue: deque[list[object]] = deque()
    review_load = 0
    credit = 0.0

    total_activity = 0
    total_reviewed = 0
    total_verified = 0
    total_verified_descendants = 0
    total_spawned = 0
    peak_review_load = 0
    capacities: list[float] = []
    records: list[StepRecord] = []

    for step in range(1, scenario.steps + 1):
        root_activity = open_root_seeds
        descendant_activity = open_descendant_seeds
        activity = root_activity + descendant_activity
        open_root_seeds = 0
        open_descendant_seeds = 0

        if root_activity:
            review_queue.append([root_activity, False])
        if descendant_activity:
            review_queue.append([descendant_activity, True])
        review_load += activity
        total_activity += activity

        remaining_review_capacity = scenario.review_capacity
        reviewed = 0
        verified = 0
        verified_descendants = 0
        while remaining_review_capacity > 0 and review_queue:
            batch = review_queue[0]
            batch_count = int(batch[0])
            is_descendant = bool(batch[1])
            take = min(batch_count, remaining_review_capacity)
            passed = verified_count(take, scenario.verification_probability, rng)

            reviewed += take
            verified += passed
            if is_descendant:
                verified_descendants += passed

            batch_count -= take
            remaining_review_capacity -= take
            review_load -= take
            if batch_count == 0:
                review_queue.popleft()
            else:
                batch[0] = batch_count

        total_reviewed += reviewed
        total_verified += verified
        total_verified_descendants += verified_descendants

        cap = capacity(review_load, scenario.capacity_k, scenario.tau)
        capacities.append(cap)
        novelty = 1.0 / math.sqrt(1.0 + total_spawned / scenario.novelty_scale)

        # ACE: Credit(t+1) = decay * Credit(t) + activity * novelty * Capacity(L)
        # "activity" is represented here by verified useful activity. The raw
        # comparator intentionally omits Capacity(L) to model activity-maximizing
        # growth without a carrying-capacity governor.
        credit_gate = cap if policy == "governed" else 1.0
        credit = scenario.decay * credit + verified * novelty * credit_gate

        # Credit is consumable: spawning a seed spends the budget that produced
        # it. The governed policy also checks current capacity at actuation time,
        # because opening follow-up work creates future review obligations.
        spawn_gate = cap if policy == "governed" else 1.0
        spawn_expectation = scenario.spawn_rate * credit * spawn_gate
        spawned = stochastic_round(spawn_expectation, rng)
        if spawned:
            credit = max(0.0, credit - spawned / scenario.spawn_rate)
        open_descendant_seeds += spawned
        total_spawned += spawned
        peak_review_load = max(peak_review_load, review_load)

        records.append(
            StepRecord(
                step=step,
                policy=policy,
                open_seeds=open_root_seeds + open_descendant_seeds,
                activity=activity,
                reviewed=reviewed,
                verified=verified,
                verified_descendants=verified_descendants,
                spawned=spawned,
                review_load=review_load,
                capacity=cap,
                novelty=novelty,
                credit=credit,
            )
        )

    # Parents verified during the final step have no future step in which their
    # descendants can verify, so they are excluded from the reproduction-window
    # denominator. This remains an illustrative finite-window R_community.
    final_step_verified = records[-1].verified if records else 0
    eligible_parents = max(0, total_verified - final_step_verified)
    r_community = (
        total_verified_descendants / eligible_parents if eligible_parents else 0.0
    )
    committed_work = total_activity + review_load

    summary = Summary(
        scenario=scenario.name,
        policy=policy,
        seed=seed,
        steps=scenario.steps,
        total_activity=total_activity,
        total_reviewed=total_reviewed,
        total_verified=total_verified,
        verified_descendants=total_verified_descendants,
        eligible_verified_parents=eligible_parents,
        total_spawned=total_spawned,
        final_open_seeds=open_root_seeds + open_descendant_seeds,
        final_review_load=review_load,
        peak_review_load=peak_review_load,
        mean_capacity=sum(capacities) / len(capacities),
        r_community=r_community,
        verified_per_activity=total_verified / total_activity if total_activity else 0.0,
        verified_per_committed_work=(
            total_verified / committed_work if committed_work else 0.0
        ),
        stable_review_load=review_load <= scenario.capacity_k,
    )
    return records, summary


def scenario_with_overrides(base: Scenario, args: argparse.Namespace) -> Scenario:
    values = asdict(base)
    for field, arg_name in (
        ("initial_seeds", "initial_seeds"),
        ("steps", "steps"),
        ("capacity_k", "k"),
        ("tau", "tau"),
        ("decay", "decay"),
        ("spawn_rate", "spawn_rate"),
        ("verification_probability", "verification_probability"),
        ("review_capacity", "review_capacity"),
        ("novelty_scale", "novelty_scale"),
    ):
        value = getattr(args, arg_name)
        if value is not None:
            values[field] = value
    return Scenario(**values)


def summary_dict(summary: Summary) -> dict[str, object]:
    data = asdict(summary)
    for key in (
        "mean_capacity",
        "r_community",
        "verified_per_activity",
        "verified_per_committed_work",
    ):
        data[key] = round(float(data[key]), 6)
    return data


def comparison(governed: Summary, raw: Summary) -> dict[str, object]:
    raw_is_busier = raw.total_activity > governed.total_activity
    raw_is_more_backlogged = raw.final_review_load > governed.final_review_load
    governed_is_more_efficient = (
        governed.verified_per_committed_work > raw.verified_per_committed_work
    )
    return {
        "scenario": governed.scenario,
        "raw_activity_minus_governed": raw.total_activity - governed.total_activity,
        "raw_final_review_load_minus_governed": (
            raw.final_review_load - governed.final_review_load
        ),
        "governed_efficiency_minus_raw": round(
            governed.verified_per_committed_work - raw.verified_per_committed_work,
            6,
        ),
        "raw_activity_can_be_worse": (
            raw_is_busier and raw_is_more_backlogged and governed_is_more_efficient
        ),
    }


def render_text(summaries: Iterable[Summary]) -> str:
    rows = list(summaries)
    lines: list[str] = []
    for summary in rows:
        lines.append(
            f"{summary.scenario:20} {summary.policy:8} "
            f"activity={summary.total_activity:4d} verified={summary.total_verified:3d} "
            f"R={summary.r_community:.3f} spawned={summary.total_spawned:4d} "
            f"open={summary.final_open_seeds:3d} final_load={summary.final_review_load:4d} "
            f"peak_load={summary.peak_review_load:4d} "
            f"eff={summary.verified_per_committed_work:.3f} "
            f"capacity={summary.mean_capacity:.3f}"
        )
    grouped: dict[str, dict[str, Summary]] = {}
    for summary in rows:
        grouped.setdefault(summary.scenario, {})[summary.policy] = summary
    for name, policies in grouped.items():
        if {"governed", "raw"} <= policies.keys():
            cmp = comparison(policies["governed"], policies["raw"])
            lines.append(
                f"  comparison[{name}]: raw_activity_can_be_worse="
                f"{str(cmp['raw_activity_can_be_worse']).lower()} "
                f"raw_extra_activity={cmp['raw_activity_minus_governed']} "
                f"raw_extra_final_load={cmp['raw_final_review_load_minus_governed']}"
            )
    return "\n".join(lines)


def render_json(summaries: Iterable[Summary]) -> str:
    rows = list(summaries)
    grouped: dict[str, dict[str, Summary]] = {}
    for summary in rows:
        grouped.setdefault(summary.scenario, {})[summary.policy] = summary
    comparisons = [
        comparison(policies["governed"], policies["raw"])
        for policies in grouped.values()
        if {"governed", "raw"} <= policies.keys()
    ]
    return json.dumps(
        {
            "model_note": "Illustrative ACE simulation; not empirical evidence.",
            "summaries": [summary_dict(item) for item in rows],
            "comparisons": comparisons,
        },
        indent=2,
        sort_keys=True,
    )


def render_csv(summaries: Iterable[Summary]) -> str:
    rows = [summary_dict(item) for item in summaries]
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().rstrip("\n")


def run_acceptance_checks(seed: int) -> None:
    """Fail fast if the default scenarios stop demonstrating their purpose."""
    under, _ = run_scenario(
        SCENARIOS["under-reproduction"], policy="governed", seed=seed
    )
    _, healthy_summary = run_scenario(
        SCENARIOS["healthy-reproduction"], policy="governed", seed=seed
    )
    _, overload_governed = run_scenario(
        SCENARIOS["overload"], policy="governed", seed=seed
    )
    _, overload_raw = run_scenario(
        SCENARIOS["overload"], policy="raw", seed=seed
    )

    if under[-1].open_seeds != 0 or under[-1].review_load != 0:
        raise AssertionError("under-reproduction should die out for the default seed")
    if healthy_summary.total_spawned <= SCENARIOS["healthy-reproduction"].initial_seeds:
        raise AssertionError(
            "healthy-reproduction should create verified follow-up opportunity"
        )
    if not healthy_summary.stable_review_load:
        raise AssertionError("healthy-reproduction should keep final review load within K")
    cmp = comparison(overload_governed, overload_raw)
    if not cmp["raw_activity_can_be_worse"]:
        raise AssertionError(
            "overload should demonstrate that more raw activity can create worse review pressure"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS],
        default="all",
        help="Scenario to run (default: all).",
    )
    parser.add_argument(
        "--policy",
        choices=["both", "governed", "raw"],
        default="both",
        help="Growth policy to compare (default: both).",
    )
    parser.add_argument("--seed", type=int, default=20260828, help="Random seed.")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run default acceptance checks before printing results.",
    )
    parser.add_argument(
        "--initial-seeds", type=int, help="Override initial Growth Seeds."
    )
    parser.add_argument("--steps", type=int, help="Override number of simulation steps.")
    parser.add_argument("--k", type=float, help="Override logistic carrying-capacity K.")
    parser.add_argument("--tau", type=float, help="Override logistic temperature tau.")
    parser.add_argument("--decay", type=float, help="Override reproductive-credit decay.")
    parser.add_argument("--spawn-rate", type=float, help="Override seed spawn rate.")
    parser.add_argument(
        "--verification-probability",
        type=float,
        help="Override probability that a reviewed activity verifies.",
    )
    parser.add_argument(
        "--review-capacity", type=int, help="Override reviews processable per step."
    )
    parser.add_argument(
        "--novelty-scale", type=float, help="Override diminishing-novelty scale."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        run_acceptance_checks(args.seed)

    selected = (
        SCENARIOS.values()
        if args.scenario == "all"
        else [SCENARIOS[args.scenario]]
    )
    policies = ["governed", "raw"] if args.policy == "both" else [args.policy]

    summaries: list[Summary] = []
    for base in selected:
        scenario = scenario_with_overrides(base, args)
        for policy in policies:
            _, summary = run_scenario(scenario, policy=policy, seed=args.seed)
            summaries.append(summary)

    if args.format == "json":
        print(render_json(summaries))
    elif args.format == "csv":
        print(render_csv(summaries))
    else:
        print(render_text(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
