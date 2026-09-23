import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_profiles import (
    ConnectorProfileError,
    load_connector_profile_document,
    parse_connector_profile_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


class ConnectorProfileValidationTests(unittest.TestCase):
    def test_valid_fixture_loads_deterministically(self):
        configs = load_connector_profile_document(
            FIXTURES / "connector_profiles_valid_v1alpha1.json"
        )
        self.assertEqual([item.id for item in configs], ["jules-main", "local-goose"])

        jules, local = configs
        self.assertEqual(jules.secret_ref, "env:JULES_API_KEY")
        self.assertEqual(jules.task_classes, frozenset({"coder"}))
        self.assertEqual(jules.capability_tiers, frozenset({"T1", "T2"}))
        self.assertTrue(jules.external_processing)
        self.assertEqual(jules.provider_family, "google")

        self.assertIsNone(local.secret_ref)
        self.assertEqual(local.max_risk, "medium")
        self.assertEqual(local.tools, frozenset({"git", "pytest"}))

    def test_single_connection_object_is_a_valid_document(self):
        raw = json.loads(
            (FIXTURES / "connector_profiles_valid_v1alpha1.json").read_text()
        )[0]
        configs = parse_connector_profile_document(raw)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].id, "jules-main")

    def test_unknown_api_version_fails_closed(self):
        with self.assertRaises(ConnectorProfileError) as caught:
            load_connector_profile_document(
                FIXTURES / "connector_profiles_unknown_version.json"
            )
        self.assertEqual(caught.exception.code, "unsupported_api_version")

    def test_duplicate_connection_ids_fail(self):
        with self.assertRaises(ConnectorProfileError) as caught:
            load_connector_profile_document(
                FIXTURES / "connector_profiles_duplicate_ids.json"
            )
        self.assertEqual(caught.exception.code, "duplicate_connection_id")

    def test_inline_raw_secret_is_rejected_without_echoing_value(self):
        sentinel = "sentinel-inline-value"
        with self.assertRaises(ConnectorProfileError) as caught:
            load_connector_profile_document(
                FIXTURES / "connector_profiles_inline_secret.json"
            )
        self.assertEqual(caught.exception.code, "inline_secret_forbidden")
        self.assertNotIn(sentinel, str(caught.exception))

    def test_secret_ref_outside_auth_is_rejected(self):
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "bad-secret-location",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            "settings": {"secret_ref": "env:SHOULD_NOT_BE_HERE"},
        }
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(raw)
        self.assertEqual(caught.exception.code, "secret_ref_outside_auth")

    def test_unknown_kind_and_bad_driver_identifier_fail_clearly(self):
        base = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "example",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
        }
        with self.assertRaises(ConnectorProfileError) as kind_error:
            parse_connector_profile_document({**base, "kind": "unknown"})
        self.assertEqual(kind_error.exception.code, "unknown_connector_kind")

        with self.assertRaises(ConnectorProfileError) as driver_error:
            parse_connector_profile_document({**base, "driver": "bad driver"})
        self.assertEqual(driver_error.exception.code, "invalid_identifier")

    def test_unknown_top_level_field_fails_closed(self):
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "example",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            "unexpected": True,
        }
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(raw)
        self.assertEqual(caught.exception.code, "unknown_field")

    def test_non_string_field_name_fails_closed(self):
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "example",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            7: "invalid-json-object-key",
        }
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(raw)
        self.assertEqual(caught.exception.code, "invalid_field_name")

    def test_conflicting_task_class_declarations_fail(self):
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "conflict",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            "capabilities": {"task_classes": ["coder"]},
            "policy": {"task_classes": ["researcher"]},
        }
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(raw)
        self.assertEqual(caught.exception.code, "conflicting_field")

    def test_non_monotonic_allowed_risk_cannot_be_lossily_normalized(self):
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "risk-gap",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            "policy": {"allowed_risk": ["low", "high"]},
        }
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(raw)
        self.assertEqual(caught.exception.code, "non_monotonic_risk_policy")

    def test_routing_profile_defaults_fail_closed_until_runtime_facts_arrive(self):
        configs = load_connector_profile_document(
            FIXTURES / "connector_profiles_valid_v1alpha1.json"
        )
        jules = configs[0]
        routed = jules.to_routing_profile(project_cost_usd=0)
        self.assertEqual(routed.health, "degraded")
        self.assertTrue(routed.secret_required)
        self.assertFalse(routed.secret_available)
        self.assertFalse(routed.capacity_available)

        ready = jules.to_routing_profile(
            project_cost_usd=0,
            health="healthy",
            secret_available=True,
            capacity_available=True,
        )
        self.assertTrue(ready.secret_available)
        self.assertTrue(ready.capacity_available)

    def test_runtime_cost_cannot_exceed_connector_policy(self):
        configs = load_connector_profile_document(
            FIXTURES / "connector_profiles_valid_v1alpha1.json"
        )
        with self.assertRaises(ConnectorProfileError) as caught:
            configs[0].to_routing_profile(project_cost_usd=0.01)
        self.assertEqual(caught.exception.code, "connector_spend_policy_exceeded")

    def test_malformed_json_reports_location_without_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"api_version": ', encoding="utf-8")
            with self.assertRaises(ConnectorProfileError) as caught:
                load_connector_profile_document(path)
        self.assertEqual(caught.exception.code, "invalid_json")
        self.assertIn("line 1", str(caught.exception))

    def test_invalid_utf8_fails_closed_without_raw_decode_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-utf8.json"
            path.write_bytes(b'{"api_version":"idkmesh.io/v1alpha1","id":"x"}\xff')
            with self.assertRaises(ConnectorProfileError) as caught:
                load_connector_profile_document(path)
        self.assertEqual(caught.exception.code, "invalid_utf8")
        self.assertIn("byte", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
