import json
import unittest

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.connector_registry import (
    ConnectorRegistry,
    ConnectorRegistryError,
    DriverCapabilities,
    StaticFakeDriver,
    build_fake_registry,
    fake_agent_driver,
)


def _config(*, kind="agent", driver="fake-agent"):
    raw = {
        "api_version": "idkmesh.io/v1alpha1",
        "id": f"{kind}-one",
        "kind": kind,
        "driver": driver,
        "enabled": True,
    }
    return parse_connector_profile_document(raw)[0]


class ConnectorRegistryTests(unittest.TestCase):
    def test_all_four_connector_kinds_resolve_offline(self):
        registry = build_fake_registry()
        expected = {
            ("agent", "fake-agent"),
            ("execution", "fake-execution"),
            ("model", "fake-model"),
            ("scm", "fake-scm"),
        }
        actual = {(item.kind, item.driver_id) for item in registry.descriptors()}
        self.assertEqual(actual, expected)

        for kind, driver_id in sorted(expected):
            with self.subTest(kind=kind):
                driver = registry.resolve(kind, driver_id)
                self.assertEqual(driver.kind, kind)
                self.assertEqual(driver.driver_id, driver_id)

    def test_descriptors_are_stable_and_serializable(self):
        registry = build_fake_registry()
        rendered = [item.to_dict() for item in registry.descriptors()]
        self.assertEqual(
            rendered,
            [
                {"kind": "agent", "driver": "fake-agent", "version": "0.1"},
                {"kind": "execution", "driver": "fake-execution", "version": "0.1"},
                {"kind": "model", "driver": "fake-model", "version": "0.1"},
                {"kind": "scm", "driver": "fake-scm", "version": "0.1"},
            ],
        )
        json.dumps(rendered, sort_keys=True)

    def test_duplicate_registration_fails_closed(self):
        registry = ConnectorRegistry()
        driver = fake_agent_driver()
        registry.register(driver)
        with self.assertRaises(ConnectorRegistryError) as caught:
            registry.register(driver)
        self.assertEqual(caught.exception.code, "duplicate_driver")

    def test_unknown_driver_fails_closed(self):
        registry = build_fake_registry()
        with self.assertRaises(ConnectorRegistryError) as caught:
            registry.resolve("agent", "not-registered")
        self.assertEqual(caught.exception.code, "unknown_driver")

    def test_same_driver_name_in_wrong_kind_does_not_cross_resolve(self):
        registry = build_fake_registry()
        with self.assertRaises(ConnectorRegistryError) as caught:
            registry.resolve("model", "fake-agent")
        self.assertEqual(caught.exception.code, "unknown_driver")

    def test_unknown_connector_kind_fails_closed(self):
        registry = build_fake_registry()
        with self.assertRaises(ConnectorRegistryError) as caught:
            registry.resolve("unknown", "fake-agent")
        self.assertEqual(caught.exception.code, "unknown_connector_kind")

    def test_resolve_config_uses_kind_and_driver_pair(self):
        registry = build_fake_registry()
        config = _config()
        driver = registry.resolve_config(config)
        self.assertEqual(driver.driver_id, "fake-agent")

    def test_fake_driver_capabilities_are_stable_and_serializable(self):
        driver = fake_agent_driver()
        capabilities = driver.declared_capabilities(_config())
        self.assertEqual(
            capabilities.to_dict(),
            {
                "tiers": ["T1", "T2"],
                "task_classes": ["coder", "docs", "tests"],
                "tools": ["git", "pytest"],
                "candidate_types": ["artifact_bundle", "github_pull_request"],
                "max_risk": "medium",
                "external_processing": False,
            },
        )
        json.dumps(capabilities.to_dict(), sort_keys=True)

    def test_driver_config_mismatch_is_explicit(self):
        driver = fake_agent_driver()
        wrong = _config(kind="model", driver="fake-model")
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(wrong)
        self.assertEqual(caught.exception.code, "driver_config_mismatch")

    def test_capability_declaration_rejects_unknown_tier_and_risk(self):
        with self.assertRaisesRegex(ValueError, "unknown capability"):
            DriverCapabilities(capability_tiers=frozenset({"T9"}))
        with self.assertRaisesRegex(ValueError, "unknown max_risk"):
            DriverCapabilities(max_risk="impossible")

    def test_capability_collections_reject_strings_and_non_string_items(self):
        with self.assertRaisesRegex(ValueError, "not a string"):
            DriverCapabilities(task_classes="coder")
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            DriverCapabilities(tools={"git", 7})

    def test_registry_has_no_routing_or_execution_methods(self):
        registry = build_fake_registry()
        for forbidden in ("route", "execute", "dispatch", "probe"):
            self.assertFalse(
                hasattr(registry, forbidden),
                f"registry must not become a {forbidden} authority surface",
            )

    def test_registry_logic_is_provider_neutral(self):
        names = {item.driver_id for item in build_fake_registry().descriptors()}
        self.assertEqual(
            names,
            {"fake-scm", "fake-agent", "fake-model", "fake-execution"},
        )

    def test_profile_claim_cannot_upgrade_driver_capability(self):
        registry = build_fake_registry()
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "overclaiming-agent",
            "kind": "agent",
            "driver": "fake-agent",
            "enabled": True,
            "capabilities": {"tiers": ["T4"]},
        }
        config = parse_connector_profile_document(raw)[0]
        driver = registry.resolve_config(config)
        declared = driver.declared_capabilities(config)
        self.assertEqual(declared.capability_tiers, frozenset({"T1", "T2"}))
        self.assertNotIn("T4", declared.capability_tiers)

    def test_driver_without_capability_interface_is_rejected(self):
        class BrokenDriver:
            kind = "agent"
            driver_id = "broken"
            driver_version = "0.1"

        registry = ConnectorRegistry()
        with self.assertRaises(ConnectorRegistryError) as caught:
            registry.register(BrokenDriver())
        self.assertEqual(caught.exception.code, "invalid_driver_interface")

    def test_malformed_driver_metadata_fails_with_registry_errors(self):
        class BadKind:
            kind = []
            driver_id = "broken"
            driver_version = "0.1"

            def declared_capabilities(self, config):
                return DriverCapabilities()

        class BlankVersion:
            kind = "agent"
            driver_id = "broken"
            driver_version = "   "

            def declared_capabilities(self, config):
                return DriverCapabilities()

        registry = ConnectorRegistry()
        with self.assertRaises(ConnectorRegistryError) as bad_kind:
            registry.register(BadKind())
        self.assertEqual(bad_kind.exception.code, "unknown_connector_kind")

        with self.assertRaises(ConnectorRegistryError) as blank_version:
            registry.register(BlankVersion())
        self.assertEqual(blank_version.exception.code, "invalid_driver_version")

    def test_custom_driver_can_register_without_registry_code_change(self):
        registry = ConnectorRegistry()
        custom = StaticFakeDriver(
            kind="agent",
            driver_id="custom-test-driver",
            driver_version="7.0",
            capabilities=DriverCapabilities(
                capability_tiers=frozenset({"T1"}),
                task_classes=frozenset({"coder"}),
            ),
        )
        registry.register(custom)
        resolved = registry.resolve("agent", "custom-test-driver")
        self.assertIs(resolved, custom)


if __name__ == "__main__":
    unittest.main()
