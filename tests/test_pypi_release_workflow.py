"""The PyPI workflow must publish one reviewed tag through OIDC, not branch state."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-pypi.yml"
RUNBOOK = ROOT / "docs" / "operations" / "PYPI_RELEASE_RUNBOOK.md"


class PyPIReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_publish_requires_an_explicit_release_tag(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("release_tag:", self.workflow)
        self.assertIn("required: true", self.workflow)

    def test_checkout_and_preflight_are_bound_to_the_release_tag(self) -> None:
        self.assertIn(
            "ref: ${{ github.event.release.tag_name || inputs.release_tag }}",
            self.workflow,
        )
        self.assertIn(
            'python tools/check_release_version.py --tag "$RELEASE_TAG"',
            self.workflow,
        )

    def test_publication_uses_oidc_not_a_pypi_token_secret(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("pypa/gh-action-pypi-publish@", self.workflow)
        lowered = self.workflow.lower()
        self.assertNotIn("pypi_api_token", lowered)
        self.assertNotIn("password:", lowered)

    def test_publish_is_protected_by_the_pypi_environment(self) -> None:
        self.assertIn("environment:", self.workflow)
        self.assertIn("name: pypi", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_release_runbook_is_tracked(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("Trusted Publishing", text)
        self.assertIn("issue #769", text)
        self.assertIn("tools/check_release_version.py", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
