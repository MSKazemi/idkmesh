"""E049 -- derived measurements issue 22 names and E024 does not report.

Issue 22 lists measurements that the emergence simulations never aggregated:

* *recovery time from an incorrect initial objective* -- E024's per-seed
  ``recovery_generations`` is self-relative (95% of the arm's *own* final value),
  so an arm that never leaves a low plateau "recovers" at generation 0, and
  ``matched_budget_emergence`` says it is not aggregated;
* *diversity of viable architectures* -- ``archive_size`` exists only for the
  Quality-Diversity arm and is ``0`` by construction for the other four, so it is
  no cross-arm measure at all;
* *compute per verified improvement* -- E024 reports only that every arm spent
  the same number of proposals.

This module computes the three **post hoc**, from a replay of the E024 arms with
the **same seeds**, without changing a byte of what E024 produced.

How the replay stays faithful
-----------------------------

``replay_seed`` calls ``matched_budget_emergence.run_seed`` itself, so every arm
keeps the proposal stream and verifier stream E024 derived for it
(``seed + offset * STRATEGY_SEED_STRIDE`` and its ``VERIFIER_STREAM_MASK`` twin).
No new randomness is drawn from either stream and no arm is added, which is the
rule that a new arm must reuse the offset of the arm it extends. The only
instrument is a recording wrapper around ``verify_candidate`` that is installed
for the duration of one call and removed in a ``finally``; it forwards every
argument unchanged and returns the original answer, so the verifier stream is
consumed exactly as before. Each arm makes exactly ``agents * generations``
verification calls (``run_seed`` raises otherwise), in proposal order, which is
how a call is attributed to an arm and to a generation without reading any arm's
private state.

The bootstrap draws from its own ``random.Random`` keyed by a string label, never
from a simulator stream.

Nothing here is evidence about real agents or real people. Every candidate,
goal, verdict and cost is synthetic.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterator, List, Sequence, Tuple

import sim.matched_budget_emergence as mbe

sim = mbe.sim

EXPERIMENT_ID = "E049"
EXPERIMENT = "derived-measurements-v1"
EVIDENCE_LEVEL = "synthetic mechanism; no real agents or humans"

STRATEGIES = mbe.STRATEGIES
ARCHIVE_ARM = "qd"

DEFAULT_SEEDS = 100
DEFAULT_SEED_START = 0
DEFAULT_AGENTS = 50
DEFAULT_GENERATIONS = 50
DEFAULT_CHANGE_AT = 25
DEFAULT_BINS = 8

#: Recovery is judged against this fraction of the best utility the *landscape*
#: allows under the changed goal. Fixed before any aggregate was computed, and
#: swept in :data:`SENSITIVITY_FRACTIONS` so no verdict rests on this one value.
PRIMARY_FRACTION = 0.90
SENSITIVITY_FRACTIONS = (0.80, 0.85, 0.90, 0.95, 0.98)

#: An accepted candidate counts as an improvement only if it beats the running
#: best by more than this. ``0.0`` is the strict reading; ``0.01`` asks whether
#: the improvement is material, because a hill-climber emits many tiny records.
PRIMARY_MATERIALITY = 0.0
MATERIAL_THRESHOLD = 0.01
SENSITIVITY_MATERIALITY = (PRIMARY_MATERIALITY, MATERIAL_THRESHOLD)

#: ``carry`` starts the running best at the best changed-goal utility among
#: everything the arm had verified before the change. ``fresh`` starts it at zero
#: when the goal changes, so the arm is credited for re-finding what it already
#: held. Both are reported; ``carry`` is primary.
PRIMARY_MODE = "carry"
IMPROVEMENT_MODES = ("carry", "fresh")


def improvement_key(mode: str, materiality: float) -> str:
    return f"{mode}:{materiality:g}"

DEFAULT_RESAMPLES = 2000
CONFIDENCE = 0.95
OPTIMUM_GRID_STEP = 0.005

#: Per baseline: two recovery readings x (McNemar + time sign test), plus six
#: paired count comparisons; four baselines.
PAIRED_TESTS = 4 * (2 * 2 + 6)

NOT_MEASURED = (
    "human attention: nothing here models a person reading, deciding or waiting, "
    "and proposal counts are not a proxy for it",
    "novelty and information gain: no novelty score or information measure is "
    "defined on candidates in this landscape, and none is invented here",
    "churn: agents never join or leave in the E024 arms",
    "energy and wall time: a proposal is a unit, not a joule or a second",
    "post-integration defects and adversarial contributors: outside the E024 "
    "perfect-panel arms (E027 and E036 model them separately)",
)


# --------------------------------------------------------------------------
# Landscape reference
# --------------------------------------------------------------------------
def reference_optimum(
    goal: Sequence[float] = sim.CHANGED_GOAL, step: float = OPTIMUM_GRID_STEP
) -> Dict[str, Any]:
    """Best utility any viable candidate can reach under ``goal``.

    A deterministic grid over reliability and security with the remaining budget
    given greedily to the other three traits by weight. Utility is linear in
    those three, so the greedy fill is exact for any fixed pair; only the pair is
    gridded, at :data:`OPTIMUM_GRID_STEP`. No arm and no random number is
    involved, so the threshold cannot be tuned to flatter an arm.
    """
    steps = int(round((1.0 - sim.MIN_RELIABILITY) / step))
    grid = [sim.MIN_RELIABILITY + i * step for i in range(steps + 1)]
    free = sorted((1, 2, 3), key=lambda index: -goal[index])
    best_value = -1.0
    best_traits: Tuple[float, ...] = ()
    for reliability in grid:
        for security in grid:
            remaining = sim.BUDGET - reliability - security - 1e-9
            if remaining < 0.0:
                continue
            traits = [reliability, 0.0, 0.0, 0.0, security]
            for index in free:
                spend = min(1.0, remaining)
                traits[index] = spend
                remaining -= spend
            candidate = sim.Candidate(tuple(traits))
            if not sim.viable(candidate):
                continue
            value = sim.utility(candidate, goal)
            if value > best_value:
                best_value, best_traits = value, candidate.traits
    return {
        "optimum_utility": round(best_value, 6),
        "optimum_traits": [round(x, 6) for x in best_traits],
        "method": f"grid over reliability x security at step {step}, "
        "greedy fill of the remaining budget by goal weight",
    }


def threshold_for(fraction: float, optimum: float) -> float:
    return fraction * optimum


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------
@contextlib.contextmanager
def _recording_verifier(log: List[Tuple["sim.Candidate", bool]]) -> Iterator[None]:
    """Record every verifier call without altering it.

    The wrapper forwards all four arguments untouched and returns the original
    answer, so the verifier stream is consumed exactly as it would be unwrapped.
    The module attribute is restored in ``finally`` even if a run raises.
    """
    original = mbe.sim.verify_candidate

    def recording(candidate, rng, config, stats):
        accepted = original(candidate, rng, config, stats)
        log.append((candidate, accepted))
        return accepted

    mbe.sim.verify_candidate = recording
    try:
        yield
    finally:
        mbe.sim.verify_candidate = original


AcceptedRecord = Tuple[int, "sim.Candidate", bool]


def replay_seed(
    seed: int,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    verification: "sim.VerificationConfig | None" = None,
) -> Tuple[Dict[str, Any], Dict[str, List[AcceptedRecord]]]:
    """E024's ``run_seed`` payload plus each arm's per-proposal verdict trace.

    The payload is exactly what an unwrapped ``run_seed`` returns. The trace for
    an arm is ``[(generation, candidate, accepted), ...]`` in proposal order.
    """
    log: List[Tuple["sim.Candidate", bool]] = []
    with _recording_verifier(log):
        payload = mbe.run_seed(seed, agents, generations, change_at, bins, verification)
    budget = agents * generations
    if len(log) != budget * len(STRATEGIES):
        raise RuntimeError("replay did not observe one verification per proposal")
    traces: Dict[str, List[AcceptedRecord]] = {}
    for offset, strategy in enumerate(STRATEGIES):
        chunk = log[offset * budget : (offset + 1) * budget]
        traces[strategy] = [
            (index // agents, candidate, accepted)
            for index, (candidate, accepted) in enumerate(chunk)
        ]
    return payload, traces


# --------------------------------------------------------------------------
# The three measurements
# --------------------------------------------------------------------------
def recovery_time(
    trace: Sequence[float], change_at: int, threshold: float, sustained: bool = False
) -> "int | None":
    """Generations after the change until delivered utility reaches ``threshold``.

    ``0`` means the arm met the bar in the change generation itself. ``None`` is
    **right-censored**: it never got there within the horizon, so its true time
    is at least ``len(trace) - change_at``, not zero and not unknown-and-dropped.

    ``sustained=False`` is first passage. ``sustained=True`` is the first
    generation from which the trace stays at or above ``threshold`` through the
    last generation, which a noisy arm that spikes over the bar once does not
    satisfy.
    """
    post = list(trace[change_at:])
    if not sustained:
        for offset, value in enumerate(post):
            if value >= threshold:
                return offset
        return None
    settled: "int | None" = None
    for offset in range(len(post) - 1, -1, -1):
        if post[offset] >= threshold:
            settled = offset
        else:
            break
    return settled


def censored_time(value: "int | None", horizon: int) -> int:
    """A censored recovery counts as the full horizon (a lower bound)."""
    return horizon if value is None else value


def niche_coverage(
    records: Sequence[AcceptedRecord],
    change_at: int,
    bins: int,
    good_threshold: float,
    goal: Sequence[float] = sim.CHANGED_GOAL,
) -> Dict[str, int]:
    """Distinct niches an arm's verified work reached, defined once for every arm.

    ``viable_post`` -- niches holding at least one candidate that the panel
    accepted, that is truly viable, and that was proposed after the change.

    ``good_post`` -- the same, restricted to candidates whose utility under the
    **changed** goal is at least ``good_threshold``: viable architectures that
    are also good ones.

    This counts what the arm's search *produced*, not what it retains. The arms
    retain different things (an archive, a population, one plan), so a retained
    count would be a different quantity per arm. See the record's caveats.
    """
    viable_cells, good_cells = niche_cells(records, change_at, bins, good_threshold, goal)
    return {"viable_post": len(viable_cells), "good_post": len(good_cells)}


def niche_cells(
    records: Sequence[AcceptedRecord],
    change_at: int,
    bins: int,
    good_threshold: float,
    goal: Sequence[float] = sim.CHANGED_GOAL,
) -> Tuple[set, set]:
    """The cell sets behind :func:`niche_coverage`, for pooling across seeds."""
    viable_cells = set()
    good_cells = set()
    for generation, candidate, accepted in records:
        if generation < change_at or not accepted or not sim.viable(candidate):
            continue
        cell = sim.niche(candidate, bins)
        viable_cells.add(cell)
        if sim.utility(candidate, goal) >= good_threshold:
            good_cells.add(cell)
    return viable_cells, good_cells


def improvement_events(
    records: Sequence[AcceptedRecord],
    change_at: int,
    materiality: float = PRIMARY_MATERIALITY,
    goal: Sequence[float] = sim.CHANGED_GOAL,
    mode: str = PRIMARY_MODE,
) -> Dict[str, Any]:
    """Verified improvements after the change, counted the same way for every arm.

    The running best starts at the best changed-goal utility among everything the
    arm had verified *before* the change (a verified artifact is still a known
    artifact when the goal moves), then every later accepted candidate whose
    changed-goal utility exceeds it by more than ``materiality`` is one verified
    improvement and raises the running best. A falsely accepted non-viable
    candidate scores ``0.0`` and can never be an improvement.

    ``proposals`` is every proposal made after the change; in this benchmark one
    proposal is one verification attempt, so the two are equal by the matched
    budget contract and only one is reported.
    """
    if mode not in IMPROVEMENT_MODES:
        raise ValueError(f"mode must be one of {IMPROVEMENT_MODES}")
    best = 0.0
    if mode == "carry":
        for generation, candidate, accepted in records:
            if generation < change_at and accepted:
                best = max(best, sim.utility(candidate, goal))
    carried = best
    improvements = 0
    proposals = 0
    for generation, candidate, accepted in records:
        if generation < change_at:
            continue
        proposals += 1
        if not accepted:
            continue
        value = sim.utility(candidate, goal)
        if value > best + materiality:
            improvements += 1
            best = value
    return {
        "improvements": improvements,
        "proposals": proposals,
        "carried_best": round(carried, 6),
        "final_best": round(best, 6),
    }


def seed_metrics(
    payload: Dict[str, Any],
    traces: Dict[str, List[AcceptedRecord]],
    optimum: float,
    change_at: int,
    bins: int,
) -> Dict[str, Dict[str, Any]]:
    """Every derived measurement for one seed, keyed by arm."""
    horizon = len(payload["results"][0]["trace"]) - change_at
    rows: Dict[str, Dict[str, Any]] = {}
    for result in payload["results"]:
        strategy = result["strategy"]
        trace = result["trace"]
        row: Dict[str, Any] = {
            "post_change_utility_auc": result["post_change_utility_auc"],
            "horizon": horizon,
            "recovery": {},
            "coverage": {},
        }
        for fraction in SENSITIVITY_FRACTIONS:
            tau = threshold_for(fraction, optimum)
            row["recovery"][_key(fraction)] = {
                "first_passage": recovery_time(trace, change_at, tau),
                "sustained": recovery_time(trace, change_at, tau, sustained=True),
            }
            row["coverage"][_key(fraction)] = niche_coverage(
                traces[strategy], change_at, bins, tau
            )
        row["improvement"] = {
            improvement_key(mode, m): improvement_events(
                traces[strategy], change_at, m, mode=mode
            )
            for mode in IMPROVEMENT_MODES
            for m in SENSITIVITY_MATERIALITY
        }
        rows[strategy] = row
    return rows


def _key(value: float) -> str:
    return f"{value:g}"


# --------------------------------------------------------------------------
# Statistics -- exact where possible, seeded bootstrap otherwise
# --------------------------------------------------------------------------
def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(successes: int, trials: int, confidence: float = CONFIDENCE) -> Dict[str, float]:
    """Exact binomial interval, by bisection on the binomial CDF."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    alpha = 1.0 - confidence

    def solve(target: float, lower_tail_of: int) -> float:
        low, high = 0.0, 1.0
        for _ in range(80):
            mid = (low + high) / 2.0
            if _binom_cdf(lower_tail_of, trials, mid) > target:
                low = mid
            else:
                high = mid
        return (low + high) / 2.0

    lower = 0.0 if successes == 0 else solve(1.0 - alpha / 2.0, successes - 1)
    upper = 1.0 if successes == trials else solve(alpha / 2.0, successes)
    return {"rate": round(successes / trials, 6), "ci95_low": round(lower, 6), "ci95_high": round(upper, 6)}


