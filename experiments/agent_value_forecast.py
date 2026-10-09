#!/usr/bin/env python3
"""E046: forecast the value of the next coding agent from a small pilot (X3, X4, X5).

This module is the analysis frozen by
`docs/research/PREREG_AGENT_VALUE_FORECAST_V1.md`. Its SHA-256 is recorded there,
and that document was merged before any held-out split was downloaded. Changing
this file after the freeze turns every result it produces into an amendment,
which the results record must say.

Input: a public agent x task solve matrix with execution-decided outcomes. That
is one SWE-bench split of the `SWE-bench/experiments` repository at a pinned
commit, fetched by `fetch` below (which reuses E045's never-vendor rule).

It answers three preregistered questions:

* **H1 shape (X3).** Fit each dependence model to a k-agent pilot and forecast
  the population's mean oracle coverage curve C(m). Is the per-item-difficulty
  model (beta-binomial) more accurate than the Kish design effect and the
  shared-shock mixture, which have the same parameter count?
* **H2 forecast (X4).** Does any prespecified item-level forecaster
  (beta-binomial, Rasch, or Chao et al. 2014 incidence extrapolation) forecast
  the full-population coverage, and therefore the blind-spot floor, within
  0.03 from a 10-agent pilot?
* **H3 selection (X5).** On held-out tasks, does greedy complementarity
  selection on calibration tasks cover more than choosing the k most accurate
  agents?

Standard library only. Deterministic for a fixed seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import socket
import sys
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

UPSTREAM_REPO = "SWE-bench/experiments"
SEED = 20261009
COMPETENCE_FLOOR = 0.05
MIN_AGENTS = 20
MIN_TASKS = 100
PILOT_SIZE = 10
SENSITIVITY_PILOT_SIZES = (5, 20)
CURVE_SIZES = (2, 5, 10, 20, 40)
PILOTS = 200
RASCH_PILOTS = 100
POPULATION_DRAWS = 200
BOOTSTRAP_REPLICATES = 200
BOOTSTRAP_PILOTS = 40
H2_TOLERANCE = 0.03
SELECTION_SIZES = (3, 5, 10)
PRIMARY_SELECTION_SIZE = 5
SELECTION_RESPLITS = 200

Matrix = Mapping[str, frozenset]


# --------------------------------------------------------------------------- fetch


@contextmanager
def _ipv4_only() -> Iterator[None]:
    """Resolve hosts to IPv4 only.

    urllib tries IPv6 first and, on a host whose IPv6 route is black-holed, hangs
    per address. That was observed while producing E045.
    """
    original = socket.getaddrinfo

    def ipv4(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [entry for entry in original(*args, **kwargs) if entry[0] == socket.AF_INET]

    socket.getaddrinfo = ipv4  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.getaddrinfo = original  # type: ignore[assignment]


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "idkmesh-e046"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https host
        return response.read()


def fetch(cache: Path, split: str, commit: str, ipv4: bool = True) -> int:
    """Download one split's per-submission results at ``commit`` into ``cache``."""
    context = _ipv4_only() if ipv4 else _nullcontext()
    with context:
        listing = json.loads(_get(f"https://api.github.com/repos/{UPSTREAM_REPO}/contents/evaluation/{split}?ref={commit}"))
        submissions = sorted(entry["name"] for entry in listing if entry["type"] == "dir")
        raw = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{commit}/evaluation/{split}"
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
    (cache / "SPLIT").write_text(split + "\n", encoding="utf-8")
    return stored


@contextmanager
def _nullcontext() -> Iterator[None]:
    yield


# ---------------------------------------------------------------------------- load


