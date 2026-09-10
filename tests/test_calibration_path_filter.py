from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/task001-v04-canonical-calibration.yml"

# Tokens that look like repo paths but are produced by the run rather than read
# from the checked-out tree.
OUTPUT_PREFIXES = ("results/",)


def watched_paths(text: str) -> set[str]:
    block = re.search(r"^    paths:\n((?:\s*(?:#.*|- \".*\")\n)+)", text, re.M)
    assert block, "no paths: filter found in the workflow"
    return set(re.findall(r'- "([^"]+)"', block.group(1)))


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
