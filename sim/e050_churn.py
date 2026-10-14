"""E050 -- agent churn at a matched proposal-plus-verification budget.

Issue 22 lists "agent churn" and "resilience to churn" among the things the
emergence simulations should measure, and ``matched_budget_emergence`` says in
its limitations that the benchmark "does not model churn". This module adds that
one missing axis for the five E024 arms and nothing else.

What "churn" is here
--------------------

Each generation, from generation 1 on, a fraction ``f`` of the ``agents`` slots
is dropped and refilled by **fresh** agents. The count is
``floor(f * agents + 0.5)`` (half rounds up) and the slots are drawn without
replacement from a dedicated churn stream. ``f`` is swept over
``FRACTIONS = (0, 0.1, 0.25, 0.5, 1.0)``; ``1.0`` is the limit in which every
agent is replaced every generation. The proposal-plus-verification budget stays
exactly ``agents * generations`` for every arm and every ``f``.

What "fresh" means depends on where an arm keeps its state. That placement is
the thing under test, so it is stated per arm and per churn model:

==========  =======================  ==========================================
arm         state that survives      what a fresh agent lacks
==========  =======================  ==========================================
random      none (agents are         nothing: it is already memoryless
            memoryless)
scalar      shared elite pool        nothing it privately held (it held none)
qd          shared MAP-Elites        nothing it privately held (it held none)
            archive
planner     one shared incumbent     nothing it privately held (it held none)
majority    shared consensus         its own goal hypothesis (``belief``), which
            artifact                 is re-drawn from ``PLAUSIBLE_GOALS``
==========  =======================  ==========================================

Two churn models are measured, because the answer depends on which one is meant:

``memory``
    A fresh agent loses its **private memory** and nothing else. Only the
    majority swarm holds any (one belief per agent), so ``random``, ``scalar``,
    ``qd`` and ``planner`` are unchanged by construction. This is a statement
    about *state placement*: an architecture that keeps its state in shared
    structures cannot lose it to an agent leaving. It is not a finding that
    those arms are robust to anything.
``cold-start``
    A fresh agent also has **no access to the shared state for its first
    proposal** (an onboarding cost): that proposal is a blind random candidate
    instead of a mutation of the archive, elite, incumbent or consensus. The
    shared state itself still survives. This is the model that can move the
    arms that keep their state elsewhere, and it moves them only by diluting
    their proposals with blind ones.

Neither model is a model of real people or of real agent churn. Shared state
here survives the departure of every agent, which no real shared structure is
guaranteed to do; that is a deliberate assumption of the placement comparison,
and the version in which state leaves with its authors is **not measured**.

How the comparison stays faithful
---------------------------------

* ``f = 0`` is E024: every arm's row, trace included, is identical to
  ``matched_budget_emergence.run_seed``'s row for the same seed, and the rebuilt
  E024 ``aggregate`` block can be checked against the committed artifact by
  digest. The arms below re-implement E024's loops line for line, with
  churn hooks that do nothing at ``f = 0``, because E024's code must not change.
* Each arm keeps E024's proposal stream and verifier stream
  (``seed + offset * STRATEGY_SEED_STRIDE`` and its ``VERIFIER_STREAM_MASK``
  twin), which is the rule that a new arm must reuse the offset of the arm it
  extends. All churn randomness (which slots, which re-drawn belief, which blind
  candidate) comes from a **third** stream keyed to the same arm seed
  (``CHURN_STREAM_MASK``), so churn never consumes a proposal draw. An arm's
  original proposals are still drawn and then replaced for fresh slots, so the
  proposal stream stays aligned with E024's wherever the shared state agrees.
* The bootstrap draws from its own ``random.Random`` keyed by a string label.

Nothing here is evidence about real agents or real people. Every candidate,
goal, verdict and cost is synthetic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Sequence

import sim.matched_budget_emergence as mbe
from sim.e049_derived_measurements import (
    canonical_digest,
    clopper_pearson,
    mcnemar_exact,
    sign_test_p,
)

sim = mbe.sim

EXPERIMENT_ID = "E050"
EXPERIMENT = "agent-churn-at-matched-budget-v1"
EVIDENCE_LEVEL = "synthetic mechanism; no real agents or humans"

STRATEGIES = mbe.STRATEGIES
ARCHIVE_ARM = "qd"
BASELINES = tuple(s for s in STRATEGIES if s != ARCHIVE_ARM)

MEMORY = "memory"
COLD_START = "cold-start"
MODELS = (MEMORY, COLD_START)

#: Churn fractions per generation. ``0`` reproduces E024; ``1.0`` replaces every
#: agent every generation and is the limit, not a realistic setting.
FRACTIONS = (0.0, 0.1, 0.25, 0.5, 1.0)

DEFAULT_SEEDS = 100
DEFAULT_SEED_START = 0
DEFAULT_AGENTS = 50
DEFAULT_GENERATIONS = 50
DEFAULT_CHANGE_AT = 25
DEFAULT_BINS = 8
DEFAULT_RESAMPLES = 2000
CONFIDENCE = 0.95

#: A third stream per arm, distinct from ``mbe.VERIFIER_STREAM_MASK``.
CHURN_STREAM_MASK = 0x0C0FFEE5

#: Arms whose state is entirely shared or absent, so ``memory`` churn cannot
#: touch them. The artifact checks this by digest instead of assuming it.
STATE_FREE_ARMS = ("random", "scalar", "qd", "planner")

NOT_MEASURED = (
    "state that leaves with its authors: the shared archive, elite pool, incumbent and "
    "consensus always survive here, so the version of churn in which retained work walks "
    "out with the people who held it is not measured",
    "onboarding as anything but a one-proposal blind draw: no learning curve, no mentoring, "
    "no partial memory, no differing skill between newcomers and veterans",
    "who churns: departures are uniform at random over slots, never correlated with a "
    "goal belief, a niche or a region of the landscape, and never adversarial",
    "arrival and departure as a process in time: churn is a fixed fraction per generation, "
    "with no bursts, no trend, no population size change and no seasonal pattern",
    "a changing agent population size: the budget is held at agents * generations",
    "malicious or faulty replacements: every fresh agent is honest (E036 models "
    "adversarial contributors separately)",
    "real people or real agent churn: this is a synthetic mechanism and says nothing about "
    "contributor retention, onboarding cost or attrition in any real project",
    "human attention, energy and wall time: a proposal is a unit, not a person-hour",
)


# --------------------------------------------------------------------------
# Churn definition
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Churn:
    """How many agents are replaced per generation, and what a fresh one lacks."""

    fraction: float = 0.0
    model: str = MEMORY

    def __post_init__(self) -> None:
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError("churn fraction must be in [0.0, 1.0]")
        if self.model not in MODELS:
            raise ValueError(f"churn model must be one of {MODELS}")

    def count(self, agents: int) -> int:
        """Agents replaced per generation: ``floor(f * agents + 0.5)``."""
        return min(agents, int(math.floor(self.fraction * agents + 0.5)))

    def fresh_slots(self, churn_rng: random.Random, agents: int, generation: int) -> List[int]:
        """The slots replaced at the start of ``generation``, ascending.

        Generation 0 is the initial population, so nothing is replaced then. At
        ``f = 0`` no draw is made at all, which is why a zero-churn run leaves
        the churn stream untouched.
        """
        k = self.count(agents)
        if generation <= 0 or k == 0:
            return []
        return sorted(churn_rng.sample(range(agents), k))


def redraw_beliefs(
    beliefs: Sequence[Sequence[float]], fresh: Sequence[int], churn_rng: random.Random
) -> List[Sequence[float]]:
    """Fresh agents get a new goal hypothesis; everyone else keeps theirs."""
    updated = list(beliefs)
    for slot in fresh:
        updated[slot] = churn_rng.choice(sim.PLAUSIBLE_GOALS)
    return updated


def cold_start_proposals(
    proposals: Sequence["sim.Candidate"],
    fresh: Sequence[int],
    churn_rng: random.Random,
    model: str,
) -> List["sim.Candidate"]:
    """Under ``cold-start`` a fresh agent proposes blind; otherwise nothing changes."""
    updated = list(proposals)
    if model != COLD_START:
        return updated
    for slot in fresh:
        updated[slot] = sim.Candidate.random(churn_rng)
    return updated


# --------------------------------------------------------------------------
# The five arms: E024's loops with churn hooks
# --------------------------------------------------------------------------
def _summary(strategy: str, trace: List[float], stats: "sim.VerificationStats",
             archive_size: int, change_at: int, agents: int, generations: int):
    return mbe._summary(strategy, trace, stats, archive_size, change_at, agents * generations)


def _random(rng, verifier_rng, churn_rng, agents, generations, change_at, verification, bins, churn):
    del bins, churn_rng, churn  # agents hold nothing, so a fresh one is the old one
    trace: List[float] = []
    stats = sim.VerificationStats()
    for generation in range(generations):
        proposals = [sim.Candidate.random(rng) for _ in range(agents)]
        accepted = [
            c for c in proposals if sim.verify_candidate(c, verifier_rng, verification, stats)
        ]
        value, _ = mbe._deliver(accepted, sim._goal_at(generation, change_at), 0.0)
        trace.append(value)
    return _summary("random", trace, stats, 0, change_at, agents, generations)


def _scalar(rng, verifier_rng, churn_rng, agents, generations, change_at, verification, bins, churn):
    del bins
    population: List["sim.Candidate"] = []
    trace: List[float] = []
    stats = sim.VerificationStats()
    elite_count = max(2, min(32, agents // 4))
    for generation in range(generations):
        fresh = churn.fresh_slots(churn_rng, agents, generation)
        ranked = sorted(
            population,
            key=lambda c: mbe._apparent_utility(c, sim.INITIAL_GOAL, 0.0),
            reverse=True,
        )
        elites = ranked[:elite_count]
        proposals = [
            rng.choice(elites).mutate(rng) if elites else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        proposals = cold_start_proposals(proposals, fresh, churn_rng, churn.model)
        accepted = [
            c for c in proposals if sim.verify_candidate(c, verifier_rng, verification, stats)
        ]
        population = elites + accepted
        value, _ = mbe._deliver(population, sim._goal_at(generation, change_at), 0.0)
        trace.append(value)
    return _summary("scalar", trace, stats, 0, change_at, agents, generations)


def _qd(rng, verifier_rng, churn_rng, agents, generations, change_at, verification, bins, churn):
    archive: Dict[Any, "sim.Candidate"] = {}
    trace: List[float] = []
    stats = sim.VerificationStats()
    for generation in range(generations):
        fresh = churn.fresh_slots(churn_rng, agents, generation)
        parents = list(archive.values())
        proposals = [
            rng.choice(parents).mutate(rng)
            if parents and rng.random() < 0.85
            else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        proposals = cold_start_proposals(proposals, fresh, churn_rng, churn.model)
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            key = sim.niche(candidate, bins)
            incumbent = archive.get(key)
            if incumbent is None or mbe._apparent_robust_quality(
                candidate, 0.0
            ) > mbe._apparent_robust_quality(incumbent, 0.0):
                archive[key] = candidate
        value, _ = mbe._deliver(list(archive.values()), sim._goal_at(generation, change_at), 0.0)
        trace.append(value)
    return _summary("qd", trace, stats, len(archive), change_at, agents, generations)


def _planner(rng, verifier_rng, churn_rng, agents, generations, change_at, verification, bins, churn):
    del bins
    incumbent: "sim.Candidate | None" = None
    trace: List[float] = []
    stats = sim.VerificationStats()
    fixed_goal = sim.INITIAL_GOAL
    for generation in range(generations):
        fresh = churn.fresh_slots(churn_rng, agents, generation)
        proposals = [
            incumbent.mutate(rng) if incumbent is not None else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        proposals = cold_start_proposals(proposals, fresh, churn_rng, churn.model)
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            if incumbent is None or mbe._apparent_utility(
                candidate, fixed_goal, 0.0
            ) > mbe._apparent_utility(incumbent, fixed_goal, 0.0):
                incumbent = candidate
        current = [incumbent] if incumbent is not None else []
        value, _ = mbe._deliver(current, sim._goal_at(generation, change_at), 0.0)
        trace.append(value)
    return _summary("planner", trace, stats, 0, change_at, agents, generations)


def _majority(rng, verifier_rng, churn_rng, agents, generations, change_at, verification, bins, churn):
    del bins
    beliefs = [rng.choice(sim.PLAUSIBLE_GOALS) for _ in range(agents)]
    threshold = agents // 2 + 1
    consensus: "sim.Candidate | None" = None
    trace: List[float] = []
    stats = sim.VerificationStats()
    for generation in range(generations):
        fresh = churn.fresh_slots(churn_rng, agents, generation)
        beliefs = redraw_beliefs(beliefs, fresh, churn_rng)
        proposals = [
            consensus.mutate(rng) if consensus is not None else sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        proposals = cold_start_proposals(proposals, fresh, churn_rng, churn.model)
        for candidate in proposals:
            if not sim.verify_candidate(candidate, verifier_rng, verification, stats):
                continue
            if consensus is None:
                consensus = candidate
                continue
            votes = sum(
                1
                for goal in beliefs
                if mbe._apparent_utility(candidate, goal, 0.0)
                > mbe._apparent_utility(consensus, goal, 0.0)
            )
            if votes >= threshold:
                consensus = candidate
        current = [consensus] if consensus is not None else []
        value, _ = mbe._deliver(current, sim._goal_at(generation, change_at), 0.0)
        trace.append(value)
    return _summary("majority", trace, stats, 0, change_at, agents, generations)


RUNNERS = {
    "random": _random,
    "scalar": _scalar,
    "qd": _qd,
    "planner": _planner,
    "majority": _majority,
}


def run_churn_seed(
    seed: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    churn: Churn,
    verification: "sim.VerificationConfig | None" = None,
) -> Dict[str, Dict[str, Any]]:
    """The five arm rows for one seed under ``churn``, keyed by strategy.

    At ``Churn(0.0)`` each row equals the corresponding row of
    ``matched_budget_emergence.run_seed`` exactly.
    """
    if agents < 2:
        raise ValueError("agents must be >= 2")
    if generations < 2:
        raise ValueError("generations must be >= 2")
    if not 1 <= change_at < generations:
        raise ValueError("change_at must satisfy 1 <= change_at < generations")
    if bins < 2:
        raise ValueError("bins must be >= 2")
    verification = verification or sim.VerificationConfig()
    budget = agents * generations
    rows: Dict[str, Dict[str, Any]] = {}
    for offset, strategy in enumerate(STRATEGIES):
        strategy_seed = seed + offset * mbe.STRATEGY_SEED_STRIDE
        row = RUNNERS[strategy](
            random.Random(strategy_seed),
            random.Random(strategy_seed ^ mbe.VERIFIER_STREAM_MASK),
            random.Random(strategy_seed ^ CHURN_STREAM_MASK),
            agents,
            generations,
            change_at,
            verification,
            bins,
            churn,
        )
        if row["verification_attempts"] != budget:
            raise RuntimeError(f"{strategy} violated the matched evaluation budget")
        rows[strategy] = row
    return rows


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def catastrophe_threshold(generations: int, change_at: int) -> float:
    """E024's absolute cutoff: ``CATASTROPHE_FRACTION`` of the post-change horizon."""
    return mbe.CATASTROPHE_FRACTION * (generations - change_at)


