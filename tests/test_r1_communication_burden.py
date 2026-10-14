from __future__ import annotations

import ast
import copy
import math
import unittest
from pathlib import Path

from randomness_lab import r1_communication_burden as burden
from randomness_lab import r1_scaling
from randomness_lab.r1_communication_burden import (
    all_to_all_reference_messages,
    analyze_communication_burden,
    bootstrap_mean_ci,
    count_duplicated_attempts,
    critical_path_hops,
    messages_per_task,
    render_markdown,
    replicated_attempts_per_task,
)

MODULE = Path(burden.__file__)
RATES = {
    "flat": {1: [0.5, 0.5, 0.4, 0.6], 2: [0.8, 0.7, 0.9, 0.6], 5: [0.9, 0.9, 0.8, 1.0]},
    "role_specialized": {
        1: [0.5, 0.5, 0.4, 0.6],
        2: [0.6, 0.5, 0.7, 0.4],
        5: [0.8, 0.8, 0.7, 0.9],
    },
    "task_dag": {
        1: [0.5, 0.5, 0.4, 0.6],
        2: [0.5, 0.6, 0.4, 0.5],
        5: [0.9, 0.8, 0.8, 0.9],
    },
}
SEEDS = [10, 11, 12, 13]


def _fixture(rates=RATES, seeds=SEEDS) -> dict[str, object]:
    cells = []
    for topology, by_size in rates.items():
        for size, values in by_size.items():
            cells.append(
                {
                    "difficulty": "d",
                    "family": "f",
                    "swarm_size": size,
                    "topology": topology,
                    "attempt_budget_per_task": size,
                    "raw_trials": [
                        {"seed": seed, "metrics": {"verified_success_rate": value}}
                        for seed, value in zip(seeds, values)
                    ],
                }
            )
    return {
        "schema_version": 2,
        "experiment": "fixture",
        "generator": "fixture",
        "config": {"swarm_sizes": [1, 2, 5], "tasks_per_trial": 7},
        "cells": cells,
    }


def _group(analysis, topology):
    return next(g for g in analysis["groups"] if g["topology"] == topology)


