#!/usr/bin/env python3
"""E015 - verification phase diagram for IDKMesh.

Sweeps the verifier panel configuration space (panel size x per-verifier accuracy
x error correlation x quorum) and measures the resulting aggregate error rates.

The headline derived quantity is the EFFECTIVE INDEPENDENT PANEL SIZE: the number
of statistically independent verifiers that would produce the same false-accept
rate as the measured correlated panel. This turns E012's qualitative claim
("reviewer count is not independent evidence count") into a number.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import time
from itertools import product
from multiprocessing import Pool
from pathlib import Path
from statistics import mean, stdev

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("emergence_sim", HERE / "emergence_sim.py")
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
spec.loader.exec_module(sim)

def _axis(env, default):
    raw = os.environ.get(env)
    return tuple(float(x) for x in raw.split(",")) if raw else default

VERIFIERS = tuple(int(v) for v in _axis("E015_VERIFIERS", (1, 3, 5, 7, 9, 11, 15, 21)))
ACCURACY = _axis("E015_ACCURACY", (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95))
CORRELATION = _axis("E015_CORRELATION", (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0))
QUORUM = _axis("E015_QUORUM", (0.5, 0.6, 0.7, 0.8))

AGENTS = 100
GENERATIONS = 60
CHANGE_AT = 30
BINS = 8

METRICS = ("false_accept_rate", "false_reject_rate", "panel_disagreement_rate",
           "final_best", "post_change_mean")


def stats(values):
    n = len(values)
    if n == 0:
        return None
    mu = mean(values)
    sd = stdev(values) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n else 0.0
    return {"n": n, "mean": round(mu, 6), "stdev": round(sd, 6),
            "ci95_low": round(mu - half, 6), "ci95_high": round(mu + half, 6)}


def cell(task):
    """Run all seeds for one (verifiers, accuracy, correlation, quorum) cell."""
    v, a, c, q, seeds, seed_start = task
    acc = {}
    for s in range(seed_start, seed_start + seeds):
        out = sim.run("all", s, AGENTS, GENERATIONS, CHANGE_AT, BINS,
                      verifiers=v, verifier_accuracy=a,
                      verifier_correlation=c, verification_quorum=q)
        for r in out["results"]:
            d = acc.setdefault(r["strategy"], {m: [] for m in METRICS})
            for m in METRICS:
                if m in r:
                    d[m].append(float(r[m]))
    return {"verifiers": v, "accuracy": a, "correlation": c, "quorum": q,
            "seeds": seeds, "seed_start": seed_start,
            "aggregate": {k: {m: stats(vals) for m, vals in d.items() if vals}
                          for k, d in acc.items()}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=400)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--shards", type=int, default=1)
    p.add_argument("--procs", type=int, default=os.cpu_count())
    p.add_argument("--out", required=True)
    args = p.parse_args()

    grid = [(v, a, c, q, args.seeds, args.seed_start)
            for v, a, c, q in product(VERIFIERS, ACCURACY, CORRELATION, QUORUM)]
    mine = [t for i, t in enumerate(grid) if i % args.shards == args.shard]

    t0 = time.time()
    done = 0
    with open(args.out, "w") as fh, Pool(args.procs) as pool:
        for rec in pool.imap_unordered(cell, mine, chunksize=1):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            done += 1
            if done % 25 == 0:
                el = time.time() - t0
                print(f"{done}/{len(mine)} cells  {el:.0f}s  eta {el/done*(len(mine)-done):.0f}s",
                      flush=True)
    print(f"DONE {done}/{len(mine)} cells in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
