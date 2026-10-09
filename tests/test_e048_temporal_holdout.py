"""E048: the temporal-holdout runner stays pinned to the frozen analysis."""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import temporal_holdout as e048  # noqa: E402


class RegistrationTests(unittest.TestCase):
    def test_baseline_commit_matches_the_data_the_earlier_experiments_used(self) -> None:
        import agent_value_forecast as frozen

        self.assertEqual(e048.BASELINE_COMMIT, "40f164d5b8f1d249bf95a6df8b74b577fd8e519d")
        self.assertIn(e048.BASELINE_COMMIT, (ROOT / "docs/research/PREREG_AGENT_VALUE_FORECAST_V2.md").read_text(encoding="utf-8"))
        self.assertEqual(frozen.UPSTREAM_REPO, "SWE-bench/experiments")

    def test_v2_names_the_same_frozen_analysis_digest_as_v1(self) -> None:
        digest = hashlib.sha256((ROOT / "experiments/agent_value_forecast.py").read_bytes()).hexdigest()
        for name in ("V1", "V2"):
            text = (ROOT / f"docs/research/PREREG_AGENT_VALUE_FORECAST_{name}.md").read_text(encoding="utf-8")
            self.assertTrue(re.search(digest, text), f"{name} no longer states the frozen digest")

    def test_all_five_splits_are_covered(self) -> None:
        self.assertEqual(set(e048.SPLITS), {"lite", "verified", "test", "multilingual", "multimodal"})


if __name__ == "__main__":
    unittest.main()
