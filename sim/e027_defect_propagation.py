#!/usr/bin/env python3
"""E027: sweep the defect-propagation channel and audit what it actually does.

E026 armed E024's verifier panel with a measured imperfect, correlated error
model and found that nothing moved. It also diagnosed why: every arm ranks
candidates with ``utility()`` and ``robust_quality()``, both of which consult
``viable()`` directly, so a falsely accepted artifact scores 0.0 and is
discarded by the very predicate the verifier panel was meant to enforce.

``sim.matched_budget_emergence.DefectChannel`` closes that gap. This module
does the two things a reader needs in order to trust or reject the result:

``--mode matrix``
    Sweeps panel quality against the defect-cost knob, 100 seeds per cell, so
    the conclusion can be read off a surface rather than off one convenient
    setting. Cost 0.0 is included and must reproduce E026's null exactly.

``--mode audit``
    Replays one seed's Quality-Diversity arm with the channel armed and counts
    what the panel waved through, how much of it ever reached the archive, how
    much survived, and how often a defect was the artifact that shipped. It
    also measures how well apparent quality *alone* separates viable from
    non-viable candidates, because that separation -- not verification -- turns
    out to be what protects the archive.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import json
import random
from typing import Dict, List, Sequence, Tuple

import sim.emergence_sim as sim
from sim.matched_budget_emergence import (
    CATASTROPHE_FRACTION,
    DEFECT_PROVENANCE,
    STRATEGIES,
    STRATEGY_SEED_STRIDE,
    VERIFIER_STREAM_MASK,
    DefectChannel,
    _apparent_robust_quality,
    _apparent_utility,
    measured_panel,
    sweep,
)

EXPERIMENT_ID = "E027"
QD = "qd"

# The same four panels E026's Result 3 table sweeps, so the two records line up
# row for row and the cost-0.0 column is directly comparable to E026's numbers.
PANELS: Dict[str, "sim.VerificationConfig"] = {
    "perfect": sim.VerificationConfig(),
    "independent": measured_panel(correlation=0.0, blind_spot=0.0),
    "measured": measured_panel(),
    "stress": measured_panel(accuracy=0.55, correlation=0.9, blind_spot=0.4),
}
PANEL_ORDER = ("perfect", "independent", "measured", "stress")

# The knob is swept across its whole declared range rather than fitted. 0.0 is
# the E024/E026 behaviour and 1.0 is the assumption-free end; the interior
# points exist so a reader can see the shape instead of two endpoints.
COSTS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _roc_auc(positive: Sequence[float], negative: Sequence[float]) -> float:
    """Rank AUROC of `positive` over `negative`, ties counted at half weight."""
    if not positive or not negative:
        return 0.0
    labelled = sorted(
        [(value, 1) for value in positive] + [(value, 0) for value in negative]
    )
    # Average ranks within tied blocks so a flat score cannot look informative.
    ranks: List[float] = [0.0] * len(labelled)
    index = 0
    while index < len(labelled):
        end = index
        while end + 1 < len(labelled) and labelled[end + 1][0] == labelled[index][0]:
            end += 1
        average = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            ranks[position] = average
        index = end + 1
    positive_rank_sum = sum(
        rank for rank, (_, label) in zip(ranks, labelled) if label == 1
    )
    n_pos, n_neg = len(positive), len(negative)
    return (positive_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def audit_qd_defects(
    seed: int,
    *,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: "sim.VerificationConfig",
    defect: DefectChannel,
) -> Dict[str, object]:
    """Replay the Quality-Diversity arm with the channel armed and inspect it.

    Mirrors ``_qd_search`` exactly -- same strategy-seed derivation, same two
    random streams, same budget -- and adds only counters, so the numbers it
    reports are the numbers the benchmark produced.
    """
    cost = defect.cost
    strategy_seed = seed + STRATEGIES.index(QD) * STRATEGY_SEED_STRIDE
    rng = random.Random(strategy_seed)
    verifier_rng = random.Random(strategy_seed ^ VERIFIER_STREAM_MASK)
    stats = sim.VerificationStats()
    archive: Dict[Tuple[int, int], "sim.Candidate"] = {}

    defects_entered_archive = 0
    defects_evicting_a_viable_incumbent = 0
    peak_defects_in_archive = 0
    generations_delivering_a_defect = 0
    accepted_viable_quality: List[float] = []
    accepted_defect_quality: List[float] = []

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
            quality = sim.unchecked_robust_quality(candidate)
            if sim.viable(candidate):
                accepted_viable_quality.append(quality)
            else:
                accepted_defect_quality.append(quality)
            key = sim.niche(candidate, bins)
            incumbent = archive.get(key)
            if incumbent is None or _apparent_robust_quality(
                candidate, cost
            ) > _apparent_robust_quality(incumbent, cost):
                if not sim.viable(candidate):
                    defects_entered_archive += 1
                    if incumbent is not None and sim.viable(incumbent):
                        defects_evicting_a_viable_incumbent += 1
                archive[key] = candidate
        held = sum(1 for c in archive.values() if not sim.viable(c))
        peak_defects_in_archive = max(peak_defects_in_archive, held)

        goal = sim._goal_at(generation, change_at)
        shipped = None
        best = None
        for candidate in archive.values():
            apparent = _apparent_utility(candidate, goal, cost)
            if best is None or apparent > best:
                best, shipped = apparent, candidate
        if shipped is not None and not sim.viable(shipped):
            generations_delivering_a_defect += 1

    return {
        "experiment_id": EXPERIMENT_ID,
        "seed": seed,
        "panel": verification.as_dict(),
        "defect_channel": defect.as_dict(),
        "verification_attempts": stats.attempts,
        "verification_accepts": stats.accepts,
        "accepted_but_non_viable": stats.false_accepts,
        "defects_entered_archive": defects_entered_archive,
        "defects_evicting_a_viable_incumbent": defects_evicting_a_viable_incumbent,
        "peak_defects_in_archive": peak_defects_in_archive,
        "archive_size": len(archive),
        "non_viable_in_final_archive": sum(
            1 for c in archive.values() if not sim.viable(c)
        ),
        "generations": generations,
        "generations_delivering_a_defect": generations_delivering_a_defect,
        "selection_as_free_verifier": {
            "statistic": "AUROC of apparent robust quality as a viability classifier, over this seed's accepted candidates",
            "auroc": round(
                _roc_auc(accepted_viable_quality, accepted_defect_quality), 6
            ),
            "accepted_viable": len(accepted_viable_quality),
            "accepted_defects": len(accepted_defect_quality),
            "why_it_matters": (
                "an AUROC above 0.5 means the archive's own quality comparison is "
                "already a partial verifier, so the archive is protected from "
                "accepted defects by the landscape and not only by retained diversity"
            ),
        },
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
    costs: Sequence[float] = COSTS,
) -> Dict[str, object]:
    """Panel quality against defect cost, one full sweep per cell."""
    horizon = generations - change_at
    threshold = CATASTROPHE_FRACTION * horizon
    cells: List[Dict[str, object]] = []
    for panel_name in panels:
        verification = PANELS[panel_name]
        for cost in costs:
            report = sweep(
                seeds=seeds,
                seed_start=seed_start,
                agents=agents,
                generations=generations,
                change_at=change_at,
                bins=bins,
                verification=verification,
                defect=DefectChannel(cost=cost),
            )
            aggregate = report["aggregate"]
            cells.append(
                {
                    "panel": panel_name,
                    "defect_cost": cost,
                    "post_change_utility_auc": {
                        strategy: aggregate[strategy]["post_change_utility_auc"]["mean"]
                        for strategy in STRATEGIES
                    },
                    "catastrophic_seeds": {
                        strategy: report["catastrophic_seeds"]["by_strategy"][strategy][
                            "seeds"
                        ]
                        for strategy in STRATEGIES
                    },
                    "delivered_defect_rate": {
                        strategy: aggregate[strategy]["delivered_defect_rate"]["mean"]
                        for strategy in STRATEGIES
                    },
                    "retained_defect_rate": {
                        strategy: aggregate[strategy]["retained_defect_rate"]["mean"]
                        for strategy in STRATEGIES
                    },
                    "false_accept_rate": {
                        strategy: aggregate[strategy]["false_accept_rate"]["mean"]
                        for strategy in STRATEGIES
                    },
                    "qd_pairwise_wins": {
                        key: value["wins"]
                        for key, value in report["pairwise_wins"].items()
                    },
                }
            )

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": "defect-propagation-panel-by-cost-matrix-v1",
        "configuration": {
            "seed_start": seed_start,
            "seeds": seeds,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "evaluation_budget_per_strategy_per_seed": agents * generations,
            "panels": {name: PANELS[name].as_dict() for name in panels},
            "defect_costs": list(costs),
            "defect_provenance": dict(DEFECT_PROVENANCE),
            "catastrophe_utility_auc_threshold": round(threshold, 6),
            "post_change_horizon": horizon,
        },
        "cells": cells,
        "limitations": [
            "Every cell is the same synthetic landscape; only the verifier-panel parameters are measured, and the defect cost is not measured at all.",
            "The defect cost is a swept dial, not a fitted quantity. Reading one column of this matrix as 'the' answer would be exactly the free-parameter mistake the sweep exists to prevent.",
            "Cost 0.0 reproduces the E024/E026 behaviour by construction, so the cost-0.0 column is a control rather than an independent confirmation.",
            "The perfect-panel rows cannot vary with cost: a panel that never accepts a non-viable candidate never creates a defect for the channel to propagate. They are a null control.",
            "Catastrophe counts use E024's threshold of 0.64 of the post-change horizon; a different threshold would move the counts but not the ordering.",
            "The matrix reports means and counts over 100 seeds per cell; it does not report a paired significance test across cells.",
        ],
    }


def _panel_from_name(name: str) -> "sim.VerificationConfig":
    return PANELS[name]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("matrix", "audit"), default="matrix")
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7, help="audit mode only")
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--panel", choices=PANEL_ORDER, default="stress",
                        help="audit mode only")
    parser.add_argument("--defect-cost", type=float, default=1.0,
                        help="audit mode only; the matrix sweeps the whole range")
    parser.add_argument("--panels", default=",".join(PANEL_ORDER),
                        help="matrix mode only: comma-separated panel names")
    parser.add_argument("--costs", default=",".join(str(c) for c in COSTS),
                        help="matrix mode only: comma-separated defect costs. The "
                             "default grid spans the whole declared range; a finer "
                             "grid is useful because the response is not linear")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.mode == "audit":
        report = audit_qd_defects(
            args.seed,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            verification=_panel_from_name(args.panel),
            defect=DefectChannel(cost=args.defect_cost),
        )
    else:
        panels = tuple(name.strip() for name in args.panels.split(",") if name.strip())
        unknown = [name for name in panels if name not in PANELS]
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
        )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
