from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = ROOT / "docs" / "conversations"
INDEX = CONVERSATIONS / "README.md"


class ConversationIndexTests(unittest.TestCase):
    def test_every_conversation_record_is_indexed_once(self) -> None:
        records = {
            path.name
            for path in CONVERSATIONS.glob("*.md")
            if path.name != INDEX.name
        }
        text = INDEX.read_text(encoding="utf-8")
        linked_records = re.findall(r"\]\(([^/#?()]+\.md)(?:#[^()]*)?\)", text)

        self.assertEqual(set(linked_records), records)
        self.assertEqual(len(linked_records), len(records))

    def test_declared_record_count_matches_the_archive(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        match = re.search(r"^(\d+) records across \d+ dates", text, re.MULTILINE)

        self.assertIsNotNone(match)
        record_count = sum(
            path.name != INDEX.name for path in CONVERSATIONS.glob("*.md")
        )
        self.assertEqual(int(match.group(1)), record_count)


if __name__ == "__main__":
    unittest.main()