class StructuralCountTests(unittest.TestCase):
    def test_messages_per_task_match_hand_counts(self) -> None:
        # flat: H->W, W->V, V->H for each of N workers.
        self.assertEqual([messages_per_task("flat", n) for n in (1, 2, 3, 10)], [3, 6, 9, 30])
        # role_specialized N=3: H->P 1, P->I 2, I->T 2, T->R 1, R->H 1 = 7.
        self.assertEqual(
            [messages_per_task("role_specialized", n) for n in (1, 2, 3, 10)],
            [3, 5, 7, 21],
        )
        # task_dag: three messages per attempt on either path.
        self.assertEqual([messages_per_task("task_dag", n) for n in (1, 2, 3, 10)], [3, 6, 9, 30])

    def test_team_of_one_is_the_same_in_every_topology(self) -> None:
        self.assertEqual({messages_per_task(t, 1) for t in r1_scaling.TOPOLOGIES}, {3})

    def test_reference_hops_and_replication_by_hand(self) -> None:
        self.assertEqual(all_to_all_reference_messages(5), 20)
        self.assertEqual(all_to_all_reference_messages(1), 0)
        self.assertEqual(critical_path_hops("flat", 5), (3, 3))
        self.assertEqual(critical_path_hops("role_specialized", 5), (5, 5))
        self.assertEqual(critical_path_hops("task_dag", 5), (3, 6))
        self.assertEqual(critical_path_hops("task_dag", 1), (3, 3))
        self.assertEqual(replicated_attempts_per_task("flat", 5), (4, 4))
        self.assertEqual(replicated_attempts_per_task("role_specialized", 5), (3, 3))
        self.assertEqual(replicated_attempts_per_task("role_specialized", 2), (0, 0))
        # N=5: 3 parent and 2 child attempts, so (3-1)+(2-1)=3 unblocked, 4 blocked.
        self.assertEqual(replicated_attempts_per_task("task_dag", 5), (3, 4))
        self.assertEqual(replicated_attempts_per_task("task_dag", 1), (0, 0))

    def test_rejects_bad_topology_and_size(self) -> None:
        with self.assertRaises(ValueError):
            messages_per_task("mesh", 3)
        for bad in (0, -1, True, 2.5):
            with self.assertRaises(ValueError):
                messages_per_task("flat", bad)  # type: ignore[arg-type]

    def test_duplicate_counting_on_a_hand_built_trace(self) -> None:
        trace = [["a", "b", "a", "a"], ["x", "y"], []]
        result = count_duplicated_attempts(trace)
        self.assertEqual(result["attempts"], 6)
        self.assertEqual(result["duplicated_attempts"], 2)
        self.assertEqual(result["distinct_attempts"], 4)
        self.assertEqual(result["duplicated_per_task"], [2, 0, 0])
        self.assertAlmostEqual(result["duplicated_fraction"], 2 / 6)

    def test_duplicates_are_never_matched_across_tasks(self) -> None:
        self.assertEqual(count_duplicated_attempts([["a"], ["a"]])["duplicated_attempts"], 0)
        self.assertIsNone(count_duplicated_attempts([])["duplicated_fraction"])


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_is_reproducible_and_seed_sensitive(self) -> None:
        values = [0.1, 0.4, 0.2, 0.9, 0.5]
        first = bootstrap_mean_ci(values, resamples=200, seed=3)
        self.assertEqual(first, bootstrap_mean_ci(values, resamples=200, seed=3))
        self.assertNotEqual(
            first["bootstrap_95_ci"],
            bootstrap_mean_ci(values, resamples=200, seed=4)["bootstrap_95_ci"],
        )
        self.assertAlmostEqual(first["mean"], 0.42)
        low, high = first["bootstrap_95_ci"]
        self.assertLessEqual(low, 0.42)
        self.assertGreaterEqual(high, 0.42)

    def test_constant_values_have_a_degenerate_interval(self) -> None:
        result = bootstrap_mean_ci([0.5] * 4, resamples=30, seed=1)
        self.assertEqual(result["bootstrap_95_ci"], [0.5, 0.5])
        self.assertEqual(result["classification"], "positive")

    def test_rejects_too_few_seeds_and_nonfinite_values(self) -> None:
        with self.assertRaises(ValueError):
            bootstrap_mean_ci([1.0], resamples=10, seed=0)
        with self.assertRaises(ValueError):
            bootstrap_mean_ci([1.0, math.inf], resamples=10, seed=0)


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = analyze_communication_burden(
            _fixture(), resamples=40, bootstrap_seed=5
        )

    def test_is_deterministic(self) -> None:
        again = analyze_communication_burden(_fixture(), resamples=40, bootstrap_seed=5)
        self.assertEqual(self.analysis, again)

    def test_curve_values_match_hand_computation(self) -> None:
        flat = _group(self.analysis, "flat")
        point = flat["points"][1]
        self.assertEqual(point["messages_per_task"], 6)
        self.assertEqual(point["messages_total_per_trial"], 42)
        self.assertEqual(point["count_label"], "structural, not measured bytes")
        # mean success 0.75 over 6 messages.
        self.assertAlmostEqual(point["verified_successes_per_message"]["mean"], 0.125)
        # N * (1 - rate) = 2 * 0.25 unproductive attempts per task.
        self.assertAlmostEqual(point["unproductive_attempts_per_task"]["mean"], 0.5)
        marginal = flat["marginal_success_per_added_message"][0]
        # (0.75 - 0.5) / (6 - 3).
        self.assertEqual(marginal["added_messages_per_task"], 3)
        self.assertAlmostEqual(
            marginal["success_gain_per_added_message"]["mean"], 0.25 / 3
        )

    def test_role_specialized_uses_its_own_message_counts(self) -> None:
        role = _group(self.analysis, "role_specialized")
        self.assertEqual([p["messages_per_task"] for p in role["points"]], [3, 5, 11])
        self.assertEqual(
            role["marginal_success_per_added_message"][1]["added_messages_per_task"], 6
        )

    def test_elasticity_is_the_log_log_slope_per_seed(self) -> None:
        flat = _group(self.analysis, "flat")
        xs = [math.log(m) for m in (3, 6, 15)]
        per_seed = []
        for index in range(4):
            ys = [math.log(RATES["flat"][n][index]) for n in (1, 2, 5)]
            mx, my = sum(xs) / 3, sum(ys) / 3
            per_seed.append(
                sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                / sum((x - mx) ** 2 for x in xs)
            )
        self.assertAlmostEqual(
            flat["success_vs_messages_elasticity"]["mean"], sum(per_seed) / 4
        )

    def test_contrast_against_flat_is_paired_and_signed(self) -> None:
        row = next(
            c for c in self.analysis["contrasts_vs_flat"] if c["topology"] == "role_specialized"
        )
        # N=2: role mean 0.55/5 = 0.11 versus flat 0.75/6 = 0.125.
        diff = row["per_message_difference_vs_flat"]["2"]
        self.assertAlmostEqual(diff["mean"], 0.11 - 0.125)
        self.assertEqual(diff["classification"], "negative")
        self.assertEqual(
            self.analysis["config"]["bootstrap_resamples"], 40
        )

    def test_duplication_is_reported_as_not_computable(self) -> None:
        self.assertIsNone(self.analysis["duplicated_attempts_in_r1_result"]["value"])
        self.assertIn("candidate identity", self.analysis["duplicated_attempts_in_r1_result"]["reason"])
        self.assertEqual(self.analysis["evidence_level"], "synthetic_mechanism")
        self.assertIn("structural, not measured bytes", render_markdown(self.analysis))

    def test_does_not_mutate_its_input(self) -> None:
        fixture = _fixture()
        snapshot = copy.deepcopy(fixture)
        analyze_communication_burden(fixture, resamples=10, bootstrap_seed=1)
        self.assertEqual(fixture, snapshot)

    def test_fails_closed_on_malformed_results(self) -> None:
        wrong_schema = _fixture()
        wrong_schema["schema_version"] = 1
        missing = _fixture()
        missing["cells"] = missing["cells"][:-1]
        wrong_budget = _fixture()
        wrong_budget["cells"][0]["attempt_budget_per_task"] = 99
        unknown = _fixture()
        unknown["cells"][0]["topology"] = "mesh"
        reordered = _fixture()
        reordered["cells"][0]["raw_trials"].reverse()
        duplicated = _fixture()
        duplicated["cells"].append(copy.deepcopy(duplicated["cells"][0]))
        for bad in (wrong_schema, missing, wrong_budget, unknown, reordered, duplicated):
            with self.assertRaises(ValueError):
                analyze_communication_burden(bad, resamples=5)

    def test_zero_rate_seed_is_dropped_from_elasticity_only(self) -> None:
        rates = copy.deepcopy(RATES)
        rates["flat"][1][0] = 0.0
        analysis = analyze_communication_burden(_fixture(rates), resamples=20)
        flat = _group(analysis, "flat")
        self.assertEqual(flat["success_vs_messages_elasticity"]["seeds_used"], 3)
        self.assertEqual(flat["points"][0]["verified_success_rate"]["n_seeds"], 4)
        contrast = next(c for c in analysis["contrasts_vs_flat"] if c["topology"] == "task_dag")
        self.assertIsNone(contrast["elasticity_difference_vs_flat"])


