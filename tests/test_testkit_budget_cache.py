"""Guard the tier cache against caching a budget failure as a pass.

`scripts/testkit.py` fails a tier for two independent reasons: the tests were
red, or the run exceeded the tier's CPU budget. The exit code accounted for
both, but the result cache recorded only whether pytest was green. A green
run that blew its budget was therefore written as `"ok": true`, and the next
invocation took the cache short-circuit and exited 0.

That made the budget a one-shot gate: it fired once, then reported
"cached pass" for as long as the tree was unchanged — which is precisely when a
developer re-runs it. Observed on this branch: the unit tier used 192.45 CPU-seconds
against a 90-second ceiling, exited 1, and the very next `make test` printed
"cached pass" and exited 0. (That 192.45 was itself inflated by unrelated load on
the machine -- the same tier measures ~62 CPU-seconds idle -- which is precisely
why a spurious trip must not then be cached as a pass.)

The exit code, the cached verdict and the printed status word now all derive
from `tier_passed`. The third was found later, reporting PASS on a run that
exited 1; `PrintedStatusMatchesTheExitCodeTests` below covers it.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
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


class PrintedStatusMatchesTheExitCodeTests(unittest.TestCase):
    """The summary line must not say PASS on a run that exits 1.

    The cache fix above gave `tier_passed` two callers, the exit code and the
    cached verdict. The status word printed on the summary line stayed on
    `result.ok` and so kept its own opinion:

        [testkit] unit: PASS in 100.0s wall / 100.0s cpu (budget 90 cpu-s)

    followed by exit 1. The BUDGET EXCEEDED explanation goes to stderr, which is
    not necessarily displayed beside stdout -- a hook capturing the streams
    separately, a CI log pane, or `--quiet` -- so the only line a human is
    guaranteed to read was the one that was wrong.

    These tests assert on the rendered output rather than on `tier_passed`,
    because the existing tests call `main()` with `--quiet` and a correct
    verdict function is exactly what the bug already had.
    """

    def setUp(self) -> None:
        self.testkit = load_testkit()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.testkit.CACHE = Path(self.tmp.name) / "testkit-cache.json"
        self.testkit.tree_fingerprint = lambda: "fixed-fingerprint"
        self._argv = sys.argv
        self.addCleanup(lambda: setattr(sys, "argv", self._argv))

    def run_unit(self, cpu: float, ok: bool = True) -> tuple[int, str]:
        self.testkit.TIERS["unit"] = lambda: self.testkit.Result(
            ok, cpu, cpu, "stub tier"
        )
        sys.argv = ["testkit.py", "unit", "--quiet", "--no-cache"]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = self.testkit.main()
        return code, stdout.getvalue()

    def test_over_budget_prints_fail(self) -> None:
        budget = self.testkit.BUDGETS["unit"]
        code, output = self.run_unit(cpu=budget * 2)

        self.assertEqual(code, 1, "precondition: an over-budget tier exits 1")
        self.assertIn(
            "unit: FAIL",
            output,
            f"the tier exited {code} but its summary line reads: {output.strip()!r}",
        )
        self.assertNotIn("unit: PASS", output)

    def test_inside_budget_still_prints_pass(self) -> None:
        code, output = self.run_unit(cpu=1.0)

        self.assertEqual(code, 0)
        self.assertIn("unit: PASS", output)

    def test_red_tests_print_fail(self) -> None:
        code, output = self.run_unit(cpu=1.0, ok=False)

        self.assertEqual(code, 1)
        self.assertIn("unit: FAIL", output)

    def test_the_status_word_agrees_with_the_exit_code_in_every_case(self) -> None:
        budget = self.testkit.BUDGETS["unit"]
        cases = [
            (True, 1.0),
            (True, budget * 2),
            (False, 1.0),
            (False, budget * 2),
        ]
        for ok, cpu in cases:
            with self.subTest(tests_green=ok, cpu=cpu):
                code, output = self.run_unit(cpu=cpu, ok=ok)
                printed_pass = "unit: PASS" in output
                self.assertEqual(
                    printed_pass,
                    code == 0,
                    f"exit code {code} disagrees with the printed status: "
                    f"{output.strip()!r}",
                )


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
