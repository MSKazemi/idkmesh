#!/usr/bin/env python3
"""X4 interval report: do the intervals a pilot forecaster reports actually cover the truth?

Issue #976 asks for bias, mean absolute error **and interval coverage** of the
intervals each forecaster reports, as a function of the pilot size k. E046
(`agent_value_forecast.py`, frozen by `docs/research/PREREG_AGENT_VALUE_FORECAST_V1.md`)
reports point forecasts only. This module adds the missing intervals without
touching the frozen file: it imports its forecasters unchanged.

For one k-agent pilot and one forecaster, a bootstrap interval for the
population coverage C(M) is the percentile interval of the forecast refitted on
resampled pilots. Two resampling schemes are compared because they answer
different questions:

* ``task``  - resample tasks with replacement (the iNEXT-style incidence
  bootstrap, Chao et al. 2014). It captures task-sampling noise only.
* ``agent`` - resample the pilot's k agents with replacement. It captures the
  noise from having drawn only k of the M agents, which is the noise a pilot
  actually has when the task set is fixed.

The truth is the exact C(M) of the whole competent population on the same
tasks (``population_curve``), and the blind-spot floor is 1 - C(M), so each
floor interval is the reflected coverage interval.

Scope: this is an exploratory instrument. Run on splits that E046 already
opened, its output is post-hoc, not confirmatory. Rasch is excluded because it
needs the full outcome matrix, not the per-task solve counts.

Standard library only. Deterministic for a fixed seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_value_forecast as e046  # noqa: E402

Forecast = Callable[[int], float]
CountForecaster = Callable[[Sequence[int], int], Forecast]

SEED = 20261012
LEVEL = 0.95
REPLICATES = 200
PILOTS = 100
PILOT_SIZES = (3, 5, 10, 20)
SCHEMES = ("task", "agent")
FORECASTERS: Mapping[str, CountForecaster] = {
    "independence": e046.forecast_independence,
    "beta_binomial": e046.forecast_beta_binomial,
    "incidence": e046.forecast_incidence,
    "pilot_only": e046.forecast_pilot_only,
}


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile of an ascending list, ``q`` in [0, 1]."""
    if not sorted_values:
        raise ValueError("percentile of an empty list")
    position = q * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def resample_tasks(columns: Sequence[Sequence[int]], rng: random.Random) -> list[int]:
    """Solve counts of a task-bootstrap replicate (tasks drawn with replacement)."""
    counts = [sum(column[t] for column in columns) for t in range(len(columns[0]))]
    return [rng.choice(counts) for _ in counts]


def resample_agents(columns: Sequence[Sequence[int]], rng: random.Random) -> list[int]:
    """Solve counts of an agent-bootstrap replicate (k pilot agents drawn with replacement)."""
    drawn = [rng.choice(columns) for _ in columns]
    return [sum(column[t] for column in drawn) for t in range(len(columns[0]))]


RESAMPLERS = {"task": resample_tasks, "agent": resample_agents}


def bootstrap_interval(
    columns: Sequence[Sequence[int]],
    forecaster: CountForecaster,
    population: int,
    scheme: str,
    rng: random.Random,
    replicates: int = REPLICATES,
    level: float = LEVEL,
) -> tuple[float, tuple[float, float]]:
    """Point forecast and percentile interval of C(population) from one pilot.

    ``columns`` holds one 0/1 vector per pilot agent over the task list.
    """
    k = len(columns)
    point = forecaster([sum(column[t] for column in columns) for t in range(len(columns[0]))], k)(population)
    resample = RESAMPLERS[scheme]
    draws = sorted(forecaster(resample(columns, rng), k)(population) for _ in range(replicates))
    tail = (1 - level) / 2
    return point, (percentile(draws, tail), percentile(draws, 1 - tail))


def floor_interval(coverage_interval: tuple[float, float]) -> tuple[float, float]:
    """The blind-spot floor is 1 - C(M), so its interval is the reflected one."""
    low, high = coverage_interval
    return 1 - high, 1 - low


