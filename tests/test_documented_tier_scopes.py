"""Keep the tier scopes in ``docs/TESTING.md`` equal to the ones actually run.

``docs/TESTING.md`` publishes a table of test tiers, and the ``Scope`` column
names the pytest marker expression each tier selects with. That column is the
only place a contributor can read what ``make test`` will and will not run, so a
wrong entry does not merely misinform -- it tells someone their pre-commit gate
covers tests it silently skips.

It was wrong on arrival. The table shipped in #435 saying the unit tier ran
``-m "not sim"`` while ``scripts/testkit.py`` in the same pull request ran
``-m "not sim and not slow"``, and the prose below it said no test carried
``@pytest.mark.sim`` while the baseline table three sections earlier already
recorded 369 deselected tests. Nothing failed, because nothing compared the two.

So the marker expressions are no longer trusted to be retyped correctly: they
are read out of ``scripts/testkit.py`` with ``ast`` and compared against the
document. The comparison is deliberately asymmetric.

* **Every expression a tier runs must appear in the document.** A tier whose
  real scope is unstated is the failure above.
* **Every expression the tier *table* publishes must be one a tier runs.** The
  table is the authoritative scope statement, so a stale entry there is a lie.
  Prose elsewhere in the document is free to show other ``-m`` examples for
  teaching; only the table is pinned.

Absolute test counts are deliberately not pinned here. ``tests/*.py`` changes in
roughly a third of commits, so a pinned total would force an unrelated Markdown
edit into most of them -- the rot that
``tests/test_documented_test_counts.py`` documents at length. Marker
expressions change when someone changes a tier boundary on purpose, which is
exactly when this file should demand the document be updated too.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTKIT = ROOT / "scripts" / "testkit.py"
DOCUMENT = ROOT / "docs" / "TESTING.md"

# The tier functions whose pytest invocation defines a published scope. `smoke`
# selects explicit test paths rather than a marker expression, and
# `integration` delegates to `tier_unit`, so neither names one of its own.
TIER_FUNCTIONS = ("tier_unit", "tier_nightly")

# `-m "<expression>"` as it is written in the document, inside backticks or not.
_DOCUMENTED_EXPRESSION = re.compile(r'-m\s+"([^"]+)"')

# The tier table, found by its header rather than by position.
_TABLE_HEADER = "| Tier | Scope | Budget | Runs |"

# "`nightly` is equivalent to `integration`", in the affirmative. The optional
# group is what distinguishes the true statement from the false one.
_EQUIVALENCE_CLAIM = re.compile(
    r"`?nightly`?\s+is\s+(not\s+)?equivalent\s+to\s+`?integration`?", re.I
)


def marker_expressions_run_by_the_tiers() -> dict[str, str]:
    """Map each tier function to the marker expression it passes to pytest.

    Read with ``ast`` rather than by substring so that a marker expression
    named in a docstring or a comment inside ``testkit.py`` -- the file is
    heavily commented -- cannot be mistaken for one that is executed.
    """
    tree = ast.parse(TESTKIT.read_text(encoding="utf-8"))
    found: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in TIER_FUNCTIONS:
            continue
        for element in ast.walk(node):
            if not isinstance(element, ast.List):
                continue
            items = [
                item.value if isinstance(item, ast.Constant) else None
                for item in element.elts
            ]
            # Every one of these commands carries `-m` twice: once as
            # Python's own "run this module" flag (`python -m pytest`) and
            # once as pytest's marker filter. Taking the first match would
            # read the expression as "pytest", which no document would ever
            # publish -- a green test that compares nothing.
            for index, item in enumerate(items[:-1]):
                if item == "-m" and items[index + 1] != "pytest":
                    expression = items[index + 1]
                    if isinstance(expression, str):
                        found[node.name] = expression
    return found


def expressions_in_the_tier_table() -> set[str]:
    """Marker expressions published in the ``Scope`` column of the tier table."""
    lines = DOCUMENT.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(_TABLE_HEADER)
    except ValueError:  # pragma: no cover - asserted directly below
        return set()

    expressions: set[str] = set()
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        expressions.update(_DOCUMENTED_EXPRESSION.findall(line))
    return expressions


class DocumentedTierScopeTests(unittest.TestCase):
    def test_the_tier_functions_still_select_with_marker_expressions(self) -> None:
        """Guard the premise of every other test here.

        If `testkit.py` stopped passing `-m` altogether -- selecting by path, or
        by a config default -- the comparisons below would pass by comparing two
        empty sets, and the document could say anything at all.
        """
        expressions = marker_expressions_run_by_the_tiers()

        self.assertEqual(
            sorted(expressions),
            sorted(TIER_FUNCTIONS),
            f"expected every tier in {list(TIER_FUNCTIONS)} to select with a "
            f"`-m` expression in {TESTKIT.name}; found {expressions}. If a tier "
            f"deliberately stopped using markers, update TIER_FUNCTIONS and the "
            f"scope column of the table in docs/TESTING.md in the same change.",
        )

    def test_the_document_contains_the_tier_table(self) -> None:
        self.assertIn(
            _TABLE_HEADER,
            DOCUMENT.read_text(encoding="utf-8"),
            f"the tier table header is gone from {DOCUMENT.name}, so the scope "
            f"column this file pins cannot be located; if the table was "
            f"restructured, update _TABLE_HEADER here.",
        )

    def test_every_scope_a_tier_runs_is_published(self) -> None:
        document = DOCUMENT.read_text(encoding="utf-8")
        published = set(_DOCUMENTED_EXPRESSION.findall(document))

        for tier, expression in sorted(marker_expressions_run_by_the_tiers().items()):
            self.assertIn(
                expression,
                published,
                f'{tier} runs pytest with -m "{expression}", which appears '
                f"nowhere in docs/TESTING.md. A contributor reading that "
                f"document cannot tell which tests their gate skips.",
            )

    def test_the_table_publishes_no_scope_that_no_tier_runs(self) -> None:
        actually_run = set(marker_expressions_run_by_the_tiers().values())
        stale = expressions_in_the_tier_table() - actually_run

        self.assertEqual(
            stale,
            set(),
            f"the tier table in docs/TESTING.md publishes marker "
            f"expression(s) {sorted(stale)} that no tier in {TESTKIT.name} "
            f"runs; the tiers actually select with {sorted(actually_run)}. "
            f"This is the exact drift that shipped the unit tier as "
            f'-m "not sim" when it had always been -m "not sim and not slow".',
        )

    def test_the_document_does_not_claim_nightly_equals_integration(self) -> None:
        """The two tiers differ, and the difference is the whole point.

        Premise, stated because it lives in another file: this holds only while
        some test still carries `sim` or `slow`, which
        `tests/test_nightly_tier_has_something_to_run.py` asserts directly. If
        the tier markers are ever retired on purpose, that test says to delete
        it in the same change -- and this one goes with it.
        """
        for match in _EQUIVALENCE_CLAIM.finditer(DOCUMENT.read_text(encoding="utf-8")):
            self.assertIsNotNone(
                match.group(1),
                f"docs/TESTING.md claims {match.group(0)!r}. It is not: the "
                f"nightly tier additionally runs everything marked `sim` or "
                f"`slow`, which the unit and integration tiers both deselect.",
            )


if __name__ == "__main__":
    unittest.main()
