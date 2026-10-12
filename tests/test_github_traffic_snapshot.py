from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from scripts.github_traffic_snapshot import _daily_totals, _get_json, _referrers, collect


class TrafficSnapshotTests(unittest.TestCase):
    def make_fake(self, mapping):
        calls = []

        def fake(url, token):
            self.assertEqual("private-secret", token)
            calls.append(url)
            return mapping[url.split("/traffic/", 1)[1]]

        return fake, calls

    def test_exact_endpoints_and_aggregate_evidence_only(self):
        fake, calls = self.make_fake({
            "views": {"count": 12, "uniques": 8, "views": [
                {"timestamp": "2026-10-10T00:00:00Z", "count": 7, "uniques": 5},
                {"timestamp": "2026-10-09T00:00:00Z", "count": 5, "uniques": 4},
            ]},
            "clones": {"count": 4, "uniques": 3, "clones": [
                {"timestamp": "2026-10-10T00:00:00Z", "count": 4, "uniques": 3},
            ]},
            "popular/referrers": [{"referrer": "Google", "count": 8, "uniques": 6}],
        })
        result = collect("MSKazemi/idkmesh", "private-secret", get_json=fake, collected_at="2026-10-11T08:00:00+00:00")
        self.assertEqual(12, result["views"]["count"])
        self.assertEqual(8, result["views"]["uniques"])
        self.assertEqual(3, result["clones"]["uniques"])
        self.assertEqual(["2026-10-09T00:00:00Z", "2026-10-10T00:00:00Z"], [row["timestamp"] for row in result["views"]["daily"]])
        self.assertEqual("2026-10-11T08:00:00Z", result["source"]["collected_at_utc"])
        self.assertEqual(["views", "clones", "popular/referrers"], [url.split("/traffic/")[1] for url in calls])
        self.assertNotIn("private-secret", json.dumps(result))
        self.assertFalse(result["authority"]["merge_authority"])
        self.assertFalse(result["authority"]["publication_authority"])

    def test_zero_count_is_evidence_not_missing_measurement(self):
        fake, _ = self.make_fake({"views": {"count": 0, "uniques": 0, "views": []},
                                  "clones": {"count": 0, "uniques": 0, "clones": []},
                                  "popular/referrers": []})
        result = collect("MSKazemi/idkmesh", "private-secret", get_json=fake)
        self.assertEqual(0, result["views"]["count"])
        self.assertEqual([], result["referrers"])

    def test_reject_bad_counts_and_non_utc_timestamps(self):
        for v in [-1, 1.5, True, "0", None]:
            with self.subTest(v=v), self.assertRaisesRegex(ValueError, "non-negative integer"):
                _daily_totals({"count": v, "uniques": 0, "views": []}, "views")
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            _daily_totals({"count": 0, "uniques": 1, "views": []}, "views")
        with self.assertRaisesRegex(ValueError, "timezone"):
            _daily_totals({"count": 1, "uniques": 1, "views": [{"timestamp": "2026-10-11", "count": 1, "uniques": 1}]}, "views")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _daily_totals({"count": 1, "uniques": 1, "views": [
                {"timestamp": "2026-10-11T00:00:00Z", "count": 1, "uniques": 1},
                {"timestamp": "2026-10-11T00:00:00+00:00", "count": 0, "uniques": 0},
            ]}, "views")

    def test_reject_malformed_referrers(self):
        for payload in [{"referrer": "A", "count": -1, "uniques": 0},
                        {"referrer": "A\nB", "count": 1, "uniques": 1},
                        {"referrer": "A", "count": 1, "uniques": 2}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                _referrers([payload])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _referrers([{"referrer": "A", "count": 1, "uniques": 1}, {"referrer": "A", "count": 1, "uniques": 1}])

    def test_only_owner_name_repository_identifiers_accepted(self):
        for path in ["MSKazemi/idkmesh/traffic", "../idkmesh", "some owner/repo", "repo"]:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "owner/name"):
                collect(path, "private-secret", get_json=lambda *_: {})

    def test_http_failure_never_leaks_token_or_response_body(self):
        def denied(*args, **kwargs):
            raise urllib.error.HTTPError("https://api.github.com/", 403, "my-secret", {}, None)

        with patch("scripts.github_traffic_snapshot.urllib.request.urlopen", side_effect=denied):
            with self.assertRaises(RuntimeError) as error:
                _get_json("https://api.github.com/repos/MSKazemi/idkmesh/traffic/views", "private-secret")
        self.assertIn("HTTP 403", str(error.exception))
        self.assertNotIn("private-secret", str(error.exception))
        self.assertNotIn("my-secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
