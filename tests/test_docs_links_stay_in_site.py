"""Guard: a relative link in ``docs/`` must not resolve outside ``docs/``.

The GitHub Pages site is built from ``main:/docs`` with ``jekyll-relative-links``.
That plugin rewrites a relative link to a Markdown file *inside the site source*
into the rendered page's URL. A relative link whose target lies outside
``docs/`` is left untouched, so the browser resolves it against the page URL
and walks off the project site entirely::

    docs/research/README.md   [..](../../paper/README.md)
    published at              https://mskazemi.com/idkmesh/research/README.html
    resolves to               https://mskazemi.com/paper/README.md   -> HTTP 404

The same link works when the file is read on GitHub, which is why every other
gate stays green: IDKGraph T2 and ``scripts/check_links.py`` resolve against the
repository tree, where the target exists. Only the published site breaks.

A link to anything outside the site must therefore be absolute, normally
``https://github.com/MSKazemi/idkmesh/blob/main/<path>`` (or ``tree/main/`` for a
directory). This module fails on any relative ``href``/``src``/Markdown link
destination in ``docs/**/*.md`` or ``docs/**/*.html`` that escapes ``docs/``.

Scope and deliberate simplifications:

* Fenced code blocks, inline code spans and HTML comments are not rendered as
  links, so they are skipped.
* Files under an underscore-prefixed directory (``docs/_layouts``) are Jekyll
  templates, not pages: their relative links resolve against whichever page
  uses them, so a file-relative check would be meaningless there.
* Existence is not checked here — ``scripts/check_links.py`` and
  ``tests/test_pages_site_links.py`` own that. This module answers one question
  only: does the link stay on the site? It reads files directly and starts no
  subprocess, to stay cheap in the unit tier.
"""

from __future__ import annotations

from pathlib import Path
import posixpath
import re
import unittest
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# `](dest` anywhere on a line: catches plain links, images, and the outer link of
# a linked image (`[![alt](img)](dest)`), which a `[text](dest)` pattern misses.
INLINE_LINK_RE = re.compile(r"\]\(\s*(<[^>\n]*>|[^)\s]+)")
REFERENCE_DEF_RE = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(<[^>\n]*>|\S+)", re.MULTILINE)
HTML_ATTR_RE = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)

# A broken extractor that scans nothing would pass the escape assertion
# vacuously. Measured at 961 relative destinations when written (1,117 before
# the 156 escaping ones were made absolute). The floor only has to catch an
# extractor that returns nothing, not freeze the count.
MINIMUM_SCANNED_LINKS = 500


