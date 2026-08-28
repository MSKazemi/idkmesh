import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-community-growth.yml"


class AceWorkflowHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_action_dependency_is_pinned(self):
        self.assertIn(
            "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b",
            self.text,
        )
        self.assertNotIn("actions/github-script@v7", self.text)

    def test_privileged_workflow_never_checks_out_or_shell_executes_pr_code(self):
        self.assertNotIn("actions/checkout", self.text)
        self.assertNotRegex(self.text, re.compile(r"^\s+run:\s*", re.MULTILINE))
        self.assertNotIn("contents: write", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("issues: write", self.text)
        self.assertIn("pull-requests: read", self.text)

    def test_untrusted_marker_is_not_authorization(self):
        self.assertIn("trustedIssueAuthors", self.text)
        self.assertIn("author_association", self.text)
        self.assertIn("trustedIssueAuthors.has(association)", self.text)

    def test_ledger_has_owned_identity_and_fail_closed_state(self):
        self.assertIn("ace:ledger", self.text)
        self.assertIn("github.paginate", self.text)
        self.assertIn("refusing to overwrite state", self.text)
        self.assertIn("refusing to reset it", self.text)

    def test_generated_seed_does_not_copy_untrusted_pr_title(self):
        self.assertNotIn("pr.title", self.text)
        self.assertIn("`- PR: #${pr.number}`", self.text)

    def test_actual_branch_protection_gates_actuation(self):
        self.assertIn("github.rest.repos.getBranch", self.text)
        self.assertIn("const mainProtected = Boolean(mainBranch.protected);", self.text)
        self.assertIn("const actuationAllowed = mainProtected;", self.text)
        self.assertIn("if (!mainProtected || state.review_load > K) mode = 'CONSOLIDATE';", self.text)
        self.assertIn("if (actuationAllowed && event === 'pull_request_target'", self.text)

    def test_seed_deduplication_requires_growth_seed_label(self):
        self.assertIn("label.name === 'growth-seed'", self.text)
        self.assertIn("spawned-from:pr-${pr.number}", self.text)


if __name__ == "__main__":
    unittest.main()
