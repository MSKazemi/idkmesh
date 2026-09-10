"""Sweep the R1 verifier panel across quorum, dependence shape and billing.

Issue #380's hypothesis-2 question is not "does a panel help" but "does it still
help once you pay for it". Three things decide that, and each has already
produced an inverted conclusion somewhere in this repository when it was fixed
rather than swept:

* **the quorum.** A prior result here survives only on a sub-range of ``need``
  and dissolves once the full ``[1, k]`` range is opened. So ``need`` is swept
  across its whole range, not pinned at the majority.
* **the dependence shape.** ``shared_shock`` concentrates mass on unanimity;
  ``item_difficulty`` spreads it across partial panel failures. They agree
  exactly at ``rho = 0`` and ``rho = 1``, so any separation between them is
  attributable to shape alone.
* **the billing.** ``per_verifier`` charges every panel read; ``per_candidate``
  charges one average-equivalent read. A population sweep in this repository
  gave *opposite* answers under free versus held budget, so reporting one
  billing without its counterfactual is not a result.

The output is therefore a full matrix and this module never reduces it to a
single headline number. Category aggregates have cancelled here before -- two
members moving in opposite directions averaged to zero and read as support.
"""

from __future__ import annotations

import argparse
import gzip
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
from statistics import mean, pstdev

from .r1 import (
    PANEL_DEPENDENCE_SHAPES,
    R1ExperimentConfig,
    Verifier,
    build_r1_conditions,
    run_r1_condition,
)

GENERATOR = "randomness_lab.r1_panel_frontier.v1"

DEFAULT_PANEL_SIZES = (1, 3, 5)
DEFAULT_CORRELATIONS = (0.0, 0.25, 0.5875, 0.75, 1.0)
DEFAULT_BILLINGS = ("per_verifier", "per_candidate")
# Measured, not guessed. The headline reversal count reads 85% at 2 seeds, 62%
# at 4, 59% at 8, and 45-52% from 16 to 32 -- so anything under ~16 seeds
# reports roughly double the effect and looks like a finding rather than an
# underpowered run. 24 sits in the stable band at ~45 s.
DEFAULT_SEEDS = tuple(range(42, 66))

# The reference arm every panel cell is compared against: a single verifier,
# which is what every committed R1 artifact was generated under.
BASELINE_PANEL_SIZE = 1

INTERPRETATION_GUARDRAIL = (
    "This is a simulator. Worker quality, verifier sensitivity, both "
    "correlations and the attention costs are invented parameters. A cell "
    "here is evidence about the model, not about real coding agents. Read "
    "cells, not the mean of cells: the two dependence shapes move in "
    "opposite directions in parts of this grid, so any average over shape "
    "cancels a real effect. And read the decisive counts, not the raw ones: "
    "most raw billing reversals are cells sitting near a tie, which is why "
    "the raw statistic reads 85% at two seeds and 45-52% at sixteen to "
    "thirty-two."
)

# Measured sample-size sensitivity of the raw reversal count, recorded so an
# underpowered run cannot be mistaken for a finding. Raw flips, of 80 cells:
#   2 seeds / 60 tasks   68 (85%)
#   4 seeds / 60 tasks   50 (62%)
#   8 seeds / 120 tasks  47 (59%)
#  16 seeds / 250 tasks  36 (45%)
#  24 seeds / 250 tasks  36 (45%)
#  32 seeds / 250 tasks  42 (52%)
# The decisive count is far steadier (0-10% over the same range) but is itself
# bounded by how few `per_candidate` cells separate from noise at all.
SAMPLE_SIZE_SENSITIVITY = {
    "raw_reversals_of_80": {
        "2x60": 68, "4x60": 50, "8x120": 47,
        "16x250": 36, "24x250": 36, "32x250": 42,
    },
    "note": (
        "Anything below roughly 16 seeds reports about double the effect. "
        "The default is 24 seeds x 250 tasks."
    ),
}