def sign_test_p(wins: int, losses: int) -> float:
    """Two-sided exact sign test; ties are excluded by the caller."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = _binom_cdf(min(wins, losses), n, 0.5)
    # Six significant figures, not six decimals: a seed-level p of 3e-30 must not
    # be written as 0.0, which reads as a bug rather than as a very small number.
    return float(f"{min(1.0, 2.0 * tail):.6g}")


def mcnemar_exact(only_first: int, only_second: int) -> float:
    """McNemar's exact test is the sign test on the discordant pairs."""
    return sign_test_p(only_first, only_second)


def bootstrap_mean_ci(
    values: Sequence[float], label: str, resamples: int = DEFAULT_RESAMPLES
) -> Dict[str, float]:
    """Percentile bootstrap of the mean over seeds, deterministic per ``label``."""
    rng = random.Random(f"{EXPERIMENT_ID}:{label}")
    n = len(values)
    means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)
    )
    low = means[int((1.0 - CONFIDENCE) / 2.0 * resamples)]
    high = means[min(resamples - 1, int((1.0 + CONFIDENCE) / 2.0 * resamples))]
    return {
        "mean": round(mean(values), 6),
        "ci95_low": round(low, 6),
        "ci95_high": round(high, 6),
    }


def bootstrap_ratio_ci(
    numerators: Sequence[float],
    denominators: Sequence[float],
    label: str,
    resamples: int = DEFAULT_RESAMPLES,
) -> Dict[str, Any]:
    """Pooled ratio of sums (proposals per improvement), bootstrapped over seeds.

    A pooled ratio is used because a single seed can have zero improvements, which
    makes its own ratio undefined. Resamples with zero pooled improvements are
    counted and dropped, and the count is reported.
    """
    rng = random.Random(f"{EXPERIMENT_ID}:{label}")
    n = len(numerators)
    total_den = sum(denominators)
    point = None if total_den == 0 else sum(numerators) / total_den
    ratios: List[float] = []
    undefined = 0
    for _ in range(resamples):
        picks = [rng.randrange(n) for _ in range(n)]
        den = sum(denominators[i] for i in picks)
        if den == 0:
            undefined += 1
            continue
        ratios.append(sum(numerators[i] for i in picks) / den)
    ratios.sort()
    if point is None or not ratios:
        return {"ratio": None, "ci95_low": None, "ci95_high": None, "undefined_resamples": undefined}
    low = ratios[int((1.0 - CONFIDENCE) / 2.0 * len(ratios))]
    high = ratios[min(len(ratios) - 1, int((1.0 + CONFIDENCE) / 2.0 * len(ratios)))]
    return {
        "ratio": round(point, 6),
        "ci95_low": round(low, 6),
        "ci95_high": round(high, 6),
        "undefined_resamples": undefined,
    }


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
def _recovery_summary(
    values: Sequence["int | None"], horizon: int, label: str, resamples: int
) -> Dict[str, Any]:
    n = len(values)
    reached = sum(1 for v in values if v is not None)
    times = [float(censored_time(v, horizon)) for v in values]
    ordered = sorted(times)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    return {
        "reached": reached,
        "censored": n - reached,
        "reached_rate": clopper_pearson(reached, n),
        # Mean of min(T, horizon): the restricted mean recovery time. Censored
        # seeds contribute the horizon, a lower bound, so this understates the
        # true mean for any arm with censored seeds.
        "restricted_mean_generations": bootstrap_mean_ci(times, label, resamples),
        "median_generations": median if median < horizon else f">={horizon}",
    }


