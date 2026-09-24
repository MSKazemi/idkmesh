"""The public 100-question map must stay generated from the real answer headings."""

from __future__ import annotations

import unittest

from tools import build_question_index as question_index


class QuestionIndexTests(unittest.TestCase):
    def test_committed_question_map_matches_generator(self) -> None:
        expected = question_index.render()
        actual = question_index.OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(expected, actual)

    def test_exactly_one_hundred_unique_questions_are_indexed(self) -> None:
        entries = question_index.question_entries()
        questions = [
            question
            for entry in entries
            for question in entry["questions"]
        ]
        self.assertEqual(10, len(entries))
        self.assertEqual(100, len(questions))
        self.assertEqual(100, len(set(questions)))

    def test_every_question_points_to_its_substantial_topic_guide(self) -> None:
        rendered = question_index.render()
        for entry in question_index.question_entries():
            url = entry["url"]
            questions = entry["questions"]
            self.assertEqual(10, len(questions))
            for question in questions:
                with self.subTest(question=question):
                    self.assertIn(f"[{question}]({url})", rendered)

    def test_question_map_is_linked_from_discovery_surfaces(self) -> None:
        root = question_index.ROOT
        expected_url = "https://mskazemi.com/idkmesh/questions.html"
        self.assertIn(
            expected_url,
            (root / "docs" / "topics" / "index.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            expected_url,
            (root / "docs" / "llms.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            expected_url,
            (root / "docs" / "sitemap.xml").read_text(encoding="utf-8"),
        )

    def test_repository_readme_links_question_map(self) -> None:
        expected_url = "https://mskazemi.com/idkmesh/questions.html"
        self.assertIn(
            expected_url,
            (question_index.ROOT / "README.md").read_text(encoding="utf-8"),
        )

    def test_index_does_not_duplicate_answers_or_create_doorway_pages(self) -> None:
        rendered = question_index.render()
        self.assertIn(
            "question map**, not a collection of thin duplicate answers",
            rendered,
        )
        self.assertIn(
            "The ten topic pages remain the answer sources",
            rendered,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
