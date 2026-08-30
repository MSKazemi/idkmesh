"""E038 -- why does a worse verifier help the archive?

[E037](../experiments/E037-ladder-under-panels.md) measured something it could
not explain. Weakening the panel from ``perfect`` to ``stress`` -- 25 verifiers
at ``0.55`` accuracy, ``0.9`` correlation and a ``0.4`` blind spot -- made the
Quality-Diversity archive's lead go *up*, from ``+1.189`` to ``+1.659``, and cut
its catastrophic seeds from ``808`` to ``138``. It also ruled out the two
obvious explanations: the archive is capacity-bound at the agent count on every
panel, so it is not absorbing more, and the gate's error is symmetric to within
``0.006`` and arm-blind to within ``0.02``, so it is not favouring anyone.

E037 recorded "why it improves is not established" and stopped there. E038 is
the follow-up, and its answer is that the second of those two findings is being
read wrongly.

The claim
---------

**An arm-blind gate is not an arm-neutral gate.** The panel errs at the same
rate for everyone, but an error is only harmful in the direction the arm is
exposed to, and the arms are not equally exposed. An arm whose proposals are
mostly viable can only be hurt by a false *reject*; an arm whose proposals are
mostly non-viable is mainly exposed to false *accepts*, which put unsound work
into its population.

:func:`base_viability` measures that exposure directly, on the ``perfect`` panel
where the gate makes no errors at all and the accept rate therefore *is* the
arm's true rate of proposing viable work. If the arms' base rates are close,
this explanation is dead and E037's question is still open.

Why this matters beyond the arena
---------------------------------

If it holds, "how accurate is the review panel" is the wrong question to ask
about a contribution pipeline on its own. The same panel is a different
instrument for a careful contributor and a scattershot one, and the pipeline's
weakest arm sets what a reviewer's error rate costs.

What this cannot show
---------------------

E038 measures exposure and damage. It does not manipulate exposure: nothing here
holds an arm's strategy fixed while moving its base viability, so the link
between the two is an association across five arms, not an intervention.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Sequence

import sim.matched_budget_emergence as mbe
import sim.e030_supplied_goal_membership as e030
import sim.e033_goal_distance as e033
import sim.e034_goal_direction as e034
import sim.e037_ladder_under_panels as e037

EXPERIMENT_ID = "E038"
EXPERIMENT = "symmetric-gate-asymmetric-burden-v1"

#: The same three panels, in the same order, as E037.
PANEL_ORDER = e037.PANEL_ORDER
BASELINE_PANEL = e037.BASELINE_PANEL
ARCHIVE_ARM = e037.ARCHIVE_ARM

#: Seeds per goal per panel. Larger than E037's leakage probe (20) because this
#: record's verdicts are per-arm rankings rather than a single yes/no.
DEFAULT_SEEDS = 40
DEFAULT_SEED_START = 1
DEFAULT_AGENTS = e033.DEFAULT_AGENTS
DEFAULT_GENERATIONS = e033.DEFAULT_GENERATIONS
DEFAULT_CHANGE_AT = e033.DEFAULT_CHANGE_AT
DEFAULT_BINS = e033.DEFAULT_BINS

#: Two arms count as having a different base viability only if they are at least
#: this far apart. Stated up front so "sharply different" is not decided after
#: seeing the numbers.
VIABILITY_GAP = 0.20

METRIC_KEYS = (
    "proposal_attempts",
    "viable_evaluations",
    "verification_attempts",
    "verification_accepts",
    "false_accepts",
    "false_rejects",
    "post_change_utility_auc",
)


def measure(
    goals: Dict[str, Sequence[float]],
    *,
    panels: Sequence[str] = PANEL_ORDER,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = DEFAULT_SEED_START,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
) -> Dict[str, Any]:
    """Per-arm raw counters under each panel, summed over seeds and goals.

    Counters rather than rates: a rate computed per seed and then averaged is
    not the rate of the pooled run, and the arms have different denominators.
    """
    rows: Dict[str, Any] = {}
    for panel in panels:
        config = e033._panel(panel)
        totals = {
            arm: {key: 0.0 for key in METRIC_KEYS} for arm in mbe.STRATEGIES
        }
        runs = 0
        for goal in goals.values():
            with e030.future_goal(tuple(goal)):
                for offset in range(seeds):
                    record = mbe.run_seed(
                        seed=seed_start + offset,
                        agents=agents,
                        generations=generations,
                        change_at=change_at,
                        bins=bins,
                        verification=config,
                    )
                    runs += 1
                    for result in record["results"]:
                        bucket = totals[result["strategy"]]
                        for key in METRIC_KEYS:
                            bucket[key] += result[key]
        rows[panel] = {
            arm: {
                **{key: round(bucket[key], 6) for key in METRIC_KEYS},
                "accept_rate": round(
                    bucket["verification_accepts"] / bucket["verification_attempts"], 6
                )
                if bucket["verification_attempts"]
                else 0.0,
                "mean_utility_auc": round(
                    bucket["post_change_utility_auc"] / runs, 6
                ),
            }
            for arm, bucket in totals.items()
        }
    return {"per_panel": rows, "runs_per_panel": runs}


def base_viability(rows: Dict[str, Any]) -> Dict[str, float]:
    """Each arm's true rate of proposing viable work.

    Read off the ``perfect`` panel, where the gate makes no errors, so the
    accept rate *is* the truth rate rather than an estimate of it.
    """
    panel = rows[BASELINE_PANEL]
    return {
        arm: round(
            panel[arm]["viable_evaluations"] / panel[arm]["proposal_attempts"], 6
        )
        if panel[arm]["proposal_attempts"]
        else 0.0
        for arm in mbe.STRATEGIES
    }


def exposure(rows: Dict[str, Any], panel: str) -> Dict[str, Any]:
    """Which direction the gate's errors actually hit each arm.

    ``false_accept_share`` is the fraction of an arm's verification errors that
    were accepts. An arm proposing mostly viable work can barely have any, and
    an arm proposing mostly junk can barely have anything else.
    """
    result = {}
    for arm in mbe.STRATEGIES:
        row = rows[panel][arm]
        errors = row["false_accepts"] + row["false_rejects"]
        result[arm] = {
            "false_accepts": row["false_accepts"],
            "false_rejects": row["false_rejects"],
            "errors": errors,
            "false_accept_share": round(row["false_accepts"] / errors, 6)
            if errors
            else 0.0,
        }
    return result


def damage(rows: Dict[str, Any], panel: str) -> Dict[str, Any]:
    """Change in each arm's mean utility from the baseline panel to ``panel``."""
    base, other = rows[BASELINE_PANEL], rows[panel]
    return {
        arm: {
            "baseline_utility": base[arm]["mean_utility_auc"],
            "panel_utility": other[arm]["mean_utility_auc"],
            "change": round(
                other[arm]["mean_utility_auc"] - base[arm]["mean_utility_auc"], 6
            ),
        }
        for arm in mbe.STRATEGIES
    }


