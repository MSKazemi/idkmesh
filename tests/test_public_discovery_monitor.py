"""Static and deterministic guards for the public discovery monitor."""

from __future__ import annotations

import unittest
from unittest import mock

from tools import check_public_discovery as monitor


class PublicDiscoveryMonitorTests(unittest.TestCase):
    def test_required_surfaces_are_https_idkmesh_urls(self) -> None:
        self.assertEqual("https://mskazemi.com/robots.txt", monitor.ROOT_ROBOTS)
        for url in (
            monitor.HOME,
            monitor.TOPICS,
            monitor.SITEMAP,
            monitor.LLMS,
            monitor.INDEXNOW_KEY_URL,
            *(url for url, _ in monitor.TOPIC_PAGES.values()),
        ):
            self.assertTrue(url.startswith("https://mskazemi.com/idkmesh/"))

    def test_exactly_ten_topic_pillars_are_monitored(self) -> None:
        self.assertEqual(10, len(monitor.TOPIC_PAGES))
        urls = [url for url, _ in monitor.TOPIC_PAGES.values()]
        self.assertEqual(10, len(set(urls)))

    def test_representative_search_and_answer_agents_are_covered(self) -> None:
        required = {
            "google",
            "bing",
            "openai",
            "claude-search",
            "claude-user",
            "perplexity",
            "perplexity-user",
        }
        self.assertTrue(required.issubset(monitor.USER_AGENTS))
        self.assertEqual(required, set(monitor.ROBOTS_USER_AGENTS))
        self.assertIn("browser", monitor.USER_AGENTS)


    def test_workflow_waits_for_pages_deployment(self) -> None:
        workflow = (
            monitor.ROOT
            if hasattr(monitor, "ROOT")
            else None
        )
        del workflow
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        text = (
            root / ".github" / "workflows" / "public-discovery-monitor.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn("pages build and deployment", text)
        self.assertIn("github.event.workflow_run.head_sha", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertNotIn("\n  push:\n", text)

    def _healthy_fetch(self, url: str, user_agent: str, timeout: float = 10.0):
        del user_agent, timeout
        if url == monitor.ROOT_ROBOTS:
            return (
                200,
                "User-agent: *\nAllow: /\n"
                "Sitemap: https://mskazemi.com/idkmesh/sitemap.xml\n",
            )
        if url == monitor.SITEMAP:
            urls = [monitor.HOME, monitor.TOPICS]
            urls.extend(url for url, _ in monitor.TOPIC_PAGES.values())
            return 200, "\n".join(f"<loc>{item}</loc>" for item in urls)
        if url == monitor.HOME:
            return 200, "<html><body>IDKMesh Verified swarm engineering</body></html>"
        if url == monitor.TOPICS:
            return (
                200,
                "<html><body>AI agent verification and multi-agent orchestration</body></html>",
            )
        if url == monitor.LLMS:
            return (
                200,
                f"AI agent verification\nMulti-agent orchestration\n{monitor.TOPICS}",
            )
        if url == monitor.INDEXNOW_KEY_URL:
            return 200, monitor.INDEXNOW_KEY + "\n"
        for topic_url, marker in monitor.TOPIC_PAGES.values():
            if url == topic_url:
                return (
                    200,
                    '<html><head><link rel="canonical" href="'
                    + topic_url
                    + '"><meta name="description" content="topic"></head><body>'
                    + marker
                    + "</body></html>",
                )
        return 404, ""

    def test_healthy_fixture_passes_every_contract(self) -> None:
        with mock.patch.object(monitor, "fetch", side_effect=self._healthy_fetch):
            self.assertEqual([], monitor.probe())

    def test_missing_topic_canonical_is_reported(self) -> None:
        broken_url = monitor.TOPIC_PAGES["ai-agent-verification"][0]

        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == broken_url:
                body = body.replace('<link rel="canonical" href="' + broken_url + '">', "")
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "ai-agent-verification: rendered page has no canonical link", failures
        )

    def test_robots_block_for_answer_engine_is_reported(self) -> None:
        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == monitor.ROOT_ROBOTS:
                body = (
                    "User-agent: OAI-SearchBot\nDisallow: /idkmesh/\n\n"
                    "User-agent: *\nAllow: /\n"
                    "Sitemap: https://mskazemi.com/idkmesh/sitemap.xml\n"
                )
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            f"robots.txt blocks openai from {monitor.HOME}", failures
        )

    def test_wrong_indexnow_key_is_reported(self) -> None:
        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == monitor.INDEXNOW_KEY_URL:
                body = "wrong-key"
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "IndexNow key body does not match the committed public key", failures
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
