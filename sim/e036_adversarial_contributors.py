#!/usr/bin/env python3
"""E036: does the archive survive contributors who *optimise* to pass the gate?

E026, E027 and E028 all model verification going wrong by accident: a panel is
noisy or correlated, a defect slips through, the defect is invisible. In all
three the archive held -- 0/100 catastrophic seeds in every cell of E027's
matrix, and E028 held that up after removing the landscape's quality/viability
leak.

Issue 22 lists something those three do not model, and
``matched_budget_emergence`` says so out loud in its own limitations: *"The
benchmark does not model churn, malicious workers, ..."*. A malicious worker is
not a noisy channel. It is an **optimising opponent**, and it optimises the one
quantity the archive selects on.

The threat model
----------------

A fraction of the contributor pool is hostile. A hostile contributor:

* draws :data:`ADVERSARY_EFFORT` candidates instead of one and submits the one
  with the highest **apparent** quality -- ``unchecked_robust_quality``, which
  is exactly what the elitist and archive arms rank on;
* sets ``integrity`` to ``0.0``, so the artifact is certainly defective on
  E028's latent dimension, which no goal weights, no behaviour descriptor
  reads, and the trait budget does not constrain.

Zero is chosen rather than "somewhere below the floor" for two reasons. It makes
a hostile artifact identifiable in an audit -- a healthy lineage produces
exactly-zero integrity with probability 0.0 -- and it makes the defect
*heritable*: 0.0 is five mutation sigmas below the 0.6 floor, so every
one-generation child of a poisoned parent is still non-viable, and about half
land back on exactly zero because the trait clamps. A captured niche stays
captured.

So the adversary maximises what the system can see while zeroing what it
cannot. ``effort = 1`` is a *faulty* contributor -- it submits junk but does not
try -- and ``effort > 1`` is a *strategic* one. The two knobs are the fraction
hostile and the effort each spends, which separates "how many" from "how hard".

Why this is a fair fight
------------------------

The evaluation budget contract is untouched. Every arm still sees exactly
``agents`` proposals per generation and spends ``agents * generations``
verification attempts, so the adversary buys no extra evaluations from the
system. Its ``effort`` draws are its own cost, not the defender's, which is the
realistic asymmetry: an attacker crafting a pull request does not consume the
maintainer's CI budget while crafting it.

Nothing in the search arms changes. The adversary is a property of the
contributor pool, so it is installed as a ``Candidate`` subclass exactly the way
E028 installs its landscape -- which also means an arm cannot special-case it.

The prediction, stated before the run
-------------------------------------

E026-E028 found the archive's advantage is robust to accidental failure. This
predicts it is **not** robust to optimised failure, because diversity
preservation is the mechanism under attack rather than the defence: the archive
keeps one elite per niche and the adversary can offer the best-looking occupant
of every niche. Concretely, we predict that as ``effort`` rises the archive's
catastrophe advantage over the majority-vote swarm *shrinks*, and that at high
effort the archive loses its 0/100 record.

:func:`matrix` records the prediction alongside the outcome so a falsification
is legible instead of being quietly rewritten.

Controls
--------

``fraction = 0.0`` consumes no randomness at all -- the coin is not flipped, it
is short-circuited -- so the zero column is **bit-identical** to E028's
landscape run, not merely close. :func:`identity_check` proves it rather than
asserting it, the way E027's cost-0.0 identity is pinned.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, Iterator, List, Sequence, Tuple

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e028_latent_defect_dimension as e028

EXPERIMENT_ID = "E036"
EXPERIMENT = "adversarial-contributor-fraction-by-effort-matrix-v1"

STRATEGIES = mbe.STRATEGIES

#: The integrity an adversarial artifact ships with. Exactly zero, so a hostile
#: candidate is certainly non-viable and cannot be confused with an unlucky
#: honest draw when auditing.
ADVERSARY_INTEGRITY = 0.0

#: Swept fractions of the contributor pool that are hostile. Weighted to the
#: low end: a 40% hostile pool collapses every arm to 100/100 and measures
#: nothing, so the interesting range is where a defender might still be alive.
FRACTIONS: Tuple[float, ...] = (0.0, 0.01, 0.02, 0.05, 0.10, 0.20)

#: Swept adversary effort. 1 is a faulty contributor -- it ships junk but does
#: not try, and its apparent quality is indistinguishable from an honest draw.
#: 8 is a strategic one, and it looks *better* than an honest contributor.
EFFORTS: Tuple[int, ...] = (1, 8)

#: E027's panels, reused by name so the cells line up with E027's and E028's
#: matrices rather than being a new axis that cannot be compared to them.
#:
#: ``perfect`` is a null control and is expected to be immune: it reads the
#: patched ``viable``, which sees ``integrity``, so it rejects every hostile
#: artifact outright. If the adversary moves a perfect-panel cell, the effect is
#: a bug rather than an attack. The other three admit hostile artifacts only
#: through their measured false-accept rate, which is the channel under test.
PANELS: Dict[str, "sim.VerificationConfig"] = dict(e027.PANELS)
PANEL_ORDER: Tuple[str, ...] = e027.PANEL_ORDER

PREDICTION = {
    "stated_before_run": True,
    "claim": (
        "The archive's catastrophe advantage over the majority-vote swarm "
        "shrinks as adversary effort rises, and at the highest fraction and "
        "effort the archive loses its 0/100 catastrophic-seed record."
    ),
    "reasoning": (
        "Diversity preservation is the mechanism under attack rather than the "
        "defence: the archive keeps one elite per niche and an optimising "
        "adversary can offer the best-looking occupant of every niche."
    ),
    "falsified_if": (
        "The archive holds at 0 catastrophic seeds in every cell, or its "
        "advantage over majority does not shrink with effort."
    ),
}


class AdversarialCandidate(e028.LatentCandidate):
    """A contributor pool in which some fraction is hostile.

    The fraction and the effort are bound to the class rather than kept in
    module state, for the reason E028 gives: two configurations must be
    comparable in one process without one leaking into the other.
    """

    #: Overridden by :func:`_candidate_class`.
    ADVERSARY_FRACTION: float = 0.0
    ADVERSARY_EFFORT: int = 1

    @classmethod
    def _is_hostile(cls, rng: random.Random) -> bool:
        """Short-circuits at zero so the control column burns no randomness."""
        if cls.ADVERSARY_FRACTION <= 0.0:
            return False
        return rng.random() < cls.ADVERSARY_FRACTION

    @classmethod
    def _compromise(cls, best: "AdversarialCandidate") -> "AdversarialCandidate":
        return type(best)(
            best.traits[: e028.LATENT_INDEX] + (ADVERSARY_INTEGRITY,)
        )

    @classmethod
    def random(cls, rng: random.Random) -> "AdversarialCandidate":
        if not cls._is_hostile(rng):
            return super().random(rng)
        drawn = [super(AdversarialCandidate, cls).random(rng) for _ in range(cls.ADVERSARY_EFFORT)]
        best = max(drawn, key=sim.unchecked_robust_quality)
        return cls._compromise(best)

    def mutate(self, rng: random.Random, sigma: float = 0.12) -> "AdversarialCandidate":
        cls = type(self)
        if not cls._is_hostile(rng):
            return super().mutate(rng, sigma)
        drawn = [super(AdversarialCandidate, self).mutate(rng, sigma) for _ in range(cls.ADVERSARY_EFFORT)]
        best = max(drawn, key=sim.unchecked_robust_quality)
        return cls._compromise(best)


def _candidate_class(
    *, fraction: float, effort: int, integrity_sigma: float
) -> type:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("adversary fraction must be in [0.0, 1.0]")
    if effort < 1:
        raise ValueError("adversary effort must be >= 1")
    if not 0.0 < integrity_sigma <= 1.0:
        raise ValueError("integrity sigma must be in (0.0, 1.0]")
    return type(
        "AdversarialCandidateBound",
        (AdversarialCandidate,),
        {
            "ADVERSARY_FRACTION": fraction,
            "ADVERSARY_EFFORT": effort,
            "INTEGRITY_SIGMA": integrity_sigma,
        },
    )


@contextlib.contextmanager
def adversarial_landscape(
    *,
    fraction: float,
    effort: int,
    integrity_sigma: float = e028.INTEGRITY_SIGMA_DEFAULT,
) -> Iterator[type]:
    """E028's latent landscape with a hostile slice of the contributor pool.

    Patches the same two module objects E028 patches, and restores them on the
    way out including on an exception, so a failed cell cannot leave a later
    cell running against a poisoned pool.
    """
    candidate_class = _candidate_class(
        fraction=fraction, effort=effort, integrity_sigma=integrity_sigma
    )
    modules = e028._landscape_modules()
    saved = [(module, module.Candidate, module.viable) for module in modules]
    try:
        for module in modules:
            module.Candidate = candidate_class
            module.viable = e028.latent_viable
        yield candidate_class
    finally:
        for module, candidate, viable in saved:
            module.Candidate = candidate
            module.viable = viable


def _panel(name: str) -> "sim.VerificationConfig":
    return PANELS[name]


def _cell(
    *,
    panel: str,
    fraction: float,
    effort: int,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    integrity_sigma: float,
) -> Dict[str, Any]:
    """One (fraction, effort) cell: a full matched-budget sweep."""
    with adversarial_landscape(
        fraction=fraction, effort=effort, integrity_sigma=integrity_sigma
    ):
        report = mbe.sweep(
            seeds=seeds,
            seed_start=seed_start,
            agents=agents,
            generations=generations,
            change_at=change_at,
            bins=bins,
            verification=_panel(panel),
            defect=mbe.DefectChannel(cost=1.0),
        )
    aggregate = report["aggregate"]
    catastrophic = report["catastrophic_seeds"]["by_strategy"]
    return {
        "panel": panel,
        "adversary_fraction": fraction,
        "adversary_effort": effort,
        "post_change_utility_auc": {
            s: aggregate[s]["post_change_utility_auc"]["mean"] for s in STRATEGIES
        },
        "catastrophic_seeds": {s: catastrophic[s]["seeds"] for s in STRATEGIES},
        "delivered_defect_rate": {
            s: aggregate[s]["delivered_defect_rate"]["mean"] for s in STRATEGIES
        },
        "retained_defect_rate": {
            s: aggregate[s]["retained_defect_rate"]["mean"] for s in STRATEGIES
        },
        "false_accept_rate": {
            s: aggregate[s]["false_accept_rate"]["mean"] for s in STRATEGIES
        },
        "archive_size": {s: aggregate[s]["archive_size"]["mean"] for s in STRATEGIES},
        "qd_pairwise_wins": {
            key: value["wins"] for key, value in report["pairwise_wins"].items()
        },
    }


def _cell_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process entry point.

    Cells run in *processes*, never threads: a cell rebinds ``Candidate`` and
    ``viable`` on two shared module objects, so two cells in one interpreter
    would silently read each other's landscape.
    """
    return _cell(**payload)


