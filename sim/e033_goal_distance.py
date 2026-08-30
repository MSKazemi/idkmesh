"""E033 -- how far can the future goal drift before the archive stops helping?

E030 asked whether the Quality-Diversity archive's lead survives when the goal
the environment switches to is *not* one of the plausible goals the arms were
supplied with. It does: on a perfect panel the archive keeps ``3.308`` of its
``3.460`` lead over the best arm that holds no hypothesis, while the
majority-vote swarm loses all of its ``0.163`` and goes to ``-0.695``.

That measurement was taken at **one** substitute goal, and E030 says so in its
own limitations:

    The substitute goal is one point, not a distribution over unheld goals.

One point cannot distinguish the two stories that both fit it:

* the archive degrades **smoothly** with distance, and E030 happened to sample a
  distance at which 95.6% of the lead survives; or
* the archive is fine out to some radius and then **falls off a cliff**, and
  E030 happened to sample inside the safe radius.

The two have opposite engineering consequences. Under the first, retained
diversity buys a graceful, budgetable margin. Under the second it buys a
guarantee that holds until it doesn't, and the useful number is the radius, not
the retention percentage.

E033 sweeps the distance.

The axis
--------

:func:`distance_to_supplied` is the Euclidean distance from a goal to the
*nearest* member of :data:`emergence_sim.PLAUSIBLE_GOALS`. It is ``0.0`` when
the future goal is in the box -- E024's original setting, and E030's ``held``
condition -- and grows as the environment moves somewhere nobody proposed.

The supplied set's own mean pairwise spread is ``0.237``, and E030's substitute
sits at ``0.206``. So the published finding lives just inside one set-spread of
the box, which is exactly the region where a cliff would be invisible.

The confound, and the two controls
----------------------------------

``PLAUSIBLE_GOALS`` contains ``INITIAL_GOAL``, so the distance to the set can
never exceed the distance from the starting goal. Pushing the future goal away
from the box therefore also makes the *change itself* bigger, and a bigger
change is harder for every arm -- including the arms that never read the box. A
naive sweep would show every arm falling and could not attribute any of it to
membership.

Two independent controls separate the two:

1. **The lead statistic.** Every number reported here is
   ``mean(arm) - mean(best arm that holds no hypothesis)``, the statistic E030
   defined for this exact reason, computed by the same rule over the same arm
   partition. A goal that is merely harder moves the reference arm too and
   cancels.
2. **The matched ladder.** :data:`MATCHED_RINGS` sweeps the distance to the set
   while holding the distance from ``INITIAL_GOAL`` fixed at
   :data:`MATCHED_CHANGE_SIZE` -- which is E030's substitute's own change size,
   so E030's measured point lies *on* the matched ladder rather than beside it.
   Along that ladder the world moves exactly as far in every ring; only its
   direction relative to the box changes.

:data:`FREE_RINGS` drops the change-size constraint and runs further out, to
``0.60``, past where the matched ladder can reach. Distance to the set is
bounded above by distance from ``INITIAL_GOAL``, so a matched ring at ``0.40``
would require the future goal to be further from the box than it is from where
it started, which is geometrically impossible.

Goals per ring
--------------

Each ring carries :data:`GOALS_PER_RING` distinct goals rather than one, chosen
by farthest-point selection from the admissible band so they spread around the
ring instead of clustering in one direction. That is the direct answer to
E030's limitation: a ring statistic is a mean over goals *at* that distance, and
its interval is the spread across those goals, so a result cannot be an accident
of which single substitute was picked.

What a null result would and would not mean
-------------------------------------------

Six goals per ring is a small sample of a four-dimensional ring, and the ring
interval is a t-interval on those six. A ring difference that does not resolve
here is not evidence of no difference; :func:`classify_decay` reports
``unresolved`` for that case and never ``flat`` unless the endpoints themselves
fail to separate. The label is secondary in any case -- every step delta, share,
and interval is in the artifact so a reader can apply their own rule.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim import e027_defect_propagation as e027  # noqa: E402
from sim import e030_supplied_goal_membership as e030  # noqa: E402
from sim import matched_budget_emergence as mbe  # noqa: E402
import sim.emergence_sim as sim  # noqa: E402

EXPERIMENT_ID = "E033"
EXPERIMENT = "goal-distance-sweep-v1"

# The arm partition is E030's. It is asserted against E030's committed artifact
# by the test suite rather than imported, because E030 builds it as a local and
# a silent divergence would make two experiments' "lead" mean different things.
HYPOTHESIS_FREE = ("random", "scalar", "planner")
HYPOTHESIS_HOLDING = ("qd", "majority")

# d(INITIAL_GOAL, E030's substitute). Holding the change size here puts E030's
# published measurement on the matched ladder instead of near it.
MATCHED_CHANGE_SIZE = 0.391918

# E030's substitute's own distance to the set, carried as a ring so the ladder
# passes exactly through the published point.
E030_SUBSTITUTE_RING = 0.206398

MATCHED_RINGS: Tuple[float, ...] = (
    0.05,
    0.10,
    0.15,
    E030_SUBSTITUTE_RING,
    0.25,
    0.30,
    0.35,
)
FREE_RINGS: Tuple[float, ...] = (
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.50,
    0.60,
)
LADDERS = ("matched", "free")

GOALS_PER_RING = 6
RING_TOLERANCE = 0.01
POOL_DRAWS = 600_000
POOL_SEED = 20260830

# E030's settings, unchanged, so the two anchors reproduce its perfect-panel
# cell exactly rather than approximately.
DEFAULT_SEEDS = e030.DEFAULT_SEEDS
DEFAULT_SEED_START = 1
DEFAULT_AGENTS = e030.DEFAULT_AGENTS
DEFAULT_GENERATIONS = e030.DEFAULT_GENERATIONS
DEFAULT_CHANGE_AT = e030.DEFAULT_CHANGE_AT
DEFAULT_BINS = e030.DEFAULT_BINS
DEFAULT_PANEL = "perfect"

# A single step is called a cliff only if it carries at least this share of the
# whole decline. 0.6 is stated up front rather than fitted; the raw share is in
# the artifact so a reader can move it.
CLIFF_SHARE = 0.6

_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def _t95(df: int) -> float:
    if df < 1:
        raise ValueError("a t interval needs at least two observations")
    return _T95.get(df, 1.96)


# --------------------------------------------------------------------------
# geometry


def distance_to_supplied(goal: Sequence[float]) -> float:
    """Euclidean distance from ``goal`` to the nearest supplied hypothesis."""
    return min(math.dist(tuple(goal), member) for member in sim.PLAUSIBLE_GOALS)


def distance_from_initial(goal: Sequence[float]) -> float:
    return math.dist(tuple(goal), sim.INITIAL_GOAL)


def simplex_pool(draws: int = POOL_DRAWS, seed: int = POOL_SEED) -> List[Tuple[float, ...]]:
    """Uniform draws from the 4-simplex of goal weights.

    Normalised exponentials, which is uniform on the simplex, so a ring's goals
    are a fair sample of the goals at that distance rather than a sample of
    whatever a hand-written construction happens to reach.
    """
    rng = random.Random(seed)
    pool: List[Tuple[float, ...]] = []
    width = len(sim.INITIAL_GOAL)
    for _ in range(draws):
        raw = [rng.expovariate(1.0) for _ in range(width)]
        total = sum(raw)
        pool.append(tuple(value / total for value in raw))
    return pool


def admissible(
    pool: Sequence[Sequence[float]],
    *,
    ring: float,
    matched: bool,
    tolerance: float = RING_TOLERANCE,
    change_size: float = MATCHED_CHANGE_SIZE,
) -> List[Tuple[float, ...]]:
    """Pool members within ``tolerance`` of the ring, and of the change size."""
    hits: List[Tuple[float, ...]] = []
    for goal in pool:
        if abs(distance_to_supplied(goal) - ring) > tolerance:
            continue
        if matched and abs(distance_from_initial(goal) - change_size) > tolerance:
            continue
        hits.append(tuple(goal))
    return hits


def ring_goals(
    pool: Sequence[Sequence[float]],
    *,
    ring: float,
    matched: bool,
    count: int = GOALS_PER_RING,
    tolerance: float = RING_TOLERANCE,
    change_size: float = MATCHED_CHANGE_SIZE,
) -> List[Tuple[float, ...]]:
    """``count`` goals spread around ``ring``, chosen deterministically.

    Farthest-point selection: start from the admissible goal closest to the
    ring's exact target and repeatedly add whichever admissible goal is furthest
    from everything already chosen. The result depends only on the pool, so it
    is reproducible and does not drift with an rng call added elsewhere.

    Raises if the band is too thin to fill, so an infeasible ring fails loudly
    instead of silently returning a smaller, differently-weighted sample.
    """
    hits = admissible(
        pool, ring=ring, matched=matched, tolerance=tolerance, change_size=change_size
    )
    if len(hits) < count:
        raise ValueError(
            f"ring {ring} ({'matched' if matched else 'free'}) admits only "
            f"{len(hits)} goals, need {count}"
        )
    seed_goal = min(hits, key=lambda g: abs(distance_to_supplied(g) - ring))
    chosen = [seed_goal]
    remaining = [g for g in hits if g != seed_goal]
    while len(chosen) < count:
        far = max(remaining, key=lambda g: min(math.dist(g, c) for c in chosen))
        chosen.append(far)
        remaining = [g for g in remaining if g != far]
    return chosen


def ladder(
    name: str,
    *,
    pool: Sequence[Sequence[float]] | None = None,
    count: int = GOALS_PER_RING,
    tolerance: float = RING_TOLERANCE,
) -> List[Dict[str, Any]]:
    """The ordered rings of one ladder, each with its measured goals."""
    if name not in LADDERS:
        raise ValueError(f"unknown ladder: {name!r}")
    if pool is None:
        pool = simplex_pool()
    rings = MATCHED_RINGS if name == "matched" else FREE_RINGS
    matched = name == "matched"
    return [
        {
            "target_distance_to_supplied": target,
            "goals": [
                {
                    "goal": [round(w, 9) for w in goal],
                    "distance_to_supplied": round(distance_to_supplied(goal), 6),
                    "distance_from_initial": round(distance_from_initial(goal), 6),
                    "is_supplied_member": tuple(goal) in sim.PLAUSIBLE_GOALS,
                }
                for goal in ring_goals(
                    pool, ring=target, matched=matched, count=count, tolerance=tolerance
                )
            ],
        }
        for target in rings
    ]


# --------------------------------------------------------------------------
# measurement


def lead_table(values: Dict[str, List[float]], threshold: float) -> Dict[str, Any]:
    """E030's advantage block for a single goal.

    The reference arm is *named*, not just valued: if it ever switches between
    rings the ladder is comparing two different baselines and the reader has to
    know.
    """
    means = {arm: statistics.fmean(values[arm]) for arm in mbe.STRATEGIES}
    reference_arm = max(HYPOTHESIS_FREE, key=lambda arm: means[arm])
    reference = means[reference_arm]
    return {
        "means": {arm: round(means[arm], 6) for arm in mbe.STRATEGIES},
        "reference_arm": reference_arm,
        "best_hypothesis_free_arm": round(reference, 6),
        "lead_over_hypothesis_free": {
            arm: round(means[arm] - reference, 6) for arm in HYPOTHESIS_HOLDING
        },
        "catastrophic_seeds": {
            arm: sum(1 for value in values[arm] if value < threshold)
            for arm in mbe.STRATEGIES
        },
    }


def _panel(name: str) -> "sim.VerificationConfig | None":
    if name == "perfect":
        # E030's perfect condition passes `None`, not `VerificationConfig()`.
        # They are not interchangeable here: `None` skips the verifier draw
        # entirely, so the arms consume a different rng stream.
        return None
    if name not in e027.PANELS:
        raise ValueError(f"unknown panel: {name!r}")
    return e027.PANELS[name]


def measure_goal(job: Dict[str, Any]) -> Dict[str, Any]:
    """One goal, every arm, every seed. Top-level so it can be pooled."""
    values = e030.per_seed_auc(
        seeds=job["seeds"],
        seed_start=job["seed_start"],
        agents=job["agents"],
        generations=job["generations"],
        change_at=job["change_at"],
        bins=job["bins"],
        verification=_panel(job["panel"]),
        goal=tuple(job["goal"]),
    )
    threshold = mbe.CATASTROPHE_FRACTION * (job["generations"] - job["change_at"])
    return {
        "goal": [round(w, 9) for w in job["goal"]],
        "distance_to_supplied": round(distance_to_supplied(job["goal"]), 6),
        "distance_from_initial": round(distance_from_initial(job["goal"]), 6),
        **lead_table(values, threshold),
    }


def _run_jobs(jobs: List[Dict[str, Any]], jobs_count: int) -> List[Dict[str, Any]]:
    """Every job, in input order. ``jobs_count`` changes speed, never output.

    Each job re-points the environment's future goal in module globals, so the
    workers must be processes rather than threads; with processes each job owns
    its own copy and the seeds it consumes do not depend on the worker count.
    """
    if jobs_count <= 1:
        return [measure_goal(job) for job in jobs]
    with multiprocessing.get_context("fork").Pool(jobs_count) as pool:
        return list(pool.map(measure_goal, jobs, chunksize=1))


def _ring_statistic(goal_results: Sequence[Dict[str, Any]], arm: str) -> Dict[str, Any]:
    """Mean lead across a ring's goals, with a t-interval on the goal spread."""
    leads = [result["lead_over_hypothesis_free"][arm] for result in goal_results]
    mean = statistics.fmean(leads)
    if len(leads) > 1:
        error = statistics.stdev(leads) / math.sqrt(len(leads))
        half = _t95(len(leads) - 1) * error
    else:
        error = 0.0
        half = 0.0
    return {
        "goals": len(leads),
        "lead_mean": round(mean, 6),
        "lead_min": round(min(leads), 6),
        "lead_max": round(max(leads), 6),
        "standard_error": round(error, 6),
        "ci95_low": round(mean - half, 6),
        "ci95_high": round(mean + half, 6),
    }