class GeneratorIsolationTests(unittest.TestCase):
    def test_generator_constants_are_untouched_by_analysis(self) -> None:
        before = (
            r1_scaling.TOPOLOGIES,
            r1_scaling.NOT_REPRESENTED_BASELINE,
            dict(r1_scaling.TOPOLOGY_CLOSES_GAP),
            r1_scaling.METRICS,
        )
        analyze_communication_burden(_fixture(), resamples=10)
        after = (
            r1_scaling.TOPOLOGIES,
            r1_scaling.NOT_REPRESENTED_BASELINE,
            dict(r1_scaling.TOPOLOGY_CLOSES_GAP),
            r1_scaling.METRICS,
        )
        self.assertEqual(before, after)

    def test_module_imports_only_constants_and_never_assigns_to_attributes(self) -> None:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "r1_scaling":
                imported.update(alias.name for alias in node.names)
            if isinstance(node, ast.Import):
                self.assertFalse(
                    any("r1_scaling" in alias.name for alias in node.names),
                    "import the generator's constants by name, never the module",
                )
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    self.assertNotIsInstance(target, ast.Attribute)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"setattr", "delattr", "exec", "eval"})
        self.assertEqual(imported, {"FLAT", "ROLE_SPECIALIZED", "TASK_DAG", "TOPOLOGIES"})


if __name__ == "__main__":
    unittest.main()
