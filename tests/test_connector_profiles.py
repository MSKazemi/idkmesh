import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_profiles import (
    ConnectorProfileError,
    PROFILE_API_VERSION,
    load_connector_profile,
    load_connector_profiles,
    parse_connector_profile,
)


FIXTURES = Path(__file__).parent / "fixtures" / "connector_profiles"


def _base_profile():
    return {
        "api_version": PROFILE_API_VERSION,
        "id": "test-agent",
        "kind": "agent",
        "driver": "fake",
        "enabled": True,
        "settings": {},
        "policy": {
            "task_classes": ["coder"],
            "allowed_risk": ["low"],
            "external_processing": False,
            "project_spend_usd_max": 0,
        },
    }


class ConnectorProfileLoadingTests(unittest.TestCase):
    def test_valid_fixture_loads_deterministically(self):
        path = FIXTURES / "valid-jules.json"

        first = load_connector_profile(path)
        second = load_connector_profile(path)

        self.assertEqual(first, second)
        self.assertEqual(first.api_version, PROFILE_API_VERSION)
        self.assertEqual(first.connection_id, "jules-main")
        self.assertEqual(first.kind, "agent")
        self.assertEqual(first.driver, "jules")
        self.assertEqual(first.secret_ref, "env:JULES_API_KEY")
        self.assertEqual(first.policy["task_classes"], ("coder",))
        self.assertEqual(first.policy["allowed_risk"], ("low",))

    def test_loaded_profile_normalizes_to_fail_closed_routing_state(self):
        loaded = load_connector_profile(FIXTURES / "valid-jules.json")

        routing = loaded.to_routing_profile()

        self.assertEqual(routing.connection_id, "jules-main")
        self.assertEqual(routing.task_classes, frozenset({"coder"}))
        self.assertEqual(routing.max_risk, "low")
        self.assertTrue(routing.external_processing)
        self.assertTrue(routing.secret_required)
        self.assertFalse(routing.secret_available)
        self.assertEqual(routing.health, "unavailable")
        self.assertFalse(routing.capacity_available)
        self.assertEqual(routing.capability_tiers, frozenset())

    def test_disabled_profile_stays_disabled_in_routing_view(self):
        raw = _base_profile()
        raw["enabled"] = False

        routing = parse_connector_profile(raw).to_routing_profile()

        self.assertEqual(routing.health, "disabled")
        self.assertFalse(routing.enabled)

    def test_unknown_version_fails_closed(self):
        with self.assertRaisesRegex(
            ConnectorProfileError, "unsupported api_version"
        ):
            load_connector_profile(FIXTURES / "unknown-version.json")

    def test_unknown_top_level_field_fails_closed(self):
        raw = _base_profile()
        raw["surprise"] = True

        with self.assertRaisesRegex(
            ConnectorProfileError, "unsupported top-level field"
        ):
            parse_connector_profile(raw)

    def test_unknown_kind_and_invalid_driver_shape_fail_clearly(self):
        bad_kind = _base_profile()
        bad_kind["kind"] = ["agent"]

        with self.assertRaisesRegex(
            ConnectorProfileError, "kind has unsupported value"
        ):
            parse_connector_profile(bad_kind)

        bad_driver = _base_profile()
        bad_driver["driver"] = "openai compatible"

        with self.assertRaisesRegex(
            ConnectorProfileError, "driver has an invalid identifier shape"
        ):
            parse_connector_profile(bad_driver)

    def test_inline_raw_secret_field_is_rejected(self):
        with self.assertRaisesRegex(
            ConnectorProfileError, "inline credential field"
        ):
            load_connector_profile(FIXTURES / "raw-secret.json")

        raw = _base_profile()
        raw["auth"] = {"api_key": "not-allowed"}

        with self.assertRaisesRegex(
            ConnectorProfileError, "auth contains unsupported field"
        ):
            parse_connector_profile(raw)

    def test_secret_reference_is_retained_as_reference_only(self):
        raw = _base_profile()
        raw["auth"] = {"secret_ref": "env:EXAMPLE_TOKEN"}

        loaded = parse_connector_profile(raw)

        self.assertEqual(loaded.secret_ref, "env:EXAMPLE_TOKEN")
        self.assertNotIn("EXAMPLE_TOKEN", loaded.settings)
        self.assertTrue(loaded.to_routing_profile().secret_required)
        self.assertFalse(loaded.to_routing_profile().secret_available)

    def test_secret_reference_requires_explicit_scheme(self):
        raw = _base_profile()
        raw["auth"] = {"secret_ref": "EXAMPLE_TOKEN"}

        with self.assertRaisesRegex(
            ConnectorProfileError, "explicit scheme"
        ):
            parse_connector_profile(raw)

    def test_duplicate_connection_ids_fail_across_profile_documents(self):
        with self.assertRaisesRegex(
            ConnectorProfileError, "duplicate connection id 'duplicate'"
        ):
            load_connector_profiles(
                [
                    FIXTURES / "duplicate-a.json",
                    FIXTURES / "duplicate-b.json",
                ]
            )

    def test_allowed_risk_normalizes_only_when_cumulative(self):
        raw = _base_profile()
        raw["policy"]["allowed_risk"] = ["high", "low", "medium"]

        loaded = parse_connector_profile(raw)

        self.assertEqual(
            loaded.policy["allowed_risk"], ("low", "medium", "high")
        )
        self.assertEqual(loaded.to_routing_profile().max_risk, "high")

    def test_sparse_allowed_risk_is_rejected_to_avoid_policy_broadening(self):
        raw = _base_profile()
        raw["policy"]["allowed_risk"] = ["low", "high"]

        with self.assertRaisesRegex(
            ConnectorProfileError, "must be cumulative"
        ):
            parse_connector_profile(raw)

    def test_policy_fields_are_type_checked(self):
        cases = [
            ("max_concurrency", 0, "integer >= 1"),
            ("external_processing", 1, "must be a boolean"),
            ("project_spend_usd_max", -1, "finite and >= 0"),
            ("network", "", "non-empty string"),
        ]

        for field, value, message in cases:
            with self.subTest(field=field):
                raw = _base_profile()
                raw["policy"][field] = value
                with self.assertRaisesRegex(ConnectorProfileError, message):
                    parse_connector_profile(raw)

    def test_unsupported_policy_field_fails_closed(self):
        raw = _base_profile()
        raw["policy"]["provider_magic"] = True

        with self.assertRaisesRegex(
            ConnectorProfileError, "policy contains unsupported field"
        ):
            parse_connector_profile(raw)

    def test_malformed_json_is_reported_without_traceback_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"api_version": ', encoding="utf-8")

            with self.assertRaisesRegex(
                ConnectorProfileError, "invalid JSON at line"
            ):
                load_connector_profile(path)

    def test_settings_are_detached_from_input_mapping(self):
        raw = _base_profile()
        raw["settings"] = {"nested": {"value": 1}}

        loaded = parse_connector_profile(raw)
        raw["settings"]["nested"]["value"] = 99

        self.assertEqual(loaded.settings["nested"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
