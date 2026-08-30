#!/usr/bin/env python3
"""E028: does the Quality-Diversity result survive when defects are invisible?

E027 armed E024's defect-propagation channel and found that the archive held at
0/100 catastrophic seeds in every panel-by-cost cell while unconstrained random
search went 0/100 to 94/100.  The same audit that produced that number also
produced the caveat that bounds it: on this landscape, apparent quality *alone*
separates viable from non-viable accepted candidates at AUROC 0.937.  Elitist
selection is therefore already a second, free verifier, and E027 could not say
how much of the archive's survival was retained diversity and how much was the
landscape quietly leaking ground truth into the quality signal.

E028 removes the leak.  It moves ground-truth viability off the five budgeted
traits and into a sixth ``integrity`` dimension that:

* no plausible goal weights, so it cannot enter ``utility`` at all;
* no behaviour descriptor reads, so it cannot enter ``niche``;
* the trait budget does not constrain, so it cannot be inferred from what a
  candidate spent elsewhere.

Apparent quality is then uninformative about viability by construction rather
than by tuning, and ``--mode parity`` measures the residual AUROC instead of
asserting it.  This is the software case the synthetic landscape was always
standing in for: a latent defect is not visible in how good the artifact looks.

Two properties of the original landscape are deliberately held fixed, because
changing difficulty at the same time as informativeness would confound the
comparison:

``base viability rate``
    ``integrity`` is drawn uniformly on ``[0, 1]`` and the floor is 0.6, so
    40.0% of fresh candidates are viable.  The original landscape's measured
    rate over 400000 draws is 0.398413.
``heritability``
    ``P(child viable | parent viable)`` under the shared mutation operator.
    The original landscape measures 0.831209.  The default integrity sigma is
    the trait sigma, 0.12, which gives 0.880 -- stickier viability, which if
    anything helps the arms and therefore biases *against* a collapse finding.
    ``--integrity-sigma 0.171`` brings it to 0.830, within 0.005 of the
    original, and is run as a sensitivity arm rather than as the default,
    because the default adds no constant that the original model did not have.

Nothing about the search arms, the verifier panels, the defect channel, the
budget contract or the catastrophe threshold changes.  ``--mode matrix`` runs
E027's own matrix twice -- once on each landscape -- so the original column is
a live control rather than a quoted number.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import json
import random
from typing import Dict, Iterator, List, Sequence, Tuple

import sim.e027_defect_propagation as e027
import sim.emergence_sim as sim
from sim.matched_budget_emergence import (
    STRATEGY_SEED_STRIDE as _STRATEGY_SEED_STRIDE,
)
from sim.matched_budget_emergence import (
    VERIFIER_STREAM_MASK as _VERIFIER_STREAM_MASK,
)
from sim.matched_budget_emergence import STRATEGIES, _apparent_robust_quality
from sim.matched_budget_emergence import sim as _arena_sim

EXPERIMENT_ID = "E028"

# The latent dimension is appended after the five budgeted traits. Utility zips
# a five-weight goal against the trait tuple and therefore stops before it; the
# behaviour descriptor reads indices 1 and 2. Both properties are pinned by
# tests rather than left to the reader to verify.
LATENT_TRAIT = "integrity"
LATENT_INDEX = len(sim.TRAITS)

# Chosen to reproduce the original landscape's base viability rate, not tuned
# against any outcome. integrity ~ U(0, 1) makes the rate 1 - MIN_INTEGRITY
# exactly, so 0.6 gives 0.400 against the measured 0.398413.
MIN_INTEGRITY = 0.6

# The trait mutation sigma. Using it unchanged means the latent landscape
# introduces no constant the original model did not already contain.
INTEGRITY_SIGMA_DEFAULT = 0.12
# The value that instead matches the original landscape's measured
# heritability, 0.831209, to three decimals. Sensitivity arm only.
INTEGRITY_SIGMA_HERITABILITY_MATCHED = 0.171

LANDSCAPE_PROVENANCE = {
    "landscape": "E028 latent-defect dimension",
    "motivating_result": "experiments/E027-defect-propagation.md",
    "caveat_closed": (
        "E027 measured apparent robust quality as a 0.937-AUROC viability classifier "
        "over its own accepted candidates, so elitist selection was already acting as "
        "a second free verifier and the archive's survival could not be attributed to "
        "retained diversity alone."
    ),
    "mechanism": (
        "ground-truth viability is decided by a sixth `integrity` trait that no "
        "plausible goal weights, no behaviour descriptor reads, and the trait budget "
        "does not constrain. The five budgeted traits, their budget, the goals, the "
        "descriptor, the panels, the defect channel and the catastrophe threshold are "
        "unchanged."
    ),
    "held_fixed": {
        "base_viability_rate": {
            "original_measured": 0.398413,
            "original_sample": 400000,
            "latent_by_construction": round(1.0 - MIN_INTEGRITY, 6),
        },
        "heritability_p_child_viable_given_parent_viable": {
            "original_measured": 0.831209,
            "original_sample": 79388,
            "latent_at_default_sigma": 0.880437,
            "latent_at_matched_sigma": 0.831456,
            "matched_sigma": INTEGRITY_SIGMA_HERITABILITY_MATCHED,
        },
    },
    "direction_of_residual_bias": (
        "the default sigma leaves viability MORE heritable in the latent landscape "
        "than in the original, which helps every arm retain viable material and "
        "therefore biases against finding that an arm collapses"
    ),
    "evidence_level": "synthetic mechanism; the landscape is constructed, not measured",
}


# A panel whose acceptance carries no information about ground truth at all:
# 25 independent verifiers each at chance, so the majority vote is a coin flip
# regardless of viability. It is not a plausible panel and is not swept in the
# matrix; it exists as the control that isolates where a residual
# quality-viability association comes from. E027's PANELS is left untouched so
# the tests that pin its contents keep pinning the same four.
TRUTH_BLIND_PANEL = sim.VerificationConfig(
    verifiers=25, accuracy=0.5, correlation=0.0, quorum=0.5,
    dependence="item-difficulty",
)
DIAGNOSTIC_PANELS = dict(e027.PANELS, **{"truth-blind": TRUTH_BLIND_PANEL})
DIAGNOSTIC_PANEL_ORDER = e027.PANEL_ORDER + ("truth-blind",)


class LatentCandidate(sim.Candidate):
    """A candidate whose viability lives outside everything the goals can see.

    ``traits`` carries the five budgeted traits followed by ``integrity``. The
    budget renormalisation applies to the first five only, so spending on the
    observable traits neither buys nor costs integrity -- which is what makes
    the two independent rather than merely uncorrelated on average.
    """

    #: Overridden by :func:`_candidate_class`; the mutation sigma for integrity.
    INTEGRITY_SIGMA: float = INTEGRITY_SIGMA_DEFAULT

    @classmethod
    def random(cls, rng: random.Random) -> "LatentCandidate":
        raw = [rng.expovariate(1.0) for _ in sim.TRAITS]
        total = sum(raw)
        spend = rng.uniform(sim.BUDGET * 0.55, sim.BUDGET)
        vals = [min(1.0, spend * x / total) for x in raw]
        # Drawn from its own stream position, after the budgeted traits, so the
        # observable part of a candidate is generated exactly as before.
        integrity = rng.random()
        return cls(sim._renormalize_budget(vals) + (integrity,))

    def mutate(self, rng: random.Random, sigma: float = 0.12) -> "LatentCandidate":
        observable = [
            max(0.0, min(1.0, x + rng.gauss(0.0, sigma)))
            for x in self.traits[:LATENT_INDEX]
        ]
        integrity = max(
            0.0,
            min(1.0, self.traits[LATENT_INDEX] + rng.gauss(0.0, self.INTEGRITY_SIGMA)),
        )
        return type(self)(sim._renormalize_budget(observable) + (integrity,))


def _candidate_class(integrity_sigma: float) -> type:
    """A ``LatentCandidate`` subclass with ``integrity_sigma`` bound to it.

    Binding the sigma to the class rather than to a module-level global keeps
    the landscape free of mutable process state, so two configurations can be
    compared in one run without one leaking into the other.
    """
    if not 0.0 < integrity_sigma <= 1.0:
        raise ValueError("integrity sigma must be in (0.0, 1.0]")
    return type(
        "LatentCandidateSigma",
        (LatentCandidate,),
        {"INTEGRITY_SIGMA": integrity_sigma},
    )


def latent_viable(candidate: "sim.Candidate") -> bool:
    """Ground truth on the latent landscape.

    The budget clause is kept for parity with the original predicate even
    though ``_renormalize_budget`` already enforces it; dropping it would be a
    second change hidden inside the first.
    """
    return (
        candidate.traits[LATENT_INDEX] >= MIN_INTEGRITY
        and sum(candidate.traits[:LATENT_INDEX]) <= sim.BUDGET + 1e-9
    )


def _landscape_modules() -> Tuple[object, ...]:
    """Every distinct module object that owns a copy of the landscape.

    ``matched_budget_emergence`` loads ``emergence_sim.py`` by file path under
    the name ``emergence_sim``, which is a different module object from the
    package's ``sim.emergence_sim``. Both are patched, because the E027 audit
    reads ``sim.emergence_sim.viable`` while the arms it audits read the other.
    Missing one would leave two disagreeing definitions of ground truth in the
    same run, which is a silent-wrong-answer failure rather than a crash.
    """
    modules = [sim]
    if _arena_sim is not sim:
        modules.append(_arena_sim)
    return tuple(modules)


@contextlib.contextmanager
def latent_defect_landscape(
    integrity_sigma: float = INTEGRITY_SIGMA_DEFAULT,
) -> Iterator[type]:
    """Install the latent-defect landscape for the duration of the block.

    Restores the original bindings on the way out, including on an exception,
    so a failed run cannot leave the process holding a landscape that a later
    test or sweep would silently inherit.
    """
    candidate_class = _candidate_class(integrity_sigma)
    modules = _landscape_modules()
    saved = [(module, module.Candidate, module.viable) for module in modules]
    try:
        for module in modules:
            module.Candidate = candidate_class
            module.viable = latent_viable
        yield candidate_class
    finally:
        for module, candidate, viable in saved:
            module.Candidate = candidate
            module.viable = viable


def _auroc(positive: Sequence[float], negative: Sequence[float]) -> float:
    """Rank AUROC, ties at half weight. Same statistic E027's audit reports."""
    if not positive or not negative:
        return 0.0
    ordered = sorted(negative)
    total = 0.0
    for value in positive:
        low = bisect.bisect_left(ordered, value)
        high = bisect.bisect_right(ordered, value)
        total += low + 0.5 * (high - low)
    return total / (len(positive) * len(negative))


