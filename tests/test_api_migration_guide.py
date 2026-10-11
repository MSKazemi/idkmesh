"""Guards for docs/API_V1_BETA_MIGRATION_GUIDE.md (issue #747).

The guide makes checkable claims -- that each behaviour change has a test, that
no deprecation is in force -- so they are checked rather than trusted.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE = REPO_ROOT / "docs" / "API_V1_BETA_MIGRATION_GUIDE.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


class MigrationGuideTests(unittest.TestCase):
    def setUp(self):
        self.text = GUIDE.read_text(encoding="utf-8")

    def test_the_guide_has_the_sections_the_gate_requires(self):
        for heading in (
            "## What you can rely on",
            "## What is not stable yet",
            "## How change is announced",
            "## Behaviour changes to check",
            "## Making your integration robust",
            "## Checking a revision",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.text)

    def test_every_repository_path_it_names_exists(self):
        paths = set(re.findall(r"`((?:tests|tools|docs|schemas)/[A-Za-z0-9_./-]+)`", self.text))
        self.assertGreaterEqual(len(paths), 6)
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).exists(), path)

    def test_each_behaviour_row_names_the_test_that_covers_it(self):
        table = self.text.split("## Behaviour changes to check")[1].split("##")[0]
        rows = [r for r in table.splitlines() if r.startswith("| ") and "---" not in r][1:]
        self.assertGreaterEqual(len(rows), 9)
        for row in rows:
            with self.subTest(row=row[:60]):
                self.assertRegex(row, r"`tests/test_[a-z_]+\.py`\s*\|$")

    def test_the_no_deprecation_claim_matches_the_changelog(self):
        changelog = CHANGELOG.read_text(encoding="utf-8")
        unreleased = changelog.split("\n## [", 2)[1] if "\n## [" in changelog else changelog
        deprecated = re.search(r"^### Deprecated\s*$", unreleased, re.MULTILINE)
        claims_none = "No deprecation is currently in force" in self.text
        self.assertEqual(
            claims_none,
            deprecated is None,
            "the guide's deprecation statement and the CHANGELOG disagree",
        )

    def test_it_is_reachable_from_the_docs_index(self):
        index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        self.assertIn("API_V1_BETA_MIGRATION_GUIDE.md", index)


if __name__ == "__main__":
    unittest.main()
