import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_sources import (
    JulesSourceService,
    parse_jules_source,
)


VALID_SOURCE = {
    "name": "sources/github/MSKazemi/idkmesh",
    "id": "github/MSKazemi/idkmesh",
    "githubRepo": {
        "owner": "MSKazemi",
        "repo": "idkmesh",
        "isPrivate": False,
        "defaultBranch": {"displayName": "main"},
        "branches": [
            {"displayName": "main"},
            {"displayName": "develop"},
            {"displayName": "develop"},
        ],
    },
}


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = VALID_SOURCE if response is None else response
        self.error = error
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        if self.error is not None:
            raise self.error
        return self.response


class JulesSourceTests(unittest.TestCase):
    def test_exact_source_repository_and_branch_validate(self):
        client = FakeClient()
        service = JulesSourceService(client, connection_id="jules-main")
        source = service.validate_github_source(
            source_name="sources/github/MSKazemi/idkmesh",
            github_owner="MSKazemi",
            github_repo="idkmesh",
            starting_branch="main",
        )
        self.assertEqual(source.github_owner, "MSKazemi")
        self.assertEqual(source.github_repo, "idkmesh")
        self.assertEqual(source.default_branch, "main")
        self.assertEqual(source.branches, ("main", "develop"))
        self.assertEqual(
            client.calls,
            [("/sources/github/MSKazemi/idkmesh", None)],
        )

    def test_repository_identity_comparison_is_case_insensitive(self):
        service = JulesSourceService(FakeClient(), connection_id="jules-main")
        source = service.validate_github_source(
            source_name="sources/github/MSKazemi/idkmesh",
            github_owner="mskazemi",
            github_repo="IDKMESH",
            starting_branch="main",
        )
        self.assertEqual(source.name, "sources/github/MSKazemi/idkmesh")

    def test_wrong_repository_fails_closed(self):
        service = JulesSourceService(FakeClient(), connection_id="jules-main")
        with self.assertRaises(ConnectorError) as caught:
            service.validate_github_source(
                source_name="sources/github/MSKazemi/idkmesh",
                github_owner="someone-else",
                github_repo="idkmesh",
                starting_branch="main",
            )
        self.assertEqual(caught.exception.code, "configuration_error")
        details = caught.exception.to_envelope()["error"]["details"]
        self.assertEqual(details["expected_repository"], "someone-else/idkmesh")
        self.assertEqual(details["observed_repository"], "MSKazemi/idkmesh")

    def test_unadvertised_starting_branch_fails_closed(self):
        service = JulesSourceService(FakeClient(), connection_id="jules-main")
        with self.assertRaises(ConnectorError) as caught:
            service.validate_github_source(
                source_name="sources/github/MSKazemi/idkmesh",
                github_owner="MSKazemi",
                github_repo="idkmesh",
                starting_branch="feature/not-connected",
            )
        self.assertEqual(caught.exception.code, "configuration_error")

    def test_provider_not_found_becomes_source_not_connected(self):
        service = JulesSourceService(
            FakeClient(
                error=ConnectorError(
                    code="not_found",
                    message="provider resource missing",
                    connection_id="jules-main",
                )
            ),
            connection_id="jules-main",
        )
        with self.assertRaises(ConnectorError) as caught:
            service.get_source("sources/github/MSKazemi/idkmesh")
        self.assertEqual(caught.exception.code, "source_not_connected")

    def test_wrong_source_name_from_provider_is_normalization_error(self):
        payload = dict(VALID_SOURCE)
        payload["name"] = "sources/github/other/repo"
        service = JulesSourceService(FakeClient(response=payload), connection_id="jules-main")
        with self.assertRaises(ConnectorError) as caught:
            service.get_source("sources/github/MSKazemi/idkmesh")
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_malformed_github_metadata_fails_closed(self):
        cases = [
            {"name": "sources/x", "id": "x"},
            {
                "name": "sources/x",
                "id": "x",
                "githubRepo": {"owner": "a", "repo": "b", "branches": "main"},
            },
            {
                "name": "sources/x",
                "id": "x",
                "githubRepo": {
                    "owner": "a",
                    "repo": "b",
                    "defaultBranch": "main",
                },
            },
            {
                "name": "sources/x",
                "id": "x",
                "githubRepo": {
                    "owner": "a",
                    "repo": "b",
                    "branches": [{"displayName": ""}],
                },
            },
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ConnectorError) as caught:
                    parse_jules_source(
                        payload,
                        connection_id="jules-main",
                        expected_name=payload["name"],
                    )
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_invalid_configured_source_name_never_reaches_client(self):
        client = FakeClient()
        service = JulesSourceService(client, connection_id="jules-main")
        for source_name in (
            "github/MSKazemi/idkmesh",
            "sources/",
            "sources/x?filter=y",
            "https://evil.example/source",
        ):
            with self.subTest(source_name=source_name):
                with self.assertRaises(ConnectorError) as caught:
                    service.get_source(source_name)
                self.assertEqual(caught.exception.code, "configuration_error")
        self.assertEqual(client.calls, [])

    def test_starting_branch_can_be_default_even_if_branch_list_is_omitted(self):
        payload = {
            "name": "sources/github/MSKazemi/idkmesh",
            "id": "github/MSKazemi/idkmesh",
            "githubRepo": {
                "owner": "MSKazemi",
                "repo": "idkmesh",
                "defaultBranch": {"displayName": "main"},
            },
        }
        service = JulesSourceService(FakeClient(response=payload), connection_id="jules-main")
        source = service.validate_github_source(
            source_name=payload["name"],
            github_owner="MSKazemi",
            github_repo="idkmesh",
            starting_branch="main",
        )
        self.assertEqual(source.default_branch, "main")
        self.assertEqual(source.branches, ())


if __name__ == "__main__":
    unittest.main()