#: Written down before the sweep. Clause 2 is the one that can kill the whole
#: explanation on its own: if the arms' base viabilities are close together,
#: differential exposure cannot explain anything.
PREDICTION: Dict[str, Any] = {
    "question": "E037 Result 2 -- why does the archive's lead rise as the panel weakens?",
    "claim": "an arm-blind gate is not an arm-neutral gate, because the arms are "
    "not equally exposed to the two directions of error",
    "clauses": {
        "arms_differ_sharply_in_base_viability": True,
        "the_least_viable_arm_is_the_most_exposed_to_false_accepts": True,
        "the_least_viable_arm_takes_the_worst_utility_damage": True,
        "the_archive_is_not_the_most_damaged_arm": True,
    },
}


def verdicts(rows: Dict[str, Any], panels: Sequence[str]) -> Dict[str, Any]:
    """Score :data:`PREDICTION` -- a pure function of the measured counters."""
    viability = base_viability(rows)
    weakest = min(viability, key=lambda arm: viability[arm])
    # Rounded before the comparison: the viabilities are themselves rounded to
    # 6 places, so an exactly-at-threshold spread like 0.95 - 0.75 comes out as
    # 0.19999999999999996 and would fail a bar it is meant to sit on.
    spread = round(max(viability.values()) - min(viability.values()), 6)
    imperfect = [name for name in panels if name != BASELINE_PANEL]

    most_exposed = {
        panel: max(
            exposure(rows, panel),
            key=lambda arm: exposure(rows, panel)[arm]["false_accept_share"],
        )
        for panel in imperfect
    }
    worst_damaged = {
        panel: min(damage(rows, panel), key=lambda arm: damage(rows, panel)[arm]["change"])
        for panel in imperfect
    }
    clauses = {
        "arms_differ_sharply_in_base_viability": spread >= VIABILITY_GAP,
        "the_least_viable_arm_is_the_most_exposed_to_false_accepts": all(
            most_exposed[panel] == weakest for panel in imperfect
        ),
        "the_least_viable_arm_takes_the_worst_utility_damage": all(
            worst_damaged[panel] == weakest for panel in imperfect
        ),
        "the_archive_is_not_the_most_damaged_arm": all(
            worst_damaged[panel] != ARCHIVE_ARM for panel in imperfect
        ),
    }
    expected = PREDICTION["clauses"]
    met = {key: clauses[key] == expected[key] for key in expected}
    return {
        "base_viability": viability,
        "base_viability_spread": spread,
        "least_viable_arm": weakest,
        "most_false_accept_exposed_arm": most_exposed,
        "worst_damaged_arm": worst_damaged,
        "clauses": clauses,
        "met": met,
        "met_count": sum(met.values()),
        "clause_count": len(met),
        "supported": all(met.values()),
        "partially_supported": any(met.values()) and not all(met.values()),
    }