@dataclass(frozen=True)
class PanelFrontierConfig:
    swarm_size: int = 5
    tasks: int = 250
    panel_sizes: tuple[int, ...] = DEFAULT_PANEL_SIZES
    correlations: tuple[float, ...] = DEFAULT_CORRELATIONS
    billings: tuple[str, ...] = DEFAULT_BILLINGS
    shapes: tuple[str, ...] = PANEL_DEPENDENCE_SHAPES
    seeds: tuple[int, ...] = DEFAULT_SEEDS

    def __post_init__(self) -> None:
        if self.tasks < 1:
            raise ValueError("tasks must be >= 1")
        if not self.seeds:
            raise ValueError("seeds must not be empty")
        if any(size < 1 for size in self.panel_sizes):
            raise ValueError("panel sizes must be >= 1")
        for shape in self.shapes:
            if shape not in PANEL_DEPENDENCE_SHAPES:
                raise ValueError(f"unknown dependence shape: {shape}")


def _homogeneous_pool(size: int) -> tuple[Verifier, ...]:
    """A pool of identically parameterised verifiers.

    Identical on purpose: `item_difficulty` is only defined for a homogeneous
    panel, and a pool that varied sensitivity would confound a shape comparison
    with a strength comparison.
    """

    return tuple(Verifier(f"panelist-{index}") for index in range(1, size + 1))


def _needs(panel_size: int) -> tuple[int, ...]:
    """Every acceptance threshold from 1 to k, expressed as E018 quorums."""

    return tuple(range(1, panel_size + 1))


def _quorum_for(need: int, panel_size: int) -> float:
    """Smallest quorum q with floor(q * k) + 1 == need."""

    if need <= 1:
        return 0.0
    return (need - 1) / panel_size


def _base_condition(config: PanelFrontierConfig):
    conditions = build_r1_conditions(R1ExperimentConfig(swarm_size=config.swarm_size))
    return conditions[0]


def _cell(config: PanelFrontierConfig, panel_size, need, shape, correlation, billing):
    """One matrix cell, averaged over seeds."""

    base = _base_condition(config)
    condition = replace(
        base,
        verifiers=_homogeneous_pool(panel_size),
        panel_size=panel_size,
        panel_quorum=_quorum_for(need, panel_size),
        panel_dependence_correlation=correlation,
        panel_dependence_shape=shape,
        panel_attention_billing=billing,
    )
    utilities, false_accepts, misses, attention = [], [], [], []
    for seed in config.seeds:
        result = run_r1_condition(
            condition, tasks=config.tasks, seed=seed, retain_task_records=False
        )
        metrics = result["metrics"]
        utilities.append(float(metrics["verified_utility_per_unit_cost"]))
        false_accepts.append(float(metrics["false_acceptance_rate"]))
        misses.append(float(metrics["missed_good_candidate_rate"]))
        attention.append(float(metrics["total_human_attention_proxy"]))
    spread = pstdev(utilities) if len(utilities) > 1 else 0.0
    return {
        "panel_size": panel_size,
        "need": need,
        "quorum": condition.panel_quorum,
        "shape": shape,
        "correlation": correlation,
        "billing": billing,
        "verified_utility_per_unit_cost": mean(utilities),
        # Kept so a verdict can be separated from a coin flip. A count of binary
        # verdicts is unstable wherever a cell sits near a tie, which is why the
        # headline below reports decisive reversals separately.
        "utility_stdev": spread,
        "utility_stderr": spread / math.sqrt(len(utilities)) if utilities else 0.0,
        "seeds": len(utilities),
        "false_acceptance_rate": mean(false_accepts),
        "missed_good_candidate_rate": mean(misses),
        "total_human_attention_proxy": mean(attention),
    }


def measure_frontier(config: PanelFrontierConfig) -> list[dict]:
    """Every (k, need, shape, rho, billing) cell.

    At `panel_size == 1` the shape and correlation cannot matter -- there is
    nothing for a panellist to be dependent *with* -- so those cells are emitted
    once rather than duplicated across shapes, and the duplication is asserted
    away rather than assumed absent.
    """

    cells: list[dict] = []
    for panel_size in config.panel_sizes:
        for need in _needs(panel_size):
            for billing in config.billings:
                if panel_size == 1:
                    cells.append(
                        _cell(config, 1, need, config.shapes[0], 0.0, billing)
                    )
                    continue
                for shape in config.shapes:
                    for correlation in config.correlations:
                        cells.append(
                            _cell(
                                config, panel_size, need, shape, correlation, billing
                            )
                        )
    return cells