def aggregate(
    per_seed: List[Dict[str, Dict[str, Any]]],
    pooled_cells: Dict[str, Dict[str, set]],
    resamples: int = DEFAULT_RESAMPLES,
) -> Dict[str, Any]:
    horizon = per_seed[0][STRATEGIES[0]]["horizon"]
    primary = _key(PRIMARY_FRACTION)
    primary_improvement = improvement_key(PRIMARY_MODE, PRIMARY_MATERIALITY)
    out: Dict[str, Any] = {}
    for strategy in STRATEGIES:
        rows = [seed[strategy] for seed in per_seed]
        first = [r["recovery"][primary]["first_passage"] for r in rows]
        sustained = [r["recovery"][primary]["sustained"] for r in rows]
        good = [float(r["coverage"][primary]["good_post"]) for r in rows]
        viable = [float(r["coverage"][primary]["viable_post"]) for r in rows]
        improvement = [r["improvement"][primary_improvement] for r in rows]
        proposals = [float(i["proposals"]) for i in improvement]
        counts = [float(i["improvements"]) for i in improvement]
        out[strategy] = {
            "recovery_first_passage": _recovery_summary(
                first, horizon, f"{strategy}:first", resamples
            ),
            "recovery_sustained": _recovery_summary(
                sustained, horizon, f"{strategy}:sustained", resamples
            ),
            "niches_good_post_change": bootstrap_mean_ci(good, f"{strategy}:good", resamples),
            "niches_viable_post_change": bootstrap_mean_ci(
                viable, f"{strategy}:viable", resamples
            ),
            "niches_pooled_across_seeds": {
                "viable": len(pooled_cells[strategy]["viable"]),
                "good": len(pooled_cells[strategy]["good"]),
            },
            "improvements_per_seed": bootstrap_mean_ci(counts, f"{strategy}:impr", resamples),
            "seeds_with_zero_improvements": sum(1 for c in counts if c == 0),
            "proposals_per_verified_improvement": bootstrap_ratio_ci(
                proposals, counts, f"{strategy}:ratio", resamples
            ),
            "proposals_per_material_improvement": bootstrap_ratio_ci(
                proposals,
                [
                    float(
                        r["improvement"][improvement_key(PRIMARY_MODE, MATERIAL_THRESHOLD)][
                            "improvements"
                        ]
                    )
                    for r in rows
                ],
                f"{strategy}:ratio-material",
                resamples,
            ),
            "post_change_utility_auc": bootstrap_mean_ci(
                [float(r["post_change_utility_auc"]) for r in rows],
                f"{strategy}:auc",
                resamples,
            ),
        }
    return out


