"""Tests for tools/schema_migration_note_check.py (issue #737's migration notes).

ADR-0020 enforces the version-bump half of "breaking changes require explicit
version bump/migration note" -- a breaking change can only ship as a new,
separately versioned file. This module pins the other half: every version
successor must land with an explicit migration note in the ``Schema
migrations`` section of ``schemas/README.md`` naming the exact file it
supersedes.

The real tree is checked against the real ledger, so the repository's own
five successors double as evidence the rule fits actual history. The failure
modes are pinned against synthetic temporary fixtures (a small schemas/ dir
plus a ledger string), the same shape ``tests/test_schema_compat_check.py``
uses for its rule set.

Deliberately stdlib-only and class-based: the PR Gate runs the tool before
``pip install``, and module-level ``def test_*`` functions here would change
the documented figures ``tests/test_documented_test_counts.py`` guards.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import schema_migration_note_check as mn


def ledger_for(*entries: str) -> str:
    """A README body whose Schema migrations section holds the given lines."""
    body = "\n".join(entries)
    return (
        "# Schemas\n\n## Schema migrations\n\n"
        f"{body}\n\n## Compatibility notes\n\nprose that must not be parsed\n"
    )


def entry(new: str, old: str, note: str = "migrates by rewriting the fields") -> str:
    return f"- `{new}` supersedes `{old}`: {note}"


class RealTreeTests(unittest.TestCase):
    """The repository's own successors all carry their migration note."""

    def test_every_real_successor_has_its_note(self) -> None:
        self.assertEqual(
            [],
            mn.check(
                ROOT / "schemas",
                (ROOT / "schemas" / "README.md").read_text(encoding="utf-8"),
            ),
            "schemas/README.md is missing or misstates a migration note; run "
            "python tools/schema_migration_note_check.py for the details",
        )

    def test_the_real_tree_actually_has_successors_to_guard(self) -> None:
        found = mn.successors(ROOT / "schemas")
        self.assertGreaterEqual(
            len(found),
            3,
            "almost no version successors were found; this guard is checking nothing",
        )
        self.assertEqual("work-unit-v0.1.schema.json", found["work-unit-v0.2.schema.json"])

    def test_the_note_shape_parses_the_real_ledger(self) -> None:
        entries = mn.parse_ledger(
            (ROOT / "schemas" / "README.md").read_text(encoding="utf-8")
        )
        self.assertIsNotNone(entries)
        self.assertGreaterEqual(len(entries), 3)
        for item in entries:
            with self.subTest(successor=item["new"]):
                self.assertTrue(item["note"].strip())


class SyntheticLedgerTests(unittest.TestCase):
    """Failure modes, pinned against a temporary schemas/ tree."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.schemas = Path(temporary.name) / "schemas"
        self.schemas.mkdir()
        for name in (
            "widget-v0.1.schema.json",
            "widget-v0.2.schema.json",
            "widget-v0.10.schema.json",
            "gadget-v0.1.schema.json",
            "legacy-open.schema.json",
            "routing-replay-v0.schema.json",
        ):
            (self.schemas / name).write_text("{}", encoding="utf-8")

    def check(self, ledger: str) -> list[str]:
        return mn.check(self.schemas, ledger)

    def test_successors_are_the_versions_above_the_lowest(self) -> None:
        self.assertEqual(
            {
                "widget-v0.2.schema.json": "widget-v0.1.schema.json",
                "widget-v0.10.schema.json": "widget-v0.2.schema.json",
            },
            mn.successors(self.schemas),
            "version order must be numeric: v0.10 is the successor of v0.2",
        )

    def test_unversioned_and_v0_style_names_have_no_successor(self) -> None:
        for name in ("legacy-open.schema.json", "routing-replay-v0.schema.json"):
            with self.subTest(name=name):
                self.assertNotIn(name, mn.successors(self.schemas))

    def test_complete_ledger_passes(self) -> None:
        ledger = ledger_for(
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.10.schema.json", "widget-v0.2.schema.json"),
        )
        self.assertEqual([], self.check(ledger))

    def test_missing_note_is_flagged(self) -> None:
        violations = self.check(ledger_for(entry("widget-v0.2.schema.json", "widget-v0.1.schema.json")))
        self.assertEqual(1, len(violations))
        self.assertIn("widget-v0.10.schema.json", violations[0])
        self.assertIn("no migration note", violations[0])

    def test_wrong_predecessor_is_flagged(self) -> None:
        ledger = ledger_for(
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.10.schema.json", "widget-v0.1.schema.json"),
        )
        violations = self.check(ledger)
        self.assertEqual(1, len(violations))
        self.assertIn("supersedes widget-v0.1.schema.json", violations[0])
        self.assertIn("immediate predecessor is widget-v0.2.schema.json", violations[0])

    def test_entry_for_a_first_version_is_flagged(self) -> None:
        ledger = ledger_for(
            entry("gadget-v0.1.schema.json", "gadget-v0.0.schema.json"),
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.10.schema.json", "widget-v0.2.schema.json"),
        )
        violations = self.check(ledger)
        self.assertEqual(1, len(violations))
        self.assertIn("gadget-v0.1.schema.json", violations[0])
        self.assertIn("not a version successor", violations[0])

    def test_entry_for_a_missing_file_is_flagged(self) -> None:
        ledger = ledger_for(
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.10.schema.json", "widget-v0.2.schema.json"),
            entry("ghost-v0.2.schema.json", "ghost-v0.1.schema.json"),
        )
        violations = self.check(ledger)
        self.assertEqual(1, len(violations))
        self.assertIn("ghost-v0.2.schema.json", violations[0])
        self.assertIn("does not exist", violations[0])

    def test_duplicate_entries_are_flagged(self) -> None:
        ledger = ledger_for(
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json"),
            entry("widget-v0.10.schema.json", "widget-v0.2.schema.json"),
        )
        violations = self.check(ledger)
        self.assertEqual(1, len(violations))
        self.assertIn("more than one ledger entry", violations[0])

    def test_hollow_note_is_flagged(self) -> None:
        ledger = ledger_for(
            entry("widget-v0.2.schema.json", "widget-v0.1.schema.json", note="todo"),
            entry("widget-v0.10.schema.json", "widget-v0.2.schema.json"),
        )
        violations = self.check(ledger)
        self.assertEqual(1, len(violations))
        self.assertIn("too short", violations[0])

    def test_missing_section_is_flagged(self) -> None:
        violations = self.check("# Schemas\n\n## Compatibility notes\n\nno ledger\n")
        self.assertEqual(1, len(violations))
        self.assertIn("Schema migrations", violations[0])

    def test_prose_outside_the_section_is_not_an_entry(self) -> None:
        text = (
            "## Schema migrations\n\n"
            "- `widget-v0.2.schema.json` supersedes `widget-v0.1.schema.json`: "
            "migrates by rewriting the fields\n\n"
            "## Compatibility notes\n\n"
            "- `widget-v0.10.schema.json` supersedes `widget-v0.2.schema.json`: "
            "migrates by rewriting the fields\n"
        )
        violations = self.check(text)
        self.assertEqual(1, len(violations))
        self.assertIn("widget-v0.10.schema.json", violations[0])


if __name__ == "__main__":
    unittest.main()
