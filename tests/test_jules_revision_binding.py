from dataclasses import dataclass
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_revision_binding import verify_jules_scm_revision


REVISION = "0123456789abcdef0123456789abcdef01234567"


@dataclass(frozen=True)
class Observation:
    repository: str
    branch: str
    revision: str


class JulesScmRevisionVerifierTests(unittest.TestCase):
    def test_exact_match_is_the_only_path_to_verified_true(self):
        binding = verify_jules_scm_revision(
            expected_repository="MSKazemi/idkmesh",
            expected_branch="idkmesh/wu-123",
            expected_revision=REVISION,
            observed=Observation(
                repository="MSKazemi/idkmesh",
                branch="idkmesh/wu-123",
                revision=REVISION,
            ),
            connection_id="github-main",
        )

        self.assertEqual(binding.github_owner, "MSKazemi")
        self.assertEqual(binding.github_repo, "idkmesh")
        self.assertEqual(binding.branch, "idkmesh/wu-123")
        self.assertEqual(binding.revision, REVISION)
        self.assertTrue(binding.verified)

    def test_repository_match_is_case_insensitive_but_output_is_authorized_form(self):
        binding = verify_jules_scm_revision(
            expected_repository="MSKazemi/idkmesh",
            expected_branch="main",
            expected_revision=REVISION.upper(),
            observed=Observation(
                repository="mskazemi/IDKMESH",
                branch="main",
                revision=REVISION,
            ),
            connection_id="github-main",
        )
        self.assertEqual(binding.github_owner, "MSKazemi")
        self.assertEqual(binding.github_repo, "idkmesh")
        self.assertEqual(binding.revision, REVISION)

    def test_each_identity_mismatch_fails_as_conflict(self):
        cases = [
            Observation("other/repo", "idkmesh/wu-123", REVISION),
            Observation("MSKazemi/idkmesh", "other", REVISION),
            Observation(
                "MSKazemi/idkmesh",
                "idkmesh/wu-123",
                "1" + REVISION[1:],
            ),
        ]
        expected_fields = ["repository", "branch", "revision"]

        for observed, field in zip(cases, expected_fields):
            with self.subTest(field=field):
                with self.assertRaises(ConnectorError) as caught:
                    verify_jules_scm_revision(
                        expected_repository="MSKazemi/idkmesh",
                        expected_branch="idkmesh/wu-123",
                        expected_revision=REVISION,
                        observed=observed,
                        connection_id="github-main",
                    )
                self.assertEqual(caught.exception.code, "conflict")
                self.assertIn(
                    field,
                    caught.exception.details["mismatched_fields"],
                )

    def test_malformed_expected_identity_is_programmer_configuration_error(self):
        cases = [
            {"expected_repository": "bad"},
            {"expected_branch": ""},
            {"expected_revision": "main"},
            {"connection_id": ""},
        ]
        base = {
            "expected_repository": "MSKazemi/idkmesh",
            "expected_branch": "main",
            "expected_revision": REVISION,
            "observed": Observation(
                "MSKazemi/idkmesh",
                "main",
                REVISION,
            ),
            "connection_id": "github-main",
        }
        for override in cases:
            with self.subTest(override=override):
                values = {**base, **override}
                with self.assertRaises(ValueError):
                    verify_jules_scm_revision(**values)

    def test_malformed_observation_is_normalization_failure(self):
        cases = [
            Observation("bad", "main", REVISION),
            Observation("MSKazemi/idkmesh", "", REVISION),
            Observation("MSKazemi/idkmesh", "main", "main"),
            object(),
        ]
        for observed in cases:
            with self.subTest(observed=observed):
                with self.assertRaises(ConnectorError) as caught:
                    verify_jules_scm_revision(
                        expected_repository="MSKazemi/idkmesh",
                        expected_branch="main",
                        expected_revision=REVISION,
                        observed=observed,
                        connection_id="github-main",
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_binding_carries_no_dispatch_or_integration_authority(self):
        binding = verify_jules_scm_revision(
            expected_repository="MSKazemi/idkmesh",
            expected_branch="main",
            expected_revision=REVISION,
            observed=Observation(
                "MSKazemi/idkmesh",
                "main",
                REVISION,
            ),
            connection_id="github-main",
        )
        for field in (
            "dispatch_approved",
            "candidate_ready",
            "accepted",
            "verification_result",
            "merge_authorized",
            "integration_authorized",
        ):
            self.assertFalse(hasattr(binding, field))


if __name__ == "__main__":
    unittest.main()
