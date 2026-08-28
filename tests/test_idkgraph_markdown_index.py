import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.idkgraph_markdown_index import (
    build_index,
    parse_markdown,
    serialize_index,
    tracked_relative_paths,
)


class MarkdownIdentityTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_deterministic_order_and_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "z.md", "# Zed\n")
            self._write(root, "a.md", "# Alpha\n## Child\n")

            first = serialize_index(build_index(root))
            second = serialize_index(build_index(root))

            self.assertEqual(first, second)
            data = json.loads(first)
            self.assertEqual([doc["path"] for doc in data["documents"]], ["a.md", "z.md"])

    def test_repeated_unicode_and_fenced_headings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write(
                root,
                "docs/sample.md",
                """# Café — α!\n## Repeat\n## Repeat\n```python\n# not a heading\n```\nTitle Ω\n=======\n""",
            )

            doc = parse_markdown(path, root)
            headings = doc["headings"]

            self.assertEqual(
                [(item["text"], item["level"], item["occurrence"]) for item in headings],
                [
                    ("Café — α!", 1, 1),
                    ("Repeat", 2, 1),
                    ("Repeat", 2, 2),
                    ("Title Ω", 1, 1),
                ],
            )
            self.assertNotEqual(headings[1]["heading_id"], headings[2]["heading_id"])

    def test_line_number_is_not_part_of_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write(root, "doc.md", "# Stable\n")
            before = parse_markdown(path, root)["headings"][0]

            self._write(root, "doc.md", "intro\n\n# Stable\n")
            after = parse_markdown(path, root)["headings"][0]

            self.assertEqual(before["heading_id"], after["heading_id"])
            self.assertNotEqual(before["line"], after["line"])

    def test_heading_or_path_change_changes_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self._write(root, "a.md", "# Alpha\n")
            alpha = parse_markdown(original, root)
            original_doc_id = alpha["document_id"]
            original_heading_id = alpha["headings"][0]["heading_id"]

            self._write(root, "a.md", "# Beta\n")
            beta = parse_markdown(original, root)
            self.assertNotEqual(original_heading_id, beta["headings"][0]["heading_id"])

            renamed = root / "b.md"
            original.rename(renamed)
            moved = parse_markdown(renamed, root)
            self.assertNotEqual(original_doc_id, moved["document_id"])
            self.assertNotEqual(beta["headings"][0]["heading_id"], moved["headings"][0]["heading_id"])


class TrackedDiscoveryTests(unittest.TestCase):
    """Repository identity must not depend on machine-local untracked files."""

    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        )

    def _repo(self, root: Path) -> None:
        # Empty --template keeps any machine-local hook template out of the fixture,
        # and staging alone is enough: git ls-files reads the index, so these tests
        # never need a commit (and never depend on a committer identity).
        self._git(root, "init", "-q", "--template=")

    def test_untracked_and_ignored_markdown_is_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            (root / "tracked.md").write_text("# Tracked\n", encoding="utf-8")
            (root / "ignored").mkdir()
            (root / "ignored" / "local.md").write_text("# Local\n", encoding="utf-8")
            (root / "untracked.md").write_text("# Untracked\n", encoding="utf-8")
            self._git(root, "add", ".gitignore", "tracked.md")

            paths = {document["path"] for document in build_index(root)["documents"]}

            self.assertIn("tracked.md", paths)
            self.assertNotIn("ignored/local.md", paths)
            self.assertNotIn("untracked.md", paths)

    def test_index_is_stable_when_untracked_output_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "tracked.md").write_text("# Tracked\n", encoding="utf-8")
            self._git(root, "add", "tracked.md")

            before = serialize_index(build_index(root))
            cache = root / ".pytest_cache"
            cache.mkdir()
            (cache / "README.md").write_text("# Cache\n", encoding="utf-8")

            self.assertEqual(before, serialize_index(build_index(root)))

    def test_outside_a_git_work_tree_every_markdown_file_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("# A\n", encoding="utf-8")

            self.assertIsNone(tracked_relative_paths(root))
            self.assertEqual(
                {document["path"] for document in build_index(root)["documents"]},
                {"a.md"},
            )


if __name__ == "__main__":
    unittest.main()
