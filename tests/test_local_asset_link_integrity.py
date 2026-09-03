"""Guard: repository-local links to non-Markdown targets must resolve.

``tools/idkgraph_link_check.py`` (IDKGraph T2) deliberately validates only
Markdown-file and fragment targets -- every other local destination is counted
as ``ignored_non_markdown_links`` and never resolved. That scope is part of the
T2 contract and is not changed here. The consequence, however, is that a link to
a directory, script, schema, or image can rot without any gate noticing: the
PR Gate's link leg reports zero findings for it.

This guard closes that hole from the outside. It resolves exactly the links T2
ignores and asserts each one either exists in the working tree or is a GitHub
repository-relative navigation route (``../../issues/24`` and friends), which is
a real link on github.com rather than a path in the tree.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

from tools.idkgraph_link_check import is_external, iter_inline_links
from tools.idkgraph_markdown_index import build_index

REPO_ROOT = Path(__file__).resolve().parents[1]

# Seeded negative fixtures are intentionally broken, exactly as the PR Gate's
# own link leg excludes them from its finding count.
EXCLUDED_PREFIXES = ("tests/fixtures/",)

# First path segment of a GitHub repository-relative route. A link such as
# ``../../issues/24`` from ``docs/index.md`` escapes the working tree by design:
# GitHub resolves it against the repository URL, not the file system.
GITHUB_ROUTES = frozenset(
    {
        "issues",
        "pull",
        "pulls",
        "discussions",
        "wiki",
        "blob",
        "tree",
        "raw",
        "actions",
        "releases",
        "tags",
        "labels",
        "milestones",
        "projects",
        "security",
        "compare",
        "commits",
        "commit",
    }
)

# Measured on 31b8f18: 58 local non-Markdown links across the tracked Markdown
# set. The floor exists so that a broken extractor cannot make this guard pass
# by scanning nothing at all.
MINIMUM_SCANNED_LINKS = 40


def _github_route(path_text: str) -> str | None:
    """Return the route namespace if ``path_text`` is a GitHub repo-relative route."""

    segments = [segment for segment in path_text.split("/") if segment not in ("", ".")]
    while segments and segments[0] == "..":
        segments.pop(0)
    if segments and segments[0] in GITHUB_ROUTES:
        return segments[0]
    return None


def tracked_paths(root: Path) -> frozenset[str]:
    """Every tracked file plus every directory implied by one.

    Resolution is deliberately against the *index*, not the filesystem. A
    generated or ignored path exists on a developer machine and not in a fresh
    CI checkout, so a filesystem check would let a link to one pass locally and
    fail the gate — the "green locally, red in CI" split this repository has
    already been bitten by once.
    """

    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    known: set[str] = set()
    for entry in listed.split("\0"):
        if not entry:
            continue
        known.add(entry)
        known.update(str(parent) for parent in Path(entry).parents if str(parent) != ".")
    return frozenset(known)


def classify_link(root: Path, source_path: str, raw_target: str, known: frozenset[str] | None = None) -> str:
    """Classify one repository-local, non-Markdown link target.

    Returns ``"exists"``, ``"github_route"``, ``"missing"``, or ``"escapes"``.
    """

    if known is None:
        known = tracked_paths(root)
    path_text = unquote(urlsplit(raw_target).path)
    route = _github_route(path_text)
    target = (root / source_path).parent / path_text
    try:
        resolved = str(target.resolve().relative_to(root.resolve()))
    except ValueError:
        return "github_route" if route else "escapes"
    # "." is the repository root itself — a legitimate target (docs/index.md
    # links to it) that no index entry can name.
    if resolved == ".":
        return "exists"
    if route and resolved not in known:
        return "github_route"
    return "exists" if resolved in known else "missing"


def collect_local_non_markdown_links(root: Path) -> list[tuple[str, int, str, str]]:
    """Every link T2 skips, with its verdict: ``(source, line, target, verdict)``."""

    results: list[tuple[str, int, str, str]] = []
    known = tracked_paths(root)
    for document in build_index(root)["documents"]:
        source_path = document["path"]
        if source_path.startswith(EXCLUDED_PREFIXES):
            continue
        for line, raw_target in iter_inline_links(root / source_path):
            if is_external(raw_target):
                continue
            path_text = unquote(urlsplit(raw_target).path)
            # No path means a same-document fragment; ``.md`` targets are T2's job.
            if not path_text or path_text.lower().endswith(".md"):
                continue
            if path_text.startswith("/"):
                # Repository-absolute; T2 already warns about these separately.
                continue
            results.append(
                (source_path, line, raw_target, classify_link(root, source_path, path_text, known))
            )
    return results


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
        """docs/index.md carries `[Main repository](..)`; the root has no index entry."""

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
