"""E031 -- does *learning* the goal rescue the consensus swarm?

E024's limitation on its own headline result has two halves. E030 measured the
first: the supplied plausible-goal set contains the goal the environment later
switches to, and the two arms that read that set are handed the answer. The
finding was arm-specific and inverted what E024 feared -- the Quality-Diversity
archive keeps `95.6%`-`98.4%` of its lead when the future goal is not a member,
while the majority-vote swarm loses its entire lead and goes negative in three
of four panels.

This is the second half:

    the plausible goals are supplied by the experimenter rather than LEARNED
    ... This is a test of retaining alternatives under known goal ambiguity,
    not a learned Goal Graph.

E031 builds the learned Goal Graph, and points it where E030 says the confound
actually lives: at ``majority``, not at the archive.

The arm
-------

``learned`` is ``majority`` with beliefs that update. Every structural choice is
identical -- one hypothesis per agent, drawn from the same supplied set with the
same rng draw, a strict-majority pairwise vote, one consensus artifact, the same
matched evaluation budget -- except that the swarm is a **particle filter** and
its hypotheses move.

That identity is not a claim; it is a reduction. At :data:`UNINFORMATIVE`
evidence strength the likelihood is flat, no weight ever changes, the effective
sample size never drops, no resampling fires, no random number is consumed by
the filter, and the arm produces a **bit-identical** trace to ``majority``. The
test suite pins that. Every difference reported here is therefore attributable
to the learning, and to nothing else.

The evidence channel, and why it is deliberately weak
-----------------------------------------------------

The obvious feedback signal -- the delivered artifact's realized utility -- is
too strong to be interesting. ``utility`` is ``min(1, sum(w_i x_i) + 0.08 *
sqrt(x_0 x_4))``, so an agent that observes the exact value and knows the
traits it shipped can subtract the interaction term and read off one linear
equation in the goal weights per generation. Four or five independent
deliveries and a least-squares solve recover the goal exactly. An experiment
built on that measures whether a 4x4 system can be inverted, not whether a
swarm can learn.

So the observation is **ordinal**: the swarm ships an artifact, and learns only
whether it did better or worse than the one it shipped before. That is what a
deployed system actually gets -- a preference, a regression signal, a rollback
-- and it is the same shape as the vote the swarm already takes internally.
It cannot be algebraically inverted.

Particles that predicted the observed direction correctly are up-weighted by
``1 - epsilon`` and the rest by ``epsilon``. When the effective sample size
falls below :data:`DEFAULT_ESS_FRACTION` of the particle count the filter
systematically resamples and jitters the survivors on the simplex.

The jitter is what makes this a *learned* Goal Graph rather than a re-weighted
oracle. Particles start at the supplied hypotheses but are not confined to
them: they diffuse, so the filter can converge on a goal that was never in the
box. Without it the arm would still be reading the experimenter's answer key,
just with better bookkeeping.

What this cannot show
---------------------

The arm learns from ``generations - change_at`` ordinal observations after the
goal moves, and only from generations in which the consensus actually changed.
A null result is therefore ambiguous between "learning does not help" and
"there was not enough evidence to learn from", which is why
:func:`belief_tracking` reports the posterior's distance to the true goal every
generation. A filter that never approaches the truth has not been given a fair
test; a filter that approaches it and still does not win has produced a real
finding.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim import e027_defect_propagation as e027  # noqa: E402
from sim import e030_supplied_goal_membership as e030  # noqa: E402
from sim import matched_budget_emergence as mbe  # noqa: E402
import sim.emergence_sim as sim  # noqa: E402

EXPERIMENT_ID = "E031"

ARM = "learned"

#: Flat likelihood. At this value the filter is provably inert and the arm
#: reduces to ``majority`` bit-for-bit; it is the control, not a setting.
UNINFORMATIVE = 0.5

DEFAULT_EPSILON = 0.3
DEFAULT_JITTER = 0.05
DEFAULT_ESS_FRACTION = 0.5

PANELS = e027.PANELS
PANEL_ORDER = e027.PANEL_ORDER
CONDITIONS = e030.CONDITIONS

DEFAULT_SEEDS = 100
DEFAULT_AGENTS = 64
DEFAULT_GENERATIONS = 50
DEFAULT_CHANGE_AT = 25
DEFAULT_BINS = 8

#: ``majority``'s own stream, deliberately. The learned arm is a modification of
#: that arm, so it must be run on that arm's random numbers or the control would
#: not reproduce the published baseline it is supposed to be. Nothing is
#: perturbed: this module never runs inside ``mbe.run_seed``, it re-derives the
#: same seed the way ``mbe.run_seed`` derives it.
LEARNED_STRATEGY_OFFSET = mbe.STRATEGIES.index("majority")


def _normalize(weights: Sequence[float]) -> Tuple[float, ...]:
    """Project a weight vector back onto the simplex, keeping it a legal goal."""
    clipped = [max(1e-6, value) for value in weights]
    total = sum(clipped)
    return tuple(value / total for value in clipped)


def _jitter(goal: Sequence[float], rng: random.Random, scale: float) -> Tuple[float, ...]:
    """Diffuse one particle. This is what lets it leave the supplied set."""
    if scale <= 0.0:
        return tuple(goal)
    return _normalize([value + rng.gauss(0.0, scale) for value in goal])


def _effective_sample_size(weights: Sequence[float]) -> float:
    total = sum(value * value for value in weights)
    return 0.0 if total <= 0.0 else 1.0 / total


def _systematic_resample(
    particles: Sequence[Sequence[float]], weights: Sequence[float], rng: random.Random
) -> List[Tuple[float, ...]]:
    """Low-variance resampling: one uniform draw, evenly spaced strata.

    Chosen over multinomial resampling because it consumes exactly one random
    number regardless of particle count, which keeps the arm's rng consumption
    a function of how often the filter fires rather than of how large it is.
    """
    count = len(particles)
    step = 1.0 / count
    start = rng.random() * step
    cumulative, index, chosen = weights[0], 0, []
    for draw in range(count):
        target = start + draw * step
        while target > cumulative and index < count - 1:
            index += 1
            cumulative += weights[index]
        chosen.append(tuple(particles[index]))
    return chosen


def _learned_swarm_search(
    rng: random.Random,
    verifier_rng: random.Random,
    agents: int,
    generations: int,
    change_at: int,
    verification: "sim.VerificationConfig",
    bins: int,
    defect: "mbe.DefectChannel | None" = None,
    *,
    epsilon: float = DEFAULT_EPSILON,
    jitter: float = DEFAULT_JITTER,
    ess_fraction: float = DEFAULT_ESS_FRACTION,
    forgetting: float = 0.0,
    learn_from: int = 0,
    reset_at: int | None = None,
    placebo: bool = False,
    diffuse_every: int = 0,
    vote_noise: float = 0.0,
    diverse_init: bool = False,
    tracking: List[Dict[str, Any]] | None = None,
) -> Dict[str, object]:
    """``mbe._majority_search`` with a particle filter behind the beliefs.

    Every line up to the evidence update is the majority arm's, in the same
    order, consuming the same random numbers, so the reduction at
    :data:`UNINFORMATIVE` is exact rather than approximate.
    """
    del bins
    cost = mbe._defect_cost(defect)
    beliefs = [rng.choice(sim.PLAUSIBLE_GOALS) for _ in range(agents)]
    particles: List[Tuple[float, ...]] = [tuple(goal) for goal in beliefs]
    # Spread ONCE, at initialisation, and then frozen. This separates "the
    # beliefs have to keep moving" from "there merely have to be many distinct
    # ones": the supplied set is four points shared across every agent, and
    # this turns it into `agents` distinct points that never change again.
    if diverse_init:
        particles = [_jitter(goal, rng, jitter) for goal in particles]
    weights = [1.0 / agents] * agents
    uniform = 1.0 / agents
    consensus: "sim.Candidate | None" = None
    trace: List[float] = []
    stats = sim.VerificationStats()
    defects = mbe.DefectStats()

    # The placebo's coin flips come from a dedicated stream, so the control
    # differs from the real filter ONLY in the weights it produces -- it does
    # not also shift every downstream mutation draw.
    placebo_rng = random.Random(rng.random()) if placebo else None
    # Loosens the consensus WITHOUT touching a single belief. The rival
    # explanation for the diffusion result is that any less-rigid consensus
    # would do as well, and this is what tests it. Its own stream, so it
    # perturbs the vote and nothing downstream.
    vote_rng = random.Random(rng.random()) if vote_noise > 0.0 else None

    previous_delivered: "sim.Candidate | None" = None
    previous_value = 0.0
    observations = 0
    resamples = 0
    diffusions = 0

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
            # Credibility-weighted, so what the filter learns actually acts.
            # Under uniform weights this is EXACTLY the strict-majority rule:
            # mass > 1/2 with every weight 1/n means count > n/2, which for
            # integer counts is count >= n//2 + 1 -- majority's threshold.
            mass = math.fsum(
                weight
                for goal, weight in zip(particles, weights)
                if mbe._apparent_utility(candidate, goal, cost)
                > mbe._apparent_utility(consensus, goal, cost)
            )
            if vote_rng is not None and vote_rng.random() < vote_noise:
                mass = 1.0 - mass
            if mass > 0.5:
                consensus = candidate
        current = [consensus] if consensus is not None else []
        value, chosen = mbe._deliver(current, sim._goal_at(generation, change_at), cost)
        defects.record_delivery(chosen)
        trace.append(value)

        # --- the only departure from ``majority`` -------------------------
        # Ordinal evidence: the swarm learns the DIRECTION its last shipment
        # moved the outcome, never the outcome itself.
        # An oracle change-detector: not a proposal, an upper bound. It tells
        # the filter for free exactly when to distrust everything it learned,
        # which no deployed system knows. If even this does not rescue the arm,
        # no amount of forgetting will.
        # Diffusion with no filter at all: no likelihood, no reweighting, no
        # resampling. The beliefs simply drift. This isolates spread from
        # everything else, because it carries not one bit of evidence.
        if diffuse_every > 0 and generation > 0 and generation % diffuse_every == 0:
            particles = [_jitter(goal, rng, jitter) for goal in particles]
            diffusions += 1

        if reset_at is not None and generation == reset_at:
            particles = [tuple(goal) for goal in beliefs]
            weights = [uniform] * agents

        if (
            epsilon != UNINFORMATIVE
            and generation >= learn_from
            and chosen is not None
            and previous_delivered is not None
            and chosen is not previous_delivered
        ):
            observed_improvement = value > previous_value
            updated = []
            for particle, weight in zip(particles, weights):
                if placebo:
                    # The same concentration dynamics, driven by a coin flip
                    # instead of evidence. Identical statistical shape, zero
                    # information. If this hurts as much as the real filter,
                    # the damage is concentration itself and not wrong beliefs.
                    agreed = placebo_rng.random() < 0.5
                else:
                    predicted_improvement = sim.unchecked_utility(
                        chosen, particle
                    ) > sim.unchecked_utility(previous_delivered, particle)
                    agreed = predicted_improvement == observed_improvement
                updated.append(weight * (1.0 - epsilon if agreed else epsilon))
            total = sum(updated)
            if total > 0.0:
                weights = [value_ / total for value_ in updated]
                if forgetting > 0.0:
                    # Bleed credibility back toward uniform. Without this the
                    # posterior that correctly identifies the FIRST goal is the
                    # same posterior that has thrown away the diversity needed
                    # to notice the second one.
                    weights = [
                        (1.0 - forgetting) * weight + forgetting * uniform
                        for weight in weights
                    ]
                observations += 1
                if _effective_sample_size(weights) < ess_fraction * agents:
                    particles = [
                        _jitter(goal, rng, jitter)
                        for goal in _systematic_resample(particles, weights, rng)
                    ]
                    weights = [1.0 / agents] * agents
                    resamples += 1
        if chosen is not None:
            previous_delivered, previous_value = chosen, value
        # ------------------------------------------------------------------

        if tracking is not None:
            posterior = _posterior_mean(particles, weights)
            truth = sim._goal_at(generation, change_at)
            tracking.append(
                {
                    "generation": generation,
                    "posterior_mean": [round(value_, 6) for value_ in posterior],
                    "distance_to_true_goal": round(math.dist(posterior, truth), 6),
                    # The variable that turns out to explain every arm here.
                    # ``majority`` holds the four supplied points, shared across
                    # every agent, however many agents it has.
                    "belief_spread": round(_belief_spread(particles), 6),
                    "effective_sample_size": round(_effective_sample_size(weights), 4),
                    "observations": observations,
                    "resamples": resamples,
                }
            )

    defects.record_retention([consensus] if consensus is not None else [])
    result = mbe._summary(
        ARM, trace, stats, 0, change_at, agents * generations, defect, defects
    )
    result["ordinal_observations"] = observations
    result["filter_resamples"] = resamples
    result["belief_diffusions"] = diffusions
    return result


def _belief_spread(particles: Sequence[Sequence[float]]) -> float:
    """How far apart the swarm's hypotheses are: mean distance from their mean.

    Counting *distinct* hypotheses is the obvious measure and it is the wrong
    one -- jitter makes every particle numerically unique, so a tightly
    collapsed cluster and a genuinely spread population both count 64. This is
    dispersion, which separates them. It is independent of the posterior's
    accuracy, and only one of the two predicts the outcome.
    """
    centre = _posterior_mean(particles, [1.0 / len(particles)] * len(particles))
    return statistics.fmean(math.dist(goal, centre) for goal in particles)


def _posterior_mean(
    particles: Sequence[Sequence[float]], weights: Sequence[float]
) -> Tuple[float, ...]:
    return tuple(
        sum(weight * particle[index] for particle, weight in zip(particles, weights))
        for index in range(len(particles[0]))
    )


def run_seed(
    *,
    seed: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None",
    epsilon: float = DEFAULT_EPSILON,
    jitter: float = DEFAULT_JITTER,
    ess_fraction: float = DEFAULT_ESS_FRACTION,
    forgetting: float = 0.0,
    learn_from: int = 0,
    reset_at: int | None = None,
    placebo: bool = False,
    diffuse_every: int = 0,
    vote_noise: float = 0.0,
    diverse_init: bool = False,
    tracking: List[Dict[str, Any]] | None = None,
) -> Dict[str, object]:
    """Run the learned arm on the stream ``run_seed`` leaves free for it."""
    verification = verification or sim.VerificationConfig()
    strategy_seed = seed + LEARNED_STRATEGY_OFFSET * mbe.STRATEGY_SEED_STRIDE
    result = _learned_swarm_search(
        random.Random(strategy_seed),
        random.Random(strategy_seed ^ mbe.VERIFIER_STREAM_MASK),
        agents,
        generations,
        change_at,
        verification,
        bins,
        None,
        epsilon=epsilon,
        jitter=jitter,
        ess_fraction=ess_fraction,
        forgetting=forgetting,
        learn_from=learn_from,
        reset_at=reset_at,
        placebo=placebo,
        diffuse_every=diffuse_every,
        vote_noise=vote_noise,
        diverse_init=diverse_init,
        tracking=tracking,
    )
    if result["verification_attempts"] != agents * generations:
        raise RuntimeError("learned arm violated the matched evaluation budget")
    return result


#: The variant ladder. Each rung exists to rule out one alternative explanation
#: for the rung above it, so the set is a decomposition rather than a sweep.
VARIANTS: Dict[str, Dict[str, Any]] = {
    # Provably identical to ``majority``. Not a setting -- the control.
    "control": {"epsilon": UNINFORMATIVE},
    # The learned Goal Graph E024 said it was not testing.
    "learned": {"epsilon": DEFAULT_EPSILON},
    # Same filter with the particles pinned to the supplied points. Separates
    # "learned the wrong goal" from "left the supplied set".
    "learned-no-jitter": {"epsilon": DEFAULT_EPSILON, "jitter": 0.0},
    # Same concentration dynamics driven by coin flips. Separates "concentrated
    # the posterior" from "concentrated it on the pre-change goal".
    "placebo": {"epsilon": DEFAULT_EPSILON, "placebo": True},
    # The placebo with its particles pinned. This is the pair that isolates the
    # jitter: same coin flips, same reweighting, no drift.
    "placebo-no-jitter": {"epsilon": DEFAULT_EPSILON, "placebo": True, "jitter": 0.0},
    # No likelihood, no reweighting, no resampling, no evidence: the beliefs
    # only drift. Isolates spread from every other thing the filter does.
    "diffusion": {"epsilon": UNINFORMATIVE, "diffuse_every": 5},
    # A quarter of the diffusion rate, so the result cannot be read as tuned.
    "diffusion-slow": {"epsilon": UNINFORMATIVE, "diffuse_every": 20},
    # Learns, but only from evidence generated after the goal has moved.
    # Separates the cost of learning from the cost of having learned early.
    "learned-after-change": {"epsilon": DEFAULT_EPSILON, "learn_from": None},
    # An upper bound, not a proposal: told for free exactly when to distrust
    # everything it knows. No deployed system gets this.
    "oracle-reset": {"epsilon": DEFAULT_EPSILON, "reset_at": None},
    # The rival explanation for the diffusion result: that any less-rigid
    # consensus would do as well. This loosens the vote without touching one
    # belief, at the noise level that minimised catastrophic seeds across a
    # 0.02-0.50 sweep -- the rival's best case, not a convenient one.
    "vote-noise": {"epsilon": UNINFORMATIVE, "vote_noise": 0.25},
    # Spread ONCE at initialisation and then frozen for the whole run. If this
    # matches ``diffusion`` then the mechanism is how many distinct hypotheses
    # the swarm holds, not that they keep moving -- a much narrower claim, and
    # the one the evidence actually supports.
    "diverse-init": {"epsilon": UNINFORMATIVE, "diverse_init": True},
}

#: Variants whose ``None`` placeholder means "the generation the goal moves".
_CHANGE_AT_KEYS = ("learn_from", "reset_at")

VARIANT_ORDER = tuple(VARIANTS)


def _variant_kwargs(name: str, change_at: int) -> Dict[str, Any]:
    kwargs = dict(VARIANTS[name])
    for key in _CHANGE_AT_KEYS:
        if key in kwargs and kwargs[key] is None:
            kwargs[key] = change_at
    return kwargs


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile. The tail is the claim, so it is reported."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def variant_sweep(
    *,
    variant: str,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig | None",
    goal: Sequence[float],
) -> Dict[str, Any]:
    """One variant, ``seeds`` seeds, with the environment's future goal at ``goal``."""
    kwargs = _variant_kwargs(variant, change_at)
    aucs: List[float] = []
    observations: List[int] = []
    resamples: List[int] = []
    diffusions: List[int] = []
    belief_error_pre: List[float] = []
    belief_error_post: List[float] = []
    distinct_pre: List[float] = []
    distinct_post: List[float] = []
    with e030.future_goal(goal):
        for offset in range(seeds):
            tracking: List[Dict[str, Any]] = []
            result = run_seed(
                seed=seed_start + offset,
                agents=agents,
                generations=generations,
                change_at=change_at,
                bins=bins,
                verification=verification,
                tracking=tracking,
                **kwargs,
            )
            aucs.append(float(result["post_change_utility_auc"]))
            observations.append(int(result["ordinal_observations"]))
            resamples.append(int(result["filter_resamples"]))
            diffusions.append(int(result["belief_diffusions"]))
            belief_error_pre.append(tracking[change_at - 1]["distance_to_true_goal"])
            belief_error_post.append(tracking[-1]["distance_to_true_goal"])
            distinct_pre.append(tracking[change_at - 1]["belief_spread"])
            distinct_post.append(tracking[-1]["belief_spread"])
    threshold = e030._catastrophe_threshold(generations, change_at)
    return {
        "variant": variant,
        "post_change_utility_auc": {
            "mean": round(statistics.fmean(aucs), 6),
            "stdev": round(statistics.pstdev(aucs), 6),
            "p05": round(_percentile(aucs, 0.05), 6),
            "min": round(min(aucs), 6),
        },
        "catastrophic_seeds": sum(1 for value in aucs if value < threshold),
        # The two numbers that separate "did not learn" from "learned and it
        # did not help". Without them a null result is unattributable.
        "belief_error": {
            "at_change": round(statistics.fmean(belief_error_pre), 6),
            "at_end": round(statistics.fmean(belief_error_post), 6),
        },
        # Reported beside the error because they are the two independent
        # properties of a belief population, and only one of them predicts the
        # outcome. ``majority`` holds four hypotheses no matter how many agents
        # it has, because the supplied set is four points.
        "belief_spread": {
            "at_change": round(statistics.fmean(distinct_pre), 6),
            "at_end": round(statistics.fmean(distinct_post), 6),
        },
        "filter_activity": {
            "ordinal_observations": round(statistics.fmean(observations), 4),
            "resamples": round(statistics.fmean(resamples), 4),
            "diffusions": round(statistics.fmean(diffusions), 4),
        },
        "per_seed_auc": [round(value, 6) for value in aucs],
    }