def _half_width(ring: Dict[str, Any]) -> float:
    return (ring["ci95_high"] - ring["ci95_low"]) / 2.0


def _disjoint(lower: Dict[str, Any], upper: Dict[str, Any]) -> bool:
    return (
        lower["ci95_high"] < upper["ci95_low"] or upper["ci95_high"] < lower["ci95_low"]
    )


def classify_decay(rings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Is the lead's decline with distance spread out, or is it one step?

    ``smooth`` -- the endpoints separate and no single step carries
    :data:`CLIFF_SHARE` of the decline. ``cliff`` -- one resolved step carries
    at least that share. ``flat`` -- the ends do not separate, the whole decline
    fits inside the endpoint margin, *and* that margin is narrower than the
    near-end lead, so a decline the size of the lead itself would have been
    visible. ``unresolved`` -- everything else, including the case that looks
    flat only because the intervals are too wide to see anything, which is a
    different statement and must not borrow the same word.
    """
    if len(rings) < 2:
        return {"shape": "unresolved", "reason": "fewer than two rings"}
    steps = []
    for lower, upper in zip(rings, rings[1:]):
        drop = lower["lead_mean"] - upper["lead_mean"]
        steps.append(
            {
                "from_distance": lower["target_distance_to_supplied"],
                "to_distance": upper["target_distance_to_supplied"],
                "lead_drop": round(drop, 6),
                "resolved": _disjoint(lower, upper),
            }
        )
    declines = [max(0.0, step["lead_drop"]) for step in steps]
    total = sum(declines)
    largest = max(declines) if declines else 0.0
    share = round(largest / total, 6) if total > 0 else 0.0
    endpoints_separate = _disjoint(rings[0], rings[-1])
    resolved = [step for step in steps if step["resolved"] and step["lead_drop"] > 0]
    total_decline = rings[0]["lead_mean"] - rings[-1]["lead_mean"]
    margin = _half_width(rings[0]) + _half_width(rings[-1])
    within_margin = abs(total_decline) <= margin
    # A ladder is only entitled to say "flat" if it could have seen a decline
    # the size of the lead it started with. Otherwise it saw nothing, which is
    # not the same finding.
    has_power = margin < abs(rings[0]["lead_mean"])
    if not endpoints_separate and not resolved:
        shape = "flat" if (within_margin and has_power) else "unresolved"
    elif resolved and share >= CLIFF_SHARE and largest == max(
        step["lead_drop"] for step in resolved
    ):
        shape = "cliff"
    elif endpoints_separate and share < CLIFF_SHARE:
        shape = "smooth"
    else:
        shape = "unresolved"
    return {
        "shape": shape,
        "steps": steps,
        "total_decline": round(total_decline, 6),
        "endpoint_margin": round(margin, 6),
        "decline_within_endpoint_margin": within_margin,
        "could_resolve_a_decline_the_size_of_the_lead": has_power,
        "largest_step_decline": round(largest, 6),
        "largest_step_share": share,
        "uniform_share": round(1.0 / len(steps), 6),
        "resolved_declining_steps": len(resolved),
        "endpoints_separate": endpoints_separate,
        "cliff_share_threshold": CLIFF_SHARE,
    }


# --------------------------------------------------------------------------
# the discriminability control


DISCRIMINABILITY_DRAWS = 200_000
DISCRIMINABILITY_SEED = 20260830


def goal_discriminability(
    goal: Sequence[float], candidates: Sequence["sim.Candidate"]
) -> Dict[str, float]:
    """How much artifact choice is worth under ``goal``, on a shared pool.

    ``headroom`` is the attainable ceiling minus the mean over viable
    candidates: the value a system gets for choosing well rather than at random.
    If it shrank as the goal moved away from the supplied set, a shrinking lead
    would mean only that nothing helps out there, and would say nothing about
    the archive.
    """
    values = [sim.unchecked_utility(candidate, goal) for candidate in candidates]
    ceiling = max(values)
    mean = statistics.fmean(values)
    return {
        "attainable_ceiling": round(ceiling, 6),
        "mean_over_viable": round(mean, 6),
        "headroom": round(ceiling - mean, 6),
        "spread_over_viable": round(statistics.pstdev(values), 6),
    }


def ladder_discriminability(
    ladder_name: str,
    *,
    count: int = GOALS_PER_RING,
    tolerance: float = RING_TOLERANCE,
    pool_draws: int = POOL_DRAWS,
    draws: int = DISCRIMINABILITY_DRAWS,
    seed: int = DISCRIMINABILITY_SEED,
) -> Dict[str, Any]:
    """:func:`goal_discriminability` for every goal of a ladder, plus the three
    published goals, all scored on one pool so the rings are comparable."""
    candidates = [
        sim.Candidate(traits) for traits in e030._reference_pool(draws, seed)
    ]
    if not candidates:  # pragma: no cover - only with a degenerate draw count
        raise ValueError("reference pool is empty")
    rungs = ladder(ladder_name, pool=simplex_pool(draws=pool_draws), count=count, tolerance=tolerance)
    rings = []
    for rung in rungs:
        rows = [
            goal_discriminability(tuple(entry["goal"]), candidates)
            for entry in rung["goals"]
        ]
        rings.append(
            {
                "target_distance_to_supplied": rung["target_distance_to_supplied"],
                "mean_distance_to_supplied": round(
                    statistics.fmean(e["distance_to_supplied"] for e in rung["goals"]), 6
                ),
                "mean_headroom": round(statistics.fmean(r["headroom"] for r in rows), 6),
                "mean_attainable_ceiling": round(
                    statistics.fmean(r["attainable_ceiling"] for r in rows), 6
                ),
                "mean_spread_over_viable": round(
                    statistics.fmean(r["spread_over_viable"] for r in rows), 6
                ),
                "goal_results": rows,
            }
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "ladder": ladder_name,
        "draws": draws,
        "seed": seed,
        "viable_pool": len(candidates),
        "goals_per_ring": count,
        "rings": rings,
        "published_goals": {
            "initial": goal_discriminability(sim.INITIAL_GOAL, candidates),
            "changed": goal_discriminability(sim.CHANGED_GOAL, candidates),
            "e030_substitute": goal_discriminability(e030.UNHELD_GOAL, candidates),
        },
    }


# --------------------------------------------------------------------------
# sweep


def _settings(**kwargs: Any) -> Dict[str, Any]:
    settings = {
        "seeds": DEFAULT_SEEDS,
        "seed_start": DEFAULT_SEED_START,
        "agents": DEFAULT_AGENTS,
        "generations": DEFAULT_GENERATIONS,
        "change_at": DEFAULT_CHANGE_AT,
        "bins": DEFAULT_BINS,
        "panel": DEFAULT_PANEL,
    }
    settings.update({k: v for k, v in kwargs.items() if v is not None})
    return settings


def anchors(**kwargs: Any) -> Dict[str, Any]:
    """E030's two published points, rerun here.

    Not decoration: these must reproduce E030's committed perfect-panel cell
    number for number. If they do not, the ladder is measuring something E030
    was not, and every comparison to its finding is void.
    """
    settings = _settings(**kwargs)
    jobs = [
        {**settings, "goal": tuple(sim.CHANGED_GOAL)},
        {**settings, "goal": tuple(e030.UNHELD_GOAL)},
    ]
    held, unheld = _run_jobs(jobs, 1)
    return {"held": held, "unheld": unheld}


def sweep(
    ladder_name: str,
    *,
    jobs: int = 1,
    count: int = GOALS_PER_RING,
    tolerance: float = RING_TOLERANCE,
    pool_draws: int = POOL_DRAWS,
    with_anchors: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    settings = _settings(**kwargs)
    pool = simplex_pool(draws=pool_draws)
    rungs = ladder(ladder_name, pool=pool, count=count, tolerance=tolerance)
    queue: List[Dict[str, Any]] = []
    for rung in rungs:
        for entry in rung["goals"]:
            queue.append({**settings, "goal": tuple(entry["goal"])})
    measured = _run_jobs(queue, jobs)

    cursor = 0
    ring_rows: List[Dict[str, Any]] = []
    for rung in rungs:
        chunk = measured[cursor : cursor + len(rung["goals"])]
        cursor += len(rung["goals"])
        row: Dict[str, Any] = {
            "target_distance_to_supplied": rung["target_distance_to_supplied"],
            "mean_distance_to_supplied": round(
                statistics.fmean(r["distance_to_supplied"] for r in chunk), 6
            ),
            "mean_distance_from_initial": round(
                statistics.fmean(r["distance_from_initial"] for r in chunk), 6
            ),
            "reference_arms": sorted({r["reference_arm"] for r in chunk}),
            "goal_results": chunk,
        }
        for arm in HYPOTHESIS_HOLDING:
            row[arm] = _ring_statistic(chunk, arm)
        for arm in mbe.STRATEGIES:
            row.setdefault("mean_catastrophic_seeds", {})[arm] = round(
                statistics.fmean(r["catastrophic_seeds"][arm] for r in chunk), 3
            )
        ring_rows.append(row)

    decay = {}
    for arm in HYPOTHESIS_HOLDING:
        decay[arm] = classify_decay(
            [
                {
                    "target_distance_to_supplied": row["target_distance_to_supplied"],
                    **row[arm],
                }
                for row in ring_rows
            ]
        )

    report: Dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "ladder": ladder_name,
        "metric": "post_change_utility_auc",
        "catastrophe_utility_auc_threshold": round(
            mbe.CATASTROPHE_FRACTION
            * (settings["generations"] - settings["change_at"]),
            6,
        ),
        "goals_per_ring": count,
        "ring_tolerance": tolerance,
        "pool_draws": pool_draws,
        "pool_seed": POOL_SEED,
        "matched_change_size": MATCHED_CHANGE_SIZE if ladder_name == "matched" else None,
        "hypothesis_free_arms": list(HYPOTHESIS_FREE),
        "hypothesis_holding_arms": list(HYPOTHESIS_HOLDING),
        "supplied_set_dispersion": round(
            statistics.fmean(
                math.dist(a, b)
                for i, a in enumerate(sim.PLAUSIBLE_GOALS)
                for b in sim.PLAUSIBLE_GOALS[i + 1 :]
            ),
            6,
        ),
        "rings": ring_rows,
        "decay": decay,
        **settings,
    }
    if with_anchors:
        report["anchors"] = anchors(**kwargs)
    return report


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E033 goal-distance sweep")
    parser.add_argument("--ladder", choices=LADDERS, default="matched")
    parser.add_argument("--seeds", type=int, default=None)
    parser.add_argument("--seed-start", type=int, default=None)
    parser.add_argument("--agents", type=int, default=None)
    parser.add_argument("--generations", type=int, default=None)
    parser.add_argument("--change-at", type=int, default=None)
    parser.add_argument("--bins", type=int, default=None)
    parser.add_argument("--panel", default=None)
    parser.add_argument("--goals-per-ring", type=int, default=GOALS_PER_RING)
    parser.add_argument("--tolerance", type=float, default=RING_TOLERANCE)
    parser.add_argument("--pool-draws", type=int, default=POOL_DRAWS)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--no-anchors", action="store_true")
    parser.add_argument(
        "--discriminability",
        action="store_true",
        help="score the ladder's goals for headroom instead of running the arms",
    )
    parser.add_argument("--draws", type=int, default=DISCRIMINABILITY_DRAWS)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    if args.discriminability:
        report = ladder_discriminability(
            args.ladder,
            count=args.goals_per_ring,
            tolerance=args.tolerance,
            pool_draws=args.pool_draws,
            draws=args.draws,
        )
        text = json.dumps(report, indent=2, sort_keys=True)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    report = sweep(
        args.ladder,
        jobs=args.jobs,
        count=args.goals_per_ring,
        tolerance=args.tolerance,
        pool_draws=args.pool_draws,
        with_anchors=not args.no_anchors,
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=args.bins,
        panel=args.panel,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