def _auroc_or_none(
    positive: Sequence[float], negative: Sequence[float]
) -> "float | None":
    """AUROC, or ``None`` when one class is empty and the statistic is undefined.

    ``_auroc`` returns 0.0 there to stay identical to E027's helper. 0.0 reads
    as perfect anti-separation, which is the opposite of "no defect was ever
    accepted, so there is nothing to separate" -- and that case is exactly what
    a good panel produces.
    """
    if not positive or not negative:
        return None
    return round(_auroc(positive, negative), 6)


def _measure_landscape(
    label: str, samples: int, seed: int, mutation_seed: int
) -> Dict[str, object]:
    """Base rate, heritability and quality-informativeness of the live landscape.

    Reads ``sim.Candidate`` and ``sim.viable`` through the module so it measures
    whichever landscape is installed, rather than a copy of one.
    """
    rng = random.Random(seed)
    candidates = [sim.Candidate.random(rng) for _ in range(samples)]
    flags = [sim.viable(candidate) for candidate in candidates]

    mutation_rng = random.Random(mutation_seed)
    retained = parents = 0
    for candidate, flag in zip(candidates, flags):
        if not flag:
            continue
        parents += 1
        retained += bool(sim.viable(candidate.mutate(mutation_rng)))

    quality = [sim.unchecked_robust_quality(candidate) for candidate in candidates]
    positive = [q for q, flag in zip(quality, flags) if flag]
    negative = [q for q, flag in zip(quality, flags) if not flag]

    return {
        "landscape": label,
        "samples": samples,
        "base_viability_rate": round(sum(flags) / samples, 6),
        "heritability": {
            "statistic": "P(child viable | parent viable) under one mutation",
            "viable_parents": parents,
            "value": round(retained / parents, 6) if parents else 0.0,
        },
        "apparent_quality_as_viability_classifier": {
            "statistic": "AUROC of unchecked robust quality over fresh random draws",
            "auroc": round(_auroc(positive, negative), 6),
            "viable": len(positive),
            "non_viable": len(negative),
            "uninformative_value": 0.5,
        },
    }