def catastrophe_advantage(cell: Dict[str, Any], baseline: str = "majority") -> int:
    """Seeds the baseline loses that the archive does not. Higher is safer."""
    return cell["catastrophic_seeds"][baseline] - cell["catastrophic_seeds"]["qd"]


def prediction_outcome(cells: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Grade :data:`PREDICTION` against what was measured.

    Both clauses are graded separately, because the prediction has an ``and`` in
    it and a half-true prediction that reads as confirmed is exactly the failure
    mode this function exists to prevent. The ``perfect`` panel is excluded from
    the grading and checked separately as a null control: it can see the latent
    trait, so it is immune by construction and including it would dilute the
    measurement with cells that cannot move.
    """
    graded = [c for c in cells if c["panel"] != "perfect"]
    efforts = sorted({cell["adversary_effort"] for cell in graded})
    hostile = [cell for cell in graded if cell["adversary_fraction"] > 0.0]
    # Keyed by string so the block survives a JSON round trip unchanged and the
    # committed artifact can be checked against a fresh call to this function.
    by_effort = {
        str(effort): sum(
            catastrophe_advantage(cell)
            for cell in hostile
            if cell["adversary_effort"] == effort
        )
        for effort in efforts
    }
    advantage_shrinks = (
        len(efforts) > 1
        and by_effort[str(efforts[-1])] < by_effort[str(efforts[0])]
    )
    baseline_qd = {
        cell["panel"]: cell["catastrophic_seeds"]["qd"]
        for cell in graded
        if cell["adversary_fraction"] == 0.0
    }
    lost_zero = sorted(
        {
            cell["panel"]
            for cell in hostile
            if baseline_qd.get(cell["panel"]) == 0
            and cell["catastrophic_seeds"]["qd"] > 0
        }
    )
    # The perfect panel decomposes the attack. It reads the patched viability
    # predicate, so it sees ``integrity`` and admits no hostile artifact at all;
    # what remains is pure *starvation*, because a hostile contributor still
    # occupies a proposal slot an honest one would have used. Measuring the two
    # separately is the point: if starvation alone moved the archive, the
    # poisoning result on the other panels would be confounded by it.
    perfect = [c for c in cells if c["panel"] == "perfect"]
    admits_no_defect = all(
        rate == 0.0
        for cell in perfect
        for rate in cell["retained_defect_rate"].values()
    ) if perfect else None
    starvation_only = {
        "admits_no_defect": admits_no_defect,
        "archive_catastrophes": sorted(
            {cell["catastrophic_seeds"]["qd"] for cell in perfect}
        ) if perfect else None,
        "archive_unmoved": (
            len({cell["catastrophic_seeds"]["qd"] for cell in perfect}) == 1
        ) if perfect else None,
        "worst_archive_auc_loss": round(
            max(cell["post_change_utility_auc"]["qd"] for cell in perfect)
            - min(cell["post_change_utility_auc"]["qd"] for cell in perfect),
            6,
        ) if perfect else None,
    }
    return {
        "advantage_by_effort": by_effort,
        "advantage_shrinks_with_effort": advantage_shrinks,
        "panels_where_the_archive_lost_a_clean_record": lost_zero,
        "archive_loses_its_zero_record": bool(lost_zero),
        "starvation_only_control": starvation_only,
        "supported": bool(advantage_shrinks and lost_zero),
        "partially_supported": bool(advantage_shrinks != bool(lost_zero)),
    }


def identity_check(
    *,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    integrity_sigma: float = e028.INTEGRITY_SIGMA_DEFAULT,
) -> Dict[str, Any]:
    """Prove the zero-fraction column *is* E028's landscape, bit for bit.

    Not "close to". The hostile branch short-circuits before touching the rng,
    so an identical stream must produce an identical report.
    """
    results = {}
    for name in PANEL_ORDER:
        with adversarial_landscape(
            fraction=0.0, effort=8, integrity_sigma=integrity_sigma
        ):
            adversarial = mbe.sweep(
                seeds=seeds, seed_start=seed_start, agents=agents,
                generations=generations, change_at=change_at, bins=bins,
                verification=_panel(name), defect=mbe.DefectChannel(cost=1.0),
            )
        with e028.latent_defect_landscape(integrity_sigma):
            baseline = mbe.sweep(
                seeds=seeds, seed_start=seed_start, agents=agents,
                generations=generations, change_at=change_at, bins=bins,
                verification=_panel(name), defect=mbe.DefectChannel(cost=1.0),
            )
        results[name] = {
            "identical": adversarial["aggregate"] == baseline["aggregate"],
            "adversarial_aggregate": adversarial["aggregate"],
            "e028_aggregate": baseline["aggregate"],
        }
    return {
        "identical": all(row["identical"] for row in results.values()),
        "by_panel": results,
    }


def matrix(
    *,
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    panels: Sequence[str] = PANEL_ORDER,
    fractions: Sequence[float] = FRACTIONS,
    efforts: Sequence[int] = EFFORTS,
    integrity_sigma: float = e028.INTEGRITY_SIGMA_DEFAULT,
    jobs: int = 1,
) -> Dict[str, Any]:
    """Panel by hostile fraction by adversary effort, one full sweep per cell."""
    horizon = generations - change_at
    threshold = mbe.CATASTROPHE_FRACTION * horizon
    payloads = [
        {
            "panel": panel,
            "fraction": fraction,
            "effort": effort,
            "seeds": seeds,
            "seed_start": seed_start,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "integrity_sigma": integrity_sigma,
        }
        for panel in panels
        for effort in efforts
        for fraction in fractions
    ]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            cells = list(pool.map(_cell_job, payloads))
    else:
        cells = [_cell_job(payload) for payload in payloads]

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "evaluation_budget_per_strategy_per_seed": agents * generations,
            "adversary_fractions": list(fractions),
            "adversary_efforts": list(efforts),
            "adversary_integrity": ADVERSARY_INTEGRITY,
            "adversary_target": "unchecked_robust_quality",
            "panels": {name: PANELS[name].as_dict() for name in panels},
            "panel_provenance": dict(mbe.PANEL_PROVENANCE),
            "defect_cost": 1.0,
            "integrity_sigma": integrity_sigma,
            "latent_trait": e028.LATENT_TRAIT,
            "minimum_integrity": e028.MIN_INTEGRITY,
            "catastrophe_utility_auc_threshold": round(threshold, 6),
            "post_change_horizon": horizon,
            "strategies": list(STRATEGIES),
        },
        "prediction": dict(PREDICTION),
        "cells": cells,
        "outcome": prediction_outcome(cells),
        "limitations": [
            "The adversary is goal-blind: it maximises unchecked_robust_quality, which is what the archive and the elitist arm rank on, but not the goal-weighted utility that decides delivery. A goal-aware adversary would be strictly stronger and is not measured here.",
            "The adversary's effort draws are free to the adversary. The system's evaluation budget is untouched and identical across cells, but a defender who could charge the attacker for its search would face a weaker opponent than this.",
            "Hostile contributors are independent. They do not coordinate, do not adapt to what was accepted, and do not persist across generations, so this is a lower bound on what an organised attacker does.",
            "Adversarial artifacts breed true, and this makes the attack stronger than an equivalent rate of accidental defects. Integrity 0.0 is 5 mutation sigmas below the 0.6 floor, so every one-generation child of a poisoned parent is still non-viable (measured 1.0), and about 49% land back on exactly 0.0 because the trait clamps at zero. A captured niche stays captured without being re-poisoned.",
            "The perfect-panel rows are a null control, not evidence: that panel reads the patched viability predicate, so it sees the latent trait and rejects every hostile artifact. They exist to show the attack runs through the false-accept channel rather than through a defect in the harness.",
            "One landscape. The panel axis reuses E027's four panels by name so the cells are comparable, but only the defect cost is held at 1.0 and E027's cost axis is not swept again.",
            "Catastrophe counts use E024's threshold of 0.64 of the post-change horizon, as in E027 and E028, so the counts are comparable across those records but the threshold is still a choice.",
            "The matrix reports means and counts over the seed set; it does not report a paired significance test across cells.",
        ],
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E036 adversarial contributors")
    parser.add_argument("--mode", choices=("matrix", "identity"), default="matrix")
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--agents", type=int, default=64)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--panel", action="append", default=None, choices=PANEL_ORDER)
    parser.add_argument("--fraction", type=float, action="append", default=None)
    parser.add_argument("--effort", type=int, action="append", default=None)
    parser.add_argument(
        "--integrity-sigma", type=float, default=e028.INTEGRITY_SIGMA_DEFAULT
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    common = dict(
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        integrity_sigma=args.integrity_sigma,
    )
    if args.mode == "identity":
        report = identity_check(**common)
    else:
        report = matrix(
            panels=tuple(args.panel) if args.panel else PANEL_ORDER,
            fractions=tuple(args.fraction) if args.fraction else FRACTIONS,
            efforts=tuple(args.effort) if args.effort else EFFORTS,
            jobs=max(1, args.jobs),
            **common,
        )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
