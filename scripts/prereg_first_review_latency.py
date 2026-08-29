#!/usr/bin/env python3
"""Pre-specified analysis for the first-review-latency -> recurrence hypothesis.

This script is the preregistration. It is committed before any datum exists that
could inform it, and it leaves no choice to be made at analysis time: the arms,
the boundary, the outcome window, the exclusions, the estimand, the priors, and
the minimum sample size are all constants below.

Running it on a snapshot that does not meet the pre-specified minimum returns
``analyzable: false`` and no estimate. That is the intended behaviour. An
estimate produced from an underpowered sample would be the exact result this
preregistration exists to prevent.

The protocol, its rationale, and its threats to validity are in
``docs/research/PREREG_FIRST_REVIEW_LATENCY_V1.md``. No causal claim is licensed
by the observational arm; see that document for the randomized design that would
be required.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.metric_uncertainty import beta_binomial_summary

PROTOCOL = "prereg-first-review-latency-v1"

# --- Pre-specified constants. Changing any of these forks the protocol. -------

# Issue 86 names the 72-hour boundary. It is fixed here so it cannot be chosen
# after seeing which cut separates the groups.
LATENCY_BOUNDARY_HOURS = 72.0

# A contributor recurs if they land a second merged pull request within this many
# days of their first one merging.
RECURRENCE_WINDOW_DAYS = 90

# Neither arm is analyzed until both reach this size. Below it the posterior is
# dominated by the prior and any reported difference is noise with a decimal point.
MINIMUM_UNITS_PER_ARM = 20

# Uniform Beta(1, 1). Deliberately not an informative prior: there is no prior
# evidence in this repository to be informed by.
ALPHA_PRIOR = 1.0
BETA_PRIOR = 1.0

# Deterministic grid for the posterior of the risk difference. No RNG, so the
# same snapshot yields the same numbers on any machine.
GRID_POINTS = 2001

ARM_FAST = "reviewed_within_boundary"
ARM_SLOW = "reviewed_after_boundary"
STRATUM_NEVER_REVIEWED = "never_independently_reviewed"


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _merged_units(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """One unit per author's earliest closed pull request in the window.

    The snapshot does not carry a merged flag, so closure is the available
    proxy. That substitution is declared rather than hidden, and it is listed as
    a threat to validity in the protocol document.
    """
    earliest: dict[str, dict[str, Any]] = {}
    for row in snapshot.get("pull_requests") or []:
        author = row.get("author")
        closed_at = row.get("closed_at")
        if not isinstance(author, str) or not isinstance(closed_at, str):
            continue
        current = earliest.get(author)
        if current is None or closed_at < current["closed_at"]:
            earliest[author] = {"author": author, "closed_at": closed_at, "row": row}
    return [earliest[author] for author in sorted(earliest)]


def _later_closures(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    closures: dict[str, list[str]] = {}
    for row in snapshot.get("pull_requests") or []:
        author = row.get("author")
        closed_at = row.get("closed_at")
        if isinstance(author, str) and isinstance(closed_at, str):
            closures.setdefault(author, []).append(closed_at)
    return {author: sorted(values) for author, values in closures.items()}


def _assign(unit: dict[str, Any]) -> tuple[str, float | None]:
    row = unit["row"]
    ready_at = row.get("review_ready_at")
    reviewed_at = row.get("first_independent_review_at")
    if not isinstance(reviewed_at, str) or not isinstance(ready_at, str):
        return STRATUM_NEVER_REVIEWED, None
    hours = (_time(reviewed_at) - _time(ready_at)).total_seconds() / 3600.0
    arm = ARM_FAST if hours < LATENCY_BOUNDARY_HOURS else ARM_SLOW
    return arm, hours


def _recurred(author: str, first_closed: str, closures: dict[str, list[str]]) -> bool:
    deadline = _time(first_closed) + timedelta(days=RECURRENCE_WINDOW_DAYS)
    for closed_at in closures.get(author, []):
        moment = _time(closed_at)
        if moment > _time(first_closed) and moment <= deadline:
            return True
    return False


def _difference_posterior(
    fast: tuple[int, int], slow: tuple[int, int]
) -> dict[str, Any]:
    """Posterior of ``p_fast - p_slow`` on a fixed grid, by direct convolution.

    Exact enough to be reproducible and simple enough to be audited by hand;
    no sampling and no random seed are involved.
    """
    step = 1.0 / (GRID_POINTS - 1)
    grid = [index * step for index in range(GRID_POINTS)]

    def density(successes: int, trials: int) -> list[float]:
        alpha = ALPHA_PRIOR + successes - 1.0
        beta = BETA_PRIOR + (trials - successes) - 1.0
        raw = [
            (point**alpha if alpha != 0 else 1.0)
            * ((1.0 - point) ** beta if beta != 0 else 1.0)
            for point in grid
        ]
        total = sum(raw) * step
        return [value / total for value in raw] if total > 0 else raw

    fast_density = density(*fast)
    slow_density = density(*slow)

    mass_positive = 0.0
    mass_tie = 0.0
    mean = 0.0
    for fast_index, fast_value in enumerate(fast_density):
        if fast_value == 0.0:
            continue
        weight = fast_value * step
        for slow_index, slow_value in enumerate(slow_density):
            if slow_value == 0.0:
                continue
            joint = weight * slow_value * step
            difference = grid[fast_index] - grid[slow_index]
            mean += joint * difference
            if difference > 0.0:
                mass_positive += joint
            elif difference == 0.0:
                mass_tie += joint
    return {
        "model": "beta_binomial_difference_grid-v1",
        "grid_points": GRID_POINTS,
        "posterior_mean": round(mean, 6),
        "posterior_probability_fast_arm_higher": round(mass_positive, 6),
        # The continuous posterior assigns zero probability to an exact tie, so
        # this mass exists only because the grid is discrete. It is reported
        # rather than redistributed, because it bounds the grid's error: the
        # continuous probability lies within +/- this value.
        "grid_tie_mass": round(mass_tie, 6),
        "interpretation": "descriptive_association_not_a_causal_effect",
    }


def analyze(snapshot: dict[str, Any]) -> dict[str, Any]:
    units = _merged_units(snapshot)
    closures = _later_closures(snapshot)

    arms: dict[str, dict[str, int]] = {
        ARM_FAST: {"units": 0, "recurred": 0},
        ARM_SLOW: {"units": 0, "recurred": 0},
        STRATUM_NEVER_REVIEWED: {"units": 0, "recurred": 0},
    }
    latencies: dict[str, list[float]] = {ARM_FAST: [], ARM_SLOW: []}

    for unit in units:
        arm, hours = _assign(unit)
        arms[arm]["units"] += 1
        if _recurred(unit["author"], unit["closed_at"], closures):
            arms[arm]["recurred"] += 1
        if hours is not None:
            latencies[arm].append(hours)

    fast = arms[ARM_FAST]
    slow = arms[ARM_SLOW]
    analyzable = (
        fast["units"] >= MINIMUM_UNITS_PER_ARM and slow["units"] >= MINIMUM_UNITS_PER_ARM
    )

    result: dict[str, Any] = {
        "protocol": PROTOCOL,
        "repository": snapshot.get("repository"),
        "cutoff_at": snapshot.get("cutoff_at"),
        "specification": {
            "latency_boundary_hours": LATENCY_BOUNDARY_HOURS,
            "recurrence_window_days": RECURRENCE_WINDOW_DAYS,
            "minimum_units_per_arm": MINIMUM_UNITS_PER_ARM,
            "alpha_prior": ALPHA_PRIOR,
            "beta_prior": BETA_PRIOR,
            "unit": "author_earliest_closed_pull_request_in_window",
            "outcome": "second_closed_pull_request_by_same_author_within_window",
        },
        "arms": {
            name: {
                "units": counts["units"],
                "recurred": counts["recurred"],
                "posterior": beta_binomial_summary(
                    counts["recurred"],
                    counts["units"],
                    alpha_prior=ALPHA_PRIOR,
                    beta_prior=BETA_PRIOR,
                ),
            }
            for name, counts in sorted(arms.items())
        },
        "observed_latency_hours": {
            name: {
                "count": len(values),
                "minimum": round(min(values), 4) if values else None,
                "maximum": round(max(values), 4) if values else None,
            }
            for name, values in sorted(latencies.items())
        },
        "analyzable": analyzable,
        "authority": {"causal_claim": False, "policy_activation": False, "github_write": False},
    }

    if analyzable:
        result["risk_difference"] = _difference_posterior(
            (fast["recurred"], fast["units"]), (slow["recurred"], slow["units"])
        )
    else:
        result["not_analyzed_because"] = (
            f"each arm requires at least {MINIMUM_UNITS_PER_ARM} units; observed "
            f"{fast['units']} and {slow['units']}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    result = analyze(snapshot)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
