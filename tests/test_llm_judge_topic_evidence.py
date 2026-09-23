"""The public LLM-judge pillar must preserve E016's negative-result scope."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "topics" / "llm-judge-reliability.md"
E016 = ROOT / "experiments" / "E016-live-verifier-correlation.md"


class LLMJudgeTopicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = PAGE.read_text(encoding="utf-8")
        cls.e016 = E016.read_text(encoding="utf-8")

    def test_public_numbers_are_retained_in_e016(self) -> None:
        for fact in (
            "mean accuracy p = 0.4743",
            "mean Youden J   = +0.0487",
            "0 / 20",
            "20-agent majority vote  accuracy : 0.514",
            'trivial "always reject" accuracy : 0.639',
            "101 of 1440 votes (7.0%) were unparseable",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, self.e016)

        for fact in (
            "| Mean accuracy | 0.4743 |",
            "| Mean Youden J | +0.0487 |",
            "| Judges significantly above J=0 after correction | **0 of 20** |",
            "| 20-judge majority-vote accuracy | 0.514 |",
            "| Trivial always-reject accuracy | **0.639** |",
            "| Unparseable votes | 7.0% |",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, self.page)

    def test_page_blocks_false_independence_interpretation(self) -> None:
        self.assertIn(
            "was **not evidence of independence**",
            self.page,
        )
        self.assertIn(
            "evaluator competence must be measured before agreement, correlation, "
            "or panel size can be interpreted",
            self.page,
        )

    def test_page_does_not_generalize_small_models_to_all_llm_judges(self) -> None:
        self.assertIn("small 1–2B open models", self.page)
        self.assertIn(
            "does **not** establish that larger current models, commercial models, "
            "or LLM judges in other domains are unreliable",
            self.page,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