def _paired(first: Sequence[float], second: Sequence[float]) -> Tuple[int, int, int]:
    wins = sum(1 for a, b in zip(first, second) if a > b)
    losses = sum(1 for a, b in zip(first, second) if a < b)
    return wins, losses, len(first) - wins - losses


def paired_against_archive(
    per_seed: List[Dict[str, Dict[str, Any]]],
    resamples: int = DEFAULT_RESAMPLES,
) -> Dict[str, Any]:
    """Seed-level comparisons of the archive with every other arm.

    Direction convention is fixed: a "win" is the archive being *better*. Faster
    recovery is better, so for time the archive wins when its time is smaller.
    Both-censored pairs are ties and are excluded, never counted as wins.
    """
    horizon = per_seed[0][STRATEGIES[0]]["horizon"]
    primary = _key(PRIMARY_FRACTION)
    primary_improvement = improvement_key(PRIMARY_MODE, PRIMARY_MATERIALITY)
    comparisons = [s for s in STRATEGIES if s != ARCHIVE_ARM]
    report: Dict[str, Any] = {}
    for other in comparisons:
        entry: Dict[str, Any] = {}
        for reading in ("first_passage", "sustained"):
            qd = [seed[ARCHIVE_ARM]["recovery"][primary][reading] for seed in per_seed]
            ot = [seed[other]["recovery"][primary][reading] for seed in per_seed]
            only_qd = sum(1 for a, b in zip(qd, ot) if a is not None and b is None)
            only_other = sum(1 for a, b in zip(qd, ot) if a is None and b is not None)
            both = sum(1 for a, b in zip(qd, ot) if a is not None and b is not None)
            neither = len(qd) - only_qd - only_other - both
            # Time sign test: censored counts as the horizon, so a reached seed
            # beats a censored one; both-censored is a tie and drops out.
            wins, losses, ties = _paired(
                [censored_time(b, horizon) for b in ot],
                [censored_time(a, horizon) for a in qd],
            )
            # `wins` counts seeds where the other arm is slower, i.e. the archive
            # is faster; `losses` where the archive is slower.
            entry[f"recovery_{reading}"] = {
                "mcnemar_reached": {
                    "archive_only": only_qd,
                    "other_only": only_other,
                    "both": both,
                    "neither": neither,
                    "p_exact_two_sided": mcnemar_exact(only_qd, only_other),
                },
                "time_sign_test": {
                    "archive_faster": wins,
                    "other_faster": losses,
                    "ties": ties,
                    "p_exact_two_sided": sign_test_p(wins, losses),
                },
            }
        for name, getter in (
            ("niches_good_post_change", lambda r: float(r["coverage"][primary]["good_post"])),
            ("niches_viable_post_change", lambda r: float(r["coverage"][primary]["viable_post"])),
            (
                "improvements",
                lambda r: float(r["improvement"][primary_improvement]["improvements"]),
            ),
            (
                "material_improvements",
                lambda r: float(
                    r["improvement"][improvement_key(PRIMARY_MODE, MATERIAL_THRESHOLD)][
                        "improvements"
                    ]
                ),
            ),
            (
                "improvements_fresh",
                lambda r: float(
                    r["improvement"][improvement_key("fresh", PRIMARY_MATERIALITY)]["improvements"]
                ),
            ),
            (
                "material_improvements_fresh",
                lambda r: float(
                    r["improvement"][improvement_key("fresh", MATERIAL_THRESHOLD)]["improvements"]
                ),
            ),
        ):
            qd = [getter(seed[ARCHIVE_ARM]) for seed in per_seed]
            ot = [getter(seed[other]) for seed in per_seed]
            wins, losses, ties = _paired(qd, ot)
            diffs = [a - b for a, b in zip(qd, ot)]
            entry[name] = {
                "archive_higher": wins,
                "other_higher": losses,
                "ties": ties,
                "paired_mean_difference": bootstrap_mean_ci(
                    diffs, f"paired:{other}:{name}", resamples
                ),
                "p_exact_two_sided": sign_test_p(wins, losses),
            }
        report[other] = entry
    return report


