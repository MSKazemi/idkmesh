"""E040's diversity advantage, recomputed under a correctly shaped worker panel.

``experiments/E040-diversity-correlation-threshold.md`` fitted the equal-budget
diversity advantage against retained independence ``1 - rho`` and found it
proportional, then hedged its own result:

    The linearity in Result 1 is therefore itself an artifact of the assumed
    shape; a correctly shaped model would put more mass on the joint failures
    that erase the diversity advantage, so these slopes are the optimistic end.

``experiments/E041-verifier-strictness-shock.md`` showed the reshape E040 asked
for has no target on the *verifier* axis, because ``randomness_lab`` has no
verifier panel. The **worker** axis does have one:
``CorrelatedBernoulliEnvironment`` is a genuine panel over the workers of a
task, and it is the flat shared shock E017 falsified. So the request is
executable one axis over, and this runner executes it.

The comparison is between two shapes that take the same two parameters and
agree at both endpoints, so any difference is attributable to shape alone:

* ``shared_shock`` — with probability ``rho`` the whole panel shares one
  correctness state, otherwise every worker is independent.
* ``item_difficulty`` — each task draws a difficulty from a Beta fitted so the
  marginal error rate and the pairwise error correlation both match, and workers
  then fail independently at that difficulty. This is the sampling counterpart
  of E018's closed-form ``item_difficulty_error``.

Nothing here calls a model. Worker quality and both correlations are invented
parameters, so every number is a statement about the simulator.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

from randomness_lab.model import (
    CorrelatedBernoulliEnvironment,
    ItemDifficultyEnvironment,
    Worker,
)
from randomness_lab.r1 import (
    R1Condition,
    R1ExperimentConfig,
    build_r1_conditions,
    run_r1_condition,
)

SHAPES = ("shared_shock", "item_difficulty")
CANDIDATE_FAMILIES = ("structural_diversity", "diverse_random_verifiers")
REFERENCE_ARM = "identical_replication"
DEFAULT_CORRELATIONS = (0.0, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0)
DEFAULT_SWARM_SIZES = (2, 5, 10)
DEFAULT_DIFFICULTIES = (("easy", 0.82), ("medium", 0.65), ("hard", 0.45))

# E040's Result 1 table, for the structural_diversity family. Reproduced here
# under `shared_shock` as a cross-runner check: this module computes the deltas
# directly from `run_r1_condition`, while E040 went through `r1_scaling`. The
# flat topology in that module calls `run_r1_condition` unchanged, so the two
# must agree exactly, and a drift means one of them has moved.
E040_PUBLISHED_SLOPES = {
    ("easy", 2): 0.1018, ("easy", 5): 0.1739, ("easy", 10): 0.1847,
    ("medium", 2): 0.1997, ("medium", 5): 0.3118, ("medium", 10): 0.3517,
    ("hard", 2): 0.1931, ("hard", 5): 0.4266, ("hard", 10): 0.5504,
}

# E040's own threshold for calling a curve proportional.
PROPORTIONALITY_THRESHOLD = 0.99

INTERPRETATION_GUARDRAIL = (
    "Neither shape is right. E020 measured a real panel and found a blind-spot "
    "floor lambda that the shared shock overshoots and the beta-binomial does "
    "not have at all -- at n=25 the beta-binomial predicted 0.0313 against a "
    "measured 0.0556. So this run does not establish that the diversity "
    "advantage is larger than E040 reported. It establishes only that E040's "
    "hedge is unsupported in the direction it was stated, and that the true "
    "direction is unknown because both candidate shapes miss the feature the "
    "one measured panel actually had."
)


@dataclass(frozen=True)
class DependenceShapeConfig:
    """E040's reference grid, run once per dependence shape."""

    tasks_per_trial: int = 200
    trials: int = 10
    base_seed: int = 42
    correlations: tuple[float, ...] = DEFAULT_CORRELATIONS
    swarm_sizes: tuple[int, ...] = DEFAULT_SWARM_SIZES
    difficulties: tuple[tuple[str, float], ...] = DEFAULT_DIFFICULTIES
    equivalence_tasks: int = 40_000

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
                "the sweep needs both endpoints: the fit is forced through the "
                "origin at rho=1, and rho=0 is the fully independent reference"
            )
        if not self.swarm_sizes or any(n < 2 for n in self.swarm_sizes):
            raise ValueError("swarm sizes must be >= 2")
        if list(self.swarm_sizes) != sorted(set(self.swarm_sizes)):
            raise ValueError("swarm sizes must be unique and ascending")
        if not self.difficulties:
            raise ValueError("difficulties must not be empty")
        names = [name for name, _ in self.difficulties]
        if len(set(names)) != len(names):
            raise ValueError("difficulty names must be unique")
        if any(not 0.0 <= quality <= 1.0 for _, quality in self.difficulties):
            raise ValueError("difficulty quality values must be in [0, 1]")
        if self.equivalence_tasks < 1000:
            raise ValueError(
                "equivalence_tasks must be >= 1000; the check exists to show the "
                "two shapes are matched, and a loose one would show nothing"
            )

    @property
    def seeds(self) -> tuple[int, ...]:
        return tuple(self.base_seed + offset for offset in range(self.trials))


