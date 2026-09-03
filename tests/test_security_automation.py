from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_USE = re.compile(r"^\s*uses:\s*[^\s]+@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)

# The pin is asserted by *shape and consistency*, never as a hard-coded value.
# Hard-coding the SHA made every Dependabot bump fail the required gate by
# construction -- updating the action is precisely what those pull requests do --
# so the three open codeql-action updates could not merge without someone also
# editing this file. That turns the security automation into toil and leaves the
# action stale, which is the opposite of what pinning is for.
#
# The two properties that actually matter are kept:
#   * every `uses:` resolves to an immutable 40-hex commit SHA, never a tag;
#   * every github/codeql-action/* step resolves to the SAME SHA, because GitHub
#     requires init, analyze and upload-sarif to come from one version.
CODEQL_ACTION_USE = re.compile(r"github/codeql-action/([a-z-]+)@([0-9a-f]{40})")


def codeql_pins(*texts: str) -> list[tuple[str, str]]:
    """(sub-action, sha) for every github/codeql-action reference given."""
    return [pin for text in texts for pin in CODEQL_ACTION_USE.findall(text)]


class SecurityAutomationTests(unittest.TestCase):
    def test_codeql_has_least_privilege_and_no_target_event(self) -> None:
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("security-events: write", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_codeql_actions_are_immutable_pins(self) -> None:
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        uses_lines = [line for line in workflow.splitlines() if line.strip().startswith("uses:")]
        self.assertEqual(len(uses_lines), 3)
        self.assertEqual(len(FULL_SHA_USE.findall(workflow)), len(uses_lines))
        pins = codeql_pins(workflow)
        self.assertEqual(sorted(name for name, _ in pins), ["analyze", "init"])
        self.assertEqual(
            len({sha for _, sha in pins}),
            1,
            "init and analyze must resolve to one codeql-action version; GitHub "
            "does not support mixing them.",
        )

    def test_dependabot_covers_actions_and_python_dependencies(self) -> None:
        config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", config)
        self.assertIn("package-ecosystem: pip", config)
        self.assertEqual(config.count("open-pull-requests-limit: 3"), 2)
        self.assertEqual(config.count("dependency-name: \"*\""), 2)
        self.assertEqual(config.count("version-update:semver-major"), 2)

    def test_scorecard_is_pinned_bounded_and_least_privilege(self) -> None:
        workflow = (ROOT / ".github/workflows/scorecard.yml").read_text(encoding="utf-8")
        self.assertIn("security-events: write", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("publish_results: false", workflow)
        self.assertIn("retention-days: 5", workflow)
        codeql = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        pins = codeql_pins(workflow)
        self.assertEqual([name for name, _ in pins], ["upload-sarif"])
        self.assertEqual(
            {sha for _, sha in pins},
            {sha for _, sha in codeql_pins(codeql)},
            "scorecard.yml must upload SARIF with the same codeql-action version "
            "codeql.yml analyses with.",
        )

        uses_lines = [line for line in workflow.splitlines() if line.strip().startswith("uses:")]
        self.assertEqual(len(uses_lines), 4)
        self.assertEqual(len(FULL_SHA_USE.findall(workflow)), len(uses_lines))


if __name__ == "__main__":
    unittest.main()