def is_catastrophic(auc: float, threshold: float) -> bool:
    return auc < threshold


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
    return {"mean": round(sum(values) / n, 6), "ci95_low": round(low, 6), "ci95_high": round(high, 6)}


def _compare(first: Sequence[float], second: Sequence[float]):
    """``(first higher, second higher, ties)`` over paired seeds."""
    higher = sum(1 for a, b in zip(first, second) if a > b)
    lower = sum(1 for a, b in zip(first, second) if a < b)
    return higher, lower, len(first) - higher - lower


def paired_difference(
    first: Sequence[float], second: Sequence[float], label: str, resamples: int
) -> Dict[str, Any]:
    """``first - second`` over the same seeds: counts, exact sign test, bootstrap mean."""
    higher, lower, ties = _compare(first, second)
    diffs = [a - b for a, b in zip(first, second)]
    result: Dict[str, Any] = {
        "first_higher": higher,
        "second_higher": lower,
        "ties": ties,
        "p_value": sign_test_p(higher, lower),
        "mean_difference": bootstrap_mean_ci(diffs, label, resamples),
    }
    return result


def paired_catastrophe(
    first: Sequence[float], second: Sequence[float], threshold: float
) -> Dict[str, Any]:
    """McNemar on seeds that are catastrophic for one of the two arms only."""
    a = [is_catastrophic(v, threshold) for v in first]
    b = [is_catastrophic(v, threshold) for v in second]
    only_first = sum(1 for x, y in zip(a, b) if x and not y)
    only_second = sum(1 for x, y in zip(a, b) if y and not x)
    both = sum(1 for x, y in zip(a, b) if x and y)
    return {
        "first_only_catastrophic": only_first,
        "second_only_catastrophic": only_second,
        "both_catastrophic": both,
        "neither": len(a) - only_first - only_second - both,
        "p_value": mcnemar_exact(only_first, only_second),
    }


