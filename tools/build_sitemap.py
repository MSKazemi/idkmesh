#!/usr/bin/env python3
"""Generate `docs/sitemap.xml` from the published documentation tree.

GitHub Pages serves `docs/` with legacy Jekyll and the default theme, so every
Markdown document under `docs/` is rendered to an HTML page whose own
`<link rel="canonical">` points at the `.html` form. This script writes the
sitemap that declares those pages, using the canonical form so the two agree.

The URL set is derived entirely from the filesystem -- there is no curated list
to fall out of date. `tests/test_pages_front_door.py` recomputes the same set and
fails in both directions -- a published page the sitemap omits, and a declared URL
that is not published -- which is the drift this file exists to stop.

`lastmod` comes from each source file's last commit date, not from the build
clock. A sitemap whose every URL claims to have changed today is a trust
negative, and it is also simply false.

`--check` compares the declared URL set against the published pages and ignores
`lastmod` deliberately: committing a file changes that file's commit date, so a
byte-exact check would fail on the very commit that regenerated it. The URL set
is what actually rots when a document is added or removed.

Usage:
    python tools/build_sitemap.py            # rewrite docs/sitemap.xml
    python tools/build_sitemap.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITEMAP = DOCS / "sitemap.xml"
BASE = "https://mskazemi.com/idkmesh/"

# Directories whose contents are reference material rank above session records.
# A sitemap is a statement of priority, not an inventory.
DIRECTORY_PRIORITY = {
    "": "0.9",
    "specifications": "0.8",
    "architecture": "0.8",
    "findings": "0.7",
    "research": "0.7",
    "protocols": "0.7",
    "interoperability": "0.7",
    "algorithms": "0.7",
    "foundations": "0.7",
    "decisions": "0.6",
    "audits": "0.6",
    "community": "0.6",
    "security": "0.6",
    "acceptance": "0.5",
    "design": "0.5",
    "evidence": "0.5",
    "planning": "0.4",
    "admin": "0.4",
    "conversations": "0.3",
}
DEFAULT_PRIORITY = "0.5"


def _git_lastmod(path: Path) -> str:
    """The file's last commit date, or today's date when git cannot answer.

    A shallow clone or an uncommitted file both fall back to today, which is
    honest: an uncommitted file genuinely has no commit date yet.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        stamp = out.stdout.strip()
        if stamp:
            date.fromisoformat(stamp)  # reject anything that is not a date
            return stamp
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return datetime.now(timezone.utc).date().isoformat()


def published_pages() -> list[tuple[str, Path]]:
    """Every URL Pages publishes as an HTML page, paired with its source file.

    Three rules, all derived from how GitHub Pages actually serves this tree:

    * ``docs/index.html`` is the site root;
    * a directory's ``README.md`` becomes that directory's index URL;
    * every other Markdown document renders at its ``.html`` path.

    Hand-written ``.html`` files other than ``index.html`` are published as-is.
    """
    pages: list[tuple[str, Path]] = [(BASE, DOCS / "index.html")]

    for source in sorted(DOCS.rglob("*.html")):
        if source.name == "index.html":
            continue
        pages.append((BASE + source.relative_to(DOCS).as_posix(), source))

    for source in sorted(DOCS.rglob("*.md")):
        relative = source.relative_to(DOCS)
        if source.name == "README.md":
            parent = relative.parent.as_posix()
            if parent == ".":
                # Shadowed: docs/index.html already occupies the site root, so
                # docs/README.md is published as raw Markdown only and has no
                # HTML page. Verified live -- /idkmesh/README.html returns 404.
                # This is the same shadowing rule that hid docs/index.md.
                continue
            pages.append((BASE + parent + "/", source))
        else:
            pages.append((BASE + relative.with_suffix(".html").as_posix(), source))

    return sorted(set(pages))


def declared_locations() -> list[str]:
    """The `<loc>` values currently committed in `docs/sitemap.xml`."""
    tree = ElementTree.parse(SITEMAP)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [element.text or "" for element in tree.findall("sm:url/sm:loc", namespace)]


def _priority(source: Path) -> str:
    top = source.relative_to(DOCS).parts
    return DIRECTORY_PRIORITY.get(top[0] if len(top) > 1 else "", DEFAULT_PRIORITY)


def render() -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- Generated by tools/build_sitemap.py. Do not edit by hand. -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, source in published_pages():
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(url)}</loc>")
        lines.append(f"    <lastmod>{_git_lastmod(source)}</lastmod>")
        lines.append(f"    <priority>{_priority(source)}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def verify_live(timeout: float = 20.0) -> int:
    """Fetch every declared URL and report the ones that do not return 200.

    A source file existing does not prove Pages publishes it: `docs/README.md`
    is shadowed by `docs/index.html` and its `.html` URL 404s. That defect was
    invisible to the offline checks -- both the file and the rule looked right.
    This is opt-in and hits the network, so it is not part of the test suite.

    A 404 here does not always mean the sitemap is wrong. Pages rebuilds behind
    `main`, so a document committed minutes ago is declared correctly and still
    404s until the site redeploys. Compare the live site's `Last-Modified`
    against the commit date before treating a failure as a defect.
    """
    import urllib.error
    import urllib.request

    broken: list[tuple[str, str]] = []
    urls = declared_locations()
    for index, url in enumerate(urls, start=1):
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, OSError, ValueError) as error:
            broken.append((url, str(error)))
            continue
        if status != 200:
            broken.append((url, str(status)))
        if index % 50 == 0:
            print(f"  checked {index}/{len(urls)}")

    for url, reason in broken:
        print(f"NOT 200 ({reason}): {url}")
    if broken:
        print(
            "\nNote: recently committed documents 404 until GitHub Pages redeploys. "
            "Check the live site's Last-Modified against the commit date before "
            "treating these as sitemap defects."
        )
    print(f"{len(urls) - len(broken)}/{len(urls)} declared URLs return 200")
    return 1 if broken else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the declared URL set does not match the published pages",
    )
    parser.add_argument(
        "--verify-live",
        action="store_true",
        help="fetch every declared URL and fail on any that does not return 200 "
        "(hits the network; not run by the test suite)",
    )
    args = parser.parse_args()

    if args.verify_live:
        return verify_live()

    if args.check:
        expected = [url for url, _ in published_pages()]
        try:
            declared = declared_locations()
        except (OSError, ElementTree.ParseError) as error:
            print(f"docs/sitemap.xml is unreadable: {error}")
            return 1
        missing = sorted(set(expected) - set(declared))
        extra = sorted(set(declared) - set(expected))
        if missing or extra:
            for url in missing:
                print(f"missing from sitemap: {url}")
            for url in extra:
                print(f"declared but not published: {url}")
            print("run: python tools/build_sitemap.py")
            return 1
        print(f"docs/sitemap.xml declares all {len(expected)} published pages")
        return 0

    rendered = render()

    SITEMAP.write_text(rendered, encoding="utf-8")
    print(f"wrote {SITEMAP.relative_to(ROOT)} ({len(published_pages())} URLs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