def summarize(trials: Sequence[tuple[float, tuple[float, float], float]], tolerance: float = e046.H2_TOLERANCE) -> dict:
    """Bias, MAE, tolerance rate, interval coverage and width from (point, interval, truth) trials."""
    n = len(trials)
    errors = [point - truth for point, _, truth in trials]
    return {
        "pilots": n,
        "bias": round(sum(errors) / n, 4),
        "mae": round(sum(abs(e) for e in errors) / n, 4),
        "within_tolerance": round(sum(abs(e) <= tolerance for e in errors) / n, 4),
        "interval_coverage": round(sum(low <= truth <= high for _, (low, high), truth in trials) / n, 4),
        "mean_width": round(sum(high - low for _, (low, high), _ in trials) / n, 4),
    }


def interval_study(
    rows: Mapping[str, frozenset],
    agents: Sequence[str],
    tasks: Sequence[str],
    k: int,
    rng: random.Random,
    pilots: int = PILOTS,
    replicates: int = REPLICATES,
    level: float = LEVEL,
) -> dict:
    """Score every (forecaster, scheme) pair at pilot size ``k`` against the exact C(M)."""
    population = len(agents)
    if not 2 <= k < population:
        raise ValueError("pilot size must satisfy 2 <= k < number of agents")
    truth = e046.population_curve(rows, agents, tasks, [population])[population]
    trials: dict[tuple[str, str], list] = {(f, s): [] for f in FORECASTERS for s in SCHEMES}
    for _ in range(pilots):
        pilot = rng.sample(list(agents), k)
        columns = [[1 if t in rows[a] else 0 for t in tasks] for a in pilot]
        for name, forecaster in FORECASTERS.items():
            for scheme in SCHEMES:
                point, interval = bootstrap_interval(columns, forecaster, population, scheme, rng, replicates, level)
                trials[(name, scheme)].append((point, interval, truth))
    return {
        "k": k,
        "population_agents": population,
        "true_coverage": round(truth, 4),
        "true_floor": round(1 - truth, 4),
        "level": level,
        "results": {f"{name}/{scheme}": summarize(rows_) for (name, scheme), rows_ in trials.items()},
    }


def study_by_k(
    rows: Mapping[str, frozenset],
    universe: frozenset,
    seed: int = SEED,
    sizes: Sequence[int] = PILOT_SIZES,
    pilots: int = PILOTS,
    replicates: int = REPLICATES,
) -> dict:
    n = len(universe)
    agents = e046.competent(rows, n) if n else []
    if len(agents) < e046.MIN_AGENTS or n < e046.MIN_TASKS:
        return {"feasible": False, "reason": f"needs >= {e046.MIN_AGENTS} competent agents and >= {e046.MIN_TASKS} tasks"}
    rng = random.Random(seed)
    tasks = sorted(universe)
    return {
        "feasible": True,
        "tasks": n,
        "competent_agents": len(agents),
        "by_k": {str(k): interval_study(rows, agents, tasks, k, rng, pilots, replicates) for k in sizes if k < len(agents)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("caches", type=Path, nargs="+", help="split caches in E046's layout")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--pilots", type=int, default=PILOTS)
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    args = parser.parse_args(argv)
    splits = {}
    for cache in args.caches:
        rows, universe, _ = e046.load_split(cache)
        name = (cache / "SPLIT").read_text(encoding="utf-8").strip() if (cache / "SPLIT").exists() else cache.name
        splits[name] = study_by_k(rows, universe, args.seed, pilots=args.pilots, replicates=args.replicates)
    summary = {
        "experiment": "X4-intervals",
        "status": "exploratory: not preregistered; on splits E046 already opened it is post-hoc",
        "seed": args.seed,
        "frozen_e046_sha256": hashlib.sha256(Path(e046.__file__).read_bytes()).hexdigest(),
        "splits": splits,
    }
    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
