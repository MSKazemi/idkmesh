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
    ("pages-site",),
    ("pages-fallback",),
    ("release-provenance",),
    ("github-authority-audit",),
    ("egress-policy", "check"),
    ("secret-reference", "check"),
    ("api-network-profile", "check"),
    ("break-glass", "check"),
    ("connections", "validate"),
    ("connections", "list"),
    ("connections", "import"),
    ("connections", "stored"),
    ("connections", "probe"),
    ("route", "explain"),
    ("doctor",),
    ("github-workflow",),
    ("github-workflow", "preview"),
    ("github-workflow", "status"),
    ("work",),
    ("work", "preview"),
    ("work-unit", "list"),
    ("work-unit", "status"),
    ("project", "status"),
    ("events", "list"),
    ("api-storage", "plan-migrations"),
    ("api-storage", "apply-migrations"),
    ("api-storage", "plan-retention"),
    ("api-storage", "backup"),
    ("api-storage", "verify-backup"),
    ("api-storage", "restore"),
    ("api-slo", "check"),
    ("api-slo", "contract"),
    ("local-loop",),
    ("local-loop-replay",),
    ("local-loop-record-decision",),
)

_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class HelpExamplesTests(unittest.TestCase):
    """Parser construction is the dominant cost here, so it is done once.

    ``cli.build_parser()`` is called ~100 times by the checks below if every
    ``help_text``/``parse_args`` call builds its own (~0.03 CPU-s each, ~7 CPU-s
    in total against the unit tier's hard CPU budget). Two parsers are built once
    in ``setUpClass`` and every test shares them. Neither is ever mutated:
    ``parse_args`` and ``--help`` rendering only read the parser. Parser ``B``
    exists so ``test_examples_are_deterministic_and_machine_path_free`` still
    compares the help of two *independently built* parsers (as it did when it
    built a fresh parser per call) rather than one parser against itself.
    """

    @classmethod
    def setUpClass(cls):
        cls.parser = cli.build_parser()
        cls.second_parser = cli.build_parser()
        cls._help_cache = {}

    def _render(self, parser, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                parser.parse_args([*argv, "--help"])
        self.assertEqual(caught.exception.code, 0)
        return stdout.getvalue()

    def help_text(self, argv, parser=None):
        """Render one command's real ``--help`` output via ``build_parser()``.

        Rendering is deterministic per (parser, argv) and the result is an
        immutable ``str``, so it is cached after its first successful render.
        """
        parser = self.parser if parser is None else parser
        key = (id(parser), tuple(argv))
        if key not in self._help_cache:
            self._help_cache[key] = self._render(parser, argv)
        return self._help_cache[key]

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
                    parsed = self.parser.parse_args(tokens[1:])
                    self.assertEqual(parsed.command, argv[0])
                    if len(argv) == 2:
                        sub_attr = f"{argv[0].replace('-', '_')}_command"
                        self.assertEqual(getattr(parsed, sub_attr), argv[1])

    def test_every_non_subparser_argument_has_help_text(self):
        import argparse

        def _walk(parser, path=("idkmesh",)):
            missing = []
            seen_parsers = set()
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, subparser in action.choices.items():
                        if id(subparser) in seen_parsers:
                            continue
                        seen_parsers.add(id(subparser))
                        missing.extend(_walk(subparser, path + (name,)))
                else:
                    if not action.help:
                        missing.append(f"{' '.join(path)} dest={action.dest!r}")
            return missing

        missing = _walk(cli.build_parser())
        self.assertEqual(
            missing,
            [],
            f"The following CLI arguments are missing help text: {missing}",
        )

    def test_examples_are_deterministic_and_machine_path_free(self):
        for argv in EXAMPLE_COMMANDS:
            first = self.help_text(argv)
            self.assertEqual(
                first,
                self.help_text(argv, self.second_parser),
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