def first_sign_change(leads: Dict[float, float]) -> Dict[str, Any]:
    """Where a lead, tabulated by churn fraction, first changes sign.

    ``leads`` maps a churn fraction to the archive's paired mean lead over an arm
    (positive: the archive is ahead). The reference sign is the one at the
    smallest fraction. Only the grid is reported: the crossing is bracketed
    between two measured fractions, never interpolated, because interpolation
    would assume a shape the experiment does not establish.
    """
    ordered = sorted(leads)
    reference = _sign(leads[ordered[0]])
    result: Dict[str, Any] = {
        "reference_fraction": ordered[0],
        "reference_sign": reference,
        "first_sign_change_fraction": None,
        "bracket": None,
    }
    previous = ordered[0]
    for fraction in ordered[1:]:
        if _sign(leads[fraction]) != reference:
            result["first_sign_change_fraction"] = fraction
            result["bracket"] = [previous, fraction]
            break
        previous = fraction
    return result


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def comparison_count(models: Sequence[str], fractions: Sequence[float]) -> Dict[str, int]:
    """How many p-values the report contains, by family.

    Family 1: the archive against each baseline, a catastrophe McNemar and an AUC
    sign test, in every cell (``f = 0`` is one cell shared by both models).
    Family 2: each arm's own change from ``f = 0``, the same two tests, in every
    churned cell.
    """
    churned = [f for f in fractions if f > 0.0]
    cells = (1 if 0.0 in fractions else 0) + len(models) * len(churned)
    lead = len(BASELINES) * 2 * cells
    own = len(STRATEGIES) * 2 * len(models) * len(churned)
    return {"lead_vs_archive": lead, "own_effect_vs_no_churn": own, "total": lead + own}


