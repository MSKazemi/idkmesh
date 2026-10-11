#!/usr/bin/env python3
"""E045 pilot: dependence among real coding agents on public execution-graded data.

The SWE-bench project publishes, for every leaderboard submission, which of the
500 SWE-bench Verified instances the submission resolved, as decided by running
the hidden test suite. That is an agent x task solve matrix with
execution-decided ground truth, for well over a hundred real systems, at zero
project spend. This module measures how dependent those agents' successes are,
and whether a small pilot of agents can predict what a large ensemble covers.

It is an *exploratory pilot*. It reads data that the repository owner has already
looked at, so no number it prints is confirmatory. See
`experiments/E045-public-agent-dependence-pilot.md` for the evidence boundary and
`docs/research/SCIENTIFIC_PROGRAM.md` for the preregistered confirmatory design
that must use a temporal holdout instead.

The upstream data repository carries no licence file, so it is never vendored
here. `fetch` downloads it at a pinned commit into a local cache directory and
`analyze` records a SHA-256 digest of every file it read, so a replay can prove it
analysed the same bytes.

Usage::

    python experiments/public_agent_dependence.py fetch --cache .cache/swebench
    python experiments/public_agent_dependence.py analyze --cache .cache/swebench \
        --out experiments/results/E045-public-agent-dependence-pilot.json
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence

UPSTREAM_REPO = "SWE-bench/experiments"
PINNED_COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
SPLIT_PATH = "evaluation/verified"
N_INSTANCES = 500
COMPETENCE_FLOOR = 0.05
ENSEMBLE_SIZES = (1, 2, 3, 5, 10, 20, 40)
PILOT_SIZES = (5, 10, 20, 40)
DRAWS = 200
SEED = 45

SolveMatrix = Mapping[str, frozenset]


# --------------------------------------------------------------------------- fetch


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "idkmesh-e045"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https host
        return response.read()


def fetch(cache: Path, commit: str = PINNED_COMMIT) -> int:
    """Download every submission's per-instance results at ``commit``."""
    listing_url = f"https://api.github.com/repos/{UPSTREAM_REPO}/contents/{SPLIT_PATH}?ref={commit}"
    submissions = sorted(entry["name"] for entry in json.loads(_get(listing_url)) if entry["type"] == "dir")
    raw = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{commit}/{SPLIT_PATH}"
    stored = 0
    for kind, relative in (("r", "results/results.json"), ("p", "per_instance_details.json")):
        (cache / kind).mkdir(parents=True, exist_ok=True)
        for name in submissions:
            try:
                payload = _get(f"{raw}/{name}/{relative}")
            except OSError:
                continue
            (cache / kind / f"{name}.json").write_bytes(payload)
            stored += 1
    (cache / "COMMIT").write_text(commit + "\n", encoding="utf-8")
    return stored


# ---------------------------------------------------------------------------- load


def load_matrix(cache: Path) -> tuple[dict[str, frozenset], dict[str, str]]:
    """Return (agent -> resolved instance ids, file -> sha256) from a cache.

    The older submission format lists resolved ids under ``results/results.json``;
    the newer one has a per-instance ``resolved`` flag. Where both exist the
    explicit list wins. A newer-format file whose flags are all false is dropped:
    on the pinned commit such files exist and they describe a missing evaluation,
    not an agent that solved nothing.
    """
    rows: dict[str, frozenset] = {}
    digests: dict[str, str] = {}
    for path in sorted((cache / "r").glob("*.json")):
        payload = path.read_bytes()
        resolved = json.loads(payload).get("resolved")
        if isinstance(resolved, list):
            rows[path.stem] = frozenset(resolved)
            digests[f"r/{path.name}"] = hashlib.sha256(payload).hexdigest()
    for path in sorted((cache / "p").glob("*.json")):
        if path.stem in rows:
            continue
        payload = path.read_bytes()
        flags = json.loads(payload)
        resolved = frozenset(k for k, v in flags.items() if isinstance(v, dict) and v.get("resolved") is True)
        if resolved:
            rows[path.stem] = resolved
            digests[f"p/{path.name}"] = hashlib.sha256(payload).hexdigest()
    return rows, digests


# ------------------------------------------------------------------------ analysis