def _strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks, keeping line numbers stable."""

    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in text.split("\n"):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_len = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                fence_char, fence_len = None, 0
            out.append("")
            continue
        out.append("" if fence_char is not None else line)
    return "\n".join(out)


def _blank_keep_lines(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def iter_destinations(text: str, *, markdown: bool) -> list[tuple[int, str]]:
    """Return ``(line, destination)`` for every link a renderer would emit."""

    if markdown:
        text = _strip_fenced_blocks(text)
    text = HTML_COMMENT_RE.sub(_blank_keep_lines, text)
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.split("\n"), 1):
        if markdown:
            line = INLINE_CODE_RE.sub("", line)
            for match in INLINE_LINK_RE.finditer(line):
                found.append((number, match.group(1).strip("<>").strip()))
        for match in HTML_ATTR_RE.finditer(line):
            found.append((number, (match.group(1) or match.group(2) or "").strip()))
    if markdown:
        for match in REFERENCE_DEF_RE.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            found.append((number, match.group(1).strip("<>").strip()))
    return found


def resolve_relative(source: str, destination: str) -> str | None:
    """Repository path a relative destination resolves to, or ``None`` if not relative.

    ``source`` is the linking file's repository path (``docs/x/y.md``). The
    result is normalised; a result starting with ``..`` lies above the
    repository root.
    """

    if not destination or destination.startswith("#"):
        return None
    if "{{" in destination or "{%" in destination:  # Liquid, resolved at build time
        return None
    parts = urlsplit(destination)
    if parts.scheme or parts.netloc or destination.startswith("//"):
        return None
    path = unquote(parts.path)
    if not path:
        return None
    if path.startswith("/"):
        # Root-absolute on the Pages host: on-site only under the project base.
        return "docs/" + path[len("/idkmesh/"):] if path.startswith("/idkmesh/") else ".." + path
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))


def is_outside_docs(resolved: str) -> bool:
    return not (resolved == "docs" or resolved.startswith("docs/"))


def site_files(docs: Path = DOCS) -> list[Path]:
    """Markdown and HTML files Jekyll publishes as pages, excluding templates."""

    files: list[Path] = []
    for suffix in ("*.md", "*.html"):
        for path in docs.rglob(suffix):
            relative = path.relative_to(docs)
            if any(part.startswith("_") for part in relative.parts[:-1]):
                continue
            files.append(path)
    return sorted(files)


def scan(root: Path = REPO_ROOT) -> tuple[int, list[tuple[str, int, str, str]]]:
    """Return ``(relative links scanned, escaping links)``.

    Each escaping entry is ``(source, line, destination, resolved_path)``.
    """

    scanned = 0
    escaping: list[tuple[str, int, str, str]] = []
    for path in site_files(root / "docs"):
        source = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for line, destination in iter_destinations(text, markdown=path.suffix == ".md"):
            resolved = resolve_relative(source, destination)
            if resolved is None:
                continue
            scanned += 1
            if is_outside_docs(resolved):
                escaping.append((source, line, destination, resolved))
    return scanned, escaping


class DocsLinksStayInSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scanned, cls.escaping = scan()

    def test_no_relative_link_escapes_the_site(self) -> None:
        self.assertEqual(
            [],
            [f"{src}:{line} -> {dest}  (resolves to {res})" for src, line, dest, res in self.escaping],
            "A relative link in docs/ resolves outside docs/, so the Pages site "
            "publishes it as a 404. Use https://github.com/MSKazemi/idkmesh/blob/main/<path> "
            "(tree/main/ for a directory).",
        )

    def test_scan_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            self.scanned,
            MINIMUM_SCANNED_LINKS,
            "Too few relative links scanned; link extraction is probably broken.",
        )


class ExtractorTests(unittest.TestCase):
    """The extractor and resolver on explicit inputs, independent of the tree."""

    def test_inline_reference_and_html_links_are_found(self) -> None:
        text = (
            "See [a](../x.md#h) and [![b](img.png)](../../y/) here.\n"
            "[ref]: ../../z.py\n"
            '<a href="../w.md">w</a> <img src=\'pic.svg\'>\n'
        )
        self.assertEqual(
            sorted(dest for _, dest in iter_destinations(text, markdown=True)),
            sorted(["../x.md#h", "img.png", "../../y/", "../../z.py", "../w.md", "pic.svg"]),
        )

    def test_code_and_comments_are_skipped(self) -> None:
        text = (
            "```bash\n[a](../../in-fence.md)\n```\n"
            "`[b](../../in-code.md)` and <!-- [c](../../in-comment.md) -->\n"
            "~~~\n<a href=\"../../tilde.md\">\n~~~\n"
            "[d](kept.md)\n"
        )
        self.assertEqual(
            iter_destinations(text, markdown=True), [(8, "kept.md")]
        )

    def test_resolution_classifies_escapes(self) -> None:
        self.assertEqual(resolve_relative("docs/r/README.md", "../../paper/README.md"), "paper/README.md")
        self.assertTrue(is_outside_docs(resolve_relative("docs/README.md", "../README.md")))
        self.assertFalse(is_outside_docs(resolve_relative("docs/r/a.md", "../b.md#x")))
        self.assertFalse(is_outside_docs(resolve_relative("docs/r/a.md", "..")))
        self.assertTrue(is_outside_docs(resolve_relative("docs/a.md", "/paper/")))
        self.assertFalse(is_outside_docs(resolve_relative("docs/a.md", "/idkmesh/start.html")))
        for absolute in ("https://x.org/a", "mailto:a@b.c", "#frag", "//cdn/x.js", "{{ '/a' | relative_url }}"):
            self.assertIsNone(resolve_relative("docs/a.md", absolute))


if __name__ == "__main__":
    unittest.main()
