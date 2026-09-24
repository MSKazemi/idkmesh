import hashlib
import hmac
import json
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_webhook_ingress import (
    GitHubWebhookEnvelope,
    parse_github_webhook,
    verify_github_webhook_signature,
)


SECRET = "test-webhook-secret"


def _payload(event="issues", *, action="labeled"):
    base = {
        "action": action,
        "repository": {
            "id": 123,
            "full_name": "MSKazemi/idkmesh",
        },
        "sender": {
            "login": "maintainer",
            "id": 42,
            "type": "User",
        },
    }
    if event == "issues":
        base["issue"] = {
            "number": 77,
            "author_association": "OWNER",
        }
        if action in {"labeled", "unlabeled"}:
            base["label"] = {"name": "agent-ready"}
    elif event == "issue_comment":
        base["issue"] = {
            "number": 77,
            "author_association": "CONTRIBUTOR",
        }
        base["comment"] = {
            "id": 555,
            "author_association": "MEMBER",
        }
    elif event == "pull_request":
        base["number"] = 88
        base["pull_request"] = {
            "number": 88,
            "author_association": "COLLABORATOR",
        }
    return base


def _request(event="issues", *, payload=None, action="labeled", secret=SECRET):
    value = _payload(event, action=action) if payload is None else payload
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Delivery": "delivery-123",
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": signature,
    }
    return headers, body


class GitHubWebhookIngressTests(unittest.TestCase):
    def test_valid_issue_label_event_is_normalized(self):
        headers, body = _request()
        envelope = parse_github_webhook(
            headers,
            body,
            secret=SECRET,
            expected_repository="MSKazemi/idkmesh",
            connection_id="github-main",
        )
        self.assertIsInstance(envelope, GitHubWebhookEnvelope)
        self.assertEqual(envelope.delivery_id, "delivery-123")
        self.assertEqual(envelope.event, "issues")
        self.assertEqual(envelope.action, "labeled")
        self.assertEqual(envelope.repository, "MSKazemi/idkmesh")
        self.assertEqual(envelope.subject_number, 77)
        self.assertEqual(envelope.label_name, "agent-ready")
        self.assertEqual(envelope.author_association, "OWNER")
        self.assertTrue(envelope.payload_digest.startswith("sha256:"))
        rendered = json.dumps(envelope.to_dict(), sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn('"issue"', rendered)

    def test_signature_binds_exact_raw_bytes(self):
        headers, body = _request()
        verify_github_webhook_signature(
            body,
            headers["X-Hub-Signature-256"],
            secret=SECRET,
        )
        with self.assertRaises(ConnectorError) as caught:
            verify_github_webhook_signature(
                body + b" ",
                headers["X-Hub-Signature-256"],
                secret=SECRET,
            )
        self.assertEqual(caught.exception.code, "authentication_error")

    def test_missing_malformed_or_wrong_signature_is_generic(self):
        headers, body = _request()
        for signature in (
            None,
            "sha1=abc",
            "sha256=xyz",
            "sha256=" + "0" * 64,
        ):
            with self.subTest(signature=signature):
                with self.assertRaises(ConnectorError) as caught:
                    verify_github_webhook_signature(
                        body,
                        signature,
                        secret=SECRET,
                        connection_id="github-main",
                    )
                self.assertEqual(caught.exception.code, "authentication_error")
                self.assertNotIn(SECRET, str(caught.exception))

    def test_header_names_are_case_insensitive(self):
        headers, body = _request()
        lowered = {key.lower(): value for key, value in headers.items()}
        envelope = parse_github_webhook(
            lowered,
            body,
            secret=SECRET,
            expected_repository="MSKazemi/idkmesh",
        )
        self.assertEqual(envelope.subject_number, 77)

    def test_unsupported_event_fails_policy_before_payload_authority(self):
        headers, body = _request("issues")
        headers["X-GitHub-Event"] = "push"
        # Signature still authenticates the raw body; event header is separately
        # admitted by the configured allowlist.
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "policy_denied")

    def test_wrong_repository_fails_closed(self):
        headers, body = _request()
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="other/repo",
            )
        self.assertEqual(caught.exception.code, "policy_denied")

    def test_issue_comment_uses_comment_author_association(self):
        headers, body = _request("issue_comment", action="created")
        envelope = parse_github_webhook(
            headers,
            body,
            secret=SECRET,
            expected_repository="MSKazemi/idkmesh",
        )
        self.assertEqual(envelope.event, "issue_comment")
        self.assertEqual(envelope.subject_number, 77)
        self.assertEqual(envelope.author_association, "MEMBER")
        self.assertIsNone(envelope.label_name)

    def test_pull_request_subject_is_normalized(self):
        headers, body = _request("pull_request", action="synchronize")
        envelope = parse_github_webhook(
            headers,
            body,
            secret=SECRET,
            expected_repository="MSKazemi/idkmesh",
        )
        self.assertEqual(envelope.subject_number, 88)
        self.assertEqual(envelope.author_association, "COLLABORATOR")

    def test_duplicate_json_keys_fail_closed(self):
        body = (
            b'{"action":"labeled","action":"opened",'
            b'"repository":{"id":123,"full_name":"MSKazemi/idkmesh"},'
            b'"sender":{"login":"x","id":1,"type":"User"},'
            b'"issue":{"number":1,"author_association":"OWNER"},'
            b'"label":{"name":"agent-ready"}}'
        )
        signature = "sha256=" + hmac.new(
            SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-GitHub-Delivery": "delivery-dup",
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": signature,
        }
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_nonstandard_json_constants_fail_closed(self):
        headers, body = _request()
        body = body.replace(b'"id":123', b'"id":NaN')
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(
            SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_body_size_limit_is_enforced(self):
        headers, body = _request()
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
                max_body_bytes=len(body) - 1,
            )
        self.assertEqual(caught.exception.code, "policy_denied")

    def test_content_type_must_be_json_when_present(self):
        headers, body = _request()
        headers["Content-Type"] = "text/plain"
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "configuration_error")

    def test_label_action_requires_label_metadata(self):
        payload = _payload("issues", action="labeled")
        del payload["label"]
        headers, body = _request("issues", payload=payload)
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_unknown_author_association_fails_closed(self):
        payload = _payload()
        payload["issue"]["author_association"] = "SUPERADMIN"
        headers, body = _request(payload=payload)
        with self.assertRaises(ConnectorError) as caught:
            parse_github_webhook(
                headers,
                body,
                secret=SECRET,
                expected_repository="MSKazemi/idkmesh",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_envelope_keeps_digest_not_raw_body(self):
        headers, body = _request()
        envelope = parse_github_webhook(
            headers,
            body,
            secret=SECRET,
            expected_repository="MSKazemi/idkmesh",
        )
        self.assertEqual(
            envelope.payload_digest,
            "sha256:" + hashlib.sha256(body).hexdigest(),
        )
        self.assertFalse(hasattr(envelope, "payload"))
        self.assertFalse(hasattr(envelope, "body"))


if __name__ == "__main__":
    unittest.main()
