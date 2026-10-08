"""Tests for canonical durable GitHub evidence links (C14-C)."""

from __future__ import annotations

import unittest

from idkmesh.github_evidence_link import (
    DurableGitHubEvidenceLinkError,
    DurableGitHubEvidenceReference,
    parse_durable_github_evidence_url,
    validate_durable_github_evidence_url,
)


SHA40 = "a" * 40
SHA64 = "b" * 64


class DurableGitHubEvidenceReferenceTests(unittest.TestCase):
    def test_builds_commit_pinned_html_and_raw_urls(self) -> None:
        reference = DurableGitHubEvidenceReference(
            repository="MSKazemi/idkmesh",
            commit_sha=SHA40,
            path="evidence/run 001/report.json",
        )

        self.assertEqual(
            reference.html_url,
            (
                "https://github.com/MSKazemi/idkmesh/blob/"
                + SHA40
                + "/evidence/run%20001/report.json"
            ),
        )
        self.assertEqual(
            reference.raw_url,
            (
                "https://raw.githubusercontent.com/MSKazemi/idkmesh/"
                + SHA40
                + "/evidence/run%20001/report.json"
            ),
        )
        self.assertEqual(
            reference.to_dict()["retention_identity"],
            "git-commit-pinned-file",
        )
        self.assertFalse(reference.to_dict()["actions_artifact"])
        self.assertFalse(reference.to_dict()["merge"])

    def test_64_hex_revision_is_supported_and_normalized_lowercase(self) -> None:
        reference = DurableGitHubEvidenceReference(
            repository="MSKazemi/idkmesh",
            commit_sha=SHA64.upper(),
            path="evidence/report.json",
        )
        self.assertEqual(reference.commit_sha, SHA64)
        self.assertIn(SHA64, reference.html_url)

    def test_path_validation_rejects_traversal_empty_and_backslash_segments(self) -> None:
        bad_paths = (
            "../secret.json",
            "evidence/../secret.json",
            "/evidence/report.json",
            "evidence/report.json/",
            "evidence//report.json",
            r"evidence\report.json",
        )
        for path in bad_paths:
            with self.subTest(path=path):
                with self.assertRaises(DurableGitHubEvidenceLinkError):
                    DurableGitHubEvidenceReference(
                        repository="MSKazemi/idkmesh",
                        commit_sha=SHA40,
                        path=path,
                    )


class DurableGitHubEvidenceUrlTests(unittest.TestCase):
    def test_accepts_canonical_blob_and_raw_commit_permalinks(self) -> None:
        html = (
            "https://github.com/MSKazemi/idkmesh/blob/"
            + SHA40
            + "/evidence/report.json"
        )
        raw = (
            "https://raw.githubusercontent.com/MSKazemi/idkmesh/"
            + SHA40
            + "/evidence/report.json"
        )

        parsed_html = parse_durable_github_evidence_url(
            html,
            expected_repository="MSKazemi/idkmesh",
        )
        parsed_raw = parse_durable_github_evidence_url(
            raw,
            expected_repository="mskazemi/IDKMESH",
        )

        self.assertEqual(parsed_html.path, "evidence/report.json")
        self.assertEqual(parsed_raw.commit_sha, SHA40)
        self.assertEqual(validate_durable_github_evidence_url(html), html)
        self.assertEqual(validate_durable_github_evidence_url(raw), raw)

        root_file = (
            "https://github.com/MSKazemi/idkmesh/blob/"
            + SHA40
            + "/report.json"
        )
        self.assertEqual(
            parse_durable_github_evidence_url(root_file).path,
            "report.json",
        )

    def test_rejects_branch_tag_actions_and_non_file_urls(self) -> None:
        bad_urls = (
            "https://github.com/MSKazemi/idkmesh/blob/main/evidence/report.json",
            "https://github.com/MSKazemi/idkmesh/blob/v0.1/evidence/report.json",
            "https://github.com/MSKazemi/idkmesh/actions/runs/123/artifacts/456",
            "https://github.com/MSKazemi/idkmesh/commit/" + SHA40,
            "https://github.com/MSKazemi/idkmesh/releases/tag/v0.1",
        )
        for url in bad_urls:
            with self.subTest(url=url):
                with self.assertRaises(DurableGitHubEvidenceLinkError):
                    validate_durable_github_evidence_url(url)

    def test_rejects_query_fragment_credentials_and_cross_repository(self) -> None:
        base = (
            "https://github.com/MSKazemi/idkmesh/blob/"
            + SHA40
            + "/evidence/report.json"
        )
        bad_urls = (
            base + "?download=1",
            base + "#L1",
            (
                "https://user@github.com/MSKazemi/idkmesh/blob/"
                + SHA40
                + "/evidence/report.json"
            ),
            (
                "https://github.com:bad/MSKazemi/idkmesh/blob/"
                + SHA40
                + "/evidence/report.json"
            ),
        )
        for url in bad_urls:
            with self.subTest(url=url):
                with self.assertRaises(DurableGitHubEvidenceLinkError):
                    validate_durable_github_evidence_url(url)

        with self.assertRaises(DurableGitHubEvidenceLinkError):
            validate_durable_github_evidence_url(
                base,
                expected_repository="MSKazemi/other",
            )

    def test_rejects_noncanonical_percent_encoding(self) -> None:
        noncanonical = (
            "https://github.com/MSKazemi/idkmesh/blob/"
            + SHA40
            + "/evidence/%72eport.json"
        )
        with self.assertRaises(DurableGitHubEvidenceLinkError):
            validate_durable_github_evidence_url(noncanonical)


if __name__ == "__main__":
    unittest.main()
