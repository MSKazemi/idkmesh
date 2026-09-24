import unittest

from idkmesh.github_branch_reader import (
    BranchHeadResolutionError,
    GitHubBranchHeadBinding,
    GitHubBranchHeadReader,
)


REVISION = "0123456789abcdef0123456789abcdef01234567"


class FakeSource:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_branch_ref(self, *, repository, branch):
        self.calls.append((repository, branch))
        return self.response


def _ref(
    *,
    ref="refs/heads/idkmesh/wu-123",
    object_type="commit",
    sha=REVISION,
):
    return {
        "ref": ref,
        "node_id": "synthetic",
        "url": (
            "https://api.github.com/repos/MSKazemi/idkmesh/"
            "git/refs/heads/idkmesh/wu-123"
        ),
        "object": {
            "type": object_type,
            "sha": sha,
            "url": (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "git/commits/" + sha
            ),
        },
    }


class GitHubBranchHeadReaderTests(unittest.TestCase):
    def test_exact_branch_head_is_bound_to_repository_branch_and_revision(self):
        source = FakeSource(_ref())
        reader = GitHubBranchHeadReader(source)

        result = reader.resolve(
            repository="MSKazemi/idkmesh",
            branch="idkmesh/wu-123",
        )

        self.assertEqual(
            result,
            GitHubBranchHeadBinding(
                repository="MSKazemi/idkmesh",
                branch="idkmesh/wu-123",
                revision=REVISION,
            ),
        )
        self.assertEqual(result.full_ref, "refs/heads/idkmesh/wu-123")
        self.assertEqual(
            result.to_dict(),
            {
                "repository": "MSKazemi/idkmesh",
                "branch": "idkmesh/wu-123",
                "revision": REVISION,
            },
        )
        self.assertEqual(
            source.calls,
            [("MSKazemi/idkmesh", "idkmesh/wu-123")],
        )

    def test_sha_is_normalized_to_lowercase(self):
        result = GitHubBranchHeadReader(
            FakeSource(_ref(sha=REVISION.upper()))
        ).resolve(
            repository="MSKazemi/idkmesh",
            branch="idkmesh/wu-123",
        )
        self.assertEqual(result.revision, REVISION)

    def test_mismatched_ref_fails_closed(self):
        source = FakeSource(_ref(ref="refs/heads/other"))
        with self.assertRaisesRegex(
            BranchHeadResolutionError,
            "different branch ref",
        ):
            GitHubBranchHeadReader(source).resolve(
                repository="MSKazemi/idkmesh",
                branch="idkmesh/wu-123",
            )

    def test_non_commit_target_fails_closed(self):
        source = FakeSource(_ref(object_type="tag"))
        with self.assertRaisesRegex(
            BranchHeadResolutionError,
            "not a commit",
        ):
            GitHubBranchHeadReader(source).resolve(
                repository="MSKazemi/idkmesh",
                branch="idkmesh/wu-123",
            )

    def test_mutable_or_malformed_revision_fails_closed(self):
        for revision in (
            "main",
            "",
            "a" * 39,
            "g" * 40,
        ):
            with self.subTest(revision=revision):
                with self.assertRaises(BranchHeadResolutionError):
                    GitHubBranchHeadReader(
                        FakeSource(_ref(sha=revision))
                    ).resolve(
                        repository="MSKazemi/idkmesh",
                        branch="idkmesh/wu-123",
                    )

    def test_malformed_shapes_fail_closed(self):
        cases = [
            [],
            {},
            {"ref": "refs/heads/idkmesh/wu-123", "object": None},
            {"ref": "refs/heads/idkmesh/wu-123", "object": {}},
        ]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(BranchHeadResolutionError):
                    GitHubBranchHeadReader(
                        FakeSource(response)
                    ).resolve(
                        repository="MSKazemi/idkmesh",
                        branch="idkmesh/wu-123",
                    )

    def test_invalid_request_identity_fails_before_source_io(self):
        source = FakeSource(_ref())
        reader = GitHubBranchHeadReader(source)
        cases = [
            ("not-a-repository", "main"),
            ("owner/repo/extra", "main"),
            ("owner/repo", ""),
            ("owner/repo", "../main"),
            ("owner/repo", "feature//double"),
            ("owner/repo", "feature..bad"),
            ("owner/repo", ".hidden"),
            ("owner/repo", "release.lock"),
            ("owner/repo", "bad branch"),
            ("owner/repo", "bad?branch"),
        ]
        for repository, branch in cases:
            with self.subTest(repository=repository, branch=branch):
                with self.assertRaises(ValueError):
                    reader.resolve(
                        repository=repository,
                        branch=branch,
                    )
        self.assertEqual(source.calls, [])

    def test_binding_carries_identity_only(self):
        result = GitHubBranchHeadReader(
            FakeSource(_ref())
        ).resolve(
            repository="MSKazemi/idkmesh",
            branch="idkmesh/wu-123",
        )
        for field in (
            "verified",
            "dispatch_approved",
            "candidate_ready",
            "accepted",
            "verification_result",
            "merge_authorized",
            "integration_authorized",
        ):
            self.assertFalse(hasattr(result, field))


if __name__ == "__main__":
    unittest.main()