def report(
    goals: Dict[str, Sequence[float]], *, panels: Sequence[str] = PANEL_ORDER, **kwargs
) -> Dict[str, Any]:
    measured = measure(goals, panels=panels, **kwargs)
    rows = measured["per_panel"]
    ordered = [name for name in panels]
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "panels": ordered,
        "baseline_panel": BASELINE_PANEL,
        "viability_gap": VIABILITY_GAP,
        "arms": list(mbe.STRATEGIES),
        "goals": {trait: [round(w, 9) for w in goal] for trait, goal in goals.items()},
        "seeds": kwargs.get("seeds", DEFAULT_SEEDS),
        "seed_start": kwargs.get("seed_start", DEFAULT_SEED_START),
        "agents": kwargs.get("agents", DEFAULT_AGENTS),
        "generations": kwargs.get("generations", DEFAULT_GENERATIONS),
        "change_at": kwargs.get("change_at", DEFAULT_CHANGE_AT),
        "bins": kwargs.get("bins", DEFAULT_BINS),
        "runs_per_panel": measured["runs_per_panel"],
        "per_panel": rows,
        "exposure": {panel: exposure(rows, panel) for panel in ordered},
        "damage": {
            panel: damage(rows, panel) for panel in ordered if panel != BASELINE_PANEL
        },
        "prediction": PREDICTION,
        "verdicts": verdicts(rows, ordered),
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E038 symmetric gate, asymmetric burden"
    )
    parser.add_argument(
        "--sweep",
        required=True,
        help="an E034-shaped artifact to take the probe goals from",
    )
    parser.add_argument("--panel", action="append", default=None)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--change-at", type=int, default=DEFAULT_CHANGE_AT)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    sweep = json.loads(Path(args.sweep).read_text(encoding="utf-8"))
    payload = report(
        e037.leakage_goals(sweep),
        panels=tuple(args.panel) if args.panel else PANEL_ORDER,
        seeds=args.seeds,
        seed_start=args.seed_start,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
    )
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
