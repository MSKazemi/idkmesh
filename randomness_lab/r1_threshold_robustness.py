"""Bootstrap and familywise sensitivity audit for synthetic R1 thresholds.

The canonical :mod:`randomness_lab.r1_low_diversity_threshold` analysis reports
normal-approximation intervals over paired deterministic seed replications. This
module is a deliberately separate downstream audit: it recomputes the same paired
seed-level marginal effects, asks whether a deterministic percentile bootstrap
supports the same directional interpretation, and then applies an exact sign test
with Holm-Bonferroni correction across the emitted threshold questions.

The bootstrap and sign tests are robustness diagnostics over a finite synthetic
seed sample. They are not population guarantees and are not real coding-agent
evidence. The exact sign test also targets directional/median consistency rather
than the magnitude of the mean effect, so it is corroborating evidence rather than
a replacement for the paired mean estimand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
SIGN_TEST_METHOD = "two-sided-exact-binomial-sign-v1"
MULTIPLICITY_METHOD = "holm-bonferroni-familywise-v1"
FAMILYWISE_ALPHA = 0.05


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
    observed values. Replaying the same input therefore produces exactly the same
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


def _exact_two_sided_sign_test(values: Sequence[float]) -> dict[str, object]:
    """Return an exact two-sided sign test for directional seed consistency.

    Zero effects are omitted, as in the classical sign test. Conditional on the
    number of non-zero effects, the null treats positive/negative signs as equally
    likely. The two-sided p-value is the doubled smaller binomial tail, capped at 1.

    This tests a median/directional null, not the paired mean estimand summarized by
    the normal and bootstrap intervals. It therefore acts only as corroboration.
    """

    numeric = [float(value) for value in values]
    if not numeric:
        raise ValueError("sign tests require observations")
    if any(not math.isfinite(value) for value in numeric):
        raise ValueError("sign-test observations must be finite")

    positive = sum(value > 0.0 for value in numeric)
    negative = sum(value < 0.0 for value in numeric)
    zero = len(numeric) - positive - negative
    nonzero = positive + negative

    if positive > negative:
        direction = "positive"
    elif negative > positive:
        direction = "negative"
    else:
        direction = "uncertain"

    if nonzero == 0:
        raw_p_value = 1.0
    else:
        extreme = min(positive, negative)
        denominator = 2**nonzero
        one_sided_tail = sum(
            math.comb(nonzero, successes) for successes in range(extreme + 1)
        ) / denominator
        raw_p_value = min(1.0, 2.0 * one_sided_tail)

    return {
        "method": SIGN_TEST_METHOD,
        "n_total": len(numeric),
        "n_nonzero": nonzero,
        "positive": positive,
        "negative": negative,
        "zero": zero,
        "direction": direction,
        "raw_p_value": raw_p_value,
    }


def _apply_holm_bonferroni(
    tests: Sequence[dict[str, object]],
    *,
    alpha: float = FAMILYWISE_ALPHA,
) -> None:
    """Annotate sign-test records with Holm-adjusted p-values in place."""

    if not 0.0 < alpha < 1.0:
        raise ValueError("familywise alpha must be in (0, 1)")
    family_size = len(tests)
    if family_size == 0:
        return

    indexed: list[tuple[int, dict[str, object]]] = list(enumerate(tests))
    try:
        ordered = sorted(
            indexed,
            key=lambda item: (float(item[1]["raw_p_value"]), item[0]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Holm correction requires numeric raw_p_value entries") from exc

    running_adjusted = 0.0
    for rank, (_, record) in enumerate(ordered):
        raw_p_value = float(record["raw_p_value"])
        if not 0.0 <= raw_p_value <= 1.0 or not math.isfinite(raw_p_value):
            raise ValueError("raw p-values must be finite and in [0, 1]")
        candidate = min(1.0, (family_size - rank) * raw_p_value)
        running_adjusted = max(running_adjusted, candidate)
        record["holm_adjusted_p_value"] = running_adjusted
        record["family_size"] = family_size
        record["familywise_alpha"] = alpha
        record["holm_reject"] = running_adjusted <= alpha


def _robust_direction(normal: str, bootstrap: str) -> str:
    if normal == bootstrap and normal in {"positive", "negative"}:
        return normal
    return "uncertain"


def _familywise_direction(
    interval_robust: str,
    sign_test: dict[str, object],
) -> str:
    if (
        interval_robust in {"positive", "negative"}
        and sign_test.get("direction") == interval_robust
        and sign_test.get("holm_reject") is True
    ):
        return interval_robust
    return "uncertain"


def audit_threshold_robustness(result: dict[str, object]) -> dict[str, object]:
    """Audit whether R1 threshold labels survive method and multiplicity checks.

    The existing low-diversity analyzer remains authoritative for the base
    definitions and fail-closed payload validation. This function reuses its
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
    sign_test_family: list[dict[str, object]] = []
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
            marginal_sign_test = _exact_two_sided_sign_test(marginal_values)
            sign_test_family.append(marginal_sign_test)

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
                change_sign_test = _exact_two_sided_sign_test(change_values)
                sign_test_family.append(change_sign_test)
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
                    "sign_test": change_sign_test,
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
                        "sign_test": marginal_sign_test,
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

    _apply_holm_bonferroni(sign_test_family)

    for difficulty in audits:
        transitions = difficulty["transitions"]
        for row in transitions:
            marginal = row["marginal"]
            marginal_familywise = _familywise_direction(
                marginal["robust_classification"], marginal["sign_test"]
            )
            marginal["familywise_robust_classification"] = marginal_familywise
            row["supported_negative_return_familywise"] = (
                marginal_familywise == "negative"
            )

            change = row["change_from_previous_marginal"]
            if change is None:
                row["supported_diminishing_return_familywise"] = False
                continue
            change_familywise = _familywise_direction(
                change["robust_classification"], change["sign_test"]
            )
            change["familywise_robust_classification"] = change_familywise
            row["supported_diminishing_return_familywise"] = (
                change_familywise == "negative"
            )

        difficulty["first_familywise_diminishing_to_n"] = next(
            (
                row["to_n"]
                for row in transitions
                if row["supported_diminishing_return_familywise"]
            ),
            None,
        )
        difficulty["first_familywise_negative_to_n"] = next(
            (
                row["to_n"]
                for row in transitions
                if row["supported_negative_return_familywise"]
            ),
            None,
        )

    return {
        "schema_version": 2,
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
        "multiplicity": {
            "method": MULTIPLICITY_METHOD,
            "alpha": FAMILYWISE_ALPHA,
            "sign_test_method": SIGN_TEST_METHOD,
            "tests_in_family": len(sign_test_family),
            "family_definition": (
                "all marginal and change-from-previous-marginal sign tests emitted "
                "across every difficulty and adjacent swarm-size transition"
            ),
            "sign_test_estimand": (
                "directional/median consistency of non-zero paired seed-level effects"
            ),
        },
        "classification_disagreements": disagreement_count,
        "difficulties": audits,
        "interpretation_guardrail": (
            "The existing robust label still requires the normal-approximation "
            "interval and deterministic percentile bootstrap to agree on a strictly "
            "positive or negative direction. The stricter familywise label also "
            "requires an exact two-sided sign test to point in the same direction "
            "after Holm-Bonferroni correction over every emitted marginal and "
            "change-from-previous-marginal question. The sign test targets directional "
            "or median consistency, not mean effect magnitude, and its exact p-value "
            "assumes independent/exchangeable signs under the null; zero effects are "
            "omitted. Holm control is conditional on those test assumptions and the "
            "declared family. None of these layers turns deterministic synthetic seed "
            "replications into a population sample of real software tasks, "
            "contributors, or coding agents."
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
        "A directional threshold is interval-robust only when the existing ",
        "normal-approximation interval and deterministic percentile bootstrap agree. ",
        "A familywise-robust label additionally requires a same-direction exact sign ",
        "test after Holm-Bonferroni correction across the full emitted test family.",
        "",
        "| Difficulty | N | Normal 95% interval | Bootstrap 95% interval | Interval robust | Holm-adjusted sign p | Familywise robust | Diminishing familywise |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for difficulty in audit["difficulties"]:
        for row in difficulty["transitions"]:
            marginal = row["marginal"]
            sign_test = marginal["sign_test"]
            lines.append(
                f"| {difficulty['difficulty']} | {row['from_n']}→{row['to_n']} "
                f"| {_format_interval(marginal['normal_approx_95_ci'])} "
                f"| {_format_interval(marginal['bootstrap_95_ci'])} "
                f"| {marginal['robust_classification']} "
                f"| {sign_test['holm_adjusted_p_value']:.4g} "
                f"| {marginal['familywise_robust_classification']} "
                f"| {'yes' if row['supported_diminishing_return_familywise'] else 'no'} |"
            )

    lines.extend(["", "## First thresholds", ""])
    for difficulty in audit["difficulties"]:
        robust_diminishing = difficulty["first_robust_diminishing_to_n"]
        robust_negative = difficulty["first_robust_negative_to_n"]
        familywise_diminishing = difficulty["first_familywise_diminishing_to_n"]
        familywise_negative = difficulty["first_familywise_negative_to_n"]
        lines.append(
            f"- **{difficulty['difficulty']}** — interval-robust diminishing to N: "
            f"{'none' if robust_diminishing is None else robust_diminishing}; "
            f"interval-robust negative to N: "
            f"{'none' if robust_negative is None else robust_negative}; "
            f"familywise diminishing to N: "
            f"{'none' if familywise_diminishing is None else familywise_diminishing}; "
            f"familywise negative to N: "
            f"{'none' if familywise_negative is None else familywise_negative}."
        )

    lines.extend(
        [
            "",
            f"Interval-classification disagreements: **{audit['classification_disagreements']}**.",
            f"Holm family size: **{audit['multiplicity']['tests_in_family']}** tests at alpha={audit['multiplicity']['alpha']}.",
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
