import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_actions import (
    JulesOperatorActionService,
    OperatorActionAuthorization,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def post_json(self, path, *, body=None):
        self.calls.append((path, body))
        return {}


def _auth(action, *, approved=True, session_name="sessions/123"):
    return OperatorActionAuthorization(
        authorization_id=f"auth-{action}",
        actor="maintainer@example",
        action=action,
        session_name=session_name,
        approved=approved,
    )


class JulesOperatorActionTests(unittest.TestCase):
    def test_approve_plan_requires_matching_explicit_authorization(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        receipt = service.approve_plan(
            "sessions/123",
            authorization=_auth("approve_plan"),
        )

        self.assertEqual(client.calls, [("/sessions/123:approvePlan", {})])
        self.assertEqual(receipt.action, "approve_plan")
        self.assertEqual(receipt.authorization_id, "auth-approve_plan")

    def test_send_message_requires_matching_explicit_authorization(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        receipt = service.send_message(
            "sessions/123",
            prompt="Please add the missing regression test.",
            authorization=_auth("send_message"),
        )

        self.assertEqual(
            client.calls,
            [
                (
                    "/sessions/123:sendMessage",
                    {"prompt": "Please add the missing regression test."},
                )
            ],
        )
        self.assertEqual(receipt.action, "send_message")
        self.assertFalse(hasattr(receipt, "prompt"))

    def test_denied_authorization_never_calls_provider(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        with self.assertRaises(ConnectorError) as caught:
            service.approve_plan(
                "sessions/123",
                authorization=_auth("approve_plan", approved=False),
            )

        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertEqual(client.calls, [])

    def test_action_mismatch_never_calls_provider(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        with self.assertRaises(ConnectorError) as caught:
            service.approve_plan(
                "sessions/123",
                authorization=_auth("send_message"),
            )

        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertEqual(client.calls, [])

    def test_session_mismatch_never_calls_provider(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        with self.assertRaises(ConnectorError) as caught:
            service.send_message(
                "sessions/123",
                prompt="continue",
                authorization=_auth(
                    "send_message",
                    session_name="sessions/other",
                ),
            )

        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertEqual(client.calls, [])

    def test_empty_message_fails_before_authorization_or_provider(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")

        with self.assertRaisesRegex(ValueError, "prompt"):
            service.send_message(
                "sessions/123",
                prompt=" ",
                authorization=_auth("send_message"),
            )

        self.assertEqual(client.calls, [])

    def test_invalid_session_names_fail_locally(self):
        client = FakeClient()
        service = JulesOperatorActionService(client, connection_id="jules-main")
        with self.assertRaisesRegex(ValueError, "session_name"):
            service.approve_plan(
                "sessions/a/b",
                authorization=_auth("approve_plan"),
            )
        self.assertEqual(client.calls, [])

    def test_authorization_object_validates_action_and_boolean(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            OperatorActionAuthorization(
                authorization_id="a",
                actor="owner",
                action="merge",
                session_name="sessions/123",
                approved=True,
            )

        with self.assertRaisesRegex(ValueError, "boolean"):
            OperatorActionAuthorization(
                authorization_id="a",
                actor="owner",
                action="approve_plan",
                session_name="sessions/123",
                approved=1,
            )


if __name__ == "__main__":
    unittest.main()
