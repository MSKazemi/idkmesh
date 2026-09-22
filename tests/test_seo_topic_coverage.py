"""Guard the 100-query SEO/AEO/GEO topic architecture."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONFIG = ROOT / "config" / "seo-topics-v1.json"
HUB = DOCS / "topics" / "README.md"
SITE_PREFIX = "https://mskazemi.com/idkmesh/topics/"


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    _, block, _ = text.split("---\n", 2)
    values: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


class SEOTopicCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.clusters = cls.payload["clusters"]

    def test_exactly_one_hundred_unique_queries_in_ten_clusters(self) -> None:
        self.assertEqual(10, len(self.clusters))
        queries = [query for cluster in self.clusters for query in cluster["queries"]]
        self.assertEqual(100, len(queries))
        self.assertEqual(100, len(set(queries)))
        self.assertTrue(all(query == query.lower().strip() for query in queries))
        self.assertTrue(all(len(cluster["queries"]) == 10 for cluster in self.clusters))

    def test_every_cluster_targets_one_real_topic_page(self) -> None:
        failures = []
        for cluster in self.clusters:
            source = ROOT / cluster["path"]
            if not source.is_file():
                failures.append(f"{cluster['id']}: missing {cluster['path']}")
                continue
            parsed = urlparse(cluster["url"])
            if not cluster["url"].startswith(SITE_PREFIX):
                failures.append(f"{cluster['id']}: target outside topics site")
            expected_name = Path(parsed.path).name.replace(".html", ".md")
            if source.name != expected_name:
                failures.append(
                    f"{cluster['id']}: {source.name} does not match {expected_name}"
                )
        self.assertEqual([], failures)

    def test_target_pages_are_substantial_question_answer_sources(self) -> None:
        failures = []
        for cluster in self.clusters:
            source = ROOT / cluster["path"]
            text = source.read_text(encoding="utf-8")
            frontmatter = _frontmatter(text)
            body = text.split("---\n", 2)[-1]
            words = re.findall(r"\b[\w'-]+\b", body)
            questions = re.findall(r"^### .+\?$", body, flags=re.MULTILINE)
            links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", body)
            if len(words) < 400:
                failures.append(f"{source.name}: only {len(words)} words")
            if len(questions) < 4:
                failures.append(f"{source.name}: only {len(questions)} question headings")
            if len(links) < 4:
                failures.append(f"{source.name}: only {len(links)} links")
            if not frontmatter.get("title"):
                failures.append(f"{source.name}: missing title frontmatter")
            description = frontmatter.get("description", "")
            if not 80 <= len(description) <= 180:
                failures.append(
                    f"{source.name}: description length {len(description)}"
                )
            if "https://mskazemi.com/idkmesh/topics/" not in body:
                failures.append(f"{source.name}: missing topic-hub link")
        self.assertEqual([], failures)

    def test_topic_hub_links_every_cluster(self) -> None:
        hub = HUB.read_text(encoding="utf-8")
        missing = [
            cluster["url"].rsplit("/", 1)[-1]
            for cluster in self.clusters
            if cluster["url"].rsplit("/", 1)[-1] not in hub
        ]
        self.assertEqual([], missing)

    def test_keyword_map_is_not_published_as_meta_keyword_stuffing(self) -> None:
        for cluster in self.clusters:
            text = (ROOT / cluster["path"]).read_text(encoding="utf-8").lower()
            self.assertNotIn("meta name=\"keywords\"", text)
            self.assertNotIn("keywords:", _frontmatter(text))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
