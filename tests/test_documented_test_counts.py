"""Guard the under-collection claim that AGENTS.md and CONTRIBUTING.md publish.

Both files warn a contributor away from ``python -m unittest discover``. The
warning rests on a factual claim: ``unittest`` finds only ``TestCase``
subclasses, so the module-level ``def test_*`` functions in ``tests/`` are
invisible to it, and they are worth roughly a tenth of the suite.

Earlier revisions backed that claim with two absolute totals -- how many tests
each runner collects. Those rot: 29% of commits on this branch touch
``tests/*.py``, so the totals were wrong twice, and at one point three
different pairs were published across the tree at the same time. Pinning them
exactly would also force an unrelated Markdown edit into three commits in ten.

So the documents now publish only the two figures the claim actually needs --
how many module-level functions there are and how many files hold them -- and
this module guards those exactly, plus the invariant that makes the warning
true in the first place:

    pytest collects exactly the module-level functions more than unittest does.

That invariant is measured live, so it stays honest as the suite grows without
asking anybody to retype a number.

The two measurements that shell out do so on purpose: running ``unittest``
discovery or a ``pytest`` collection inside the suite that is already running
would import every test module a second time under a different module name,
and any import-time registration would then run twice.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

# Every file that publishes the figures. Add a file here when it starts quoting
# them; leaving one out is how the numbers diverged between documents before.
DOCUMENTS = ("AGENTS.md", "CONTRIBUTING.md")

# The share of the suite the documents describe as "roughly a tenth". The band
# is deliberately wide: it exists to catch the phrase becoming plainly wrong
# (a fifth, or a rounding error), not to police a decimal.
SHARE_LOWER, SHARE_UPPER = 0.05, 0.15

_FUNCTIONS_RE = re.compile(r"\*{0,2}(\d+)\*{0,2}\s+module-level", re.I)
_FILES_RE = re.compile(r"across\s+\*{0,2}(\d+)\*{0,2}\s+files", re.I)
# Guard against the fragile absolutes creeping back in.
_ABSOLUTE_RE = re.compile(
    r"(?:runs|collects)\s+\*{0,2}\d{3,}\*{0,2}\s+tests", re.I
)


def _documented(name: str) -> dict[str, int | None]:
    """Pull the published figures out of one Markdown file.

    Whitespace is collapsed first: the same sentence is written on one long
    line in AGENTS.md and wrapped across several lines in CONTRIBUTING.md.
    """
    text = " ".join((REPO_ROOT / name).read_text(encoding="utf-8").split())
    figures: dict[str, int | None] = {}
    for key, pattern in (("functions", _FUNCTIONS_RE), ("files", _FILES_RE)):
        match = pattern.search(text)
        figures[key] = int(match.group(1)) if match else None
    figures["absolute_totals"] = len(_ABSOLUTE_RE.findall(text))
    return figures


def _measure_unittest_discovery(start_dir: str) -> int:
    """Count what ``python -m unittest discover -s <start_dir>`` would run."""
    script = (
        "import unittest, sys;"
        "print(unittest.TestLoader().discover(start_dir=sys.argv[1]).countTestCases())"
    )
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", script, start_dir],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"unittest discovery of {start_dir!r} failed:\n{result.stderr}"
        )
    return int(result.stdout.strip())


def _measure_pytest_collection(target: str) -> int:
    """Count what ``pytest --collect-only`` collects under ``target``."""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only",
         "--no-header", "-p", "no:cacheprovider", target],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=600,
    )
    match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout)
    if match is None:
        raise AssertionError(
            "could not read a collection count from pytest output:\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return int(match.group(1))


def _count_module_level_test_functions() -> tuple[int, int]:
    """Return (functions, files) for module-level ``test_*`` defs in tests/.

    "Module level" means exactly what makes ``unittest`` blind to them: a
    ``def test_*`` at the top level of the module, not inside a class.
    """
    functions = 0
    files = 0
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        count = sum(
            1
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
        if count:
            functions += count
            files += 1
    return functions, files


class DocumentedUnderCollectionTests(unittest.TestCase):
    """The published under-collection warning must match a fresh measurement."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.documented = {name: _documented(name) for name in DOCUMENTS}

    def test_every_document_publishes_both_figures(self) -> None:
        for name, figures in self.documented.items():
            for key in ("functions", "files"):
                self.assertIsNotNone(
                    figures[key],
                    f"{name} no longer states the {key!r} figure, or states it in "
                    f"wording this guard cannot parse. Keep the phrasing "
                    f"'N module-level ... across M files', or update the regexes "
                    f"in {Path(__file__).name}.",
                )

    def test_documents_agree_with_each_other(self) -> None:
        reference_name, reference = next(iter(self.documented.items()))
        for name, figures in self.documented.items():
            if name == reference_name:
                continue
            for key in ("functions", "files"):
                self.assertEqual(
                    figures[key], reference[key],
                    f"{name} says {key}={figures[key]} but {reference_name} says "
                    f"{reference[key]}. The same measurement must not be published "
                    f"two different ways.",
                )

    def test_documents_do_not_publish_absolute_suite_totals(self) -> None:
        """Absolute per-runner totals go stale; keep them out of the documents.

        They were wrong twice before this guard existed. The figures that
        survive a growing suite are the ones the warning actually needs.
        """
        for name, figures in self.documented.items():
            self.assertEqual(
                figures["absolute_totals"], 0,
                f"{name} publishes an absolute suite total again (a phrase like "
                f"'runs 1476 tests' or 'collects 1638'). 29% of commits touch "
                f"tests/, so that number is stale almost immediately. State the "
                f"module-level function count instead and let this guard check it.",
            )

    def test_module_level_figures_are_current(self) -> None:
        functions, files = _count_module_level_test_functions()
        for name, figures in self.documented.items():
            self.assertEqual(
                figures["functions"], functions,
                f"{name} says {figures['functions']} module-level test_* "
                f"functions; tests/ now has {functions}. Update the number.",
            )
            self.assertEqual(
                figures["files"], files,
                f"{name} says they are spread across {figures['files']} files; "
                f"they are now across {files}. Update the number.",
            )

    @unittest.skipUnless(find_spec("pytest"), "pytest is not installed")
    def test_unittest_misses_exactly_the_module_level_functions(self) -> None:
        """The claim itself: the gap between the runners *is* those functions.

        If this fails, the warning has stopped being true -- either unittest
        started finding some of them, or pytest is collecting something else
        unittest cannot see -- and the paragraph needs rewriting, not the
        number bumping.
        """
        functions, _ = _count_module_level_test_functions()
        by_pytest = _measure_pytest_collection("tests")
        by_unittest = _measure_unittest_discovery("tests")
        self.assertEqual(
            by_pytest - by_unittest, functions,
            f"pytest collects {by_pytest} in tests/ and unittest discovers "
            f"{by_unittest}, a gap of {by_pytest - by_unittest}, but there are "
            f"{functions} module-level test_* functions. The documented "
            f"explanation for the gap no longer accounts for it.",
        )

    @unittest.skipUnless(find_spec("pytest"), "pytest is not installed")
    def test_the_missed_share_is_still_roughly_a_tenth(self) -> None:
        functions, _ = _count_module_level_test_functions()
        by_pytest = _measure_pytest_collection("tests")
        share = functions / by_pytest
        self.assertTrue(
            SHARE_LOWER <= share <= SHARE_UPPER,
            f"the documents call the missed functions 'roughly a tenth' of the "
            f"suite, but they are now {share:.1%} ({functions} of {by_pytest}). "
            f"Reword the claim in {' and '.join(DOCUMENTS)}.",
        )


if __name__ == "__main__":
    unittest.main()