def parity(
    *, samples: int, seed: int, integrity_sigma: float = INTEGRITY_SIGMA_DEFAULT
) -> Dict[str, object]:
    """The control block: what changed between the landscapes, and what did not.

    Both landscapes are measured in the same process, with the same sample
    size and the same seeds, so the three numbers are directly comparable.
    """
    original = _measure_landscape("original", samples, seed, seed ^ 0x1F1F1F)
    with latent_defect_landscape(integrity_sigma):
        latent = _measure_landscape("latent-defect", samples, seed, seed ^ 0x1F1F1F)
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "latent-defect-landscape-parity-v1",
        "integrity_sigma": integrity_sigma,
        "landscape_provenance": LANDSCAPE_PROVENANCE,
        "measurements": [original, latent],
        "reading": (
            "the intended difference is the AUROC alone: base viability rate and "
            "heritability are held near the original landscape's measured values so "
            "the matrix comparison is not confounded by a change in difficulty"
        ),
    }


def matrix(
    *,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    panels: Sequence[str],
    costs: Sequence[float],
    integrity_sigma: float = INTEGRITY_SIGMA_DEFAULT,
) -> Dict[str, object]:
    """E027's matrix run once per landscape, paired cell by cell.

    The original landscape is re-run here rather than quoted, so the comparison
    cannot drift out of date and a change to the shared arms would show up as a
    disagreement with the published E027 record instead of hiding in a diff.
    """
    arguments = dict(
        seeds=seeds,
        seed_start=seed_start,
        agents=agents,
        generations=generations,
        change_at=change_at,
        bins=bins,
        panels=tuple(panels),
        costs=tuple(costs),
    )
    original = e027.matrix(**arguments)
    with latent_defect_landscape(integrity_sigma):
        latent = e027.matrix(**arguments)

    paired: List[Dict[str, object]] = []
    for original_cell, latent_cell in zip(original["cells"], latent["cells"]):
        assert original_cell["panel"] == latent_cell["panel"]
        assert original_cell["defect_cost"] == latent_cell["defect_cost"]
        paired.append(
            {
                "panel": original_cell["panel"],
                "defect_cost": original_cell["defect_cost"],
                "catastrophic_seeds": {
                    strategy: {
                        "original": original_cell["catastrophic_seeds"][strategy],
                        "latent": latent_cell["catastrophic_seeds"][strategy],
                        "delta": latent_cell["catastrophic_seeds"][strategy]
                        - original_cell["catastrophic_seeds"][strategy],
                    }
                    for strategy in STRATEGIES
                },
                "post_change_utility_auc": {
                    strategy: {
                        "original": original_cell["post_change_utility_auc"][strategy],
                        "latent": latent_cell["post_change_utility_auc"][strategy],
                    }
                    for strategy in STRATEGIES
                },
                "delivered_defect_rate": {
                    strategy: {
                        "original": original_cell["delivered_defect_rate"][strategy],
                        "latent": latent_cell["delivered_defect_rate"][strategy],
                    }
                    for strategy in STRATEGIES
                },
                "retained_defect_rate": {
                    strategy: {
                        "original": original_cell["retained_defect_rate"][strategy],
                        "latent": latent_cell["retained_defect_rate"][strategy],
                    }
                    for strategy in STRATEGIES
                },
                "qd_pairwise_wins": {
                    "original": original_cell["qd_pairwise_wins"],
                    "latent": latent_cell["qd_pairwise_wins"],
                },
            }
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "latent-defect-landscape-paired-matrix-v1",
        "configuration": dict(
            original["configuration"],
            integrity_sigma=integrity_sigma,
            reused_from="sim.e027_defect_propagation.matrix",
        ),
        "landscape_provenance": LANDSCAPE_PROVENANCE,
        "cells": paired,
        "limitations": [
            "Both landscapes are synthetic. Only the verifier-panel parameters are measured; the latent dimension is constructed to be uninformative, not observed to be.",
            "The latent landscape holds base viability rate and heritability near the original's measured values, but no other moment of the original landscape is matched.",
            "At the default integrity sigma the latent landscape is MORE heritable than the original (0.880 against 0.831). Run --integrity-sigma 0.171 for the heritability-matched sensitivity arm.",
            "The original column here is a live re-run of E027's matrix; it is the same synthetic model and is not independent evidence for E027's conclusion.",
            "Catastrophe counts use E024's threshold of 0.64 of the post-change horizon, unchanged, so the two landscapes are scored identically.",
            "A cell reports means and counts over its seeds; no paired significance test across cells is computed.",
        ],
    }


