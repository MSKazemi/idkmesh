"""Guard the documentation directory indexes against silent coverage drift.

`docs/conversations/` already has an exhaustive-index guard. The same defect
class reached the curated directory indexes: five documents were added to
`docs/specifications/` and `docs/research/` after their indexes were written and
were never linked from them.

The IDKGraph observatory cannot detect this. It reports a document only when
*no* inbound Markdown link exists anywhere, so a document that is linked from
some unrelated page but missing from its own directory index stays invisible to
the deterministic health checks. This test closes exactly that blind spot.

A directory is listed here only when its index claims to cover the whole
directory. Adding a directory is a deliberate act; collections where
category-level discoverability is sufficient stay out.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Directories whose README.md is an exhaustive index of that directory.
EXHAUSTIVELY_INDEXED_DIRECTORIES = (
    "docs/architecture",
    "docs/audits",
    "docs/community",
    # Added with docs/decisions/README.md. The ADRs are the repository's
    # canonical current authority -- docs/findings/README.md defers to them by
    # name -- and were the last authority surface with no index of their own.
    "docs/decisions",
    "docs/findings",
    "docs/research",
    "docs/specifications",
    # Added after an audit found 21 experiment records with 3 linked from their
    # own index. A record nobody can navigate to is a published result nobody
    # reads, which on a public research repository is the whole cost.
    "experiments",
)

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")


def _documents(directory: Path) -> set[Path]:
    """Every Markdown document the index is expected to cover."""
    return {
        path.resolve()
        for path in directory.rglob("*.md")
        if path.name != "README.md"
    }


def _linked_inside(index: Path, directory: Path) -> list[Path]:
    """Index link targets that resolve inside the indexed directory.

    Links pointing outside the directory are legitimate cross-references and are
    deliberately ignored; only intra-directory coverage is asserted here.
    """
    text = index.read_text(encoding="utf-8")
    inside = []
    for target in MARKDOWN_LINK.findall(text):
        resolved = (index.parent / target).resolve()
        if resolved.is_relative_to(directory.resolve()):
            inside.append(resolved)
    return inside


class DocumentationDirectoryIndexTests(unittest.TestCase):
    def test_every_indexed_directory_has_an_index(self) -> None:
        for relative in EXHAUSTIVELY_INDEXED_DIRECTORIES:
            with self.subTest(directory=relative):
                index = ROOT / relative / "README.md"
                self.assertTrue(
                    index.is_file(),
                    f"{relative}/README.md is declared an exhaustive index but "
                    f"does not exist",
                )

    def test_every_document_is_linked_from_its_directory_index(self) -> None:
        for relative in EXHAUSTIVELY_INDEXED_DIRECTORIES:
            with self.subTest(directory=relative):
                directory = ROOT / relative
                linked = set(_linked_inside(directory / "README.md", directory))
                missing = sorted(
                    path.relative_to(directory).as_posix()
                    for path in _documents(directory) - linked
                )
                self.assertEqual(
                    missing,
                    [],
                    f"{relative}/README.md claims to index the whole directory "
                    f"but does not link: {missing}",
                )

    def test_no_index_links_a_document_that_does_not_exist(self) -> None:
        for relative in EXHAUSTIVELY_INDEXED_DIRECTORIES:
            with self.subTest(directory=relative):
                directory = ROOT / relative
                dangling = sorted(
                    path.relative_to(directory).as_posix()
                    for path in set(_linked_inside(directory / "README.md", directory))
                    - _documents(directory)
                )
                self.assertEqual(
                    dangling,
                    [],
                    f"{relative}/README.md links documents that do not exist: "
                    f"{dangling}",
                )

    def test_no_document_is_linked_more_than_once(self) -> None:
        for relative in EXHAUSTIVELY_INDEXED_DIRECTORIES:
            with self.subTest(directory=relative):
                directory = ROOT / relative
                linked = _linked_inside(directory / "README.md", directory)
                duplicates = sorted(
                    {
                        path.relative_to(directory).as_posix()
                        for path in linked
                        if linked.count(path) > 1
                    }
                )
                self.assertEqual(
                    duplicates,
                    [],
                    f"{relative}/README.md links these documents more than "
                    f"once: {duplicates}",
                )


if __name__ == "__main__":
    unittest.main()
