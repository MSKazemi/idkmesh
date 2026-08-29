import hashlib
import json
from pathlib import Path
import sys
import unittest

from randomness_lab.r4 import (
    default_r4_environment,
    lockin_r4_environment,
    run_r4_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "results" / "experiments" / "r4"
REFERENCE_RUNTIME = (3, 12)


class R4ReferenceEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {
            "reference-default.json": {
                "environment": default_r4_environment(
                    steps=800,
                    shift_step=400,
                    task_seed=42,
                    outcome_seed=4242,
                ),
                "policy_seed": 1337,
                "sha256": "29af5b29dbb2ddb7c231f497814b6a7ee3757190f84b1e4403c5314933f0a963",
            },
            "reference-lockin.json": {
                "environment": lockin_r4_environment(
                    steps=500,
                    shift_step=100,
                    task_seed=11,
                    outcome_seed=1111,
                ),
                "policy_seed": 77,
                "sha256": "f89cc9723054bfa1aa94762ba46fa74e5fbbb823e4c2691110a34942270e6bde",
            },
        }

    def test_committed_references_match_hashes_and_replay_contract(self):
        for filename, case in self.cases.items():
            with self.subTest(filename=filename):
                path = REFERENCE_DIR / filename
                actual_bytes = path.read_bytes()
                self.assertEqual(
                    hashlib.sha256(actual_bytes).hexdigest(),
                    case["sha256"],
                )
                regenerated = run_r4_benchmark(
                    case["environment"],
                    policy_seed=case["policy_seed"],
                    include_events=True,
                )
                committed = json.loads(actual_bytes)
                self.assertEqual(
                    json.loads(json.dumps(regenerated["environment"])),
                    committed["environment"],
                )
                self.assertEqual(regenerated["trace_digest"], committed["trace_digest"])
                self.assertEqual(regenerated["policy_seed"], committed["policy_seed"])
                self.assertEqual(
                    set(regenerated["policies"]),
                    set(committed["policies"]),
                )
                for policy_name, result in regenerated["policies"].items():
                    if policy_name.startswith("stigmergy-"):
                        self.assertEqual(
                            result["metrics"][
                                "unverified_activity_pheromone_increase"
                            ],
                            0.0,
                        )
                if filename == "reference-lockin.json":
                    permanent = regenerated["policies"]["stigmergy-no-evap"]["metrics"]
                    adaptive = regenerated["policies"]["stigmergy-evap-explore"][
                        "metrics"
                    ]
                    self.assertGreater(
                        permanent["cumulative_expected_regret"],
                        adaptive["cumulative_expected_regret"],
                    )
                    self.assertLess(
                        permanent["post_shift_verified_success_rate"],
                        adaptive["post_shift_verified_success_rate"],
                    )
                if sys.version_info[:2] == REFERENCE_RUNTIME:
                    expected_bytes = (
                        json.dumps(regenerated, indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                    self.assertEqual(actual_bytes, expected_bytes)

    def test_reference_preserves_integrity_and_harmful_lockin_evidence(self):
        for filename in self.cases:
            with self.subTest(filename=filename):
                report = json.loads((REFERENCE_DIR / filename).read_text())
                self.assertEqual(
                    {result["trace_digest"] for result in report["policies"].values()},
                    {report["trace_digest"]},
                )
                for policy_name, result in report["policies"].items():
                    if policy_name.startswith("stigmergy-"):
                        self.assertEqual(
                            result["metrics"][
                                "unverified_activity_pheromone_increase"
                            ],
                            0.0,
                        )

        lockin = json.loads(
            (REFERENCE_DIR / "reference-lockin.json").read_text()
        )["policies"]
        permanent = lockin["stigmergy-no-evap"]["metrics"]
        adaptive = lockin["stigmergy-evap-explore"]["metrics"]
        thompson = lockin["thompson"]["metrics"]
        self.assertGreater(
            permanent["cumulative_expected_regret"],
            adaptive["cumulative_expected_regret"],
        )
        self.assertLess(
            permanent["post_shift_verified_success_rate"],
            adaptive["post_shift_verified_success_rate"],
        )
        self.assertGreater(
            permanent["longest_failed_same_worker_lockin"],
            adaptive["longest_failed_same_worker_lockin"],
        )
        self.assertGreater(
            thompson["verified_success_rate"],
            adaptive["verified_success_rate"],
        )


if __name__ == "__main__":
    unittest.main()