def quality_viability_diagnostic(
    seed: int,
    *,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    panel: "str | sim.VerificationConfig",
    defect_cost: float,
) -> Dict[str, object]:
    """Is E027's AUROC a landscape property, or an artifact of pooling?

    E027 measures apparent quality as a viability classifier over *all* the
    candidates one seed ever accepted, pooled across generations. Two things
    drift upward together over a run: archive quality rises as search proceeds,
    and the accepted pool's viable fraction rises as proposals come to be drawn
    from an accepted -- and therefore panel-enriched -- archive. Pooling two
    quantities that both trend with generation manufactures an association
    between them even when none exists at any fixed generation.

    This replays the same Quality-Diversity arm as ``e027.audit_qd_defects`` --
    same seed derivation, same two streams, same order of operations -- and
    reports the pooled AUROC alongside the generation-stratified one. The
    stratified figure conditions on generation, so it is the landscape's own
    separation with the drift removed.

    Runs on whichever landscape is installed, so the same function measures
    both and the comparison is not between two implementations.
    """
    verification = DIAGNOSTIC_PANELS[panel] if isinstance(panel, str) else panel
    strategy_seed = seed + STRATEGIES.index("qd") * _STRATEGY_SEED_STRIDE
    rng = random.Random(strategy_seed)
    verifier_rng = random.Random(strategy_seed ^ _VERIFIER_STREAM_MASK)
    stats = _arena_sim.VerificationStats()
    archive: Dict[Tuple[int, int], object] = {}

    per_generation: List[Tuple[List[float], List[float]]] = []
    pooled_viable: List[float] = []
    pooled_defect: List[float] = []

    for generation in range(generations):
        parents = list(archive.values())
        proposals = [
            rng.choice(parents).mutate(rng)
            if parents and rng.random() < 0.85
            else _arena_sim.Candidate.random(rng)
            for _ in range(agents)
        ]
        viable_here: List[float] = []
        defect_here: List[float] = []
        for candidate in proposals:
            if not _arena_sim.verify_candidate(
                candidate, verifier_rng, verification, stats
            ):
                continue
            quality = _arena_sim.unchecked_robust_quality(candidate)
            if _arena_sim.viable(candidate):
                viable_here.append(quality)
            else:
                defect_here.append(quality)
            key = _arena_sim.niche(candidate, bins)
            incumbent = archive.get(key)
            if incumbent is None or _apparent_robust_quality(
                candidate, defect_cost
            ) > _apparent_robust_quality(incumbent, defect_cost):
                archive[key] = candidate
        pooled_viable.extend(viable_here)
        pooled_defect.extend(defect_here)
        per_generation.append((viable_here, defect_here))

    # Weight each generation by its own pair count, so a generation that
    # accepted almost nothing cannot swing the conditioned figure.
    weighted_total = 0.0
    pairs_total = 0
    scored_generations = 0
    for viable_here, defect_here in per_generation:
        pairs = len(viable_here) * len(defect_here)
        if pairs == 0:
            continue
        scored_generations += 1
        pairs_total += pairs
        weighted_total += pairs * _auroc(viable_here, defect_here)

    viable_fraction = [
        len(v) / (len(v) + len(d)) if (v or d) else None for v, d in per_generation
    ]
    observed = [x for x in viable_fraction if x is not None]

    return {
        "experiment_id": EXPERIMENT_ID,
        "diagnostic": "pooled-versus-generation-stratified-auroc-v1",
        "seed": seed,
        "panel": panel if isinstance(panel, str) else verification.as_dict(),
        "defect_cost": defect_cost,
        "generations": generations,
        "change_at": change_at,
        "accepted_viable": len(pooled_viable),
        "accepted_defects": len(pooled_defect),
        "pooled_auroc": {
            "statistic": "E027's figure: apparent robust quality over all accepted candidates",
            "value": _auroc_or_none(pooled_viable, pooled_defect),
            "undefined_when": "the panel accepted no defect at all, so there is nothing to separate",
        },
        "generation_stratified_auroc": {
            "statistic": "the same figure computed within each generation, weighted by pair count",
            "value": round(weighted_total / pairs_total, 6) if pairs_total else None,
            "scored_generations": scored_generations,
            "pairs": pairs_total,
        },
        "viable_fraction_of_accepted": {
            "first_scored": round(observed[0], 6) if observed else None,
            "last_scored": round(observed[-1], 6) if observed else None,
            "why_it_matters": (
                "if this drifts upward while archive quality also rises, the pooled "
                "AUROC is measuring the shared trend and not the landscape"
            ),
        },
    }


