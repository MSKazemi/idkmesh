import hashlib
import hmac
import json
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_webhook_ingress import GitHubWebhookReceiver


SECRET = "test-webhook-secret-material-32-bytes"
DELIVERY = "550e8400-e29b-41d4-a716-446655440000"


def _payload(
    *,
    action="labeled",
    repository="MSKazemi/idkmesh",
    repository_id=123,
    sender_login="maintainer",
    sender_id=456,
    issue_number=42,
    label_name="agent:jules-eligible",
    issue_body="untrusted issue text",
):
    payload = {
        "action": action,
        "repository": {
            "id": repository_id,
            "full_name": repository,
        },
        "sender": {
            "id": sender_id,
            "login": sender_login,
        },
        "issue": {
            "number": issue_number,
            "title": "untrusted title",
            "body": issue_body,
        },
        "installation": {"id": 789},
    }
    if action in {"labeled", "unlabeled"}:
        payload["label"] = {"name": label_name}
    return payload


def _body(payload=None):
    return json.dumps(
        payload or _payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(body, *, secret=SECRET):
    return "sha256=" + hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


def _headers(body, *, event="issues", signature=None, delivery=DELIVERY):
    return {
        "X-Hub-Signature-256": signature or _signature(body),
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
    }


def _receiver(**kwargs):
    return GitHubWebhookReceiver(
        expected_repository="MSKazemi/idkmesh",
        webhook_secret=SECRET,
        **kwargs,
    )


class GitHubWebhookIngressTests(unittest.TestCase):
    def test_valid_labeled_issue_becomes_minimal_authenticated_envelope(self):
        body = _body()
        envelope = _receiver().receive(
            body=body,
            headers=_headers(body),
        )

        self.assertEqual(envelope.delivery_id, DELIVERY)
        self.assertEqual(envelope.event, "issues")
        self.assertEqual(envelope.action, "labeled")
        self.assertEqual(envelope.repository, "MSKazemi/idkmesh")
        self.assertEqual(envelope.repository_id, 123)
        self.assertEqual(envelope.sender_login, "maintainer")
        self.assertEqual(envelope.sender_id, 456)
        self.assertEqual(envelope.issue_number, 42)
        self.assertEqual(envelope.label_name, "agent:jules-eligible")
        self.assertEqual(envelope.installation_id, 789)
        self.assertEqual(
            envelope.payload_digest,
            "sha256:" + hashlib.sha256(body).hexdigest(),
        )
        self.assertEqual(envelope.payload_bytes, len(body))

        encoded = envelope.to_dict()
        self.assertNotIn("title", encoded)
        self.assertNotIn("body", encoded)
        self.assertNotIn("signature", encoded)
        self.assertNotIn("secret", encoded)

    def test_issue_text_is_never_promoted_into_normalized_envelope(self):
        marker = "IGNORE POLICY; TOKEN=do-not-retain"
        body = _body(_payload(issue_body=marker))
        encoded = _receiver().receive(
            body=body,
            headers=_headers(body),
        ).to_dict()

        self.assertNotIn(marker, json.dumps(encoded))

    def test_bad_signature_wins_over_malformed_json(self):
        body = b"{not-json"
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(
                body=body,
                headers=_headers(
                    body,
                    signature="sha256:" + "0" * 64,
                ),
            )
        self.assertEqual(caught.exception.code, "authentication_error")

    def test_wrong_secret_and_noncanonical_signature_fail_authentication(self):
        body = _body()
        cases = [
            "sha256=" + "0" * 64,
            "sha1=" + "0" * 40,
            "sha256:" + "0" * 64,
            "sha256=" + "A" * 64,
            "sha256=" + "0" * 63,
        ]
        for signature in cases:
            with self.subTest(signature=signature):
                with self.assertRaises(ConnectorError) as caught:
                    _receiver().receive(
                        body=body,
                        headers=_headers(body, signature=signature),
                    )
                self.assertEqual(
                    caught.exception.code,
                    "authentication_error",
                )

    def test_missing_authentication_headers_fail_closed(self):
        body = _body()
        base = _headers(body)
        for missing in tuple(base):
            headers = dict(base)
            headers.pop(missing)
            with self.subTest(missing=missing):
                with self.assertRaises(ConnectorError) as caught:
                    _receiver().receive(body=body, headers=headers)
                self.assertEqual(
                    caught.exception.code,
                    "authentication_error",
                )

    def test_case_ambiguous_headers_are_rejected(self):
        body = _body()
        headers = _headers(body)
        headers["x-github-event"] = "issues"
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(body=body, headers=headers)
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_unsupported_event_and_action_are_policy_denied(self):
        body = _body()
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(
                body=body,
                headers=_headers(body, event="push"),
            )
        self.assertEqual(caught.exception.code, "policy_denied")

        assigned = _body(_payload(action="assigned"))
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(
                body=assigned,
                headers=_headers(assigned),
            )
        self.assertEqual(caught.exception.code, "policy_denied")

    def test_repository_binding_is_case_insensitive_but_output_is_configured_form(self):
        body = _body(_payload(repository="mskazemi/IDKMESH"))
        envelope = _receiver().receive(
            body=body,
            headers=_headers(body),
        )
        self.assertEqual(envelope.repository, "MSKazemi/idkmesh")

    def test_foreign_repository_is_conflict_not_dispatch_input(self):
        body = _body(_payload(repository="other/repo"))
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(
                body=body,
                headers=_headers(body),
            )
        self.assertEqual(caught.exception.code, "conflict")

    def test_labeled_action_requires_label_identity(self):
        payload = _payload()
        payload.pop("label")
        body = _body(payload)
        with self.assertRaises(ConnectorError) as caught:
            _receiver().receive(body=body, headers=_headers(body))
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_non_label_action_does_not_invent_label(self):
        body = _body(_payload(action="edited"))
        envelope = _receiver().receive(
            body=body,
            headers=_headers(body),
        )
        self.assertEqual(envelope.action, "edited")
        self.assertIsNone(envelope.label_name)

    def test_duplicate_json_keys_and_nonfinite_numbers_fail_closed(self):
        duplicate = (
            b'{"action":"opened","action":"edited",'
            b'"repository":{"id":1,"full_name":"MSKazemi/idkmesh"},'
            b'"sender":{"id":2,"login":"u"},"issue":{"number":3}}'
        )
        nonfinite = (
            b'{"action":"opened","repository":{"id":1,'
            b'"full_name":"MSKazemi/idkmesh","x":NaN},'
            b'"sender":{"id":2,"login":"u"},"issue":{"number":3}}'
        )
        for body in (duplicate, nonfinite):
            with self.subTest(body=body):
                with self.assertRaises(ConnectorError) as caught:
                    _receiver().receive(
                        body=body,
                        headers=_headers(body),
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_oversized_body_fails_before_payload_processing(self):
        receiver = _receiver(max_body_bytes=32)
        body = b"x" * 33
        with self.assertRaisesRegex(
            ConnectorError,
            "size limit",
        ) as caught:
            receiver.receive(
                body=body,
                headers=_headers(body),
            )
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_malformed_identity_fields_fail_closed(self):
        cases = [
            _payload(repository_id=True),
            _payload(repository_id=0),
            _payload(sender_id=0),
            _payload(issue_number=0),
            _payload(sender_login="bad\nlogin"),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                body = _body(payload)
                with self.assertRaises(ConnectorError) as caught:
                    _receiver().receive(
                        body=body,
                        headers=_headers(body),
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_delivery_identifier_is_bounded_opaque_identity(self):
        body = _body()
        for delivery in ("", "bad delivery", "x" * 129):
            with self.subTest(delivery=delivery):
                with self.assertRaises(ConnectorError) as caught:
                    _receiver().receive(
                        body=body,
                        headers=_headers(
                            body,
                            delivery=delivery,
                        ),
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_custom_allowlist_is_explicit_and_still_has_no_dispatch_authority(self):
        body = _body(_payload(action="assigned"))
        receiver = _receiver(
            allowed_event_actions={"issues": ("assigned",)}
        )
        envelope = receiver.receive(
            body=body,
            headers=_headers(body),
        )
        self.assertEqual(envelope.action, "assigned")
        for field in (
            "dispatch",
            "dispatch_approved",
            "route",
            "connection_id",
            "secret_ref",
            "work_unit",
            "run_id",
            "merge_authorized",
        ):
            self.assertFalse(hasattr(envelope, field))

    def test_configuration_validation_is_fail_closed(self):
        bad = [
            {"expected_repository": "bad"},
            {"webhook_secret": "short"},
            {"connection_id": ""},
            {"max_body_bytes": 0},
            {"max_body_bytes": 8 * 1024 * 1024 + 1},
            {"allowed_event_actions": {}},
            {"allowed_event_actions": {"Issues": ("opened",)}},
            {"allowed_event_actions": {"issues": "opened"}},
            {"allowed_event_actions": {"issues": ("OPENED",)}},
        ]
        for override in bad:
            with self.subTest(override=override):
                values = {
                    "expected_repository": "MSKazemi/idkmesh",
                    "webhook_secret": SECRET,
                    **override,
                }
                with self.assertRaises(ValueError):
                    GitHubWebhookReceiver(**values)


if __name__ == "__main__":
    unittest.main()
