#!/usr/bin/env python3
"""Deterministic ACE population experiment using the live-open-work capacity model.

This is an illustrative scientific toy model, not empirical evidence about real
GitHub communities and not an ACE actuation component.

It compares:
- governed: verified useful work earns reproductive credit multiplied by the
  canonical live-open-work carrying-capacity gate;
- raw: the same reproduction rule omits the carrying-capacity gate.

The model intentionally represents current open work as four recoverable state
components rather than accumulating historical GitHub events.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class OpenWorkState:
    ready_prs: int = 0
    draft_prs: int = 0
    open_growth_seeds: int = 0
    other_open_issues: int = 0


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    initial_seeds: int
    steps: int
    other_open_issues: int
    review_slots: int
    capacity_k: float
    tau: float
    decay: float
    spawn_rate: float
    activation_probability: float
    draft_ready_probability: float
    verification_probability: float
    novelty_scale: float = 50.0


@dataclass
class StepRecord:
    step: int
    policy: str
    activated_seeds: int
    promoted_prs: int
    reviewed_prs: int
    verified_descendants: int
    spawned_seeds: int
    open_work: OpenWorkState
    review_load: float
    capacity: float
    credit: float


@dataclass
class Summary:
    scenario: str
    policy: str
    seed: int
    steps: int
    total_candidate_activations: int
    total_spawned_seeds: int
    total_public_activity: int
    total_reviewed_prs: int
    total_verified_descendants: int
    eligible_matured_parents: int
    final_open_work: OpenWorkState
    final_review_load: float
    peak_review_load: float
    mean_capacity: float
    r_community: float
    stable_final_load: bool


SCENARIOS: dict[str, Scenario] = {
    "under-reproduction": Scenario(
        name="under-reproduction",
        description="Low verification/reproduction causes follow-up work to die out.",
        initial_seeds=8,
        steps=30,
        other_open_issues=2,
        review_slots=8,
        capacity_k=8.0,
        tau=2.0,
        decay=0.80,
        spawn_rate=0.45,
        activation_probability=0.65,
        draft_ready_probability=0.80,
        verification_probability=0.45,
        novelty_scale=20.0,
    ),
    "healthy-reproduction": Scenario(
        name="healthy-reproduction",
        description="Verified work reproduces while current open-work pressure stays bounded.",
        initial_seeds=8,
        steps=40,
        other_open_issues=4,
        review_slots=8,
        capacity_k=8.0,
        tau=2.0,
        decay=0.90,
        spawn_rate=1.20,
        activation_probability=0.75,
        draft_ready_probability=0.90,
        verification_probability=0.90,
        novelty_scale=100.0,
    ),
    "overload": Scenario(
        name="overload",
        description="Unconstrained reproduction creates open work faster than review can clear it.",
        initial_seeds=12,
        steps=40,
        other_open_issues=10,
        review_slots=4,
        capacity_k=8.0,
        tau=2.0,
        decay=0.96,
        spawn_rate=1.80,
        activation_probability=0.90,
        draft_ready_probability=0.95,
        verification_probability=0.90,
        novelty_scale=500.0,
    ),
}


def _require_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def live_review_load(state: OpenWorkState) -> float:
    """Return the canonical ACE live-open-work-v1 load.

    L = 1.00 * ready PRs
      + 0.25 * draft PRs
      + 0.50 * open Growth Seeds
      + 0.10 * min(other open human-facing issues, 20)
    """
    _require_non_negative_int(state.ready_prs, "ready_prs")
    _require_non_negative_int(state.draft_prs, "draft_prs")
    _require_non_negative_int(state.open_growth_seeds, "open_growth_seeds")
    _require_non_negative_int(state.other_open_issues, "other_open_issues")
    return (
        1.00 * state.ready_prs
        + 0.25 * state.draft_prs
        + 0.50 * state.open_growth_seeds
        + 0.10 * min(state.other_open_issues, 20)
    )


def capacity(review_load: float, k: float, tau: float) -> float:
    """Return the ACE logistic carrying-capacity multiplier."""
    if tau <= 0:
        raise ValueError("tau must be positive")
    if not math.isfinite(review_load) or review_load < 0:
        raise ValueError("review_load must be a finite non-negative number")
    if not math.isfinite(k):
        raise ValueError("k must be finite")
    z = (review_load - k) / tau
    if z > 60:
        return 0.0
    if z < -60:
        return 1.0
    return 1.0 / (1.0 + math.exp(z))


def stochastic_count(count: int, probability: float, rng: random.Random) -> int:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    _require_non_negative_int(count, "count")
    return sum(1 for _ in range(count) if rng.random() < probability)


def stochastic_round(value: float, rng: random.Random) -> int:
    if not math.isfinite(value) or value < 0:
        raise ValueError("value must be a finite non-negative number")
    base = math.floor(value)
    return base + (1 if rng.random() < value - base else 0)


def validate_scenario(scenario: Scenario) -> None:
    _require_non_negative_int(scenario.initial_seeds, "initial_seeds")
    _require_non_negative_int(scenario.other_open_issues, "other_open_issues")
    if scenario.steps <= 0:
        raise ValueError("steps must be positive")
    if scenario.review_slots <= 0:
        raise ValueError("review_slots must be positive")
    if scenario.capacity_k < 0:
        raise ValueError("capacity_k must be non-negative")
    if scenario.tau <= 0:
        raise ValueError("tau must be positive")
    if not 0.0 <= scenario.decay <= 1.0:
        raise ValueError("decay must be between 0 and 1")
    if scenario.spawn_rate <= 0 or scenario.novelty_scale <= 0:
        raise ValueError("spawn_rate and novelty_scale must be positive")
    for value, name in (
        (scenario.activation_probability, "activation_probability"),
        (scenario.draft_ready_probability, "draft_ready_probability"),
        (scenario.verification_probability, "verification_probability"),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")


def run_scenario(
    scenario: Scenario, *, policy: str, seed: int
) -> tuple[list[StepRecord], Summary]:
    """Run one scenario/policy pair and return its trace plus summary.

    Each Growth Seed can produce at most one candidate PR in this toy model.
    Once that candidate reaches a terminal review outcome, its seed counts as an
    eligible matured parent. A successful independent review is a verified
    descendant. New seeds are created only from verified-useful-work credit.

    Historical event counts are deliberately absent from the state.
    """
    validate_scenario(scenario)
    if policy not in {"governed", "raw"}:
        raise ValueError(f"unknown policy: {policy}")

    activation_rng = random.Random(f"{seed}:activation")
    promotion_rng = random.Random(f"{seed}:promotion")
    verification_rng = random.Random(f"{seed}:verification")
    spawn_rng = random.Random(f"{seed}:{policy}:spawn")

    open_seeds = scenario.initial_seeds
    draft_prs = 0
    ready_prs = 0
    credit = 0.0

    total_candidate_activations = 0
    total_spawned = 0
    total_reviewed = 0
    total_verified = 0
    loads: list[float] = []
    capacities: list[float] = []
    records: list[StepRecord] = []

    for step in range(1, scenario.steps + 1):
        activated = stochastic_count(
            open_seeds, scenario.activation_probability, activation_rng
        )
        open_seeds -= activated
        draft_prs += activated
        total_candidate_activations += activated

        promoted = stochastic_count(
            draft_prs, scenario.draft_ready_probability, promotion_rng
        )
        draft_prs -= promoted
        ready_prs += promoted

        reviewed = min(ready_prs, scenario.review_slots)
        ready_prs -= reviewed
        verified = stochastic_count(
            reviewed, scenario.verification_probability, verification_rng
        )
        total_reviewed += reviewed
        total_verified += verified

        # Reproductive credit is based on verified useful output, not raw GitHub
        # activity. The governed comparator applies the canonical capacity gate.
        decision_state = OpenWorkState(
            ready_prs=ready_prs,
            draft_prs=draft_prs,
            open_growth_seeds=open_seeds,
            other_open_issues=scenario.other_open_issues,
        )
        decision_load = live_review_load(decision_state)
        decision_capacity = capacity(
            decision_load, scenario.capacity_k, scenario.tau
        )
        novelty = 1.0 / math.sqrt(
            1.0 + total_spawned / scenario.novelty_scale
        )
        credit_gate = decision_capacity if policy == "governed" else 1.0
        credit = (
            scenario.decay * credit
            + verified * novelty * credit_gate
        )

        spawned = stochastic_round(scenario.spawn_rate * credit, spawn_rng)
        if spawned:
            credit = max(0.0, credit - spawned / scenario.spawn_rate)
        open_seeds += spawned
        total_spawned += spawned

        # Telemetry is end-of-step current state, including newly opened seeds.
        open_work = OpenWorkState(
            ready_prs=ready_prs,
            draft_prs=draft_prs,
            open_growth_seeds=open_seeds,
            other_open_issues=scenario.other_open_issues,
        )
        end_load = live_review_load(open_work)
        end_capacity = capacity(end_load, scenario.capacity_k, scenario.tau)
        loads.append(end_load)
        capacities.append(end_capacity)

        records.append(
            StepRecord(
                step=step,
                policy=policy,
                activated_seeds=activated,
                promoted_prs=promoted,
                reviewed_prs=reviewed,
                verified_descendants=verified,
                spawned_seeds=spawned,
                open_work=open_work,
                review_load=end_load,
                capacity=end_capacity,
                credit=credit,
            )
        )

    final_open_work = records[-1].open_work
    final_load = records[-1].review_load
    eligible_matured_parents = total_reviewed
    r_community = (
        total_verified / eligible_matured_parents
        if eligible_matured_parents
        else 0.0
    )
    summary = Summary(
        scenario=scenario.name,
        policy=policy,
        seed=seed,
        steps=scenario.steps,
        total_candidate_activations=total_candidate_activations,
        total_spawned_seeds=total_spawned,
        total_public_activity=total_candidate_activations + total_spawned,
        total_reviewed_prs=total_reviewed,
        total_verified_descendants=total_verified,
        eligible_matured_parents=eligible_matured_parents,
        final_open_work=final_open_work,
        final_review_load=final_load,
        peak_review_load=max(loads),
        mean_capacity=sum(capacities) / len(capacities),
        r_community=r_community,
        stable_final_load=final_load <= scenario.capacity_k,
    )
    return records, summary


def summary_dict(summary: Summary) -> dict[str, object]:
    data = asdict(summary)
    for key in ("final_review_load", "peak_review_load", "mean_capacity", "r_community"):
        data[key] = round(float(data[key]), 6)
    return data


def comparison(governed: Summary, raw: Summary) -> dict[str, object]:
    if governed.scenario != raw.scenario:
        raise ValueError("summaries must come from the same scenario")
    raw_extra_activity = raw.total_public_activity - governed.total_public_activity
    raw_extra_load = raw.final_review_load - governed.final_review_load
    return {
        "scenario": governed.scenario,
        "raw_activity_minus_governed": raw_extra_activity,
        "raw_final_review_load_minus_governed": round(raw_extra_load, 6),
        "raw_reviewed_prs_minus_governed": (
            raw.total_reviewed_prs - governed.total_reviewed_prs
        ),
        "raw_verified_descendants_minus_governed": (
            raw.total_verified_descendants - governed.total_verified_descendants
        ),
        "raw_activity_can_be_worse": (
            raw_extra_activity > 0
            and raw_extra_load > 0
            and raw.total_reviewed_prs <= governed.total_reviewed_prs
        ),
    }


def render_text(summaries: Iterable[Summary]) -> str:
    rows = list(summaries)
    lines: list[str] = []
    for item in rows:
        lines.append(
            f"{item.scenario:20} {item.policy:8} "
            f"activity={item.total_public_activity:4d} "
            f"reviewed={item.total_reviewed_prs:3d} "
            f"verified={item.total_verified_descendants:3d} "
            f"R={item.r_community:.3f} "
            f"final_load={item.final_review_load:7.2f} "
            f"peak_load={item.peak_review_load:7.2f} "
            f"mean_capacity={item.mean_capacity:.3f}"
        )
    grouped: dict[str, dict[str, Summary]] = {}
    for item in rows:
        grouped.setdefault(item.scenario, {})[item.policy] = item
    for name, policies in grouped.items():
        if {"governed", "raw"} <= policies.keys():
            cmp = comparison(policies["governed"], policies["raw"])
            lines.append(
                f"  comparison[{name}]: "
                f"raw_activity_can_be_worse={str(cmp['raw_activity_can_be_worse']).lower()} "
                f"raw_extra_activity={cmp['raw_activity_minus_governed']} "
                f"raw_extra_final_load={cmp['raw_final_review_load_minus_governed']}"
            )
    return "\n".join(lines)


def render_json(summaries: Iterable[Summary]) -> str:
    rows = list(summaries)
    grouped: dict[str, dict[str, Summary]] = {}
    for item in rows:
        grouped.setdefault(item.scenario, {})[item.policy] = item
    comparisons = [
        comparison(policies["governed"], policies["raw"])
        for policies in grouped.values()
        if {"governed", "raw"} <= policies.keys()
    ]
    return json.dumps(
        {
            "model": "ACE live-open-work population experiment v1",
            "model_note": "Illustrative simulation; not empirical community evidence or actuation authority.",
            "capacity_formula": (
                "L = 1.00*ready_prs + 0.25*draft_prs + "
                "0.50*open_growth_seeds + 0.10*min(other_open_issues,20)"
            ),
            "summaries": [summary_dict(item) for item in rows],
            "comparisons": comparisons,
        },
        indent=2,
        sort_keys=True,
    )


def render_csv(summaries: Iterable[Summary]) -> str:
    rows: list[dict[str, object]] = []
    for item in summaries:
        row = summary_dict(item)
        open_work = row.pop("final_open_work")
        assert isinstance(open_work, dict)
        for key, value in open_work.items():
            row[f"final_{key}"] = value
        rows.append(row)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().rstrip("\n")


def run_acceptance_checks(seed: int) -> None:
    """Assert the default scenarios still demonstrate their intended regimes."""
    high = OpenWorkState(
        ready_prs=12, draft_prs=4, open_growth_seeds=4, other_open_issues=50
    )
    low = OpenWorkState(
        ready_prs=2, draft_prs=1, open_growth_seeds=1, other_open_issues=10
    )
    high_load = live_review_load(high)
    low_load = live_review_load(low)
    if not low_load < high_load:
        raise AssertionError("closing open work must reduce live review pressure")
    if not capacity(low_load, 8.0, 2.0) > capacity(high_load, 8.0, 2.0):
        raise AssertionError("capacity must recover when current pressure falls")
    capped_20 = live_review_load(OpenWorkState(other_open_issues=20))
    capped_200 = live_review_load(OpenWorkState(other_open_issues=200))
    if capped_20 != capped_200:
        raise AssertionError("ordinary-issue contribution must remain capped at 20")

    _, under = run_scenario(
        SCENARIOS["under-reproduction"], policy="governed", seed=seed
    )
    _, healthy = run_scenario(
        SCENARIOS["healthy-reproduction"], policy="governed", seed=seed
    )
    _, overload_governed = run_scenario(
        SCENARIOS["overload"], policy="governed", seed=seed
    )
    _, overload_raw = run_scenario(
        SCENARIOS["overload"], policy="raw", seed=seed
    )

    active_under = (
        under.final_open_work.ready_prs
        + under.final_open_work.draft_prs
        + under.final_open_work.open_growth_seeds
    )
    if active_under != 0:
        raise AssertionError("under-reproduction should exhaust ACE work")
    if healthy.total_spawned_seeds <= SCENARIOS["healthy-reproduction"].initial_seeds:
        raise AssertionError("healthy reproduction should create repeated descendant opportunity")
    if not healthy.stable_final_load or healthy.peak_review_load > healthy.steps:
        raise AssertionError("healthy reproduction should remain within bounded live pressure")
    overload_cmp = comparison(overload_governed, overload_raw)
    if not overload_cmp["raw_activity_can_be_worse"]:
        raise AssertionError(
            "overload must show raw activity increasing pressure without review throughput"
        )
    if overload_raw.total_verified_descendants != overload_governed.total_verified_descendants:
        raise AssertionError(
            "default overload comparison should hold verified output constant"
        )
    if not overload_governed.stable_final_load:
        raise AssertionError(
            "governed overload should recover to a final live load at or below K"
        )


def scenario_with_overrides(base: Scenario, args: argparse.Namespace) -> Scenario:
    data = asdict(base)
    for field, arg_name in (
        ("initial_seeds", "initial_seeds"),
        ("steps", "steps"),
        ("other_open_issues", "other_open_issues"),
        ("review_slots", "review_slots"),
        ("capacity_k", "k"),
        ("tau", "tau"),
        ("decay", "decay"),
        ("spawn_rate", "spawn_rate"),
        ("activation_probability", "activation_probability"),
        ("draft_ready_probability", "draft_ready_probability"),
        ("verification_probability", "verification_probability"),
        ("novelty_scale", "novelty_scale"),
    ):
        value = getattr(args, arg_name)
        if value is not None:
            data[field] = value
    return Scenario(**data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["all", *SCENARIOS], default="all")
    parser.add_argument(
        "--policy", choices=["both", "governed", "raw"], default="both"
    )
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run deterministic qualitative acceptance checks before output.",
    )
    parser.add_argument("--initial-seeds", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--other-open-issues", type=int)
    parser.add_argument("--review-slots", type=int)
    parser.add_argument("--k", type=float)
    parser.add_argument("--tau", type=float)
    parser.add_argument("--decay", type=float)
    parser.add_argument("--spawn-rate", type=float)
    parser.add_argument("--activation-probability", type=float)
    parser.add_argument("--draft-ready-probability", type=float)
    parser.add_argument("--verification-probability", type=float)
    parser.add_argument("--novelty-scale", type=float)
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
