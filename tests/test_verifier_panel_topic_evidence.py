"""The public verifier-panel pillar must preserve E017's measured scope."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "topics" / "verifier-panels.md"
E017 = ROOT / "experiments" / "E017-item-difficulty-and-quorum.md"


class VerifierPanelTopicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = PAGE.read_text(encoding="utf-8")
        cls.e017 = E017.read_text(encoding="utf-8")

    def test_public_numbers_are_retained_in_the_experiment(self) -> None:
        experiment_facts = (
            "mean accuracy p = 0.7956",
            "mean rho=+0.5873",
            "measured effective size         : 1.00   (of 25 nominal)",
            "real 25-verifier majority error : 0.2083",
            "0.2083 -> 0.0556",
        )
        for fact in experiment_facts:
            with self.subTest(fact=fact):
                self.assertIn(fact, self.e017)

        for public_fact in (
            "| Mean verifier accuracy | 0.7956 |",
            "| Mean pairwise error correlation | 0.5873 |",
            "| Majority-vote panel error | 0.2083 |",
            "| Measured effective panel size | **1.00 of 25** |",
            "| Error with a 24-of-25 acceptance quorum | 0.0556 |",
        ):
            with self.subTest(public_fact=public_fact):
                self.assertIn(public_fact, self.page)

    def test_page_does_not_relabel_the_programmatic_panel_as_llm_evidence(self) -> None:
        self.assertIn("These verifiers were programs, not people or LLM judges", self.page)
        self.assertIn(
            "does **not** claim that a 25-LLM panel is worth one vote",
            self.page,
        )
        self.assertIn("E016-live-verifier-correlation.md", self.page)

    def test_llm_reliability_cross_link_is_not_duplicated(self) -> None:
        link = "https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html"
        self.assertEqual(1, self.page.count(link))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
