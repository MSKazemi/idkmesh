"""What ``verifier_error_correlation`` actually couples in the R1 lab.

``experiments/E040-diversity-correlation-threshold.md`` closed by naming the
next test: sweep ``verifier_error_correlation`` against a beta-binomial
joint-failure shape rather than the flat shared shock, using E017's fitted
parameters as the reference point.

That test cannot be run against this lab, and the reason is the finding this
runner exists to record. A joint-failure shape describes how the errors of a
*panel* co-occur. ``randomness_lab/r1.py`` has no panel: ``run_r1_condition``
picks exactly one verifier per candidate — ``condition.verifiers[0]`` under
``fixed`` assignment, ``rng.choice`` under ``random`` — and no quorum, vote, or
aggregation rule appears anywhere in ``randomness_lab``. Five of the six arms
in ``build_r1_conditions`` are constructed with a single verifier. There is no
joint distribution over verifiers to give a different shape.

What the parameter does instead is visible in ``_verifier_accepts``: with
probability ``rho`` a candidate is judged against a uniform draw *shared with
every other candidate that the same verifier reads in the same task*, otherwise
against a fresh one. It is a within-task strictness shock on one verifier, not
dependence between verifiers. This runner measures that reading four ways —
the shock is invisible in the marginals, visible in the within-task joint,
inert when a task has one candidate, and exactly predictable at ``rho = 1`` —
and then measures the two consequences that matter for issue #13: the cost does
not amortize over swarm size, and a second verifier removes most of it.

Nothing here calls a model. Sensitivity, false-positive rate, worker quality and
both correlations are invented parameters, so every number below is a statement
about the simulator.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

from randomness_lab.r1 import (
    R1Condition,
    R1ExperimentConfig,
    Verifier,
    build_r1_conditions,
    run_r1_condition,
)

DEFAULT_CORRELATIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
DEFAULT_SWARM_SIZES = (2, 3, 5, 8, 12, 20)
DEFAULT_POOL_SIZES = (1, 2, 3, 4, 5, 8)

# The arm every section below is measured on. It is the one E040 fitted, it
# carries a single fixed verifier, and its worker correlation is the repository
# default rather than a pinned extreme.
REFERENCE_ARM = "structural_diversity"

# The arm whose task carries exactly one candidate, so a within-task shock has
# nothing to couple.
SINGLE_ATTEMPT_ARM = "single_deterministic"

INTERPRETATION_GUARDRAIL = (
    "verifier_error_correlation is a within-task strictness shock on one "
    "verifier, not dependence between verifiers. It must not be cited as "
    "evidence about panel independence, and the beta-binomial reshape E040 "
    "asked for cannot be applied to it: there is no panel in randomness_lab "
    "whose joint-failure shape could be changed. Giving this lab a panel is a "
    "design change to run_r1_condition, not a sweep."
)


@dataclass(frozen=True)
class VerifierDependenceConfig:
    """Grid for every section of the run."""

    tasks_per_trial: int = 300
    trials: int = 50
    base_seed: int = 42
    correlations: tuple[float, ...] = DEFAULT_CORRELATIONS
    swarm_sizes: tuple[int, ...] = DEFAULT_SWARM_SIZES
    pool_sizes: tuple[int, ...] = DEFAULT_POOL_SIZES
    penalty_swarm_size: int = 5

    def __post_init__(self) -> None:
        if self.tasks_per_trial < 1:
            raise ValueError("tasks_per_trial must be >= 1")
        if self.trials < 2:
            raise ValueError("trials must be >= 2 so uncertainty can be reported")
        if len(self.correlations) < 2:
            raise ValueError("a single correlation is not a sweep")
        if any(not 0.0 <= value <= 1.0 for value in self.correlations):
            raise ValueError("correlations must be in [0, 1]")
        if list(self.correlations) != sorted(set(self.correlations)):
            raise ValueError("correlations must be unique and ascending")
        if 0.0 not in self.correlations or 1.0 not in self.correlations:
            raise ValueError(
                "the sweep needs both endpoints: 0.0 is the penalty baseline "
                "and 1.0 is the cell the closed form predicts"
            )
        if not self.swarm_sizes or any(n < 2 for n in self.swarm_sizes):
            raise ValueError("swarm sizes must be >= 2")
        if list(self.swarm_sizes) != sorted(set(self.swarm_sizes)):
            raise ValueError("swarm sizes must be unique and ascending")
        if not self.pool_sizes or any(k < 1 for k in self.pool_sizes):
            raise ValueError("pool sizes must be >= 1")
        if list(self.pool_sizes) != sorted(set(self.pool_sizes)):
            raise ValueError("pool sizes must be unique and ascending")
        if self.penalty_swarm_size < 2:
            raise ValueError("penalty_swarm_size must be >= 2")

    @property
    def seeds(self) -> tuple[int, ...]:
        return tuple(self.base_seed + offset for offset in range(self.trials))


def _arm(name: str, config: R1ExperimentConfig) -> R1Condition:
    return next(
        condition
        for condition in build_r1_conditions(config)
        if condition.name == name
    )


def _condition(
    *,
    swarm_size: int,
    correlation: float,
    arm: str = REFERENCE_ARM,
    pool_size: int | None = None,
) -> R1Condition:
    config = R1ExperimentConfig(
        swarm_size=swarm_size, verifier_error_correlation=correlation
    )
    condition = _arm(arm, config)
    if pool_size is None:
        return condition
    pool = tuple(
        Verifier(
            f"verifier-{index + 1}",
            sensitivity=config.verifier_sensitivity,
            false_positive_rate=config.verifier_false_positive_rate,
            attention_cost=config.verifier_attention_cost,
        )
        for index in range(pool_size)
    )
    return replace(
        condition,
        verifiers=pool,
        verifier_assignment="fixed" if pool_size == 1 else "random",
    )


def _trial_rates(
    condition: R1Condition,
    *,
    tasks: int,
    seeds: Sequence[int],
    metric: str,
) -> list[float]:
    return [
        float(
            run_r1_condition(
                condition, tasks=tasks, seed=seed, retain_task_records=False
            )["metrics"][metric]
        )
        for seed in seeds
    ]


def _welch(left: Sequence[float], right: Sequence[float]) -> dict[str, float]:
    """Unpaired difference of means with a 95% interval.

    The comparison cannot be paired by seed. ``_verifier_accepts`` draws the
    correlation coin before deciding whether to draw again, so two runs at the
    same seed and different ``rho`` consume different numbers of values and the
    streams diverge after the first candidate. Matching seeds therefore matches
    nothing beyond the first task, and Welch is the honest test.
    """
    difference = statistics.mean(left) - statistics.mean(right)
    standard_error = math.sqrt(
        statistics.variance(left) / len(left)
        + statistics.variance(right) / len(right)
    )
    margin = 1.96 * standard_error
    return {
        "difference": difference,
        "standard_error": standard_error,
        "ci95": [difference - margin, difference + margin],
        "resolves": abs(difference) > margin,
    }


def _ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0.0:
        return float("nan")
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def _pearson(xs: Sequence[int], ys: Sequence[int]) -> float:
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denominator = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denominator == 0.0:
        return float("nan")
    return sum(x * y for x, y in zip(dx, dy)) / denominator


def measure_structure(config: VerifierDependenceConfig) -> dict[str, object]:
    """How many verifiers read one candidate, counted rather than asserted."""
    condition = _condition(
        swarm_size=config.penalty_swarm_size, correlation=DEFAULT_CORRELATIONS[-1]
    )
    decisions: set[int] = set()
    candidates = 0
    for seed in config.seeds[:2]:
        result = run_r1_condition(
            condition, tasks=config.tasks_per_trial, seed=seed
        )
        for record in result["task_records"]:
            for candidate in record["candidates"]:
                candidates += 1
                # One 'verifier' and one 'accepted' key per candidate is the
                # whole decision record; a panel would need a sequence.
                decisions.add(
                    1 if isinstance(candidate["verifier"], str) else -1
                )
    arms = build_r1_conditions(R1ExperimentConfig(swarm_size=config.penalty_swarm_size))
    return {
        "candidates_inspected": candidates,
        "verifiers_per_candidate": sorted(decisions),
        "arms_with_a_single_verifier": sorted(
            arm.name for arm in arms if len(arm.verifiers) == 1
        ),
        "arms_with_a_verifier_pool": sorted(
            arm.name for arm in arms if len(arm.verifiers) > 1
        ),
        "note": (
            "One verifier per candidate in every arm; the pool arm varies which "
            "one, never how many. No quorum or vote aggregation exists in "
            "randomness_lab, so there is no panel joint distribution."
        ),
    }


def measure_marginals_and_joint(config: VerifierDependenceConfig) -> list[dict]:
    """Accept rates (flat in rho) against within-task structure (not flat)."""
    points = []
    for correlation in config.correlations:
        condition = _condition(
            swarm_size=config.penalty_swarm_size, correlation=correlation
        )
        good_accepted = good_total = bad_accepted = bad_total = 0
        first, second = [], []
        nested_accepted = nested_total = 0
        for seed in config.seeds:
            result = run_r1_condition(
                condition, tasks=config.tasks_per_trial, seed=seed
            )
            for record in result["task_records"]:
                candidates = record["candidates"]
                for candidate in candidates:
                    if candidate["is_good"]:
                        good_total += 1
                        good_accepted += int(bool(candidate["accepted"]))
                    else:
                        bad_total += 1
                        bad_accepted += int(bool(candidate["accepted"]))
                if len(candidates) >= 2:
                    first.append(int(bool(candidates[0]["accepted"])))
                    second.append(int(bool(candidates[1]["accepted"])))
                # If a shared draw cleared the false-positive rate it has
                # cleared the sensitivity too, so an accepted bad candidate
                # should drag every good one in the same task with it.
                accepted_bad = [
                    candidate
                    for candidate in candidates
                    if not candidate["is_good"] and candidate["accepted"]
                ]
                goods = [
                    candidate for candidate in candidates if candidate["is_good"]
                ]
                if accepted_bad and goods:
                    nested_total += len(goods)
                    nested_accepted += sum(
                        1 for candidate in goods if candidate["accepted"]
                    )
        points.append(
            {
                "verifier_error_correlation": correlation,
                "accept_rate_given_good": good_accepted / good_total,
                "accept_rate_given_bad": bad_accepted / bad_total,
                "within_task_accept_correlation": _pearson(first, second),
                "good_accepted_when_a_bad_one_was": (
                    nested_accepted / nested_total if nested_total else float("nan")
                ),
                "nesting_denominator": nested_total,
            }
        )
    return points


def measure_single_attempt_inertness(config: VerifierDependenceConfig) -> dict:
    """One candidate per task leaves a within-task shock nothing to couple."""
    points = []
    for correlation in config.correlations:
        condition = _condition(
            swarm_size=config.penalty_swarm_size,
            correlation=correlation,
            arm=SINGLE_ATTEMPT_ARM,
        )
        rates = _trial_rates(
            condition,
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        )
        points.append(
            {
                "verifier_error_correlation": correlation,
                "attempts_per_task": condition.attempts_per_task,
                "verified_success_rate": statistics.mean(rates),
                "verified_success_rate_stdev": statistics.stdev(rates),
            }
        )
    extremes = _welch(
        _trial_rates(
            _condition(
                swarm_size=config.penalty_swarm_size,
                correlation=0.0,
                arm=SINGLE_ATTEMPT_ARM,
            ),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        ),
        _trial_rates(
            _condition(
                swarm_size=config.penalty_swarm_size,
                correlation=1.0,
                arm=SINGLE_ATTEMPT_ARM,
            ),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        ),
    )
    return {"points": points, "rho_zero_minus_rho_one": extremes}


def measure_closed_form(config: VerifierDependenceConfig) -> dict:
    """At rho = 1 one uniform draw decides the whole task, so it is solvable.

    With sensitivity ``s``, false-positive rate ``f`` and a single shared draw
    ``u`` per task, every candidate is judged against the same ``u``:

    * ``u < f``      — everything is accepted, so the integrated candidate is
      the first one generated;
    * ``f <= u < s`` — the good candidates are accepted and the bad ones are
      not, so the task abstains exactly when it produced no good candidate;
    * ``u >= s``     — nothing is accepted and the task abstains.

    Which gives, with ``g`` the probability a task produced at least one good
    candidate and ``g0`` the probability its first candidate was good:

        abstention   = (1 - s) + (s - f) * (1 - g)
        verified     = f * g0 + (s - f) * g
        false accept = f * (1 - g0)
    """
    condition = _condition(swarm_size=config.penalty_swarm_size, correlation=1.0)
    verifier = condition.verifiers[0]
    sensitivity = verifier.sensitivity
    false_positive_rate = verifier.false_positive_rate

    verified, false_accepts, abstentions, any_good = [], [], [], []
    first_good = first_total = 0
    for seed in config.seeds:
        result = run_r1_condition(condition, tasks=config.tasks_per_trial, seed=seed)
        metrics = result["metrics"]
        verified.append(float(metrics["verified_success_rate"]))
        false_accepts.append(float(metrics["false_acceptance_rate"]))
        abstentions.append(float(metrics["abstention_rate"]))
        any_good.append(float(metrics["candidate_any_good_rate"]))
        for record in result["task_records"]:
            first_total += 1
            first_good += int(bool(record["candidates"][0]["is_good"]))

    g = statistics.mean(any_good)
    g0 = first_good / first_total
    predicted = {
        "abstention_rate": (1 - sensitivity)
        + (sensitivity - false_positive_rate) * (1 - g),
        "verified_success_rate": false_positive_rate * g0
        + (sensitivity - false_positive_rate) * g,
        "false_acceptance_rate": false_positive_rate * (1 - g0),
    }
    observed = {
        "abstention_rate": statistics.mean(abstentions),
        "verified_success_rate": statistics.mean(verified),
        "false_acceptance_rate": statistics.mean(false_accepts),
    }
    return {
        "sensitivity": sensitivity,
        "false_positive_rate": false_positive_rate,
        "probability_task_had_a_good_candidate": g,
        "probability_first_candidate_was_good": g0,
        "predicted": predicted,
        "observed": observed,
        "absolute_error": {
            key: abs(predicted[key] - observed[key]) for key in predicted
        },
        "max_absolute_error": max(
            abs(predicted[key] - observed[key]) for key in predicted
        ),
    }


def measure_swarm_size_penalty(config: VerifierDependenceConfig) -> dict:
    """Does adding workers buy back what a correlated verifier costs?"""
    points = []
    samples: dict[int, tuple[list[float], list[float]]] = {}
    for swarm_size in config.swarm_sizes:
        independent = _trial_rates(
            _condition(swarm_size=swarm_size, correlation=0.0),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        )
        shocked = _trial_rates(
            _condition(swarm_size=swarm_size, correlation=1.0),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        )
        samples[swarm_size] = (independent, shocked)
        points.append(
            {
                "swarm_size": swarm_size,
                "verified_success_rate_rho_zero": statistics.mean(independent),
                "verified_success_rate_rho_one": statistics.mean(shocked),
                "penalty": _welch(independent, shocked),
            }
        )
    # The two smallest swarms are excluded from the trend: at N=2 the shock has
    # only one other candidate to couple to, so the penalty is still growing in
    # N and would be read as amortization running the wrong way.
    plateau = [point for point in points if point["swarm_size"] >= config.penalty_swarm_size]
    slope = _ols_slope(
        [math.log(point["swarm_size"]) for point in plateau],
        [point["penalty"]["difference"] for point in plateau],
    )

    # A slope near zero is a point estimate. The bound that survives being
    # wrong about the functional form is the plain difference of the smallest
    # and largest plateau penalties, with the interval that goes with it.
    first, last = plateau[0]["swarm_size"], plateau[-1]["swarm_size"]
    change = statistics.mean(samples[last][0]) - statistics.mean(samples[last][1]) - (
        statistics.mean(samples[first][0]) - statistics.mean(samples[first][1])
    )
    variance = sum(
        statistics.variance(series) / len(series)
        for size in (first, last)
        for series in samples[size]
    )
    margin = 1.96 * math.sqrt(variance)
    return {
        "points": points,
        "plateau_swarm_sizes": [point["swarm_size"] for point in plateau],
        "penalty_slope_per_e_fold": slope,
        "penalties_that_resolve": sum(
            1 for point in points if point["penalty"]["resolves"]
        ),
        "penalty_change_across_plateau": {
            "from_swarm_size": first,
            "to_swarm_size": last,
            "change": change,
            "ci95": [change - margin, change + margin],
            "resolves": abs(change) > margin,
        },
        "note": (
            "A penalty that amortized would need a clearly negative slope and a "
            "resolving negative change across the plateau. Swarm size is the "
            "axis issue #13 scales; this is the axis it cannot buy on."
        ),
    }


def measure_pool_dilution(config: VerifierDependenceConfig) -> dict:
    """Does a second verifier remove the shock, and how fast?"""
    points = []
    for pool_size in config.pool_sizes:
        independent = _trial_rates(
            _condition(
                swarm_size=config.penalty_swarm_size,
                correlation=0.0,
                pool_size=pool_size,
            ),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        )
        shocked = _trial_rates(
            _condition(
                swarm_size=config.penalty_swarm_size,
                correlation=1.0,
                pool_size=pool_size,
            ),
            tasks=config.tasks_per_trial,
            seeds=config.seeds,
            metric="verified_success_rate",
        )
        penalty = _welch(independent, shocked)
        points.append(
            {
                "pool_size": pool_size,
                "verifier_assignment": "fixed" if pool_size == 1 else "random",
                "verified_success_rate_rho_zero": statistics.mean(independent),
                "verified_success_rate_rho_one": statistics.mean(shocked),
                "penalty": penalty,
            }
        )
    single = next(point for point in points if point["pool_size"] == 1)
    for point in points:
        # Reported so the decay can be compared against the obvious guess.
        point["one_over_k_prediction"] = (
            single["penalty"]["difference"] / point["pool_size"]
        )
    return {
        "points": points,
        "single_verifier_penalty": single["penalty"]["difference"],
        "smallest_pool_that_does_not_resolve": next(
            (
                point["pool_size"]
                for point in points
                if not point["penalty"]["resolves"]
            ),
            None,
        ),
        "note": (
            "The shared draw is keyed by verifier, so two candidates read by "
            "different verifiers are never coupled. This is what the "
            "diverse_random_verifiers arm actually buys; E040 measured that arm "
            "on the worker-correlation slope, where it buys nothing."
        ),
    }


def run_verifier_dependence(config: VerifierDependenceConfig) -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment": "E041-verifier-strictness-shock",
        "generator": "randomness_lab.r1_verifier_dependence.v1",
        "evidence_level": "synthetic_mechanism",
        "config": asdict(config),
        "seeds": list(config.seeds),
        "reference_arm": REFERENCE_ARM,
        "structure": measure_structure(config),
        "marginals_and_joint": measure_marginals_and_joint(config),
        "single_attempt_inertness": measure_single_attempt_inertness(config),
        "closed_form_at_perfect_correlation": measure_closed_form(config),
        "swarm_size_penalty": measure_swarm_size_penalty(config),
        "pool_dilution": measure_pool_dilution(config),
        "interpretation_guardrail": INTERPRETATION_GUARDRAIL,
    }


def render_markdown(result: dict[str, object]) -> str:
    config = result["config"]
    lines = [
        "# R1 verifier dependence — a within-task strictness shock",
        "",
        f"Arm `{result['reference_arm']}`, "
        f"{config['trials']} seeds x {config['tasks_per_trial']} tasks per cell.",
        "",
        "## What reads a candidate",
        "",
    ]
    structure = result["structure"]
    lines += [
        f"- verifiers per candidate: {structure['verifiers_per_candidate']}",
        f"- arms with one verifier: {', '.join(structure['arms_with_a_single_verifier'])}",
        f"- arms with a pool: {', '.join(structure['arms_with_a_verifier_pool'])}",
        "",
        "## The shock is invisible in the marginals",
        "",
        "| rho_v | P(accept \\| good) | P(accept \\| bad) | corr(accept_0, accept_1) "
        "| P(good accepted \\| a bad one was) |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in result["marginals_and_joint"]:
        lines.append(
            f"| {point['verifier_error_correlation']:.2f} "
            f"| {point['accept_rate_given_good']:.4f} "
            f"| {point['accept_rate_given_bad']:.4f} "
            f"| {point['within_task_accept_correlation']:.4f} "
            f"| {point['good_accepted_when_a_bad_one_was']:.4f} |"
        )

    closed = result["closed_form_at_perfect_correlation"]
    lines += [
        "",
        "## At rho_v = 1 the task is solvable in closed form",
        "",
        "| metric | predicted | observed | absolute error |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in sorted(closed["predicted"]):
        lines.append(
            f"| {key} | {closed['predicted'][key]:.4f} "
            f"| {closed['observed'][key]:.4f} "
            f"| {closed['absolute_error'][key]:.4f} |"
        )

    penalty = result["swarm_size_penalty"]
    lines += [
        "",
        "## Swarm size does not buy the penalty back",
        "",
        "| N | verified at rho_v=0 | verified at rho_v=1 | penalty | 95% CI |",
        "| ---: | ---: | ---: | ---: | --- |",
    ]
    for point in penalty["points"]:
        low, high = point["penalty"]["ci95"]
        lines.append(
            f"| {point['swarm_size']} "
            f"| {point['verified_success_rate_rho_zero']:.4f} "
            f"| {point['verified_success_rate_rho_one']:.4f} "
            f"| {point['penalty']['difference']:+.4f} "
            f"| [{low:+.4f}, {high:+.4f}] |"
        )
    change = penalty["penalty_change_across_plateau"]
    lines += [
        "",
        f"Penalty slope over N >= {penalty['plateau_swarm_sizes'][0]}: "
        f"{penalty['penalty_slope_per_e_fold']:+.5f} per e-fold. Change from "
        f"N={change['from_swarm_size']} to N={change['to_swarm_size']}: "
        f"{change['change']:+.4f} "
        f"[{change['ci95'][0]:+.4f}, {change['ci95'][1]:+.4f}].",
        "",
        "## A second verifier removes most of it",
        "",
        "| pool | assignment | penalty | 95% CI | 1/K would predict |",
        "| ---: | --- | ---: | --- | ---: |",
    ]
    for point in result["pool_dilution"]["points"]:
        low, high = point["penalty"]["ci95"]
        lines.append(
            f"| {point['pool_size']} | {point['verifier_assignment']} "
            f"| {point['penalty']['difference']:+.4f} "
            f"| [{low:+.4f}, {high:+.4f}] "
            f"| {point['one_over_k_prediction']:.4f} |"
        )
    lines += ["", "## Guardrail", "", str(result["interpretation_guardrail"]), ""]
    return "\n".join(lines)


def _parse_floats(value: str) -> tuple[float, ...]:
    try:
        return tuple(float(item) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use comma-separated floats") from exc


def _parse_ints(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use comma-separated integers") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_verifier_dependence",
        description=(
            "Measure what verifier_error_correlation couples in the R1 lab, and "
            "what it costs."
        ),
    )
    parser.add_argument("--tasks", type=int, default=300)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--correlations", type=_parse_floats, default=DEFAULT_CORRELATIONS
    )
    parser.add_argument(
        "--swarm-sizes", type=_parse_ints, default=DEFAULT_SWARM_SIZES
    )
    parser.add_argument("--pool-sizes", type=_parse_ints, default=DEFAULT_POOL_SIZES)
    parser.add_argument("--penalty-swarm-size", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_verifier_dependence(
        VerifierDependenceConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            base_seed=args.seed,
            correlations=args.correlations,
            swarm_sizes=args.swarm_sizes,
            pool_sizes=args.pool_sizes,
            penalty_swarm_size=args.penalty_swarm_size,
        )
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
