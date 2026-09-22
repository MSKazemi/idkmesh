"""Deterministic tests for the IndexNow discovery notifier."""

from __future__ import annotations

import unittest
from datetime import date

from tools import submit_indexnow


class IndexNowTests(unittest.TestCase):
    def test_key_file_matches_declared_key(self) -> None:
        key_file = submit_indexnow.ROOT / "docs" / f"{submit_indexnow.KEY}.txt"
        self.assertTrue(key_file.is_file())
        self.assertEqual(submit_indexnow.KEY, key_file.read_text(encoding="utf-8").strip())

    def test_key_location_is_under_the_same_public_site_path(self) -> None:
        self.assertEqual(
            f"https://mskazemi.com/idkmesh/{submit_indexnow.KEY}.txt",
            submit_indexnow.KEY_LOCATION,
        )

    def test_payload_rejects_urls_outside_verified_path(self) -> None:
        with self.assertRaises(ValueError):
            submit_indexnow.payload(["https://example.com/not-idkmesh"])

    def test_payload_shape_is_protocol_specific_and_secret_free(self) -> None:
        urls = ["https://mskazemi.com/idkmesh/topics/"]
        data = submit_indexnow.payload(urls)
        self.assertEqual("mskazemi.com", data["host"])
        self.assertEqual(submit_indexnow.KEY, data["key"])
        self.assertEqual(submit_indexnow.KEY_LOCATION, data["keyLocation"])
        self.assertEqual(urls, data["urlList"])

    def test_recent_filter_uses_truthful_sitemap_dates(self) -> None:
        urls = submit_indexnow.recently_changed(1, today=date(2026, 9, 22))
        self.assertTrue(urls)
        self.assertTrue(all(url.startswith("https://mskazemi.com/idkmesh/") for url in urls))

    def test_recent_filter_rejects_invalid_window(self) -> None:
        with self.assertRaises(ValueError):
            submit_indexnow.recently_changed(0, today=date(2026, 9, 22))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
