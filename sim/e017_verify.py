#!/usr/bin/env python3
"""Run a panel of partial test oracles over the E016 candidate corpus.

Each verifier is a (region, seed) pair: it draws inputs from one region of a
problem's input domain and accepts a candidate only if the candidate agrees with
the reference implementation on every one of them. Verifiers are therefore real
programs making real errors -- a verifier misses a defect exactly when its
sampled inputs fail to expose it.

Outputs are evaluated once per candidate over the union of all sampled inputs,
then each verifier is applied as a subset filter. That is equivalent to running
every verifier separately and vastly cheaper.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


oracles = _load("e017_oracles", HERE / "e017_oracles.py")
corpus = _load("e016_corpus", HERE / "e016_corpus.py")

SENTINEL = "__E017_RAISED__"


def evaluate(source: str, calls: list, timeout: int = 20):
    """Run `source` against every call, returning a repr per call.

    A call that raises yields SENTINEL rather than aborting the batch, so one
    bad input cannot hide a candidate's behaviour on the others.
    """
    body = source + "\n\nimport json as _json\n_args = _json.loads(%r)\n" % json.dumps(calls)
    body += (
        "_out = []\n"
        "for _a in _args:\n"
        "    try:\n"
        "        _r = solve(*_a)\n"
        "        _out.append([type(_r).__name__, repr(_r)])\n"
        "    except Exception:\n"
        "        _out.append([%r, %r])\n"
        "print(_json.dumps(_out))\n" % (SENTINEL, SENTINEL)
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           timeout=timeout, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            return [[SENTINEL, SENTINEL]] * len(calls)
        return json.loads(r.stdout)
    except Exception:
        return [[SENTINEL, SENTINEL]] * len(calls)
    finally:
        Path(path).unlink(missing_ok=True)


def build_panel(regions, seeds):
    """Panel definition: one verifier per (region, seed)."""
    return [{"verifier_id": f"{region}-s{seed}", "region": region, "seed": seed}
            for region in regions for seed in seeds]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", default="benchmarks/e016-verification-corpus/tasks.jsonl")
    ap.add_argument("--out", default="e017-votes.jsonl")
    ap.add_argument("--draws", type=int, default=6,
                    help="inputs drawn per verifier per problem")
    ap.add_argument("--seeds", type=int, default=4,
                    help="verifiers per region")
    args = ap.parse_args()

    tasks = [json.loads(line) for line in open(args.tasks)]
    by_problem = {}
    for t in tasks:
        by_problem.setdefault(t["problem"], []).append(t)

    reference = {name: variants["ok"]
                 for name, _spec, variants, _tests in corpus.PROBLEMS}

    panel = build_panel(oracles.REGIONS, range(args.seeds))
    rows = []
    for problem, candidates in sorted(by_problem.items()):
        # Input pool: every verifier's draw, concatenated, with an index range
        # recorded per verifier so the subset filter is exact.
        pool, spans = [], {}
        for v in panel:
            drawn = oracles.draw_inputs(problem, v["region"], args.draws, v["seed"])
            spans[v["verifier_id"]] = (len(pool), len(pool) + len(drawn))
            pool.extend(drawn)
        pool = [list(a) for a in pool]
        if not pool:
            continue

        ref_out = evaluate(reference[problem], pool)
        # Inputs on which the reference itself raises are out of contract and
        # are excluded from every verifier -- rejecting there would be the
        # oracle's fault, not the candidate's.
        valid = {i for i, o in enumerate(ref_out) if o[0] != SENTINEL}

        for task in candidates:
            cand_out = evaluate(task["candidate"], pool)
            for v in panel:
                lo, hi = spans[v["verifier_id"]]
                idx = [i for i in range(lo, hi) if i in valid]
                if not idx:
                    verdict = None
                else:
                    verdict = all(cand_out[i] == ref_out[i] for i in idx)
                rows.append({
                    "agent_id": v["verifier_id"],
                    "model": v["region"],          # region is the panel's
                    "template": f"seed{v['seed']}",  # declared independence label
                    "task_id": task["task_id"],
                    "problem": problem,
                    "verdict": verdict,
                    "n_inputs": len(idx),
                })
        print(f"  {problem:26s} pool={len(pool):4d} valid={len(valid):4d} "
              f"candidates={len(candidates)}", flush=True)

    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} votes for {len(panel)} verifiers -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