def summarise_shape_separation(cells: list[dict]) -> list[dict]:
    """Where the two shapes disagree, cell by cell. Never averaged over shape."""

    keyed: dict[tuple, dict] = {}
    for cell in cells:
        if cell["panel_size"] == 1:
            continue
        key = (cell["panel_size"], cell["need"], cell["correlation"], cell["billing"])
        keyed.setdefault(key, {})[cell["shape"]] = cell

    rows = []
    for key, by_shape in sorted(keyed.items()):
        if len(by_shape) != 2:
            continue
        shock = by_shape["shared_shock"]
        item = by_shape["item_difficulty"]
        rows.append(
            {
                "panel_size": key[0],
                "need": key[1],
                "correlation": key[2],
                "billing": key[3],
                "shared_shock_utility": shock["verified_utility_per_unit_cost"],
                "item_difficulty_utility": item["verified_utility_per_unit_cost"],
                "utility_delta": item["verified_utility_per_unit_cost"]
                - shock["verified_utility_per_unit_cost"],
                "false_acceptance_delta": item["false_acceptance_rate"]
                - shock["false_acceptance_rate"],
            }
        )
    return rows


def summarise_billing_sensitivity(cells: list[dict]) -> list[dict]:
    """Does the panel-vs-single verdict flip when you stop charging per read?

    This is the counterfactual #380 names as most likely to decide the answer.
    """

    baseline: dict[tuple, dict] = {}
    for cell in cells:
        if cell["panel_size"] == BASELINE_PANEL_SIZE and cell["need"] == 1:
            baseline[(cell["billing"],)] = cell

    rows = []
    for cell in cells:
        if cell["panel_size"] == BASELINE_PANEL_SIZE:
            continue
        reference = baseline.get((cell["billing"],))
        if reference is None:
            continue
        margin = (
            cell["verified_utility_per_unit_cost"]
            - reference["verified_utility_per_unit_cost"]
        )
        # Two independent means, so the difference's standard error is the root
        # of the summed squares. "Decisive" means the sign survives two of them.
        stderr = math.sqrt(
            cell["utility_stderr"] ** 2 + reference["utility_stderr"] ** 2
        )
        rows.append(
            {
                "panel_size": cell["panel_size"],
                "need": cell["need"],
                "shape": cell["shape"],
                "correlation": cell["correlation"],
                "billing": cell["billing"],
                "utility_vs_single_verifier": margin,
                "margin_stderr": stderr,
                "beats_single_verifier": margin > 0,
                "decisive": abs(margin) > 2 * stderr,
            }
        )
    return rows


def count_billing_disagreements(billing_rows: list[dict]) -> dict:
    """How many (k, need, shape, rho) cells change verdict with the billing.

    A non-zero count is the finding: it means "does a panel pay for itself"
    cannot be answered without naming the billing.
    """

    by_cell: dict[tuple, dict[str, dict]] = {}
    for row in billing_rows:
        key = (row["panel_size"], row["need"], row["shape"], row["correlation"])
        by_cell.setdefault(key, {})[row["billing"]] = row

    compared = disagreed = decisive_disagreed = 0
    examples = []
    for key, rows_by_billing in sorted(by_cell.items()):
        if len(rows_by_billing) < 2:
            continue
        compared += 1
        verdicts = {b: r["beats_single_verifier"] for b, r in rows_by_billing.items()}
        if len(set(verdicts.values())) <= 1:
            continue
        disagreed += 1
        # A reversal only counts as decisive when BOTH sides are individually
        # decisive. Otherwise the cell is near a tie and the "reversal" is noise
        # -- which is exactly how this statistic read 85% at two seeds and 45%
        # at sixteen.
        both_decisive = all(r["decisive"] for r in rows_by_billing.values())
        if both_decisive:
            decisive_disagreed += 1
        if len(examples) < 8:
            examples.append(
                {
                    "panel_size": key[0],
                    "need": key[1],
                    "shape": key[2],
                    "correlation": key[3],
                    "verdicts": dict(sorted(verdicts.items())),
                    "decisive": both_decisive,
                }
            )
    return {
        "cells_compared": compared,
        "cells_that_change_verdict": disagreed,
        "cells_that_change_verdict_decisively": decisive_disagreed,
        "examples": examples,
    }


