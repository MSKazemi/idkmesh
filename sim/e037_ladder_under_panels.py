"""E037 -- is E034's direction result about the goal geometry, or about a
perfect verifier?

E030 through E035 all share one setting they never varied: the verification
panel was perfect. Every candidate's true quality was observed exactly and for
free. E035 closed by naming that as the test that would move the mechanism::

    Next: every result here is on a perfect panel, and the arena's whole point
    is that verification is imperfect. The test that would move the mechanism
    now is E033's and E034's ladder on a panel with a non-zero blind-spot floor
    -- if the directional structure is a property of the goal geometry it
    should survive, and if it is a property of costless perfect verification it
    should not.

E037 is that test, and the prediction in :data:`PREDICTION` is E035's sentence
turned into four clauses that can each come out false.

Why no new simulation code
--------------------------

``sim/e033_goal_distance.py`` has always taken a ``panel`` setting and
``sim/e034_goal_direction.py`` has always forwarded it, so the two new arms are
E034's own sweep run with ``--panel measured`` and ``--panel stress``. Nothing
in the arena, the arms, or the ladder is touched, which is the point: if a
result moves, the panel moved it.

The panels are E027's, unchanged. ``measured`` is the one that matters. It holds
the *same 25 verifiers at the same 0.7956 accuracy* as ``independent`` and
differs only in correlation -- E036 showed that correlation, not accuracy, is
what a panel's blind spot is made of.

Why this comparison is paired and E035's was not
------------------------------------------------

E035 compared shells at different distances, so each shell drew its own goals
and only an unpaired test was available. Here the shell is *identical* -- same
distance, same pool, same seed, same selection -- so all three panels measure
the **same goals**. :func:`paired_shift` therefore differences the panels goal
by goal, which is both valid and much sharper.

That is a claim about the artifacts, not an assumption about them:
:func:`comparability` refuses any pair whose design differs in anything but the
panel, and :func:`goal_alignment` refuses to pair panels whose goal sets are not
identical. If either fails the comparison degrades to the unpaired ladder
statistics rather than reporting a paired number that is not paired.

The trap this design has to avoid
---------------------------------

``lead_over_hypothesis_free`` is measured against *the best hypothesis-free arm
for that goal*, chosen per goal by name. A panel that damages ``random`` more
than ``planner`` moves the baseline, so a lead that grew might mean the archive
improved or might mean its yardstick shrank. :func:`reference_arm_switches`
counts that directly, and :func:`absolute_shift` reports the archive's own mean
alongside the lead so the two cannot be confused.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import sim.matched_budget_emergence as mbe
import sim.e033_goal_distance as e033
import sim.e035_direction_across_shells as e035

EXPERIMENT_ID = "E037"
EXPERIMENT = "goal-direction-under-imperfect-panels-v1"

#: The panels compared, weakest verification last. ``perfect`` is E034's own
#: committed artifact, reused rather than recomputed.
PANEL_ORDER: Tuple[str, ...] = ("perfect", "measured", "stress")
BASELINE_PANEL = "perfect"

#: The arm under test and the other hypothesis-holding arm, named so a reader
#: never has to infer which column a number came from.
ARCHIVE_ARM = "qd"
CONSENSUS_ARM = "majority"

#: One bar for both records. E035 set it at the two-sided 0.01 critical value
#: for its smallest df, which is the Bonferroni-corrected 0.05 over five
#: preregistered ladders; reusing the constant is what makes an E037 "resolved"
#: mean the same thing as an E035 "resolved".
RESOLVED_T = e035.RESOLVED_T

#: Every design field that must match across panels for the comparison to be
#: about the panel. ``panel`` is deliberately absent -- it is the treatment.
DESIGN_KEYS: Tuple[str, ...] = (
    "agents",
    "bins",
    "catastrophe_utility_auc_threshold",
    "change_at",
    "descriptor_traits",
    "experiment",
    "experiment_id",
    "floor_traits",
    "generations",
    "goals_per_cell",
    "hypothesis_free_arms",
    "hypothesis_holding_arms",
    "metric",
    "minimum_reliability",
    "minimum_security",
    "seed_start",
    "seeds",
    "shell",
    "trait_categories",
    "unconstrained_traits",
    "weight_targets",
    "weight_tolerance",
)


def panel_of(report: Dict[str, Any]) -> str:
    return report["panel"]


def design_of(report: Dict[str, Any]) -> Dict[str, Any]:
    """The part of an artifact that must not vary across panels."""
    return {key: report[key] for key in DESIGN_KEYS if key in report}


def comparability(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Do these artifacts differ in the panel and nothing else?

    A cross-panel claim is only about the panel if every other setting is held.
    The differing keys are listed rather than summarised, so a failure says what
    moved instead of only that something did.
    """
    names = sorted(reports)
    base = design_of(reports[BASELINE_PANEL]) if BASELINE_PANEL in reports else None
    differing: Dict[str, List[str]] = {}
    if base is not None:
        for name in names:
            if name == BASELINE_PANEL:
                continue
            other = design_of(reports[name])
            keys = sorted(
                key
                for key in DESIGN_KEYS
                if base.get(key) != other.get(key)
            )
            if keys:
                differing[name] = keys
    return {
        "panels": names,
        "baseline_present": base is not None,
        "declared_panels": {name: panel_of(reports[name]) for name in names},
        "panel_labels_match_artifacts": all(
            panel_of(reports[name]) == name for name in names
        ),
        "differing_design_keys": differing,
        "differs_only_in_panel": base is not None and not differing,
    }


