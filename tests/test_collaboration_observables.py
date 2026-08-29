import copy
import json
import random
import unittest
from pathlib import Path

from scripts.collaboration_observables import analyze, serialize


ROOT = Path(__file__).resolve().parents[1]


class CollaborationObservablesTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(
            (ROOT / "tests/fixtures/collaboration_observables_snapshot.json").read_text()
        )

    def test_metrics_match_frozen_observations(self):
        result = analyze(self.snapshot)
        metrics = result["metrics"]
        self.assertEqual(36.0, metrics["first_independent_review_latency"]["median_hours"])
        self.assertEqual(1, metrics["first_independent_review_latency"]["right_censored"])
        self.assertEqual(2, metrics["review_queue"]["open_review_ready"])
        self.assertEqual(60.0, metrics["review_queue"]["median_age_hours"])
        self.assertEqual(0.555556, metrics["review_concentration"]["hhi"])
        self.assertEqual(0.625, metrics["ownership_concentration"]["hhi"])
        self.assertEqual(2, metrics["structural_debt"]["observed_findings"])
        self.assertEqual(6, metrics["ci_evidence"]["successes"])
        self.assertEqual(8, metrics["ci_evidence"]["trials"])
        self.assertEqual(2, metrics["contributor_recurrence"]["successes"])

    def test_replay_is_invariant_to_record_order(self):
        expected = serialize(analyze(self.snapshot))
        changed = copy.deepcopy(self.snapshot)
        random.Random(86).shuffle(changed["pull_requests"])
        random.Random(87).shuffle(changed["contributors"])
        self.assertEqual(expected, serialize(analyze(changed)))

    def test_priors_come_only_from_verified_outcomes(self):
        rows = analyze(self.snapshot)["evidence_derived_strategy_priors"]
        self.assertEqual(["documentation", "verification"], [row["strategy"] for row in rows])
        self.assertAlmostEqual(1.0, sum(row["normalized_weight"] for row in rows), places=5)
        self.assertEqual(2, rows[1]["evidence"]["trials"])

    def test_invalid_ci_counts_fail_closed(self):
        changed = copy.deepcopy(self.snapshot)
        changed["pull_requests"][0]["ci_checks"] = {"passed": 3, "total": 2}
        with self.assertRaisesRegex(ValueError, "CI check counts"):
            analyze(changed)

    def test_future_contribution_fails_closed(self):
        changed = copy.deepcopy(self.snapshot)
        changed["contributors"][0]["meaningful_contributions"].append("2026-09-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "after cutoff"):
            analyze(changed)

    def test_self_review_and_self_report_fail_closed(self):
        changed = copy.deepcopy(self.snapshot)
        changed["pull_requests"][0]["independent_reviewers"] = ["carol"]
        with self.assertRaisesRegex(ValueError, "author or bot"):
            analyze(changed)
        changed = copy.deepcopy(self.snapshot)
        changed["pull_requests"][0]["verification_independent"] = False
        with self.assertRaisesRegex(ValueError, "independent verification"):
            analyze(changed)

    def test_output_grants_no_causal_or_write_authority(self):
        authority = analyze(self.snapshot)["authority"]
        self.assertEqual({"causal_claim": False, "policy_activation": False, "github_write": False}, authority)

    def test_causal_study_is_preregistered_without_outcomes(self):
        protocol = json.loads(
            (ROOT / "experiments/E023-first-review-latency-recurrence.json").read_text()
        )
        self.assertEqual("preregistered_no_outcomes", protocol["status"])
        self.assertEqual(90, protocol["outcome"]["window_days"])
        self.assertFalse(protocol["interpretation"]["causal_claim_allowed"])
        self.assertNotIn("results", protocol)


if __name__ == "__main__":
    unittest.main()
