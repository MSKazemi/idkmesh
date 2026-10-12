from __future__ import annotations

import json
from pathlib import Path
import unittest

import idkmesh.github_governance_preflight as preflight

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "github-governance"


def fixture() -> dict[str, object]:
    return json.loads(
        (EXAMPLES / "governance-pass-v0.1.json").read_text(encoding="utf-8")
    )


class GitHubGovernanceSecurityBoundaryTests(unittest.TestCase):
    def test_high_risk_dispatch_blocks_without_environment_approval(self) -> None:
        observation = fixture()
        observation["environment_settings"]["approval_required"] = False

        report = preflight.evaluate_governance("high_risk_dispatch", observation)
        row = next(
            item
            for item in report["guards"]
            if item["code"] == "high-risk-environment-approval"
        )

        self.assertEqual(row["status"], "FAIL")
        self.assertFalse(report["operation_allowed"])

    def test_untrusted_pr_with_provider_secret_blocks_secret_dispatch(self) -> None:
        source = """on:
  pull_request:
permissions:
  contents: read
jobs:
  dispatch:
    runs-on: ubuntu-latest
    environment: idkmesh-dispatch-high
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - run: echo '${{ secrets.PROVIDER_TOKEN }}'
"""
        lint = preflight.lint_workflow_text(source)
        self.assertIn(
            "untrusted-pr-secret-isolation",
            {item["code"] for item in lint["findings"]},
        )

        observation = preflight.merge_workflow_lints(fixture(), [lint])
        report = preflight.evaluate_governance(
            "secret_bearing_dispatch", observation
        )
        row = next(
            item
            for item in report["guards"]
            if item["code"] == "untrusted-pr-secret-isolation"
        )
        self.assertEqual(row["status"], "FAIL")
        self.assertFalse(report["operation_allowed"])


if __name__ == "__main__":
    unittest.main()