def sensitivity(per_seed: List[Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """Reached-rate, mean niches and improvements across the declared grids."""
    out: Dict[str, Any] = {"recovery_and_coverage_by_threshold_fraction": {}, "improvement_by_definition": {}}
    horizon = per_seed[0][STRATEGIES[0]]["horizon"]
    n = len(per_seed)
    for fraction in SENSITIVITY_FRACTIONS:
        key = _key(fraction)
        block: Dict[str, Any] = {}
        for strategy in STRATEGIES:
            rows = [seed[strategy] for seed in per_seed]
            first = [r["recovery"][key]["first_passage"] for r in rows]
            sustained = [r["recovery"][key]["sustained"] for r in rows]
            block[strategy] = {
                "first_passage_reached": sum(1 for v in first if v is not None),
                "sustained_reached": sum(1 for v in sustained if v is not None),
                "trials": n,
                "mean_good_niches": round(mean(r["coverage"][key]["good_post"] for r in rows), 6),
            }
        out["recovery_and_coverage_by_threshold_fraction"][key] = block
    for mode in IMPROVEMENT_MODES:
        for materiality in SENSITIVITY_MATERIALITY:
            key = improvement_key(mode, materiality)
            counts = {
                strategy: [float(seed[strategy]["improvement"][key]["improvements"]) for seed in per_seed]
                for strategy in STRATEGIES
            }
            proposals = [
                float(seed[STRATEGIES[0]]["improvement"][key]["proposals"]) for seed in per_seed
            ]
            out["improvement_by_definition"][key] = {
                strategy: {
                    "mean_improvements": round(mean(values), 6),
                    "seeds_with_zero": sum(1 for v in values if v == 0),
                    "pooled_proposals_per_improvement": (
                        None if sum(values) == 0 else round(sum(proposals) / sum(values), 6)
                    ),
                }
                for strategy, values in counts.items()
            }
    out["horizon"] = horizon
    return out


# --------------------------------------------------------------------------
# Replay check against the committed E024 artifact
# --------------------------------------------------------------------------
def canonical_digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def e024_aggregate_from_payloads(payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Rebuild E024's ``aggregate`` block from replayed payloads.

    Uses E024's own ``_stats`` and metric list, so equality with the committed
    artifact means the replay reproduced the published numbers, not a lookalike.
    """
    rows = {s: {m: [] for m in mbe.SUMMARY_METRICS} for s in STRATEGIES}
    for payload in payloads:
        for row in payload["results"]:
            for metric in mbe.SUMMARY_METRICS:
                rows[row["strategy"]][metric].append(float(row[metric]))
    return {
        strategy: {metric: mbe._stats(values) for metric, values in metrics.items()}
        for strategy, metrics in rows.items()
    }


def compare_to_committed_e024(
    payloads: Sequence[Dict[str, Any]], artifact: Path
) -> Dict[str, Any]:
    committed = json.loads(artifact.read_text(encoding="utf-8"))
    replayed = e024_aggregate_from_payloads(payloads)
    return {
        "artifact": "experiments/results/" + artifact.name,
        "committed_aggregate_sha256": canonical_digest(committed["aggregate"]),
        "replayed_aggregate_sha256": canonical_digest(replayed),
        "matches": committed["aggregate"] == replayed,
    }


# --------------------------------------------------------------------------
# Sweep and report
# --------------------------------------------------------------------------
def measure(
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = DEFAULT_SEED_START,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    resamples: int = DEFAULT_RESAMPLES,
    committed_e024: "Path | None" = None,
    verification: "sim.VerificationConfig | None" = None,
    reference: "Dict[str, Any] | None" = None,
) -> Dict[str, Any]:
    if seeds < 2:
        raise ValueError("seeds must be >= 2")
    optimum = reference if reference is not None else reference_optimum()
    optimum_value = optimum["optimum_utility"]
    per_seed: List[Dict[str, Dict[str, Any]]] = []
    payloads: List[Dict[str, Any]] = []
    pooled: Dict[str, Dict[str, set]] = {s: {"viable": set(), "good": set()} for s in STRATEGIES}
    tau = threshold_for(PRIMARY_FRACTION, optimum_value)
    for seed in range(seed_start, seed_start + seeds):
        payload, traces = replay_seed(seed, agents, generations, change_at, bins, verification)
        payloads.append(payload)
        per_seed.append(seed_metrics(payload, traces, optimum_value, change_at, bins))
        for strategy in STRATEGIES:
            viable_cells, good_cells = niche_cells(traces[strategy], change_at, bins, tau)
            pooled[strategy]["viable"] |= viable_cells
            pooled[strategy]["good"] |= good_cells

    primary_key = _key(PRIMARY_FRACTION)
    primary_improvement_key = improvement_key(PRIMARY_MODE, PRIMARY_MATERIALITY)
    report: Dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "evidence_level": EVIDENCE_LEVEL,
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "post_change_horizon": generations - change_at,
            "niche_cells": bins * bins,
            "verification": (verification or sim.VerificationConfig()).as_dict(),
            "bootstrap_resamples": resamples,
            "source": "replay of matched_budget_emergence.run_seed with identical seeds",
        },
        "threshold_rule": {
            "rule": "tau = fraction * optimum, where optimum is the best utility any "
            "viable candidate can reach under the changed goal",
            "primary_fraction": PRIMARY_FRACTION,
            "primary_tau": round(tau, 6),
            "sensitivity_fractions": list(SENSITIVITY_FRACTIONS),
            "optimum": optimum,
            "why_absolute": "E024's recovery_generations compares an arm with 95% of its "
            "own final value, so an arm that stays on a low plateau recovers at "
            "generation 0. A threshold on the utility scale itself, derived from the "
            "landscape and not from any arm, cannot be passed by standing still.",
            "censoring": "a seed that never reaches tau within the horizon is right-censored: "
            "its time is at least the horizon, it counts as not reached, and it contributes "
            "the horizon (a lower bound) to restricted means",
            "readings": {
                "first_passage": "first post-change generation with delivered utility >= tau",
                "sustained": "first generation from which delivered utility stays >= tau "
                "through the last generation",
            },
            "fixed_before": "the primary fraction was fixed before any aggregate was computed; "
            "seed 0's traces were viewed once while checking the replay",
        },
        "coverage_definition": {
            "niche": "sim.niche(candidate, bins): adaptability x efficiency cells",
            "viable_post": "cells holding a panel-accepted, truly viable candidate proposed "
            "after the change",
            "good_post": "viable_post restricted to candidates with changed-goal utility >= tau",
            "scope": "what the arm's search produced after the change, identically defined "
            "for all five arms; not what each arm retains",
        },
        "improvement_definition": {
            "improvement": "an accepted candidate whose changed-goal utility exceeds the "
            "running best by more than the materiality; the running best starts at the best "
            "changed-goal utility among everything the arm had verified before the change",
            "primary_materiality": PRIMARY_MATERIALITY,
            "sensitivity_materiality": list(SENSITIVITY_MATERIALITY),
            "primary_mode": PRIMARY_MODE,
            "modes": {
                "carry": "running best starts at the best changed-goal utility among everything "
                "the arm verified before the change",
                "fresh": "running best starts at zero when the goal changes, so an arm is "
                "credited for re-finding what it already held",
            },
            "cost": "proposals per improvement; one proposal is one verification attempt "
            "in this benchmark, so the two are equal by contract",
            "pooled_ratio": "ratio of summed proposals to summed improvements, because a "
            "single seed can have zero improvements",
        },
        "aggregate": aggregate(per_seed, pooled, resamples),
        "paired_against_archive": paired_against_archive(per_seed, resamples),
        "sensitivity": sensitivity(per_seed),
        "multiple_comparisons": {
            "paired_tests_reported": PAIRED_TESTS,
            "bonferroni_alpha_0.05": round(0.05 / PAIRED_TESTS, 6),
            "note": "p-values are exact and uncorrected; read them against this alpha, "
            "and read the threshold and materiality grids as part of the same family",
        },
        "not_measured": list(NOT_MEASURED),
        "per_seed_primary": {
            strategy: {
                "recovery_first_passage": [
                    s[strategy]["recovery"][primary_key]["first_passage"] for s in per_seed
                ],
                "recovery_sustained": [
                    s[strategy]["recovery"][primary_key]["sustained"] for s in per_seed
                ],
                "good_niches_post_change": [
                    s[strategy]["coverage"][primary_key]["good_post"] for s in per_seed
                ],
                "viable_niches_post_change": [
                    s[strategy]["coverage"][primary_key]["viable_post"] for s in per_seed
                ],
                "improvements": [
                    s[strategy]["improvement"][primary_improvement_key]["improvements"]
                    for s in per_seed
                ],
                "post_change_utility_auc": [
                    s[strategy]["post_change_utility_auc"] for s in per_seed
                ],
            }
            for strategy in STRATEGIES
        },
        "limitations": [
            "All candidates, goals, verdicts and costs are synthetic; this is mechanism evidence, "
            "not evidence about real agents or people.",
            "The threshold is a fraction of a reference optimum of this landscape; the fraction is a "
            "choice, which is why a five-point grid is reported next to it.",
            "Coverage counts niches the search produced, not niches an arm retains. A random-search "
            "arm scatters proposals and is advantaged on produced coverage by construction.",
            "An improvement count rewards incremental climbing (many small records) unless "
            "materiality is raised, and depends on whether earlier verified work carries over, so "
            "it is reported at two materialities and under both carry-over modes.",
            "Proposal counts are a compute proxy only; the E024 matched budget makes them equal "
            "per arm, so only the improvement count differs.",
            "The E024 perfect panel is used, so no false accept can inflate an arm's coverage or "
            "improvements.",
        ],
    }
    if committed_e024 is not None:
        report["replay_check"] = compare_to_committed_e024(payloads, committed_e024)
    return report


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--change-at", type=int, default=DEFAULT_CHANGE_AT)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument(
        "--check-e024",
        default=None,
        metavar="PATH",
        help="committed E024 artifact whose aggregate the replay must reproduce",
    )
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.seeds < 2:
        parser.error("--seeds must be >= 2")
    if args.resamples < 10:
        parser.error("--resamples must be >= 10")
    if not 1 <= args.change_at < args.generations:
        parser.error("--change-at must satisfy 1 <= change-at < generations")
    return args


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    result = measure(
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        resamples=args.resamples,
        committed_e024=Path(args.check_e024) if args.check_e024 else None,
    )
    text = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
