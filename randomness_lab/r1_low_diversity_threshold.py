"""Descriptive threshold analysis for issue #13's low-diversity scaling hypothesis.

This module deliberately sits downstream of :mod:`randomness_lab.r1_scaling` so the
frozen R1 reference generator and artifact remain unchanged.  It operationalizes
one narrow question: when the existing synthetic ``homogeneous`` family is treated
as a low-diversity proxy, where do paired marginal verified-success gains diminish
or become negative as swarm size grows?

The intervals here are descriptive normal-approximation intervals over deterministic
seed replications.  They are not formal hypothesis tests and are not evidence for a
real-world scaling law.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev
from typing import Sequence

from .r1_scaling import R1ScalingConfig, run_r1_scaling


LOW_DIVERSITY_FAMILY = "homogeneous"
FLAT_TOPOLOGY = "flat"
METRIC = "verified_success_rate"


def _descriptive_summary(values: Sequence[float]) -> dict[str, object]:
    if len(values) < 2:
        raise ValueError("descriptive intervals require at least two paired seeds")
    center = mean(values)
    spread = stdev(values)
    margin = 1.96 * spread / math.sqrt(len(values))
    interval = [center - margin, center + margin]
    if interval[0] > 0.0:
        classification = "positive"
    elif interval[1] < 0.0:
        classification = "negative"
    else:
        classification = "uncertain"
    return {
        "n": len(values),
        "mean": center,
        "sample_std": spread,
        "normal_approx_95_ci": interval,
        "min": min(values),
        "max": max(values),
        "classification": classification,
    }


def _flat_homogeneous_cells(result: dict[str, object]) -> list[dict[str, object]]:
    raw_cells = result.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("R1 result must contain a cells list")

    cells: list[dict[str, object]] = []
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, dict):
            raise ValueError("every R1 cell must be a mapping")
        topology = raw_cell.get("topology", FLAT_TOPOLOGY)
        if raw_cell.get("family") == LOW_DIVERSITY_FAMILY and topology == FLAT_TOPOLOGY:
            cells.append(raw_cell)
    if not cells:
        raise ValueError("R1 result has no flat homogeneous cells")
    return cells


def _configured_sizes(result: dict[str, object]) -> tuple[int, ...]:
    raw_config = result.get("config")
    if not isinstance(raw_config, dict):
        raise ValueError("R1 result must contain a config mapping")
    raw_sizes = raw_config.get("swarm_sizes")
    if not isinstance(raw_sizes, (list, tuple)):
        raise ValueError("R1 config must contain swarm_sizes")
    try:
        sizes = tuple(int(value) for value in raw_sizes)
    except (TypeError, ValueError) as exc:
        raise ValueError("swarm_sizes must contain integers") from exc
    if len(sizes) < 2 or any(value < 1 for value in sizes):
        raise ValueError("swarm_sizes must contain at least two positive sizes")
    if tuple(sorted(set(sizes))) != sizes:
        raise ValueError("swarm_sizes must be unique and strictly increasing")
    return sizes


def _difficulty_order(result: dict[str, object], cells: Sequence[dict[str, object]]) -> list[str]:
    raw_config = result.get("config")
    if isinstance(raw_config, dict):
        raw_levels = raw_config.get("difficulty_levels")
        if isinstance(raw_levels, (list, tuple)):
            names: list[str] = []
            for item in raw_levels:
                if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
                    names.append(item[0])
            if names:
                return names

    names = []
    for cell in cells:
        difficulty = cell.get("difficulty")
        if not isinstance(difficulty, str) or not difficulty:
            raise ValueError("every selected cell must name a difficulty")
        if difficulty not in names:
            names.append(difficulty)
    return names


def _seed_rates(cell: dict[str, object]) -> tuple[list[int], dict[int, float]]:
    raw_trials = cell.get("raw_trials")
    if not isinstance(raw_trials, list) or len(raw_trials) < 2:
        raise ValueError("each selected cell must contain at least two raw_trials")

    seeds: list[int] = []
    rates: dict[int, float] = {}
    for raw_row in raw_trials:
        if not isinstance(raw_row, dict):
            raise ValueError("raw trial rows must be mappings")
        seed = raw_row.get("seed")
        metrics = raw_row.get("metrics")
        if not isinstance(seed, int) or not isinstance(metrics, dict):
            raise ValueError("raw trials must contain integer seed and metrics")
        raw_rate = metrics.get(METRIC)
        if not isinstance(raw_rate, (int, float)) or isinstance(raw_rate, bool):
            raise ValueError(f"raw trial metrics must contain numeric {METRIC}")
        rate = float(raw_rate)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"{METRIC} must be in [0, 1]")
        if seed in rates:
            raise ValueError("raw trial seeds must be unique within a cell")
        seeds.append(seed)
        rates[seed] = rate
    return seeds, rates


def analyze_low_diversity_threshold(result: dict[str, object]) -> dict[str, object]:
    """Measure paired marginal-return thresholds in the synthetic homogeneous arm.

    ``homogeneous`` is a deliberately strong low-diversity proxy: workers share the
    same strategy family.  For each adjacent pair of swarm sizes, the per-seed
    marginal gain is

    ``(success(N_to) - success(N_from)) / (N_to - N_from)``.

    A *supported diminishing return* requires the descriptive 95% interval for the
    paired change from the preceding marginal gain to be entirely below zero.  A
    *supported negative return* requires the marginal-gain interval itself to be
    entirely below zero.  These labels describe this synthetic mechanism only.
    """

    if not isinstance(result, dict):
        raise ValueError("R1 result must be a mapping")
    if result.get("experiment") != "R1-collective-capability-scaling":
        raise ValueError("expected an R1 collective-capability scaling result")

    sizes = _configured_sizes(result)
    cells = _flat_homogeneous_cells(result)
    difficulties = _difficulty_order(result, cells)

    indexed: dict[tuple[str, int], dict[str, object]] = {}
    for cell in cells:
        difficulty = cell.get("difficulty")
        swarm_size = cell.get("swarm_size")
        if not isinstance(difficulty, str) or not isinstance(swarm_size, int):
            raise ValueError("selected cells must contain difficulty and integer swarm_size")
        key = (difficulty, swarm_size)
        if key in indexed:
            raise ValueError(f"duplicate flat homogeneous cell for {difficulty!r}, N={swarm_size}")
        indexed[key] = cell

    analyses: list[dict[str, object]] = []
    for difficulty in difficulties:
        missing = [size for size in sizes if (difficulty, size) not in indexed]
        if missing:
            raise ValueError(
                f"missing flat homogeneous cells for {difficulty!r}: N={missing}"
            )

        seeds_by_size: dict[int, list[int]] = {}
        rates_by_size: dict[int, dict[int, float]] = {}
        for size in sizes:
            seeds, rates = _seed_rates(indexed[(difficulty, size)])
            seeds_by_size[size] = seeds
            rates_by_size[size] = rates

        reference_seeds = seeds_by_size[sizes[0]]
        for size in sizes[1:]:
            if seeds_by_size[size] != reference_seeds:
                raise ValueError(
                    f"paired cells for {difficulty!r} must use identical ordered seeds"
                )

        transitions: list[dict[str, object]] = []
        previous_marginal: dict[int, float] | None = None
        for lower_n, upper_n in zip(sizes, sizes[1:]):
            worker_delta = upper_n - lower_n
            marginal_by_seed = {
                seed: (
                    rates_by_size[upper_n][seed] - rates_by_size[lower_n][seed]
                )
                / worker_delta
                for seed in reference_seeds
            }
            marginal_summary = _descriptive_summary(
                [marginal_by_seed[seed] for seed in reference_seeds]
            )

            change_summary: dict[str, object] | None = None
            if previous_marginal is not None:
                change_summary = _descriptive_summary(
                    [
                        marginal_by_seed[seed] - previous_marginal[seed]
                        for seed in reference_seeds
                    ]
                )

            transitions.append(
                {
                    "from_n": lower_n,
                    "to_n": upper_n,
                    "additional_workers": worker_delta,
                    "marginal_verified_success_per_additional_worker": marginal_summary,
                    "change_from_previous_marginal": change_summary,
                    "supported_diminishing_return": bool(
                        change_summary is not None
                        and change_summary["classification"] == "negative"
                    ),
                    "supported_negative_return": (
                        marginal_summary["classification"] == "negative"
                    ),
                }
            )
            previous_marginal = marginal_by_seed

        analyses.append(
            {
                "difficulty": difficulty,
                "seeds_used": list(reference_seeds),
                "transitions": transitions,
                "first_supported_diminishing_to_n": next(
                    (
                        row["to_n"]
                        for row in transitions
                        if row["supported_diminishing_return"]
                    ),
                    None,
                ),
                "first_supported_negative_to_n": next(
                    (
                        row["to_n"]
                        for row in transitions
                        if row["supported_negative_return"]
                    ),
                    None,
                ),
                "first_interval_not_strictly_positive_to_n": next(
                    (
                        row["to_n"]
                        for row in transitions
                        if row["marginal_verified_success_per_additional_worker"][
                            "classification"
                        ]
                        != "positive"
                    ),
                    None,
                ),
            }
        )

    return {
        "schema_version": 1,
        "analysis": "R1-low-diversity-marginal-threshold",
        "source_experiment": result.get("experiment"),
        "source_generator": result.get("generator"),
        "source_schema_version": result.get("schema_version"),
        "evidence_level": "synthetic_mechanism",
        "low_diversity_proxy": LOW_DIVERSITY_FAMILY,
        "topology": FLAT_TOPOLOGY,
        "metric": METRIC,
        "swarm_sizes": list(sizes),
        "definitions": {
            "marginal_gain": (
                "paired change in verified_success_rate divided by the number of "
                "additional workers between adjacent configured swarm sizes"
            ),
            "supported_diminishing_return": (
                "normal-approximation 95% interval for the paired change from the "
                "previous marginal gain is entirely below zero"
            ),
            "supported_negative_return": (
                "normal-approximation 95% interval for the marginal gain is entirely "
                "below zero"
            ),
            "interval_not_strictly_positive": (
                "the marginal-gain interval overlaps or falls below zero; this is "
                "descriptive uncertainty, not evidence that the true gain is zero"
            ),
        },
        "difficulties": analyses,
        "interpretation_guardrail": (
            "This analysis reuses deterministic synthetic R1 trials. The homogeneous "
            "family is a model proxy for low diversity, not a measurement of real "
            "contributors or coding agents. Normal-approximation intervals are "
            "descriptive and are not multiplicity-adjusted hypothesis tests. Results "
            "can falsify or expose regimes inside the simulator, but they cannot "
            "establish a real-world scaling law or close issue #13."
        ),
    }


def _format_optional(value: object) -> str:
    return "none" if value is None else str(value)


def render_markdown(analysis: dict[str, object]) -> str:
    lines = [
        "# R1 low-diversity marginal-threshold analysis",
        "",
        "Evidence level: **synthetic mechanism only**.",
        "",
        "The `homogeneous` family is used as the low-diversity proxy. Intervals are ",
        "descriptive normal approximations over paired deterministic seeds, not formal ",
        "hypothesis tests.",
        "",
        "| Difficulty | N | Marginal gain / added worker | 95% interval | Class | Δ previous marginal | Diminishing supported | Negative supported |",
        "| --- | --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for difficulty in analysis["difficulties"]:
        for row in difficulty["transitions"]:
            marginal = row["marginal_verified_success_per_additional_worker"]
            interval = marginal["normal_approx_95_ci"]
            change = row["change_from_previous_marginal"]
            change_text = "—" if change is None else f"{change['mean']:.4f}"
            lines.append(
                f"| {difficulty['difficulty']} | {row['from_n']}→{row['to_n']} "
                f"| {marginal['mean']:.4f} | [{interval[0]:.4f}, {interval[1]:.4f}] "
                f"| {marginal['classification']} | {change_text} "
                f"| {'yes' if row['supported_diminishing_return'] else 'no'} "
                f"| {'yes' if row['supported_negative_return'] else 'no'} |"
            )

    lines.extend(["", "## First observed thresholds", ""])
    for difficulty in analysis["difficulties"]:
        lines.append(
            f"- **{difficulty['difficulty']}** — supported diminishing to N: "
            f"{_format_optional(difficulty['first_supported_diminishing_to_n'])}; "
            f"supported negative to N: "
            f"{_format_optional(difficulty['first_supported_negative_to_n'])}; "
            f"first marginal interval not strictly positive to N: "
            f"{_format_optional(difficulty['first_interval_not_strictly_positive_to_n'])}."
        )

    lines.extend(
        [
            "",
            "## Scope boundary",
            "",
            str(analysis["interpretation_guardrail"]),
            "",
            "A missing supported threshold means this seeded synthetic run did not "
            "resolve one at the configured swarm sizes; it is not evidence that no "
            "threshold exists.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_sizes(value: str) -> tuple[int, ...]:
    try:
        sizes = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return sizes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze issue #13's low-diversity marginal-return threshold"
    )
    parser.add_argument("--output", type=Path, help="write machine-readable JSON")
    parser.add_argument("--report", type=Path, help="write a Markdown report")
    parser.add_argument("--tasks", type=int, default=R1ScalingConfig.tasks_per_trial)
    parser.add_argument("--trials", type=int, default=R1ScalingConfig.trials)
    parser.add_argument("--seed", type=int, default=R1ScalingConfig.base_seed)
    parser.add_argument(
        "--swarm-sizes",
        type=_parse_sizes,
        default=R1ScalingConfig.swarm_sizes,
        help="comma-separated sizes beginning with 1 (default: 1,2,5,10)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = R1ScalingConfig(
        tasks_per_trial=args.tasks,
        trials=args.trials,
        base_seed=args.seed,
        swarm_sizes=args.swarm_sizes,
    )
    analysis = analyze_low_diversity_threshold(run_r1_scaling(config))
    rendered = render_markdown(analysis)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    if args.output is None and args.report is None:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
