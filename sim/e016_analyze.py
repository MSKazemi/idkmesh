#!/usr/bin/env python3
"""Measure real verifier error correlation and test the E015 predictions.

E012/E013/E015 all state the same limitation: error correlation `rho` is a knob
set inside a synthetic shared-shock mixture, never measured. This reads the
verdicts of real open-weight LLM verifiers on a corpus with executable ground
truth and asks three questions.

1. What IS the pairwise error correlation between real verifiers, and does it
   decompose along the axes ADR-0008 hypothesises (model family, prompt)?
2. Does the shared-shock mixture, fed the MEASURED rho, predict the panel error
   that the real panel actually produces?
3. Do the E015 conclusions -- the N_eff heuristic being optimistic, and the
   accuracy-dependent ceiling -- hold for real verifiers?
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
from math import comb


def load(votes_path: str, tasks_path: str):
    truth = {}
    for line in open(tasks_path):
        t = json.loads(line)
        truth[t["task_id"]] = t["viable"]
    votes = collections.defaultdict(dict)   # agent -> task -> verdict
    meta = {}
    for line in open(votes_path):
        v = json.loads(line)
        votes[v["agent_id"]][v["task_id"]] = v["verdict"]
        meta[v["agent_id"]] = (v["model"], v["template"])
    return truth, votes, meta


def error_vectors(truth, votes, tasks, unparseable_is_error=True):
    """agent -> [1 if wrong else 0] aligned on `tasks`."""
    out = {}
    for a, tv in votes.items():
        vec = []
        for t in tasks:
            v = tv.get(t)
            if v is None:
                vec.append(1 if unparseable_is_error else None)
            else:
                vec.append(0 if v == truth[t] else 1)
        out[a] = vec
    return out


def phi(x, y):
    """Correlation between two binary vectors (Pearson == phi here)."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    num = sum((a - mx) * (b - my) for a, b in pairs)
    dx = math.sqrt(sum((a - mx) ** 2 for a, _ in pairs))
    dy = math.sqrt(sum((b - my) ** 2 for _, b in pairs))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def majority_error_independent(n, acc, quorum=0.5):
    need = math.floor(quorum * n) + 1
    return sum(comb(n, k) * acc**k * (1 - acc) ** (n - k) for k in range(0, need))


def effective_n(measured_err, acc, nmax=201):
    if acc <= 0.5:
        return float("nan")
    sizes = [n for n in range(1, nmax, 2)]
    errs = [majority_error_independent(n, acc) for n in sizes]
    if measured_err >= errs[0]:
        return 1.0
    if measured_err <= errs[-1]:
        return float(sizes[-1])
    for i in range(len(sizes) - 1):
        hi, lo = errs[i], errs[i + 1]
        if lo <= measured_err <= hi:
            if hi == lo:
                return float(sizes[i])
            return sizes[i] + (hi - measured_err) / (hi - lo) * 2
    return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("votes")
    ap.add_argument("--tasks", default="benchmarks/e016-verification-corpus/tasks.jsonl")
    args = ap.parse_args()

    truth, votes, meta = load(args.votes, args.tasks)
    agents = sorted(votes)
    tasks = sorted(truth)
    print(f"agents: {len(agents)}   tasks: {len(tasks)}")

    total = sum(len(v) for v in votes.values())
    unparse = sum(1 for a in agents for t in tasks if votes[a].get(t) is None)
    print(f"votes recorded: {total}   missing/unparseable: {unparse} "
          f"({100.0*unparse/max(1,len(agents)*len(tasks)):.1f}%)")

    err = error_vectors(truth, votes, tasks)

    print("\n" + "=" * 74)
    print("1. PER-AGENT ACCURACY")
    print("=" * 74)
    accs = {}
    for a in agents:
        acc = 1 - sum(err[a]) / len(tasks)
        accs[a] = acc
        m, tp = meta[a]
        print(f"  {a:10s} {m:14s} {tp:12s} accuracy={acc:.3f}")
    mean_acc = sum(accs.values()) / len(accs)
    print(f"  mean accuracy p = {mean_acc:.4f}")

    print("\n" + "=" * 74)
    print("2. PAIRWISE ERROR CORRELATION, DECOMPOSED BY SHARED ATTRIBUTE")
    print("=" * 74)
    groups = collections.defaultdict(list)
    allr = []
    for a, b in itertools.combinations(agents, 2):
        r = phi(err[a], err[b])
        if r is None:
            continue
        allr.append(r)
        same_model = meta[a][0] == meta[b][0]
        same_tmpl = meta[a][1] == meta[b][1]
        key = ("same model" if same_model else "diff model") + " / " + \
              ("same prompt" if same_tmpl else "diff prompt")
        groups[key].append(r)
    for key in sorted(groups):
        v = sorted(groups[key])
        mean = sum(v) / len(v)
        print(f"  {key:28s} n={len(v):4d}  mean rho={mean:+.4f}  "
              f"median={v[len(v)//2]:+.4f}  range=[{v[0]:+.3f},{v[-1]:+.3f}]")
    mean_rho = sum(allr) / len(allr)
    print(f"  {'ALL PAIRS':28s} n={len(allr):4d}  mean rho={mean_rho:+.4f}")

    print("\n" + "=" * 74)
    print("3. DOES THE SHARED-SHOCK MODEL PREDICT THE REAL PANEL?")
    print("=" * 74)
    n = len(agents)
    need = n // 2 + 1
    wrong = 0
    for i, t in enumerate(tasks):
        yes = sum(1 for a in agents if votes[a].get(t) is True)
        decided = yes >= need
        if decided != truth[t]:
            wrong += 1
    measured_panel_err = wrong / len(tasks)
    pred = mean_rho * (1 - mean_acc) + (1 - mean_rho) * \
        majority_error_independent(n, mean_acc)
    print(f"  real {n}-verifier majority error : {measured_panel_err:.4f}")
    print(f"  shared-shock prediction at measured p and rho : {pred:.4f}")
    print(f"  independent-panel prediction (rho=0)          : "
          f"{majority_error_independent(n, mean_acc):.4f}")
    print(f"  single verifier                               : {1-mean_acc:.4f}")

    print("\n" + "=" * 74)
    print("4. EFFECTIVE PANEL SIZE: REAL vs HEURISTIC vs E015 CEILING")
    print("=" * 74)
    n_eff = effective_n(measured_panel_err, mean_acc)
    heur = n / (1 + (n - 1) * mean_rho) if mean_rho > 0 else float(n)
    ceiling = effective_n(mean_rho * (1 - mean_acc), mean_acc) if mean_rho > 0 else float("inf")
    print(f"  nominal panel size            : {n}")
    print(f"  measured effective size       : {n_eff:.2f}")
    print(f"  N_eff heuristic N/(1+(N-1)rho): {heur:.2f}")
    print(f"  E015 ceiling at measured p,rho: {ceiling:.2f}")
    if heur > n_eff:
        print(f"  -> heuristic OVERSTATES real independence by {heur/n_eff:.2f}x")
    else:
        print(f"  -> heuristic understates real independence by {n_eff/heur:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
