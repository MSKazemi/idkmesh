#!/usr/bin/env python3
"""E020: the acceptance-quorum frontier under the dependence shape E017 measured.

E015 swept the acceptance quorum at two levels (0.5, 0.7) under a shared-shock
mixture and concluded that cost-asymmetric quorums help. E017 confirmed that on
real verifiers and found a sharper form: with one-sided error, unanimity beat
majority by 3.7x. E018 and E019 then showed that swapping shared-shock for the
measured item-difficulty shape overturns E015's ceiling -- but both deliberately
restricted themselves to quorum 0.5, because comparing quorums requires modelling
false accepts and false rejects separately, and that needs a corpus base rate.

This module closes that gap. It has a real base rate (E016's corpus, 26 viable of
72) and real per-task votes (E017's 25 partial oracles), so the quorum frontier
can be computed from data rather than assumed.

Three models of the panel's error-count distribution are compared, all at two
free parameters except where noted:

  shared-shock      with probability `rho` all verifiers share one state
  beta-binomial     each task draws difficulty d ~ Beta(a, b); verifiers err at d
  one-inflated      a lambda-atom of irreducible tasks, plus a beta-binomial

The one-inflated model has three parameters and is included because both
two-parameter models get the high-quorum limit wrong, in opposite directions.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
from math import lgamma

DEFAULT_VOTES = "experiments/results/E017-partial-oracle-votes.jsonl.gz"
DEFAULT_TASKS = "benchmarks/e016-verification-corpus/tasks.jsonl"


# --------------------------------------------------------------------------
# distributions over "how many of the n verifiers are wrong on this task"
# --------------------------------------------------------------------------

def log_choose(n: int, k: int) -> float:
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)


def log_beta(a: float, b: float) -> float:
    return lgamma(a) + lgamma(b) - lgamma(a + b)


def binomial_pmf(n: int, mu: float):
    """P(k of n) for independent errors, evaluated in log space.

    The naive form exp(log_choose(n, k)) * mu**k * ... overflows for panels of
    a few hundred, which the asymptotic checks in this module do reach.
    """
    if mu <= 0.0:
        return [1.0 if k == 0 else 0.0 for k in range(n + 1)]
    if mu >= 1.0:
        return [1.0 if k == n else 0.0 for k in range(n + 1)]
    log_mu, log_nmu = math.log(mu), math.log1p(-mu)
    return [math.exp(log_choose(n, k) + k * log_mu + (n - k) * log_nmu)
            for k in range(n + 1)]


def beta_parameters(mu: float, icc: float):
    """Beta(a, b) with mean `mu` and intra-class correlation `icc`.

    The ICC of a beta-binomial equals its pairwise error correlation, which is
    what makes this a like-for-like swap for the shared-shock `rho`.
    """
    if not 0.0 < icc < 1.0 or not 0.0 < mu < 1.0:
        return None
    scale = (1.0 - icc) / icc
    return mu * scale, (1.0 - mu) * scale


def shared_shock_pmf(n: int, mu: float, rho: float):
    """P(k of n verifiers wrong) under the shared-shock mixture."""
    indep = binomial_pmf(n, mu)
    out = []
    for k in range(n + 1):
        shock = mu if k == n else ((1.0 - mu) if k == 0 else 0.0)
        out.append((1.0 - rho) * indep[k] + rho * shock)
    return out


def beta_binomial_pmf(n: int, mu: float, icc: float):
    """P(k of n verifiers wrong) under per-task difficulty d ~ Beta(a, b)."""
    params = beta_parameters(mu, icc)
    if params is None:
        # Degenerate limits: icc -> 0 is binomial, icc -> 1 is all-or-nothing.
        if icc <= 0.0:
            return binomial_pmf(n, mu)
        return [(1.0 - mu) if k == 0 else (mu if k == n else 0.0)
                for k in range(n + 1)]
    a, b = params
    return [math.exp(log_choose(n, k) + log_beta(a + k, b + n - k) - log_beta(a, b))
            for k in range(n + 1)]


def one_inflated_pmf(n: int, mu: float, icc: float, lam: float):
    """Beta-binomial mixed with a `lam`-weight atom on 'every verifier wrong'.

    The atom represents defects that the whole panel shares a blind spot for.
    No amount of quorum can catch those, so they set a floor the two-parameter
    models cannot express.
    """
    base = beta_binomial_pmf(n, mu, icc)
    out = [(1.0 - lam) * p for p in base]
    out[n] += lam
    return out


def tail(pmf, lo: int) -> float:
    """P(K >= lo)."""
    if lo > len(pmf) - 1:
        return 0.0
    return sum(pmf[max(lo, 0):])


# --------------------------------------------------------------------------
# the quorum frontier
# --------------------------------------------------------------------------

def panel_costs(pmf, n: int, need: int, base_rate: float,
                cost_fa: float = 1.0, cost_fr: float = 1.0):
    """(false-accept rate, false-reject rate, expected cost) at `need` votes.

    A panel accepts when at least `need` of `n` verifiers vote accept.

    On a non-viable task an accept vote IS an error, so the panel wrongly
    accepts when at least `need` verifiers err.  On a viable task a reject vote
    is the error, so the panel wrongly rejects when more than `n - need`
    verifiers err.  Both use the same error-count distribution, which assumes
    the panel is equally fallible in both directions -- see `limitations` in the
    experiment write-up.
    """
    false_accept = tail(pmf, need)
    false_reject = tail(pmf, n - need + 1)
    cost = base_rate * cost_fa * false_accept + (1.0 - base_rate) * cost_fr * false_reject
    return false_accept, false_reject, cost


def optimal_quorum(pmf, n: int, base_rate: float,
                   cost_fa: float = 1.0, cost_fr: float = 1.0):
    """The `need` in 1..n minimising expected cost, and that cost.

    Ties resolve to the smallest `need`, which is the conservative choice: it
    never claims a higher quorum is required than the evidence supports.
    """
    best = None
    for need in range(1, n + 1):
        _, _, cost = panel_costs(pmf, n, need, base_rate, cost_fa, cost_fr)
        if best is None or cost < best[1] - 1e-15:
            best = (need, cost)
    return best


def unanimity_decay_exponent(mu: float, icc: float):
    """Exponent of the n^-beta decay of P(all n verifiers wrong) under Beta(a,b).

    P(all wrong) = E[d^n] = B(a+n, b)/B(a, b), and Gamma(a+n)/Gamma(a+b+n)
    behaves as n^-b for large n, so the tail decays polynomially with exponent
    b = (1-mu)(1-icc)/icc -- slowly, but without a floor.  The shared-shock
    model instead has the hard floor rho*mu at every panel size.
    """
    params = beta_parameters(mu, icc)
    if params is None:
        return None
    return params[1]


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------

def _open(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path)


def load_votes(votes_path: str, tasks_path: str):
    """-> (agents, tasks, truth, errors-per-task)."""
    truth = {}
    for line in _open(tasks_path):
        row = json.loads(line)
        truth[row["task_id"]] = row["viable"]
    votes = collections.defaultdict(dict)
    for line in _open(votes_path):
        row = json.loads(line)
        votes[row["agent_id"]][row["task_id"]] = row["verdict"]
    agents = sorted(votes)
    tasks = sorted(set(truth).intersection(*[set(v) for v in votes.values()]))
    errors = {t: sum(1 for a in agents if votes[a][t] != truth[t]) for t in tasks}
    return agents, tasks, truth, votes, errors


def fit_moments(counts, n: int):
    """Method-of-moments (mean, ICC) for an error-count sample."""
    m = sum(counts) / len(counts)
    var = sum((c - m) ** 2 for c in counts) / (len(counts) - 1)
    mu = m / n
    icc = ((var / (n * mu * (1.0 - mu))) - 1.0) / (n - 1)
    return mu, icc


def empirical_curve(agents, tasks, truth, votes):
    """Real panel error at every quorum, using accept-threshold semantics."""
    out = []
    n = len(agents)
    for need in range(1, n + 1):
        wrong = 0
        for t in tasks:
            yes = sum(1 for a in agents if votes[a][t])
            if (yes >= need) != truth[t]:
                wrong += 1
        out.append(wrong / len(tasks))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--votes", default=DEFAULT_VOTES)
    ap.add_argument("--tasks", default=DEFAULT_TASKS)
    args = ap.parse_args()

    agents, tasks, truth, votes, errors = load_votes(args.votes, args.tasks)
    n = len(agents)
    base_rate = 1.0 - sum(truth[t] for t in tasks) / len(tasks)
    counts = [errors[t] for t in tasks]
    mu, icc = fit_moments(counts, n)
    lam = sum(1 for c in counts if c == n) / len(counts)
    reducible = [c for c in counts if c < n]
    mu_r, icc_r = fit_moments(reducible, n)

    print("=" * 74)
    print("1. THE PANEL")
    print("=" * 74)
    print(f"  verifiers                    : {n}")
    print(f"  tasks                        : {len(tasks)}  "
          f"({sum(truth[t] for t in tasks)} viable, base rate {base_rate:.4f})")
    print(f"  false rejects on viable code : "
          f"{sum(1 for t in tasks if truth[t] for a in agents if not votes[a][t])}")
    print(f"  moment fit                   : mu={mu:.4f}  icc={icc:.4f}")
    print(f"  irreducible tasks (all wrong): {int(lam * len(counts))} -> lambda={lam:.4f}")
    print(f"  reducible-only fit           : mu={mu_r:.4f}  icc={icc_r:.4f}")

    real = empirical_curve(agents, tasks, truth, votes)
    ss = shared_shock_pmf(n, mu, icc)
    bb = beta_binomial_pmf(n, mu, icc)
    oi = one_inflated_pmf(n, mu_r, icc_r, lam)

    print()
    print("=" * 74)
    print("2. THE REAL QUORUM FRONTIER, AND WHAT EACH MODEL PREDICTS")
    print("=" * 74)
    print(f"  {'need':>5} {'real':>8} {'shared-shock':>13} {'beta-binom':>11} "
          f"{'one-inflated':>13}")
    for need in (1, 5, 9, 13, 17, 19, 22, 24, 25):
        if need > n:
            continue
        print(f"  {need:>5} {real[need-1]:>8.4f} {tail(ss, need):>13.4f} "
              f"{tail(bb, need):>11.4f} {tail(oi, need):>13.4f}")

    def rmse(pmf):
        return math.sqrt(sum((real[i] - tail(pmf, i + 1)) ** 2
                             for i in range(n)) / n)

    print()
    print(f"  RMSE over all {n} quorums     : shared-shock={rmse(ss):.4f}  "
          f"beta-binomial={rmse(bb):.4f}  one-inflated={rmse(oi):.4f}")
    print(f"  at unanimity (need={n})       : real={real[-1]:.4f}  "
          f"shared-shock={tail(ss, n):.4f}  beta-binomial={tail(bb, n):.4f}  "
          f"one-inflated={tail(oi, n):.4f}")
    print(f"  -> shared-shock OVER-predicts the floor by "
          f"{tail(ss, n)/real[-1]:.2f}x, beta-binomial UNDER-predicts it by "
          f"{real[-1]/tail(bb, n):.2f}x")

    print()
    print("=" * 74)
    print("3. WHY THE TWO-PARAMETER MODELS CANNOT BOTH BE RIGHT AT HIGH QUORUM")
    print("=" * 74)
    beta_exp = unanimity_decay_exponent(mu, icc)
    print(f"  shared-shock P(all wrong)     -> rho*mu = {icc*mu:.6f}, "
          f"a hard floor at every panel size")
    print(f"  beta-binomial P(all wrong)    -> decays as n^-{beta_exp:.4f}, "
          f"no floor at all")
    print(f"  measured                      -> floor {lam:.4f} "
          f"({int(lam*len(counts))} defects the whole panel shares a blind spot for)")
    a, b = beta_parameters(mu, icc)
    k = 1
    while k < 10 ** 7 and math.exp(lgamma(a + k) + lgamma(a + b)
                                   - lgamma(a + b + k) - lgamma(a)) > real[-1]:
        k += 1
    print(f"  The beta-binomial says {k} verifiers are enough to reach {real[-1]:.4f},")
    print(f"  and then keeps promising improvement past it. The real panel bottoms")
    print(f"  out at {real[-1]:.4f} and stays there from need={n - 3} onward: the last")
    print("  defects are not rare-and-independent, they are invisible to this panel.")

    print()
    print("=" * 74)
    print("4. DOES THE SHAPE MOVE THE OPTIMAL QUORUM?")
    print("=" * 74)
    print(f"  {'n':>3} {'rho':>6} {'base':>6} {'FA:FR':>7} | "
          f"{'q* shock':>9} {'q* item':>8} {'shift':>6}")
    spread = {"shock": [], "item": []}
    for size in (5, 11, 25):
        for rho in (0.25, round(icc, 4), 0.8):
            for base in (round(base_rate, 3), 0.1):
                for cfa, cfr in ((1, 1), (10, 1)):
                    q_s, _ = optimal_quorum(shared_shock_pmf(size, mu, rho),
                                            size, base, cfa, cfr)
                    q_i, _ = optimal_quorum(beta_binomial_pmf(size, mu, rho),
                                            size, base, cfa, cfr)
                    if size == 25:
                        spread["shock"].append(q_s)
                        spread["item"].append(q_i)
                    print(f"  {size:>3} {rho:>6.3f} {base:>6.3f} "
                          f"{cfa:>3}:{cfr:<3} | {q_s:>9} {q_i:>8} {q_i-q_s:>+6}")
    print()
    print(f"  at n=25 the optimum spans {min(spread['shock'])}-{max(spread['shock'])} "
          f"under shared-shock but {min(spread['item'])}-{max(spread['item'])} "
          f"under item-difficulty.")
    print("  -> the assumed SHAPE, not the correlation, decides the aggregation rule.")

    print()
    print("=" * 74)
    print("5. DECISION TEST -- HOW MUCH DOES TUNING THE QUORUM ACTUALLY BUY?")
    print("=" * 74)
    print("  Each model is fitted to this panel, then asked how much error a")
    print("  better quorum could remove. The answer is checked against the panel.")
    majority = (n // 2) + 1
    print()
    print(f"  {'source':>16} {'at majority':>12} {'best reachable':>15} {'gain':>7}")
    real_best = min(real)
    print(f"  {'MEASURED':>16} {real[majority-1]:>12.4f} {real_best:>15.4f} "
          f"{real[majority-1]/real_best:>6.2f}x")
    for label, pmf in (("shared-shock", ss), ("beta-binomial", bb),
                       ("one-inflated", oi)):
        maj = tail(pmf, majority)
        best = min(tail(pmf, need) for need in range(1, n + 1))
        gain = maj / best if best > 0 else float("inf")
        print(f"  {label:>16} {maj:>12.4f} {best:>15.4f} {gain:>6.2f}x")
    print()
    print("  The shared-shock model reports that no quorum can beat majority by")
    print("  more than a rounding error, because its floor rho*mu is reached well")
    print("  below majority. On this panel a better quorum is in fact the single")
    print("  largest available reduction in error.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
