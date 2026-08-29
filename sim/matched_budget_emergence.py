#!/usr/bin/env python3
"""Matched-evaluation-budget emergence benchmark for E024.

This module reuses the E011 landscape and candidate/verifier mechanics while
giving every search strategy exactly the same number of proposals and
verification attempts.  It is a synthetic mechanism test, not evidence of
real-world system emergence.

Issue #22 names five comparison arms.  Alongside random, fixed-scalar, and
Quality-Diversity search this module implements the two the issue requires and
E024 previously recorded as absent:

- ``planner``  -- a centralized planner committed to one fixed objective,
  refined by directed local search rather than by evolution;
- ``majority`` -- a majority-vote swarm whose consensus advances only when a
  strict majority of agents prefer a candidate under their own goal hypothesis.

New strategies are appended to :data:`STRATEGIES` rather than inserted, because
``run_seed`` derives each arm's seed from its index.  Appending keeps the
previously published random/scalar/qd results bit-for-bit reproducible.

The verifier panel is perfect by default, which is how the committed 100-seed
reference sweep was produced.  ``--imperfect-panel`` swaps in the panel E017
measured -- 25 correlated partial test oracles with an irreducible shared blind
spot -- so the benchmark can ask whether the Quality-Diversity result survives
verifiers that are wrong *together*.  See :data:`E017_MEASURED_PANEL`.

E026 armed that panel and found that nothing moved, and diagnosed why: every arm
here ranks candidates with ``utility()`` and ``robust_quality()``, both of which
consult ``viable()`` directly.  A falsely accepted artifact therefore scores
0.0, never displaces anything, and is discarded by the very predicate the
verifier panel was meant to enforce -- so verifier error cannot reach the
outcome metric at all.  ``--defect-channel`` closes that gap: selection and
delivery then rank by *apparent* quality, which is what a system can observe
once its panel has accepted an artifact, while the trace still scores the
delivered artifact by ground truth.  See :class:`DefectChannel`.  It is off by
default, so the committed reference sweep still reproduces.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Callable, Dict, List, Sequence, Tuple

HERE = Path(__file__).resolve().parent
SIM_PATH = HERE / "emergence_sim.py"

spec = importlib.util.spec_from_file_location("emergence_sim", SIM_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)

STRATEGIES = ("random", "scalar", "qd", "planner", "majority")
EXPERIMENT_ID = "E024"

# The imperfect panel is not invented: every number below was measured in this
# repository on 25 partial test oracles over 72 candidates whose ground truth is
# decided by executing hidden tests.
#
#   experiments/E017-item-difficulty-and-quorum.md
#     25 verifiers, mean per-verifier accuracy 0.7956 (marginal error 0.2044),
#     mean pairwise error correlation rho = +0.5873, and the finding that the
#     shared-shock shape is wrong: it under-predicts real panel error by 1.71x
#     because real panels fail *partially*. A beta-binomial over per-item
#     difficulty reproduces that at the same parameter count.
#   experiments/E020-quorum-frontier-under-measured-shape.md
#     the same votes refit with a lambda-atom: 4 of 72 units are missed by every
#     verifier, lambda = 0.0556, and the residual reducible tasks fit
#     mu = 0.1576, icc = 0.4513.
#
# CORRELATION PROVENANCE, stated precisely because it is easy to double-count.
# E017's headline rho = +0.5873 is the *marginal* pairwise correlation of the
# whole panel, blind-spot units included -- those units contribute perfectly
# correlated errors. Once the blind spot is represented explicitly as its own
# atom, the correlation left in the reducible units is E020's icc = 0.4513.
# Feeding 0.5873 as the base correlation *and* arming the atom would count the
# same shared failures twice, so the panel below uses the decomposed pair
# (0.4513, 0.0556) whose implied marginal correlation is E017's measurement.
# `--verifier-correlation` overrides it for sensitivity work.
E017_MEASURED_PANEL = {
    "verifiers": 25,
    "accuracy": 0.7956,
    "correlation": 0.4513,
    "blind_spot": 0.0556,
    "dependence": "item-difficulty",
    "quorum": 0.5,
}
E017_MEASURED_MARGINAL_CORRELATION = 0.5873
PANEL_PROVENANCE = {
    "panel": "E017 partial-test-oracle panel, refit with a blind-spot atom in E020",
    "source_experiments": [
        "experiments/E017-item-difficulty-and-quorum.md",
        "experiments/E020-quorum-frontier-under-measured-shape.md",
    ],
    "measured_verifiers": 25,
    "measured_candidates": 72,
    "measured_marginal_accuracy": 0.7956,
    "measured_marginal_pairwise_correlation": E017_MEASURED_MARGINAL_CORRELATION,
    "measured_blind_spot_lambda": 0.0556,
    "measured_blind_spot_units": "4 of 72",
    "reducible_fit_mean_error": 0.1576,
    "reducible_fit_icc": 0.4513,
    "dependence_shape": "beta-binomial over per-item difficulty plus a blind-spot atom",
    "shape_rejected": "shared-shock; E017 measured it 1.71x too low on panel error",
    "evidence_level": "measured-on-real-verifiers parameters, applied to a synthetic landscape",
}
# The defect-propagation channel closes the gap E026 measured. Its provenance is
# a *diagnosis*, not a measurement: no defect cost was observed anywhere, so the
# knob is swept across its whole range rather than fitted, and the range
# includes the setting that reproduces E026's null exactly.
DEFECT_MECHANISM = (
    "selection, retention and delivery rank candidates by apparent quality -- the "
    "quality a system can observe once its verifier panel has accepted an artifact -- "
    "while the trace scores the delivered artifact by ground truth. A falsely "
    "accepted non-viable artifact is credited `cost` times its apparent quality, so "
    "it can displace an incumbent, occupy an archive niche, be drawn as a parent, and "
    "be shipped; when it is shipped it delivers 0.0."
)
DEFECT_PROVENANCE = {
    "channel": "E027 latent-defect propagation channel",
    "motivating_result": "experiments/E026-imperfect-verifier-panel.md",
    "gap_closed": (
        "E024 and E026 rank candidates with utility() and robust_quality(), both of "
        "which consult viable() directly. A falsely accepted artifact therefore scores "
        "0.0 and is silently discarded by the same predicate the verifier panel was "
        "meant to enforce, so verifier error cannot reach the outcome metric."
    ),
    "mechanism": DEFECT_MECHANISM,
    "knob": "defect cost in [0, 1]",
    "knob_meaning": (
        "the fraction of a latent defect's apparent quality that the system's own "
        "selection machinery still credits, i.e. how far the defect stays latent past "
        "the acceptance gate"
    ),
    "knob_zero_means": (
        "exactly the E024/E026 behaviour: the search operator holds a free viability "
        "oracle and discards a falsely accepted artifact for nothing"
    ),
    "knob_one_means": (
        "no free oracle anywhere: the system trusts its verifier panel completely, "
        "which is the only assumption-free setting"
    ),
    "default_cost": 1.0,
    "why_the_default_is_the_extreme": (
        "cost 1.0 adds no parameter. Every value below it hands the search operator "
        "ground-truth viability information that no real system has, so the knob is a "
        "dial back toward E024's optimistic assumption rather than a dial tuned to "
        "manufacture an effect."
    ),
    "evidence_level": "synthetic mechanism; no defect cost is measured anywhere",
}

# Aggregated only when the channel is armed, so a disarmed report keeps exactly
# the schema the committed E024 and E026 artifacts were published with.
DEFECT_METRICS = (
    "delivered_defect_rate",
    "retained_defect_rate",
)


@dataclass(frozen=True)
class DefectChannel:
    """How much of an accepted defect the system keeps believing in.

    ``cost`` is the single knob, in ``[0.0, 1.0]``:

    ``0.0``
        The E024/E026 behaviour. A non-viable candidate is worth 0.0 to every
        selection rule, so it is thrown away the instant it is accepted --
        which is a free viability oracle sitting behind the verifier panel.
        The channel is armed but inert, and the outcome metrics are identical
        to a run with no channel at all. A regression test pins that identity.
    ``1.0``
        No free oracle. The system ranks and ships artifacts on what it can
        observe, so a falsely accepted defect competes on its apparent merits,
        can evict a real solution, can be drawn as a parent, and delivers 0.0
        whenever it is the artifact that ships.

    The default is 1.0 because it is the end of the range that adds no
    assumption; see :data:`DEFECT_PROVENANCE`.
    """

    cost: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.cost <= 1.0:
            raise ValueError("defect cost must be in [0.0, 1.0]")

    def as_dict(self) -> Dict[str, object]:
        return {"cost": self.cost, "mechanism": DEFECT_MECHANISM}


@dataclass
class DefectStats:
    """What the defect channel actually did, per arm."""

    generations: int = 0
    delivered_defects: int = 0
    retained_artifacts: int = 0
    retained_defects: int = 0

    def record_delivery(self, chosen: "sim.Candidate | None") -> None:
        self.generations += 1
        if chosen is not None and not sim.viable(chosen):
            self.delivered_defects += 1

    def record_retention(self, retained: Sequence["sim.Candidate"]) -> None:
        self.retained_artifacts = len(retained)
        self.retained_defects = sum(1 for c in retained if not sim.viable(c))

    def as_metrics(self) -> Dict[str, object]:
        delivered_rate = self.delivered_defects / self.generations if self.generations else 0.0
        retained_rate = (
            self.retained_defects / self.retained_artifacts if self.retained_artifacts else 0.0
        )
        return {
            "delivered_defect_generations": self.delivered_defects,
            "delivered_defect_rate": round(delivered_rate, 6),
            "retained_artifacts": self.retained_artifacts,
            "retained_defects": self.retained_defects,
            "retained_defect_rate": round(retained_rate, 6),
        }


def _apparent_utility(
    candidate: "sim.Candidate", weights: Sequence[float], cost: float
) -> float:
    """Utility as the system sees it after the panel has accepted the artifact.

    At ``cost`` 0.0 this is ``sim.utility`` exactly -- same expression, and the
    non-viable branch multiplies by zero -- which is what keeps an armed-but-
    inert channel numerically identical to no channel.
    """
    value = sim.unchecked_utility(candidate, weights)
    return value if sim.viable(candidate) else cost * value


def _apparent_robust_quality(candidate: "sim.Candidate", cost: float) -> float:
    """``sim.robust_quality`` as the system sees it. Identical at ``cost`` 0.0."""
    value = sim.unchecked_robust_quality(candidate)
    return value if sim.viable(candidate) else cost * value


def _deliver(
    population: Sequence["sim.Candidate"], goal: Sequence[float], cost: float
) -> Tuple[float, "sim.Candidate | None"]:
    """Ship the artifact that looks best, then score it honestly.

    Separating the choice from the score is the whole channel: the choice is
    made on apparent quality, which the panel's verdict is part of, and the
    score is ground truth. At ``cost`` 0.0 the chosen artifact is always the
    true maximiser, so this returns exactly what ``sim._best_actual`` returned.
    """
    chosen: "sim.Candidate | None" = None
    best: float | None = None
    for candidate in population:
        apparent = _apparent_utility(candidate, goal, cost)
        if best is None or apparent > best:
            best, chosen = apparent, candidate
    if chosen is None:
        return 0.0, None
    return sim.utility(chosen, goal), chosen


SUMMARY_METRICS = (
    "pre_change_best",
    "post_change_immediate",
    "post_change_mean",
    "post_change_utility_auc",
    "post_change_regret_auc",
    "final_best",
    "verification_accepts",
    "false_accept_rate",
    "false_reject_rate",
    "panel_disagreement_rate",
    "archive_size",
)


# A seed is called catastrophic for an arm when its post-change utility AUC
# falls below this fraction of the achievable horizon.  0.64 of a 25-generation
# horizon is AUC 16, the exact threshold the published E024 record used to count
# the majority-vote swarm's stale-consensus failures, so the two are comparable.
CATASTROPHE_FRACTION = 0.64


# Each strategy gets its own proposal stream and its own verifier stream, so an
# arm cannot consume another arm's randomness. Named here rather than inlined so
# a replay can derive the identical streams instead of copying magic numbers.
STRATEGY_SEED_STRIDE = 100003
VERIFIER_STREAM_MASK = 0x5EED5EED


def measured_panel(**overrides: object) -> "sim.VerificationConfig":
    """The E017/E020 panel: 25 correlated oracles with a shared blind spot.

    Every parameter is measured; see :data:`E017_MEASURED_PANEL` for the
    provenance and for why the base correlation is E020's decomposed 0.4513
    rather than E017's marginal 0.5873.
    """
    settings = dict(E017_MEASURED_PANEL)
    settings.update({key: value for key, value in overrides.items() if value is not None})
    return sim.VerificationConfig(**settings)


def panel_is_perfect(verification: "sim.VerificationConfig") -> bool:
    """True when the panel cannot err, so the report keeps its original schema.

    An imperfect-panel report is a strict superset of the perfect-panel one.
    Keeping the perfect case byte-identical is what lets the committed 100-seed
    reference sweep still reproduce after this module learned to be wrong.
    """
    return verification.accuracy >= 1.0 and verification.blind_spot <= 0.0


def _summary(
    strategy: str,
    trace: List[float],
    stats: "sim.VerificationStats",
    archive_size: int,
    change_at: int,
    evaluation_budget: int,
    defect: "DefectChannel | None" = None,
    defects: "DefectStats | None" = None,
) -> Dict[str, object]:
    result = sim._summary(strategy, trace, stats, archive_size, change_at)
    post_trace = trace[change_at:]
    result.update(
        {
            "proposal_attempts": stats.attempts,
            "matched_evaluation_budget": evaluation_budget,
            "post_change_utility_auc": round(sum(post_trace), 6),
            "post_change_regret_auc": round(sum(1.0 - value for value in post_trace), 6),
        }
    )
    # Emitted only when the channel is armed, so a disarmed row stays exactly
    # the row the committed E024 and E026 artifacts were published with.
    if defect is not None and defects is not None:
        result.update(defects.as_metrics())
    return result


def _defect_cost(defect: "DefectChannel | None") -> float:
    return defect.cost if defect is not None else 0.0


def _random_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    del bins
    cost = _defect_cost(defect)
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = DefectStats()
    accepted: List["sim.Candidate"] = []
    for generation in range(generations):
        proposals = [sim.Candidate.random(rng) for _ in range(agents)]
        accepted = [
            candidate
            for candidate in proposals
            if sim.verify_candidate(candidate, verifier_rng, verification, stats)
        ]
        value, chosen = _deliver(accepted, sim._goal_at(generation, change_at), cost)
        defects.record_delivery(chosen)
        trace.append(value)
    defects.record_retention(accepted)
    return _summary(
        "random", trace, stats, 0, change_at, agents * generations, defect, defects
    )


def _scalar_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    del bins
    cost = _defect_cost(defect)
    population: List["sim.Candidate"] = []
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = DefectStats()
    elite_count = max(2, min(32, agents // 4))

    for generation in range(generations):
        ranked = sorted(
            population,
            key=lambda candidate: _apparent_utility(candidate, sim.INITIAL_GOAL, cost),
            reverse=True,
        )
        elites = ranked[:elite_count]
        proposals = [
            rng.choice(elites).mutate(rng) if elites else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        accepted = [
            candidate
            for candidate in proposals
            if sim.verify_candidate(candidate, verifier_rng, verification, stats)
        ]
        population = elites + accepted
        value, chosen = _deliver(population, sim._goal_at(generation, change_at), cost)
        defects.record_delivery(chosen)
        trace.append(value)

    defects.record_retention(population)
    return _summary(
        "scalar", trace, stats, 0, change_at, agents * generations, defect, defects
    )


def _qd_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    cost = _defect_cost(defect)
    archive: Dict[Tuple[int, int], "sim.Candidate"] = {}
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = DefectStats()

    for generation in range(generations):
        parents = list(archive.values())
        proposals = [
            rng.choice(parents).mutate(rng)
            if parents and rng.random() < 0.85
            else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            key = sim.niche(candidate, bins)
            incumbent = archive.get(key)
            if incumbent is None or _apparent_robust_quality(
                candidate, cost
            ) > _apparent_robust_quality(incumbent, cost):
                archive[key] = candidate
        value, chosen = _deliver(
            list(archive.values()), sim._goal_at(generation, change_at), cost
        )
        defects.record_delivery(chosen)
        trace.append(value)

    defects.record_retention(list(archive.values()))
    return _summary(
        "qd", trace, stats, len(archive), change_at, agents * generations, defect, defects
    )


def _planner_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    """Centralized planner with one fixed objective (issue #22 baseline 1).

    One central plan is broadcast each generation and refined by directed local
    search.  The planner is deliberately non-evolutionary: it keeps a single
    incumbent rather than a population, retains no diversity, and scores every
    candidate against ``INITIAL_GOAL`` only.  Its objective never updates when
    the true goal changes, which is the property the baseline exists to expose.
    """
    del bins
    cost = _defect_cost(defect)
    incumbent: "sim.Candidate | None" = None
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = DefectStats()
    fixed_goal = sim.INITIAL_GOAL

    for generation in range(generations):
        # The whole swarm works from the plan held at the start of the
        # generation, so direction is centralized rather than emergent.
        proposals = [
            incumbent.mutate(rng) if incumbent is not None else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            if incumbent is None or _apparent_utility(
                candidate, fixed_goal, cost
            ) > _apparent_utility(incumbent, fixed_goal, cost):
                incumbent = candidate
        current = [incumbent] if incumbent is not None else []
        value, chosen = _deliver(current, sim._goal_at(generation, change_at), cost)
        defects.record_delivery(chosen)
        trace.append(value)

    defects.record_retention([incumbent] if incumbent is not None else [])
    return _summary(
        "planner", trace, stats, 0, change_at, agents * generations, defect, defects
    )


def _majority_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    """Majority-vote swarm (issue #22 baseline 2).

    Each agent holds one fixed goal hypothesis drawn from the plausible set, so
    the swarm's beliefs are genuinely spread.  A verified candidate replaces the
    consensus only when a strict majority prefer it under their own hypothesis.
    Selection is therefore by vote rather than by independent evidence, and the
    swarm collapses onto a single consensus artifact instead of an archive.
    """
    del bins
    cost = _defect_cost(defect)
    beliefs = [rng.choice(sim.PLAUSIBLE_GOALS) for _ in range(agents)]
    threshold = agents // 2 + 1
    consensus: "sim.Candidate | None" = None
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = DefectStats()

    for generation in range(generations):
        proposals = [
            consensus.mutate(rng) if consensus is not None else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            if consensus is None:
                consensus = candidate
                continue
            votes = sum(
                1
                for goal in beliefs
                if _apparent_utility(candidate, goal, cost)
                > _apparent_utility(consensus, goal, cost)
            )
            if votes >= threshold:
                consensus = candidate
        current = [consensus] if consensus is not None else []
        value, chosen = _deliver(current, sim._goal_at(generation, change_at), cost)
        defects.record_delivery(chosen)
        trace.append(value)

    defects.record_retention([consensus] if consensus is not None else [])
    return _summary(
        "majority", trace, stats, 0, change_at, agents * generations, defect, defects
    )


RUNNERS: Dict[str, Callable[..., Dict[str, object]]] = {
    "random": _random_search,
    "scalar": _scalar_search,
    "qd": _qd_search,
    "planner": _planner_search,
    "majority": _majority_search,
}


def run_seed(
    seed: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None" = None,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    if agents < 2:
        raise ValueError("agents must be >= 2")
    if generations < 2:
        raise ValueError("generations must be >= 2")
    if not 1 <= change_at < generations:
        raise ValueError("change_at must satisfy 1 <= change_at < generations")
    if bins < 2:
        raise ValueError("bins must be >= 2")

    verification = verification or sim.VerificationConfig()
    evaluation_budget = agents * generations
    results = []
    for offset, strategy in enumerate(STRATEGIES):
        strategy_seed = seed + offset * STRATEGY_SEED_STRIDE
        result = RUNNERS[strategy](
            random.Random(strategy_seed),
            random.Random(strategy_seed ^ VERIFIER_STREAM_MASK),
            agents,
            generations,
            change_at,
            verification,
            bins,
            defect,
        )
        if result["verification_attempts"] != evaluation_budget:
            raise RuntimeError(f"{strategy} violated the matched evaluation budget")
        results.append(result)

    payload: Dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "matched-budget-emergence-v1",
        "seed": seed,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "bins": bins,
        "budget_contract": {
            "unit": "candidate proposal plus one panel-verification attempt",
            "per_strategy": evaluation_budget,
            "includes_initialization": True,
            "retry_until_acceptance": False,
            # One panel decision costs `verifiers` verifier votes for every arm,
            # so enlarging the panel scales the cost identically across arms and
            # cannot quietly buy one of them more evidence than another.
            "verifier_votes_per_strategy": evaluation_budget * verification.verifiers,
        },
        "verification": verification.as_dict(),
        "results": results,
    }
    # Absent when the channel is disarmed, so a default run's per-seed record
    # stays byte-identical to the one E024 and E026 published.
    if defect is not None:
        payload["defect_channel"] = defect.as_dict()
    return payload


def _stats(values: Sequence[float]) -> Dict[str, float | int]:
    n = len(values)
    average = mean(values)
    standard_deviation = stdev(values) if n > 1 else 0.0
    half_width = 1.96 * standard_deviation / math.sqrt(n)
    return {
        "n": n,
        "mean": round(average, 6),
        "stdev": round(standard_deviation, 6),
        "ci95_low": round(average - half_width, 6),
        "ci95_high": round(average + half_width, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def sweep(
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None" = None,
    defect: "DefectChannel | None" = None,
) -> Dict[str, object]:
    if seeds < 2:
        raise ValueError("seeds must be >= 2")

    metrics_collected = SUMMARY_METRICS + (DEFECT_METRICS if defect is not None else ())
    rows = {
        strategy: {metric: [] for metric in metrics_collected}
        for strategy in STRATEGIES
    }
    # Compare the constraint-guided archive against every other arm, so adding a
    # baseline extends the comparison table instead of silently going unreported.
    baselines = tuple(s for s in STRATEGIES if s != "qd")
    qd_wins = {
        f"qd_gt_{baseline}_post_change_utility_auc": 0 for baseline in baselines
    }

    for seed in range(seed_start, seed_start + seeds):
        result = run_seed(seed, agents, generations, change_at, bins, verification, defect)
        by_strategy = {row["strategy"]: row for row in result["results"]}
        for strategy, row in by_strategy.items():
            for metric in metrics_collected:
                rows[strategy][metric].append(float(row[metric]))

        for baseline in baselines:
            qd_wins[f"qd_gt_{baseline}_post_change_utility_auc"] += int(
                by_strategy["qd"]["post_change_utility_auc"]
                > by_strategy[baseline]["post_change_utility_auc"]
            )

    verification = verification or sim.VerificationConfig()
    report: Dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "matched-budget-emergence-sweep-v1",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "evaluation_budget_per_strategy_per_seed": agents * generations,
            "verification": verification.as_dict(),
        },
        "aggregate": {
            strategy: {
                metric: _stats(values)
                for metric, values in metrics.items()
            }
            for strategy, metrics in rows.items()
        },
        "pairwise_wins": {
            key: {
                "wins": wins,
                "trials": seeds,
                "rate": round(wins / seeds, 6),
            }
            for key, wins in qd_wins.items()
        },
        "limitations": [
            "All candidates, goals, and verification outcomes are synthetic.",
            "One evaluation unit is a simulator proposal plus panel decision, not measured compute, energy, or human attention.",
            "Quality-Diversity is given the four predefined plausible goals; the Goal Graph does not yet learn from evidence.",
            "The five strategies receive equal evaluation counts, but their internal bookkeeping costs are not measured.",
            "The benchmark does not model churn, malicious workers, task dependencies, stigmergic traces, or post-integration defects.",
            "The centralized planner and majority-vote swarm are single-artifact baselines by construction; their archive_size is always 0 and is not a defect.",
            "The legacy strategy-relative recovery_generations field remains in per-seed rows but is not aggregated; post-change utility/regret AUC is the comparable adaptation measure.",
        ],
    }

    if panel_is_perfect(verification) and defect is None:
        # Exactly the schema the committed reference artifact was published
        # with. Anything below would change it, so it stays behind this guard.
        return report

    horizon = generations - change_at
    threshold = CATASTROPHE_FRACTION * horizon
    if not panel_is_perfect(verification):
        report["configuration"]["panel_provenance"] = dict(PANEL_PROVENANCE)
    report["catastrophic_seeds"] = {
        "definition": "post_change_utility_auc below CATASTROPHE_FRACTION of the post-change horizon",
        "fraction_of_horizon": CATASTROPHE_FRACTION,
        "post_change_horizon": horizon,
        "utility_auc_threshold": round(threshold, 6),
        "by_strategy": {
            strategy: {
                "seeds": sum(
                    1
                    for value in metrics["post_change_utility_auc"]
                    if value < threshold
                ),
                "trials": seeds,
                "rate": round(
                    sum(
                        1
                        for value in metrics["post_change_utility_auc"]
                        if value < threshold
                    )
                    / seeds,
                    6,
                ),
            }
            for strategy, metrics in rows.items()
        },
    }
    if not panel_is_perfect(verification):
        report["limitations"].extend(_panel_limitations())
    if defect is not None:
        report["configuration"]["defect_channel"] = defect.as_dict()
        report["configuration"]["defect_provenance"] = dict(DEFECT_PROVENANCE)
        report["limitations"].extend(_defect_limitations())
    return report


def _panel_limitations() -> List[str]:
    return [
        "The verifier panel is imperfect here; its accuracy, correlation, and blind-spot floor are taken from E017/E020 measurements of 25 real partial test oracles, but they are applied to a synthetic landscape and are not a universal constant for verification panels.",
        "E017's oracles had strictly one-sided error (368 false accepts, 0 false rejects); this simulator's panel errs in both directions, so its false_reject_rate is a model output rather than a transferred measurement.",
        "The blind-spot fraction lambda rests on 4 of 72 tasks (Clopper-Pearson 95%: 0.015-0.136) and is a property of that panel's blind spots, not a transferable constant.",
        "Panel size scales verifier votes for every arm identically, so the comparison stays matched, but the extra verifier cost is counted in votes and not in wall time, energy, or human attention.",
    ]


def _defect_limitations() -> List[str]:
    return [
        "The defect-propagation channel is a synthetic mechanism. No defect cost was measured anywhere; the knob is swept across its whole range, including the zero that reproduces the E024/E026 behaviour, rather than fitted.",
        "A latent defect costs exactly the ground-truth utility of the artifact carrying it. Rework, blast radius, remediation effort, and defects that damage artifacts other than their own are not modelled.",
        "Defect propagation is instantaneous within a generation: there is no latency before a defect surfaces and no retroactive correction of an earlier trace point.",
        "The channel is deliberately not neutral across arms. A single-artifact arm ships a defect for a whole generation while an archive can route around a contaminated niche; that asymmetry is the mechanism under test, not a bias to be corrected.",
        "The channel changes what each arm retains, so the arms explore different regions than they did with the channel disarmed. Differences against E024 or E026 are the combined effect of contamination and of the altered search trajectory, which this benchmark does not separate.",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    panel = parser.add_argument_group(
        "verifier panel",
        "Perfect by default, which is how the committed reference sweep was "
        "produced. --imperfect-panel loads the measured E017/E020 panel; the "
        "individual flags then override any part of it.",
    )
    panel.add_argument(
        "--imperfect-panel",
        action="store_true",
        help="verify with the panel E017 measured: 25 partial test oracles, "
             "marginal accuracy 0.7956, item-difficulty dependence at icc "
             "0.4513, and E020's irreducible blind spot lambda=0.0556 "
             "(implied marginal pairwise rho 0.5873)",
    )
    panel.add_argument("--verifiers", type=int, default=None)
    panel.add_argument("--verifier-accuracy", type=float, default=None,
                       help="marginal per-verifier accuracy over all work units")
    panel.add_argument("--verifier-correlation", type=float, default=None,
                       help="pairwise error correlation of the reducible units, "
                            "excluding the blind-spot atom")
    panel.add_argument("--verifier-blind-spot", type=float, default=None,
                       help="irreducible fraction of units the whole panel gets "
                            "wrong together, whatever its size")
    panel.add_argument("--verifier-dependence",
                       choices=("shared-shock", "item-difficulty"), default=None,
                       help="E017 measured shared-shock to be the wrong shape")
    panel.add_argument("--verification-quorum", type=float, default=None)
    defects = parser.add_argument_group(
        "defect propagation",
        "Off by default, which is how the committed reference sweeps were "
        "produced. --defect-channel makes an accepted defect able to persist "
        "and do harm; --defect-cost then dials how much of it the system still "
        "believes in.",
    )
    defects.add_argument(
        "--defect-channel",
        action="store_true",
        help="rank and ship artifacts by apparent quality rather than by a free "
             "viability oracle, so a falsely accepted artifact can evict an "
             "incumbent, occupy a niche, be drawn as a parent, and deliver 0.0 "
             "when it ships (E027; closes the gap E026 measured)",
    )
    defects.add_argument(
        "--defect-cost",
        type=float,
        default=None,
        help="fraction of a latent defect's apparent quality the system still "
             "credits, in [0.0, 1.0]. 0.0 reproduces the E024/E026 behaviour "
             "exactly; 1.0 (the default) adds no assumption at all",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be >= 2")
    if args.agents < 2:
        parser.error("--agents must be >= 2")
    if args.generations < 2:
        parser.error("--generations must be >= 2")
    if not 1 <= args.change_at < args.generations:
        parser.error("--change-at must satisfy 1 <= change-at < generations")
    if args.bins < 2:
        parser.error("--bins must be >= 2")

    overrides = {
        "verifiers": args.verifiers,
        "accuracy": args.verifier_accuracy,
        "correlation": args.verifier_correlation,
        "blind_spot": args.verifier_blind_spot,
        "dependence": args.verifier_dependence,
        "quorum": args.verification_quorum,
    }
    named = {key: value for key, value in overrides.items() if value is not None}
    if named and not args.imperfect_panel:
        parser.error(
            "panel flags require --imperfect-panel; the default panel is "
            "perfect so that the committed reference sweep reproduces"
        )
    if args.verifiers is not None and args.verifiers < 1:
        parser.error("--verifiers must be >= 1")
    if args.verifier_accuracy is not None and not 0.5 <= args.verifier_accuracy <= 1.0:
        parser.error("--verifier-accuracy must be between 0.5 and 1.0")
    if args.verifier_correlation is not None and not 0.0 <= args.verifier_correlation <= 1.0:
        parser.error("--verifier-correlation must be between 0.0 and 1.0")
    if args.verifier_blind_spot is not None and not 0.0 <= args.verifier_blind_spot <= 1.0:
        parser.error("--verifier-blind-spot must be between 0.0 and 1.0")
    if args.verification_quorum is not None and not 0.0 <= args.verification_quorum < 1.0:
        parser.error("--verification-quorum must be in [0.0, 1.0)")

    if args.defect_cost is not None and not args.defect_channel:
        parser.error(
            "--defect-cost requires --defect-channel; the channel is off by "
            "default so that the committed reference sweeps reproduce"
        )
    if args.defect_cost is not None and not 0.0 <= args.defect_cost <= 1.0:
        parser.error("--defect-cost must be between 0.0 and 1.0")

    if args.imperfect_panel:
        try:
            args.verification = measured_panel(**named)
        except ValueError as error:
            parser.error(str(error))
    else:
        args.verification = None
    if args.defect_channel:
        args.defect = DefectChannel(
            **({} if args.defect_cost is None else {"cost": args.defect_cost})
        )
    else:
        args.defect = None
    return args


def main() -> None:
    args = parse_args()
    result = sweep(
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        verification=args.verification,
        defect=args.defect,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
