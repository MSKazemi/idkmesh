"""Static guards for the public discovery monitor."""

from __future__ import annotations

import unittest

from tools import check_public_discovery


class PublicDiscoveryMonitorTests(unittest.TestCase):
    def test_required_surfaces_are_https_idkmesh_urls(self) -> None:
        self.assertEqual("https://mskazemi.com/robots.txt", check_public_discovery.ROOT_ROBOTS)
        for url in (
            check_public_discovery.HOME,
            check_public_discovery.TOPICS,
            check_public_discovery.SITEMAP,
        ):
            self.assertTrue(url.startswith("https://mskazemi.com/idkmesh/"))

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
        self.assertTrue(required.issubset(check_public_discovery.USER_AGENTS))

    def test_monitor_has_a_browser_baseline(self) -> None:
        self.assertIn("browser", check_public_discovery.USER_AGENTS)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
