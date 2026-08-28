#!/usr/bin/env python3
"""Compare naive and independence-aware verifier aggregation.

E013 asks a deliberately narrow question: if the same verifier votes come from
uneven independence groups, when does counting every vote equally become worse
than first aggregating within each group and then giving groups equal weight?

The simulator is synthetic and transparent. It is designed to falsify simple
coordination claims before those claims become IDKMesh architecture.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass
class DecisionStats:
    trials: int = 0
    false_accepts: int = 0
    false_rejects: int = 0

    def record(self, truth: bool, decision: bool) -> None:
        self.trials += 1
        self.false_accepts += int(decision and not truth)
        self.false_rejects += int((not decision) and truth)

    def as_dict(self) -> Dict[str, float | int]:
        positives = (self.trials + 1) // 2
        negatives = self.trials // 2
        error_count = self.false_accepts + self.false_rejects
        return {
            "trials": self.trials,
            "false_accepts": self.false_accepts,
            "false_rejects": self.false_rejects,
            "false_accept_rate": round(self.false_accepts / negatives, 6) if negatives else 0.0,
            "false_reject_rate": round(self.false_rejects / positives, 6) if positives else 0.0,
            "error_rate": round(error_count / self.trials, 6) if self.trials else 0.0,
        }


def majority(votes: Sequence[bool], quorum: float = 0.5) -> bool:
    if not votes:
        raise ValueError("votes must not be empty")
    return (sum(1 for vote in votes if vote) / len(votes)) > quorum


def parse_group_sizes(raw: str) -> Tuple[int, ...]:
    sizes = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not sizes:
        raise ValueError("at least one independence group is required")
    if any(size < 1 for size in sizes):
        raise ValueError("group sizes must all be >= 1")
    return sizes


def parse_correlations(raw: str) -> Tuple[float, ...]:
    values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("at least one correlation value is required")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("correlations must all be between 0.0 and 1.0")
    return values


def beta_parameters(accuracy: float, correlation: float):
    """Beta(alpha, beta) over task difficulty matching a mean error and an
    intra-class correlation. ``None`` at the degenerate ends."""
    mu = 1.0 - accuracy
    if correlation <= 0.0 or correlation >= 1.0 or mu <= 0.0 or mu >= 1.0:
        return None
    scale = (1.0 - correlation) / correlation
    return mu * scale, (1.0 - mu) * scale


def sample_group_votes(
    truth: bool,
    group_size: int,
    accuracy: float,
    correlation: float,
    rng: random.Random,
    dependence: str = "shared-shock",
    difficulty: float | None = None,
) -> List[bool]:
    """Sample one independence group's votes.

    ``dependence`` selects the within-group model:

    ``"shared-shock"``
        With probability ``correlation`` all members share one correctness draw,
        otherwise each draws independently. The original E013 model, and the
        default so E013 reproduces exactly.
    ``"item-difficulty"``
        The group's task has a difficulty and each member errs independently at
        that rate. E017 measured this shape on a real panel; it spreads
        probability over PARTIAL group failures instead of collapsing the group
        to a single vote.

    ``difficulty`` lets the caller supply one difficulty shared across groups.
    That models the case E017 actually measured, where verifiers sharing no
    declared attribute still shared 53% of their errors -- so "independent"
    groups are not independent.
    """

    if accuracy >= 1.0:
        correctness = [True] * group_size
    elif dependence == "item-difficulty":
        if difficulty is None:
            params = beta_parameters(accuracy, correlation)
            if params is None:
                if correlation >= 1.0:
                    shared = rng.random() < accuracy
                    correctness = [shared] * group_size
                else:
                    correctness = [rng.random() < accuracy for _ in range(group_size)]
                return [truth if c else not truth for c in correctness]
            difficulty = rng.betavariate(*params)
        correctness = [rng.random() >= difficulty for _ in range(group_size)]
    elif rng.random() < correlation:
        shared_correct = rng.random() < accuracy
        correctness = [shared_correct] * group_size
    else:
        correctness = [rng.random() < accuracy for _ in range(group_size)]
    return [truth if correct else not truth for correct in correctness]


def sample_panel(
    truth: bool,
    group_sizes: Sequence[int],
    accuracy: float,
    correlation: float,
    rng: random.Random,
    dependence: str = "shared-shock",
    cross_group: bool = False,
) -> List[List[bool]]:
    """Sample every group's votes.

    With ``cross_group`` the panel draws ONE task difficulty and every group errs
    at that rate, so the declared groups no longer carry independent evidence.
    E017 found real panels look like this, which is the regime where group
    balancing has nothing left to balance.
    """
    difficulty = None
    if cross_group and dependence == "item-difficulty" and accuracy < 1.0:
        params = beta_parameters(accuracy, correlation)
        if params is not None:
            difficulty = rng.betavariate(*params)
        elif correlation >= 1.0:
            # The limit of Beta(alpha, beta) as alpha, beta -> 0: difficulty is
            # 1 or 0 for the whole panel at once. Falling back to per-group
            # sampling here would silently restore the independence that
            # cross_group exists to remove.
            difficulty = 1.0 if rng.random() < (1.0 - accuracy) else 0.0
        else:
            # correlation 0: difficulty is a point mass at the mean error rate.
            difficulty = 1.0 - accuracy
    return [
        sample_group_votes(truth, size, accuracy, correlation, rng,
                           dependence=dependence, difficulty=difficulty)
        for size in group_sizes
    ]


def naive_majority(groups: Sequence[Sequence[bool]], quorum: float = 0.5) -> bool:
    votes = [vote for group in groups for vote in group]
    return majority(votes, quorum)


def group_balanced_majority(groups: Sequence[Sequence[bool]], quorum: float = 0.5) -> bool:
    group_decisions = [majority(group, quorum) for group in groups]
    return majority(group_decisions, quorum)


def run_seed(
    seed: int,
    trials: int,
    group_sizes: Sequence[int],
    accuracy: float,
    correlation: float,
    quorum: float = 0.5,
) -> Dict[str, object]:
    rng = random.Random(seed)
    naive = DecisionStats()
    balanced = DecisionStats()
    panel_disagreement = 0
    group_disagreement = 0

    # Alternate truth values so prevalence is exactly balanced for even trials.
    for trial in range(trials):
        truth = trial % 2 == 0
        groups = sample_panel(truth, group_sizes, accuracy, correlation, rng)
        flat = [vote for group in groups for vote in group]
        group_decisions = [majority(group, quorum) for group in groups]

        naive_decision = majority(flat, quorum)
        balanced_decision = majority(group_decisions, quorum)
        naive.record(truth, naive_decision)
        balanced.record(truth, balanced_decision)

        panel_disagreement += int(any(vote != flat[0] for vote in flat[1:]))
        group_disagreement += int(any(decision != group_decisions[0] for decision in group_decisions[1:]))

    return {
        "seed": seed,
        "correlation": correlation,
        "naive_majority": naive.as_dict(),
        "group_balanced": balanced.as_dict(),
        "panel_disagreement_rate": round(panel_disagreement / trials, 6),
        "group_disagreement_rate": round(group_disagreement / trials, 6),
    }


def summary_stats(values: Sequence[float]) -> Dict[str, float | int]:
    n = len(values)
    mu = mean(values)
    sd = stdev(values) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n else 0.0
    return {
        "n": n,
        "mean": round(mu, 6),
        "stdev": round(sd, 6),
        "ci95_low": round(mu - half, 6),
        "ci95_high": round(mu + half, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def sweep(
    correlations: Iterable[float],
    seeds: int,
    seed_start: int,
    trials: int,
    group_sizes: Sequence[int],
    accuracy: float,
    quorum: float = 0.5,
) -> Dict[str, object]:
    levels = []
    correlations = list(correlations)

    for correlation in correlations:
        rows = [
            run_seed(
                seed=seed,
                trials=trials,
                group_sizes=group_sizes,
                accuracy=accuracy,
                correlation=correlation,
                quorum=quorum,
            )
            for seed in range(seed_start, seed_start + seeds)
        ]

        metrics: Dict[str, Dict[str, object]] = {}
        for method in ("naive_majority", "group_balanced"):
            metrics[method] = {
                metric: summary_stats([float(row[method][metric]) for row in rows])
                for metric in ("false_accept_rate", "false_reject_rate", "error_rate")
            }

        balanced_wins = sum(
            int(float(row["group_balanced"]["error_rate"]) < float(row["naive_majority"]["error_rate"]))
            for row in rows
        )
        naive_wins = sum(
            int(float(row["naive_majority"]["error_rate"]) < float(row["group_balanced"]["error_rate"]))
            for row in rows
        )
        ties = seeds - balanced_wins - naive_wins

        levels.append(
            {
                "correlation": correlation,
                "aggregate": metrics,
                "pairwise": {
                    "group_balanced_wins": balanced_wins,
                    "naive_majority_wins": naive_wins,
                    "ties": ties,
                    "trials": seeds,
                    "group_balanced_win_rate": round(balanced_wins / seeds, 6),
                },
                "panel_disagreement_rate": summary_stats(
                    [float(row["panel_disagreement_rate"]) for row in rows]
                ),
                "group_disagreement_rate": summary_stats(
                    [float(row["group_disagreement_rate"]) for row in rows]
                ),
            }
        )

    crossover = None
    for level in levels:
        balanced_error = level["aggregate"]["group_balanced"]["error_rate"]["mean"]
        naive_error = level["aggregate"]["naive_majority"]["error_rate"]["mean"]
        if balanced_error < naive_error:
            crossover = level["correlation"]
            break

    return {
        "experiment": "independence-aware-verifier-aggregation-v0",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "trials_per_seed": trials,
            "group_sizes": list(group_sizes),
            "nominal_verifiers": sum(group_sizes),
            "independence_groups": len(group_sizes),
            "individual_accuracy": accuracy,
            "quorum": quorum,
            "correlations": correlations,
        },
        "first_observed_crossover_correlation": crossover,
        "levels": levels,
        "limitations": [
            "Independence-group labels are assumed known rather than inferred from evidence.",
            "All verifiers share the same marginal accuracy in this first model.",
            "Within-group dependence uses a simple shared-correctness mixture.",
            "The experiment classifies synthetic binary claims, not real software changes.",
            "Group-balanced voting is a transparent baseline, not a proposed final trust algorithm.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-sizes", default="7,1,1,1,1")
    parser.add_argument("--correlations", default="0,0.25,0.5,0.75,1")
    parser.add_argument("--accuracy", type=float, default=0.75)
    parser.add_argument("--quorum", type=float, default=0.5)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        args.group_sizes = parse_group_sizes(args.group_sizes)
        args.correlations = parse_correlations(args.correlations)
    except ValueError as exc:
        parser.error(str(exc))

    if not 0.5 <= args.accuracy <= 1.0:
        parser.error("--accuracy must be between 0.5 and 1.0")
    if not 0.0 <= args.quorum < 1.0:
        parser.error("--quorum must be in [0.0, 1.0)")
    if args.seeds < 2:
        parser.error("--seeds must be >= 2")
    if args.trials < 2 or args.trials % 2:
        parser.error("--trials must be an even integer >= 2")
    return args


def main() -> None:
    args = parse_args()
    result = sweep(
        correlations=args.correlations,
        seeds=args.seeds,
        seed_start=args.seed_start,
        trials=args.trials,
        group_sizes=args.group_sizes,
        accuracy=args.accuracy,
        quorum=args.quorum,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
