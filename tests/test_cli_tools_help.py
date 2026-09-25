"""Smoke test asserting that every argparse CLI tool under tools/ responds to --help."""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"


def discover_argparse_tools() -> list[Path]:
    """Discover Python scripts in tools/ that use argparse."""
    tools = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "argparse" in content:
            tools.append(path)
    return tools


def _help_output(tool_path: Path) -> tuple[int, str]:
    """Run one tool's ``--help`` as ``__main__`` inside this process.

    Spawning an interpreter per tool cost about 13 of the unit tier's 90 CPU-second
    budget -- over 50 interpreter startups, which was the whole cost rather than any
    work the tools do. ``runpy`` still executes each tool through its real
    ``__main__`` entry path with a real ``argv``, so the property under test is
    unchanged, while the startup is paid once for the suite.
    """
    argv = sys.argv[:]
    path = sys.path[:]
    modules = set(sys.modules)
    cwd = os.getcwd()
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    try:
        os.chdir(ROOT)
        sys.argv = [str(tool_path), "--help"]
        # CPython puts a script's own directory at sys.path[0]. Several tools rely
        # on that for a `from tools.x import ...` / `from x import ...` sibling
        # import fallback, so reproduce it rather than lose that coverage.
        sys.path.insert(0, str(tool_path.parent))
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(str(tool_path), run_name="__main__")
            except SystemExit as exc:
                code = 0 if exc.code is None else int(exc.code)
    finally:
        sys.argv = argv
        sys.path[:] = path
        # Evict only modules loaded out of tools/, so one tool cannot satisfy
        # another's sibling import and mask a broken fallback. Everything else
        # stays cached: purging the whole set forced 50-odd re-imports here and
        # evicted modules the rest of the suite reuses, which cost more CPU than
        # the subprocesses this replaced.
        for name in set(sys.modules) - modules:
            module = sys.modules.get(name)
            origin = getattr(module, "__file__", None) or ""
            if origin.startswith(str(TOOLS_DIR)):
                sys.modules.pop(name, None)
        os.chdir(cwd)
    return code, stdout.getvalue()


class ArgparseToolsHelpTests(unittest.TestCase):
    def test_discover_argparse_tools_finds_minimum_count(self) -> None:
        """Guard the tool discovery against silent under-collection."""
        tools = discover_argparse_tools()
        self.assertGreaterEqual(
            len(tools),
            40,
            f"Expected at least 40 argparse tools in {TOOLS_DIR}, found {len(tools)}.",
        )

    def test_tools_support_help_option(self) -> None:
        """Assert that every discovered tool exits with 0 and prints help on --help."""
        for tool_path in discover_argparse_tools():
            rel_path = tool_path.relative_to(ROOT)
            with self.subTest(tool=str(rel_path)):
                code, out = _help_output(tool_path)
                self.assertEqual(
                    code, 0, f"Tool {rel_path} exited with code {code} on --help."
                )
                self.assertTrue(
                    out.strip(), f"Tool {rel_path} produced empty stdout on --help."
                )


if __name__ == "__main__":
    unittest.main()