def load_split(cache: Path) -> tuple[dict[str, frozenset], frozenset, dict[str, str]]:
    """Return (agent -> resolved ids, task universe, file -> sha256).

    The resolved-set rule is E045's: an explicit ``resolved`` list wins, and a
    per-instance file whose flags are all false is a missing evaluation and is
    dropped. The task universe is the union of every instance id that appears
    under any list-valued key of any ``results.json``, or as a key of any
    ``per_instance_details.json``, in the split.
    """
    rows: dict[str, frozenset] = {}
    universe: set[str] = set()
    digests: dict[str, str] = {}
    for path in sorted((cache / "r").glob("*.json")):
        payload = path.read_bytes()
        record = json.loads(payload)
        if not isinstance(record, dict):
            continue
        for value in record.values():
            if isinstance(value, list):
                universe.update(item for item in value if isinstance(item, str))
        resolved = record.get("resolved")
        if isinstance(resolved, list):
            rows[path.stem] = frozenset(item for item in resolved if isinstance(item, str))
            digests[f"r/{path.name}"] = hashlib.sha256(payload).hexdigest()
    for path in sorted((cache / "p").glob("*.json")):
        payload = path.read_bytes()
        flags = json.loads(payload)
        if not isinstance(flags, dict):
            continue
        universe.update(key for key in flags if isinstance(key, str))
        if path.stem in rows:
            continue
        resolved = frozenset(k for k, v in flags.items() if isinstance(v, dict) and v.get("resolved") is True)
        if resolved:
            rows[path.stem] = resolved
            digests[f"p/{path.name}"] = hashlib.sha256(payload).hexdigest()
    return rows, frozenset(universe), digests


def competent(rows: Matrix, n: int) -> list[str]:
    return sorted(agent for agent, solved in rows.items() if len(solved) / n >= COMPETENCE_FLOOR)


# ---------------------------------------------------------------------- primitives


def coverage(rows: Matrix, agents: Sequence[str], tasks: frozenset | None = None) -> int:
    covered = frozenset().union(*(rows[a] for a in agents)) if agents else frozenset()
    return len(covered if tasks is None else covered & tasks)


def solve_counts(rows: Matrix, agents: Sequence[str], tasks: Sequence[str]) -> list[int]:
    return [sum(1 for a in agents if task in rows[a]) for task in tasks]


def mean_phi(rows: Matrix, agents: Sequence[str], tasks: Sequence[str]) -> float:
    n = len(tasks)
    task_set = frozenset(tasks)
    values = []
    for i, a in enumerate(agents):
        sa = rows[a] & task_set
        for b in agents[i + 1 :]:
            sb = rows[b] & task_set
            pa, pb = len(sa) / n, len(sb) / n
            denominator = math.sqrt(pa * (1 - pa) * pb * (1 - pb))
            if denominator > 0:
                values.append((len(sa & sb) / n - pa * pb) / denominator)
    return sum(values) / len(values) if values else 0.0


def population_curve(rows: Matrix, agents: Sequence[str], tasks: Sequence[str], sizes: Sequence[int], rng: random.Random | None = None) -> dict[int, float]:
    """Exact mean oracle coverage of a uniformly random m-subset of ``agents``.

    A task solved by c of the M agents is missed by an m-subset with
    hypergeometric probability C(M - c, m) / C(M, m), so no sampling is needed.
    """
    population = len(agents)
    counts = solve_counts(rows, agents, tasks)
    curve = {}
    for m in sizes:
        m = min(m, population)
        log_total = _log_comb(population, m)
        missed = sum(math.exp(_log_comb(population - c, m) - log_total) for c in counts if population - c >= m)
        curve[m] = 1 - missed / len(tasks)
    return curve


# --------------------------------------------------------------------- forecasters
#
# Each forecaster sees only the pilot: k agents' outcomes on every task. It
# returns a function m -> forecast mean oracle coverage of m random agents
# drawn from the population.


Forecast = Callable[[int], float]


def forecast_independence(counts: Sequence[int], k: int) -> Forecast:
    p = sum(counts) / (k * len(counts))
    return lambda m: 1 - (1 - p) ** m


def forecast_kish(counts: Sequence[int], k: int, phi_bar: float) -> Forecast:
    p = sum(counts) / (k * len(counts))
    rho = max(0.0, phi_bar)

    def curve(m: int) -> float:
        n_eff = m / (1 + (m - 1) * rho)
        return 1 - (1 - p) ** n_eff

    return curve


def forecast_shared_shock(counts: Sequence[int], k: int, phi_bar: float) -> Forecast:
    """With probability w every agent shares one outcome; otherwise independent.

    For equal success rates, the pairwise phi of this mixture is exactly w.
    """
    p = sum(counts) / (k * len(counts))
    w = min(1.0, max(0.0, phi_bar))
    return lambda m: w * p + (1 - w) * (1 - (1 - p) ** m)


