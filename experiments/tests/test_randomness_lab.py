import argparse
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "experiments" / "randomness_lab.py"
spec = importlib.util.spec_from_file_location("randomness_lab", MODULE_PATH)
lab = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = lab
spec.loader.exec_module(lab)


class RandomnessLabTests(unittest.TestCase):
    def make_args(self):
        return argparse.Namespace(
            policy="all",
            workers=5,
            tasks=40,
            trials=4,
            seed=12345,
            shared_outcome_probability=0.3,
            churn_probability=0.05,
            verifier_accuracy=0.98,
            output=Path("unused.jsonl"),
            summary=Path("unused-summary.json"),
        )

    def test_reproducible_for_fixed_seed(self):
        args = self.make_args()
        records_a, summary_a = lab.run_experiment(args)
        records_b, summary_b = lab.run_experiment(args)
        self.assertEqual(records_a, records_b)
        self.assertEqual(summary_a, summary_b)

    def test_all_policies_are_exercised(self):
        records, summary = lab.run_experiment(self.make_args())
        self.assertEqual(set(summary["summary"]), set(lab.POLICY_NAMES))
        self.assertEqual(len(records), len(lab.POLICY_NAMES) * 4)

    def test_perfect_verifier_never_accepts_bad_work(self):
        workers = lab.build_workers(5, 99)
        workload = lab.generate_workload(workers, 100, 77, 0.4, 0.0)
        result = lab.run_policy("thompson", workers, workload, 77, 1.0)
        self.assertEqual(result["escaped_failures"], 0)

    def test_shared_workload_is_identical_across_repeated_generation(self):
        workers = lab.build_workers(4, 17)
        first = lab.generate_workload(workers, 30, 999, 0.6, 0.1)
        second = lab.generate_workload(workers, 30, 999, 0.6, 0.1)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
