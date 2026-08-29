from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_USE = re.compile(r"^\s*uses:\s*[^\s]+@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)
CODEQL_V4_PIN = "f205ea1c3313d32999d8d6a48b4f6530d4437b38"


class SecurityAutomationTests(unittest.TestCase):
    def test_codeql_has_least_privilege_and_no_target_event(self) -> None:
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("security-events: write", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_codeql_actions_are_immutable_pins(self) -> None:
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        uses_lines = [line for line in workflow.splitlines() if line.strip().startswith("uses:")]
        self.assertEqual(len(uses_lines), 3)
        self.assertEqual(len(FULL_SHA_USE.findall(workflow)), len(uses_lines))
        self.assertEqual(workflow.count(f"github/codeql-action/init@{CODEQL_V4_PIN}"), 1)
        self.assertEqual(workflow.count(f"github/codeql-action/analyze@{CODEQL_V4_PIN}"), 1)

    def test_dependabot_covers_actions_and_python_dependencies(self) -> None:
        config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", config)
        self.assertIn("package-ecosystem: pip", config)
        self.assertEqual(config.count("open-pull-requests-limit: 3"), 2)
        self.assertEqual(config.count("dependency-name: \"*\""), 2)
        self.assertEqual(config.count("version-update:semver-major"), 2)

    def test_scorecard_is_pinned_bounded_and_least_privilege(self) -> None:
        workflow = (ROOT / ".github/workflows/scorecard.yml").read_text(encoding="utf-8")
        self.assertIn("security-events: write", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("publish_results: false", workflow)
        self.assertIn("retention-days: 5", workflow)
        self.assertEqual(workflow.count(f"github/codeql-action/upload-sarif@{CODEQL_V4_PIN}"), 1)

        uses_lines = [line for line in workflow.splitlines() if line.strip().startswith("uses:")]
        self.assertEqual(len(uses_lines), 4)
        self.assertEqual(len(FULL_SHA_USE.findall(workflow)), len(uses_lines))


if __name__ == "__main__":
    unittest.main()
