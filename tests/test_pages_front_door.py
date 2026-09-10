"""Guard the published GitHub Pages surface against silent visibility drift.

Two defect classes reached the live site and neither was detectable from the
repository:

* `docs/sitemap.xml` did not exist at all, so the 300-odd documents Pages
  publishes were discoverable only by crawl-following. The sitemap is generated
  now, which means it can also go stale -- a document added without
  regenerating it is invisible again, silently.
* `docs/index.html` shadows `docs/index.md`, so a change written into the
  Markdown file never reaches the live front door. That is exactly how the
  `gate-audit` pointer was added and never published.

`docs/PAGES_SETUP.md` states the two hand-written pages are dependency-free:
"no JavaScript, external fonts, analytics, trackers, package build, or second
documentation framework". Nothing enforced that claim, and the rest of the site
(rendered by GitHub's default Jekyll theme) does not honour it. These tests make
the claim true where it is actually made.

A green check can mean the change was well formed rather than that it reached
anything. PR #391 is the worked example: it merged green, and the outcome in its
title never occurred, because it edited a file the site does not serve.
"""

from __future__ import annotations

import json
import re
import unittest
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from tools.build_sitemap import BASE, declared_locations, published_pages

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITEMAP = DOCS / "sitemap.xml"
NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# The pages PAGES_SETUP.md describes as dependency-free. The generated theme
# pages are explicitly out of scope -- they load an anchor script from a CDN,
# which is GitHub's default behaviour and not this repository's choice.
HAND_WRITTEN_PAGES = ("index.html", "pipelines.html")


class SitemapTests(unittest.TestCase):
    def test_sitemap_exists_and_parses(self) -> None:
        self.assertTrue(SITEMAP.exists(), "docs/sitemap.xml is missing")
        tree = ElementTree.parse(SITEMAP)
        self.assertTrue(
            tree.getroot().tag.endswith("urlset"),
            "docs/sitemap.xml root element is not <urlset>",
        )

    def test_every_published_page_is_declared(self) -> None:
        declared = set(declared_locations())
        missing = sorted({url for url, _ in published_pages()} - declared)
        self.assertEqual(
            missing,
            [],
            "these published pages are absent from docs/sitemap.xml; run "
            f"`python tools/build_sitemap.py`: {missing}",
        )

    def test_no_declared_url_is_unpublished(self) -> None:
        published = {url for url, _ in published_pages()}
        extra = sorted(set(declared_locations()) - published)
        self.assertEqual(
            extra,
            [],
            "docs/sitemap.xml declares URLs that no source file produces; a "
            f"sitemap pointing at 404s is worse than none: {extra}",
        )

    def test_locations_are_absolute_https_urls_under_the_site_root(self) -> None:
        offenders = [url for url in declared_locations() if not url.startswith(BASE)]
        self.assertEqual(
            offenders,
            [],
            f"every <loc> must be an absolute URL under {BASE}: {offenders}",
        )

    def test_lastmod_values_are_real_dates_that_are_not_in_the_future(self) -> None:
        tree = ElementTree.parse(SITEMAP)
        today = date.today()
        for element in tree.findall("sm:url", NAMESPACE):
            location = element.findtext("sm:loc", default="", namespaces=NAMESPACE)
            stamp = element.findtext("sm:lastmod", default="", namespaces=NAMESPACE)
            with self.subTest(url=location):
                try:
                    parsed = date.fromisoformat(stamp)
                except ValueError:  # pragma: no cover - assertion reports it
                    self.fail(f"{location} has a non-ISO lastmod: {stamp!r}")
                self.assertLessEqual(
                    parsed,
                    today,
                    f"{location} claims a future lastmod ({stamp})",
                )

    def test_priorities_are_within_the_sitemap_protocol_range(self) -> None:
        tree = ElementTree.parse(SITEMAP)
        for element in tree.findall("sm:url", NAMESPACE):
            location = element.findtext("sm:loc", default="", namespaces=NAMESPACE)
            raw = element.findtext("sm:priority", default="", namespaces=NAMESPACE)
            with self.subTest(url=location):
                self.assertRegex(raw, r"^(0\.\d|1\.0)$", f"{location}: {raw!r}")


class LandingPageTests(unittest.TestCase):
    """What this branch is responsible for on the hand-written pages.

    Assertions about the landing page's SEO content -- canonical, entity block,
    the measured claim -- deliberately live with whoever owns docs/index.html,
    not here. This class keeps only the shadowing rule that the index.md
    deletion depends on, and the dependency-free claim PAGES_SETUP.md makes.
    """

    def test_no_markdown_front_door_shadows_the_html_one(self) -> None:
        # Jekyll serves index.html at /idkmesh/, so an index.md beside it is
        # unreachable as a page and becomes a competing source of truth --
        # which PAGES_SETUP.md forbids, and which silently swallowed one
        # front-door change already.
        self.assertFalse(
            (DOCS / "index.md").exists(),
            "docs/index.md is shadowed by docs/index.html and can never be "
            "served as the front door; fold its content into index.html",
        )

    def test_hand_written_pages_load_no_script_and_no_external_asset(self) -> None:
        for name in HAND_WRITTEN_PAGES:
            source = (DOCS / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertNotRegex(
                    source,
                    r"<script[^>]*\ssrc=",
                    f"docs/{name} loads an external script; PAGES_SETUP.md "
                    "states these pages are dependency-free",
                )
                remote = sorted(
                    set(re.findall(r'(?:src|href)="(https?://[^"]+)"', source))
                    - _local_anchors(source)
                )
                offenders = [
                    url
                    for url in remote
                    if not url.startswith(
                        ("https://github.com/", "https://mskazemi.com/")
                    )
                ]
                self.assertEqual(
                    offenders,
                    [],
                    f"docs/{name} references a third-party asset host: {offenders}",
                )


def _local_anchors(source: str) -> set[str]:
    """Link hrefs, which are navigation rather than loaded assets."""
    return set(re.findall(r'<a\b[^>]*href="(https?://[^"]+)"', source))


if __name__ == "__main__":
    unittest.main()
