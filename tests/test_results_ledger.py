"""Structural guard for ``docs/research/RESULTS_LEDGER.md``.

The ledger states every experiment record in one sentence with an evidence
class and a verdict. Its value is that no indexed record is missing, none is
listed twice, and no row can claim an evidence class or verdict outside the
published vocabulary (in particular, nothing can quietly relabel a synthetic
record as ``real-run`` by inventing a new word for it).

This test checks structure only. It cannot check that a headline is faithful to
its record; that remains a human review. It reads two files once each and starts
no subprocess, to stay cheap in the unit tier.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "research" / "RESULTS_LEDGER.md"
EXPERIMENTS_INDEX = ROOT / "experiments" / "README.md"

EVIDENCE_CLASSES = {"synthetic", "public-observed", "real-run", "analytic"}
VERDICTS = {
    "supported",
    "falsified",
    "partially falsified",
    "inconclusive",
    "negative result",
    "see record",
}

RECORD_BASE = "https://github.com/MSKazemi/idkmesh/blob/main/experiments/"

# A record is a Markdown file directly inside experiments/ that the index links
# by bare file name. Links into experiments/results/ contain a slash and are
# result documents of a record, not records.
INDEX_LINK = re.compile(r"\]\(([^)/#\s]+\.md)\)")
ROW = re.compile(
    r"^\| (?P<id>[^|]+?) \| `(?P<cls>[^`]+)` \| (?P<headline>[^|]+?) \| "
    r"`(?P<verdict>[^`]+)` \| \[[^\]]+\]\((?P<url>[^)]+)\) \|$"
)


def _indexed_records() -> set[str]:
    text = EXPERIMENTS_INDEX.read_text(encoding="utf-8")
    return {name for name in INDEX_LINK.findall(text) if name != "README.md"}


def _ledger_rows() -> list[dict[str, str]]:
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            rows.append(match.groupdict())
    return rows


class ResultsLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.indexed = _indexed_records()
        cls.rows = _ledger_rows()
        cls.filenames = [
            row["url"][len(RECORD_BASE):]
            for row in cls.rows
            if row["url"].startswith(RECORD_BASE)
        ]

    def test_index_and_ledger_are_non_trivial(self) -> None:
        # Guards the guard: a broken regex that matches nothing would make every
        # other assertion vacuously true.
        self.assertGreaterEqual(len(self.indexed), 40)
        self.assertEqual(len(self.rows), len(self.filenames))

    def test_every_indexed_record_has_exactly_one_row(self) -> None:
        counts = {name: self.filenames.count(name) for name in self.indexed}
        missing = sorted(name for name, n in counts.items() if n == 0)
        duplicated = sorted(name for name, n in counts.items() if n > 1)
        self.assertEqual(missing, [], f"indexed records without a ledger row: {missing}")
        self.assertEqual(duplicated, [], f"records with more than one row: {duplicated}")

    def test_no_row_names_an_unindexed_record(self) -> None:
        ghosts = sorted(set(self.filenames) - self.indexed)
        self.assertEqual(ghosts, [], f"ledger rows for unindexed records: {ghosts}")

    def test_every_row_url_is_a_record_url(self) -> None:
        foreign = [row["url"] for row in self.rows if not row["url"].startswith(RECORD_BASE)]
        self.assertEqual(foreign, [])

    def test_evidence_class_and_verdict_use_the_published_vocabulary(self) -> None:
        bad_class = [(r["id"], r["cls"]) for r in self.rows if r["cls"] not in EVIDENCE_CLASSES]
        bad_verdict = [(r["id"], r["verdict"]) for r in self.rows if r["verdict"] not in VERDICTS]
        self.assertEqual(bad_class, [])
        self.assertEqual(bad_verdict, [])

    def test_row_ids_are_unique_and_match_their_record(self) -> None:
        ids = [row["id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate record ids in the ledger")
        mismatched = [
            (row["id"], name)
            for row, name in zip(self.rows, self.filenames)
            if not name.startswith(row["id"].split()[0] + "-")
        ]
        self.assertEqual(mismatched, [])

    def test_known_classifications_are_not_relabelled(self) -> None:
        # E045-E047 analyse third-party SWE-bench results (we ran no agent), and
        # E029 is the one real model-attempt record and a negative one. Pinning
        # them stops an edit from presenting either as something stronger.
        by_id = {row["id"]: row for row in self.rows}
        for record in ("E045", "E046", "E047"):
            self.assertEqual(by_id[record]["cls"], "public-observed", record)
        self.assertEqual(by_id["E029"]["cls"], "real-run")
        self.assertEqual(by_id["E029"]["verdict"], "negative result")


if __name__ == "__main__":
    unittest.main()
