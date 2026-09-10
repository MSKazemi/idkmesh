"""Guard: the GitHub Pages site's own links, which no other gate resolves.

The published site is ``main:/docs``, and its hand-written HTML pages are the
project's first-contact surface. Nothing checked them before this module:

* IDKGraph T2 (``tools/idkgraph_link_check.py``) reads Markdown only, so it
  never opens an ``.html`` file;
* ``tests/test_local_asset_link_integrity.py`` closes T2's non-Markdown hole,
  but only for links *written inside Markdown documents*;
* ``tools/idkgraph_health_checks.py`` scans an allowlist of artifact suffixes
  that deliberately excludes ``.html``.

So a site page could link to a deleted document, drop its stylesheet, or grow a
navigation bar that disagrees with its siblings, and every gate would stay
green. This module resolves those links instead.

Three link kinds are checked:

``assets/site.css``, ``start.html``      page-relative, must exist under ``docs/``
``#main``                                a fragment, whose ``id`` must exist on the page
``.../blob/main/README.md``              a repository file, which must be tracked

Resolution is against the git **index**, not the filesystem, for the same
reason ``test_local_asset_link_integrity`` gives: an untracked file exists on a
developer machine and not in a fresh CI checkout, and a link to one must not
pass locally and fail the gate.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

SITE_ORIGIN = "https://mskazemi.com/idkmesh"
BLOB_PREFIX = "https://github.com/MSKazemi/idkmesh/blob/main/"
TREE_PREFIX = "https://github.com/MSKazemi/idkmesh/tree/main/"

# The stylesheet every page shares. Named here so that dropping the link from
# one page is a test failure rather than an unstyled page discovered in public.
SHARED_STYLESHEET = "assets/site.css"

# Liquid's delimiters. GitHub Pages runs Jekyll over this directory, and Liquid
# expands these *before* Markdown or anything else sees the file — so a fenced
# code block does not protect them, and neither does an HTML comment. One
# unterminated Actions interpolation copied into a documented workflow snippet
# took the whole site build down for six consecutive builds on 2026-09-09/10,
# `7307b41` through `c798726`; the failure is global, not scoped to the page.
# This file writes the delimiters freely, in the constant and in a docstring
# below, because `tests/` is outside `docs/` and Pages never processes it.
# `docs/PAGES_SETUP.md` documents the same failure without writing them once,
# because a file Jekyll *does* read cannot afford to.
LIQUID_DELIMITERS = ("{{", "{%")

# A broken extractor that scans nothing would otherwise pass every assertion
# below. Measured at 520 in-page links across the six site pages when written.
# The floor sits well under that: it exists to catch an extractor returning
# nothing, not to freeze the link count, which legitimately moves as the
# library follows the tree.
MINIMUM_SCANNED_LINKS = 300


class _Extractor(HTMLParser):
    """Collect hrefs, element ids, stylesheet links and canonical URLs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.stylesheets: list[str] = []
        self.canonical: str | None = None
        self.has_inline_style = False
        self.nav_hrefs: list[str] = []
        self._nav_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if "id" in attr:
            self.ids.add(attr["id"])
        if tag == "nav" and "sitenav" in attr.get("class", ""):
            self._nav_depth = 1
        elif self._nav_depth:
            # Nested elements inside the nav; <nav> is never nested here.
            self._nav_depth += 1
        if tag == "link":
            rel = attr.get("rel", "").lower()
            if rel == "stylesheet":
                self.stylesheets.append(attr.get("href", ""))
            elif rel == "canonical":
                self.canonical = attr.get("href", "")
        if tag == "style":
            self.has_inline_style = True
        if tag == "a" and "href" in attr:
            self.hrefs.append(attr["href"])
            if self._nav_depth:
                self.nav_hrefs.append(attr["href"])

    def handle_endtag(self, tag: str) -> None:
        if self._nav_depth:
            self._nav_depth -= 1


def tracked_paths(root: Path) -> frozenset[str]:
    """Every tracked file plus every directory implied by one."""

    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    known: set[str] = set()
    for entry in listed.split("\0"):
        if not entry:
            continue
        known.add(entry)
        known.update(str(parent) for parent in Path(entry).parents if str(parent) != ".")
    return frozenset(known)


