import gzip
import hashlib
import json
from pathlib import Path
import unittest

from randomness_lab.r1_scaling import (
    FAMILIES,
    FLAT,
    NOT_REPRESENTED_BASELINE,
    ROLE_SPECIALIZED,
    TASK_DAG,
    TOPOLOGIES,
    R1ScalingConfig,
    render_markdown,
    run_r1_scaling,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/coordination-topology-seeds42-51.json.gz"
EXPECTED_SHA256 = "2815cc524584f72afa6ebde73bb0590ffca5f6db0589a7b4aad37fbed86ce419"


class R1TopologyScalingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = R1ScalingConfig(
            tasks_per_trial=25,
            trials=3,
            base_seed=17,
            swarm_sizes=(1, 2, 5),
            difficulty_levels=(("easy", 0.80), ("hard", 0.40)),
        )

    def run_all_topologies(self) -> dict[str, object]:
        return run_r1_scaling(self.config, topologies=TOPOLOGIES)

    def test_topology_run_is_deterministic_and_covers_every_arm(self) -> None:
        first = self.run_all_topologies()
        second = self.run_all_topologies()
        self.assertEqual(first, second)
        self.assertEqual(first["topologies"], list(TOPOLOGIES))
        self.assertEqual(len(first["cells"]), 54)
        for topology in TOPOLOGIES:
            arm = [cell for cell in first["cells"] if cell["topology"] == topology]
            self.assertEqual(len(arm), 18)
            self.assertTrue(all(len(cell["raw_trials"]) == 3 for cell in arm))

    def test_topology_arms_consume_the_same_budget_as_the_flat_arm(self) -> None:
        result = self.run_all_topologies()
        parity = result["topology_budget_parity"]
        self.assertEqual(len(parity), 2 * len(FAMILIES) * 3 * (len(TOPOLOGIES) - 1))
        for row in parity:
            for key, value in row.items():
                if key.startswith("equal_"):
                    self.assertTrue(value, f"{key} failed for {row}")

        for cell in result["cells"]:
            if cell["topology"] == FLAT or cell["swarm_size"] == 1:
                continue
            for trial in cell["raw_trials"]:
                metrics = trial["metrics"]
                self.assertEqual(
                    metrics["mean_attempt_units_per_task"], float(cell["swarm_size"])
                )
                self.assertEqual(
                    metrics["mean_verification_units_per_task"],
                    float(cell["swarm_size"]),
                )

    def test_matched_budget_makes_utility_and_success_exponent_deltas_identical(
        self,
    ) -> None:
        # Synthetic resource cost is identical across topologies at every N, so
        # log(utility) and log(success) differ only by a term that cancels in the
        # paired contrast. Any drift here means the budget stopped matching.
        result = self.run_all_topologies()
        by_key = {
            (
                row["difficulty"],
                row["family"],
                row["candidate_topology"],
                row["metric"],
            ): row
            for row in result["topology_exponent_contrasts"]
        }
        for (difficulty, family, topology, metric), row in by_key.items():
            if metric != "verified_success_rate":
                continue
            twin = by_key[
                (difficulty, family, topology, "verified_utility_per_unit_cost")
            ]
            self.assertAlmostEqual(
                row["exponent_delta"]["mean"],
                twin["exponent_delta"]["mean"],
                places=12,
            )

    def test_single_worker_cells_are_shared_across_topologies(self) -> None:
        result = self.run_all_topologies()
        baselines = {}
        for cell in result["cells"]:
            if cell["swarm_size"] != 1:
                continue
            key = (cell["difficulty"], cell["family"])
            baselines.setdefault(key, []).append(cell["raw_trials"])
        self.assertTrue(baselines)
        for trials in baselines.values():
            self.assertEqual(len(trials), len(TOPOLOGIES))
            for other in trials[1:]:
                self.assertEqual(trials[0], other)

    def test_exponents_are_reported_with_a_descriptive_interval(self) -> None:
        result = self.run_all_topologies()
        rows = result["topology_scaling_exponents"]
        self.assertEqual(len(rows), 2 * len(FAMILIES) * len(TOPOLOGIES) * 2)
        for row in rows:
            summary = row["exponent"]
            self.assertEqual(len(summary["normal_approx_95_ci"]), 2)
            self.assertIn(
                summary["classification"], {"positive", "negative", "uncertain"}
            )
            self.assertEqual(row["seeds_used"], [17, 18, 19])
        for row in result["topology_exponent_contrasts"]:
            self.assertEqual(row["baseline_topology"], FLAT)
            self.assertIn(row["candidate_topology"], {ROLE_SPECIALIZED, TASK_DAG})
            self.assertIsInstance(row["changes_exponent"], bool)

    def test_flat_only_run_keeps_the_v1_document_and_the_full_gap_ledger(self) -> None:
        legacy = run_r1_scaling(self.config)
        self.assertEqual(legacy["schema_version"], 1)
        self.assertEqual(legacy["generator"], "randomness_lab.r1_scaling.v1")
        self.assertNotIn("topology_scaling_exponents", legacy)
        self.assertEqual(
            legacy["issue_13_coverage"]["not_represented"],
            list(NOT_REPRESENTED_BASELINE),
        )
        self.assertNotIn("coordination topology", render_markdown(legacy))

    def test_topology_run_closes_exactly_the_two_topology_gaps(self) -> None:
        result = self.run_all_topologies()
        closed = set(NOT_REPRESENTED_BASELINE) - set(
            result["issue_13_coverage"]["not_represented"]
        )
        self.assertEqual(
            closed,
            {
                "planner plus implementer plus tester plus reviewer topology",
                "task-DAG team topology",
            },
        )
        self.assertIn(
            "real held-out software tasks",
            result["issue_13_coverage"]["not_represented"],
        )
        self.assertIn(
            "measured inference cost, reviewer minutes, communication bytes, and duplication",
            result["issue_13_coverage"]["not_represented"],
        )
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertIn("cannot close issue #13", result["interpretation_guardrail"])
        report = render_markdown(result)
        self.assertIn("synthetic mechanism only", report)
        self.assertIn("Scaling exponent by coordination topology", report)

    def test_topology_selection_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            run_r1_scaling(self.config, topologies=(ROLE_SPECIALIZED,))
        with self.assertRaises(ValueError):
            run_r1_scaling(self.config, topologies=(FLAT, FLAT))
        with self.assertRaises(ValueError):
            run_r1_scaling(self.config, topologies=(FLAT, "star"))


class R1TopologyReferenceTests(unittest.TestCase):
    def test_frozen_topology_result_digest_and_evidence_boundary(self) -> None:
        payload = RESULT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_SHA256)
        result = json.loads(gzip.decompress(payload))
        self.assertEqual(result["generator"], "randomness_lab.r1_scaling.v2")
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertEqual(result["topologies"], list(TOPOLOGIES))
        self.assertEqual(result["config"]["swarm_sizes"], [1, 2, 5, 10])
        self.assertEqual(len(result["cells"]), 108)
        self.assertIn(
            "real held-out software tasks",
            result["issue_13_coverage"]["not_represented"],
        )

    def test_frozen_topology_result_keeps_every_seed_and_matched_budget(self) -> None:
        result = json.loads(gzip.decompress(RESULT.read_bytes()))
        expected_seeds = list(range(42, 52))
        for cell in result["cells"]:
            self.assertEqual(
                [trial["seed"] for trial in cell["raw_trials"]], expected_seeds
            )
        for row in result["topology_budget_parity"]:
            for key, value in row.items():
                if key.startswith("equal_"):
                    self.assertTrue(value, f"{key} failed for {row}")


if __name__ == "__main__":
    unittest.main()
