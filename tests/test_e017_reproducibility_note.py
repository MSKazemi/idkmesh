"""E017's public reproduction note must remain bound to retained evidence."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs" / "research" / "E017_VERIFIER_PANEL_REPRODUCIBILITY.md"
RECORD = ROOT / "experiments" / "E017-item-difficulty-and-quorum.md"
VOTES = ROOT / "experiments" / "results" / "E017-partial-oracle-votes.jsonl.gz"
EXPECTED_BLOB = "0b710ba6d376da6a688edcc0cab9bf6fb98e322a"


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


class E017ReproducibilityNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.record = RECORD.read_text(encoding="utf-8")

    def test_retained_vote_artifact_identity_is_exact(self) -> None:
        self.assertEqual(EXPECTED_BLOB, git_blob_sha(VOTES))
        self.assertIn(EXPECTED_BLOB, self.note)
        self.assertEqual(8535, VOTES.stat().st_size)

    def test_headline_metrics_are_retained_in_canonical_record(self) -> None:
        record_facts = (
            "mean accuracy p = 0.7956",
            "mean rho=+0.5873",
            "real 25-verifier majority error : 0.2083",
            "single verifier                 : 0.2044",
            "measured effective size         : 1.00   (of 25 nominal)",
            "need>=24             0.0556",
        )
        for fact in record_facts:
            with self.subTest(fact=fact):
                self.assertIn(fact, self.record)

        note_facts = (
            "| Mean verifier accuracy | 0.7956 |",
            "| Mean all-pairs error correlation | 0.5873 |",
            "| Majority-vote panel error | 0.2083 |",
            "| Single-average-verifier error | 0.2044 |",
            "| Measured effective panel size | **1.00 of 25** |",
            "| 24-of-25 acceptance error | 0.0556 |",
        )
        for fact in note_facts:
            with self.subTest(fact=fact):
                self.assertIn(fact, self.note)

    def test_note_preserves_programmatic_panel_scope(self) -> None:
        self.assertIn(
            "E017 should not be cited as evidence that 25 LLM judges equal one judge",
            self.note,
        )
        self.assertIn(
            "The measured verifiers are **programs**, not people or LLMs",
            self.note,
        )
        self.assertIn("72 candidates from 24 independent problems", self.note)
        self.assertIn("Failed reproduction is useful evidence", self.note)

    def test_public_discovery_surfaces_link_the_note(self) -> None:
        url = (
            "https://mskazemi.com/idkmesh/research/"
            "E017_VERIFIER_PANEL_REPRODUCIBILITY.html"
        )
        for path in (
            ROOT / "docs" / "topics" / "verifier-panels.md",
            ROOT / "docs" / "research.html",
            ROOT / "docs" / "llms.txt",
            ROOT / "docs" / "sitemap.xml",
        ):
            with self.subTest(path=path):
                self.assertIn(url, path.read_text(encoding="utf-8"))

    def test_reproduction_commands_pin_five_seeds_and_six_draws(self) -> None:
        self.assertIn("python sim/e017_verify.py \\", self.note)
        self.assertIn("--seeds 5 \\", self.note)
        self.assertIn("--draws 6 \\", self.note)
        self.assertIn("--trials 200000", self.note)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