def beta_binomial_parameters(counts: Sequence[int], k: int) -> tuple[float, float] | None:
    """Method-of-moments (alpha, beta), or None when no overdispersion is seen."""
    n = len(counts)
    mu = sum(counts) / (k * n)
    if mu <= 0 or mu >= 1 or k < 2:
        return None
    mean = sum(counts) / n
    variance = sum((c - mean) ** 2 for c in counts) / (n - 1)
    rho = (variance / (k * mu * (1 - mu)) - 1) / (k - 1)
    if rho <= 0:
        return None
    rho = min(rho, 0.999)
    scale = 1 / rho - 1
    return mu * scale, (1 - mu) * scale


def forecast_beta_binomial(counts: Sequence[int], k: int) -> Forecast:
    parameters = beta_binomial_parameters(counts, k)
    if parameters is None:
        return forecast_independence(counts, k)
    alpha, beta = parameters
    log_b = math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
    return lambda m: 1 - math.exp(math.lgamma(alpha) + math.lgamma(beta + m) - math.lgamma(alpha + beta + m) - log_b)


def forecast_rasch(rows: Matrix, pilot: Sequence[str], tasks: Sequence[str], iterations: int = 25, prior: float = 0.01) -> Forecast:
    """Rasch model with a N(0, prior^-1) ridge on difficulties, fitted to the pilot.

    The population's abilities are assumed to be distributed like the pilot's.
    Conditional on a task, agents are independent, so a task's coverage is
    1 - (1 - q_t)^m with q_t = mean_j sigmoid(a_j - b_t).
    """
    outcomes = [[1 if task in rows[a] else 0 for task in tasks] for a in pilot]
    ability = [0.0] * len(pilot)
    difficulty = [0.0] * len(tasks)

    def sigmoid(x: float) -> float:
        return 1 / (1 + math.exp(-x)) if x > -35 else 0.0

    for _ in range(iterations):
        for t in range(len(tasks)):
            gradient, curvature = -prior * difficulty[t], prior
            for j in range(len(pilot)):
                p = sigmoid(ability[j] - difficulty[t])
                gradient += p - outcomes[j][t]
                curvature += p * (1 - p)
            difficulty[t] += gradient / curvature
        for j in range(len(pilot)):
            gradient, curvature = -0.01 * ability[j], 0.01
            for t in range(len(tasks)):
                p = sigmoid(ability[j] - difficulty[t])
                gradient += outcomes[j][t] - p
                curvature += p * (1 - p)
            ability[j] += gradient / curvature
    q = [sum(sigmoid(a - b) for a in ability) / len(ability) for b in difficulty]
    return lambda m: sum(1 - (1 - qt) ** m for qt in q) / len(q)


def forecast_incidence(counts: Sequence[int], k: int) -> Forecast:
    """Chao et al. (2014) incidence-based rarefaction and extrapolation of richness.

    Tasks are species and agents are sampling units. Returns covered fraction.
    """
    n = len(counts)
    frequencies: dict[int, int] = {}
    for c in counts:
        if c > 0:
            frequencies[c] = frequencies.get(c, 0) + 1
    observed = sum(frequencies.values())
    q1, q2 = frequencies.get(1, 0), frequencies.get(2, 0)
    q0 = (k - 1) / k * (q1 * q1 / (2 * q2) if q2 > 0 else q1 * (q1 - 1) / 2)

    def curve(m: int) -> float:
        if m <= k:
            expected = sum(
                count * (1 - math.exp(_log_comb(k - j, m) - _log_comb(k, m))) if k - j >= m else count
                for j, count in frequencies.items()
            )
            return expected / n
        if q0 <= 0:
            return observed / n
        extra = q0 * (1 - (1 - q1 / (k * q0 + q1)) ** (m - k))
        return min(observed + extra, n) / n

    return curve


def forecast_pilot_only(counts: Sequence[int], k: int) -> Forecast:
    """Baseline: rarefy within the pilot, then assume no further gain."""
    incidence = forecast_incidence(counts, k)
    flat = sum(1 for c in counts if c > 0) / len(counts)
    return lambda m: incidence(m) if m <= k else flat


