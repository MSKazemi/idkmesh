#!/usr/bin/env python3
"""E018: recompute E015's phase diagram under the dependence model E017 measured.

E012, E013 and E015 all model verifier dependence as a shared-shock mixture:
with probability `rho` every verifier shares one correctness state, otherwise
they are independent. E017 measured a real panel and found that shape wrong --
it assigns near-zero probability to a panel failing *partially*, which is how
most real panel failures actually look.

This module computes E015's grid under BOTH models in closed form, so the
question "which of E015's conclusions depend on the shape of the dependence
model?" can be answered exactly rather than by simulation noise.

Both models take the same two parameters (accuracy, correlation) and agree
exactly at correlation 0 and 1, so any difference between them is attributable
to shape alone.
"""

from __future__ import annotations

import argparse
import math
from itertools import product

VERIFIERS = (1, 3, 5, 7, 9, 11, 15, 21)
ACCURACY = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
CORRELATION = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)
# E015 swept quorum too, but this comparison is restricted to 0.5 on purpose.
# Both error functions here express "the panel is wrong when fewer than `need`
# verifiers are correct", which coincides with an accept-threshold rule only at
# a symmetric majority. Above 0.5 the two diverge (E017 hit exactly this on real
# data), and separating false accepts from false rejects needs the base rate of
# viable work, which is a property of the corpus rather than of the panel.
QUORUM = (0.5,)


def _lbeta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def beta_binomial_pmf(k, n, alpha, beta):
    return math.exp(math.log(math.comb(n, k))
                    + _lbeta(k + alpha, n - k + beta) - _lbeta(alpha, beta))


def independent_error(n, accuracy, quorum=0.5):
    """Panel error when every verifier is independent."""
    need = math.floor(quorum * n) + 1
    return sum(math.comb(n, k) * accuracy ** k * (1 - accuracy) ** (n - k)
               for k in range(0, need))


def shared_shock_error(n, accuracy, correlation, quorum=0.5):
    """The model E012/E013/E015 use. Validated against simulation in E015."""
    return correlation * (1 - accuracy) + \
        (1 - correlation) * independent_error(n, accuracy, quorum)


def item_difficulty_error(n, accuracy, correlation, quorum=0.5):
    """Beta-binomial: each task draws a difficulty, verifiers then err independently.

    Same two parameters as `shared_shock_error`, and identical to it at
    correlation 0 and 1. In between it spreads probability across partial panel
    failures instead of concentrating it on unanimity.
    """
    mu = 1 - accuracy
    if correlation <= 0.0:
        return independent_error(n, accuracy, quorum)
    if correlation >= 1.0 or mu <= 0.0 or mu >= 1.0:
        return mu
    scale = (1 - correlation) / correlation
    alpha, beta = mu * scale, (1 - mu) * scale
    need = math.floor(quorum * n) + 1
    # The panel is wrong when fewer than `need` verifiers are correct, i.e.
    # when at least n - need + 1 of them err.
    return sum(beta_binomial_pmf(k, n, alpha, beta)
               for k in range(n - need + 1, n + 1))


def effective_n(measured_error, accuracy, quorum=0.5, nmax=201):
    """Independent panel size that would produce `measured_error`."""
    if accuracy <= 0.5:
        return float("nan")
    sizes = [n for n in range(1, nmax, 2)]
    errs = [independent_error(n, accuracy, quorum) for n in sizes]
    if measured_error >= errs[0]:
        return 1.0
    if measured_error <= errs[-1]:
        return float(sizes[-1])
    for i in range(len(sizes) - 1):
        hi, lo = errs[i], errs[i + 1]
        if lo <= measured_error <= hi:
            if hi == lo:
                return float(sizes[i])
            return sizes[i] + (hi - measured_error) / (hi - lo) * 2
    return float("nan")


def heuristic_effective_n(n, correlation):
    return n / (1 + (n - 1) * correlation)


def grid():
    """Every comparable cell of E015's grid under both models."""
    for n, acc, rho, q in product(VERIFIERS, ACCURACY, CORRELATION, QUORUM):
        # `need` correct is only the accept threshold at a symmetric majority.
        assert abs(q - 0.5) < 1e-9, "asymmetric quorums need a base rate; see QUORUM"
        if n == 1 or rho in (0.0, 1.0):
            continue          # the models coincide here by construction
        shock = shared_shock_error(n, acc, rho, q)
        item = item_difficulty_error(n, acc, rho, q)
        yield {
            "verifiers": n, "accuracy": acc, "correlation": rho, "quorum": q,
            "shared_shock_error": shock,
            "item_difficulty_error": item,
            "eff_shared_shock": effective_n(shock, acc, q),
            "eff_item_difficulty": effective_n(item, acc, q),
            "heuristic": heuristic_effective_n(n, rho),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quorum", type=float, default=0.5,
                    help="only 0.5 is modelled; see the QUORUM comment")
    args = ap.parse_args()

    cells = [c for c in grid() if abs(c["quorum"] - args.quorum) < 1e-9]
    usable = [c for c in cells if c["eff_shared_shock"] == c["eff_shared_shock"]
              and c["eff_item_difficulty"] == c["eff_item_difficulty"]]

    print(f"E015 grid at quorum={args.quorum}: {len(cells)} comparable cells "
          f"({len(usable)} with a defined effective size)\n")

    worse = sum(1 for c in usable
                if c["item_difficulty_error"] > c["shared_shock_error"])
    print("1. DOES THE SHAPE CHANGE THE PREDICTED PANEL ERROR?")
    print(f"   item-difficulty predicts MORE error than shared-shock in "
          f"{worse}/{len(usable)} cells ({100*worse/len(usable):.0f}%)")
    ratios = sorted(c["item_difficulty_error"] / c["shared_shock_error"]
                    for c in usable if c["shared_shock_error"] > 0)
    print(f"   error ratio (item/shock): median {ratios[len(ratios)//2]:.2f}x, "
          f"max {ratios[-1]:.2f}x")

    print("\n2. DOES E015'S N_eff WARNING SURVIVE?")
    for name, key in (("shared-shock", "eff_shared_shock"),
                      ("item-difficulty", "eff_item_difficulty")):
        over = sum(1 for c in usable if c["heuristic"] > c[key])
        print(f"   under {name:16s}: heuristic OVERSTATES independence in "
              f"{over:4d}/{len(usable)} cells ({100*over/len(usable):3.0f}%)")
    print("   -> E015 stated the heuristic is optimistic FOR ACCURATE VERIFIERS.")

    print("\n3. DOES THE ACCURACY-DEPENDENT CEILING SURVIVE?")
    print("   (effective size as the panel grows, at quorum 0.5)")
    for acc in (0.75, 0.90):
        for rho in (0.125, 0.5):
            row = [c for c in usable
                   if abs(c["accuracy"] - acc) < 1e-9
                   and abs(c["correlation"] - rho) < 1e-9]
            row.sort(key=lambda c: c["verifiers"])
            ss = ", ".join(f"{c['eff_shared_shock']:.1f}" for c in row)
            it = ", ".join(f"{c['eff_item_difficulty']:.1f}" for c in row)
            ns = ", ".join(str(c["verifiers"]) for c in row)
            print(f"   p={acc} rho={rho}  n=[{ns}]")
            print(f"      shared-shock   : [{ss}]")
            print(f"      item-difficulty: [{it}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
