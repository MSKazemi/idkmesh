"""Guard the tier cache against caching a budget failure as a pass.

`scripts/testkit.py` fails a tier for two independent reasons: the tests were
red, or the run exceeded the tier's CPU budget. The exit code accounted for
both, but the result cache recorded only whether pytest was green. A green
run that blew its budget was therefore written as `"ok": true`, and the next
invocation took the cache short-circuit and exited 0.

That made the budget a one-shot gate: it fired once, then reported
"cached pass" for as long as the tree was unchanged — which is precisely when a
developer re-runs it. Observed on `main`: the unit tier used 192.45 CPU-seconds
against a 90-second ceiling, exited 1, and the very next `make test` printed
"cached pass" and exited 0.

Both the exit code and the cached verdict now derive from `tier_passed`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTKIT = ROOT / "scripts" / "testkit.py"


def load_testkit():
    """Import testkit by path; `scripts/` is not an importable package."""
    name = "testkit_under_test"
    spec = importlib.util.spec_from_file_location(name, TESTKIT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # `@dataclass` resolves its annotations through sys.modules[__module__],
    # so the module has to be registered before it is executed.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


class TierPassedTests(unittest.TestCase):
    """The single source of truth for 'did this tier pass'."""

    def setUp(self) -> None:
        self.testkit = load_testkit()

    def test_green_and_inside_budget_passes(self) -> None:
        self.assertTrue(self.testkit.tier_passed(True, 10.0, 90.0))

    def test_green_but_over_budget_fails(self) -> None:
        self.assertFalse(self.testkit.tier_passed(True, 192.45, 90.0))

    def test_red_inside_budget_fails(self) -> None:
        self.assertFalse(self.testkit.tier_passed(False, 10.0, 90.0))

    def test_unbudgeted_tier_only_depends_on_the_tests(self) -> None:
        self.assertTrue(self.testkit.tier_passed(True, 10_000.0, None))
        self.assertFalse(self.testkit.tier_passed(False, 0.1, None))


class BudgetFailureIsNotCachedAsPassTests(unittest.TestCase):
    """The regression: run twice, and the second run must not go green."""

    def setUp(self) -> None:
        self.testkit = load_testkit()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.testkit.CACHE = Path(self.tmp.name) / "testkit-cache.json"

        # A tier that is green but spends twice its budget.
        budget = self.testkit.BUDGETS["unit"]
        self.over = budget * 2
        self.testkit.TIERS["unit"] = lambda: self.testkit.Result(
            True, self.over, self.over, "stub: green but over budget"
        )
        # Keep the fingerprint stable so the second run takes the cache path.
        self.testkit.tree_fingerprint = lambda: "fixed-fingerprint"

        self._argv = sys.argv
        self.addCleanup(lambda: setattr(sys, "argv", self._argv))

    def run_unit(self) -> int:
        sys.argv = ["testkit.py", "unit", "--quiet"]
        return self.testkit.main()

    def test_first_run_fails_on_budget(self) -> None:
        self.assertEqual(self.run_unit(), 1)

    def test_cache_records_the_budget_failure(self) -> None:
        self.run_unit()
        entry = json.loads(self.testkit.CACHE.read_text())["unit"]
        self.assertFalse(
            entry["ok"],
            "a budget failure was cached as a pass; the next run will report "
            f"'cached pass' and exit 0 (entry: {entry})",
        )

    def test_second_run_does_not_go_green_from_the_cache(self) -> None:
        self.assertEqual(self.run_unit(), 1)
        self.assertEqual(
            self.run_unit(),
            1,
            "re-running an unchanged, over-budget tree exited 0: the cache "
            "short-circuit disarmed the budget gate",
        )

    def test_auto_tier_shares_the_short_circuit(self) -> None:
        """`make gate` resolves a tier then checks the same cache entry."""
        self.run_unit()
        self.testkit.tier_auto = lambda: ("unit", self.testkit.TIERS["unit"]())
        sys.argv = ["testkit.py", "auto", "--quiet"]
        self.assertEqual(self.testkit.main(), 1)


class FingerprintCoversEveryTrackedFileTests(unittest.TestCase):
    """The cache key must move whenever anything a test can read moves.

    `tree_fingerprint` hashed only `.py`, `.json`, `.ini` and `.cfg`. The suite
    is not only Python: guard tests read Markdown and workflow YAML, and the
    integration tier runs a Markdown link gate. So a contributor could break a
    documentation link, watch `make integration` answer `cached pass`, push, and
    only then find out CI disagreed — which is the worst possible moment, and a
    documentation fix is the most common first contribution there is.
    """

    def setUp(self) -> None:
        self.testkit = load_testkit()

    def fingerprint_moves_for(self, name: str, body: str) -> None:
        path = ROOT / name
        original = path.read_bytes() if path.exists() else None
        self.addCleanup(
            lambda: path.write_bytes(original) if original is not None else path.unlink(True)
        )
        before = self.testkit.tree_fingerprint()
        path.write_bytes((original or b"") + body.encode())
        self.assertNotEqual(
            before,
            self.testkit.tree_fingerprint(),
            f"editing {name} left the fingerprint unchanged, so the result "
            "cache will report 'cached pass' for a tree that tests read",
        )

    def test_markdown_edit_moves_the_fingerprint(self) -> None:
        self.fingerprint_moves_for("SUPPORT.md", "\n<!-- fingerprint probe -->\n")

    def test_workflow_yaml_edit_moves_the_fingerprint(self) -> None:
        self.fingerprint_moves_for(
            ".github/workflows/pr-gate.yml", "\n# fingerprint probe\n"
        )

    def test_python_edit_still_moves_the_fingerprint(self) -> None:
        self.fingerprint_moves_for("scripts/check_links.py", "\n# fingerprint probe\n")


if __name__ == "__main__":
    unittest.main()
