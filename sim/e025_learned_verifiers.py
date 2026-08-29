#!/usr/bin/env python3
"""E025: learn verifier reliability and dependence from calibration history.

Calibration and held-out streams use disjoint deterministic RNG namespaces.
The learned model is frozen before evaluation, and prediction accepts votes --
not held-out truth. This is a synthetic falsification experiment, not a
production reputation system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean, stdev
from typing import Iterable, Sequence

try:
    from sim.e015_analyze import effective_n as e015_effective_n
except ModuleNotFoundError:  # Direct execution from outside the repository root.
    from e015_analyze import effective_n as e015_effective_n

METHODS = (
    "naive_majority", "declared_group_oracle", "inferred_dependence_groups",
    "effective_sample_heuristic", "empirical_effective_evidence",
    "bayesian_reliability", "combined_reliability_dependence",
)


@dataclass(frozen=True)
class Verifier:
    name: str
    group: str
    accuracy: float


@dataclass(frozen=True)
class Observation:
    truth: bool
    votes: tuple[bool, ...]


@dataclass(frozen=True)
class Scenario:
    name: str
    calibration_accuracy: tuple[float, ...]
    evaluation_accuracy: tuple[float, ...]
    calibration_correlation: float
    evaluation_correlation: float
    calibration_dependence: str
    evaluation_dependence: str
    purpose: str


@dataclass(frozen=True)
class LearnedModel:
    names: tuple[str, ...]
    declared_groups: tuple[str, ...]
    accuracy_mean: tuple[float, ...]
    accuracy_ci_low: tuple[float, ...]
    accuracy_ci_high: tuple[float, ...]
    error_correlations: tuple[tuple[float, ...], ...]
    inferred_clusters: tuple[tuple[int, ...], ...]
    cluster_accuracy: tuple[float, ...]
    calibration_digest: str
    calibration_trials: int


BASE_PANEL = (
    *(Verifier(f"cluster_{i}", "cluster", .72) for i in range(1, 8)),
    Verifier("solo_low", "solo_low", .62),
    Verifier("solo_mid", "solo_mid", .74),
    Verifier("solo_high", "solo_high", .84),
    Verifier("solo_best", "solo_best", .90),
)
BASE_ACCURACY = tuple(v.accuracy for v in BASE_PANEL)
SHIFTED_ACCURACY = (.88,) * 7 + (.58, .60, .63, .66)
SCENARIOS = (
    Scenario("stable_shared_shock", BASE_ACCURACY, BASE_ACCURACY, .70, .70,
             "shared-shock", "shared-shock", "stable E013 dependence shape"),
    Scenario("stable_item_difficulty", BASE_ACCURACY, BASE_ACCURACY, .70, .70,
             "item-difficulty", "item-difficulty", "stable E017/E018 partial-failure shape"),
    Scenario("reliability_shift", BASE_ACCURACY, SHIFTED_ACCURACY, .70, .70,
             "item-difficulty", "item-difficulty", "historical reliability reverses"),
    Scenario("dependence_dissipates", BASE_ACCURACY, BASE_ACCURACY, .80, 0.,
             "item-difficulty", "item-difficulty", "learned discount throws away new independence"),
    Scenario("dependence_emerges", BASE_ACCURACY, BASE_ACCURACY, 0., .80,
             "item-difficulty", "item-difficulty", "unseen dependence creates false-confidence risk"),
)


def panel(accuracies: Sequence[float]) -> tuple[Verifier, ...]:
    if len(accuracies) != len(BASE_PANEL) or any(not .5 < x < 1 for x in accuracies):
        raise ValueError("accuracy vector must match panel and be in (0.5, 1)")
    return tuple(Verifier(v.name, v.group, float(a)) for v, a in zip(BASE_PANEL, accuracies))


def group_indices(verifiers: Sequence[Verifier]) -> tuple[tuple[int, ...], ...]:
    groups: dict[str, list[int]] = {}
    for i, verifier in enumerate(verifiers):
        groups.setdefault(verifier.group, []).append(i)
    return tuple(tuple(indices) for indices in groups.values())


def _correctness(size: int, accuracy: float, rho: float, shape: str,
                 rng: random.Random) -> list[bool]:
    if shape == "shared-shock":
        if rng.random() < rho:
            return [rng.random() < accuracy] * size
        return [rng.random() < accuracy for _ in range(size)]
    if shape != "item-difficulty":
        raise ValueError(f"unknown dependence model: {shape}")
    if rho <= 0:
        return [rng.random() < accuracy for _ in range(size)]
    if rho >= 1:
        return [rng.random() < accuracy] * size
    scale = (1 - rho) / rho
    difficulty = rng.betavariate((1 - accuracy) * scale, accuracy * scale)
    return [rng.random() >= difficulty for _ in range(size)]


def generate_stream(verifiers: Sequence[Verifier], rho: float, shape: str,
                    trials: int, seed: int) -> tuple[Observation, ...]:
    if trials < 2 or trials % 2 or not 0 <= rho <= 1:
        raise ValueError("trials must be even >=2 and correlation in [0,1]")
    rng, groups, rows = random.Random(seed), group_indices(verifiers), []
    for trial in range(trials):
        truth, votes = trial % 2 == 0, [False] * len(verifiers)
        for indices in groups:
            accuracies = {verifiers[i].accuracy for i in indices}
            if len(accuracies) != 1:
                raise ValueError("accuracy must be equal within each dependence group")
            for index, correct in zip(indices, _correctness(
                    len(indices), next(iter(accuracies)), rho, shape, rng)):
                votes[index] = truth if correct else not truth
        rows.append(Observation(truth, tuple(votes)))
    return tuple(rows)


def stream_digest(rows: Sequence[Observation]) -> str:
    data = "".join(("1" if r.truth else "0") +
                   "".join("1" if v else "0" for v in r.votes) for r in rows)
    return hashlib.sha256(data.encode()).hexdigest()


def _phi(xs: Sequence[bool], ys: Sequence[bool]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx, vy = mx * (1 - mx), my * (1 - my)
    if vx == 0 or vy == 0:
        return 0.
    covariance = sum(x and y for x, y in zip(xs, ys)) / len(xs) - mx * my
    return max(-1., min(1., covariance / math.sqrt(vx * vy)))


def _components(matrix: Sequence[Sequence[float]], threshold: float) -> tuple[tuple[int, ...], ...]:
    remaining, answer = set(range(len(matrix))), []
    while remaining:
        stack, found = [min(remaining)], set()
        while stack:
            node = stack.pop()
            if node in found:
                continue
            found.add(node); remaining.discard(node)
            stack.extend(j for j in tuple(remaining) if matrix[node][j] >= threshold)
        answer.append(tuple(sorted(found)))
    return tuple(answer)


def _posterior(correct: int, total: int) -> tuple[float, float, float]:
    a, b = 1 + correct, 1 + total - correct
    mu = a / (a + b)
    half = 1.96 * math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return mu, max(0., mu - half), min(1., mu + half)


def calibrate(verifiers: Sequence[Verifier], history: Sequence[Observation],
              threshold: float = .20) -> LearnedModel:
    if not history or any(len(r.votes) != len(verifiers) for r in history):
        raise ValueError("nonempty calibration rows must match panel")
    errors = [[r.votes[i] != r.truth for r in history] for i in range(len(verifiers))]
    intervals = [_posterior(sum(not e for e in col), len(history)) for col in errors]
    matrix = tuple(tuple(1. if i == j else _phi(errors[i], errors[j])
                         for j in range(len(verifiers))) for i in range(len(verifiers)))
    clusters = _components(matrix, threshold)
    cluster_accuracy = tuple(sum(
        (sum(r.votes[i] for i in cluster) > len(cluster) / 2) == r.truth for r in history
    ) / len(history) for cluster in clusters)
    return LearnedModel(
        tuple(v.name for v in verifiers), tuple(v.group for v in verifiers),
        tuple(x[0] for x in intervals), tuple(x[1] for x in intervals),
        tuple(x[2] for x in intervals), matrix, clusters, cluster_accuracy,
        stream_digest(history), len(history),
    )


def _cluster_probability(votes: Sequence[bool], clusters: Sequence[Sequence[int]]) -> float:
    decisions = [sum(votes[i] for i in c) > len(c) / 2 for c in clusters]
    return sum(decisions) / len(decisions)


def _rho(model: LearnedModel, cluster: Sequence[int]) -> float:
    pairs = [model.error_correlations[i][j] for p, i in enumerate(cluster) for j in cluster[p + 1:]]
    return max(0., mean(pairs)) if pairs else 0.


def _weighted(votes: Sequence[bool], weights: Sequence[float]) -> float:
    return sum(w for v, w in zip(votes, weights) if v) / sum(weights) if sum(weights) else .5


def independent_error(n: int, accuracy: float) -> float:
    """Probability that an odd, independent panel has too few correct votes."""
    need = n // 2 + 1
    return sum(math.comb(n, k) * accuracy**k * (1 - accuracy)**(n-k) for k in range(need))


def empirical_neff(group_accuracy: float, member_accuracy: float, maximum: int) -> float:
    """Continuous E015 effective size fitted to calibration group error."""
    if member_accuracy <= .5:
        # E015 defines n_eff only for a better-than-chance reference verifier.
        # A short-history estimate that misses that gate gets no panel bonus.
        return 1.
    largest_odd = maximum if maximum % 2 else maximum - 1
    return e015_effective_n(
        1 - group_accuracy, member_accuracy, .5, nmax=largest_odd + 2
    )


@lru_cache(maxsize=None)
def _prediction_plan(model: LearnedModel) -> tuple[object, ...]:
    declared: dict[str, list[int]] = {}
    for i, group in enumerate(model.declared_groups):
        declared.setdefault(group, []).append(i)
    heuristic, empirical = [1.] * len(model.names), [1.] * len(model.names)
    for cluster, accuracy in zip(model.inferred_clusters, model.cluster_accuracy):
        discount = 1 / (1 + (len(cluster) - 1) * _rho(model, cluster))
        eff = empirical_neff(accuracy, mean(model.accuracy_mean[i] for i in cluster), len(cluster))
        for i in cluster:
            heuristic[i], empirical[i] = discount, eff / len(cluster)
    reliability = [max(0., math.log(a / (1 - a))) for a in model.accuracy_mean]
    combined = list(reliability)
    for cluster in model.inferred_clusters:
        discount = 1 / (1 + (len(cluster) - 1) * _rho(model, cluster))
        for i in cluster:
            combined[i] *= discount
    return (tuple(map(tuple, declared.values())), tuple(heuristic), tuple(empirical),
            tuple(reliability), tuple(combined))


def predict_probabilities(votes: Sequence[bool], model: LearnedModel) -> dict[str, float]:
    """Predict with a frozen model. Held-out truth cannot enter this interface."""
    declared_clusters, heuristic, empirical, reliability, combined = _prediction_plan(model)

    def logistic(weights: Sequence[float]) -> float:
        score = sum(w * (1 if vote else -1) for vote, w in zip(votes, weights))
        return 1 / (1 + math.exp(-max(-40, min(40, score))))

    return {
        "naive_majority": sum(votes) / len(votes),
        "declared_group_oracle": _cluster_probability(votes, declared_clusters),
        "inferred_dependence_groups": _cluster_probability(votes, model.inferred_clusters),
        "effective_sample_heuristic": _weighted(votes, heuristic),
        "empirical_effective_evidence": _weighted(votes, empirical),
        "bayesian_reliability": logistic(reliability),
        "combined_reliability_dependence": logistic(combined),
    }


def evaluate(model: LearnedModel, heldout: Sequence[Observation]) -> dict[str, dict[str, float]]:
    keys = ("fa", "fr", "errors", "brier", "confidence", "high_confidence_errors")
    counts = {method: dict.fromkeys(keys, 0.) for method in METHODS}
    for row in heldout:
        for method, probability in predict_probabilities(row.votes, model).items():
            decision, wrong = probability > .5, (probability > .5) != row.truth
            c = counts[method]
            c["fa"] += decision and not row.truth; c["fr"] += not decision and row.truth
            c["errors"] += wrong; c["brier"] += (probability - row.truth) ** 2
            c["confidence"] += 2 * abs(probability - .5)
            c["high_confidence_errors"] += wrong and (probability <= .1 or probability >= .9)
    positive, total = sum(r.truth for r in heldout), len(heldout)
    return {method: {
        "false_accept_rate": c["fa"] / (total - positive),
        "false_reject_rate": c["fr"] / positive,
        "error_rate": c["errors"] / total,
        "brier_score": c["brier"] / total,
        "mean_confidence": c["confidence"] / total,
        "high_confidence_error_rate": c["high_confidence_errors"] / total,
    } for method, c in counts.items()}


def summary(values: Sequence[float]) -> dict[str, float | int]:
    mu, sd = mean(values), stdev(values) if len(values) > 1 else 0.
    half = 1.96 * sd / math.sqrt(len(values))
    return {"n": len(values), "mean": round(mu, 6), "stdev": round(sd, 6),
            "ci95_low": round(mu-half, 6), "ci95_high": round(mu+half, 6),
            "min": round(min(values), 6), "max": round(max(values), 6)}


def correlation_diagnostics(model: LearnedModel, true_rho: float) -> dict[str, float]:
    errors = []
    for i in range(len(model.names)):
        for j in range(i + 1, len(model.names)):
            expected = true_rho if model.declared_groups[i] == model.declared_groups[j] else 0.
            errors.append(model.error_correlations[i][j] - expected)
    true_groups = {tuple(i for i, x in enumerate(model.declared_groups) if x == group)
                   for group in model.declared_groups}
    return {
        "pairwise_correlation_mae": mean(abs(x) for x in errors),
        "pairwise_correlation_signed_error": mean(errors),
        "overestimated_independence_pair_rate": mean(x < -.05 for x in errors),
        "underestimated_independence_pair_rate": mean(x > .05 for x in errors),
        "exact_group_recovery": float(set(model.inferred_clusters) == true_groups),
    }


def evidence_diagnostics(model: LearnedModel, true_rho: float) -> dict[str, float]:
    learned = empirical = 0.
    for cluster, accuracy in zip(model.inferred_clusters, model.cluster_accuracy):
        learned += len(cluster) / (1 + (len(cluster)-1) * _rho(model, cluster))
        empirical += empirical_neff(accuracy, mean(model.accuracy_mean[i] for i in cluster), len(cluster))
    declared_sizes: dict[str, int] = {}
    for group in model.declared_groups:
        declared_sizes[group] = declared_sizes.get(group, 0) + 1
    true_heuristic = sum(n / (1 + (n-1)*true_rho) for n in declared_sizes.values())
    return {"learned_rho_heuristic_total": learned, "true_rho_heuristic_total": true_heuristic,
            "calibration_observed_effective_total": empirical,
            "nominal_verifiers": float(len(model.names))}


def run_cell(scenario: Scenario, history_trials: int, heldout_trials: int,
             seeds: int, seed_start: int) -> dict[str, object]:
    rows = []
    for seed in range(seed_start, seed_start + seeds):
        calibration = generate_stream(panel(scenario.calibration_accuracy),
            scenario.calibration_correlation, scenario.calibration_dependence,
            history_trials, 1_000_003 + seed * 10_007)
        heldout = generate_stream(panel(scenario.evaluation_accuracy),
            scenario.evaluation_correlation, scenario.evaluation_dependence,
            heldout_trials, 2_000_003 + seed * 10_009)
        model = calibrate(panel(scenario.calibration_accuracy), calibration)
        rows.append({"metrics": evaluate(model, heldout),
                     "correlation": correlation_diagnostics(model, scenario.calibration_correlation),
                     "heldout_correlation": correlation_diagnostics(model, scenario.evaluation_correlation),
                     "evidence": evidence_diagnostics(model, scenario.calibration_correlation),
                     "interval_width": mean(h-l for l, h in zip(model.accuracy_ci_low, model.accuracy_ci_high)),
                     "calibration_digest": model.calibration_digest,
                     "heldout_digest": stream_digest(heldout)})
    metric_names = tuple(rows[0]["metrics"][METHODS[0]])
    corr_names, evidence_names = tuple(rows[0]["correlation"]), tuple(rows[0]["evidence"])
    return {
        "scenario": scenario.name, "purpose": scenario.purpose,
        "history_trials": history_trials, "heldout_trials": heldout_trials,
        "calibration": {"correlation": scenario.calibration_correlation,
                        "dependence": scenario.calibration_dependence,
                        "accuracy": list(scenario.calibration_accuracy)},
        "heldout": {"correlation": scenario.evaluation_correlation,
                    "dependence": scenario.evaluation_dependence,
                    "accuracy": list(scenario.evaluation_accuracy)},
        "metrics": {method: {metric: summary([r["metrics"][method][metric] for r in rows])
                              for metric in metric_names} for method in METHODS},
        "correlation_estimation": {name: summary([r["correlation"][name] for r in rows])
                                   for name in corr_names},
        "heldout_correlation_misspecification": {
            name: summary([r["heldout_correlation"][name] for r in rows]) for name in corr_names
        },
        "effective_evidence": {name: summary([r["evidence"][name] for r in rows])
                               for name in evidence_names},
        "model_uncertainty": {"mean_accuracy_ci95_width": summary([r["interval_width"] for r in rows]),
                              "interval": "normal approximation to Beta(1,1) posterior"},
        "stream_identity": {"distinct_calibration_digests": len({r["calibration_digest"] for r in rows}),
                            "distinct_heldout_digests": len({r["heldout_digest"] for r in rows})},
    }


def run_experiment(histories: Iterable[int], heldout_trials: int, seeds: int,
                   seed_start: int = 0, scenarios: Sequence[Scenario] = SCENARIOS) -> dict[str, object]:
    histories = tuple(histories)
    cells = [run_cell(s, h, heldout_trials, seeds, seed_start) for s in scenarios for h in histories]
    improvement = [c for c in cells if c["scenario"].startswith("stable_") and
                   c["metrics"]["combined_reliability_dependence"]["error_rate"]["mean"] <
                   c["metrics"]["naive_majority"]["error_rate"]["mean"]]
    harm = [c for c in cells if not c["scenario"].startswith("stable_") and
            c["metrics"]["combined_reliability_dependence"]["error_rate"]["mean"] >
            c["metrics"]["naive_majority"]["error_rate"]["mean"]]
    return {
        "schema_version": "e025.learned-verifier-results.v1",
        "experiment": "E025-learned-verifier-reliability-dependence",
        "configuration": {"seed_start": seed_start, "seeds": seeds,
            "history_trials": list(histories), "heldout_trials": heldout_trials,
            "panel": [v.__dict__ for v in BASE_PANEL], "correlation_threshold": .20,
            "methods": list(METHODS),
            "uncertainty": "95% normal intervals across independent deterministic seeds"},
        "separation": {"calibration_seed_formula": "1000003 + seed * 10007",
            "heldout_seed_formula": "2000003 + seed * 10009",
            "frozen_model_before_heldout": True, "heldout_truth_available_to_aggregator": False,
            "matched_heldout_votes_across_methods": True},
        "findings": {"stable_improvement_cells": len(improvement), "shift_harm_cells": len(harm),
            "improvement_observed": bool(improvement), "harm_observed": bool(harm),
            "production_reputation_claim": False},
        "cells": cells,
        "limitations": [
            "All outcomes are synthetic; learned scores are not production-ready reputation.",
            "Declared groups are used only by the oracle reference and diagnostics.",
            "Pairwise correlation does not identify dependence shape or shared blind spots.",
            "N/(1+(N-1)rho) is an intentionally unsafe E015 baseline, not a confidence guarantee.",
            "The shared-shock ceiling is not applied under item difficulty because E018 found it model-specific.",
            "Intervals are descriptive and are not sequential guarantees.",
        ],
    }


def parse_histories(raw: str) -> tuple[int, ...]:
    values = tuple(int(x) for x in raw.split(",") if x.strip())
    if not values or any(x < 2 or x % 2 for x in values):
        raise ValueError("history lengths must be even integers >= 2")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--histories", default="40,200,1000")
    parser.add_argument("--heldout-trials", type=int, default=2000)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        histories = parse_histories(args.histories)
    except ValueError as exc:
        parser.error(str(exc))
    if args.seeds < 2 or args.heldout_trials < 2 or args.heldout_trials % 2:
        parser.error("seeds must be >=2 and heldout trials even >=2")
    print(json.dumps(run_experiment(histories, args.heldout_trials, args.seeds,
                                    args.seed_start), indent=2 if args.pretty else None,
                     sort_keys=True))


if __name__ == "__main__":
    main()
