"""Pin the root README inside the contributor-command drift guard."""

from __future__ import annotations

from pathlib import Path
import unittest

from tools.contributor_command_guard import CANONICAL_DOCS, inspect_repository

REPO_ROOT = Path(__file__).resolve().parents[1]


class RootReadmeCommandGuardTests(unittest.TestCase):
    def test_root_readme_is_a_guarded_first_contact_surface(self) -> None:
        self.assertIn("README.md", CANONICAL_DOCS)

    def test_current_root_readme_agrees_with_executable_commands(self) -> None:
        findings = inspect_repository(REPO_ROOT)
        readme_findings = [finding for finding in findings if finding.source == "README.md"]
        self.assertEqual(readme_findings, [])


if __name__ == "__main__":
    unittest.main()
