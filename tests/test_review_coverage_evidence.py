"""Review/approval coverage must say how many ready PRs stand behind the figure.

``review_coverage`` is a policy input that defaults to 1.0 when nothing is
waiting for review. Without an evidence block, 0 ready PRs and 100 reviewed
ready PRs both read "1.0". These tests pin that the point values stay exactly as
they were while a Beta-Binomial block records the observed sample size.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evolution_live_governor as governor  # noqa: E402
import repository_evolution_score as score  # noqa: E402

MODULES = (("repository_evolution_score", score), ("evolution_live_governor", governor))


def _snapshot(*, ready: int, reviewed: int, approved: int = 0, drafts: int = 0) -> dict:
    prs = []
    for index in range(ready):
        prs.append(
            {
                "number": 100 + index,
                "draft": False,
                "independent_review_count": 1 if index < reviewed else 0,
                "independent_approval_count": 1 if index < approved else 0,
            }
        )
    for index in range(drafts):
        prs.append(
            {
                "number": 500 + index,
                "draft": True,
                "independent_review_count": 1,
                "independent_approval_count": 1,
            }
        )
    return {"open_pull_requests": prs}


class ReviewCoverageEvidenceTests(unittest.TestCase):
    def test_empty_ready_set_keeps_default_but_is_labelled_prior_only(self):
        for name, module in MODULES:
            with self.subTest(module=name):
                result = module.review_metrics(_snapshot(ready=0, reviewed=0))
                self.assertEqual(result["review_coverage"], 1.0)
                self.assertEqual(result["approval_coverage"], 1.0)
                for key in ("review_coverage_evidence", "approval_coverage_evidence"):
                    evidence = result[key]
                    self.assertEqual(evidence["evidence_status"], "prior_only_no_observations")
                    self.assertEqual(evidence["observed_sample_size"], 0)
                    self.assertIsNone(evidence["empirical_rate"])

    def test_same_point_value_different_evidence_mass(self):
        for name, module in MODULES:
            with self.subTest(module=name):
                one = module.review_metrics(_snapshot(ready=1, reviewed=1))
                many = module.review_metrics(_snapshot(ready=100, reviewed=100))
                self.assertEqual(one["review_coverage"], many["review_coverage"])
                self.assertEqual(one["review_coverage_evidence"]["observed_sample_size"], 1)
                self.assertEqual(many["review_coverage_evidence"]["observed_sample_size"], 100)
                one_low = one["review_coverage_evidence"]["credible_interval_95"][0]
                many_low = many["review_coverage_evidence"]["credible_interval_95"][0]
                self.assertLess(one_low, 0.5)
                self.assertGreater(many_low, 0.95)

    def test_drafts_are_not_counted_as_observations(self):
        for name, module in MODULES:
            with self.subTest(module=name):
                result = module.review_metrics(_snapshot(ready=2, reviewed=1, drafts=7))
                self.assertEqual(result["ready_prs"], 2)
                self.assertEqual(result["review_coverage"], 0.5)
                evidence = result["review_coverage_evidence"]
                self.assertEqual((evidence["successes"], evidence["trials"]), (1, 2))

    def test_approval_evidence_is_independent_of_review_evidence(self):
        for name, module in MODULES:
            with self.subTest(module=name):
                result = module.review_metrics(_snapshot(ready=4, reviewed=4, approved=1))
                self.assertEqual(result["review_coverage"], 1.0)
                self.assertEqual(result["approval_coverage"], 0.25)
                self.assertEqual(result["review_coverage_evidence"]["successes"], 4)
                self.assertEqual(result["approval_coverage_evidence"]["successes"], 1)

    def test_both_implementations_agree(self):
        for ready, reviewed, approved in ((0, 0, 0), (3, 1, 0), (5, 5, 2)):
            with self.subTest(ready=ready, reviewed=reviewed, approved=approved):
                snapshot = _snapshot(ready=ready, reviewed=reviewed, approved=approved)
                self.assertEqual(score.review_metrics(snapshot), governor.review_metrics(snapshot))


if __name__ == "__main__":
    unittest.main()
