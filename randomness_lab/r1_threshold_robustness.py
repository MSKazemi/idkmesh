"""Bootstrap sensitivity audit for the synthetic R1 low-diversity threshold analysis.

The canonical :mod:`randomness_lab.r1_low_diversity_threshold` analysis reports
normal-approximation intervals over paired deterministic seed replications.  This
module is a deliberately separate downstream audit: it recomputes the same paired
seed-level marginal effects and asks whether a deterministic percentile bootstrap
supports the same directional interpretation.

The bootstrap is a robustness diagnostic over a finite synthetic seed sample.  It
is not a population confidence guarantee, is not multiplicity adjusted, and is not
real coding-agent evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from statistics import mean
from typing import Sequence

from .r1_low_diversity_threshold import (
    METRIC,
    _configured_sizes,
    _difficulty_order,
    _flat_homogeneous_cells,
    _seed_rates,
    analyze_low_diversity_threshold,
)
from .r1_scaling import R1ScalingConfig, run_r1_scaling


BOOTSTRAP_RESAMPLES = 5000
METHOD = "paired-deterministic-percentile-bootstrap-v1"


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires observations")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("percentile probability must be in [0, 1]")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _classification(interval: Sequence[float]) -> str:
    lower, upper = interval
    if lower > 0.0:
        return "positive"
    if upper < 0.0:
        return "negative"
    return "uncertain"


def _bootstrap_mean_summary(
    values: Sequence[float],
    *,
    seed_material: str,
) -> dict[str, object]:
    """Return a deterministic percentile-bootstrap interval for a sample mean.

    Pseudorandom resampling is seeded from the semantic transition identity and
    observed values.  Replaying the same input therefore produces exactly the same
    audit, while different transitions do not accidentally share a random stream.
    """

    if len(values) < 2:
        raise ValueError("bootstrap intervals require at least two paired seeds")
    numeric = [float(value) for value in values]
    payload = json.dumps(
        {"seed_material": seed_material, "values": numeric},
        sort_keys=True,
        separators=(",", ":"),
    )
    seed = int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)
    generator = random.Random(seed)
    sample_size = len(numeric)
    draws = [
        mean(numeric[generator.randrange(sample_size)] for _ in range(sample_size))
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    interval = [_percentile(draws, 0.025), _percentile(draws, 0.975)]
    return {
        "method": METHOD,
        "n": sample_size,
        "resamples": BOOTSTRAP_RESAMPLES,
        "mean": mean(numeric),
        "percentile_95_interval": interval,
        "classification": _classification(interval),
    }


def _robust_direction(normal: str, bootstrap: str) -> str:
    if normal == bootstrap and normal in {"positive", "negative"}:
        return normal
    return "uncertain"


def audit_threshold_robustness(result: dict[str, object]) -> dict[str, object]:
    """Audit whether R1 threshold labels survive a second interval construction.

    The existing low-diversity analyzer remains authoritative for the base
    definitions and fail-closed payload validation.  This function reuses its
    extraction helpers so the sensitivity audit cannot silently invent a second
    interpretation of the R1 result structure.
    """

    base = analyze_low_diversity_threshold(result)
    sizes = _configured_sizes(result)
    cells = _flat_homogeneous_cells(result)
    difficulties = _difficulty_order(result, cells)

    indexed: dict[tuple[str, int], dict[str, object]] = {}
    for cell in cells:
        difficulty = cell.get("difficulty")
        swarm_size = cell.get("swarm_size")
        if not isinstance(difficulty, str) or not isinstance(swarm_size, int):
            raise ValueError("selected cells must contain difficulty and integer swarm_size")
        indexed[(difficulty, swarm_size)] = cell

    audits: list[dict[str, object]] = []
    disagreement_count = 0
    for difficulty_index, difficulty in enumerate(difficulties):
        rates_by_size: dict[int, dict[int, float]] = {}
        seeds_by_size: dict[int, list[int]] = {}
        for size in sizes:
            seeds, rates = _seed_rates(indexed[(difficulty, size)])
            seeds_by_size[size] = seeds
            rates_by_size[size] = rates

        reference_seeds = seeds_by_size[sizes[0]]
        base_difficulty = base["difficulties"][difficulty_index]
        if base_difficulty["difficulty"] != difficulty:
            raise ValueError("base analysis difficulty order does not match R1 input")

        transitions: list[dict[str, object]] = []
        previous_marginal: dict[int, float] | None = None
        for transition_index, (lower_n, upper_n) in enumerate(zip(sizes, sizes[1:])):
            worker_delta = upper_n - lower_n
            marginal_by_seed = {
                seed: (
                    rates_by_size[upper_n][seed] - rates_by_size[lower_n][seed]
                )
                / worker_delta
                for seed in reference_seeds
            }
            marginal_values = [marginal_by_seed[seed] for seed in reference_seeds]
            marginal_bootstrap = _bootstrap_mean_summary(
                marginal_values,
                seed_material=f"{difficulty}:{lower_n}->{upper_n}:marginal",
            )

            base_transition = base_difficulty["transitions"][transition_index]
            normal_marginal = base_transition[
                "marginal_verified_success_per_additional_worker"
            ]
            normal_class = normal_marginal["classification"]
            bootstrap_class = marginal_bootstrap["classification"]
            marginal_agrees = normal_class == bootstrap_class
            if not marginal_agrees:
                disagreement_count += 1

            change_audit: dict[str, object] | None = None
            robust_diminishing = False
            if previous_marginal is not None:
                change_values = [
                    marginal_by_seed[seed] - previous_marginal[seed]
                    for seed in reference_seeds
                ]
                change_bootstrap = _bootstrap_mean_summary(
                    change_values,
                    seed_material=f"{difficulty}:{lower_n}->{upper_n}:delta-marginal",
                )
                normal_change = base_transition["change_from_previous_marginal"]
                normal_change_class = normal_change["classification"]
                bootstrap_change_class = change_bootstrap["classification"]
                change_agrees = normal_change_class == bootstrap_change_class
                if not change_agrees:
                    disagreement_count += 1
                robust_change = _robust_direction(
                    normal_change_class, bootstrap_change_class
                )
                robust_diminishing = robust_change == "negative"
                change_audit = {
                    "normal_approx_95_ci": normal_change["normal_approx_95_ci"],
                    "normal_classification": normal_change_class,
                    "bootstrap_95_ci": change_bootstrap["percentile_95_interval"],
                    "bootstrap_classification": bootstrap_change_class,
                    "classification_agrees": change_agrees,
                    "robust_classification": robust_change,
                }

            robust_marginal = _robust_direction(normal_class, bootstrap_class)
            transitions.append(
                {
                    "from_n": lower_n,
                    "to_n": upper_n,
                    "additional_workers": worker_delta,
                    "marginal": {
                        "normal_approx_95_ci": normal_marginal[
                            "normal_approx_95_ci"
                        ],
                        "normal_classification": normal_class,
                        "bootstrap_95_ci": marginal_bootstrap[
                            "percentile_95_interval"
                        ],
                        "bootstrap_classification": bootstrap_class,
                        "classification_agrees": marginal_agrees,
                        "robust_classification": robust_marginal,
                    },
                    "change_from_previous_marginal": change_audit,
                    "supported_negative_return_robust": robust_marginal == "negative",
                    "supported_diminishing_return_robust": robust_diminishing,
                }
            )
            previous_marginal = marginal_by_seed

        audits.append(
            {
                "difficulty": difficulty,
                "seeds_used": list(reference_seeds),
                "transitions": transitions,
                "first_robust_diminishing_to_n": next(
                    (
                        row["to_n"]
                        for row in transitions
                        if row["supported_diminishing_return_robust"]
                    ),
                    None,
                ),
                "first_robust_negative_to_n": next(
                    (
                        row["to_n"]
                        for row in transitions
                        if row["supported_negative_return_robust"]
                    ),
                    None,
                ),
            }
        )

    return {
        "schema_version": 1,
        "analysis": "R1-low-diversity-threshold-robustness",
        "base_analysis": base["analysis"],
        "source_experiment": base["source_experiment"],
        "source_generator": base["source_generator"],
        "source_schema_version": base["source_schema_version"],
        "evidence_level": "synthetic_mechanism_sensitivity",
        "metric": METRIC,
        "swarm_sizes": list(sizes),
        "bootstrap": {
            "method": METHOD,
            "resamples": BOOTSTRAP_RESAMPLES,
            "estimand": "mean paired seed-level marginal effect",
        },
        "classification_disagreements": disagreement_count,
        "difficulties": audits,
        "interpretation_guardrail": (
            "A robust directional label requires the existing normal-approximation "
            "interval and this deterministic percentile bootstrap to agree on a "
            "strictly positive or negative direction. Disagreement is reported as "
            "uncertain rather than resolved in favor of either method. The bootstrap "
            "resamples only the finite deterministic synthetic seed replications; "
            "with small n its percentile coverage is approximate, it is not "
            "multiplicity adjusted, and it does not represent a population sample "
            "of real software tasks, contributors, or coding agents."
        ),
    }


def _format_interval(interval: Sequence[float]) -> str:
    return f"[{interval[0]:.4f}, {interval[1]:.4f}]"


def render_markdown(audit: dict[str, object]) -> str:
    lines = [
        "# R1 low-diversity threshold robustness audit",
        "",
        "Evidence level: **synthetic mechanism sensitivity only**.",
        "",
        "A directional threshold is called robust here only when the existing ",
        "normal-approximation interval and the deterministic percentile bootstrap ",
        "agree. Method disagreement is kept as `uncertain`.",
        "",
        "| Difficulty | N | Normal 95% interval | Bootstrap 95% interval | Normal | Bootstrap | Robust | Diminishing robust |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for difficulty in audit["difficulties"]:
        for row in difficulty["transitions"]:
            marginal = row["marginal"]
            lines.append(
                f"| {difficulty['difficulty']} | {row['from_n']}→{row['to_n']} "
                f"| {_format_interval(marginal['normal_approx_95_ci'])} "
                f"| {_format_interval(marginal['bootstrap_95_ci'])} "
                f"| {marginal['normal_classification']} "
                f"| {marginal['bootstrap_classification']} "
                f"| {marginal['robust_classification']} "
                f"| {'yes' if row['supported_diminishing_return_robust'] else 'no'} |"
            )

    lines.extend(["", "## First robust thresholds", ""])
    for difficulty in audit["difficulties"]:
        diminishing = difficulty["first_robust_diminishing_to_n"]
        negative = difficulty["first_robust_negative_to_n"]
        lines.append(
            f"- **{difficulty['difficulty']}** — diminishing to N: "
            f"{'none' if diminishing is None else diminishing}; negative to N: "
            f"{'none' if negative is None else negative}."
        )

    lines.extend(
        [
            "",
            f"Interval-classification disagreements: **{audit['classification_disagreements']}**.",
            "",
            "## Scope boundary",
            "",
            str(audit["interpretation_guardrail"]),
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_sizes(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
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
    audit = audit_threshold_robustness(run_r1_scaling(config))
    rendered = render_markdown(audit)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    if args.output is None and args.report is None:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