def goals_of(report: Dict[str, Any]) -> Dict[Tuple[float, ...], Dict[str, Any]]:
    """Every goal measured on one panel, keyed by the goal itself."""
    return {
        tuple(g["goal"]): g
        for trait in report["traits"].values()
        for cell in trait["cells"]
        for g in cell["goal_results"]
    }


def goal_alignment(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Do the panels measure the same goals, so differences can be paired?

    They should: the shell is deterministic in the pool seed and the distance.
    Checking is cheap and the alternative is a paired statistic computed over
    goals that were never paired.
    """
    sets = {name: set(goals_of(report)) for name, report in reports.items()}
    shared = set.intersection(*sets.values()) if sets else set()
    return {
        "goals_per_panel": {name: len(value) for name, value in sets.items()},
        "shared_goals": len(shared),
        "identical_goal_sets": all(value == shared for value in sets.values()),
    }


def _paired(differences: Sequence[float]) -> Dict[str, Any]:
    """Paired t on a list of per-goal differences."""
    mean = statistics.fmean(differences)
    error = statistics.stdev(differences) / math.sqrt(len(differences))
    if error:
        t = mean / error
    elif mean:
        # Every pair moved by exactly the same non-zero amount.
        t = math.copysign(math.inf, mean)
    else:
        # Nothing moved at all. That is the *absence* of a shift, and calling
        # it an infinitely well resolved one would invert the reading.
        t = 0.0
    return {
        "pairs": len(differences),
        "mean_difference": round(mean, 6),
        "standard_error": round(error, 6),
        "t": round(t, 6),
        "resolved": abs(t) > RESOLVED_T,
    }


def paired_shift(
    baseline: Dict[str, Any],
    other: Dict[str, Any],
    *,
    arm: str = ARCHIVE_ARM,
) -> Dict[str, Any]:
    """How far the arm's lead moves, goal by goal, from baseline to other."""
    left, right = goals_of(baseline), goals_of(other)
    shared = sorted(set(left) & set(right))
    differences = [
        right[goal]["lead_over_hypothesis_free"][arm]
        - left[goal]["lead_over_hypothesis_free"][arm]
        for goal in shared
    ]
    worse = sum(1 for value in differences if value < 0)
    return {
        **_paired(differences),
        "goals_where_lead_falls": worse,
        "share_where_lead_falls": round(worse / len(differences), 6),
    }


def absolute_shift(
    baseline: Dict[str, Any],
    other: Dict[str, Any],
    *,
    arm: str = ARCHIVE_ARM,
) -> Dict[str, Any]:
    """The arm's own score, not its lead -- the lead's denominator can move."""
    left, right = goals_of(baseline), goals_of(other)
    shared = sorted(set(left) & set(right))
    differences = [
        right[goal]["means"][arm] - left[goal]["means"][arm] for goal in shared
    ]
    return _paired(differences)


def reference_arm_switches(
    baseline: Dict[str, Any], other: Dict[str, Any]
) -> Dict[str, Any]:
    """How often the panel changes which hypothesis-free arm sets the bar.

    Every ``lead_over_hypothesis_free`` is relative to a per-goal winner. If the
    panel moves that winner, part of any change in the lead is a change of
    yardstick and must not be read as a change in the archive.
    """
    left, right = goals_of(baseline), goals_of(other)
    shared = sorted(set(left) & set(right))
    switches: Dict[str, int] = {}
    for goal in shared:
        before = left[goal]["reference_arm"]
        after = right[goal]["reference_arm"]
        if before != after:
            switches[f"{before}->{after}"] = switches.get(f"{before}->{after}", 0) + 1
    changed = sum(switches.values())
    return {
        "goals": len(shared),
        "goals_with_a_different_reference_arm": changed,
        "share": round(changed / len(shared), 6),
        "transitions": dict(sorted(switches.items())),
        "yardstick_is_stable": changed == 0,
    }


def catastrophe_shift(
    baseline: Dict[str, Any],
    other: Dict[str, Any],
    *,
    arm: str = ARCHIVE_ARM,
) -> Dict[str, Any]:
    """Catastrophic seeds for one arm, paired goal by goal."""
    left, right = goals_of(baseline), goals_of(other)
    shared = sorted(set(left) & set(right))
    before = [left[goal]["catastrophic_seeds"][arm] for goal in shared]
    after = [right[goal]["catastrophic_seeds"][arm] for goal in shared]
    return {
        "goals": len(shared),
        "baseline_mean": round(statistics.fmean(before), 6),
        "panel_mean": round(statistics.fmean(after), 6),
        "baseline_total": sum(before),
        "panel_total": sum(after),
        "goals_that_get_worse": sum(1 for a, b in zip(before, after) if b > a),
        "goals_that_get_better": sum(1 for a, b in zip(before, after) if b < a),
    }


def arm_catastrophes(report: Dict[str, Any]) -> Dict[str, Any]:
    """Every arm's catastrophic seeds on one panel, so the archive is ranked."""
    goals = goals_of(report)
    totals = {
        arm: sum(g["catastrophic_seeds"][arm] for g in goals.values())
        for arm in mbe.STRATEGIES
    }
    best = min(totals, key=lambda arm: totals[arm])
    return {
        "goals": len(goals),
        "seeds_per_goal": report["seeds"],
        "totals": totals,
        "best_arm": best,
        "archive_is_best": totals[ARCHIVE_ARM] == totals[best],
        "archive_is_strictly_best": all(
            totals[ARCHIVE_ARM] < totals[arm]
            for arm in mbe.STRATEGIES
            if arm != ARCHIVE_ARM
        ),
    }


def panel_facts(name: str) -> Dict[str, Any]:
    """The panel's own parameters, resolved exactly as the sweep resolves them.

    Deliberately routed through ``e033._panel`` rather than ``e027.PANELS``.
    ``e027.PANELS`` does contain a ``perfect`` entry -- one verifier at accuracy
    ``1.0`` -- but the sweep does not use it: ``e033._panel("perfect")`` returns
    ``None``, which skips the verifier draw entirely and so consumes a different
    rng stream. Reading the config here would describe a run that never
    happened, so the ``perfect`` column is reported as what it is.
    """
    config = e033._panel(name)
    if config is None:
        return {
            "verification_drawn": False,
            "verifiers": 0,
            "accuracy": 1.0,
            "correlation": 0.0,
            "blind_spot": 0.0,
        }
    return {
        "verification_drawn": True,
        "verifiers": config.verifiers,
        "accuracy": config.accuracy,
        "correlation": config.correlation,
        "blind_spot": config.blind_spot,
    }


#: The leakage probe. A weaker panel changes two things at once -- it rejects
#: viable candidates and it accepts non-viable ones -- and the ladder cannot
#: tell them apart. :func:`leakage` runs a handful of seeds with the per-arm
#: verification metrics kept instead of discarded, so the direction of the
#: archive's gain is measured rather than argued.
LEAKAGE_SEEDS = 20
LEAKAGE_WEIGHT = 0.40


def leakage_goals(report: Dict[str, Any], *, weight: float = LEAKAGE_WEIGHT):
    """One goal per trait, taken from a committed sweep rather than redrawn.

    Reading them out of the artifact guarantees the probe runs on goals the
    ladder actually measured; rebuilding the pool here could drift from it.
    """
    goals = {}
    for trait, block in sorted(report["traits"].items()):
        for cell in block["cells"]:
            if abs(cell["target_weight"] - weight) < 1e-9:
                goals[trait] = tuple(cell["goal_results"][0]["goal"])
                break
    return goals


def leakage_summary(
    rows: Dict[str, Any], ordered: Sequence[str]
) -> Dict[str, Any]:
    """The verdicts a leakage table supports, as a pure function of the table.

    Separated from :func:`leakage` so the committed probe can be re-derived from
    its own rows without rerunning the arena.
    """
    return {
        "false_accepts_rise_as_the_panel_weakens": all(
            rows[ordered[index]][ARCHIVE_ARM]["false_accept_rate"]
            < rows[ordered[index + 1]][ARCHIVE_ARM]["false_accept_rate"]
            for index in range(len(ordered) - 1)
        ),
        "false_rejects_rise_as_the_panel_weakens": all(
            rows[ordered[index]][ARCHIVE_ARM]["false_reject_rate"]
            < rows[ordered[index + 1]][ARCHIVE_ARM]["false_reject_rate"]
            for index in range(len(ordered) - 1)
        ),
        # How lopsided the panel's error is. A gate that mostly *leaks* and a
        # gate that mostly *blocks* would explain the ladder in opposite ways,
        # so the asymmetry is measured rather than assumed in either direction.
        "error_asymmetry": {
            panel: round(
                rows[panel][ARCHIVE_ARM]["false_accept_rate"]
                - rows[panel][ARCHIVE_ARM]["false_reject_rate"],
                6,
            )
            for panel in ordered
        },
        # Whether the panel treats the arms differently. It should not -- it
        # cannot see which arm proposed -- and if it did, every cross-arm
        # comparison in E030-E035 would be confounded.
        "widest_false_accept_gap_between_arms": {
            panel: round(
                max(rows[panel][arm]["false_accept_rate"] for arm in mbe.STRATEGIES)
                - min(rows[panel][arm]["false_accept_rate"] for arm in mbe.STRATEGIES),
                6,
            )
            for panel in ordered
        },
        "archive_size_by_panel": {
            panel: rows[panel][ARCHIVE_ARM]["archive_size"] for panel in ordered
        },
        # The obvious mechanism -- "a leaky gate lets the archive hold more" --
        # requires the archive to grow. It does not: it is capacity-bound at the
        # agent count on every panel, which rules that explanation out.
        "archive_is_capacity_bound": len(
            {rows[panel][ARCHIVE_ARM]["archive_size"] for panel in ordered}
        )
        == 1,
    }


def leakage(
    goals: Dict[str, Sequence[float]],
    *,
    panels: Sequence[str] = PANEL_ORDER,
    seeds: int = LEAKAGE_SEEDS,
    seed_start: int = 1,
    agents: int = 64,
    generations: int = 50,
    change_at: int = 25,
    bins: int = 8,
) -> Dict[str, Any]:
    """Per-arm verification metrics under each panel, which the sweep drops.

    ``e030.per_seed_auc`` keeps only the utility AUC, so a sweep artifact cannot
    say whether a weaker panel helped the archive by leaking non-viable
    candidates in or by rejecting viable ones. This keeps the metrics.
    """
    import sim.e030_supplied_goal_membership as e030

    rows: Dict[str, Any] = {}
    for panel in panels:
        config = e033._panel(panel)
        per_arm: Dict[str, Dict[str, List[float]]] = {
            arm: {"false_accept_rate": [], "false_reject_rate": [], "archive_size": []}
            for arm in mbe.STRATEGIES
        }
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
                    for result in record["results"]:
                        bucket = per_arm[result["strategy"]]
                        for key in bucket:
                            bucket[key].append(result[key])
        rows[panel] = {
            arm: {
                key: round(statistics.fmean(values), 6)
                for key, values in bucket.items()
            }
            for arm, bucket in per_arm.items()
        }
    ordered = [name for name in panels]
    return {
        "experiment_id": EXPERIMENT_ID,
        "mode": "leakage",
        "panels": ordered,
        "goals": {trait: [round(w, 9) for w in goal] for trait, goal in goals.items()},
        "seeds": seeds,
        "seed_start": seed_start,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "bins": bins,
        "per_panel": rows,
        **leakage_summary(rows, ordered),
    }


#: E035's closing sentence, turned into clauses that can each come out false.
#: Written before the ``measured`` and ``stress`` sweeps were run.
PREDICTION: Dict[str, Any] = {
    "source": "E035, Decision: the ladder on a panel with a non-zero blind-spot floor",
    "if_the_structure_is_geometric": {
        "descriptor_contrast_resolves_on_every_panel": True,
        "no_trait_sign_flips_across_panels": True,
        "floored_pair_asymmetry_holds": True,
        "archive_still_leads_on_every_panel": True,
    },
    "reasoning": (
        "E034's ladder is a statement about which directions the archive's "
        "diversity covers. Coverage is a property of the niche grid and the "
        "budget, neither of which the panel touches. If instead the ladder was "
        "an artifact of free, exact quality observation, weakening the panel "
        "should break it -- and `stress`, at 0.55 accuracy and 0.9 correlation, "
        "is as weak as the arena's published panels get."
    ),
}


def prediction_outcome(comparison: Dict[str, Any]) -> Dict[str, Any]:
    """Score :data:`PREDICTION` against the measurement, clause by clause.

    A pure function of the committed comparison, so it can be recomputed from
    the artifact and cannot drift away from it.
    """
    clauses = {
        "descriptor_contrast_resolves_on_every_panel": comparison[
            "descriptor_cancellation_survives"
        ],
        "no_trait_sign_flips_across_panels": comparison["no_sign_flips"],
        "floored_pair_asymmetry_holds": comparison["floored_pair_asymmetry_survives"],
        "archive_still_leads_on_every_panel": comparison["archive_still_leads"],
    }
    expected = PREDICTION["if_the_structure_is_geometric"]
    met = {key: clauses[key] == expected[key] for key in expected}
    return {
        "clauses": clauses,
        "met": met,
        "met_count": sum(met.values()),
        "clause_count": len(met),
        "supported": all(met.values()),
        "partially_supported": any(met.values()) and not all(met.values()),
    }


def compare(reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The cross-panel comparison."""
    names = [name for name in PANEL_ORDER if name in reports]
    if BASELINE_PANEL not in reports:
        raise ValueError(f"the {BASELINE_PANEL!r} baseline panel is required")
    traits = sorted(reports[names[0]]["traits"])
    baseline = reports[BASELINE_PANEL]

    per_panel = {
        name: {
            "panel": panel_facts(name),
            "direction_spread": e035.direction_spread(reports[name]),
            "catastrophes": arm_catastrophes(reports[name]),
            "ladders": {
                trait: e035.ladder_change(reports[name], trait) for trait in traits
            },
            "descriptor_contrast": e035.contrast(
                e035.ladder_change(reports[name], "adaptability"),
                e035.ladder_change(reports[name], "efficiency"),
            ),
            "floored_contrast": e035.contrast(
                e035.ladder_change(reports[name], "reliability"),
                e035.ladder_change(reports[name], "security"),
            ),
        }
        for name in names
    }
    against_baseline = {
        name: {
            "lead": paired_shift(baseline, reports[name]),
            "archive_score": absolute_shift(baseline, reports[name]),
            "consensus_lead": paired_shift(baseline, reports[name], arm=CONSENSUS_ARM),
            "reference_arm": reference_arm_switches(baseline, reports[name]),
            "archive_catastrophes": catastrophe_shift(baseline, reports[name]),
        }
        for name in names
        if name != BASELINE_PANEL
    }
    trait_replication = {
        trait: e035.replication([per_panel[name]["ladders"][trait] for name in names])
        for trait in traits
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "panels": names,
        "baseline_panel": BASELINE_PANEL,
        "resolved_t": RESOLVED_T,
        "comparability": comparability(reports),
        "goal_alignment": goal_alignment(reports),
        "per_panel": per_panel,
        "against_baseline": against_baseline,
        "trait_replication": trait_replication,
        "descriptor_cancellation_survives": all(
            per_panel[name]["descriptor_contrast"]["resolved"] for name in names
        ),
        "floored_pair_asymmetry_survives": all(
            per_panel[name]["ladders"]["reliability"]["change"]
            > per_panel[name]["ladders"]["security"]["change"]
            and not per_panel[name]["ladders"]["security"]["resolved"]
            for name in names
        ),
        "no_sign_flips": all(
            block["verdict"] != e035.SIGN_FLIPS
            for block in trait_replication.values()
        ),
        "archive_still_leads": all(
            per_panel[name]["direction_spread"]["lead_mean"] > 0 for name in names
        ),
        "archive_is_best_arm_on_every_panel": all(
            per_panel[name]["catastrophes"]["archive_is_best"] for name in names
        ),
        # Whether the *ranking* moves is the panel question. Whether the archive
        # happens to top it is not: on this metric a hypothesis-free arm can win
        # at the baseline too, and that would be an E034 fact, not an E037 one.
        "catastrophe_ranking_is_panel_invariant": len(
            {per_panel[name]["catastrophes"]["best_arm"] for name in names}
        )
        == 1,
        "catastrophe_best_arm_by_panel": {
            name: per_panel[name]["catastrophes"]["best_arm"] for name in names
        },
        "prediction": PREDICTION,
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E037 ladder under imperfect panels")
    parser.add_argument(
        "--panel",
        action="append",
        default=None,
        metavar="NAME=PATH",
        help="an E034-shaped artifact, e.g. measured=results/E037-panel-measured.json",
    )
    parser.add_argument(
        "--mode", choices=("compare", "leakage"), default="compare"
    )
    parser.add_argument("--seeds", type=int, default=LEAKAGE_SEEDS)
    parser.add_argument("--agents", type=int, default=64)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--change-at", type=int, default=25)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    if not args.panel:
        raise SystemExit("--panel NAME=PATH is required")
    reports = {}
    for item in args.panel:
        name, _, path = item.partition("=")
        reports[name] = json.loads(Path(path).read_text(encoding="utf-8"))
    if args.mode == "leakage":
        report = leakage(
            leakage_goals(reports[BASELINE_PANEL]),
            panels=[name for name in PANEL_ORDER if name in reports],
            seeds=args.seeds,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
        )
    else:
        report = compare(reports)
        report["prediction_outcome"] = prediction_outcome(report)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