def _arm(name: str, config: R1ExperimentConfig) -> R1Condition:
    return next(
        condition
        for condition in build_r1_conditions(config)
        if condition.name == name
    )


def _verified_rates(
    condition: R1Condition,
    *,
    shape: str,
    tasks: int,
    seeds: Sequence[int],
) -> list[float]:
    shaped = replace(condition, worker_dependence_shape=shape)
    return [
        float(
            run_r1_condition(
                shaped, tasks=tasks, seed=seed, retain_task_records=False
            )["metrics"]["verified_success_rate"]
        )
        for seed in seeds
    ]


def _fit_through_origin(
    points: Sequence[tuple[float, float]]
) -> tuple[float, float]:
    """Slope and uncentered R-squared of ``delta = slope * (1 - rho)``.

    Forced through the origin because the design pins that point: at ``rho = 1``
    the diverse arm and ``identical_replication`` differ by a profile label and
    nothing else. E040 uses the same fit, so the numbers are comparable.
    """
    xs = [1.0 - rho for rho, _ in points]
    ys = [delta for _, delta in points]
    denominator = sum(x * x for x in xs)
    if denominator == 0.0:
        return float("nan"), float("nan")
    slope = sum(x * y for x, y in zip(xs, ys)) / denominator
    residual = sum((y - slope * x) ** 2 for x, y in zip(xs, ys))
    total = sum(y * y for y in ys)
    return slope, (1.0 - residual / total if total else float("nan"))


def measure_shape_equivalence(config: DependenceShapeConfig) -> list[dict]:
    """Both shapes must match on marginal and correlation, and differ in the tail.

    This is the correctness foundation for everything below. If the two shapes
    are not matched, a difference in the fitted slopes says nothing about shape.
    """
    size = 5
    quality = 0.68
    workers = [Worker(f"worker-{index}", quality) for index in range(size)]
    points = []
    for correlation in config.correlations:
        row: dict[str, object] = {"error_correlation": correlation}
        for shape, environment in (
            ("shared_shock", CorrelatedBernoulliEnvironment(correlation)),
            ("item_difficulty", ItemDifficultyEnvironment(correlation)),
        ):
            rng = random.Random(config.base_seed)
            failures: list[int] = []
            first: list[int] = []
            second: list[int] = []
            for _ in range(config.equivalence_tasks):
                outcomes = environment.sample(workers, rng)
                errors = [0 if outcomes[w.name] else 1 for w in workers]
                failures.append(sum(errors))
                first.append(errors[0])
                second.append(errors[1])
            mean_first = statistics.mean(first)
            mean_second = statistics.mean(second)
            dx = [value - mean_first for value in first]
            dy = [value - mean_second for value in second]
            denominator = math.sqrt(
                sum(x * x for x in dx) * sum(y * y for y in dy)
            )
            row[shape] = {
                "marginal_error_rate": statistics.mean(failures) / size,
                "measured_pairwise_correlation": (
                    sum(x * y for x, y in zip(dx, dy)) / denominator
                    if denominator
                    else float("nan")
                ),
                "probability_whole_panel_failed": (
                    failures.count(size) / config.equivalence_tasks
                ),
            }
        points.append(row)
    return points


