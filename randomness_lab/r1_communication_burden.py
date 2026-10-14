"""Structural communication and redundancy accounting for the R1 topology arms.

Issue 13's metric list names messages communicated, duplicated work, and curves for
communication burden.  The synthetic R1 scaling lab declares those not represented:
it never varies a communication budget or shared memory, and its trials are
per-seed aggregates with no per-candidate content.  This module is a downstream
analyzer over an existing schema-v2 R1 topology result.  It does not edit, import-
and-mutate, or re-run the frozen generator (:mod:`randomness_lab.r1_scaling`), and
the committed R1 artifacts stay byte-identical.

What is counted, and what is not:

* **Messages are structural.**  They are edges traversed in each topology's
  *definition*, counted by an explicit rule (see :func:`messages_per_task`).  They are
  not measured bytes, tokens, or latency, and no real agent exchanged anything.
* **Duplication is only partly definable.**  The R1 result carries no candidate
  identity, so "an attempt whose candidate equals an earlier candidate in the same
  task" cannot be computed from it.  :func:`count_duplicated_attempts` implements that
  definition for a caller-supplied trace but is applied to no R1 data.  What the
  topology definitions do fix is *structural replication* (attempts beyond the first
  on the same unit of work, by design) and *unproductive attempts* (attempts spent on
  tasks that did not end in a verified success).  Neither is content duplication.

Intervals are percentile bootstrap intervals over the lab's deterministic seeds.  They
are descriptive, are not multiplicity adjusted, and say nothing about real tasks.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
from pathlib import Path
from statistics import mean
from typing import Hashable, Iterable, Sequence

from .r1_scaling import FLAT, ROLE_SPECIALIZED, TASK_DAG, TOPOLOGIES

SCHEMA_VERSION = 1
GENERATOR = "randomness_lab.r1_communication_burden.v1"
EVIDENCE_LEVEL = "synthetic_mechanism"
COUNT_LABEL = "structural, not measured bytes"
METRIC = "verified_success_rate"
DEFAULT_RESAMPLES = 2000
DEFAULT_BOOTSTRAP_SEED = 20261014
DEFAULT_INPUT = Path("results/experiments/r1/coordination-topology-seeds42-51.json.gz")

COUNTING_RULE = (
    "A message is one directed transfer of a task statement, a plan, a candidate, or a "
    "verdict along one edge of the topology's role graph, counted once per task episode "
    "(the lab's only unit of interaction; it has no multi-round exchanges). H is the "
    "integrating hub; a verifier decision is a message only when a role other than the "
    "verifier must receive it. flat: H->W_k, W_k->V_k, V_k->H for k=1..N, so 3N. "
    "role_specialized (N>=2): H->planner 1, planner->implementer N-1, "
    "implementer->tester N-1, tester->reviewer 1, reviewer->H 1, so 2N+1; the tester "
    "decides per candidate internally, which is why this arm is cheaper than flat "
    "under this rule and is a property of the rule. task_dag (N>=2): every attempt, "
    "parent or child, is one dispatch, one candidate hand-off, and one verdict, and the "
    "child dispatch carries the accepted parent artifact; blocked child budget is "
    "re-spent on parent attempts with the same three messages each, so 3N on either "
    "path. N=1 is a team of one and uses the flat rule (3) in every topology."
)

NOT_REPRESENTED = (
    "measured communication bytes, tokens, or latency",
    "content-level duplication: R1 results carry no candidate identity",
    "a communication budget K or shared memory M as a varied factor",
    "real agents, real messages, or any real task corpus",
)


def _validate_size(n: int) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("swarm size must be a positive integer")


def _validate_topology(topology: str) -> None:
    if topology not in TOPOLOGIES:
        raise ValueError(f"unknown coordination topology: {topology}")


def messages_per_task(topology: str, n: int) -> int:
    """Structural messages per task episode under :data:`COUNTING_RULE`."""

    _validate_topology(topology)
    _validate_size(n)
    if n == 1 or topology in (FLAT, TASK_DAG):
        return 3 * n
    return 2 * n + 1


def all_to_all_reference_messages(n: int) -> int:
    """Directed messages if N peers each told every other peer: ``N * (N - 1)``.

    A reference contrast only.  No topology in the lab is all-to-all.
    """

    _validate_size(n)
    return n * (n - 1)


def critical_path_hops(topology: str, n: int) -> tuple[int, int]:
    """Minimum and maximum sequential message hops from dispatch to final verdict."""

    _validate_topology(topology)
    _validate_size(n)
    if n == 1 or topology == FLAT:
        return (3, 3)
    if topology == ROLE_SPECIALIZED:
        return (5, 5)
    return (3, 6)


def replicated_attempts_per_task(topology: str, n: int) -> tuple[int, int]:
    """Minimum and maximum attempts beyond the first on the same unit of work.

    Derived from the topology definition alone: this is redundancy by design, not
    a count of equal candidates.  ``task_dag`` has a range because whether the
    child budget is re-spent upstream depends on a per-task acceptance the
    aggregate result does not carry.
    """

    _validate_topology(topology)
    _validate_size(n)
    if n == 1:
        return (0, 0)
    if topology == FLAT:
        return (n - 1, n - 1)
    if topology == ROLE_SPECIALIZED:
        return (n - 2, n - 2)
    parents = n - n // 2
    children = n // 2
    unblocked = (parents - 1) + max(children - 1, 0)
    return (unblocked, n - 1)


def count_duplicated_attempts(
    task_traces: Iterable[Sequence[Hashable]],
) -> dict[str, object]:
    """Count attempts whose candidate key equals an earlier key in the same task.

    ``task_traces`` holds one sequence of hashable candidate keys per task, in
    attempt order.  Keys are never compared across tasks.  The R1 results carry no
    such trace, so this is defined here but is not applied to them.
    """

    attempts = 0
    duplicated = 0
    per_task: list[int] = []
    for trace in task_traces:
        seen: set[Hashable] = set()
        task_duplicates = 0
        for key in trace:
            attempts += 1
            if key in seen:
                task_duplicates += 1
            else:
                seen.add(key)
        duplicated += task_duplicates
        per_task.append(task_duplicates)
    return {
        "attempts": attempts,
        "duplicated_attempts": duplicated,
        "distinct_attempts": attempts - duplicated,
        "duplicated_per_task": per_task,
        "duplicated_fraction": (duplicated / attempts) if attempts else None,
    }


def _ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = mean(xs)
    mean_y = mean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0.0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def _resample_indices(
    count: int, resamples: int, rng: random.Random
) -> list[list[int]]:
    if count < 2:
        raise ValueError("bootstrap needs at least two seeds")
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    return [[rng.randrange(count) for _ in range(count)] for _ in range(resamples)]


def _bootstrap_summary(
    values: Sequence[float], index_sets: Sequence[Sequence[int]]
) -> dict[str, object]:
    if any(not math.isfinite(value) for value in values):
        raise ValueError("bootstrap values must be finite")
    pick = values.__getitem__
    boot = sorted(sum(map(pick, indices)) / len(indices) for indices in index_sets)
    lower = boot[int(0.025 * len(boot))]
    upper = boot[max(math.ceil(0.975 * len(boot)) - 1, 0)]
    if lower > 0.0:
        classification = "positive"
    elif upper < 0.0:
        classification = "negative"
    else:
        classification = "uncertain"
    return {
        "n_seeds": len(values),
        "mean": mean(values),
        "bootstrap_95_ci": [lower, upper],
        "classification": classification,
    }


def bootstrap_mean_ci(
    values: Sequence[float], *, resamples: int, seed: int
) -> dict[str, object]:
    """Percentile bootstrap of the mean over seeds, deterministic in ``seed``."""

    rng = random.Random(seed)
    return _bootstrap_summary(values, _resample_indices(len(values), resamples, rng))


def _cell_table(
    result: dict[str, object],
) -> tuple[tuple[int, ...], tuple[int, ...], int, list[str], dict]:
    """Validate the R1 result and return sizes, seeds, tasks, difficulties, cells."""

    config = result.get("config")
    cells = result.get("cells")
    if not isinstance(config, dict) or not isinstance(cells, list):
        raise ValueError("R1 result must contain config and cells")
    if result.get("schema_version") != 2:
        raise ValueError("a schema-v2 R1 topology result is required")
    sizes = tuple(int(size) for size in config.get("swarm_sizes", ()))
    if len(sizes) < 2 or sizes[0] != 1 or tuple(sorted(set(sizes))) != sizes:
        raise ValueError("swarm_sizes must be strictly increasing and start at 1")
    tasks = config.get("tasks_per_trial")
    if isinstance(tasks, bool) or not isinstance(tasks, int) or tasks < 1:
        raise ValueError("config must give tasks_per_trial")

    table: dict[tuple[str, str, str, int], dict[str, object]] = {}
    difficulties: list[str] = []
    seeds: tuple[int, ...] | None = None
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("every R1 cell must be a mapping")
        topology = cell.get("topology")
        if topology not in TOPOLOGIES:
            raise ValueError(f"cell has unknown topology: {topology!r}")
        key = (cell["difficulty"], cell["family"], topology, int(cell["swarm_size"]))
        if key in table:
            raise ValueError(f"duplicate R1 cell: {key}")
        budget = cell.get("attempt_budget_per_task")
        if budget is not None and budget != key[3]:
            raise ValueError(f"attempt budget does not equal N in cell {key}")
        trials = cell.get("raw_trials")
        if not isinstance(trials, list) or len(trials) < 2:
            raise ValueError(f"cell {key} needs at least two raw trials")
        cell_seeds = tuple(int(row["seed"]) for row in trials)
        if len(set(cell_seeds)) != len(cell_seeds):
            raise ValueError(f"cell {key} repeats a seed")
        if seeds is None:
            seeds = cell_seeds
        elif cell_seeds != seeds:
            raise ValueError("every cell must carry the same ordered seeds")
        rates = []
        for row in trials:
            rate = row["metrics"][METRIC]
            if isinstance(rate, bool) or not isinstance(rate, (int, float)):
                raise ValueError(f"{METRIC} must be numeric")
            if not 0.0 <= float(rate) <= 1.0:
                raise ValueError(f"{METRIC} must be in [0, 1]")
            rates.append(float(rate))
        table[key] = {"rates": rates}
        if key[0] not in difficulties:
            difficulties.append(key[0])
    if seeds is None:
        raise ValueError("R1 result has no cells")
    return sizes, seeds, tasks, difficulties, table


def _group_analysis(
    topology: str,
    sizes: Sequence[int],
    tasks: int,
    rates_by_size: dict[int, list[float]],
    index_sets: Sequence[Sequence[int]],
) -> tuple[dict[str, object], dict[str, list[float]]]:
    """Curves for one (difficulty, family, topology); also return paired series."""

    count = len(rates_by_size[sizes[0]])
    messages = {n: messages_per_task(topology, n) for n in sizes}
    points = []
    per_message: dict[int, list[float]] = {}
    for n in sizes:
        rates = rates_by_size[n]
        per_message[n] = [rate / messages[n] for rate in rates]
        replicated = replicated_attempts_per_task(topology, n)
        hops = critical_path_hops(topology, n)
        points.append(
            {
                "n": n,
                "messages_per_task": messages[n],
                "messages_total_per_trial": messages[n] * tasks,
                "count_label": COUNT_LABEL,
                "all_to_all_reference_messages_per_task": all_to_all_reference_messages(n),
                "critical_path_hops": list(hops),
                "structural_replicated_attempts_per_task": list(replicated),
                "verified_success_rate": _bootstrap_summary(rates, index_sets),
                "verified_successes_per_message": _bootstrap_summary(
                    per_message[n], index_sets
                ),
                "unproductive_attempts_per_task": _bootstrap_summary(
                    [n * (1.0 - rate) for rate in rates], index_sets
                ),
            }
        )

    marginals = []
    for low, high in zip(sizes, sizes[1:]):
        added = messages[high] - messages[low]
        series = [
            (rates_by_size[high][s] - rates_by_size[low][s]) / added
            for s in range(count)
        ]
        marginals.append(
            {
                "from_n": low,
                "to_n": high,
                "added_messages_per_task": added,
                "success_gain_per_added_message": _bootstrap_summary(series, index_sets),
            }
        )

    elasticity_seeds = [
        s for s in range(count) if all(rates_by_size[n][s] > 0.0 for n in sizes)
    ]
    elasticity: dict[str, object] | None = None
    elasticity_series: list[float] = []
    if len(elasticity_seeds) >= 2:
        xs = [math.log(messages[n]) for n in sizes]
        elasticity_series = [
            _ols_slope(xs, [math.log(rates_by_size[n][s]) for n in sizes])
            for s in elasticity_seeds
        ]
        if len(elasticity_seeds) == count:
            elasticity = _bootstrap_summary(elasticity_series, index_sets)
        else:
            sub = [
                [elasticity_seeds.index(i) for i in indices if i in elasticity_seeds]
                for indices in index_sets
            ]
            sub = [indices for indices in sub if indices]
            elasticity = _bootstrap_summary(elasticity_series, sub)
        elasticity["seeds_used"] = len(elasticity_seeds)
    series = {
        "elasticity_full": elasticity_series if len(elasticity_seeds) == count else [],
        "per_message_end": per_message[sizes[-1]],
    }
    series.update({f"per_message_{n}": per_message[n] for n in sizes})
    return (
        {
            "topology": topology,
            "points": points,
            "marginal_success_per_added_message": marginals,
            "success_vs_messages_elasticity": elasticity,
        },
        series,
    )


def analyze_communication_burden(
    result: dict[str, object],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, object]:
    """Structural message, replication, and success-per-message curves."""

    sizes, seeds, tasks, difficulties, table = _cell_table(result)
    families = sorted({key[1] for key in table})
    groups: list[dict[str, object]] = []
    contrasts: list[dict[str, object]] = []
    for difficulty in difficulties:
        for family in families:
            # One resample set per (difficulty, family), shared by every topology,
            # so the paired contrasts against flat resample identical seeds.
            rng = random.Random(f"{bootstrap_seed}|{difficulty}|{family}")
            index_sets = _resample_indices(len(seeds), resamples, rng)
            series_by_topology: dict[str, dict[str, list[float]]] = {}
            for topology in TOPOLOGIES:
                rates_by_size = {}
                for n in sizes:
                    cell = table.get((difficulty, family, topology, n))
                    if cell is None:
                        raise ValueError(
                            f"missing cell: {(difficulty, family, topology, n)}"
                        )
                    rates_by_size[n] = cell["rates"]
                group, series = _group_analysis(
                    topology, sizes, tasks, rates_by_size, index_sets
                )
                group.update({"difficulty": difficulty, "family": family})
                groups.append(group)
                series_by_topology[topology] = series
            baseline = series_by_topology[FLAT]
            for topology in TOPOLOGIES:
                if topology == FLAT:
                    continue
                other = series_by_topology[topology]
                row: dict[str, object] = {
                    "difficulty": difficulty,
                    "family": family,
                    "topology": topology,
                    "baseline_topology": FLAT,
                    "per_message_difference_vs_flat": {},
                }
                for n in sizes[1:]:
                    diff = [
                        a - b
                        for a, b in zip(
                            other[f"per_message_{n}"], baseline[f"per_message_{n}"]
                        )
                    ]
                    row["per_message_difference_vs_flat"][str(n)] = _bootstrap_summary(
                        diff, index_sets
                    )
                if other["elasticity_full"] and baseline["elasticity_full"]:
                    row["elasticity_difference_vs_flat"] = _bootstrap_summary(
                        [
                            a - b
                            for a, b in zip(
                                other["elasticity_full"], baseline["elasticity_full"]
                            )
                        ],
                        index_sets,
                    )
                else:
                    row["elasticity_difference_vs_flat"] = None
                contrasts.append(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "R1-communication-burden",
        "generator": GENERATOR,
        "evidence_level": EVIDENCE_LEVEL,
        "count_label": COUNT_LABEL,
        "source_experiment": result.get("experiment"),
        "source_generator": result.get("generator"),
        "config": {
            "swarm_sizes": list(sizes),
            "seeds": list(seeds),
            "tasks_per_trial": tasks,
            "bootstrap_resamples": resamples,
            "bootstrap_seed": bootstrap_seed,
            "metric": METRIC,
        },
        "counting_rule": COUNTING_RULE,
        "definitions": {
            "verified_successes_per_message": (
                "per-seed verified_success_rate divided by structural messages per task"
            ),
            "unproductive_attempts_per_task": (
                "N * (1 - verified_success_rate): attempts spent on tasks that did not "
                "end in a verified success. Every arm spends exactly N attempts per "
                "task. This is not duplication."
            ),
            "structural_replicated_attempts_per_task": (
                "attempts beyond the first on the same unit of work, by design; a "
                "[min, max] range where the topology's blocking is not in the result"
            ),
            "success_vs_messages_elasticity": (
                "per-seed OLS slope of log(verified_success_rate) on log(messages per "
                "task) over the configured sizes; seeds with a zero rate are excluded"
            ),
            "success_gain_per_added_message": (
                "per-seed change in verified_success_rate between adjacent sizes over "
                "the change in messages per task"
            ),
            "duplicated_attempts": (
                "attempts whose candidate equals an earlier candidate in the same "
                "task; implemented by count_duplicated_attempts for a supplied trace"
            ),
        },
        "duplicated_attempts_in_r1_result": {
            "value": None,
            "reason": (
                "the R1 result holds per-seed aggregate metrics only; no candidate "
                "identity or per-task trace exists to compare"
            ),
        },
        "not_represented": list(NOT_REPRESENTED),
        "groups": groups,
        "contrasts_vs_flat": contrasts,
        "interpretation_guardrail": (
            "Message counts are structural, not measured bytes, derived from a stated "
            "counting rule over three synthetic topology definitions. Success rates "
            "are synthetic. Percentile bootstrap intervals over the lab's seeds are "
            "descriptive, not multiplicity adjusted, and the ordering of topologies by "
            "message count is a property of the counting rule. Nothing here measures "
            "real agents or real communication and it cannot close issue 13."
        ),
    }


def load_result(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _fmt_ci(summary: dict[str, object], digits: int = 4) -> str:
    low, high = summary["bootstrap_95_ci"]
    return f"{summary['mean']:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def render_markdown(analysis: dict[str, object]) -> str:
    sizes = analysis["config"]["swarm_sizes"]
    lines = [
        "# R1 communication burden (structural)",
        "",
        "Evidence level: **synthetic mechanism only**. Message counts are "
        f"**{COUNT_LABEL}**.",
        "",
        "Percentile bootstrap intervals over the lab's deterministic seeds; "
        "descriptive, not hypothesis tests.",
        "",
        "## Structural messages per task",
        "",
        "| N | " + " | ".join(TOPOLOGIES) + " | all-to-all reference |",
        "| ---: | " + " | ".join("---:" for _ in TOPOLOGIES) + " | ---: |",
    ]
    for n in sizes:
        lines.append(
            f"| {n} | "
            + " | ".join(str(messages_per_task(t, n)) for t in TOPOLOGIES)
            + f" | {all_to_all_reference_messages(n)} |"
        )
    lines.extend(
        [
            "",
            "## Success per message, by difficulty, family, and topology",
            "",
            "| Difficulty | Family | Topology | N | Messages | Success | Success per message | Elasticity |",
            "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for group in analysis["groups"]:
        elasticity = group["success_vs_messages_elasticity"]
        text = "n/a" if elasticity is None else _fmt_ci(elasticity, 3)
        for index, point in enumerate(group["points"]):
            lines.append(
                f"| {group['difficulty']} | {group['family']} | {group['topology']} "
                f"| {point['n']} | {point['messages_per_task']} "
                f"| {_fmt_ci(point['verified_success_rate'])} "
                f"| {_fmt_ci(point['verified_successes_per_message'])} "
                f"| {text if index == 0 else ''} |"
            )
    lines.extend(
        [
            "",
            "## Scope boundary",
            "",
            str(analysis["interpretation_guardrail"]),
            "",
            "Duplicated attempts: not computed for the R1 result ("
            + str(analysis["duplicated_attempts_in_r1_result"]["reason"])
            + ").",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Structural communication burden over an R1 topology result"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="write machine-readable JSON (.gz ok)")
    parser.add_argument("--report", type=Path, help="write a Markdown report")
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    analysis = analyze_communication_burden(
        load_result(args.input),
        resamples=args.resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    rendered = json.dumps(analysis, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == ".gz":
            args.output.write_bytes(
                gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0)
            )
        else:
            args.output.write_text(rendered, encoding="utf-8")
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(analysis), encoding="utf-8")
    if args.output is None and args.report is None:
        print(render_markdown(analysis), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
