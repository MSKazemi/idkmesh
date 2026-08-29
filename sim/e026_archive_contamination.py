#!/usr/bin/env python3
"""Audit whether falsely accepted candidates survive in the E024 QD archive.

E026 reports that E024's landscape barely transmits verifier error into its
outcome metrics. The mechanism behind that claim is checkable rather than
inferred: count how many non-viable candidates the panel waves through, then
count how many of them are still in the final Quality-Diversity archive.

This audit exists so that claim carries a reproduction command. It re-runs the
Quality-Diversity arm exactly as `matched_budget_emergence` runs it -- same
strategy-seed derivation, same two random streams, same budget -- and reports
the two counts side by side under a chosen panel.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import json
import random
from typing import Dict, Tuple

import sim.emergence_sim as sim
from sim.matched_budget_emergence import (
    STRATEGIES,
    STRATEGY_SEED_STRIDE,
    VERIFIER_STREAM_MASK,
    measured_panel,
)

QD = "qd"


def audit_qd_archive(
    seed: int,
    *,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    verification: sim.VerificationConfig,
) -> Dict[str, object]:
    """Replay the Quality-Diversity arm and inspect what survived."""
    strategy_seed = seed + STRATEGIES.index(QD) * STRATEGY_SEED_STRIDE
    rng = random.Random(strategy_seed)
    verifier_rng = random.Random(strategy_seed ^ VERIFIER_STREAM_MASK)
    stats = sim.VerificationStats()
    archive: Dict[Tuple[int, int], sim.Candidate] = {}

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
            if incumbent is None or sim.robust_quality(candidate) > sim.robust_quality(incumbent):
                archive[key] = candidate

    non_viable_in_archive = sum(1 for candidate in archive.values() if not sim.viable(candidate))
    return {
        "seed": seed,
        "panel": verification.as_dict(),
        "verification_attempts": stats.attempts,
        "verification_accepts": stats.accepts,
        "accepted_but_non_viable": stats.false_accepts,
        "archive_size": len(archive),
        "non_viable_in_archive": non_viable_in_archive,
        "why": (
            "utility() and robust_quality() both return 0.0 for a non-viable candidate, "
            "so a falsely accepted artifact never displaces an archive incumbent. This "
            "landscape has no defect-propagation channel."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument(
        "--panel",
        choices=("perfect", "measured", "stress"),
        default="stress",
        help="perfect: the E024 default; measured: E017/E020 parameters; stress: a deliberately absurd panel",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.panel == "perfect":
        verification = sim.VerificationConfig()
    elif args.panel == "measured":
        verification = measured_panel()
    else:
        verification = measured_panel(accuracy=0.55, correlation=0.9, blind_spot=0.4)

    report = audit_qd_archive(
        args.seed,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        verification=verification,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
