import json
import tempfile
import unittest
from pathlib import Path

from tools.idkgraph_markdown_index import build_index, parse_markdown, serialize_index


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


if __name__ == "__main__":
    unittest.main()
