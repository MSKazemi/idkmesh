"""SEO contracts for the public GitHub Pages documentation surface.

The hand-written HTML pages own their metadata directly. Markdown pages are
rendered by GitHub Pages/Jekyll, so docs/_config.yml provides the shared identity
and URL context for that long-tail surface. These checks keep both paths aligned.
"""

from __future__ import annotations

import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITE = "https://mskazemi.com/idkmesh"
SOCIAL_IMAGE = f"{SITE}/assets/idkmesh-social.png"
REPOSITORY = "https://github.com/MSKazemi/idkmesh"


class _PageSEO(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = ""
        self.title = ""
        self._in_title = False
        self._title_parts: list[str] = []
        self.h1_count = 0
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.jsonld: list[Any] = []
        self._json_parts: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "html":
            self.lang = attr.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta":
            key = attr.get("name") or attr.get("property")
            if key:
                self.meta[key.lower()] = attr.get("content", "")
        elif tag == "link":
            self.links.append(attr)
        elif tag == "script" and attr.get("type", "").lower() == "application/ld+json":
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            self.title = "".join(self._title_parts).strip()
        elif tag == "script" and self._json_parts is not None:
            payload = "".join(self._json_parts).strip()
            if payload:
                self.jsonld.append(json.loads(payload))
            self._json_parts = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._json_parts is not None:
            self._json_parts.append(data)


def _parse(path: Path) -> _PageSEO:
    parser = _PageSEO()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def _schema_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _schema_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _schema_objects(nested)


def _has_type(obj: dict[str, Any], expected: str) -> bool:
    value = obj.get("@type")
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return expected in value
    return False


class PagesSEOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = sorted(DOCS.glob("*.html"))
        cls.parsed = {page.name: _parse(page) for page in cls.pages}

    def test_site_has_hand_written_pages(self) -> None:
        self.assertGreaterEqual(len(self.pages), 6)

    def test_each_page_has_one_clear_search_identity(self) -> None:
        failures = []
        for page in self.pages:
            data = self.parsed[page.name]
            description = data.meta.get("description", "")
            if data.lang != "en":
                failures.append(f"{page.name}: html lang={data.lang!r}")
            if data.h1_count != 1:
                failures.append(f"{page.name}: h1_count={data.h1_count}")
            if not (10 <= len(data.title) <= 70):
                failures.append(f"{page.name}: title length={len(data.title)}")
            if not (50 <= len(description) <= 180):
                failures.append(
                    f"{page.name}: description length={len(description)}"
                )
        self.assertEqual([], failures)

    def test_each_page_explicitly_allows_search_and_rich_previews(self) -> None:
        required = {
            "index",
            "follow",
            "max-image-preview:large",
            "max-snippet:-1",
            "max-video-preview:-1",
        }
        failures = []
        for page in self.pages:
            value = self.parsed[page.name].meta.get("robots", "")
            actual = {part.strip().lower() for part in value.split(",") if part.strip()}
            if not required.issubset(actual):
                failures.append(f"{page.name}: robots={value!r}")
        self.assertEqual([], failures)

    def test_canonical_open_graph_and_twitter_metadata_agree(self) -> None:
        failures = []
        for page in self.pages:
            data = self.parsed[page.name]
            expected_url = f"{SITE}/" if page.name == "index.html" else f"{SITE}/{page.name}"
            description = data.meta.get("description", "")
            canonicals = [
                link.get("href", "")
                for link in data.links
                if "canonical" in link.get("rel", "").lower().split()
            ]
            expected = {
                "og:url": expected_url,
                "og:title": data.title,
                "og:description": description,
                "og:site_name": "IDKMesh",
                "og:locale": "en_US",
                "og:image": SOCIAL_IMAGE,
                "og:image:type": "image/png",
                "twitter:card": "summary_large_image",
                "twitter:title": data.title,
                "twitter:description": description,
                "twitter:image": SOCIAL_IMAGE,
                "author": "Mohsen Seyedkazemi Ardebili",
            }
            if canonicals != [expected_url]:
                failures.append(f"{page.name}: canonical={canonicals!r}")
            for key, value in expected.items():
                if data.meta.get(key) != value:
                    failures.append(
                        f"{page.name}: {key}={data.meta.get(key)!r}, expected {value!r}"
                    )
            if not data.meta.get("og:image:alt"):
                failures.append(f"{page.name}: missing og:image:alt")
        self.assertEqual([], failures)

    def test_jsonld_is_parseable_and_describes_the_page_and_project(self) -> None:
        failures = []
        for page in self.pages:
            data = self.parsed[page.name]
            expected_url = f"{SITE}/" if page.name == "index.html" else f"{SITE}/{page.name}"
            objects = [
                obj
                for document in data.jsonld
                for obj in _schema_objects(document)
                if isinstance(obj, dict)
            ]
            web_pages = [obj for obj in objects if _has_type(obj, "WebPage")]
            software = [obj for obj in objects if _has_type(obj, "SoftwareSourceCode")]
            if not web_pages:
                failures.append(f"{page.name}: missing WebPage JSON-LD")
            else:
                page_obj = web_pages[0]
                if page_obj.get("url") != expected_url:
                    failures.append(
                        f"{page.name}: JSON-LD url={page_obj.get('url')!r}"
                    )
                if page_obj.get("name") != data.title:
                    failures.append(
                        f"{page.name}: JSON-LD name={page_obj.get('name')!r}"
                    )
                if page_obj.get("description") != data.meta.get("description"):
                    failures.append(f"{page.name}: JSON-LD description drift")
            if not software:
                failures.append(f"{page.name}: missing SoftwareSourceCode JSON-LD")
            elif software[0].get("codeRepository") != REPOSITORY:
                failures.append(f"{page.name}: SoftwareSourceCode repository drift")
        self.assertEqual([], failures)

    def test_llms_guide_is_published_and_points_to_canonical_sources(self) -> None:
        guide = (DOCS / "llms.txt").read_text(encoding="utf-8")
        for expected in (
            f"{SITE}/",
            REPOSITORY,
            f"{SITE}/start.html",
            f"{SITE}/research.html",
            "research preview; not production software",
            "The GitHub repository is the canonical source of truth",
        ):
            self.assertIn(expected, guide)

    def test_markdown_social_images_do_not_prepend_baseurl_twice(self) -> None:
        bad = 'image: "/idkmesh/assets/idkmesh-social.png"'
        offenders = []

        config = (DOCS / "_config.yml").read_text(encoding="utf-8")
        if bad in config:
            offenders.append("docs/_config.yml")

        for path in DOCS.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                continue
            end = text.find("\n---", 4)
            front_matter = text if end < 0 else text[: end + 4]
            if bad in front_matter:
                offenders.append(path.relative_to(ROOT).as_posix())

        self.assertEqual(
            [],
            sorted(offenders),
            "Jekyll SEO Tag applies baseurl when rendering page.image; "
            "metadata paths that already contain /idkmesh render as "
            f"/idkmesh/idkmesh: {sorted(offenders)}",
        )

    def test_jekyll_config_pins_markdown_page_identity_and_urls(self) -> None:
        config = (DOCS / "_config.yml").read_text(encoding="utf-8")
        required = (
            "theme: jekyll-theme-primer",
            "title: IDKMesh",
            'url: "https://mskazemi.com"',
            'baseurl: "/idkmesh"',
            "repository: MSKazemi/idkmesh",
            "lang: en",
            'image: "/assets/idkmesh-social.png"',
        )
        for entry in required:
            self.assertIn(entry, config)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
