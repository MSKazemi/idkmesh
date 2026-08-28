from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.idkgraph_link_check import check_links, serialize_report
from tools.idkgraph_markdown_index import build_index


class IDKGraphLinkCheckTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_links_bind_to_canonical_t1_identities(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write(
                root,
                "docs/a.md",
                """# Alpha\n\n"
                "[Cross doc](b.md#café)\n"
                "[Same doc duplicate](#repeat-1)\n"
                "[Setext target](b.md#setext-title)\n"
                "[Issue route](../../issues/24)\n"
                "[External](https://example.com/x)\n"
                "`[Inline code is not a link](missing.md)`\n\n"
                "## Repeat\n"
                "## Repeat\n"
                """,
            )
            self.write(
                root,
                "docs/b.md",
                """# Café\n\nSetext Title\n------------\n""",
            )

            report = check_links(root)
            self.assertEqual(report["identity_contract"], "idkgraph-markdown-index-v0.1")
            self.assertEqual(report["summary"]["errors"], 0)
            self.assertEqual(report["summary"]["warnings"], 0)
            self.assertEqual(report["summary"]["resolved_local_markdown_links"], 3)
            self.assertEqual(report["summary"]["ignored_external_links"], 1)
            self.assertEqual(report["summary"]["ignored_non_markdown_links"], 1)

            t1 = build_index(root)
            docs = {item["path"]: item for item in t1["documents"]}
            b_headings = {item["text"]: item["heading_id"] for item in docs["docs/b.md"]["headings"]}
            a_repeat_ids = [
                item["heading_id"]
                for item in docs["docs/a.md"]["headings"]
                if item["text"] == "Repeat"
            ]

            resolved = {item["raw_target"]: item for item in report["resolved_links"]}
            self.assertEqual(resolved["b.md#café"]["target_heading_id"], b_headings["Café"])
            self.assertEqual(
                resolved["b.md#setext-title"]["target_heading_id"],
                b_headings["Setext Title"],
            )
            self.assertEqual(
                resolved["#repeat-1"]["target_heading_id"],
                a_repeat_ids[1],
            )
            self.assertEqual(
                resolved["#repeat-1"]["source_document_id"],
                docs["docs/a.md"]["document_id"],
            )

    def test_missing_file_anchor_escape_and_absolute_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            root.mkdir()
            self.write(
                root,
                "docs/a.md",
                """# A\n\n"
                "[Missing](missing.md)\n"
                "[Bad anchor](b.md#does-not-exist)\n"
                "[Escape](../../escape.md)\n"
                "[Ambiguous absolute](/README.md)\n"
                """,
            )
            self.write(root, "docs/b.md", "# B\n")
            self.write(root, "README.md", "# Root\n")

            report = check_links(root)
            categories = [item["category"] for item in report["findings"]]
            self.assertEqual(report["summary"]["errors"], 3)
            self.assertEqual(report["summary"]["warnings"], 1)
            self.assertIn("missing_markdown_file", categories)
            self.assertIn("missing_markdown_anchor", categories)
            self.assertIn("target_escapes_repository", categories)
            self.assertIn("repository_absolute_markdown_link", categories)

    def test_fragment_only_link_resolves_to_t1_heading_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write(root, "README.md", "# Hello World\n\n[Jump](#hello-world)\n")

            report = check_links(root)
            t1 = build_index(root)
            heading_id = t1["documents"][0]["headings"][0]["heading_id"]
            self.assertEqual(report["summary"]["errors"], 0)
            self.assertEqual(report["resolved_links"][0]["target_heading_id"], heading_id)

    def test_fenced_and_inline_code_do_not_create_false_links(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write(
                root,
                "README.md",
                """# Code\n\n"
                "```markdown\n"
                "[Fake](missing.md)\n"
                "```\n\n"
                "`[Also fake](missing.md)`\n"
                """,
            )

            report = check_links(root)
            self.assertEqual(report["summary"]["links_seen"], 0)
            self.assertEqual(report["summary"]["errors"], 0)

    def test_report_is_byte_deterministic_for_same_tree(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write(root, "a.md", "# A\n\n[B](b.md#b)\n")
            self.write(root, "b.md", "# B\n")

            first = serialize_report(check_links(root))
            second = serialize_report(check_links(root))
            self.assertEqual(first, second)
            self.assertEqual(json.loads(first), json.loads(second))

    def test_authority_boundary_is_read_only_and_identity_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write(root, "README.md", "# A\n")
            report = check_links(root)
            self.assertEqual(
                report["authority"],
                {
                    "repository_write": False,
                    "github_mutation": False,
                    "semantic_inference": False,
                    "identity_definition": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
