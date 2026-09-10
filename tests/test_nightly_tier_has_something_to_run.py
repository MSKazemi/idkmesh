from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
TIER_MARKERS = {"sim", "slow"}


def modules_carrying_a_tier_marker() -> dict[str, set[str]]:
    """Modules assigning ``pytestmark = pytest.mark.<sim|slow>``.

    Read with ``ast`` rather than by substring, so a marker named only in a
    comment or a docstring cannot be mistaken for one that is applied.
    """
    found: dict[str, set[str]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken file fails elsewhere
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
            ):
                continue
            for attribute in ast.walk(node.value):
                if (
                    isinstance(attribute, ast.Attribute)
                    and attribute.attr in TIER_MARKERS
                    and isinstance(attribute.value, ast.Attribute)
                    and attribute.value.attr == "mark"
                ):
                    found.setdefault(path.name, set()).add(attribute.attr)
    return found


class NightlyTierHasSomethingToRunTests(unittest.TestCase):
    """`scripts/testkit.py` treats "no tests matched" as a passing nightly tier.

        sim_ok = code in (0, 5)  # 5 == no tests matched the marker

    Tolerating exit 5 is reasonable for a repository with no simulation tests.
    This one has 369 selected by `-m "sim or slow"`, so zero would mean the tier
    markers had been removed or renamed -- and `nightly` would report success
    having run none of them.

    Scope, stated because it is narrower than it first looks: each marked module
    applies its marker under `if importlib.util.find_spec("pytest") is not None`,
    and that is always true when pytest is the thing running, so the conditional
    does NOT put the markers at risk. What this guards is a future edit deleting
    or renaming them.
    """

    def test_some_module_still_carries_a_tier_marker(self) -> None:
        carriers = modules_carrying_a_tier_marker()

        self.assertTrue(
            carriers,
            "no test module assigns pytestmark = pytest.mark.sim or .slow, so "
            "`testkit.py nightly` would select zero tests, exit 5, and report a "
            "pass having run nothing. If the tier markers were retired on "
            "purpose, delete this test in the same change.",
        )

    def test_both_tier_markers_are_still_in_use(self) -> None:
        in_use = set().union(*modules_carrying_a_tier_marker().values())

        self.assertEqual(
            TIER_MARKERS - in_use,
            set(),
            f"these tier markers are declared in pytest.ini but applied nowhere: "
            f"{sorted(TIER_MARKERS - in_use)}; the unit tier excludes them, so "
            f"nothing excludes anything and the split is decorative",
        )


if __name__ == "__main__":
    unittest.main()
