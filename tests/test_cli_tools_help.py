"""Smoke test asserting that every argparse CLI tool under tools/ responds to --help."""

from __future__ import annotations

import os
import sys
import subprocess
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
        """Assert that every discovered tool exits with 0 and prints help output on --help."""
        tools = discover_argparse_tools()
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)

        for tool_path in tools:
            rel_path = tool_path.relative_to(ROOT)
            with self.subTest(tool=str(rel_path)):
                res = subprocess.run(
                    [sys.executable, str(tool_path), "--help"],
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(ROOT),
                )
                self.assertEqual(
                    res.returncode,
                    0,
                    f"Tool {rel_path} exited with code {res.returncode} on --help.\n"
                    f"Stdout:\n{res.stdout}\nStderr:\n{res.stderr}",
                )
                self.assertTrue(
                    res.stdout.strip(),
                    f"Tool {rel_path} produced empty stdout on --help.",
                )


if __name__ == "__main__":
    unittest.main()
