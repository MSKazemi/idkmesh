import hashlib
import json
from pathlib import Path
import unittest

from experiments.verification_scaling_matrix import (
    MODES,
    benchmark,
    evidence_bundle,
    make_candidate,
    simulate,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "experiments"
    / "results"
    / "E022-verification-scaling-matrix-20-seed-summary.json"
)
REFERENCE_SHA256 = "074934de6f15eb60b28a6ad5a1ade3f8760a53b6343235290eaf333f01872ca4"


class VerificationScalingMatrixTests(unittest.TestCase):
    def test_all_seven_required_modes_are_present(self):
        self.assertEqual(
            set(MODES),
            {
                "no-independent-verification",
                "one-reviewer",
                "fixed-three-reviewer-quorum",
                "independent-tests",
                "tests-plus-adversarial-reviewer",
                "risk-adaptive",
                "risk-adaptive-backpressure",
            },
        )

    def test_candidate_and_run_are_seed_reproducible(self):
        self.assertEqual(make_candidate(7, 19), make_candidate(7, 19))
        kwargs = dict(
            mode="risk-adaptive-backpressure",
            seed=7,
            steps=40,
            initial_fanout=12,
            verification_capacity_per_window=8.0,
        )
        self.assertEqual(simulate(**kwargs), simulate(**kwargs))

    def test_fixed_modes_receive_the_same_candidate_stream(self):
        digests = set()
        for mode in MODES[:-1]:
            run = simulate(
                mode=mode,
                seed=4,
                steps=30,
                initial_fanout=4,
                verification_capacity_per_window=8.0,
            )
            digests.add(run["generated_stream_sha256"])
        self.assertEqual(len(digests), 1)

    def test_no_verification_is_not_mislabeled_as_verified_output(self):
        run = simulate(
            mode="no-independent-verification",
            seed=3,
            steps=20,
            initial_fanout=4,
            verification_capacity_per_window=8.0,
        )
        self.assertEqual(run["independently_examined_candidates"], 0)
        self.assertEqual(run["verified_useful_accepted_candidates"], 0)
        self.assertGreater(run["escaped_defects"], 0)
        self.assertEqual(run["integration_authority"], "none")

    def test_risk_adaptive_bundle_escalates_with_risk(self):
        candidates = [make_candidate(9, index) for index in range(100)]
        low = min(candidates, key=lambda candidate: candidate.risk)
        high = max(candidates, key=lambda candidate: candidate.risk)
        self.assertEqual(evidence_bundle("risk-adaptive", low), ("independent-test",))
        self.assertEqual(
            evidence_bundle("risk-adaptive", high),
            ("independent-test", "adversarial-reviewer"),
        )

    def test_backpressure_reduces_overload_without_acceptance_authority(self):
        kwargs = dict(
            seed=5,
            steps=80,
            initial_fanout=12,
            verification_capacity_per_window=8.0,
        )
        fixed = simulate(mode="risk-adaptive", **kwargs)
        adaptive = simulate(mode="risk-adaptive-backpressure", **kwargs)
        self.assertLess(adaptive["pending_candidates"], fixed["pending_candidates"])
        self.assertLess(adaptive["peak_queue_length"], fixed["peak_queue_length"])
        self.assertLess(adaptive["final_fanout"], 12)
        self.assertEqual(adaptive["integration_authority"], "none")

    def test_summary_covers_every_fanout_mode_cell(self):
        result = benchmark(
            seeds=2,
            steps=10,
            fanouts=[2, 8],
            verification_capacity_per_window=8.0,
            include_runs=False,
        )
        cells = {
            (row["initial_fanout"], row["mode"])
            for row in result["summaries"]
        }
        self.assertEqual(cells, {(fanout, mode) for fanout in (2, 8) for mode in MODES})
        self.assertNotIn("runs", result)

    def test_reference_summary_preserves_success_and_tradeoff_claims(self):
        raw = REFERENCE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), REFERENCE_SHA256)
        report = json.loads(raw)
        self.assertEqual(report["modes"], list(MODES))
        self.assertEqual(report["authority"]["integration_authority"], "none")
        cells = {
            (row["initial_fanout"], row["mode"]): row
            for row in report["summaries"]
        }
        fixed = cells[(8, "risk-adaptive")]
        controlled = cells[(8, "risk-adaptive-backpressure")]
        tests_only = cells[(8, "independent-tests")]
        adversarial = cells[(8, "tests-plus-adversarial-reviewer")]
        unsafe = cells[(8, "no-independent-verification")]
        self.assertLess(
            controlled["pending_candidates"]["mean"],
            fixed["pending_candidates"]["mean"],
        )
        self.assertGreaterEqual(
            controlled["verified_useful_throughput_per_window"]["mean"],
            0.95 * fixed["verified_useful_throughput_per_window"]["mean"],
        )
        self.assertLessEqual(
            controlled["escaped_defects"]["mean"],
            fixed["escaped_defects"]["mean"] + 1.0,
        )
        self.assertGreater(
            tests_only["escaped_defects"]["mean"],
            adversarial["escaped_defects"]["mean"],
        )
        self.assertEqual(
            unsafe["verified_useful_accepted_candidates"]["mean"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
