"""Usage-example regression tests for ``idkmesh run`` and ``idkmesh control-tower``.

Issue #901 asks each of these commands' ``--help`` output to end with a
copy-pasteable ``Examples:`` block. These tests fail when an example block is
missing, and they parse every example's argv through the real
``idkmesh.cli.build_parser()`` so an example that uses a flag the parser
rejects fails here instead of misleading users.

Modeled on ``tests/test_product_spine_run_cli.py`` and
``tests/test_cli_tools_help.py``: help text is rendered in-process through the
real parser, keeping the checks fast and deterministic.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shlex
import unittest

from idkmesh import cli


# (subcommand path, ...) for every command that must carry examples.
EXAMPLE_COMMANDS = (
    ("run", "create"),
    ("run", "status"),
    ("run", "list"),
    ("run", "cancel"),
    ("control-tower",),
)

_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class HelpExamplesTests(unittest.TestCase):
    def help_text(self, argv):
        """Render one command's real ``--help`` output via ``build_parser()``."""
        parser = cli.build_parser()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                parser.parse_args([*argv, "--help"])
        self.assertEqual(caught.exception.code, 0)
        return stdout.getvalue()

    def example_lines(self, argv):
        text = self.help_text(argv)
        self.assertIn(
            "Examples:",
            text,
            f"help for {' '.join(argv)} has no Examples: block",
        )
        block = text.split("Examples:", 1)[1]
        return [line.strip() for line in block.splitlines() if line.strip()]

    def test_each_command_help_ends_with_an_examples_block(self):
        for argv in EXAMPLE_COMMANDS:
            with self.subTest(command=" ".join(argv)):
                text = self.help_text(argv)
                examples = self.example_lines(argv)
                self.assertGreaterEqual(
                    len(examples),
                    2,
                    f"{' '.join(argv)} should show 2-3 examples, "
                    f"found {len(examples)}",
                )
                self.assertLessEqual(
                    len(examples),
                    3,
                    f"{' '.join(argv)} should show 2-3 examples, "
                    f"found {len(examples)}",
                )
                for line in examples:
                    self.assertTrue(
                        line == "idkmesh" or line.startswith("idkmesh "),
                        f"example line is not an idkmesh command: {line!r}",
                    )
                self.assertEqual(
                    text.rstrip().splitlines()[-1].strip(),
                    examples[-1],
                    f"help for {' '.join(argv)} does not end with its "
                    f"Examples: block",
                )

    def test_every_example_is_accepted_by_the_real_parser(self):
        for argv in EXAMPLE_COMMANDS:
            for line in self.example_lines(argv):
                with self.subTest(example=line):
                    tokens = shlex.split(line)
                    self.assertEqual(tokens[0], "idkmesh")
                    parsed = cli.build_parser().parse_args(tokens[1:])
                    self.assertEqual(parsed.command, argv[0])
                    if len(argv) == 2:
                        self.assertEqual(parsed.run_command, argv[1])

    def test_examples_are_deterministic_and_machine_path_free(self):
        for argv in EXAMPLE_COMMANDS:
            first = self.help_text(argv)
            self.assertEqual(
                first,
                self.help_text(argv),
                f"help for {' '.join(argv)} is not deterministic",
            )
            home = os.path.expanduser("~")
            for line in self.example_lines(argv):
                for token in shlex.split(line):
                    self.assertFalse(
                        os.path.isabs(token)
                        or token.startswith("~")
                        or _DRIVE_PATH_RE.match(token),
                        f"example uses a machine path: {line!r}",
                    )
                self.assertNotIn(
                    home,
                    line,
                    f"example leaks a home directory path: {line!r}",
                )


if __name__ == "__main__":
    unittest.main()