def matrix(
    *,
    panels: Dict[str, "sim.VerificationConfig"],
    panel_order: Sequence[str],
    variants: Sequence[str] = VARIANT_ORDER,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = 1,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
) -> Dict[str, Any]:
    threshold = e030._catastrophe_threshold(generations, change_at)
    cells: List[Dict[str, Any]] = []
    for panel in panel_order:
        for condition in CONDITIONS:
            goal = e030._goal_for(condition)
            # The published five arms, recomputed live rather than quoted, so
            # the reference this record compares against is this run's.
            baseline = e030.per_seed_auc(
                seeds=seeds,
                seed_start=seed_start,
                agents=agents,
                generations=generations,
                change_at=change_at,
                bins=bins,
                verification=panels[panel],
                goal=goal,
            )
            arms = {
                name: {
                    "mean": round(statistics.fmean(values), 6),
                    "catastrophic_seeds": sum(1 for v in values if v < threshold),
                }
                for name, values in baseline.items()
            }
            cells.append(
                {
                    "panel": panel,
                    "condition": condition,
                    "baseline_arms": arms,
                    "variants": [
                        variant_sweep(
                            variant=name,
                            seeds=seeds,
                            seed_start=seed_start,
                            agents=agents,
                            generations=generations,
                            change_at=change_at,
                            bins=bins,
                            verification=panels[panel],
                            goal=goal,
                        )
                        for name in variants
                    ],
                }
            )
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "learned-goal-filter-v1",
        "metric": "post_change_utility_auc",
        "seeds": seeds,
        "seed_start": seed_start,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "bins": bins,
        "catastrophe_utility_auc_threshold": round(threshold, 6),
        "epsilon": DEFAULT_EPSILON,
        "jitter": DEFAULT_JITTER,
        "ess_fraction": DEFAULT_ESS_FRACTION,
        "unheld_goal": list(e030.UNHELD_GOAL),
        "variants": {name: _variant_kwargs(name, change_at) for name in variants},
        "cells": cells,
        "limitations": [
            "The evidence channel is deliberately ordinal. The realized utility "
            "of a delivered artifact is a linear equation in the goal weights, "
            "so an arm that observed it could solve for the goal in four "
            "generations; that would measure linear algebra, not learning.",
            "Learning happens only from generations in which the consensus "
            "actually changed, so the post-change evidence rate is a few "
            "observations, not one per generation. The belief_error block is "
            "what makes a null result readable.",
            "The defect channel is disarmed. E027 and E028 cover it.",
            "The oracle-reset variant is an upper bound, not a design: it is "
            "told for free exactly when the goal moved.",
            "One landscape, one substitute goal, one filter family. A different "
            "belief representation could behave differently.",
        ],
    }