def wilson(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def phi(a: frozenset, b: frozenset, n: int) -> float | None:
    """Pearson correlation of two agents' binary solve vectors over n tasks."""
    pa, pb = len(a) / n, len(b) / n
    denominator = math.sqrt(pa * (1 - pa) * pb * (1 - pb))
    if denominator == 0:
        return None
    return (len(a & b) / n - pa * pb) / denominator


def coverage(rows: SolveMatrix, agents: Iterable[str], n: int) -> float:
    return len(frozenset().union(*(rows[a] for a in agents))) / n


def independent_coverage(rows: SolveMatrix, agents: Iterable[str], n: int) -> float:
    return 1 - math.prod(1 - len(rows[a]) / n for a in agents)


def chao2(rows: SolveMatrix, agents: Sequence[str], n: int) -> float:
    """Bias-corrected Chao2 estimate of the fraction of tasks the population solves.

    Incidence-based species-richness extrapolation: a task is a "species", an
    agent is a "sampling unit". f1 and f2 count tasks solved by exactly one and
    exactly two of the sampled agents.
    """
    k = len(agents)
    counts = Counter(task for a in agents for task in rows[a])
    f1 = sum(1 for c in counts.values() if c == 1)
    f2 = sum(1 for c in counts.values() if c == 2)
    correction = (k - 1) / k * (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)
    return min(len(counts) + correction, n) / n


def analyze(rows: SolveMatrix, n: int = N_INSTANCES, seed: int = SEED, draws: int = DRAWS) -> dict:
    competent = sorted(a for a in rows if len(rows[a]) / n >= COMPETENCE_FLOOR)
    if len(competent) < 2:
        raise ValueError("need at least two competent agents")
    rates = sorted(len(rows[a]) / n for a in competent)
    solved_by = Counter(task for a in competent for task in rows[a])
    union = len(solved_by)
    unsolved = n - union
    phis = [p for a, b in itertools.combinations(competent, 2) if (p := phi(rows[a], rows[b], n)) is not None]

    rng = random.Random(seed)
    full = union / n
    curve = []
    for k in ENSEMBLE_SIZES:
        if k > len(competent):
            continue
        observed, independent = [], []
        for _ in range(draws):
            sample = rng.sample(competent, k)
            observed.append(coverage(rows, sample, n))
            independent.append(independent_coverage(rows, sample, n))
        curve.append(
            {
                "k": k,
                "oracle_coverage_mean": round(sum(observed) / draws, 4),
                "independence_prediction_mean": round(sum(independent) / draws, 4),
            }
        )

    extrapolation = []
    for k in PILOT_SIZES:
        if k >= len(competent):
            continue
        gaps, errors = [], []
        for _ in range(draws):
            sample = rng.sample(competent, k)
            gaps.append(full - coverage(rows, sample, n))
            errors.append(full - chao2(rows, sample, n))
        extrapolation.append(
            {
                "pilot_agents": k,
                "observed_gap_to_population_mean": round(sum(gaps) / draws, 4),
                "chao2_bias_mean": round(sum(errors) / draws, 4),
                "chao2_mean_abs_error": round(sum(abs(e) for e in errors) / draws, 4),
            }
        )

    histogram = Counter(solved_by.values())
    floor_low, floor_high = wilson(unsolved, n)
    return {
        "agents_with_results": len(rows),
        "competent_agents": len(competent),
        "competence_floor": COMPETENCE_FLOOR,
        "instances": n,
        "solve_rate": {
            "min": round(rates[0], 4),
            "median": round(rates[len(rates) // 2], 4),
            "max": round(rates[-1], 4),
        },
        "population_coverage": round(full, 4),
        "blind_spot_floor": {
            "unsolved_by_every_agent": unsolved,
            "fraction": round(unsolved / n, 4),
            "wilson_95": [round(floor_low, 4), round(floor_high, 4)],
        },
        "solved_by_exactly_one_agent": histogram.get(1, 0),
        "mean_pairwise_phi": round(sum(phis) / len(phis), 4),
        "pairs": len(phis),
        "oracle_coverage_curve": curve,
        "chao2_extrapolation": extrapolation,
        "seed": seed,
        "draws": draws,
    }


# ----------------------------------------------------------------------------- cli


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_cmd = sub.add_parser("fetch", help="download the pinned upstream results into a cache")
    fetch_cmd.add_argument("--cache", type=Path, required=True)
    fetch_cmd.add_argument("--commit", default=PINNED_COMMIT)
    analyze_cmd = sub.add_parser("analyze", help="analyse a cache and print or write the pilot summary")
    analyze_cmd.add_argument("--cache", type=Path, required=True)
    analyze_cmd.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    if args.command == "fetch":
        print(f"stored {fetch(args.cache, args.commit)} files from {UPSTREAM_REPO}@{args.commit}")
        return 0

    rows, digests = load_matrix(args.cache)
    commit_file = args.cache / "COMMIT"
    summary = {
        "experiment": "E045",
        "evidence_class": "observed public data; exploratory pilot, not confirmatory",
        "upstream": {
            "repository": UPSTREAM_REPO,
            "commit": commit_file.read_text(encoding="utf-8").strip() if commit_file.exists() else None,
            "split": SPLIT_PATH,
            "files_read": len(digests),
            "files_sha256": hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest(),
        },
        **analyze(rows),
    }
    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
