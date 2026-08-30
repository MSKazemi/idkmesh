"""Where the assumed worker-error correlation erases the diversity advantage.

Issue #13 hypothesis 2 states that heterogeneous teams with independent
verification outperform homogeneous teams at an equal inference budget on at
least some software-engineering workloads. The R1 scaling runner already
measures exactly that contrast — ``equal_attempt_budget_comparisons`` pairs the
structurally diverse arm against maximally correlated replication at an
identical attempt count — but it measures it at a single assumed correlation,
``structural_error_correlation = 0.25``. ``docs/research/R1_COLLECTIVE_SCALING.md``
says of the resulting advantage that it "is partly constructed by the
correlation assumptions", and leaves it there.

This runner turns that caveat into a number. It replays the flat scaling grid
across a ladder of assumed correlations and reports, for every difficulty and
swarm size, the correlation above which the diversity advantage is no longer
resolvable at the configured seed count.

The correlation being swept is the *only* thing that separates the two arms:
``build_r1_conditions`` pins ``identical_replication`` at
``worker_error_correlation = 1.0`` and hands ``structural_error_correlation`` to
the diverse arms, while both draw from profiles with the same base success
probability. At ``rho = 1.0`` the two arms therefore coincide by construction,
which is a property of the design rather than a finding, and is asserted as a
self-check rather than reported as evidence.

What this cannot do is convert the answer into real coding agents. The
correlation is a parameter of a shared-shock Bernoulli environment, and the one
error correlation this repository has actually measured — ``+0.5873`` across a
verifier panel in ``experiments/E017-item-difficulty-and-quorum.md`` — came with
the finding that the flat shared-shock model understates the joint-failure tail
at that value by about 1.71x. The threshold below is in the model's own
coordinates and is, on E017's evidence, the optimistic end of the range.
"""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

from randomness_lab.r1_scaling import (
    FLAT,
    R1ScalingConfig,
    run_r1_scaling,
)

CANDIDATE_FAMILIES = ("structural_diversity", "diverse_verifiers")
DEFAULT_CORRELATIONS = (0.0, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0)

# The only pairwise error correlation measured anywhere in this repository.
MEASURED_REFERENCE = {
    "value": 0.5873,
    "measured_on": "a 25-model verifier panel, not coding workers",
    "source": "experiments/E017-item-difficulty-and-quorum.md",
    "caveat": (
        "E017 also found that a flat shared-shock model at this correlation "
        "understates the joint-failure tail by about 1.71x, so it is not a "
        "sufficient statistic and this runner's parameterization is the "
        "optimistic one."
    ),
}


@dataclass(frozen=True)
class CorrelationSweepConfig:
    """The scaling grid, plus the ladder of assumed correlations to run it at."""

    base: R1ScalingConfig = R1ScalingConfig()
    correlations: tuple[float, ...] = DEFAULT_CORRELATIONS

    def __post_init__(self) -> None:
        if len(self.correlations) < 2:
            raise ValueError("sweep at least two correlations")
        if any(not 0.0 <= value <= 1.0 for value in self.correlations):
            raise ValueError("correlations must be in [0, 1]")
        if tuple(sorted(set(self.correlations))) != tuple(self.correlations):
            raise ValueError("correlations must be unique and strictly increasing")


def _comparison_key(row: dict[str, object]) -> tuple[str, int, str]:
    return (
        str(row["difficulty"]),
        int(row["swarm_size"]),
        str(row["candidate_family"]),
    )


def _resolved_at(
    points: Sequence[dict[str, object]],
    correlation: float,
) -> dict[str, object]:
    """Is the advantage still resolved at the bracket containing ``correlation``?

    The swept ladder rarely lands exactly on a reference value, so this reports
    the bracketing swept points rather than interpolating a classification that
    was never measured.
    """

    below = [row for row in points if float(row["correlation"]) <= correlation]
    above = [row for row in points if float(row["correlation"]) >= correlation]
    if not below or not above:
        return {"bracketed": False, "lower": None, "upper": None, "resolved": None}
    lower, upper = below[-1], above[0]
    return {
        "bracketed": True,
        "lower": {
            "correlation": lower["correlation"],
            "classification": lower["classification"],
        },
        "upper": {
            "correlation": upper["correlation"],
            "classification": upper["classification"],
        },
        "resolved": (
            lower["classification"] == "positive"
            and upper["classification"] == "positive"
        ),
    }


