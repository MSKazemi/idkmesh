"""Guard the installable package's public discovery metadata.

The pip-installable surface is deliberately narrower than the whole IDKMesh
research repository. These tests keep its metadata discoverable without
misrepresenting the package as the unfinished Verified Swarm Runner.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


class PackageDiscoveryMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]

    def test_description_names_the_shipped_verification_surface(self) -> None:
        description = self.project["description"].lower()
        for phrase in ("review-gate", "verifier", "correlated", "evidence"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, description)
        self.assertNotIn("swarm runner", description)

    def test_keywords_cover_the_primary_installable_intents(self) -> None:
        keywords = set(self.project["keywords"])
        required = {
            "ai-agent-verification",
            "ai-code-review",
            "agent-evaluation",
            "llm-evaluation",
            "llm-as-judge",
            "verifier-panel",
            "evidence",
            "provenance",
        }
        self.assertTrue(required.issubset(keywords))
        self.assertEqual(len(keywords), len(self.project["keywords"]))

    def test_project_urls_connect_package_to_canonical_discovery_surfaces(self) -> None:
        urls = self.project["urls"]
        self.assertEqual("https://mskazemi.com/idkmesh/", urls["Homepage"])
        self.assertEqual(
            "https://mskazemi.com/idkmesh/topics/",
            urls["Topics"],
        )
        self.assertEqual(
            "https://mskazemi.com/idkmesh/research.html",
            urls["Research"],
        )
        self.assertEqual(
            "https://github.com/MSKazemi/idkmesh",
            urls["Repository"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