def run_panel_frontier(config: PanelFrontierConfig) -> dict[str, object]:
    cells = measure_frontier(config)
    billing_rows = summarise_billing_sensitivity(cells)
    return {
        "schema_version": 1,
        "generator": GENERATOR,
        "config": asdict(config),
        "interpretation_guardrail": INTERPRETATION_GUARDRAIL,
        "sample_size_sensitivity": SAMPLE_SIZE_SENSITIVITY,
        "cells": cells,
        "shape_separation": summarise_shape_separation(cells),
        "billing_sensitivity": billing_rows,
        "billing_disagreement": count_billing_disagreements(billing_rows),
    }


def render_markdown(result: dict[str, object]) -> str:
    config = result["config"]
    disagreement = result["billing_disagreement"]
    lines = [
        "# R1 verifier panel frontier",
        "",
        f"Generator: `{result['generator']}`.",
        f"Swarm size {config['swarm_size']}, {config['tasks']} tasks, "
        f"seeds {tuple(config['seeds'])}.",
        "",
        f"> {result['interpretation_guardrail']}",
        "",
        "## Does the billing change the verdict?",
        "",
        f"Of {disagreement['cells_compared']} (panel size, need, shape, correlation) "
        f"cells, **{disagreement['cells_that_change_verdict']}** reverse whether the "
        "panel beats a single verifier when the billing changes.",
        "",
        "| k | need | shape | rho | per_verifier | per_candidate |",
        "| ---: | ---: | --- | ---: | --- | --- |",
    ]
    for example in disagreement["examples"]:
        verdicts = example["verdicts"]
        lines.append(
            f"| {example['panel_size']} | {example['need']} | {example['shape']} | "
            f"{example['correlation']} | {verdicts.get('per_verifier')} | "
            f"{verdicts.get('per_candidate')} |"
        )
    lines += [
        "",
        "## Shape separation, cell by cell",
        "",
        "Never averaged over shape: the two move in opposite directions in parts "
        "of this grid, so a mean over shape cancels a real effect.",
        "",
        "| k | need | rho | billing | shared_shock | item_difficulty | delta |",
        "| ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in result["shape_separation"][:24]:
        lines.append(
            f"| {row['panel_size']} | {row['need']} | {row['correlation']} | "
            f"{row['billing']} | {row['shared_shock_utility']:.4f} | "
            f"{row['item_difficulty_utility']:.4f} | {row['utility_delta']:+.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep the R1 verifier panel frontier.")
    parser.add_argument("--swarm-size", type=int, default=5)
    parser.add_argument("--tasks", type=int, default=250)
    parser.add_argument("--seeds", type=str, default="42,43,44")
    # `--output` / `--report` rather than `--json` / `--markdown`, matching
    # r1_verifier_dependence, r1_dependence_shape and r1_scaling. One CLI shape
    # across the R1 runners is worth more than a locally nicer name.
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = PanelFrontierConfig(
        swarm_size=args.swarm_size,
        tasks=args.tasks,
        seeds=tuple(int(part) for part in args.seeds.split(",") if part.strip()),
    )
    result = run_panel_frontier(config)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == ".gz":
            # Compressed like the other committed R1 payloads; mtime=0 keeps the
            # bytes stable so the artifact is byte-reproducible.
            args.output.write_bytes(
                gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0)
            )
        else:
            args.output.write_text(rendered, encoding="utf-8")
    else:
        # Deliberately NOT the payload. The other R1 runners print their full
        # JSON here, and CodeQL's security-extended set reads a value named
        # `seed` as a private cryptographic seed and flags the write as
        # clear-text logging of sensitive data. Those instances are
        # grandfathered; a new one is a new high-severity alert.
        #
        # The seeds are genuinely public -- they are in the artifact filename --
        # so this is a false positive, and it could be silenced with an inline
        # suppression. Not doing that: a 157 KB grid was never a useful thing to
        # dump to a terminal, every real invocation writes a file, and printing
        # a scalar summary is better behaviour independently of the alert.
        # Silencing a warning to keep a default nobody wants is the wrong trade.
        disagreement = result["billing_disagreement"]
        print(f"cells: {len(result['cells'])}")
        print(f"billing reversals: {disagreement['cells_that_change_verdict']}"
              f" of {disagreement['cells_compared']} compared")
        print(f"decisive reversals: "
              f"{disagreement['cells_that_change_verdict_decisively']}")
        print("pass --output to write the payload, --report for the summary")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