def _independence_proportionality(
    points: Sequence[dict[str, object]],
) -> dict[str, object]:
    """Fit the curve against retained independence, ``1 - rho``, through zero.

    A threshold summary answers "where does it stop", which presumes there is a
    knee to find. The stronger question is whether the advantage is simply
    proportional to how much worker independence the assumption leaves, in
    which case there is no threshold at all and the 0.25 default is not a
    privileged operating point. The fit is forced through the origin because
    the arms coincide by construction at ``rho = 1``; a free intercept would
    fit a degree of freedom the design has already pinned.
    """

    xs = [1.0 - float(row["correlation"]) for row in points]
    ys = [float(row["mean_delta"]) for row in points]
    denominator = sum(x * x for x in xs)
    if denominator == 0.0:
        return {"slope": None, "r_squared": None, "proportional": False}
    slope = sum(x * y for x, y in zip(xs, ys)) / denominator
    residual = sum((y - slope * x) ** 2 for x, y in zip(xs, ys))
    total = sum(y * y for y in ys)
    r_squared = None if total == 0.0 else 1.0 - residual / total
    return {
        "slope": slope,
        "r_squared": r_squared,
        # A high uncentered R-squared through the origin means the curve is
        # carried by retained independence alone, with no knee to locate.
        "proportional": r_squared is not None and r_squared >= 0.99,
    }


def _threshold(points: Sequence[dict[str, object]]) -> dict[str, object]:
    """Summarize one difficulty/N/family curve across the correlation ladder.

    ``points`` arrives ordered by ascending correlation. Two boundaries are
    reported and they are not the same question: the last correlation whose
    interval still excludes zero, and the first at which it no longer does.
    Between them the sweep says nothing, and the gap is reported rather than
    hidden by picking one side of it.
    """

    positive = [row for row in points if row["classification"] == "positive"]
    unresolved = [row for row in points if row["classification"] != "positive"]
    means = [float(row["mean_delta"]) for row in points]
    return {
        "highest_resolved_positive_correlation": (
            positive[-1]["correlation"] if positive else None
        ),
        "first_unresolved_correlation": (
            unresolved[0]["correlation"] if unresolved else None
        ),
        "resolved_positive_at_every_swept_correlation": not unresolved,
        "monotone_non_increasing_in_correlation": all(
            later <= earlier + 1e-12 for earlier, later in zip(means, means[1:])
        ),
        "mean_delta_at_lowest_correlation": means[0],
        "mean_delta_at_highest_correlation": means[-1],
    }