def audit(
    seed: int,
    *,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    panel: str,
    defect_cost: float,
    integrity_sigma: float = INTEGRITY_SIGMA_DEFAULT,
) -> Dict[str, object]:
    """E027's Quality-Diversity audit replayed on the latent landscape."""
    with latent_defect_landscape(integrity_sigma):
        report = e027.audit_qd_defects(
            seed,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verification=e027.PANELS[panel],
            defect=e027.DefectChannel(cost=defect_cost),
        )
    report["experiment_id"] = EXPERIMENT_ID
    report["landscape"] = "latent-defect"
    report["integrity_sigma"] = integrity_sigma
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("parity", "matrix", "audit", "diagnostic"),
        default="parity",
    )
    parser.add_argument("--samples", type=int, default=200000, help="parity mode only")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--seeds", type=int, default=100, help="matrix mode only")
    parser.add_argument("--seed-start", type=int, default=0, help="matrix mode only")
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--panel", choices=DIAGNOSTIC_PANEL_ORDER, default="stress",
                        help="audit and diagnostic modes only; 'truth-blind' is a "
                             "diagnostic-only control and is rejected elsewhere")
    parser.add_argument("--defect-cost", type=float, default=1.0, help="audit mode only")
    parser.add_argument("--panels", default=",".join(e027.PANEL_ORDER),
                        help="matrix mode only: comma-separated panel names")
    parser.add_argument("--costs", default=",".join(str(c) for c in e027.COSTS),
                        help="matrix mode only: comma-separated defect costs")
    parser.add_argument(
        "--integrity-sigma", type=float, default=INTEGRITY_SIGMA_DEFAULT,
        help=f"mutation sigma for the latent dimension; "
             f"{INTEGRITY_SIGMA_HERITABILITY_MATCHED} matches the original "
             f"landscape's measured heritability",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if not 0.0 < args.integrity_sigma <= 1.0:
        parser.error("--integrity-sigma must be in (0.0, 1.0]")

    if args.mode == "parity":
        if args.samples < 2:
            parser.error("--samples must be >= 2")
        report = parity(
            samples=args.samples,
            seed=args.seed,
            integrity_sigma=args.integrity_sigma,
        )
    elif args.mode == "diagnostic":
        arguments = dict(
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            panel=args.panel,
            defect_cost=args.defect_cost,
        )
        original = quality_viability_diagnostic(args.seed, **arguments)
        with latent_defect_landscape(args.integrity_sigma):
            latent = quality_viability_diagnostic(args.seed, **arguments)
        report = {
            "experiment_id": EXPERIMENT_ID,
            "experiment": "pooled-versus-stratified-auroc-by-landscape-v1",
            "integrity_sigma": args.integrity_sigma,
            "landscape_provenance": LANDSCAPE_PROVENANCE,
            "measurements": [
                dict(original, landscape="original"),
                dict(latent, landscape="latent-defect"),
            ],
            "reading": (
                "the pooled figure is E027's. The stratified figure conditions on "
                "generation and removes the shared upward drift in archive quality "
                "and in the accepted pool's viable fraction. What survives "
                "stratification on the original landscape is a real landscape "
                "property; what survives it on the latent landscape is induced by a "
                "panel that is better than chance, and vanishes when the panel is not."
            ),
        }
    elif args.mode == "audit":
        if args.panel not in e027.PANELS:
            parser.error(f"--panel {args.panel} is a diagnostic-only control")
        report = audit(
            args.seed,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            panel=args.panel,
            defect_cost=args.defect_cost,
            integrity_sigma=args.integrity_sigma,
        )
    else:
        panels = tuple(name.strip() for name in args.panels.split(",") if name.strip())
        unknown = [name for name in panels if name not in e027.PANELS]
        if unknown:
            parser.error(f"unknown panel(s): {unknown}")
        try:
            costs = tuple(float(value) for value in args.costs.split(",") if value.strip())
        except ValueError:
            parser.error("--costs must be comma-separated floats")
        if not costs or not all(0.0 <= cost <= 1.0 for cost in costs):
            parser.error("--costs must all be in [0.0, 1.0]")
        report = matrix(
            seeds=args.seeds,
            seed_start=args.seed_start,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            panels=panels,
            costs=costs,
            integrity_sigma=args.integrity_sigma,
        )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
