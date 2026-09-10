"""Keep the repository asset guard and its original assertions on shared code.

The complementary asset resolver now lives in scripts/check_links.py, which
combines it with the unchanged T2 Markdown/anchor checker for local and CI use.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.check_links import (
    classify_link,
    collect_local_non_markdown_links,
    tracked_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Retain the original non-vacuity floor; extraction must not hide lost coverage.
MINIMUM_SCANNED_LINKS = 40


class LocalAssetLinkIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.links = collect_local_non_markdown_links(REPO_ROOT)

    def test_every_local_non_markdown_target_resolves(self) -> None:
        missing = [item for item in self.links if item[3] == "missing"]
        self.assertEqual(
            [],
            [f"{path}:{line} -> {target}" for path, line, target, _ in missing],
            "Markdown link points at a repository path that does not exist.",
        )

    def test_no_link_escapes_the_tree_except_github_routes(self) -> None:
        escaping = [item for item in self.links if item[3] == "escapes"]
        self.assertEqual(
            [],
            [f"{path}:{line} -> {target}" for path, line, target, _ in escaping],
            "Link resolves outside the repository and is not a GitHub route.",
        )

    def test_scan_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            len(self.links),
            MINIMUM_SCANNED_LINKS,
            "Too few links scanned; link extraction is probably broken.",
        )


class ClassifyLinkTests(unittest.TestCase):
    """The classifier itself, on explicit path sets, independent of any repository."""

    def test_existing_file_and_directory_targets_resolve(self) -> None:
        known = frozenset({"docs", "docs/a.md", "scripts", "scripts/run.py"})
        root = Path("/repo")
        self.assertEqual(classify_link(root, "docs/a.md", "../scripts/run.py", known), "exists")
        self.assertEqual(classify_link(root, "docs/a.md", "../scripts", known), "exists")

    def test_missing_file_and_directory_targets_are_reported(self) -> None:
        known = frozenset({"docs", "docs/a.md"})
        root = Path("/repo")
        self.assertEqual(classify_link(root, "docs/a.md", "../evolution", known), "missing")
        self.assertEqual(classify_link(root, "docs/a.md", "../scripts/gone.py", known), "missing")

    def test_untracked_path_is_missing_even_when_it_exists_on_disk(self) -> None:
        """A generated or ignored path is absent from a fresh checkout, so it must not pass."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
            (root / "generated").mkdir()
            (root / "generated" / "out.json").write_text("{}", encoding="utf-8")
            self.assertTrue((root / "generated" / "out.json").is_file())
            known = frozenset({"docs", "docs/a.md"})  # index does not carry generated/
            self.assertEqual(
                classify_link(root, "docs/a.md", "../generated/out.json", known), "missing"
            )

    def test_repository_root_is_a_valid_target(self) -> None:
        """Docs link to the repository root as `..`; the root has no index entry."""

        known = frozenset({"docs", "docs/a.md"})
        self.assertEqual(classify_link(Path("/repo"), "docs/a.md", "..", known), "exists")

    def test_github_routes_are_not_treated_as_paths(self) -> None:
        known = frozenset({"docs", "docs/a.md"})
        root = Path("/repo")
        self.assertEqual(classify_link(root, "docs/a.md", "../../issues/24", known), "github_route")
        self.assertEqual(classify_link(root, "docs/a.md", "../../pulls", known), "github_route")

    def test_unrecognised_escape_is_not_excused(self) -> None:
        known = frozenset({"docs", "docs/a.md"})
        root = Path("/repo")
        self.assertEqual(classify_link(root, "docs/a.md", "../../etc/passwd", known), "escapes")


class TrackedPathsTests(unittest.TestCase):
    def test_tracked_paths_includes_implied_directories(self) -> None:
        known = tracked_paths(REPO_ROOT)
        self.assertIn("tools/idkgraph_link_check.py", known)
        self.assertIn("tools", known)
        self.assertIn("docs", known)
        self.assertNotIn(".venv", known)


if __name__ == "__main__":
    unittest.main()
