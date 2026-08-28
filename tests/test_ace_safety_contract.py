import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-community-growth.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class AceSafetyContractTests(unittest.TestCase):
    def test_privileged_workflow_does_not_checkout_pr_code(self):
        self.assertNotIn("actions/checkout", TEXT)
        self.assertNotRegex(TEXT, r"\brun:\s*")

    def test_third_party_action_is_pinned(self):
        self.assertIn(
            "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b",
            TEXT,
        )

    def test_main_protection_fail_closed_gate_exists(self):
        self.assertIn("github.rest.repos.getBranch", TEXT)
        self.assertIn("const mainProtected = Boolean(mainBranch.protected);", TEXT)
        self.assertIn("const actuationAllowed = mainProtected;", TEXT)
        self.assertIn("if (!mainProtected || state.review_load > K) mode = 'CONSOLIDATE';", TEXT)
        self.assertIn("if (actuationAllowed && event === 'pull_request_target'", TEXT)

    def test_untrusted_seed_marker_is_not_authorization(self):
        self.assertIn("trustedIssueAuthors", TEXT)
        self.assertIn("issue?.author_association", TEXT)
        self.assertIn("trustedIssueAuthors.has(association)", TEXT)

    def test_ledger_identity_and_parse_fail_closed(self):
        self.assertIn("ace:ledger", TEXT)
        self.assertIn("github.paginate", TEXT)
        self.assertIn("refusing to overwrite state", TEXT)
        self.assertIn("refusing to reset it", TEXT)

    def test_generated_seed_dedupe_requires_growth_seed_label(self):
        self.assertRegex(
            TEXT,
            re.compile(
                r"some\(label => label\.name === 'growth-seed'\).*?includes\(marker\)",
                re.DOTALL,
            ),
        )

    def test_generated_issue_does_not_interpolate_pr_title(self):
        self.assertNotIn("${pr.title}", TEXT)

    def test_permissions_do_not_include_contents_write(self):
        self.assertIn("contents: read", TEXT)
        self.assertNotIn("contents: write", TEXT)


if __name__ == "__main__":
    unittest.main()
