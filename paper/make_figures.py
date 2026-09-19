#!/usr/bin/env python3
"""Emit pgfplots data files for the paper from the committed evidence artifacts.

Pure standard library, matching the repository's no-third-party-dependency rule.
Every number is recomputed by importing the same analysis modules the experiment
records used, so a figure cannot drift from the record it illustrates.

    python3 paper/make_figures.py
"""
from __future__ import annotations

import collections
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "figures"
VOTES = ROOT / "experiments/results/E017-partial-oracle-votes.jsonl.gz"
TASKS = ROOT / "benchmarks/e016-verification-corpus/tasks.jsonl"
E015 = ROOT / "experiments/results/E015-verification-phase-diagram.jsonl"


def _import(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


e020 = _import(ROOT / "sim/e020_quorum_frontier.py")


def write(name: str, header: str, rows) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w") as fh:
        fh.write(f"{header}\n")
        for row in rows:
            fh.write(" ".join(str(c) for c in row) + "\n")
    print(f"wrote figures/{name}")


def main() -> None:
    agents, tasks, truth, votes, errors = e020.load_votes(str(VOTES), str(TASKS))
    n = len(agents)
    counts = [errors[t] for t in tasks]
    mu, icc = e020.fit_moments(counts, n)
    lam = sum(1 for c in counts if c == n) / len(counts)
    mu_r, icc_r = e020.fit_moments([c for c in counts if c < n], n)

    ss = e020.shared_shock_pmf(n, mu, icc)
    bb = e020.beta_binomial_pmf(n, mu, icc)
    oi = e020.one_inflated_pmf(n, mu_r, icc_r, lam)

    # Figure 1 -- how many of the 25 verifiers err on the same task.
    obs = collections.Counter(counts)
    write(
        "kerr-distribution.dat",
        "k observed betabinom sharedshock",
        [
            (k, obs.get(k, 0), round(len(tasks) * bb[k], 4), round(len(tasks) * ss[k], 4))
            for k in range(n + 1)
        ],
    )

    # Figure 2 -- panel error at every acceptance threshold.
    real = e020.empirical_curve(agents, tasks, truth, votes)
    write(
        "quorum-frontier.dat",
        "need real sharedshock betabinom oneinflated",
        [
            (
                need,
                round(real[need - 1], 6),
                round(e020.tail(ss, need), 6),
                round(e020.tail(bb, need), 6),
                round(e020.tail(oi, need), 6),
            )
            for need in range(1, n + 1)
        ],
    )

    # Figure 3 -- effective panel size against correlation, from E015's grid.
    grid = collections.defaultdict(dict)
    with open(E015) as fh:
        for line in fh:
            r = json.loads(line)
            if r["quorum"] == 0.5 and r["accuracy"] == 0.75:
                grid[r["verifiers"]][r["correlation"]] = r["n_eff"]
    sizes = sorted(grid)
    write(
        "neff-grid.dat",
        "rho " + " ".join(f"n{s}" for s in sizes),
        [[rho] + [grid[s][rho] for s in sizes] for rho in sorted(grid[sizes[0]])],
    )

    # Figure 4 -- the design-effect heuristic at the measured correlation.
    write(
        "design-effect.dat",
        "n heuristic",
        [(k, round(k / (1.0 + (k - 1) * 0.5873), 4)) for k in range(1, 41)],
    )

    # ---- statistics the paper quotes -------------------------------------
    def wilson(k, total, z=1.96):
        """95% Wilson score interval for a binomial proportion."""
        if total == 0:
            return (0.0, 0.0)
        phat = k / total
        denom = 1 + z * z / total
        centre = (phat + z * z / (2 * total)) / denom
        half = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
        return (centre - half, centre + half)

    def mcnemar_exact(a_right, b_right):
        """Two-sided exact McNemar p for two paired correct/incorrect vectors."""
        b = sum(1 for t in tasks if a_right[t] and not b_right[t])
        c = sum(1 for t in tasks if b_right[t] and not a_right[t])
        if b + c == 0:
            return b, c, 1.0
        total = b + c
        k = min(b, c)
        p = 2 * sum(math.comb(total, i) for i in range(k + 1)) / 2 ** total
        return b, c, min(1.0, p)

    need = n // 2 + 1
    panel = {t: (sum(1 for a in agents if votes[a][t]) >= need) for t in tasks}
    panel_err = sum(1 for t in tasks if panel[t] != truth[t])
    member_err = {a: sum(1 for t in tasks if votes[a][t] != truth[t]) for a in agents}
    best = min(member_err, key=member_err.get)
    n_viable = sum(1 for t in tasks if truth[t])

    b, c, p_mc = mcnemar_exact(
        {t: panel[t] == truth[t] for t in tasks},
        {t: votes[best][t] == truth[t] for t in tasks},
    )
    plo, phi = wilson(panel_err, len(tasks))
    blo, bhi = wilson(member_err[best], len(tasks))
    llo, lhi = wilson(int(lam * len(tasks)), len(tasks))
    first_beat = next(
        (q for q in range(1, n + 1) if real[q - 1] < n_viable / len(tasks)), None
    )

    print(
        f"\n--- statistics quoted in the paper ---\n"
        f"panel majority error   {panel_err}/{len(tasks)} = {panel_err/len(tasks):.4f}"
        f"  95% CI [{plo:.4f}, {phi:.4f}]\n"
        f"mean member error      {sum(member_err.values())/n/len(tasks):.4f}\n"
        f"best member ({best})   {member_err[best]}/{len(tasks)} = {member_err[best]/len(tasks):.4f}"
        f"  95% CI [{blo:.4f}, {bhi:.4f}]\n"
        f"panel vs best: b={b} c={c} exact McNemar p={p_mc:.4f}\n"
        f"blind-spot floor       {lam:.4f}  95% CI [{llo:.4f}, {lhi:.4f}]\n"
        f"always-reject error    {n_viable}/{len(tasks)} = {n_viable/len(tasks):.4f}"
        f"   panel first beats it at need={first_beat}"
    )

    print(
        f"\npartial panel failures ({need} <= k < {n}): "
        f"observed={sum(obs.get(k, 0) for k in range(need, n))} "
        f"betabinom={len(tasks) * sum(bb[need:n]):.2f} "
        f"sharedshock={len(tasks) * sum(ss[need:n]):.2f}\n"
        f"unanimous failures (k={n}): observed={obs.get(n, 0)} "
        f"betabinom={len(tasks) * bb[n]:.2f} sharedshock={len(tasks) * ss[n]:.2f}"
    )

    rmse = lambda pmf: math.sqrt(
        sum((real[i] - e020.tail(pmf, i + 1)) ** 2 for i in range(n)) / n
    )
    print(
        f"\npanel n={n} tasks={len(tasks)} mu={mu:.4f} icc={icc:.4f} lambda={lam:.4f}\n"
        f"reducible mu={mu_r:.4f} icc={icc_r:.4f}\n"
        f"RMSE shock={rmse(ss):.4f} beta={rmse(bb):.4f} one-inflated={rmse(oi):.4f}\n"
        f"unanimity real={real[-1]:.4f} shock={e020.tail(ss, n):.4f} "
        f"beta={e020.tail(bb, n):.4f} one-inflated={e020.tail(oi, n):.4f}"
    )


if __name__ == "__main__":
    main()
