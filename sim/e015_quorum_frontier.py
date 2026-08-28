#!/usr/bin/env python3
"""Select the optimal verification quorum from an E015 grid.

E015's first sweep compared only two quorum levels, so it could report a
crossover between them but not an optimum. Given a grid with more quorum levels
this script reports, for each (panel size, accuracy, correlation) cell, the
quorum that minimises cost-weighted panel error.

Cost weighting follows `e015_analyze.effective_n_weighted`: a false accept is
`--cost` times as expensive as a false reject, so `--cost 1` is balanced error.

    python sim/e015_quorum_frontier.py results.jsonl.gz --cost 1 --cost 10
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import sys


def load(path: str) -> list:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def weighted_error(false_accept: float, false_reject: float, cost: float) -> float:
    return (cost * false_accept + false_reject) / (1.0 + cost)


def cells_by_config(rows: list, strategy: str) -> dict:
    """Map (verifiers, accuracy, correlation) -> {quorum: (fa, fr)}."""
    out = collections.defaultdict(dict)
    for row in rows:
        agg = row["aggregate"][strategy]
        key = (row["verifiers"], row["accuracy"], row["correlation"])
        out[key][row["quorum"]] = (
            agg["false_accept_rate"]["mean"],
            agg["false_reject_rate"]["mean"],
        )
    return out


def best_for_cost(quorum_map: dict, cost: float):
    """Return (quorum, error) minimising weighted error; ties go to the lower quorum."""
    scored = sorted(
        (weighted_error(fa, fr, cost), q) for q, (fa, fr) in quorum_map.items()
    )
    err, q = scored[0]
    return q, err


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", help="E015 raw JSONL (.jsonl or .jsonl.gz)")
    ap.add_argument("--cost", type=float, action="append", default=None,
                    help="false-accept cost relative to false reject (repeatable)")
    ap.add_argument("--strategy", default="qd", choices=("qd", "random", "scalar"))
    ap.add_argument("--detail", action="store_true",
                    help="print the per-cell winning quorum, not just the summary")
    args = ap.parse_args()
    costs = args.cost or [1.0]

    rows = load(args.raw)
    cells = cells_by_config(rows, args.strategy)
    quorums = sorted({row["quorum"] for row in rows})
    print(f"cells: {len(cells)}   quorum levels: {quorums}   strategy: {args.strategy}")
    if len(quorums) < 3:
        print("WARNING: fewer than 3 quorum levels — this reports a crossover, "
              "not an optimum.", file=sys.stderr)

    for cost in costs:
        wins = collections.Counter()
        interior = []
        for key in sorted(cells):
            qmap = cells[key]
            if len(qmap) < len(quorums):
                continue                      # incomplete cell: never guess
            q, err = best_for_cost(qmap, cost)
            wins[q] += 1
            if q != quorums[0]:
                interior.append((key, q, err))
            if args.detail:
                n, acc, rho = key
                print(f"  N={n:3d} p={acc:.2f} rho={rho:.3f}  best_quorum={q:.2f}  err={err:.5f}")
        total = sum(wins.values())
        print(f"\nfalse-accept cost = {cost:g}   ({total} complete cells)")
        for q in quorums:
            share = 100.0 * wins[q] / total if total else 0.0
            print(f"  quorum {q:.2f} wins {wins[q]:5d}  ({share:5.1f}%)")
        if interior:
            print(f"  cells preferring a stricter-than-lowest quorum: {len(interior)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
