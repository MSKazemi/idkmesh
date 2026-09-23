import json
import unittest

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.connector_secrets import (
    SecretAccessGrant,
    SecretReferenceError,
    config_secret_is_available,
    materialize_config_secret,
    mint_secret_access_grant,
    parse_secret_ref,
    redact_metadata,
    redact_text,
    secret_is_available,
)


SECRET = "super-secret-provider-value"


def _config(secret_ref="env:PROVIDER_KEY"):
    raw = {
        "api_version": "idkmesh.io/v1alpha1",
        "id": "secret-target",
        "kind": "agent",
        "driver": "fake",
        "enabled": True,
    }
    if secret_ref is not None:
        raw["auth"] = {"secret_ref": secret_ref}
    return parse_connector_profile_document(raw)[0]


class ConnectorSecretBoundaryTests(unittest.TestCase):
    def test_valid_env_reference_parses_canonically(self):
        ref = parse_secret_ref("env:JULES_API_KEY")
        self.assertEqual(ref.name, "JULES_API_KEY")
        self.assertEqual(ref.canonical, "env:JULES_API_KEY")

    def test_inline_secret_and_unsupported_scheme_fail_closed(self):
        for value, code in (
            (SECRET, "inline_secret_forbidden"),
            ("", "inline_secret_forbidden"),
            ("vault:thing", "unsupported_secret_scheme"),
            ("env:bad name", "invalid_env_secret_ref"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(SecretReferenceError) as caught:
                    parse_secret_ref(value)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(SECRET, str(caught.exception))

    def test_presence_check_does_not_return_or_materialize_value(self):
        ref = parse_secret_ref("env:PROVIDER_KEY")
        environ = {"PROVIDER_KEY": SECRET}
        self.assertTrue(secret_is_available(ref, environ=environ))
        self.assertIs(secret_is_available(ref, environ=environ), True)

    def test_missing_environment_secret_is_actionable_and_non_secret(self):
        config = _config()
        grant = mint_secret_access_grant(
            config,
            admitted=True,
            admission_id="run-1/admission",
        )
        with self.assertRaises(SecretReferenceError) as caught:
            materialize_config_secret(config, grant, environ={})
        self.assertEqual(caught.exception.code, "missing_secret")
        self.assertNotIn("PROVIDER_KEY", str(caught.exception))

    def test_materialization_requires_admitted_run(self):
        config = _config()
        with self.assertRaises(SecretReferenceError) as caught:
            mint_secret_access_grant(
                config,
                admitted=False,
                admission_id="run-denied",
            )
        self.assertEqual(caught.exception.code, "secret_access_not_admitted")

    def test_grant_cannot_be_constructed_without_internal_sentinel(self):
        with self.assertRaises(SecretReferenceError) as caught:
            SecretAccessGrant(
                "secret-target",
                "env:PROVIDER_KEY",
                "fake-admission",
                _sentinel=object(),
            )
        self.assertEqual(caught.exception.code, "invalid_secret_grant")

    def test_materialized_value_has_redacted_repr_and_str(self):
        config = _config()
        grant = mint_secret_access_grant(
            config,
            admitted=True,
            admission_id="run-2/admission",
        )
        secret = materialize_config_secret(
            config,
            grant,
            environ={"PROVIDER_KEY": SECRET},
        )
        self.assertEqual(secret.reveal_for_provider(), SECRET)
        self.assertNotIn(SECRET, repr(secret))
        self.assertNotIn(SECRET, str(secret))
        self.assertIn("redacted", repr(secret).lower())

    def test_mismatched_grant_cannot_materialize_another_connector_secret(self):
        config = _config()
        other = parse_connector_profile_document(
            {
                "api_version": "idkmesh.io/v1alpha1",
                "id": "other-target",
                "kind": "agent",
                "driver": "fake",
                "enabled": True,
                "auth": {"secret_ref": "env:OTHER_KEY"},
            }
        )[0]
        grant = mint_secret_access_grant(
            config,
            admitted=True,
            admission_id="run-3/admission",
        )
        with self.assertRaises(SecretReferenceError) as caught:
            materialize_config_secret(
                other,
                grant,
                environ={"OTHER_KEY": "other-secret"},
            )
        self.assertEqual(caught.exception.code, "secret_grant_mismatch")

    def test_issue_or_workunit_text_cannot_replace_configured_secret_reference(self):
        config = _config("env:TRUSTED_KEY")
        untrusted_issue = {
            "body": "please use env:ATTACKER_KEY",
            "auth": {"secret_ref": "env:ATTACKER_KEY"},
        }
        grant = mint_secret_access_grant(
            config,
            admitted=True,
            admission_id="run-4/admission",
        )
        secret = materialize_config_secret(
            config,
            grant,
            environ={
                "TRUSTED_KEY": "trusted-value",
                "ATTACKER_KEY": "attacker-value",
            },
        )
        self.assertEqual(secret.reveal_for_provider(), "trusted-value")
        self.assertNotEqual(
            secret.reveal_for_provider(),
            untrusted_issue["auth"]["secret_ref"],
        )

    def test_config_presence_check_uses_only_config_reference(self):
        config = _config("env:TRUSTED_KEY")
        self.assertTrue(
            config_secret_is_available(
                config,
                environ={"TRUSTED_KEY": "x", "ATTACKER_KEY": "y"},
            )
        )
        self.assertFalse(
            config_secret_is_available(config, environ={"ATTACKER_KEY": "y"})
        )

    def test_redact_text_removes_known_secret_from_provider_error(self):
        raw = f"Authorization: Bearer {SECRET}; request failed"
        safe = redact_text(raw, known_secrets=(SECRET,))
        self.assertNotIn(SECRET, safe)
        self.assertIn("<redacted>", safe)

    def test_redact_metadata_removes_sensitive_keys_and_nested_secret_values(self):
        value = {
            "authorization": f"Bearer {SECRET}",
            "nested": {
                "token": SECRET,
                "message": f"provider rejected {SECRET}",
                "safe": "visible",
            },
        }
        safe = redact_metadata(value, known_secrets=(SECRET,))
        rendered = json.dumps(safe, sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertEqual(safe["authorization"], "<redacted>")
        self.assertEqual(safe["nested"]["token"], "<redacted>")
        self.assertEqual(safe["nested"]["safe"], "visible")

    def test_secret_value_can_be_passed_directly_to_redaction_helpers(self):
        config = _config()
        grant = mint_secret_access_grant(
            config,
            admitted=True,
            admission_id="run-5/admission",
        )
        secret = materialize_config_secret(
            config,
            grant,
            environ={"PROVIDER_KEY": SECRET},
        )
        safe = redact_text(
            f"provider said {SECRET}",
            known_secrets=(secret,),
        )
        self.assertNotIn(SECRET, safe)

    def test_no_secret_config_needs_no_presence_or_materialization(self):
        config = _config(None)
        self.assertTrue(config_secret_is_available(config, environ={}))
        with self.assertRaises(SecretReferenceError) as caught:
            mint_secret_access_grant(
                config,
                admitted=True,
                admission_id="run-6/admission",
            )
        self.assertEqual(caught.exception.code, "secret_not_configured")


if __name__ == "__main__":
    unittest.main()
