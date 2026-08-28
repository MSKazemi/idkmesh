#!/usr/bin/env python3
"""Analyze the E015 verification phase diagram.

Derives the EFFECTIVE INDEPENDENT PANEL SIZE n_eff: the number of independent
verifiers whose majority vote would produce the measured false-accept rate.
An n-member panel with correlated errors is worth n_eff independent members.
"""
from __future__ import annotations
import gzip, json, math, sys
from collections import defaultdict
from pathlib import Path
from math import comb


def majority_error_independent(n: int, acc: float, quorum: float) -> float:
    """P(majority of n independent verifiers, each correct w.p. acc, is wrong)."""
    need = math.floor(quorum * n) + 1          # votes required to accept
    # error = P(fewer than `need` correct)  -> panel rejects a good item, and
    # symmetrically accepts a bad one; with symmetric accuracy this is the
    # same binomial tail.
    p_wrong = 0.0
    for k in range(0, need):
        p_wrong += comb(n, k) * (acc ** k) * ((1 - acc) ** (n - k))
    return p_wrong


def balanced_error_independent(n: int, acc: float, quorum: float) -> float:
    """Mean of the two error types for an independent panel.

    `majority_error_independent` is the false-reject tail. The false-accept tail
    is its mirror: a non-viable item is accepted when at least `need` verifiers
    are *wrong*, which happens with per-verifier probability `1 - acc`.

    At `quorum = 0.5` the two coincide. Above it they diverge sharply, which is
    exactly why a one-sided metric cannot compare quorums.
    """
    need = math.floor(quorum * n) + 1
    false_reject = majority_error_independent(n, acc, quorum)
    false_accept = sum(
        comb(n, k) * ((1 - acc) ** k) * (acc ** (n - k))
        for k in range(need, n + 1)
    )
    return (false_accept + false_reject) / 2.0


def effective_n_balanced(measured_false_accept: float, measured_false_reject: float,
                         acc: float, nmax: int = 201) -> float:
    """Quorum-comparable effective panel size.

    Matches the panel's *balanced* error against a fixed reference family:
    independent simple-majority panels (`quorum = 0.5`), where the two error
    types are symmetric. Because the reference does not move with the measured
    panel's quorum, values are comparable across quorums -- unlike `effective_n`,
    which a high quorum inflates by trading false accepts for false rejects.
    """
    balanced = (measured_false_accept + measured_false_reject) / 2.0
    return effective_n(balanced, acc, 0.5, nmax=nmax)


def effective_n_weighted(measured_false_accept: float, measured_false_reject: float,
                         acc: float, false_accept_cost: float = 1.0,
                         nmax: int = 201) -> float:
    """Cost-weighted effective panel size.

    `false_accept_cost` is how many false rejects one false accept is worth. For
    IDKMesh the asymmetry is real: merging an unsafe patch is more expensive than
    asking a contributor to resubmit. `1.0` reproduces `effective_n_balanced`.

    The weighted error is normalised so that the equal-cost case keeps the same
    scale as the balanced metric, which keeps every published figure comparable.
    """
    w = false_accept_cost
    weighted = (w * measured_false_accept + measured_false_reject) / (1.0 + w)
    return effective_n(weighted, acc, 0.5, nmax=nmax)


def best_quorum(cells, acc: float, corr: float, verifiers: int,
                false_accept_cost: float = 1.0):
    """Quorum maximising cost-weighted evidence for one panel configuration.

    `cells` are analysed records carrying `false_accept` and `false_reject`.
    Returns `(quorum, n_eff_weighted)` or None when the configuration is absent.
    """
    best = None
    for c in cells:
        if (c["verifiers"] != verifiers
                or abs(c["accuracy"] - acc) > 1e-9
                or abs(c["correlation"] - corr) > 1e-9):
            continue
        if c.get("false_reject") is None:
            continue
        score = effective_n_weighted(c["false_accept"], c["false_reject"],
                                     acc, false_accept_cost)
        if best is None or score > best[1]:
            best = (c["quorum"], score)
    return best


def heuristic_effective_n(n: int, correlation: float) -> float:
    """The classic equal-correlation heuristic `N / (1 + (N-1) rho)`.

    Recorded in `MATHEMATICAL_FOUNDATIONS.md` section 9. Provided here so it can
    be compared against the effective panel size actually measured by E015.
    """
    return n / (1.0 + (n - 1) * correlation)


def effective_n_ceiling(acc: float, correlation: float, nmax: int = 201) -> float:
    """Largest effective panel size any panel size can reach at `acc`/`correlation`.

    Under the shared-shock mixture the shared branch fires with probability
    `rho` and then the whole panel inherits one verifier's error, so balanced
    panel error floors at `rho * (1 - acc)` however many verifiers are added.
    Effective size floors with it. The heuristic has no such term: it rises to
    `1 / rho` regardless of verifier accuracy.
    """
    if acc <= 0.5:
        return float("nan")
    if correlation <= 0.0:
        return float("inf")
    return effective_n(correlation * (1.0 - acc), acc, 0.5, nmax=nmax)


