import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-cohort-observer.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class AceCohortObserverContractTests(unittest.TestCase):
    def test_privileged_observer_does_not_checkout_or_run_pr_code(self):
        self.assertNotIn("actions/checkout", TEXT)
        self.assertNotIn("run:", TEXT)

    def test_action_dependency_is_immutable(self):
        self.assertIn(
            "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b",
            TEXT,
        )

    def test_bootstrap_seed_admission_requires_trusted_provenance(self):
        self.assertIn("trustedSeedAuthors", TEXT)
        self.assertIn("issue.author_association", TEXT)
        self.assertIn("trustedSeedAuthors.has(issue.author_association || 'NONE')", TEXT)
        self.assertIn("cohort=bootstrap-1", TEXT)

    def test_observatory_identity_is_workflow_owned(self):
        self.assertIn("const statusLabel = 'ace:cohort-observer';", TEXT)
        self.assertIn("label.name === statusLabel", TEXT)
        self.assertIn("ACE_COHORT_STATE", TEXT)

    def test_snapshot_does_not_claim_full_reproduction_number(self):
        self.assertIn("metric_scope: 'bootstrap_growth_seed_exposure'", TEXT)
        self.assertIn("full_r_community_ready: false", TEXT)
        self.assertIn("not yet the full", TEXT.lower())

    def test_verification_label_is_observed_not_auto_applied(self):
        self.assertIn("const verifiedLabel = 'ace:verified-descendant';", TEXT)
        self.assertNotIn("labels: [verifiedLabel]", TEXT)

    def test_observer_never_auto_creates_cohort_two(self):
        self.assertIn("EVALUATE_COHORT_2", TEXT)
        self.assertNotIn("title: '[ACE] Bootstrap Cohort 2", TEXT)

    def test_permissions_do_not_include_contents_write(self):
        self.assertIn("contents: read", TEXT)
        self.assertNotIn("contents: write", TEXT)


if __name__ == "__main__":
    unittest.main()
