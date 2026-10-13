"""Keep the GitHub Actions reference grounded in current repository workflows.

This is a static trigger/permission/source-path guard, not a full YAML evaluator
or a claim about externally granted permissions, executed jobs, or security.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reference" / "GITHUB_ACTIONS_CODE_MAP.md"
WORKFLOWS = ROOT / ".github" / "workflows"
ROW = re.compile(
    r"^\| \[\x60([a-z0-9-]+\.yml)\x60\]\("
    r"https://github\.com/MSKazemi/idkmesh/blob/main/\.github/workflows/"
    r"([a-z0-9-]+\.yml)\) \| ([^|]+) \| ([^|]+) \|",
    re.MULTILINE,
)
TOP_LEVEL_KEY = re.compile(r"(?m)^[a-zA-Z][a-zA-Z0-9_-]*:")
EVENT_KEY = re.compile(r"(?m)^  ([a-z_]+):")
WRITE_SCOPE = re.compile(r"(?m)^\s+(contents|issues|pull-requests|actions|id-token|attestations|security-events|packages|pages|checks|statuses):\s*write\s*(?:#.*)?$")
SOURCE_LINK = re.compile(r"\]\(https://github\.com/MSKazemi/idkmesh/(blob|tree)/main/([^\s)]+)\)")


def declared_events(source: str) -> set[str]:
    match = re.search(r"(?m)^on:\s*$", source)
    if match is None:
        raise AssertionError("missing top-level on: trigger block")
    tail = source[match.end():]
    stop = TOP_LEVEL_KEY.search(tail)
    block = tail[:stop.start()] if stop else tail
    return set(EVENT_KEY.findall(block))


def declared_write_scopes(source: str) -> set[str]:
    return set(WRITE_SCOPE.findall(source))


class GithubWorkflowDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.rows = ROW.findall(cls.text)

    def test_each_workflow_is_mapped_once(self):
        expected = sorted(
            path.name for suffix in ("*.yml", "*.yaml")
            for path in WORKFLOWS.glob(suffix)
        )
        names = [name for name, _, _, _ in self.rows]
        targets = [target for _, target, _, _ in self.rows]
        self.assertEqual(sorted(targets), expected)
        self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(names, targets)

    def test_declared_events_and_write_scopes_match_source(self):
        for name, target, event_cell, scope_cell in self.rows:
            with self.subTest(workflow=name):
                source = (WORKFLOWS / target).read_text(encoding="utf-8")
                events = {part.strip() for part in event_cell.split(",")}
                writes = {part.strip() for part in scope_cell.split(",")}
                if writes == {"none"}:
                    writes = set()
                self.assertEqual(events, declared_events(source))
                self.assertEqual(writes, declared_write_scopes(source))

    def test_source_links_refer_to_existing_paths(self):
        for kind, path in SOURCE_LINK.findall(self.text):
            with self.subTest(target=path):
                target = ROOT / path
                self.assertTrue(target.is_file() if kind == "blob" else target.is_dir())


if __name__ == "__main__":
    unittest.main()