def _log_comb(n: int, r: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(r + 1) - math.lgamma(n - r + 1)


CLOSED_FORM = ("independence", "kish", "shared_shock", "beta_binomial", "incidence", "pilot_only")


def closed_form_forecasts(rows: Matrix, pilot: Sequence[str], tasks: Sequence[str]) -> dict[str, Forecast]:
    k = len(pilot)
    counts = solve_counts(rows, pilot, tasks)
    phi_bar = mean_phi(rows, pilot, tasks)
    return {
        "independence": forecast_independence(counts, k),
        "kish": forecast_kish(counts, k, phi_bar),
        "shared_shock": forecast_shared_shock(counts, k, phi_bar),
        "beta_binomial": forecast_beta_binomial(counts, k),
        "incidence": forecast_incidence(counts, k),
        "pilot_only": forecast_pilot_only(counts, k),
    }


# ------------------------------------------------------------------------ H1 / H2


def _grid(population: int) -> list[int]:
    return [m for m in CURVE_SIZES if m < population] + [population]


def forecast_errors(rows: Matrix, agents: Sequence[str], tasks: Sequence[str], k: int, pilots: int, rasch_pilots: int, rng: random.Random) -> dict:
    grid = _grid(len(agents))
    truth = population_curve(rows, agents, tasks, grid, rng)
    curve_errors: dict[str, list[float]] = {name: [] for name in CLOSED_FORM + ("rasch",)}
    floor_errors: dict[str, list[float]] = {name: [] for name in CLOSED_FORM + ("rasch",)}
    for index in range(pilots):
        pilot = rng.sample(list(agents), k)
        models = closed_form_forecasts(rows, pilot, tasks)
        if index < rasch_pilots:
            models["rasch"] = forecast_rasch(rows, pilot, tasks)
        for name, model in models.items():
            curve_errors[name].append(sum(abs(model(m) - truth[m]) for m in grid) / len(grid))
            floor_errors[name].append(model(grid[-1]) - truth[grid[-1]])
    return {
        "grid": grid,
        "population_curve": {str(m): round(v, 4) for m, v in truth.items()},
        "curve_mae": {name: round(sum(v) / len(v), 4) for name, v in curve_errors.items() if v},
        "population_coverage_bias": {name: round(sum(v) / len(v), 4) for name, v in floor_errors.items() if v},
        "population_coverage_mae": {name: round(sum(abs(x) for x in v) / len(v), 4) for name, v in floor_errors.items() if v},
    }


def bootstrap_h1(rows: Matrix, agents: Sequence[str], tasks: Sequence[str], k: int, rng: random.Random, replicates: int = BOOTSTRAP_REPLICATES) -> dict:
    """Task-cluster bootstrap of the curve-MAE differences (comparator - beta-binomial)."""
    differences: dict[str, list[float]] = {"kish": [], "shared_shock": []}
    grid = _grid(len(agents))
    for _ in range(replicates):
        sample = [rng.choice(tasks) for _ in tasks]
        multiplicity: dict[str, int] = {}
        for task in sample:
            multiplicity[task] = multiplicity.get(task, 0) + 1
        # Expand duplicates into distinct pseudo-tasks so set-based code sees them.
        expanded_rows = {a: frozenset(f"{t}#{i}" for t in solved if t in multiplicity for i in range(multiplicity[t])) for a, solved in rows.items() if a in set(agents)}
        expanded_tasks = [f"{t}#{i}" for t, c in multiplicity.items() for i in range(c)]
        truth = population_curve(expanded_rows, agents, expanded_tasks, grid, rng)
        totals = {"kish": 0.0, "shared_shock": 0.0, "beta_binomial": 0.0}
        for _ in range(BOOTSTRAP_PILOTS):
            pilot = rng.sample(list(agents), k)
            models = closed_form_forecasts(expanded_rows, pilot, expanded_tasks)
            for name in totals:
                totals[name] += sum(abs(models[name](m) - truth[m]) for m in grid) / len(grid)
        for name in differences:
            differences[name].append((totals[name] - totals["beta_binomial"]) / BOOTSTRAP_PILOTS)
    summary = {}
    for name, values in differences.items():
        values.sort()
        summary[name] = {
            "mean": round(sum(values) / len(values), 4),
            "ci95": [round(values[int(0.025 * len(values))], 4), round(values[min(len(values) - 1, int(0.975 * len(values)))], 4)],
        }
    return summary


def h1_verdict(curve_mae: Mapping[str, float], bootstrap: Mapping[str, Mapping]) -> str:
    better = [bootstrap[name]["ci95"][0] > 0 for name in ("kish", "shared_shock")]
    worse = [bootstrap[name]["ci95"][1] < 0 for name in ("kish", "shared_shock")]
    if all(better):
        return "supported"
    if any(worse):
        return "falsified"
    return "unresolved"


def h2_verdict(coverage_mae: Mapping[str, float]) -> dict:
    meets = {name: coverage_mae[name] <= H2_TOLERANCE for name in ("beta_binomial", "rasch", "incidence") if name in coverage_mae}
    beats_baseline = {name: coverage_mae[name] < coverage_mae["pilot_only"] for name in meets}
    return {"meets_tolerance": meets, "beats_pilot_only": beats_baseline, "verdict": "supported" if any(meets.values()) else "falsified"}


# ----------------------------------------------------------------------------- H3


def calibration_half(task: str) -> bool:
    return int(hashlib.sha256(task.encode("utf-8")).hexdigest(), 16) % 2 == 0


def select_top_k(rows: Matrix, agents: Sequence[str], calibration: frozenset, k: int) -> list[str]:
    return sorted(agents, key=lambda a: (-len(rows[a] & calibration), a))[:k]


def select_greedy(rows: Matrix, agents: Sequence[str], calibration: frozenset, k: int) -> list[str]:
    chosen: list[str] = []
    covered: frozenset = frozenset()
    for _ in range(k):
        best = max(
            (a for a in agents if a not in chosen),
            key=lambda a: (len((rows[a] & calibration) - covered), len(rows[a] & calibration), [-ord(ch) for ch in a]),
        )
        chosen.append(best)
        covered |= rows[best] & calibration
    return chosen


def exact_mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def selection(rows: Matrix, agents: Sequence[str], tasks: Sequence[str], rng: random.Random) -> dict:
    calibration = frozenset(t for t in tasks if calibration_half(t))
    held_out = frozenset(tasks) - calibration
    result: dict = {"calibration_tasks": len(calibration), "held_out_tasks": len(held_out), "by_k": {}}
    for k in SELECTION_SIZES:
        top = select_top_k(rows, agents, calibration, k)
        greedy = select_greedy(rows, agents, calibration, k)
        top_cover = frozenset().union(*(rows[a] for a in top)) & held_out
        greedy_cover = frozenset().union(*(rows[a] for a in greedy)) & held_out
        random_mean = sum(coverage(rows, rng.sample(list(agents), k), held_out) for _ in range(POPULATION_DRAWS)) / POPULATION_DRAWS
        b, c = len(greedy_cover - top_cover), len(top_cover - greedy_cover)
        resplit = []
        for _ in range(SELECTION_RESPLITS):
            shuffled = list(tasks)
            rng.shuffle(shuffled)
            cal, hold = frozenset(shuffled[: len(shuffled) // 2]), frozenset(shuffled[len(shuffled) // 2 :])
            g = select_greedy(rows, agents, cal, k)
            t = select_top_k(rows, agents, cal, k)
            resplit.append((coverage(rows, g, hold) - coverage(rows, t, hold)) / len(hold))
        result["by_k"][str(k)] = {
            "greedy_held_out_coverage": round(len(greedy_cover) / len(held_out), 4),
            "top_k_held_out_coverage": round(len(top_cover) / len(held_out), 4),
            "random_held_out_coverage": round(random_mean / len(held_out), 4),
            "greedy_only_tasks": b,
            "top_k_only_tasks": c,
            "mcnemar_p": round(exact_mcnemar(b, c), 6),
            "resplit_mean_difference": round(sum(resplit) / len(resplit), 4),
            "resplit_greedy_not_worse_fraction": round(sum(1 for d in resplit if d >= 0) / len(resplit), 4),
        }
    primary = result["by_k"][str(PRIMARY_SELECTION_SIZE)]
    if primary["greedy_only_tasks"] > primary["top_k_only_tasks"] and primary["mcnemar_p"] < 0.05:
        result["verdict"] = "supported"
    elif primary["top_k_only_tasks"] > primary["greedy_only_tasks"] and primary["mcnemar_p"] < 0.05:
        result["verdict"] = "falsified"
    else:
        result["verdict"] = "unresolved"
    return result


# ------------------------------------------------------------------------- driver


def analyze_split(rows: Matrix, universe: frozenset, seed: int = SEED, bootstrap: bool = True) -> dict:
    n = len(universe)
    agents = competent(rows, n) if n else []
    report: dict = {"tasks": n, "agents_with_results": len(rows), "competent_agents": len(agents)}
    if len(agents) < MIN_AGENTS or n < MIN_TASKS:
        report["feasible"] = False
        report["reason"] = f"needs >= {MIN_AGENTS} competent agents and >= {MIN_TASKS} tasks"
        return report
    report["feasible"] = True
    rng = random.Random(seed)
    tasks = sorted(universe)
    unsolved = n - coverage(rows, agents, universe)
    report["blind_spot_floor"] = {"unsolved_by_every_agent": unsolved, "fraction": round(unsolved / n, 4)}
    report["mean_pairwise_phi"] = round(mean_phi(rows, agents, tasks), 4)
    primary = forecast_errors(rows, agents, tasks, PILOT_SIZE, PILOTS, RASCH_PILOTS, rng)
    report["primary"] = primary
    report["h1_bootstrap"] = bootstrap_h1(rows, agents, tasks, PILOT_SIZE, rng) if bootstrap else None
    report["h1_verdict"] = h1_verdict(primary["curve_mae"], report["h1_bootstrap"]) if bootstrap else None
    report["h2"] = h2_verdict(primary["population_coverage_mae"])
    report["sensitivity"] = {
        str(k): forecast_errors(rows, agents, tasks, k, PILOTS // 4, 0, rng)["curve_mae"] for k in SENSITIVITY_PILOT_SIZES if k < len(agents)
    }
    report["h3"] = selection(rows, agents, tasks, rng)
    return report


def combine(split_reports: Mapping[str, Mapping]) -> dict:
    """Preregistered cross-split decision rules (section 6 of the preregistration)."""
    feasible = {name: r for name, r in split_reports.items() if r.get("feasible")}
    h1 = [r["h1_verdict"] for r in feasible.values()]
    h3 = [r["h3"]["verdict"] for r in feasible.values()]
    h2_names = ("beta_binomial", "rasch", "incidence")
    h2_all = {name: all(r["h2"]["meets_tolerance"].get(name, False) for r in feasible.values()) for name in h2_names}

    def majority(verdicts: list[str]) -> str:
        if not verdicts:
            return "infeasible"
        if verdicts.count("supported") > len(verdicts) / 2 and "falsified" not in verdicts:
            return "supported"
        if verdicts.count("falsified") > len(verdicts) / 2:
            return "falsified"
        return "unresolved"

    return {
        "feasible_splits": sorted(feasible),
        "H1": majority(h1),
        "H2": ("supported" if any(h2_all.values()) else "falsified") if feasible else "infeasible",
        "H2_estimators_meeting_tolerance_on_every_split": [n for n, ok in h2_all.items() if ok],
        "H3": majority(h3),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_cmd = sub.add_parser("fetch")
    fetch_cmd.add_argument("--cache", type=Path, required=True)
    fetch_cmd.add_argument("--split", required=True)
    fetch_cmd.add_argument("--commit", required=True)
    analyze_cmd = sub.add_parser("analyze", help="analyse one or more split caches")
    analyze_cmd.add_argument("caches", type=Path, nargs="+")
    analyze_cmd.add_argument("--out", type=Path)
    analyze_cmd.add_argument("--no-bootstrap", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "fetch":
        print(f"stored {fetch(args.cache, args.split, args.commit)} files for {args.split}@{args.commit}")
        return 0
    splits = {}
    for cache in args.caches:
        rows, universe, digests = load_split(cache)
        name = (cache / "SPLIT").read_text(encoding="utf-8").strip() if (cache / "SPLIT").exists() else cache.name
        report = analyze_split(rows, universe, bootstrap=not args.no_bootstrap)
        report["upstream"] = {
            "commit": (cache / "COMMIT").read_text(encoding="utf-8").strip() if (cache / "COMMIT").exists() else None,
            "files_read": len(digests),
            "files_sha256": hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest(),
        }
        splits[name] = report
    summary = {
        "experiment": "E046",
        "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seed": SEED,
        "splits": splits,
        "decision": combine(splits),
    }
    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
