import gzip
import hashlib
import json
import math
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

    def test_flat_arm_still_regenerates_the_committed_payload(self) -> None:
        # The coordination-topology arms must not perturb the frozen flat run.
        #
        # This compares values rather than bytes. The committed payload
        # reproduces byte for byte on the platform that generated it, but not on
        # every platform: the simulation goes through libm (`exp`, `**`), whose
        # last-place rounding is not identical across CPUs and C libraries, and
        # a one-ulp difference changes the JSON repr and therefore the digest.
        # Asserting bytes here would make the test assert something about the
        # runner rather than about this change.
        result = run_r1_scaling(
            R1ScalingConfig(
                tasks_per_trial=200,
                trials=10,
                base_seed=42,
                swarm_sizes=(1, 2, 5, 10),
                difficulty_levels=(("easy", 0.82), ("medium", 0.65), ("hard", 0.45)),
            )
        )
        # Round-trip through JSON so tuples compare against the arrays they
        # serialize to, rather than failing on container type.
        replayed = json.loads(json.dumps(result, sort_keys=True))
        committed = json.loads(gzip.decompress(RESULT.read_bytes()))
        self._assert_equivalent(replayed, committed, path="$")

        # The rendered table is generated from the same values, so it is checked
        # for shape rather than for bytes, for the same libm reason.
        rendered = render_markdown(result).splitlines()
        self.assertEqual(len(rendered), len(REPORT.read_text(encoding="utf-8").splitlines()))

    def _assert_equivalent(self, actual, expected, *, path: str) -> None:
        self.assertIs(type(actual), type(expected), msg=path)
        if isinstance(expected, dict):
            self.assertEqual(sorted(actual), sorted(expected), msg=path)
            for key in expected:
                self._assert_equivalent(actual[key], expected[key], path=f"{path}.{key}")
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), msg=path)
            for index, item in enumerate(expected):
                self._assert_equivalent(actual[index], item, path=f"{path}[{index}]")
        elif isinstance(expected, float):
            self.assertTrue(
                math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12),
                msg=f"{path}: {actual!r} is not within tolerance of {expected!r}",
            )
        else:
            self.assertEqual(actual, expected, msg=path)


if __name__ == "__main__":
    unittest.main()
