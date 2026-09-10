"""Keep the copy-pasteable hook snippets in ``docs/TESTING.md`` runnable.

The automation section of that document hands a contributor three files to
create: a ``.claude/settings.json`` and two shell hooks. They cannot live in the
repository -- ``.gitignore`` excludes ``.claude/`` because it holds per-agent
configuration and personal notes -- so the document reproducing them in full is
the only way anyone gets them, and nothing else in the tree can go red when they
rot.

What this file checks is narrow on purpose: that the JSON parses and that the
shell parses. It cannot check that the hooks still do the right thing, because
running them means running a test tier from inside a test tier. The document
says as much and tells the reader to re-run the probe themselves; this is the
part a machine can hold.

That is still worth holding. A snippet is copied, not read: a contributor pastes
it, gets a syntax error from a file they did not write, and has no reason to
suspect the documentation rather than their own setup.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "TESTING.md"

SECTION_START = "## Automation: running the tiers"
SECTION_END = "### Test selection, and its limits"

_FENCE = re.compile(r"```(json|bash)\n(.*?)```", re.S)


def automation_section() -> str:
    text = DOCUMENT.read_text(encoding="utf-8")
    start, end = text.find(SECTION_START), text.find(SECTION_END)
    if start < 0 or end < 0 or end <= start:
        return ""
    return text[start:end]


def snippets() -> list[tuple[str, str]]:
    """The fenced ``json`` and ``bash`` blocks of the automation section."""
    return _FENCE.findall(automation_section())


def section_prose() -> str:
    """The section with every fenced block removed.

    Checks about what the *document* tells a reader have to run against the
    prose. Searching the whole section instead lets the settings snippet
    satisfy a claim about itself: the first version of
    ``test_the_settings_snippet_points_at_the_scripts_it_publishes`` passed
    happily when the command was renamed to a script the section never shows,
    because the renamed path was still present -- in the very block being
    checked.
    """
    return _FENCE.sub("", automation_section())


def settings_snippet() -> str:
    """The single ``json`` block: the `.claude/settings.json` a reader pastes."""
    return next((text for language, text in snippets() if language == "json"), "")


class DocumentedHookSnippetTests(unittest.TestCase):
    def test_the_automation_section_is_still_findable(self) -> None:
        """Without this, every test below would pass over an empty string."""
        self.assertTrue(
            automation_section(),
            f"could not locate the section between {SECTION_START!r} and "
            f"{SECTION_END!r} in docs/TESTING.md; if it was renamed, update "
            f"SECTION_START/SECTION_END here in the same change.",
        )

    def test_the_section_still_publishes_snippets(self) -> None:
        found = snippets()

        self.assertEqual(
            [language for language, _ in found],
            ["json", "bash", "bash"],
            "expected the settings file and both hook scripts, in that order; "
            f"found {[language for language, _ in found]}. A contributor "
            "follows this section by copying every block in order.",
        )

    def test_the_settings_snippet_is_valid_json(self) -> None:
        body = settings_snippet()

        try:
            settings = json.loads(body)
        except json.JSONDecodeError as error:  # pragma: no cover - message path
            self.fail(f"the .claude/settings.json snippet does not parse: {error}")

        self.assertIn(
            "hooks",
            settings,
            "the settings snippet parses but declares no `hooks` key, so "
            "pasting it wires up nothing at all",
        )

    def test_the_settings_snippet_points_at_the_scripts_it_publishes(self) -> None:
        """A settings file naming a path the document never provides is a dead end."""
        body = settings_snippet()
        commands = re.findall(r'"command":\s*"([^"]+)"', body)

        self.assertTrue(commands, "the settings snippet registers no command")
        prose = section_prose()
        for command in commands:
            with self.subTest(command=command):
                self.assertIn(
                    Path(command).name,
                    prose,
                    f"the settings snippet runs {command}, which this section "
                    f"never shows the reader how to create",
                )

    @unittest.skipIf(shutil.which("bash") is None, "bash is not installed")
    def test_each_shell_snippet_parses(self) -> None:
        scripts = [text for language, text in snippets() if language == "bash"]

        self.assertTrue(scripts, "no shell snippet found to check")
        for index, script in enumerate(scripts):
            with self.subTest(snippet=index):
                result = subprocess.run(
                    ["bash", "-n"],
                    input=script,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"shell snippet {index} in docs/TESTING.md is not valid "
                    f"bash: {result.stderr.strip()}",
                )

    def test_each_shell_snippet_delegates_to_testkit(self) -> None:
        """The hooks exist to run a tier; one that runs pytest directly diverges.

        `docs/TESTING.md` states that the Makefile, the hooks and CI all go
        through `scripts/testkit.py` "and cannot drift apart". A snippet calling
        pytest itself would quietly cost that property -- no budget, no cache.
        """
        scripts = [text for language, text in snippets() if language == "bash"]

        self.assertTrue(scripts, "no shell snippet found to check")
        for index, script in enumerate(scripts):
            with self.subTest(snippet=index):
                self.assertIn(
                    "scripts/testkit.py",
                    script,
                    f"shell snippet {index} does not go through testkit.py, so "
                    f"it bypasses the tier budgets and the result cache",
                )


if __name__ == "__main__":
    unittest.main()
