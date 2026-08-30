"""The emergence-sim test list must be the same in the workflow and the README.

`sim/README.md` tells a reader "This is the same list
`.github/workflows/emergence-sim.yml` runs; keep the two in step."  That claim
went false once already: E030 landed in the README and was never added to the
workflow, so the documented command covered a module that CI did not.  Prose
cannot hold the two in step, so this does.
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "emergence-sim.yml")
README = os.path.join(REPO_ROOT, "sim", "README.md")

TEST_FILE = re.compile(r"tests/test_[a-z0-9_]+\.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _workflow_pytest_list() -> set:
    for line in _read(WORKFLOW).splitlines():
        stripped = line.strip()
        if stripped.startswith("run: python -m pytest -q tests/"):
            return set(TEST_FILE.findall(stripped))
    raise AssertionError("no pytest run line found in emergence-sim.yml")


def _readme_pytest_list() -> set:
    text = _read(README)
    marker = "python -m pytest -q \\"
    start = text.index(marker)
    end = text.index("```", start)
    return set(TEST_FILE.findall(text[start:end]))


class TestListParityTest(unittest.TestCase):
    def test_the_readme_still_makes_the_claim_this_test_guards(self):
        self.assertIn(
            "This is the same list `.github/workflows/emergence-sim.yml` runs",
            _read(README),
            "if the claim is removed, remove this guard with it",
        )

    def test_the_two_lists_are_identical(self):
        workflow, readme = _workflow_pytest_list(), _readme_pytest_list()
        self.assertEqual(
            workflow - readme,
            set(),
            "the workflow runs tests the README does not document",
        )
        self.assertEqual(
            readme - workflow,
            set(),
            "the README documents tests the workflow does not run",
        )

    def test_every_listed_test_file_exists(self):
        for name in _workflow_pytest_list():
            with self.subTest(name=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(REPO_ROOT, name)),
                    f"{name} is listed but not present",
                )

    def test_every_sim_experiment_module_has_a_listed_test(self):
        # A new sim/eNNN_*.py that nobody added to the list is the exact drift
        # that made the README's claim false for E030.
        listed = _workflow_pytest_list()
        sim_dir = os.path.join(REPO_ROOT, "sim")
        for entry in sorted(os.listdir(sim_dir)):
            match = re.fullmatch(r"(e\d{3})_[a-z0-9_]+\.py", entry)
            if not match:
                continue
            prefix = f"tests/test_{match.group(1)}_"
            with self.subTest(module=entry):
                self.assertTrue(
                    any(name.startswith(prefix) for name in listed)
                    or not any(
                        f.startswith(f"test_{match.group(1)}_")
                        for f in os.listdir(os.path.join(REPO_ROOT, "tests"))
                    ),
                    f"{entry} has a test file that the emergence-sim list omits",
                )


if __name__ == "__main__":
    unittest.main()
