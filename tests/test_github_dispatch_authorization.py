import unittest

from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    authorize_github_issue_dispatch,
)
from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope


def _envelope(**overrides):
    values = {
        "delivery_id": "delivery-1",
        "event": "issues",
        "action": "labeled",
        "repository": "MSKazemi/idkmesh",
        "repository_id": 123,
        "sender_login": "TrustedMaintainer",
        "sender_id": 42,
        "sender_type": "User",
        "author_association": "NONE",
        "subject_number": 77,
        "label_name": "agent-ready",
        "payload_digest": "sha256:" + "a" * 64,
    }
    values.update(overrides)
    return GitHubWebhookEnvelope(**values)


def _policy(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "dispatch_labels": frozenset({"agent-ready"}),
        "trusted_actor_logins": frozenset({"TrustedMaintainer"}),
    }
    values.update(overrides)
    return GitHubDispatchAuthorizationPolicy(**values)


class GitHubDispatchAuthorizationTests(unittest.TestCase):
    def test_trusted_actor_explicit_label_is_authorized(self):
        decision = authorize_github_issue_dispatch(
            _envelope(),
            _policy(),
        )
        self.assertTrue(decision.authorized)
        self.assertEqual(decision.reasons, ())
        self.assertEqual(decision.issue_number, 77)

    def test_actor_and_label_matching_are_case_insensitive(self):
        decision = authorize_github_issue_dispatch(
            _envelope(
                sender_login="trustedmaintainer",
                label_name="AGENT-READY",
            ),
            _policy(),
        )
        self.assertTrue(decision.authorized)

    def test_untrusted_actor_is_denied_even_with_dispatch_label(self):
        decision = authorize_github_issue_dispatch(
            _envelope(sender_login="issue-author"),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn("actor_not_trusted", decision.reasons)

    def test_unconfigured_label_is_denied_even_for_trusted_actor(self):
        decision = authorize_github_issue_dispatch(
            _envelope(label_name="bug"),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn(
            "dispatch_label_not_configured",
            decision.reasons,
        )

    def test_opened_comment_and_pull_request_events_do_not_dispatch(self):
        cases = [
            _envelope(action="opened", label_name=None),
            _envelope(
                event="issue_comment",
                action="created",
                label_name=None,
            ),
            _envelope(
                event="pull_request",
                action="opened",
                label_name=None,
            ),
        ]
        for envelope in cases:
            with self.subTest(event=envelope.event, action=envelope.action):
                decision = authorize_github_issue_dispatch(
                    envelope,
                    _policy(),
                )
                self.assertFalse(decision.authorized)
                self.assertTrue(
                    "event_not_dispatchable" in decision.reasons
                    or "action_not_dispatchable" in decision.reasons
                )

    def test_repository_binding_is_rechecked_at_authorization_boundary(self):
        decision = authorize_github_issue_dispatch(
            _envelope(repository="other/repo"),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn(
            "repository_not_authorized",
            decision.reasons,
        )

    def test_bot_sender_is_denied_unless_explicitly_enabled_and_allowlisted(self):
        bot = _envelope(
            sender_login="dispatch-bot[bot]",
            sender_type="Bot",
        )
        denied = authorize_github_issue_dispatch(bot, _policy())
        self.assertFalse(denied.authorized)
        self.assertIn("sender_type_not_trusted", denied.reasons)
        self.assertIn("actor_not_trusted", denied.reasons)

        allowed = authorize_github_issue_dispatch(
            bot,
            _policy(
                trusted_actor_logins=frozenset({"dispatch-bot[bot]"}),
                allowed_sender_types=frozenset({"Bot"}),
            ),
        )
        self.assertTrue(allowed.authorized)

    def test_issue_author_association_is_not_implicit_actor_authority(self):
        # The maintainer explicitly labels an issue from an untrusted author.
        # By default the maintainer action is sufficient; the issue author's
        # association does not become or remove actor authority.
        allowed = authorize_github_issue_dispatch(
            _envelope(author_association="FIRST_TIMER"),
            _policy(),
        )
        self.assertTrue(allowed.authorized)

        restricted = authorize_github_issue_dispatch(
            _envelope(author_association="FIRST_TIMER"),
            _policy(
                allowed_issue_author_associations=frozenset(
                    {"OWNER", "MEMBER"}
                )
            ),
        )
        self.assertFalse(restricted.authorized)
        self.assertIn(
            "issue_author_association_not_allowed",
            restricted.reasons,
        )

    def test_missing_issue_number_fails_closed(self):
        decision = authorize_github_issue_dispatch(
            _envelope(subject_number=None),
            _policy(),
        )
        self.assertFalse(decision.authorized)
        self.assertIn("issue_number_missing", decision.reasons)

    def test_policy_requires_explicit_labels_and_actors(self):
        with self.assertRaisesRegex(ValueError, "dispatch_labels"):
            _policy(dispatch_labels=frozenset())
        with self.assertRaisesRegex(ValueError, "trusted_actor_logins"):
            _policy(trusted_actor_logins=frozenset())

    def test_unknown_association_in_policy_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            _policy(
                allowed_issue_author_associations=frozenset(
                    {"SUPERADMIN"}
                )
            )

    def test_decision_contains_no_issue_text_or_comment_content(self):
        decision = authorize_github_issue_dispatch(
            _envelope(),
            _policy(),
        )
        rendered = decision.to_dict()
        self.assertNotIn("title", rendered)
        self.assertNotIn("body", rendered)
        self.assertNotIn("comment", rendered)


if __name__ == "__main__":
    unittest.main()