def measure_curves(config: DependenceShapeConfig) -> list[dict]:
    """E040's 18 curves, once per shape."""
    curves = []
    for family in CANDIDATE_FAMILIES:
        for difficulty, quality in config.difficulties:
            for swarm_size in config.swarm_sizes:
                entry: dict[str, object] = {
                    "family": family,
                    "difficulty": difficulty,
                    "worker_quality": quality,
                    "swarm_size": swarm_size,
                }
                for shape in SHAPES:
                    reference = _verified_rates(
                        _arm(
                            REFERENCE_ARM,
                            R1ExperimentConfig(
                                swarm_size=swarm_size,
                                base_worker_success_probability=quality,
                            ),
                        ),
                        shape=shape,
                        tasks=config.tasks_per_trial,
                        seeds=config.seeds,
                    )
                    points = []
                    for correlation in config.correlations:
                        candidate = _verified_rates(
                            _arm(
                                family,
                                R1ExperimentConfig(
                                    swarm_size=swarm_size,
                                    base_worker_success_probability=quality,
                                    structural_error_correlation=correlation,
                                ),
                            ),
                            shape=shape,
                            tasks=config.tasks_per_trial,
                            seeds=config.seeds,
                        )
                        # Paired by seed, as r1_scaling's _paired_deltas is.
                        points.append(
                            (
                                correlation,
                                statistics.mean(
                                    c - r for c, r in zip(candidate, reference)
                                ),
                            )
                        )
                    slope, r_squared = _fit_through_origin(points)
                    entry[shape] = {
                        "slope": slope,
                        "r_squared": r_squared,
                        "proportional": r_squared >= PROPORTIONALITY_THRESHOLD,
                        "points": [
                            {"correlation": rho, "mean_delta": delta}
                            for rho, delta in points
                        ],
                    }
                shock = entry["shared_shock"]["slope"]
                item = entry["item_difficulty"]["slope"]
                entry["slope_change"] = item - shock
                entry["slope_change_fraction"] = (
                    (item - shock) / shock if shock else float("nan")
                )
                curves.append(entry)
    return curves


def summarize(curves: Sequence[dict]) -> dict[str, object]:
    structural = [c for c in curves if c["family"] == "structural_diversity"]
    reproduction = []
    worst = 0.0
    for curve in structural:
        key = (curve["difficulty"], curve["swarm_size"])
        published = E040_PUBLISHED_SLOPES.get(key)
        if published is None:
            continue
        measured = curve["shared_shock"]["slope"]
        worst = max(worst, abs(measured - published))
        reproduction.append(
            {
                "difficulty": curve["difficulty"],
                "swarm_size": curve["swarm_size"],
                "published_slope": published,
                "reproduced_slope": measured,
                "absolute_difference": abs(measured - published),
            }
        )
    rises = sum(1 for c in curves if c["slope_change"] > 0)
    return {
        "curves": len(curves),
        "e040_reproduction": {
            "cells": reproduction,
            "max_absolute_difference": worst,
        },
        "proportional_curves": {
            shape: sum(1 for c in curves if c[shape]["proportional"])
            for shape in SHAPES
        },
        "curves_where_the_slope_rose": rises,
        "curves_where_the_slope_fell": len(curves) - rises,
        "mean_slope_change_fraction": statistics.mean(
            c["slope_change_fraction"] for c in curves
        ),
        "largest_slope_increase_fraction": max(
            c["slope_change_fraction"] for c in curves
        ),
        "largest_slope_decrease_fraction": min(
            c["slope_change_fraction"] for c in curves
        ),
        "e040_hedge_direction_holds": rises * 2 < len(curves),
    }


def run_dependence_shape(config: DependenceShapeConfig) -> dict[str, object]:
    curves = measure_curves(config)
    return {
        "schema_version": 1,
        "experiment": "E042-worker-dependence-shape",
        "generator": "randomness_lab.r1_dependence_shape.v1",
        "evidence_level": "synthetic_mechanism",
        "config": asdict(config),
        "seeds": list(config.seeds),
        "shapes": list(SHAPES),
        "reference_arm": REFERENCE_ARM,
        "proportionality_threshold": PROPORTIONALITY_THRESHOLD,
        "shape_equivalence": measure_shape_equivalence(config),
        "curves": curves,
        "summary": summarize(curves),
        "interpretation_guardrail": INTERPRETATION_GUARDRAIL,
    }


