import gzip
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/collective-scaling-seeds42-51.json.gz"
EXPECTED_SHA256 = "77771304719c746637a575bb414c79278341e4933dd2e7f7e84db3b822043280"


class R1ScalingReferenceTests(unittest.TestCase):
    def test_frozen_result_digest_and_evidence_boundary(self) -> None:
        payload = RESULT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_SHA256)
        result = json.loads(gzip.decompress(payload))
        self.assertEqual(result["generator"], "randomness_lab.r1_scaling.v1")
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertEqual(result["config"]["swarm_sizes"], [1, 2, 5, 10])
        self.assertEqual(len(result["cells"]), 36)
        self.assertIn(
            "real held-out software tasks",
            result["issue_13_coverage"]["not_represented"],
        )

    def test_every_reference_cell_retains_all_seed_trials(self) -> None:
        result = json.loads(gzip.decompress(RESULT.read_bytes()))
        expected_seeds = list(range(42, 52))
        for cell in result["cells"]:
            self.assertEqual(
                [trial["seed"] for trial in cell["raw_trials"]], expected_seeds
            )


if __name__ == "__main__":
    unittest.main()
