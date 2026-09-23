import json
from pathlib import Path
import unittest

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    GitHubPullRequestCandidateReference,
    candidate_reference_from_dict,
)


SHA1 = "0123456789abcdef0123456789abcdef01234567"
SHA256_GIT = "a" * 64
CONTENT_DIGEST = "sha256:" + "b" * 64


class CandidateReferenceTests(unittest.TestCase):
    def test_github_pull_request_round_trip(self):
        ref = GitHubPullRequestCandidateReference(
            repository="MSKazemi/idkmesh",
            number=42,
            head_sha=SHA1.upper(),
        )
        self.assertEqual(ref.head_sha, SHA1)
        self.assertEqual(ref.canonical_url, "https://github.com/MSKazemi/idkmesh/pull/42")
        encoded = ref.to_dict()
        self.assertEqual(
            candidate_reference_from_dict(encoded),
            ref,
        )
        self.assertEqual(
            encoded,
            {
                "schema_version": "0.1",
                "type": "github_pull_request",
                "repository": "MSKazemi/idkmesh",
                "number": 42,
                "head_sha": SHA1,
            },
        )

    def test_sha256_git_object_id_is_supported(self):
        ref = GitHubPullRequestCandidateReference(
            repository="owner/repo",
            number=1,
            head_sha=SHA256_GIT,
        )
        self.assertEqual(ref.head_sha, SHA256_GIT)

    def test_pr_reference_rejects_mutable_or_ambiguous_identity(self):
        invalid = [
            {"repository": "repo", "number": 1, "head_sha": SHA1},
            {"repository": "owner/repo/extra", "number": 1, "head_sha": SHA1},
            {"repository": "owner/repo", "number": 0, "head_sha": SHA1},
            {"repository": "owner/repo", "number": True, "head_sha": SHA1},
            {"repository": "owner/repo", "number": 1, "head_sha": "main"},
            {"repository": "owner/repo", "number": 1, "head_sha": "a" * 39},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    GitHubPullRequestCandidateReference(**kwargs)

    def test_artifact_bundle_round_trip(self):
        ref = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.tar",
            digest=CONTENT_DIGEST,
            media_type="application/x-tar",
        )
        encoded = ref.to_dict()
        self.assertEqual(candidate_reference_from_dict(encoded), ref)
        self.assertEqual(encoded["digest"], CONTENT_DIGEST)

    def test_artifact_bundle_requires_content_address(self):
        for digest in ("", "b" * 64, "sha256:" + "B" * 64, "sha1:" + "b" * 40):
            with self.subTest(digest=digest):
                with self.assertRaises(ValueError):
                    ArtifactBundleCandidateReference(
                        locator="file:///tmp/candidate.tar",
                        digest=digest,
                    )

    def test_parser_rejects_unknown_versions_types_and_fields(self):
        good = {
            "schema_version": "0.1",
            "type": "github_pull_request",
            "repository": "owner/repo",
            "number": 1,
            "head_sha": SHA1,
        }
        cases = [
            {**good, "schema_version": "9.9"},
            {**good, "type": "provider_magic"},
            {**good, "accepted": True},
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    candidate_reference_from_dict(raw)

    def test_parser_rejects_missing_fields(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            candidate_reference_from_dict(
                {
                    "schema_version": "0.1",
                    "type": "github_pull_request",
                    "repository": "owner/repo",
                    "number": 1,
                }
            )

    def test_schema_is_versioned_strict_union(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "schemas" / "candidate-reference-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(len(schema["oneOf"]), 2)
        for form in schema["oneOf"]:
            self.assertFalse(form["additionalProperties"])
            self.assertIn("schema_version", form["required"])
            self.assertIn("type", form["required"])

    def test_reference_has_no_acceptance_or_verification_fields(self):
        ref = GitHubPullRequestCandidateReference(
            repository="owner/repo",
            number=1,
            head_sha=SHA1,
        ).to_dict()
        forbidden = {
            "accepted",
            "verified",
            "verification_status",
            "merge_authorized",
            "provider_completed",
        }
        self.assertTrue(forbidden.isdisjoint(ref))


if __name__ == "__main__":
    unittest.main()
