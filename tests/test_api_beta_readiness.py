"""Tests for tools/api_beta_readiness.py (issue #747).

The tool is only worth trusting if its own declarations cannot rot: every
evidence file must exist, a ``satisfied`` item must not carry a recorded gap,
every item that is not satisfied must say what is missing, and an item backed by
the qualification run must be un-satisfied whenever that report is absent,
stale, dirty or red.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import api_beta_readiness as ready
from tools import api_release_qualification as aq

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40


def _git(tags=(), dirty=False, head=HEAD):
    def run(argv, root):
        if argv[:2] == ["rev-parse", "HEAD"]:
            return head
        if argv[:2] == ["tag", "--points-at"]:
            return "\n".join(tags)
        if argv[:2] == ["status", "--porcelain"]:
            return " M x" if dirty else ""
        return None

    return run


def _report(root, *, head=HEAD, dirty=False, failing=()):
    groups = ("contract", "fuzz", "security", "reliability", "client")
    checks = [
        {"id": f"{g}:x", "group": g, "status": "failed" if g in failing else "passed"}
        for g in groups
    ]
    path = root / ready.QUALIFICATION_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"git_revision": head, "git_dirty": dirty, "checks": checks}))


def _tree(items):
    """A temp repo containing exactly the evidence files the items name."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for item in items:
        for rel in item.evidence:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("x")
    return tmp, root


class DeclarationTests(unittest.TestCase):
    def test_the_item_list_matches_the_fourteen_required_by_the_issue(self):
        self.assertEqual(len(ready.ITEMS), 14)
        ids = [item.id for item in ready.ITEMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_evidence_file_exists_in_the_repository(self):
        for item in ready.ITEMS:
            for rel in item.evidence:
                with self.subTest(item=item.id, evidence=rel):
                    self.assertTrue((REPO_ROOT / rel).exists(), rel)

    def test_a_satisfied_item_has_no_gap_and_an_unsatisfied_one_names_it(self):
        for item in ready.ITEMS:
            with self.subTest(item=item.id):
                if item.declared == ready.SATISFIED:
                    self.assertEqual(item.gap, "")
                    self.assertTrue(item.evidence or item.probe)
                else:
                    self.assertTrue(item.gap, "say what is missing")

    def test_qualification_groups_are_groups_the_qualification_run_emits(self):
        known = {check.group for check in aq.build_checks(None)}
        for item in ready.ITEMS:
            for group in item.qualification_groups:
                with self.subTest(item=item.id, group=group):
                    self.assertIn(group, known)


class EvaluationTests(unittest.TestCase):
    def evaluate(self, items, **git_kwargs):
        tmp, root = _tree(items)
        self.addCleanup(tmp.cleanup)
        return root, lambda: ready.evaluate(root, items, git=_git(**git_kwargs))

    def test_the_real_tree_is_not_ready_and_says_why(self):
        results = ready.evaluate(REPO_ROOT)
        self.assertEqual(ready.verdict(results), "not ready")
        text = ready.render(results)
        self.assertIn("release note must state", text)
        self.assertIn("NOT READY", text)

    def test_a_missing_evidence_file_makes_the_item_unverified(self):
        item = ready.Item("x", "req", ready.SATISFIED, evidence=("docs/gone.md",))
        results = ready.evaluate(REPO_ROOT, (item,), git=_git())
        self.assertEqual(results[0].status, ready.UNVERIFIED)
        self.assertIn("docs/gone.md", results[0].reasons[0])

    def test_a_qualification_backed_item_needs_a_current_green_report(self):
        item = ready.Item(
            "r", "req", ready.SATISFIED, evidence=("a.md",), qualification_groups=("reliability",)
        )
        cases = {
            "absent": (None, ready.UNVERIFIED),
            "green": (dict(), ready.SATISFIED),
            "stale revision": (dict(head="b" * 40), ready.UNVERIFIED),
            "dirty tree": (dict(dirty=True), ready.UNVERIFIED),
            "failing group": (dict(failing=("reliability",)), ready.UNVERIFIED),
            "other group failing": (dict(failing=("client",)), ready.SATISFIED),
        }
        for name, (report_kwargs, expected) in cases.items():
            with self.subTest(case=name):
                root, run = self.evaluate((item,))
                if report_kwargs is not None:
                    _report(root, **report_kwargs)
                self.assertEqual(run()[0].status, expected)

    def test_the_tag_item_needs_a_beta_tag_on_a_clean_head(self):
        template = next(i for i in ready.ITEMS if i.probe == "git_tag")
        item = ready.Item(
            template.id, template.requirement, template.declared,
            gap=template.gap, probe="git_tag",
        )
        cases = (
            ("no tag", dict(tags=()), ready.UNMET),
            ("other tag", dict(tags=("v1.0.0",)), ready.UNMET),
            ("beta tag, clean", dict(tags=("api-v1-beta.1",)), ready.SATISFIED),
            ("beta tag, dirty", dict(tags=("api-v1-beta.1",), dirty=True), ready.UNMET),
        )
        for name, git_kwargs, expected in cases:
            with self.subTest(case=name):
                result = ready.evaluate(REPO_ROOT, (item,), git=_git(**git_kwargs))
                self.assertEqual(result[0].status, expected)

    def test_ready_only_when_every_item_is_satisfied(self):
        ok = ready.Item("a", "a", ready.SATISFIED)
        partial = ready.Item("b", "b", ready.PARTIAL, gap="g")
        self.assertEqual(ready.verdict(ready.evaluate(REPO_ROOT, (ok,), git=_git())), "ready")
        self.assertEqual(
            ready.verdict(ready.evaluate(REPO_ROOT, (ok, partial), git=_git())), "not ready"
        )


class CliTests(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(ready.main(["--no-fail"]), 0)
        self.assertEqual(ready.main([]), 1)  # the real tree is not ready
        self.assertEqual(ready.main(["--root", "/nonexistent-root"]), 2)

    def test_json_report_is_machine_readable(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ready.main(["--json", "--no-fail"])
        document = json.loads(buffer.getvalue())
        self.assertEqual(document["schema"], ready.REPORT_SCHEMA)
        self.assertEqual(len(document["items"]), 14)


if __name__ == "__main__":
    unittest.main()
