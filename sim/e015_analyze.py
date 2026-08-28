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
        rec["n_eff"] = round(effective_n(fa_m, r["accuracy"], r["quorum"]), 3)
        rec["n_eff_ratio"] = (round(rec["n_eff"] / r["verifiers"], 4)
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
    print(f"\nwrote e015-phase-diagram.jsonl ({len(out)} cells)")


if __name__ == "__main__":
    main()