# --------------------------------------------------------------------------
# One (model, fraction) cell, optionally in a worker process
# --------------------------------------------------------------------------
def _cell_job(job: Dict[str, Any]) -> Dict[str, Any]:
    churn = Churn(job["fraction"], job["model"])
    verification = None
    per_seed: Dict[str, List[float]] = {s: [] for s in STRATEGIES}
    metrics: List[Dict[str, Dict[str, float]]] = []
    digests = {s: hashlib.sha256() for s in STRATEGIES}
    for seed in range(job["seed_start"], job["seed_start"] + job["seeds"]):
        rows = run_churn_seed(
            seed, job["agents"], job["generations"], job["change_at"], job["bins"], churn,
            verification,
        )
        metrics.append(
            {s: {m: float(rows[s][m]) for m in mbe.SUMMARY_METRICS} for s in STRATEGIES}
        )
        for strategy in STRATEGIES:
            per_seed[strategy].append(rows[strategy]["post_change_utility_auc"])
            digests[strategy].update(
                json.dumps(rows[strategy], sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
    return {
        "model": job["model"],
        "fraction": job["fraction"],
        "per_seed_auc": per_seed,
        "metrics": metrics,
        "row_digests": {s: digests[s].hexdigest() for s in STRATEGIES},
    }


def e024_aggregate(metrics: Sequence[Dict[str, Dict[str, float]]]) -> Dict[str, Any]:
    """E024's ``aggregate`` block rebuilt with its own ``_stats``."""
    rows = {s: {m: [] for m in mbe.SUMMARY_METRICS} for s in STRATEGIES}
    for seed_metrics in metrics:
        for strategy in STRATEGIES:
            for metric in mbe.SUMMARY_METRICS:
                rows[strategy][metric].append(seed_metrics[strategy][metric])
    return {
        strategy: {metric: mbe._stats(values) for metric, values in per_metric.items()}
        for strategy, per_metric in rows.items()
    }


def _cell_key(model: str, fraction: float) -> str:
    return f"{model}:{fraction:g}"


def _label_model(model: str, fraction: float) -> str:
    """Bootstrap labels ignore the model at ``f = 0``, where the two models coincide,
    so the shared reference cell gets one set of intervals under either model."""
    return "reference" if fraction == 0.0 else model


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
    fractions: Sequence[float] = FRACTIONS,
    models: Sequence[str] = MODELS,
    resamples: int = DEFAULT_RESAMPLES,
    committed_e024: "Path | None" = None,
    workers: int = 1,
) -> Dict[str, Any]:
    if seeds < 2:
        raise ValueError("seeds must be >= 2")
    fractions = tuple(sorted(set(float(f) for f in fractions)))
    if fractions[0] != 0.0:
        raise ValueError("fractions must include 0.0, the E024 reference")
    threshold = catastrophe_threshold(generations, change_at)

    # f = 0 is one cell: both models coincide there, and it is the E024 reference.
    jobs = [{"model": MEMORY, "fraction": 0.0}]
    for model in models:
        for fraction in fractions:
            if fraction > 0.0:
                jobs.append({"model": model, "fraction": fraction})
    base = {
        "seeds": seeds, "seed_start": seed_start, "agents": agents,
        "generations": generations, "change_at": change_at, "bins": bins,
    }
    jobs = [dict(base, **job) for job in jobs]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            outputs = list(pool.map(_cell_job, jobs))
    else:
        outputs = [_cell_job(job) for job in jobs]

    reference = outputs[0]
    cells: Dict[str, Dict[str, Any]] = {}
    for out in outputs:
        key = "reference:0" if out["fraction"] == 0.0 else _cell_key(out["model"], out["fraction"])
        cells[key] = out

    def cell(model: str, fraction: float) -> Dict[str, Any]:
        return reference if fraction == 0.0 else cells[_cell_key(model, fraction)]

    def auc(model: str, fraction: float, arm: str) -> List[float]:
        return cell(model, fraction)["per_seed_auc"][arm]

    aggregate: Dict[str, Any] = {}
    paired_vs_archive: Dict[str, Any] = {}
    own_effect: Dict[str, Any] = {}
    for model in models:
        aggregate[model] = {}
        paired_vs_archive[model] = {}
        own_effect[model] = {}
        for fraction in fractions:
            fkey = f"{fraction:g}"
            aggregate[model][fkey] = {}
            paired_vs_archive[model][fkey] = {}
            for arm in STRATEGIES:
                values = auc(model, fraction, arm)
                catastrophes = sum(1 for v in values if is_catastrophic(v, threshold))
                aggregate[model][fkey][arm] = {
                    "post_change_utility_auc": bootstrap_mean_ci(
                        values, f"auc:{_label_model(model, fraction)}:{fkey}:{arm}", resamples
                    ),
                    "catastrophic_seeds": catastrophes,
                    "catastrophic_rate": clopper_pearson(catastrophes, len(values)),
                }
            archive = auc(model, fraction, ARCHIVE_ARM)
            for arm in BASELINES:
                other = auc(model, fraction, arm)
                paired_vs_archive[model][fkey][arm] = {
                    "auc_archive_minus_arm": paired_difference(
                        archive, other, f"lead:{_label_model(model, fraction)}:{fkey}:{arm}", resamples
                    ),
                    "catastrophe_archive_first": paired_catastrophe(archive, other, threshold),
                }
        for fraction in fractions:
            if fraction == 0.0:
                continue
            fkey = f"{fraction:g}"
            own_effect[model][fkey] = {}
            for arm in STRATEGIES:
                churned = auc(model, fraction, arm)
                still = auc(model, 0.0, arm)
                own_effect[model][fkey][arm] = {
                    "auc_churned_minus_no_churn": paired_difference(
                        churned, still, f"own:{model}:{fkey}:{arm}", resamples
                    ),
                    "catastrophe_churned_first": paired_catastrophe(churned, still, threshold),
                }

    lead_sign_changes: Dict[str, Any] = {}
    for model in models:
        lead_sign_changes[model] = {}
        for arm in BASELINES:
            leads = {
                f: paired_vs_archive[model][f"{f:g}"][arm]["auc_archive_minus_arm"][
                    "mean_difference"
                ]["mean"]
                for f in fractions
            }
            entry = first_sign_change(leads)
            entry["archive_lead_by_fraction"] = {f"{f:g}": v for f, v in leads.items()}
            lead_sign_changes[model][arm] = entry

    memory_noop = {}
    for arm in STRATEGIES:
        memory_noop[arm] = {
            f"{f:g}": cell(MEMORY, f)["row_digests"][arm] == reference["row_digests"][arm]
            for f in fractions
            if f > 0.0 and MEMORY in models
        }

    counts = comparison_count(models, fractions)
    report: Dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "evidence_level": EVIDENCE_LEVEL,
        "configuration": {
            **base,
            "post_change_horizon": generations - change_at,
            "verification": sim.VerificationConfig().as_dict(),
            "fractions": list(fractions),
            "models": list(models),
            "churned_per_generation": {
                f"{f:g}": Churn(f).count(agents) for f in fractions
            },
            "bootstrap_resamples": resamples,
            "catastrophe_threshold_auc": round(threshold, 6),
            "catastrophe_rule": "post_change_utility_auc < CATASTROPHE_FRACTION * horizon, "
            "E024's absolute cutoff, applied unchanged at every churn fraction",
            "source": "re-implementation of matched_budget_emergence's five arm loops with "
            "churn hooks; f = 0 reproduces E024 row for row",
        },
        "churn_definition": {
            "schedule": "from generation 1, each generation floor(f * agents + 0.5) slots are "
            "drawn without replacement from a dedicated churn stream and refilled by fresh agents",
            "streams": "proposal and verifier streams are E024's (same per-arm seed offset); "
            "churn draws come from a third stream, strategy_seed ^ CHURN_STREAM_MASK",
            "fresh_by_arm": {
                "random": "agents hold nothing; fresh equals old; churn is a no-op",
                "scalar": "shared elite pool survives; agents hold nothing private",
                "qd": "shared archive survives; agents hold nothing private",
                "planner": "one shared incumbent survives; agents hold nothing private",
                "majority": "shared consensus survives; a fresh agent's goal belief is re-drawn "
                "uniformly from the four plausible goals",
            },
            "models": {
                MEMORY: "a fresh agent loses private memory only; only the majority swarm has any, "
                "so the other four arms are unchanged by construction",
                COLD_START: "memory loss plus a blind random first proposal in place of a mutation "
                "of the shared state; the shared state itself survives",
            },
            "state_placement": "the archive, elite pool, incumbent and consensus are shared state "
            "that survives every departure; the swarm's beliefs are per-agent. The comparison is "
            "about where an architecture keeps its state, not a claim about people.",
        },
        "reference_check": {
            "f0_row_digests": reference["row_digests"],
            "e024_aggregate_rebuilt_sha256": canonical_digest(
                e024_aggregate(reference["metrics"])
            ),
            "memory_model_arm_rows_identical_to_no_churn": memory_noop,
        },
        "aggregate": aggregate,
        "paired_against_archive": paired_vs_archive,
        "own_effect_of_churn": own_effect,
        "lead_sign_changes": lead_sign_changes,
        "multiple_comparisons": {
            "p_values_reported": counts,
            "bonferroni_alpha_0.05": round(0.05 / counts["total"], 6),
            "note": "p-values are exact and uncorrected; read them against this alpha. Tests on "
            "arms the memory model cannot change are counted anyway (they are guaranteed ties), "
            "which makes the level conservative.",
        },
        "not_measured": list(NOT_MEASURED),
        "per_seed_post_change_utility_auc": {
            model: {
                f"{f:g}": {arm: auc(model, f, arm) for arm in STRATEGIES} for f in fractions
            }
            for model in models
        },
        "limitations": [
            "All candidates, goals, verdicts and costs are synthetic; this is mechanism evidence, "
            "not evidence about real agents, real people or real churn.",
            "Shared state survives every departure by assumption; that is the property being "
            "compared, and the opposite assumption is not measured.",
            "The cold-start model is one blind proposal per fresh agent; it is a dilution of "
            "proposals, not an onboarding model.",
            "The E024 perfect verifier panel is used, so no false accept can inflate an arm.",
            "100 seeds of one landscape, one change size and one direction (E033-E035 show the "
            "archive's lead depends on both).",
        ],
    }
    if committed_e024 is not None:
        committed = json.loads(Path(committed_e024).read_text(encoding="utf-8"))
        rebuilt = e024_aggregate(reference["metrics"])
        report["reference_check"]["committed_e024"] = {
            "artifact": "experiments/results/" + Path(committed_e024).name,
            "committed_aggregate_sha256": canonical_digest(committed["aggregate"]),
            "replayed_aggregate_sha256": canonical_digest(rebuilt),
            "matches": committed["aggregate"] == rebuilt,
        }
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--fractions", type=float, nargs="+", default=list(FRACTIONS),
        help="churn fractions per generation; must include 0",
    )
    parser.add_argument(
        "--check-e024", default=None, metavar="PATH",
        help="committed E024 artifact whose aggregate the f = 0 cell must reproduce",
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
    if 0.0 not in args.fractions:
        parser.error("--fractions must include 0")
    if any(not 0.0 <= f <= 1.0 for f in args.fractions):
        parser.error("--fractions must lie in [0, 1]")
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
        fractions=args.fractions,
        resamples=args.resamples,
        committed_e024=Path(args.check_e024) if args.check_e024 else None,
        workers=args.workers,
    )
    text = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
