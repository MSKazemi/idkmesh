import re
from pathlib import Path
import unittest

from tools.publish_starter_tasks import (
    BASE_LABELS,
    BLOB_ROOT,
    CATALOGUE,
    Task,
    absolutise_links,
    parse_catalogue,
    plan,
)


ROOT = Path(__file__).resolve().parents[1]
TASKS = parse_catalogue(CATALOGUE.read_text(encoding="utf-8"))
LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")


class ParsingTests(unittest.TestCase):
    def test_every_catalogued_task_is_parsed(self) -> None:
        # The catalogue's own header states the count, and
        # tests/test_starter_tasks.py holds it to the tree. Reading it here
        # rather than hard-coding a number means the two cannot drift apart.
        header = CATALOGUE.read_text(encoding="utf-8")
        self.assertIn("Ten small, independently useful pieces of work", header)
        self.assertEqual(len(TASKS), 10)

    def test_identifiers_are_unique_and_carry_a_discipline(self) -> None:
        identifiers = [task.identifier for task in TASKS]
        self.assertEqual(len(set(identifiers)), len(identifiers))
        for task in TASKS:
            with self.subTest(task=task.identifier):
                self.assertTrue(task.discipline)
                self.assertTrue(task.heading)
                self.assertTrue(task.body.strip())

    def test_acceptance_criteria_survive_into_the_body(self) -> None:
        # A starter task without its acceptance criterion is bait, not a task.
        for task in TASKS:
            with self.subTest(task=task.identifier):
                self.assertIn("**Acceptance:**", task.issue_body)


class LabelTests(unittest.TestCase):
    def test_every_task_is_newcomer_labelled(self) -> None:
        # This is the whole point: the catalogue exists because the only
        # newcomer-labelled issues were independent-review requests.
        for task in TASKS:
            with self.subTest(task=task.identifier):
                for label in BASE_LABELS:
                    self.assertIn(label, task.labels)


class LinkTests(unittest.TestCase):
    def test_no_relative_link_survives_rendering(self) -> None:
        # A relative target resolves against the file's directory in the
        # catalogue and against the repository root in an issue body. Shipping
        # one would file an issue with a broken link in it.
        for task in TASKS:
            for match in LINK.finditer(task.issue_body):
                with self.subTest(task=task.identifier, target=match.group("target")):
                    self.assertTrue(
                        match.group("target").startswith(("http://", "https://", "#"))
                    )

    def test_every_rewritten_link_points_at_a_file_that_exists(self) -> None:
        for task in TASKS:
            for match in LINK.finditer(task.issue_body):
                target = match.group("target")
                if not target.startswith(BLOB_ROOT):
                    continue
                relative = target[len(BLOB_ROOT) + 1 :].split("#", 1)[0]
                with self.subTest(task=task.identifier, path=relative):
                    self.assertTrue(
                        (ROOT / relative).exists(),
                        msg=f"{task.identifier} links to missing {relative}",
                    )

    def test_parent_segments_collapse_rather_than_leaking(self) -> None:
        rewritten = absolutise_links("[c](../../CONTRIBUTING.md)")
        self.assertEqual(rewritten, f"[c]({BLOB_ROOT}/CONTRIBUTING.md)")

    def test_absolute_and_anchor_targets_are_left_alone(self) -> None:
        for original in ("[a](https://example.org/x)", "[b](#section)"):
            with self.subTest(original=original):
                self.assertEqual(absolutise_links(original), original)

    def test_a_fragment_is_preserved_across_the_rewrite(self) -> None:
        self.assertEqual(
            absolutise_links("[a](README.md#why)"),
            f"[a]({BLOB_ROOT}/docs/community/README.md#why)",
        )


class PlanTests(unittest.TestCase):
    def test_a_task_that_names_its_tracking_issue_is_never_filed(self) -> None:
        # V1 is issue 167. Filing it again would fork the one review request
        # the project actually has.
        tracked = [task for task in TASKS if task.tracked_issue is not None]
        self.assertEqual(
            [(task.identifier, task.tracked_issue) for task in tracked],
            [("V1", 167)],
        )
        fileable, skipped = plan(TASKS, set())
        self.assertNotIn("V1", [task.identifier for task in fileable])
        self.assertEqual(len(fileable), 9)
        self.assertTrue(any("#167" in note for note in skipped))

    def test_an_existing_open_title_makes_the_run_idempotent(self) -> None:
        first = plan(TASKS, set())[0]
        existing = {first[0].issue_title}
        second, skipped = plan(TASKS, existing)
        self.assertEqual(len(second), len(first) - 1)
        self.assertTrue(any("already has this title" in note for note in skipped))

    def test_titles_are_unique_and_carry_no_backticks(self) -> None:
        titles = [task.issue_title for task in TASKS]
        self.assertEqual(len(set(titles)), len(titles))
        for title in titles:
            with self.subTest(title=title):
                self.assertNotIn("`", title)
                self.assertTrue(title.startswith("Starter task "))


class SafetyTests(unittest.TestCase):
    def test_posting_is_not_reachable_without_the_explicit_flag(self) -> None:
        # The guard is the point of this tool, so it is asserted on the source
        # rather than trusted: create_issue must be called only under --post.
        source = (ROOT / "tools/publish_starter_tasks.py").read_text(encoding="utf-8")
        self.assertIn("if not args.post:", source)
        after_guard = source.split("if not args.post:", 1)[1]
        before_guard = source.split("if not args.post:", 1)[0]
        self.assertNotIn("create_issue(task)", before_guard.split("def main(")[-1])
        self.assertIn("create_issue(task)", after_guard)

    def test_the_tool_never_creates_a_label(self) -> None:
        source = (ROOT / "tools/publish_starter_tasks.py").read_text(encoding="utf-8")
        self.assertNotIn("label create", source)
        self.assertNotIn('"label"', source)


if __name__ == "__main__":
    unittest.main()
