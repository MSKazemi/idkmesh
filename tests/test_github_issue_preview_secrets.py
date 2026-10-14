"""Credential refusal in the GitHub issue preview (E5, #672).

Issue text is copied into the WorkUnit objective, so a token pasted into a public
issue must stop the preview. Sample credentials are assembled from fragments so
this file holds no complete credential-shaped literal.
"""

from __future__ import annotations

import json
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    GitHubIssueWorkPolicy,
    parse_github_issue_snapshot,
    preview_github_issue_work_unit,
)

SHA = "0123456789abcdef0123456789abcdef01234567"
REPOSITORY = "MSKazemi/idkmesh"
GITHUB_TOKEN = "gh" + "p_" + "A1b2C3d4E5" * 4
SK_KEY = "sk" + "-ant-" + "x1Y2" * 10
PEM_HEADER = "-----BEGIN " + "OPENSSH PRIVATE" + " KEY-----"


def _snapshot(**overrides):
    raw = {
        "id": 9001,
        "number": 77,
        "title": "Add a bounded feature",
        "body": "Implement the requested behavior and add tests.",
        "state": "open",
        "locked": False,
        "user": {"login": "contributor", "id": 88},
        "author_association": "CONTRIBUTOR",
        "labels": [{"name": "agent-ready"}],
        "html_url": f"https://github.com/{REPOSITORY}/issues/77",
        "updated_at": "2026-09-24T01:00:00Z",
    }
    raw.update(overrides)
    return parse_github_issue_snapshot(raw, repository=REPOSITORY, expected_number=77)


def _policy(**overrides):
    values = {
        "repository": REPOSITORY,
        "allowed_paths": ("idkmesh/**", "tests/**"),
        "forbidden_paths": (".github/**", "SECURITY.md"),
    }
    values.update(overrides)
    return GitHubIssueWorkPolicy(**values)


def _preview(snapshot, **kwargs):
    policy = kwargs.pop("policy", None) or _policy()
    return preview_github_issue_work_unit(
        snapshot, source_revision=SHA, policy=policy, **kwargs
    )


class CredentialRefusalTests(unittest.TestCase):
    def assert_refused(self, caught, *, rules, fields, secret) -> None:
        error = caught.exception
        self.assertEqual(error.code, "policy_denied")
        self.assertEqual(error.details["rules"], rules)
        self.assertEqual(error.details["fields"], fields)
        # Neither the message, the details nor the serialised envelope echo it.
        blob = str(error) + json.dumps(error.details) + json.dumps(error.to_envelope())
        self.assertNotIn(secret, blob)

    def test_credential_in_the_body_is_refused(self) -> None:
        for rule, secret in (
            ("github_token", GITHUB_TOKEN),
            ("api_key_sk", SK_KEY),
            ("private_key_block", PEM_HEADER),
        ):
            with self.subTest(rule=rule):
                snapshot = _snapshot(body=f"It fails when I use {secret} here.")
                with self.assertRaises(ConnectorError) as caught:
                    _preview(snapshot)
                self.assert_refused(
                    caught, rules=[rule], fields=["body"], secret=secret
                )

    def test_credential_in_the_title_is_refused(self) -> None:
        with self.assertRaises(ConnectorError) as caught:
            _preview(_snapshot(title=f"leak {GITHUB_TOKEN}"))
        self.assert_refused(
            caught, rules=["github_token"], fields=["title"], secret=GITHUB_TOKEN
        )

    def test_credential_in_snapshot_metadata_is_refused(self) -> None:
        with self.assertRaises(ConnectorError) as caught:
            _preview(_snapshot(labels=[{"name": GITHUB_TOKEN}]))
        self.assert_refused(
            caught, rules=["github_token"], fields=["metadata"], secret=GITHUB_TOKEN
        )

    def test_several_findings_report_each_rule_and_field_once(self) -> None:
        # One string reports its first matching rule only, so use two fields.
        snapshot = _snapshot(title=f"a {SK_KEY}", body=f"b {GITHUB_TOKEN} and {GITHUB_TOKEN}")
        with self.assertRaises(ConnectorError) as caught:
            _preview(snapshot)
        self.assert_refused(
            caught,
            rules=["api_key_sk", "github_token"],
            fields=["body", "title"],
            secret=SK_KEY,
        )

    def test_intake_form_path_is_covered(self) -> None:
        # The scan runs on the raw snapshot, before the form is parsed, so form
        # parsing cannot be used to carry a credential into the task text.
        snapshot = _snapshot(body=f"### Task\n\nUse {GITHUB_TOKEN}\n")
        with self.assertRaises(ConnectorError) as caught:
            _preview(snapshot, use_intake_form=True)
        self.assertEqual(caught.exception.details["fields"], ["body"])

    def test_unscannable_text_is_refused_not_passed(self) -> None:
        snapshot = _snapshot(body="x" * 300_000)
        with self.assertRaises(ConnectorError) as caught:
            _preview(snapshot, policy=_policy(max_body_chars=1_000_000))
        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertIn("could not be fully scanned", caught.exception.message)
        self.assertEqual(caught.exception.details["reasons"], ["string_too_large"])

    def test_ordinary_text_still_previews(self) -> None:
        bodies = (
            "Implement the requested behavior and add tests.",
            "Docs should show scheme://user:password@host for basic auth.",
            "Use a bearer token-based-authentication header scheme.",
            "The password field and the token budget are unrelated words.",
            "Commit 0123456789abcdef0123456789abcdef01234567 broke this.",
            "Set JULES_API_KEY in the environment (env:JULES_API_KEY).",
        )
        for body in bodies:
            with self.subTest(body=body):
                preview = _preview(_snapshot(body=body))
                self.assertIn(body, preview.work_unit["objective"])


if __name__ == "__main__":
    unittest.main()
