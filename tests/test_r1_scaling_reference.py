import gzip
import hashlib
import json
from pathlib import Path
import unittest

from randomness_lab.r1_scaling import (
    R1ScalingConfig,
    render_markdown,
    run_r1_scaling,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/collective-scaling-seeds42-51.json.gz"
REPORT = ROOT / "results/experiments/r1/collective-scaling-seeds42-51.md"
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

    def test_flat_arm_still_regenerates_the_committed_payload_exactly(self) -> None:
        # The coordination-topology arms must not perturb the frozen flat run,
        # so the default flat-only invocation is replayed and compared byte for
        # byte against the committed payload and its rendered table.
        result = run_r1_scaling(
            R1ScalingConfig(
                tasks_per_trial=200,
                trials=10,
                base_seed=42,
                swarm_sizes=(1, 2, 5, 10),
                difficulty_levels=(("easy", 0.82), ("medium", 0.65), ("hard", 0.45)),
            )
        )
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        self.assertEqual(
            rendered.encode("utf-8"),
            gzip.decompress(RESULT.read_bytes()),
        )
        self.assertEqual(
            render_markdown(result).encode("utf-8"),
            REPORT.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