def site_pages(docs: Path) -> list[Path]:
    return sorted(docs.glob("*.html"))


def parse(page: Path) -> _Extractor:
    extractor = _Extractor()
    extractor.feed(page.read_text(encoding="utf-8"))
    return extractor


def classify(page: Path, href: str, known: frozenset[str]) -> tuple[str, str]:
    """Return ``(verdict, resolved)`` for one href on ``page``.

    Verdicts: ``ok``, ``external``, ``missing``, ``escapes``, ``bad_fragment``.
    A fragment is resolved on the page it names, same-document or not.
    """

    if href.startswith(BLOB_PREFIX) or href.startswith(TREE_PREFIX):
        prefix = BLOB_PREFIX if href.startswith(BLOB_PREFIX) else TREE_PREFIX
        target = unquote(urlsplit(href[len(prefix):]).path).rstrip("/")
        if target not in known:
            return "missing", target
        is_dir = not (REPO_ROOT / target).is_file()
        if prefix is BLOB_PREFIX and is_dir:
            return "missing", f"{target} (a directory; use /tree/main/)"
        if prefix is TREE_PREFIX and not is_dir:
            return "missing", f"{target} (a file; use /blob/main/)"
        return "ok", target

    split = urlsplit(href)
    if split.scheme or split.netloc:
        return "external", href

    path_text = unquote(split.path)
    if not path_text:
        # Same-document fragment: the id has to be on this page.
        if split.fragment and split.fragment not in parse(page).ids:
            return "bad_fragment", split.fragment
        return "ok", href

    target = (page.parent / path_text).resolve()
    try:
        resolved = str(target.relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return "escapes", path_text
    if resolved == ".":
        return "ok", resolved
    # A directory link such as "./" resolves to docs/ itself.
    if resolved not in known:
        return "missing", resolved
    # A fragment on another *site* page is resolvable, so resolve it: a
    # renamed section id is exactly the kind of rot that reaches a reader as a
    # link that silently lands at the top of the wrong page.
    if split.fragment and target.suffix == ".html" and target.is_file():
        if split.fragment not in parse(target).ids:
            return "bad_fragment", f"{resolved}#{split.fragment}"
    return "ok", resolved


class PagesSiteLinkTests(unittest.TestCase):
    """Every link written into a published site page must resolve."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.known = tracked_paths(REPO_ROOT)
        cls.pages = site_pages(DOCS)
        cls.parsed = {page.name: parse(page) for page in cls.pages}
        cls.links = [
            (page.name, href) + classify(page, href, cls.known)
            for page in cls.pages
            for href in cls.parsed[page.name].hrefs
        ]

    def test_the_site_has_pages_to_check(self) -> None:
        self.assertGreaterEqual(len(self.pages), 2, "docs/ has no published HTML pages.")

    def test_every_page_relative_link_resolves(self) -> None:
        broken = [f"{name}: {href} -> {resolved}"
                  for name, href, verdict, resolved in self.links if verdict == "missing"]
        self.assertEqual([], broken, "Site page links at a path that is not tracked.")

    def test_no_link_escapes_the_repository(self) -> None:
        escaping = [f"{name}: {href}"
                    for name, href, verdict, _ in self.links if verdict == "escapes"]
        self.assertEqual([], escaping, "Site page link resolves outside the repository.")

    def test_every_fragment_target_exists(self) -> None:
        dangling = [f"{name}: {href}"
                    for name, href, verdict, _ in self.links if verdict == "bad_fragment"]
        self.assertEqual([], dangling, "Site page links to an id that no page carries.")

    def test_scan_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            len(self.links),
            MINIMUM_SCANNED_LINKS,
            "Too few links scanned; the HTML extractor is probably broken.",
        )


class PagesSiteConsistencyTests(unittest.TestCase):
    """The navigation and stylesheet are duplicated per page, so pin them.

    The site has no build step and no template engine on purpose, which means
    the navigation bar is copied into each page by hand. That is the honest
    cost of the no-JavaScript, no-framework constraint in docs/PAGES_SETUP.md —
    and it is only safe if divergence is a test failure.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = site_pages(DOCS)
        cls.parsed = {page.name: parse(page) for page in cls.pages}

    def test_every_page_carries_the_shared_navigation(self) -> None:
        missing = [name for name, doc in self.parsed.items() if not doc.nav_hrefs]
        self.assertEqual([], missing, "Site page has no shared navigation bar.")

    def test_navigation_is_identical_across_pages(self) -> None:
        seen = {name: tuple(doc.nav_hrefs) for name, doc in self.parsed.items()}
        distinct = set(seen.values())
        self.assertEqual(
            1,
            len(distinct),
            f"Navigation bars disagree across pages: {seen}",
        )

    def test_navigation_reaches_every_published_page(self) -> None:
        any_nav = next(iter(self.parsed.values())).nav_hrefs
        # "./" is index.html; every other page is named directly.
        reachable = {"index.html" if href == "./" else href for href in any_nav}
        unreachable = sorted(
            page.name for page in self.pages if page.name not in reachable
        )
        self.assertEqual(
            [],
            unreachable,
            "A published page is not reachable from the site navigation.",
        )

    def test_every_page_is_styled(self) -> None:
        """Either the shared sheet or its own inline one — never nothing.

        ``pipelines.html`` predates the shared stylesheet and keeps its rules
        inline, because its diagram primitives are the page. That is allowed;
        loading no styling at all is not, because the failure is invisible
        locally and total in public.
        """

        unstyled = [
            name for name, doc in self.parsed.items()
            if not doc.stylesheets and not doc.has_inline_style
        ]
        self.assertEqual([], unstyled, "Site page carries no styling at all.")

    def test_any_linked_stylesheet_is_the_shared_one(self) -> None:
        """A second stylesheet would be a second design system by the back door."""

        unexpected = [
            f"{name}: {href}"
            for name, doc in self.parsed.items()
            for href in doc.stylesheets
            if href != SHARED_STYLESHEET
        ]
        self.assertEqual([], unexpected, "Site page links a stylesheet other than the shared one.")

    def test_every_page_declares_its_canonical_url(self) -> None:
        """Jekyll gives rendered Markdown a canonical URL; these pages must carry their own."""

        wrong = []
        for page in self.pages:
            expected = (
                f"{SITE_ORIGIN}/" if page.name == "index.html"
                else f"{SITE_ORIGIN}/{page.name}"
            )
            actual = self.parsed[page.name].canonical
            if actual != expected:
                wrong.append(f"{page.name}: {actual!r} != {expected!r}")
        self.assertEqual([], wrong, "Site page has a missing or incorrect canonical URL.")

    def test_no_page_loads_an_external_asset(self) -> None:
        """docs/PAGES_SETUP.md forbids external fonts, scripts and trackers here."""

        external = [
            f"{name}: {href}"
            for name, doc in self.parsed.items()
            for href in doc.stylesheets
            if urlsplit(href).netloc
        ]
        self.assertEqual([], external, "Site page loads a stylesheet from another origin.")

    def test_no_page_contains_a_liquid_delimiter(self) -> None:
        """A stray `{{` or `{%` anywhere in these files kills the whole site build.

        Scanned here because the Markdown-side guard cannot see them: these are
        `.html` and `.css`, and Jekyll's failure mode is the entire deployment,
        not one page. The usual way in is pasting a GitHub Actions snippet —
        `${{ github.event_name ... }}` — into an example block.
        """

        offenders = []
        for path in [*self.pages, DOCS / SHARED_STYLESHEET]:
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for delimiter in LIQUID_DELIMITERS:
                    if delimiter in line:
                        offenders.append(f"{path.name}:{number} contains {delimiter!r}")
        self.assertEqual(
            [],
            offenders,
            "Liquid delimiter in a published site file; Jekyll would fail the whole build.",
        )

    def test_no_page_contains_a_script_element(self) -> None:
        """The no-JavaScript constraint, enforced rather than documented."""

        offenders = []
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            for marker in ("<script", "onclick=", "onload=", "javascript:"):
                if marker == "<script":
                    # Structured data is a <script type="application/ld+json">
                    # block: inert data, never executed.
                    executable = text.count("<script") - text.count(
                        '<script type="application/ld+json">'
                    )
                    if executable > 0:
                        offenders.append(f"{page.name}: {executable} executable <script>")
                elif marker in text:
                    offenders.append(f"{page.name}: {marker}")
        self.assertEqual([], offenders, "Site page contains JavaScript.")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
