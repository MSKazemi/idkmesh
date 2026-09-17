"""Safety-contract tests for automated benchmark publication (issue #10).

These assertions intentionally inspect the workflow as text instead of loading
YAML. They are guard rails around the few properties that make publication
scientifically and operationally safe: pull requests cannot publish, the exact
committed artifacts are revalidated before release, and every public snapshot
is bound to an immutable protected-main commit.
"""

from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-publication.yml"
CONTRACT_WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-cohort-contract.yml"


class BenchmarkPublicationWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.contract_workflow = CONTRACT_WORKFLOW.read_text(encoding="utf-8")

    def test_publication_never_runs_on_pull_request_events(self):
        trigger = self.workflow.split("permissions:", 1)[0]
        self.assertNotIn("pull_request:", trigger)
        self.assertIn("branches: [main]", trigger)
        self.assertIn("workflow_dispatch:", trigger)

    def test_write_permission_is_scoped_to_publication_workflow(self):
        self.assertIn("permissions:\n  contents: write", self.workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.contract_workflow)

    def test_release_is_preceded_by_reproducibility_and_contract_checks(self):
        check = "PYTHONPATH=. python tools/benchmark_publication.py --check"
        tests = "python -m unittest tests.test_benchmark_publication -v"
        release = 'gh release create "${RELEASE_TAG}"'
        self.assertIn(check, self.workflow)
        self.assertIn(tests, self.workflow)
        self.assertIn(release, self.workflow)
        self.assertLess(self.workflow.index(check), self.workflow.index(release))
        self.assertLess(self.workflow.index(tests), self.workflow.index(release))

    def test_release_tag_and_target_are_exact_commit_bound(self):
        self.assertIn("RELEASE_TAG: benchmark-cohort-${{ github.sha }}", self.workflow)
        self.assertIn('expected_sha="${GITHUB_SHA}"', self.workflow)
        self.assertIn('target_args=(--target "${expected_sha}")', self.workflow)
        self.assertIn("--verify-tag", self.workflow)
        self.assertNotIn("--clobber", self.workflow)
        self.assertNotIn("git tag -f", self.workflow)

    def test_missing_tag_probe_is_empty_and_transport_failures_are_not_masked(self):
        self.assertIn("git ls-remote --refs --tags", self.workflow)
        self.assertIn('"refs/tags/${RELEASE_TAG}"', self.workflow)
        self.assertIn("set -euo pipefail", self.workflow)
        self.assertNotIn('gh api "repos/${GITHUB_REPOSITORY}/git/ref/tags/', self.workflow)
        self.assertNotIn("|| true", self.workflow)

    def test_release_contains_both_canonical_publication_formats(self):
        self.assertIn(
            '"benchmarks/PUBLICATION.md#benchmark-publication.md"', self.workflow
        )
        self.assertIn(
            '"benchmarks/publication.json#benchmark-publication.json"', self.workflow
        )
        self.assertIn("--notes-file benchmarks/PUBLICATION.md", self.workflow)
        self.assertIn("--latest=false", self.workflow)

    def test_contract_workflow_revalidates_publication_workflow_changes(self):
        self.assertIn(
            '".github/workflows/benchmark-publication.yml"', self.contract_workflow
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