def _resolve_panels(
    selected: Sequence[str] | None,
) -> Tuple[Dict[str, "sim.VerificationConfig"], Tuple[str, ...]]:
    if not selected:
        return dict(PANELS), tuple(PANEL_ORDER)
    unknown = sorted(set(selected) - set(PANELS))
    if unknown:
        raise ValueError(f"unknown panel(s): {', '.join(unknown)}")
    chosen = set(selected)
    return (
        {name: PANELS[name] for name in PANEL_ORDER if name in chosen},
        tuple(name for name in PANEL_ORDER if name in chosen),
    )


def belief_tracking(
    *,
    seed: int = 7,
    variant: str = "learned",
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    verification: "sim.VerificationConfig | None" = None,
    condition: str = "held",
) -> Dict[str, Any]:
    """One run's belief trajectory, so a reader can see the filter work."""
    tracking: List[Dict[str, Any]] = []
    with e030.future_goal(e030._goal_for(condition)):
        result = run_seed(
            seed=seed,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verification=verification,
            tracking=tracking,
            **_variant_kwargs(variant, change_at),
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "seed": seed,
        "variant": variant,
        "condition": condition,
        "post_change_utility_auc": result["post_change_utility_auc"],
        "trajectory": tracking,
    }


def _json_default(value: Any) -> Any:  # pragma: no cover - defensive
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not serialisable: {type(value)!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("matrix", "trajectory"), default="matrix")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--change-at", type=int, default=DEFAULT_CHANGE_AT)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--panel", action="append", default=None)
    parser.add_argument("--variant", action="append", default=None)
    parser.add_argument("--condition", choices=CONDITIONS, default="held")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    if args.mode == "trajectory":
        payload: Dict[str, Any] = belief_tracking(
            seed=args.seed,
            variant=(args.variant or ["learned"])[0],
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            condition=args.condition,
        )
    else:
        panels, order = _resolve_panels(args.panel)
        chosen = args.variant or list(VARIANT_ORDER)
        unknown = sorted(set(chosen) - set(VARIANTS))
        if unknown:
            raise ValueError(f"unknown variant(s): {', '.join(unknown)}")
        payload = matrix(
            panels=panels,
            panel_order=order,
            variants=[name for name in VARIANT_ORDER if name in set(chosen)],
            seeds=args.seeds,
            seed_start=args.seed_start,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
        )

    text = json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