def effective_n(measured_err: float, acc: float, quorum: float,
                nmax: int = 201) -> float:
    """Smallest independent panel size reproducing `measured_err`.

    Returns a float via linear interpolation between the bracketing odd sizes.
    """
    if acc <= 0.5:
        return float("nan")
    sizes = [n for n in range(1, nmax, 2)]
    errs = [majority_error_independent(n, acc, quorum) for n in sizes]
    # errs is decreasing in n
    if measured_err >= errs[0]:
        return 1.0
    if measured_err <= errs[-1]:
        return float(sizes[-1])
    for i in range(len(sizes) - 1):
        hi, lo = errs[i], errs[i + 1]
        if lo <= measured_err <= hi:
            if hi == lo:
                return float(sizes[i])
            frac = (hi - measured_err) / (hi - lo)
            return sizes[i] + frac * (sizes[i + 1] - sizes[i])
    return float("nan")


def main():
    rows = []
    for p in sys.argv[1:]:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    print(f"loaded {len(rows)} cells", file=sys.stderr)

    out = []
    for r in rows:
        agg = r["aggregate"]
        # pool the three strategies: verification error is a property of the
        # panel, and all three feed it the same kind of candidate stream.
        fa = [agg[s]["false_accept_rate"]["mean"] for s in agg
              if "false_accept_rate" in agg[s]]
        fr = [agg[s]["false_reject_rate"]["mean"] for s in agg
              if "false_reject_rate" in agg[s]]
        dis = [agg[s]["panel_disagreement_rate"]["mean"] for s in agg
               if "panel_disagreement_rate" in agg[s]]
        if not fa:
            continue
        fa_m = sum(fa) / len(fa)
        rec = {
            "verifiers": r["verifiers"], "accuracy": r["accuracy"],
            "correlation": r["correlation"], "quorum": r["quorum"],
            "seeds": r["seeds"],
            "false_accept": round(fa_m, 6),
            "false_reject": round(sum(fr) / len(fr), 6) if fr else None,
            "disagreement": round(sum(dis) / len(dis), 6) if dis else None,
        }
        fr_m = sum(fr) / len(fr) if fr else None
        rec["n_eff"] = round(effective_n(fa_m, r["accuracy"], r["quorum"]), 3)
        rec["n_eff_ratio"] = (round(rec["n_eff"] / r["verifiers"], 4)
                              if r["verifiers"] else None)
        if fr_m is not None:
            rec["n_eff_balanced"] = round(
                effective_n_balanced(fa_m, fr_m, r["accuracy"]), 3)
            rec["n_eff_balanced_ratio"] = (
                round(rec["n_eff_balanced"] / r["verifiers"], 4)
                if r["verifiers"] else None)
        out.append(rec)

    out.sort(key=lambda d: (d["verifiers"], d["accuracy"],
                            d["correlation"], d["quorum"]))
    with open("e015-phase-diagram.jsonl", "w") as fh:
        for rec in out:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    # headline table: n_eff vs correlation at the E012 reference operating point
    print("\n## n_eff at accuracy=0.75, quorum=0.5 (E012 reference)\n")
    print(f"{'panel n':>8} | " + " | ".join(f"c={c:<5}" for c in
          (0.0, 0.25, 0.5, 0.75, 1.0)))
    print("-" * 60)
    for v in (1, 3, 5, 7, 9, 11, 15, 21):
        cells = {d["correlation"]: d for d in out
                 if d["verifiers"] == v and abs(d["accuracy"] - 0.75) < 1e-9
                 and abs(d["quorum"] - 0.5) < 1e-9}
        if not cells:
            continue
        row = []
        for c in (0.0, 0.25, 0.5, 0.75, 1.0):
            d = cells.get(c)
            row.append(f"{d['n_eff']:<7.2f}" if d else "  --   ")
        print(f"{v:>8} | " + " | ".join(row))
    # quorum comparison -- only the balanced metric is valid across quorums
    quorums = sorted({d["quorum"] for d in out})
    if len(quorums) > 1:
        print("\n## n_eff_balanced across quorums (accuracy=0.75)\n")
        header = " | ".join(f"q={q:<4}" for q in quorums)
        print(f"{'panel n':>8} | {'rho':>5} | {header}")
        print("-" * (18 + 9 * len(quorums)))
        for v in sorted({d["verifiers"] for d in out}):
            for c in (0.0, 0.5, 1.0):
                cells = {d["quorum"]: d for d in out
                         if d["verifiers"] == v
                         and abs(d["accuracy"] - 0.75) < 1e-9
                         and abs(d["correlation"] - c) < 1e-9}
                if not cells:
                    continue
                row = " | ".join(
                    f"{cells[q]['n_eff_balanced']:<6.2f}" if q in cells
                    and cells[q].get("n_eff_balanced") is not None else "  --  "
                    for q in quorums)
                print(f"{v:>8} | {c:>5} | {row}")

    print(f"\nwrote e015-phase-diagram.jsonl ({len(out)} cells)")


if __name__ == "__main__":
    main()
