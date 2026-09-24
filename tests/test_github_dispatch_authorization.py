import unittest

from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    TrustedGitHubActor,
    authorize_github_dispatch,
)
from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope


def _envelope(**overrides):
    values = {
        "delivery_id": "delivery-123",
        "event": "issues",
        "action": "labeled",
        "repository": "MSKazemi/idkmesh",
        "repository_id": 123,
        "sender_login": "TrustedMaintainer",
        "sender_id": 42,
        "issue_number": 77,
        "label_name": "agent-ready",
        "installation_id": 9001,
        "payload_digest": "sha256:" + "a" * 64,
        "payload_bytes": 512,
    }
    values.update(overrides)
    return GitHubWebhookEnvelope(**values)


def _policy(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "dispatch_labels": frozenset({"agent-ready"}),
        "trusted_actors": (
            TrustedGitHubActor(
                actor_id=42,
                login="TrustedMaintainer",
                role="maintainer",
            ),
        ),
    }
    values.update(overrides)
    return GitHubDispatchAuthorizationPolicy(**values)


class GitHubDispatchAuthorizationTests(unittest.TestCase):
    def test_explicit_trusted_actor_label_is_authorized(self):
        decision = authorize_github_dispatch(
            _envelope(),
            _policy(),
        )
        self.assertTrue(decision.authorized)
        self.assertEqual(decision.reasons, ())
        self.assertEqual(decision.actor_role, "maintainer")
        self.assertTrue(
            decision.to_dict()["secret_resolution_allowed"]
        )
        self.assertFalse(decision.to_dict()["dispatch_performed"])

    def test_login_and_label_match_case_insensitively(self):
        decision = authorize_github_dispatch(
            _envelope(
                sender_login="trustedmaintainer",
                label_name="AGENT-READY",
            ),
            _policy(),
        )
        self.assertTrue(decision.authorized)

    def test_numeric_actor_id_is_primary_trust_binding(self):
        decision = authorize_github_dispatch(
            _envelope(
                sender_id=999,
                sender_login="TrustedMaintainer",
            ),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn("actor_id_not_trusted", decision.reasons)

    def test_actor_login_must_match_configured_identity_for_trusted_id(self):
        decision = authorize_github_dispatch(
            _envelope(sender_login="renamed-or-spoofed"),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn("actor_login_mismatch", decision.reasons)

    def test_role_must_be_explicitly_allowed(self):
        policy = _policy(
            trusted_actors=(
                TrustedGitHubActor(
                    actor_id=42,
                    login="TrustedMaintainer",
                    role="triager",
                ),
            ),
        )
        decision = authorize_github_dispatch(
            _envelope(),
            policy,
        )
        self.assertFalse(decision.authorized)
        self.assertIn(
            "actor_role_not_authorized",
            decision.reasons,
        )

        allowed = authorize_github_dispatch(
            _envelope(),
            _policy(
                trusted_actors=(
                    TrustedGitHubActor(
                        actor_id=42,
                        login="TrustedMaintainer",
                        role="triager",
                    ),
                ),
                allowed_roles=frozenset({"triager"}),
            ),
        )
        self.assertTrue(allowed.authorized)

    def test_repository_event_action_and_label_all_fail_closed(self):
        cases = (
            (
                _envelope(repository="other/repo"),
                "repository_not_authorized",
            ),
            (
                _envelope(event="pull_request"),
                "event_not_dispatchable",
            ),
            (
                _envelope(action="opened", label_name=None),
                "action_not_dispatchable",
            ),
            (
                _envelope(label_name="bug"),
                "dispatch_label_not_authorized",
            ),
            (
                _envelope(issue_number=None),
                "issue_number_missing",
            ),
        )
        for envelope, reason in cases:
            with self.subTest(reason=reason):
                decision = authorize_github_dispatch(
                    envelope,
                    _policy(),
                )
                self.assertFalse(decision.authorized)
                self.assertIn(reason, decision.reasons)

    def test_installation_binding_is_optional_but_strict_when_configured(self):
        policy = _policy(
            allowed_installation_ids=frozenset({9001})
        )
        self.assertTrue(
            authorize_github_dispatch(
                _envelope(),
                policy,
            ).authorized
        )

        missing = authorize_github_dispatch(
            _envelope(installation_id=None),
            policy,
        )
        self.assertFalse(missing.authorized)
        self.assertIn("installation_id_missing", missing.reasons)

        wrong = authorize_github_dispatch(
            _envelope(installation_id=9002),
            policy,
        )
        self.assertFalse(wrong.authorized)
        self.assertIn(
            "installation_not_authorized",
            wrong.reasons,
        )

    def test_automation_role_can_be_explicitly_enabled(self):
        policy = _policy(
            trusted_actors=(
                TrustedGitHubActor(
                    actor_id=77,
                    login="dispatch-bot[bot]",
                    role="automation",
                ),
            ),
            allowed_roles=frozenset({"automation"}),
        )
        decision = authorize_github_dispatch(
            _envelope(
                sender_id=77,
                sender_login="dispatch-bot[bot]",
            ),
            policy,
        )
        self.assertTrue(decision.authorized)

    def test_policy_rejects_malformed_repository(self):
        with self.assertRaisesRegex(ValueError, "owner/name"):
            _policy(repository="not-a-repository")

    def test_policy_rejects_duplicate_actor_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            _policy(
                trusted_actors=(
                    TrustedGitHubActor(
                        actor_id=42,
                        login="one",
                        role="maintainer",
                    ),
                    TrustedGitHubActor(
                        actor_id=42,
                        login="two",
                        role="owner",
                    ),
                )
            )

    def test_policy_rejects_unknown_roles_and_empty_authority_sets(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            TrustedGitHubActor(
                actor_id=42,
                login="x",
                role="admin",
            )
        with self.assertRaisesRegex(ValueError, "dispatch_labels"):
            _policy(dispatch_labels=frozenset())
        with self.assertRaisesRegex(ValueError, "trusted_actors"):
            _policy(trusted_actors=())
        with self.assertRaisesRegex(ValueError, "allowed_roles"):
            _policy(allowed_roles=frozenset())

    def test_decision_contains_no_issue_text_or_secret_value(self):
        decision = authorize_github_dispatch(
            _envelope(),
            _policy(),
        )
        rendered = decision.to_dict()
        self.assertNotIn("title", rendered)
        self.assertNotIn("body", rendered)
        self.assertNotIn("comment", rendered)
        self.assertNotIn("secret_value", rendered)
        self.assertNotIn("token", rendered)
        self.assertNotIn("authorization_header", rendered)


if __name__ == "__main__":
    unittest.main()