def render_markdown(result: dict[str, object]) -> str:
    config = result["config"]
    summary = result["summary"]
    lines = [
        "# E040's diversity advantage under a correctly shaped worker panel",
        "",
        f"{config['trials']} seeds x {config['tasks_per_trial']} tasks per cell; "
        f"{len(result['curves'])} curves per shape.",
        "",
        "## The two shapes are matched",
        "",
        "| rho | shared-shock marginal | item-difficulty marginal "
        "| shared-shock corr | item-difficulty corr "
        "| shared-shock P(all fail) | item-difficulty P(all fail) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result["shape_equivalence"]:
        shock, item = row["shared_shock"], row["item_difficulty"]
        lines.append(
            f"| {row['error_correlation']:.2f} "
            f"| {shock['marginal_error_rate']:.4f} "
            f"| {item['marginal_error_rate']:.4f} "
            f"| {shock['measured_pairwise_correlation']:.4f} "
            f"| {item['measured_pairwise_correlation']:.4f} "
            f"| {shock['probability_whole_panel_failed']:.4f} "
            f"| {item['probability_whole_panel_failed']:.4f} |"
        )

    reproduction = summary["e040_reproduction"]
    lines += [
        "",
        "## Cross-runner check against E040",
        "",
        f"Largest absolute difference from E040's published slopes: "
        f"`{reproduction['max_absolute_difference']:.4f}` "
        f"across {len(reproduction['cells'])} cells.",
        "",
        "## Slopes",
        "",
        "| family | difficulty | N | shared-shock | R2 | item-difficulty | R2 | change |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for curve in result["curves"]:
        shock, item = curve["shared_shock"], curve["item_difficulty"]
        lines.append(
            f"| {curve['family']} | {curve['difficulty']} | {curve['swarm_size']} "
            f"| {shock['slope']:.4f} | {shock['r_squared']:.4f} "
            f"| {item['slope']:.4f} | {item['r_squared']:.4f} "
            f"| {curve['slope_change_fraction']:+.1%} |"
        )
    lines += [
        "",
        f"- curves proportional at R2 >= {result['proportionality_threshold']}: "
        f"shared-shock {summary['proportional_curves']['shared_shock']}, "
        f"item-difficulty {summary['proportional_curves']['item_difficulty']}, "
        f"of {summary['curves']}",
        f"- slope rose in {summary['curves_where_the_slope_rose']} curves, "
        f"fell in {summary['curves_where_the_slope_fell']}",
        f"- mean slope change: {summary['mean_slope_change_fraction']:+.1%} "
        f"(range {summary['largest_slope_decrease_fraction']:+.1%} to "
        f"{summary['largest_slope_increase_fraction']:+.1%})",
        f"- E040's hedge holds (slopes mostly fall): "
        f"**{summary['e040_hedge_direction_holds']}**",
        "",
        "## Guardrail",
        "",
        str(result["interpretation_guardrail"]),
        "",
    ]
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


def _parse_difficulties(value: str) -> tuple[tuple[str, float], ...]:
    parsed = []
    try:
        for item in value.split(","):
            name, quality = item.strip().split(":", 1)
            parsed.append((name, float(quality)))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "use name:quality comma-separated pairs"
        ) from exc
    return tuple(parsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_dependence_shape",
        description=(
            "Recompute E040's equal-budget diversity advantage under both worker "
            "dependence shapes."
        ),
    )
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--correlations", type=_parse_floats, default=DEFAULT_CORRELATIONS
    )
    parser.add_argument(
        "--swarm-sizes", type=_parse_ints, default=DEFAULT_SWARM_SIZES
    )
    parser.add_argument(
        "--difficulties", type=_parse_difficulties, default=DEFAULT_DIFFICULTIES
    )
    parser.add_argument("--equivalence-tasks", type=int, default=40_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_dependence_shape(
        DependenceShapeConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            base_seed=args.seed,
            correlations=args.correlations,
            swarm_sizes=args.swarm_sizes,
            difficulties=args.difficulties,
            equivalence_tasks=args.equivalence_tasks,
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
