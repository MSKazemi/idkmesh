#!/usr/bin/env python3
"""E017: is pairwise correlation a sufficient statistic for panel error?

E016 could not answer this, because its LLM verifiers did not discriminate.
This panel does: partial test oracles with measured accuracy around 0.80 and
measured pairwise error correlation, on the same 72-candidate corpus.

Having a panel that passes the discrimination screen makes three questions
answerable with real error vectors instead of a synthetic knob:

1. What IS the correlation between real verifiers, and does the declared
   independence label (input region) predict it?
2. Does the flat shared-shock mixture -- the model E012/E013/E015 all use,
   parameterised by ONE pairwise rho -- reproduce the real panel's error?
3. If not, does a nested model that also matches the block structure
   (within-region vs cross-region correlation) close the gap? If it does, the
   deficiency is in the flat model's single parameter, not in the shared-shock
   idea itself.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import itertools
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("e016_analyze", HERE / "e016_analyze.py")
e016 = importlib.util.module_from_spec(_spec)
sys.modules["e016_analyze"] = e016
_spec.loader.exec_module(e016)


def simulate_nested(n_per_block, n_blocks, acc, g, b, trials, seed=0):
    """Nested shared-shock: a global shock, else a per-block shock, else independent.

    Pairwise correlation implied by this model:
      cross-block  = g
      within-block = g + (1 - g) * b
    so it can match BOTH measured levels, where the flat model can match only
    their average.
    """
    rng = random.Random(seed)
    n = n_per_block * n_blocks
    need = n // 2 + 1
    wrong = 0
    for _ in range(trials):
        if rng.random() < g:
            correct = n if rng.random() < acc else 0
        else:
            correct = 0
            for _blk in range(n_blocks):
                if rng.random() < b:
                    correct += n_per_block if rng.random() < acc else 0
                else:
                    correct += sum(1 for _ in range(n_per_block) if rng.random() < acc)
        if correct < need:
            wrong += 1
    return wrong / trials


def simulate_flat(n, acc, rho, trials, seed=0):
    """The model E012/E013/E015 use: one shared shock with probability rho."""
    rng = random.Random(seed)
    need = n // 2 + 1
    wrong = 0
    for _ in range(trials):
        if rng.random() < rho:
            correct = n if rng.random() < acc else 0
        else:
            correct = sum(1 for _ in range(n) if rng.random() < acc)
        if correct < need:
            wrong += 1
    return wrong / trials


def fit_beta_binomial(counts, n):
    """Method-of-moments fit of a per-item difficulty distribution.

    Model: each task has its own difficulty d ~ Beta(alpha, beta), and given d
    every verifier errs independently with probability d. This has the same
    number of free parameters as the flat shared-shock model (a mean and a
    correlation), so the comparison between them is at equal parameter count --
    the difference is the SHAPE of the dependence, not extra freedom.

    Returns (alpha, beta, mu, icc); `icc` is the model's implied pairwise error
    correlation and should land near the measured rho.
    """
    m = statistics.mean(counts)
    v = statistics.pvariance(counts)
    mu = m / n
    if not 0 < mu < 1:
        return float("nan"), float("nan"), mu, float("nan")
    icc = ((v / (n * mu * (1 - mu))) - 1) / (n - 1)
    icc = min(max(icc, 1e-6), 0.999)
    scale = (1 - icc) / icc
    return mu * scale, (1 - mu) * scale, mu, icc


def _lbeta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def beta_binomial_pmf(k, n, alpha, beta):
    return math.exp(math.log(math.comb(n, k))
                    + _lbeta(k + alpha, n - k + beta) - _lbeta(alpha, beta))


def shared_shock_pmf(k, n, acc, rho):
    """P(exactly k of n verifiers err) under the flat shared-shock mixture."""
    shock = acc if k == 0 else ((1 - acc) if k == n else 0.0)
    indep = math.comb(n, k) * ((1 - acc) ** k) * (acc ** (n - k))
    return rho * shock + (1 - rho) * indep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("votes")
    ap.add_argument("--tasks", default="benchmarks/e016-verification-corpus/tasks.jsonl")
    ap.add_argument("--trials", type=int, default=200000)
    args = ap.parse_args()

    truth, votes, meta = e016.load(args.votes, args.tasks)
    agents = sorted(votes)
    tasks = sorted(set(truth).intersection(*[set(v) for v in votes.values()]))
    err = e016.error_vectors(truth, votes, tasks)
    accs = {a: 1 - sum(err[a]) / len(tasks) for a in agents}
    region = {a: meta[a][0] for a in agents}

    print("=" * 74)
    print("1. DISCRIMINATION SCREEN (the precondition E016 failed)")
    print("=" * 74)
    z = 2.85
    passed = []
    for a in agents:
        j, se = e016.youden_j(truth, votes[a], tasks)
        if j - z * se > 0:
            passed.append(a)
    print(f"  verifiers: {len(agents)}   discriminating above chance: {len(passed)}/{len(agents)}")
    print(f"  mean accuracy p = {statistics.mean(accs.values()):.4f}")
    if len(passed) < 3:
        print("  SCREEN FAILED -- correlation below would not be interpretable.")
        return 1

    print("\n" + "=" * 74)
    print("2. MEASURED CORRELATION, AND WHETHER THE DECLARED LABEL PREDICTS IT")
    print("=" * 74)
    within, between = [], []
    for a, b_ in itertools.combinations(agents, 2):
        r = e016.phi(err[a], err[b_])
        if r != r:
            continue
        (within if region[a] == region[b_] else between).append(r)
    mw, mb = statistics.mean(within), statistics.mean(between)
    allp = within + between
    ma = statistics.mean(allp)
    print(f"  same region (declared dependent)   n={len(within):3d}  mean rho={mw:+.4f}")
    print(f"  diff region (declared independent) n={len(between):3d}  mean rho={mb:+.4f}")
    print(f"  ALL PAIRS                          n={len(allp):3d}  mean rho={ma:+.4f}")
    print(f"  -> the label carries real signal ({mw:+.3f} vs {mb:+.3f}),")
    print(f"     but 'independent' verifiers still share {mb:.0%} of their errors.")

    print("\n" + "=" * 74)
    print("3. DOES A SINGLE PAIRWISE rho REPRODUCE THE REAL PANEL?")
    print("=" * 74)
    n = len(agents)
    need = n // 2 + 1
    # Accept-threshold semantics, matching a real quorum: the panel accepts
    # when at least `need` verifiers vote viable. For an odd panel this
    # coincides exactly with "a majority is correct", so the empirical number
    # and the analytic model measure the same quantity with no tie convention
    # left to choose.
    wrong = 0
    for i, t in enumerate(tasks):
        yes = sum(1 for a in agents if votes[a].get(t) is True)
        if (yes >= need) != truth[t]:
            wrong += 1
    real = wrong / len(tasks)
    if n % 2 == 0:
        print(f"  WARNING: even panel (n={n}); ties resolve toward reject and the "
              f"analytic model assumes symmetric majority. Use an odd panel.")
    acc = statistics.mean(accs.values())
    n_blocks = len(set(region.values()))
    per_block = n // n_blocks
    g = mb
    b = (mw - mb) / (1 - mb) if mb < 1 else 0.0
    flat = simulate_flat(n, acc, ma, args.trials, seed=1)
    nested = simulate_nested(per_block, n_blocks, acc, g, b, args.trials, seed=2)
    indep = e016.majority_error_independent(n, acc)
    print(f"  real {n}-verifier majority error         : {real:.4f}")
    print(f"  independent model (rho=0)                : {indep:.4f}")
    print(f"  FLAT shared-shock at mean rho={ma:.3f}      : {flat:.4f}")
    print(f"  NESTED shared-shock (g={g:.3f}, b={b:.3f})   : {nested:.4f}")
    print(f"  single verifier                          : {1-acc:.4f}")
    print()
    print(f"  flat model underestimates real error by  : {real-flat:+.4f} "
          f"({real/flat:.2f}x)" if flat else "")
    print(f"  nested model underestimates real error by: {real-nested:+.4f} "
          f"({real/nested:.2f}x)" if nested else "")

    print("\n" + "=" * 74)
    print("4. EFFECTIVE PANEL SIZE")
    print("=" * 74)
    eff = e016.effective_n(real, acc)
    heur = n / (1 + (n - 1) * ma)
    print(f"  nominal panel size                : {n}")
    print(f"  measured effective size           : {eff:.2f}")
    print(f"  N_eff heuristic N/(1+(N-1)rho)    : {heur:.2f}")
    print(f"  -> heuristic {'OVERSTATES' if heur > eff else 'understates'} real "
          f"independence by {max(heur,eff)/max(1e-9,min(heur,eff)):.2f}x")

    print("\n" + "=" * 74)
    print("5. WHERE THE SHARED-SHOCK MODEL PUTS ITS MASS, AND WHERE REALITY DOES")
    print("=" * 74)

    counts = [sum(err[a][i] for a in agents) for i in range(len(tasks))]
    alpha, beta_, mu, icc = fit_beta_binomial(counts, n)
    print(f"  beta-binomial fit: mu={mu:.4f}  implied pairwise rho={icc:.4f}  "
          f"(measured {ma:.4f})")
    obs = collections.Counter(counts)
    T = len(tasks)
    print(f"\n  {'k err':>6} {'observed':>9} {'beta-binom':>11} {'shared-shock':>13}")
    hard_o = hard_b = hard_s = 0
    for k in range(n + 1):
        o, bb, ss = obs.get(k, 0), beta_binomial_pmf(k, n, alpha, beta_) * T, \
                    shared_shock_pmf(k, n, acc, ma) * T
        if need <= k < n:
            hard_o += o; hard_b += bb; hard_s += ss
        if k in (0, 1, need, n - 1, n):
            print(f"  {k:6d} {o:9d} {bb:11.1f} {ss:13.1f}")
    print(f"  {'partial':>6} {hard_o:9d} {hard_b:11.1f} {hard_s:13.1f}"
          f"   <- panel failures short of unanimous")
    p_bb = sum(beta_binomial_pmf(k, n, alpha, beta_) for k in range(need, n + 1))
    print(f"\n  panel error   real={real:.4f}   beta-binomial={p_bb:.4f}   "
          f"flat shared-shock={flat:.4f}")
    print(f"  -> at equal parameter count, the item-difficulty shape is "
          f"{abs(flat-real)/max(1e-9,abs(p_bb-real)):.1f}x closer to reality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
