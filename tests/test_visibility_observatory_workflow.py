"""The visibility observatory must self-check when its measurement contract changes."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "visibility-observatory.yml"


class VisibilityObservatoryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_weekly_manual_and_contract_change_triggers_are_present(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn('cron: "11 6 * * 1"', self.text)
        self.assertIn("\n  push:\n", self.text)
        self.assertIn("\n      - main\n", self.text)

    def test_push_trigger_is_path_bounded_to_measurement_contract(self) -> None:
        required = (
            ".github/workflows/visibility-observatory.yml",
            "config/seo-topics-v1.json",
            "config/discovery-query-portfolio-v0.1.json",
            "config/visibility-growth-policy-v0.1.json",
            "scripts/discovery_query_portfolio.py",
            "scripts/search_console_snapshot.py",
            "scripts/visibility_growth_selector.py",
            "scripts/visibility_observatory.py",
        )
        for path in required:
            with self.subTest(path=path):
                self.assertIn(f'- "{path}"', self.text)

        self.assertNotIn('docs/topics/**', self.text)
        self.assertNotIn('docs/questions.md', self.text)

    def test_observatory_preserves_every_measurement_run(self) -> None:
        self.assertIn("cancel-in-progress: false", self.text)

    def test_search_console_remains_optional_and_read_only(self) -> None:
        self.assertIn("Detect Search Console configuration", self.text)
        self.assertIn("steps.gsc.outputs.configured == 'true'", self.text)
        self.assertIn("contents: read", self.text)
        self.assertNotIn("contents: write", self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
