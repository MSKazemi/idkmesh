from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/task001-v04-canonical-calibration.yml"

# Tokens that look like repo paths but are produced by the run rather than read
# from the checked-out tree.
OUTPUT_PREFIXES = ("results/",)


# A YAML sequence entry may be double-quoted, single-quoted or bare, and the
# block may carry comments. Parsing only one of those spellings makes a purely
# cosmetic reformat look like a missing path: an earlier version of this parser
# read zero entries from a single-quoted block and then reported every watched
# file as unwatched.
ENTRY = re.compile(r"""^\s*-\s*(?:"([^"]+)"|'([^']+)'|([^\s#].*?))\s*$""")


def watched_paths(text: str) -> set[str]:
    found: set[str] = set()
    in_block = False
    saw_block = False
    for line in text.splitlines():
        if re.match(r"^\s*paths:\s*$", line):
            in_block, saw_block = True, True
            continue
        if not in_block:
            continue
        if not line.strip() or re.match(r"^\s*#", line):
            continue
        match = ENTRY.match(line)
        if match:
            found.add(next(g for g in match.groups() if g))
        else:
            in_block = False
    assert saw_block, "no paths: filter found in the workflow"
    assert found, "the paths: filter parsed to zero entries; the parser is wrong, "\
                  "not the workflow"
    return found


def named_tree_files(text: str) -> set[str]:
    """Every current-tree file this workflow's own steps name.

    Two spellings count. A literal path (``experiments/foo.py``) appears in
    ``py_compile`` lists, ``test -f`` guards and script arguments. A dotted
    module (``python -m unittest tests.test_x``) names a file just as
    concretely, and is the spelling that hid
    ``tests/test_patch_evaluator_transition_v04.py`` from an earlier reading.
    """
    found = set()

    for token in re.findall(r"[\w./-]+\.(?:py|json|txt|md|yml|yaml)", text):
        if "$" in token or token.startswith(OUTPUT_PREFIXES):
            continue
        if (ROOT / token).is_file():
            found.add(token)

    for module in re.findall(r"python -m unittest\s+([\w.]+)", text):
        candidate = Path(*module.split(".")).with_suffix(".py")
        if (ROOT / candidate).is_file():
            found.add(candidate.as_posix())

    return found


class PathsBlockParserTests(unittest.TestCase):
    """The parser must read the filter, not one way of spelling it.

    All three sequence-entry spellings below are the same YAML. A parser that
    understands only one of them reports the other two as an empty filter, and
    the caller then blames the workflow for files it does watch.
    """

    BLOCK = """on:
  pull_request:
    paths:
      # a comment inside the block
      - "double.py"
      - 'single.py'
      - bare.py
  push:
    branches: [main]
"""

    def test_all_three_entry_spellings_are_read(self) -> None:
        self.assertEqual(
            watched_paths(self.BLOCK),
            {"double.py", "single.py", "bare.py"},
        )

    def test_the_real_workflow_reformatted_to_single_quotes_reads_the_same(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        reformatted = re.sub(r'^(\s*-\s*)"([^"]+)"$', r"\1'\2'", text, flags=re.M)

        self.assertNotEqual(reformatted, text, "the fixture no longer reformats anything")
        self.assertEqual(watched_paths(reformatted), watched_paths(text))

    def test_a_filter_that_parses_to_nothing_is_an_error_not_a_pass(self) -> None:
        with self.assertRaises(AssertionError):
            watched_paths("on:\n  pull_request:\n    paths:\n\njobs:\n")


class CalibrationPathFilterTests(unittest.TestCase):
    """The calibration runs against the PR head, so it must watch what it reads.

    Before this guard, the filter watched the two calibration *tools* but not
    ``experiments/transition_patch_verifier.py`` — the module whose behaviour the
    calibration certifies. Editing it therefore did not run the calibration, and
    the workflow's verdict was produced only for pull requests that happened to
    touch something else.
    """

    def test_every_file_the_run_names_is_watched(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        watched = watched_paths(text)

        unwatched = sorted(named_tree_files(text) - watched)

        self.assertEqual(
            unwatched,
            [],
            "these files are read by the calibration but do not trigger it: "
            f"{unwatched}",
        )

    def test_the_filter_only_lists_files_that_exist(self) -> None:
        watched = watched_paths(WORKFLOW.read_text(encoding="utf-8"))

        missing = sorted(p for p in watched if not (ROOT / p).exists())

        self.assertEqual(
            missing,
            [],
            f"the filter watches paths that no longer exist: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
