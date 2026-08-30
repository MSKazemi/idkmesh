"""The starter-task catalogue must stay true to the tree it describes.

A list of contribution opportunities is worth exactly as much as its accuracy.
A newcomer who picks a task, follows it, and finds the work already done learns
that this project's documentation cannot be trusted -- which is a worse first
impression than having no list at all.

So the checkable claims are checked. When a task is completed, the relevant
assertion here fails and the catalogue entry has to be removed or rewritten in
the same change.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "docs" / "community" / "STARTER_TASKS.md"
INDEX = ROOT / "docs" / "community" / "README.md"


def _argparse_tools():
    return sorted(
        path
        for path in (ROOT / "tools").glob("*.py")
        if "argparse" in path.read_text(encoding="utf-8")
    )


def _untested_sim_modules():
    untested = []
    for path in sorted((ROOT / "sim").glob("*.py")):
        if path.stem == "__init__":
            continue
        if not (ROOT / "tests" / f"test_{path.stem}.py").exists():
            untested.append(path.stem)
    return untested


class CatalogueStructureTest(unittest.TestCase):
    def setUp(self):
        self.text = CATALOGUE.read_text(encoding="utf-8")
        self.tasks = re.findall(r"^### ([A-Z]+\d+) — (.+)$", self.text, re.M)
        self.disciplines = re.findall(r"^## (.+)$", self.text, re.M)

    def test_the_catalogue_offers_at_least_ten_tasks(self):
        self.assertGreaterEqual(len(self.tasks), 10, "issue 9 asks for at least ten")

    def test_task_identifiers_are_unique(self):
        ids = [task_id for task_id, _ in self.tasks]
        self.assertEqual(sorted(ids), sorted(set(ids)), f"duplicate ids in {ids}")

    def test_the_catalogue_spans_more_than_coding(self):
        headings = {d.strip().lower() for d in self.disciplines}
        for required in ("documentation", "testing", "security", "research", "community"):
            with self.subTest(discipline=required):
                self.assertIn(
                    required,
                    headings,
                    f"issue 9 asks for {required} tasks, not only coding",
                )

    def test_every_task_states_how_it_will_be_accepted(self):
        sections = re.split(r"^### ", self.text, flags=re.M)[1:]
        for section in sections:
            name = section.splitlines()[0]
            with self.subTest(task=name):
                self.assertIn("**Acceptance:**", section)

    def test_parallel_attempts_are_marked(self):
        self.assertIn(
            "Parallel welcome",
            self.text,
            "issue 9 asks that tasks welcoming parallel attempts be marked",
        )

    def test_the_catalogue_is_reachable_from_its_directory_index(self):
        self.assertIn("STARTER_TASKS.md", INDEX.read_text(encoding="utf-8"))


class CatalogueAccuracyTest(unittest.TestCase):
    """The claims a reader would act on must match the repository."""

    def setUp(self):
        self.text = CATALOGUE.read_text(encoding="utf-8")

    def test_the_stated_tool_count_matches_the_tree(self):
        match = re.search(r"contains (\d+) modules that build an `argparse` parser", self.text)
        self.assertIsNotNone(match, "task T1 no longer states a tool count")
        self.assertEqual(
            int(match.group(1)),
            len(_argparse_tools()),
            "task T1's tool count is stale",
        )

    def test_every_module_named_as_untested_is_still_untested(self):
        untested = set(_untested_sim_modules())
        block = self.text.split("### T2")[1].split("###")[0]
        named = set(re.findall(r"`(e0\d+_\w+|run_\w+)`", block))
        self.assertTrue(named, "task T2 no longer names any module")
        done = sorted(named - untested)
        self.assertEqual(
            done,
            [],
            f"these modules now have tests and must leave the catalogue: {done}",
        )

    def test_referenced_paths_exist(self):
        for target in re.findall(r"\]\(([^)#]+\.md)\)", self.text):
            if target.startswith("http"):
                continue
            with self.subTest(target=target):
                self.assertTrue(
                    (CATALOGUE.parent / target).resolve().exists(),
                    f"{target} does not exist",
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
