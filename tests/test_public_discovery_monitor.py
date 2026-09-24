"""Static and deterministic guards for the public discovery monitor."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from tools import check_public_discovery as monitor


class PublicDiscoveryMonitorTests(unittest.TestCase):
    def test_required_surfaces_are_https_idkmesh_urls(self) -> None:
        self.assertEqual("https://mskazemi.com/robots.txt", monitor.ROOT_ROBOTS)
        for url in (
            monitor.HOME,
            monitor.TOPICS,
            monitor.QUESTIONS,
            monitor.SITEMAP,
            monitor.LLMS,
            monitor.INDEXNOW_KEY_URL,
            monitor.JEKYLL_SENTINEL,
            *monitor.DIRECTORY_HUBS.values(),
            *(url for url, _ in monitor.TOPIC_PAGES.values()),
        ):
            self.assertTrue(url.startswith("https://mskazemi.com/idkmesh/"))

    def test_ten_legacy_directory_hubs_are_monitored(self) -> None:
        self.assertEqual(10, len(monitor.DIRECTORY_HUBS))
        self.assertEqual(10, len(set(monitor.DIRECTORY_HUBS.values())))

    def test_exactly_ten_topic_pillars_are_monitored(self) -> None:
        self.assertEqual(10, len(monitor.TOPIC_PAGES))
        urls = [url for url, _ in monitor.TOPIC_PAGES.values()]
        self.assertEqual(10, len(set(urls)))

    def test_representative_search_and_answer_agents_are_covered(self) -> None:
        required = {
            "google",
            "bing",
            "yahoo",
            "duckduckgo",
            "apple",
            "openai",
            "claude-search",
            "claude-user",
            "perplexity",
            "perplexity-user",
            "mistral-index",
            "mistral-user",
            "amazon-search",
            "amazon-user",
        }
        self.assertTrue(required.issubset(monitor.USER_AGENTS))
        self.assertEqual(required, set(monitor.ROBOTS_USER_AGENTS))
        self.assertEqual({"gemini": "Google-Extended"}, monitor.ROBOTS_PRODUCT_TOKENS)
        self.assertIn("browser", monitor.USER_AGENTS)


    def test_workflow_uses_pages_native_build_event(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (
            root / ".github" / "workflows" / "public-discovery-monitor.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("page_build:", text)
        self.assertIn("github.event.build.commit", text)
        self.assertIn("github.event.build.status", text)
        self.assertIn('PAGES_STATUS" != "built"', text)
        self.assertNotIn("workflow_run:", text)
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
            urls = [monitor.HOME, monitor.TOPICS, monitor.QUESTIONS]
            urls.extend(monitor.DIRECTORY_HUBS.values())
            urls.extend(url for url, _ in monitor.TOPIC_PAGES.values())
            return 200, "\n".join(f"<loc>{item}</loc>" for item in urls)
        if url == monitor.HOME:
            return 200, "<html><body>IDKMesh Verified swarm engineering</body></html>"
        if url in monitor.DIRECTORY_HUBS.values():
            return 200, "<html><body>directory hub</body></html>"
        if url == monitor.TOPICS:
            return (
                200,
                '<html><head><link rel="canonical" href="'
                + monitor.TOPICS
                + '"><meta property="og:image" content="'
                + monitor.SOCIAL_IMAGE
                + '"></head><body>AI agent verification and multi-agent orchestration</body></html>',
            )
        if url == monitor.JEKYLL_SENTINEL:
            return (
                200,
                '<html><head><link rel="canonical" href="'
                + monitor.JEKYLL_SENTINEL
                + '"><meta property="og:image" content="'
                + monitor.SOCIAL_IMAGE
                + '"></head><body>IDKMesh document</body></html>',
            )
        if url == monitor.QUESTIONS:
            return (
                200,
                '<html><head><link rel="canonical" href="'
                + monitor.QUESTIONS
                + '"><meta property="og:image" content="'
                + monitor.SOCIAL_IMAGE
                + '"></head><body>'
                + '100 questions about AI agent verification, orchestration, and trust. '
                + 'What is verified swarm engineering?'
                + '</body></html>',
            )
        if url == monitor.LLMS:
            return (
                200,
                "AI agent verification\n"
                "Multi-agent orchestration\n"
                f"{monitor.TOPICS}\n{monitor.QUESTIONS}",
            )
        if url == monitor.INDEXNOW_KEY_URL:
            return 200, monitor.INDEXNOW_KEY + "\n"
        for topic_url, marker in monitor.TOPIC_PAGES.values():
            if url == topic_url:
                return (
                    200,
                    '<html><head><link rel="canonical" href="'
                    + topic_url
                    + '"><meta name="description" content="topic">'
                    + '<meta property="og:image" content="'
                    + monitor.SOCIAL_IMAGE
                    + '"></head><body>'
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
            "ai-agent-verification: canonical URLs [] do not equal the expected "
            f"{broken_url!r}",
            failures,
        )

    def test_wrong_topic_canonical_is_reported(self) -> None:
        broken_url = monitor.TOPIC_PAGES["ai-agent-verification"][0]
        wrong_url = monitor.TOPIC_PAGES["agent-governance"][0]

        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == broken_url:
                body = body.replace(broken_url, wrong_url, 1)
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "ai-agent-verification: canonical URLs "
            f"[{wrong_url!r}] do not equal the expected {broken_url!r}",
            failures,
        )

    def test_topic_noindex_is_reported(self) -> None:
        broken_url = monitor.TOPIC_PAGES["ai-agent-verification"][0]

        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == broken_url:
                body = body.replace(
                    "</head>",
                    '<meta name="robots" content="noindex,follow"></head>',
                )
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "ai-agent-verification: rendered page contains a noindex directive: "
            "['noindex,follow']",
            failures,
        )

    def test_google_extended_block_for_gemini_is_reported(self) -> None:
        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == monitor.ROOT_ROBOTS:
                body = (
                    "User-agent: Google-Extended\n"
                    "Disallow: /idkmesh/\n\n"
                    "User-agent: *\n"
                    "Allow: /\n"
                    "Sitemap: https://mskazemi.com/idkmesh/sitemap.xml\n"
                )
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "robots.txt blocks gemini product token Google-Extended from "
            + monitor.HOME,
            failures,
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

    def test_duplicated_social_image_baseurl_is_reported(self) -> None:
        broken_url = monitor.TOPIC_PAGES["ai-agent-verification"][0]

        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == broken_url:
                body = body.replace(monitor.SOCIAL_IMAGE, monitor.BAD_SOCIAL_IMAGE)
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "ai-agent-verification: rendered page duplicates the /idkmesh "
            "base path in its social image",
            failures,
        )

    def test_answer_engine_block_on_question_map_is_reported(self) -> None:
        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            if (
                url == monitor.QUESTIONS
                and user_agent == monitor.USER_AGENTS["openai"]
            ):
                return 403, ""
            return self._healthy_fetch(url, user_agent, timeout)

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn("openai: question map HTTP 403", failures)

    def test_answer_engine_specific_noindex_on_question_map_is_reported(self) -> None:
        def fetch(url: str, user_agent: str, timeout: float = 10.0):
            status, body = self._healthy_fetch(url, user_agent, timeout)
            if url == monitor.QUESTIONS and user_agent == monitor.USER_AGENTS["openai"]:
                body = body.replace(
                    "</head>",
                    '<meta name="robots" content="noindex"></head>',
                )
            return status, body

        with mock.patch.object(monitor, "fetch", side_effect=fetch):
            failures = monitor.probe()
        self.assertIn(
            "openai: question map: rendered page contains a noindex directive: "
            "['noindex']",
            failures,
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
