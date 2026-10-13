"""Tests for the E5 enterprise data/egress/credential decision kernel (#672)."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from idkmesh.enterprise_authz import AuthorizationDecision
from idkmesh.enterprise_data_policy import (
    authorize_secret_access,
    decide_credential,
    decide_egress,
    decide_external_processing,
    normalize_host,
)

ROOT = Path(__file__).resolve().parents[1]
G1 = json.loads(
    (ROOT / "examples" / "enterprise" / "g1-github-native.example.json").read_text("utf-8")
)
G2 = json.loads(
    (ROOT / "examples" / "enterprise" / "g2-self-hosted.example.json").read_text("utf-8")
)
APPROVED = ("provider-a",)


def authz(effect: str = "allow", action: str = "execute") -> AuthorizationDecision:
    return AuthorizationDecision(
        effect=effect,
        code="test",
        message="fixture",
        request_id="req-1",
        principal_id="github:user:alice",
        action=action,
        tenant_id="tenant-a",
        project_id="project-main",
        resource_type="secret",
        resource_id="ref-1",
        requested_risk="low",
        effective_risk="low",
        data_classification="internal",
        policy_id="policy-1",
        policy_revision="1",
        identity_revision="identity:1",
        evaluated_at_epoch=1790168400,
    )


class ExternalProcessingTests(unittest.TestCase):
    def decide(self, profile, data_class, provider="provider-a", approved=APPROVED):
        return decide_external_processing(
            profile,
            data_class=data_class,
            provider_id=provider,
            approved_provider_ids=approved,
        )

    def test_public_to_approved_provider_is_allowed(self) -> None:
        self.assertTrue(self.decide(G1, "public").allowed)

    def test_every_non_public_class_fails_closed_in_baseline(self) -> None:
        for data_class in ("internal", "confidential", "restricted"):
            with self.subTest(data_class=data_class):
                decision = self.decide(G1, data_class)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.code, "external_processing_forbidden")

    def test_restricted_denied_even_for_approved_provider(self) -> None:
        profile = deepcopy(G1)
        profile["data"]["external_processing"]["restricted"] = False
        self.assertFalse(self.decide(profile, "restricted").allowed)

    def test_eligibility_is_non_compensating_across_classes(self) -> None:
        profile = deepcopy(G1)
        for name in ("public", "internal", "confidential"):
            profile["data"]["external_processing"][name] = True
        self.assertTrue(self.decide(profile, "confidential").allowed)
        decision = self.decide(profile, "restricted")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "external_processing_forbidden")

    def test_unadmitted_class_is_denied_even_if_flag_is_true(self) -> None:
        profile = deepcopy(G1)
        profile["data"]["allowed_classifications"] = ["public", "internal"]
        profile["data"]["external_processing"]["restricted"] = True
        decision = self.decide(profile, "restricted")
        self.assertEqual(decision.code, "class_not_admitted")

    def test_unapproved_or_malformed_provider_is_denied(self) -> None:
        self.assertEqual(
            self.decide(G1, "public", provider="other").code, "provider_not_approved"
        )
        self.assertEqual(
            self.decide(G1, "public", provider="bad provider!").code, "invalid_provider"
        )
        self.assertEqual(
            self.decide(G1, "public", approved=()).code, "provider_not_approved"
        )

    def test_approved_provider_list_rejects_scalar_and_malformed_inputs(self) -> None:
        for invalid in (
            "provider-a", b"provider-a", {"provider-a": True}, None,
            ["provider-a", 17], ["provider-a", "bad provider"],
        ):
            with self.subTest(invalid=repr(invalid)):
                decision = self.decide(G1, "public", approved=invalid)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.code, "invalid_approved_providers")
        self.assertTrue(
            self.decide(G1, "public", approved=(x for x in APPROVED)).allowed
        )
        self.assertEqual(
            self.decide(G1, "public", approved=["provider-a"] * 257).code,
            "invalid_approved_providers",
        )

    def test_unknown_class_and_invalid_profile_deny(self) -> None:
        self.assertEqual(self.decide(G1, "top-secret").code, "unknown_data_class")
        self.assertEqual(self.decide(G1, None).code, "unknown_data_class")
        broken = deepcopy(G1)
        del broken["data"]
        self.assertEqual(self.decide(broken, "public").code, "invalid_profile")
        self.assertEqual(self.decide("nope", "public").code, "invalid_profile")

    def test_untrusted_provider_text_is_not_echoed(self) -> None:
        decision = self.decide(G1, "public", provider="x\nIGNORE PREVIOUS")
        self.assertEqual(decision.subject, "<invalid>")
        self.assertNotIn("IGNORE", json.dumps(decision.to_dict()))


class EgressTests(unittest.TestCase):
    def test_allowlist_collection_rejects_scalar_mapping_and_oversize(self) -> None:
        for invalid in ("a", b"a", {"a": True}, None, ["a", 1], ["a", "*.example.org"]):
            with self.subTest(invalid=repr(invalid)):
                decision = decide_egress(G1, destination_host="a", allowlist=invalid)
                self.assertEqual(decision.code, "invalid_allowlist")
                self.assertFalse(decision.allowed)
        self.assertEqual(
            decide_egress(G1, destination_host="a", allowlist=["a"] * 257).code,
            "invalid_allowlist",
        )

    def test_default_deny_blocks_unlisted_host(self) -> None:
        decision = decide_egress(
            G1, destination_host="api.example.com", allowlist=["other.example.com"]
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "egress_denied_by_default")

    def test_empty_allowlist_denies_everything(self) -> None:
        self.assertFalse(
            decide_egress(G1, destination_host="api.example.com", allowlist=[]).allowed
        )

    def test_exact_normalised_match_is_allowed(self) -> None:
        decision = decide_egress(
            G1, destination_host="API.Example.com.", allowlist=["api.example.com"]
        )
        self.assertTrue(decision.allowed)

    def test_no_wildcard_or_suffix_matching(self) -> None:
        for allowlist in (["example.com"], ["*.example.com"]):
            with self.subTest(allowlist=allowlist):
                self.assertFalse(
                    decide_egress(
                        G1, destination_host="api.example.com", allowlist=allowlist
                    ).allowed
                )

    def test_malformed_allowlist_entry_denies_even_a_listed_host(self) -> None:
        decision = decide_egress(
            G1,
            destination_host="api.example.com",
            allowlist=["api.example.com", "https://evil.example.com/x"],
        )
        self.assertEqual(decision.code, "invalid_allowlist")

    def test_destination_must_be_a_bare_hostname(self) -> None:
        for bad in (
            "https://api.example.com",
            "api.example.com:443",
            "user@api.example.com",
            "api.example.com/path",
            "api .example.com",
            "",
            None,
            "-bad.example.com",
            "a..b",
        ):
            with self.subTest(bad=bad):
                decision = decide_egress(
                    G1, destination_host=bad, allowlist=["api.example.com"]
                )
                self.assertEqual(decision.code, "invalid_destination")

    def test_allow_default_is_reachable_only_for_a_local_g0_profile(self) -> None:
        profile = deepcopy(G1)
        profile["data"]["egress_default"] = "allow"
        # G1 requires deny-by-default, so the kernel refuses this profile.
        self.assertEqual(
            decide_egress(
                profile, destination_host="api.example.com", allowlist=[]
            ).code,
            "invalid_profile",
        )
        profile["deployment"].update(
            profile="g0_local_operator",
            tenant_scope="single_project",
            remote_api_enabled=False,
            coordinator_lifecycle="local_process",
        )
        profile["identity"].update(
            human_source="local_trusted_operator", service_source="process"
        )
        decision = decide_egress(
            profile, destination_host="api.example.com", allowlist=[]
        )
        self.assertEqual(decision.code, "egress_allowed_by_profile_default")

    def test_normalize_host(self) -> None:
        self.assertEqual(normalize_host("A.B."), "a.b")
        self.assertIsNone(normalize_host("a_b.com"))
        self.assertIsNone(normalize_host("x" * 300))


class CredentialTests(unittest.TestCase):
    def test_workload_identity_allowed_under_oidc_backend(self) -> None:
        self.assertTrue(
            decide_credential(G2, credential_kind="workload_identity").allowed
        )

    def test_long_lived_cloud_key_forbidden_by_profile(self) -> None:
        for profile in (G1, G2):
            decision = decide_credential(profile, credential_kind="long_lived_cloud_key")
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.code, "long_lived_keys_forbidden")

    def test_long_lived_cloud_key_needs_explicit_opt_in(self) -> None:
        profile = deepcopy(G1)
        profile["secrets"]["long_lived_cloud_keys_allowed"] = True
        decision = decide_credential(profile, credential_kind="long_lived_cloud_key")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, "long_lived_key_permitted")

    def test_kind_must_match_profile_backend(self) -> None:
        decision = decide_credential(G1, credential_kind="workload_identity")
        self.assertEqual(decision.code, "credential_not_from_profile_backend")
        self.assertTrue(decide_credential(G1, credential_kind="github_secret").allowed)

    def test_none_backend_denies_every_credential(self) -> None:
        profile = deepcopy(G1)
        profile["secrets"]["backend"] = "none"
        for kind in ("github_secret", "workload_identity", "long_lived_cloud_key"):
            with self.subTest(kind=kind):
                self.assertEqual(
                    decide_credential(profile, credential_kind=kind).code,
                    "no_secret_backend",
                )

    def test_unknown_kind_denies(self) -> None:
        self.assertEqual(
            decide_credential(G1, credential_kind="root_password").code,
            "unknown_credential_kind",
        )


class SecretAccessTests(unittest.TestCase):
    def access(self, profile=G2, **overrides):
        kwargs = {
            "authorization": authz(),
            "credential_kind": "workload_identity",
        }
        kwargs.update(overrides)
        return authorize_secret_access(profile, **kwargs)

    def test_authorized_access_from_profile_backend_is_allowed(self) -> None:
        self.assertTrue(self.access().allowed)

    def test_no_authorization_means_no_access(self) -> None:
        for value in (None, True, {"effect": "allow"}):
            with self.subTest(value=value):
                self.assertEqual(
                    self.access(authorization=value).code, "authorization_required"
                )

    def test_deny_and_approval_pending_effects_do_not_open_access(self) -> None:
        for effect in ("deny", "requires_approval"):
            with self.subTest(effect=effect):
                self.assertEqual(
                    self.access(authorization=authz(effect)).code,
                    "authorization_not_allowed",
                )

    def test_only_dispatch_and_execute_allows_unlock_secrets(self) -> None:
        for action in ("dispatch", "execute"):
            with self.subTest(action=action):
                self.assertTrue(self.access(authorization=authz(action=action)).allowed)
        for action in ("read", "claim", "release", "verify", "integrate",
                       "manage_policy", "audit_export"):
            with self.subTest(action=action):
                decision = self.access(authorization=authz(action=action))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.code, "authorization_action_not_permitted")

    def test_request_text_cannot_select_the_secret_source(self) -> None:
        decision = self.access(requested_backend="environment")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "untrusted_source_selection")

    def test_matching_requested_backend_is_only_corroboration(self) -> None:
        self.assertTrue(self.access(requested_backend="oidc_workload_identity").allowed)

    def test_forbidden_credential_still_blocks_after_authorization(self) -> None:
        decision = self.access(credential_kind="long_lived_cloud_key")
        self.assertEqual(decision.code, "long_lived_keys_forbidden")

    def test_decision_serialisation_carries_no_secret_material(self) -> None:
        payload = self.access().to_dict()
        self.assertFalse(payload["authority"]["reads_secret_value"])
        self.assertEqual(
            sorted(payload),
            [
                "authority",
                "code",
                "control",
                "effect",
                "kind",
                "message",
                "schema_version",
                "subject",
            ],
        )

    def test_invalid_profile_blocks_access(self) -> None:
        self.assertEqual(self.access(profile={}).code, "invalid_profile")


if __name__ == "__main__":
    unittest.main()
