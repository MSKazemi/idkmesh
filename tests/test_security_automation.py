from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_USE = re.compile(r"^\s*uses:\s*[^\s]+@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)


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

    def test_dependabot_covers_actions_and_python_dependencies(self) -> None:
        config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", config)
        self.assertIn("package-ecosystem: pip", config)
        self.assertEqual(config.count("open-pull-requests-limit: 3"), 2)


if __name__ == "__main__":
    unittest.main()