def _verifier_assignment_increment(
    thresholds: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    """Split hypothesis 2's two claims apart.

    Issue #13 hypothesis 2 bundles "heterogeneous teams" with "independent
    verification" into one sentence, so a positive result is easy to read as
    support for both. The two arms here differ by exactly one thing — the
    ``diverse_verifiers`` arm randomizes verifier assignment over a pool while
    ``structural_diversity`` keeps one fixed verifier — so subtracting their
    fitted slopes isolates what the verification half is worth.
    """

    by_key: dict[tuple[str, int], dict[str, dict[str, object]]] = {}
    for row in thresholds:
        key = (str(row["difficulty"]), int(row["swarm_size"]))
        by_key.setdefault(key, {})[str(row["candidate_family"])] = row

    rows = []
    for (difficulty, swarm_size), families in sorted(by_key.items()):
        worker = families.get("structural_diversity")
        both = families.get("diverse_verifiers")
        if worker is None or both is None:
            continue
        worker_slope = worker["retained_independence_fit"]["slope"]
        both_slope = both["retained_independence_fit"]["slope"]
        if worker_slope is None or both_slope is None:
            continue
        increment = float(both_slope) - float(worker_slope)
        rows.append(
            {
                "difficulty": difficulty,
                "swarm_size": swarm_size,
                "worker_diversity_slope": worker_slope,
                "worker_plus_verifier_diversity_slope": both_slope,
                "verifier_assignment_increment": increment,
                "increment_share_of_worker_slope": (
                    increment / float(worker_slope) if worker_slope else None
                ),
            }
        )
    return rows


def run_correlation_sweep(config: CorrelationSweepConfig) -> dict[str, object]:
    runs = []
    for correlation in config.correlations:
        scaling = run_r1_scaling(
            replace(config.base, structural_error_correlation=correlation),
            topologies=(FLAT,),
        )
        runs.append((correlation, scaling["equal_attempt_budget_comparisons"]))

    points: list[dict[str, object]] = []
    for correlation, comparisons in runs:
        for row in comparisons:
            delta = row["verified_success_rate_delta"]
            points.append(
                {
                    "correlation": correlation,
                    "difficulty": row["difficulty"],
                    "swarm_size": row["swarm_size"],
                    "candidate_family": row["candidate_family"],
                    "baseline_family": row["baseline_family"],
                    "mean_delta": delta["mean"],
                    "normal_approx_95_ci": delta["normal_approx_95_ci"],
                    "classification": delta["classification"],
                    "equal_attempt_count": row["equal_attempt_count"],
                    "equal_mean_compute_per_task": row["equal_mean_compute_per_task"],
                }
            )

    grouped: dict[tuple[str, int, str], list[dict[str, object]]] = {}
    for point in points:
        grouped.setdefault(_comparison_key(point), []).append(point)

    thresholds = []
    for (difficulty, swarm_size, family), rows in grouped.items():
        rows.sort(key=lambda row: float(row["correlation"]))
        thresholds.append(
            {
                "difficulty": difficulty,
                "swarm_size": swarm_size,
                "candidate_family": family,
                **_threshold(rows),
                "retained_independence_fit": _independence_proportionality(rows),
                "resolved_at_measured_reference": _resolved_at(
                    rows, float(MEASURED_REFERENCE["value"])
                ),
            }
        )
    thresholds.sort(
        key=lambda row: (
            row["candidate_family"],
            row["difficulty"],
            row["swarm_size"],
        )
    )

    increments = _verifier_assignment_increment(thresholds)

    coincidence = [
        point
        for point in points
        if point["correlation"] == 1.0 and point["classification"] == "positive"
    ]

    return {
        "schema_version": 1,
        "experiment": "E040-diversity-correlation-threshold",
        "generator": "randomness_lab.r1_correlation_threshold.v1",
        "evidence_level": "synthetic_mechanism",
        "question": (
            "Issue #13 hypothesis 2: at an equal attempt budget, above which "
            "assumed worker-error correlation is the heterogeneous arm's "
            "advantage over replication no longer resolvable?"
        ),
        "config": {
            "base": asdict(config.base),
            "correlations": list(config.correlations),
        },
        "measured_reference_correlation": MEASURED_REFERENCE,
        "points": points,
        "thresholds": thresholds,
        "verifier_assignment_increment": increments,
        "summary": {
            "curves": len(thresholds),
            "cells_where_verifier_assignment_raised_the_slope": sum(
                1 for row in increments if row["verifier_assignment_increment"] > 0.0
            ),
            "max_absolute_verifier_assignment_increment": (
                max(abs(row["verifier_assignment_increment"]) for row in increments)
                if increments
                else None
            ),
            "max_verifier_increment_share_of_worker_slope": (
                max(
                    abs(row["increment_share_of_worker_slope"])
                    for row in increments
                    if row["increment_share_of_worker_slope"] is not None
                )
                if increments
                else None
            ),
            "curves_proportional_to_retained_independence": sum(
                1 for row in thresholds if row["retained_independence_fit"]["proportional"]
            ),
            "curves_resolved_at_measured_reference": sum(
                1 for row in thresholds if row["resolved_at_measured_reference"]["resolved"]
            ),
            "curves_resolved_at_every_swept_correlation": sum(
                1 for row in thresholds if row["resolved_positive_at_every_swept_correlation"]
            ),
        },
        "self_check": {
            "arms_coincide_at_correlation_one": (
                1.0 not in config.correlations or not coincidence
            ),
            "note": (
                "At rho=1.0 the diverse arm and identical_replication differ "
                "only by a profile label, so a resolved advantage there would "
                "indicate a defect in the harness rather than a finding."
            ),
        },
        "interpretation_guardrail": (
            "The swept quantity is a parameter of a synthetic shared-shock "
            "environment, not a measurement of real coding agents. A threshold "
            "here bounds when the assumption carries the result; it does not "
            "establish that heterogeneous coding agents beat replicated ones."
        ),
    }


def render_markdown(result: dict[str, object]) -> str:
    correlations = result["config"]["correlations"]
    lines = [
        "# E040 diversity advantage against assumed error correlation",
        "",
        f"Generator: `{result['generator']}`  ",
        f"Evidence level: `{result['evidence_level']}`",
        "",
        result["question"],
        "",
        "## Verified-success-rate delta, diverse arm minus replication",
        "",
        "Positive means the heterogeneous arm won at an equal attempt budget.",
        "A cell reads `mean (classification)` where the classification is the",
        "descriptive 95% interval's position relative to zero.",
        "",
    ]
    header = "| family | difficulty | N | " + " | ".join(
        f"rho={value:g}" for value in correlations
    ) + " |"
    lines.append(header)
    lines.append("| --- | --- | ---: |" + " ---: |" * len(correlations))

    ordered = sorted(
        {
            (
                str(point["candidate_family"]),
                str(point["difficulty"]),
                int(point["swarm_size"]),
            )
            for point in result["points"]
        }
    )
    indexed = {
        (
            str(point["candidate_family"]),
            str(point["difficulty"]),
            int(point["swarm_size"]),
            float(point["correlation"]),
        ): point
        for point in result["points"]
    }
    for family, difficulty, swarm_size in ordered:
        cells = []
        for correlation in correlations:
            point = indexed[(family, difficulty, swarm_size, float(correlation))]
            cells.append(
                f"{float(point['mean_delta']):+.4f} ({point['classification'][:3]})"
            )
        lines.append(
            f"| {family} | {difficulty} | {swarm_size} | " + " | ".join(cells) + " |"
        )

    lines += [
        "",
        "## Where the advantage stops resolving",
        "",
        "| family | difficulty | N | highest resolved rho | first unresolved rho | "
        "monotone | slope vs 1-rho | R^2 | resolved at 0.5873 |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in result["thresholds"]:
        highest = row["highest_resolved_positive_correlation"]
        first = row["first_unresolved_correlation"]
        fit = row["retained_independence_fit"]
        reference = row["resolved_at_measured_reference"]
        lines.append(
            "| {family} | {difficulty} | {n} | {highest} | {first} | {monotone} "
            "| {slope} | {r2} | {reference} |".format(
                family=row["candidate_family"],
                difficulty=row["difficulty"],
                n=row["swarm_size"],
                highest="none" if highest is None else f"{float(highest):g}",
                first="none" if first is None else f"{float(first):g}",
                monotone="yes" if row["monotone_non_increasing_in_correlation"] else "no",
                slope="n/a" if fit["slope"] is None else f"{float(fit['slope']):.4f}",
                r2="n/a" if fit["r_squared"] is None else f"{float(fit['r_squared']):.4f}",
                reference=(
                    "unbracketed"
                    if not reference["bracketed"]
                    else ("yes" if reference["resolved"] else "no")
                ),
            )
        )

    lines += [
        "",
        "## What the verification half of hypothesis 2 is worth",
        "",
        "The two arms differ by exactly one thing: `diverse_verifiers` randomizes",
        "verifier assignment over a pool, `structural_diversity` keeps one fixed",
        "verifier. The slope difference is what that buys.",
        "",
        "| difficulty | N | worker-diversity slope | + verifier diversity | increment | share |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result["verifier_assignment_increment"]:
        share = row["increment_share_of_worker_slope"]
        lines.append(
            "| {difficulty} | {n} | {worker:.4f} | {both:.4f} | {inc:+.4f} | {share} |".format(
                difficulty=row["difficulty"],
                n=row["swarm_size"],
                worker=float(row["worker_diversity_slope"]),
                both=float(row["worker_plus_verifier_diversity_slope"]),
                inc=float(row["verifier_assignment_increment"]),
                share="n/a" if share is None else f"{float(share):+.1%}",
            )
        )

    summary = result["summary"]
    lines += [
        "",
        "## Summary",
        "",
        f"- curves measured: {summary['curves']}",
        "- curves whose advantage is proportional to retained independence "
        f"(uncentered R^2 >= 0.99 through the origin): "
        f"{summary['curves_proportional_to_retained_independence']}",
        "- curves still resolved at the one correlation this repository has "
        f"measured: {summary['curves_resolved_at_measured_reference']}",
        "- curves resolved at every swept correlation: "
        f"{summary['curves_resolved_at_every_swept_correlation']}",
        "- cells where randomizing verifier assignment raised the slope: "
        f"{summary['cells_where_verifier_assignment_raised_the_slope']} of "
        f"{len(result['verifier_assignment_increment'])}",
        "- largest absolute verifier-assignment increment: "
        f"{float(summary['max_absolute_verifier_assignment_increment']):.4f} "
        f"({float(summary['max_verifier_increment_share_of_worker_slope']):.1%} "
        "of the worker-diversity slope in that cell)",
    ]

    reference = result["measured_reference_correlation"]
    lines += [
        "",
        "## Reference point",
        "",
        f"The only pairwise error correlation measured in this repository is "
        f"`{reference['value']}`, on {reference['measured_on']} "
        f"(`{reference['source']}`). {reference['caveat']}",
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
        raise argparse.ArgumentTypeError("use name:quality comma-separated pairs") from exc
    return tuple(parsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_correlation_threshold",
        description=(
            "Sweep the assumed worker-error correlation and report where the "
            "equal-budget diversity advantage stops resolving."
        ),
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
        "--correlations",
        type=_parse_floats,
        default=DEFAULT_CORRELATIONS,
        help="comma-separated assumed worker-error correlations, ascending",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_correlation_sweep(
        CorrelationSweepConfig(
            base=R1ScalingConfig(
                tasks_per_trial=args.tasks,
                trials=args.trials,
                base_seed=args.seed,
                swarm_sizes=args.swarm_sizes,
                difficulty_levels=args.difficulties,
            ),
            correlations=args.correlations,
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
