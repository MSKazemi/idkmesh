import json
import unittest

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.connector_probe import (
    DriverProbeOutcome,
    FakeProbeDriver,
    ProbeFailure,
    probe_connector,
)
from idkmesh.connector_registry import ConnectorRegistry, DriverCapabilities


CHECKED_AT = "2026-09-22T14:15:00Z"


def _config(*, enabled=True, with_secret=False):
    raw = {
        "api_version": "idkmesh.io/v1alpha1",
        "id": "probe-target",
        "kind": "agent",
        "driver": "fake-probe-agent",
        "enabled": enabled,
        "capabilities": {
            "tiers": ["T1"],
            "task_classes": ["coder"],
            "tools": ["git"],
        },
    }
    if with_secret:
        raw["auth"] = {"secret_ref": "env:FAKE_PROVIDER_KEY"}
    return parse_connector_profile_document(raw)[0]


def _registry(driver):
    registry = ConnectorRegistry()
    registry.register(driver)
    return registry


class ConnectorProbeTests(unittest.TestCase):
    def test_healthy_probe_is_stable_and_serializable(self):
        driver = FakeProbeDriver()
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.connection_id, "probe-target")
        self.assertEqual(driver.probe_calls, 1)
        rendered = result.to_dict()
        self.assertEqual(rendered["driver"]["driver"], "fake-probe-agent")
        self.assertEqual(rendered["observed"]["capabilities"]["tiers"], ["T1"])
        self.assertTrue(rendered["auth"]["configured"])
        self.assertIsNone(rendered["failure"])
        json.dumps(rendered, sort_keys=True)

    def test_degraded_probe_preserves_symbolic_warning(self):
        driver = FakeProbeDriver(
            outcome=DriverProbeOutcome(
                status="degraded",
                warnings=("capacity_low",),
            )
        )
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.warnings, ("capacity_low",))

    def test_provider_outage_is_distinct_from_missing_configuration(self):
        provider_driver = FakeProbeDriver(
            outcome=DriverProbeOutcome(
                status="unavailable",
                failure=ProbeFailure("provider_unavailable", "provider_unreachable"),
            )
        )
        provider = probe_connector(
            _config(),
            _registry(provider_driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(provider.failure.kind, "provider_unavailable")
        self.assertEqual(provider.failure.code, "provider_unreachable")
        self.assertEqual(provider_driver.probe_calls, 1)

        config_driver = FakeProbeDriver()
        configuration = probe_connector(
            _config(with_secret=True),
            _registry(config_driver),
            checked_at=CHECKED_AT,
            secret_available=False,
        )
        self.assertEqual(configuration.status, "unavailable")
        self.assertEqual(configuration.failure.kind, "configuration")
        self.assertEqual(configuration.failure.code, "secret_unavailable")
        self.assertEqual(config_driver.probe_calls, 0)

    def test_missing_secret_fails_closed_when_availability_unknown(self):
        driver = FakeProbeDriver()
        result = probe_connector(
            _config(with_secret=True),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertFalse(result.auth_configured)
        self.assertEqual(result.failure.code, "secret_unavailable")
        self.assertEqual(driver.probe_calls, 0)

    def test_available_secret_is_only_a_boolean_observation(self):
        driver = FakeProbeDriver()
        result = probe_connector(
            _config(with_secret=True),
            _registry(driver),
            checked_at=CHECKED_AT,
            secret_available=True,
        )
        rendered = json.dumps(result.to_dict(), sort_keys=True)
        self.assertTrue(result.auth_configured)
        self.assertNotIn("FAKE_PROVIDER_KEY", rendered)
        self.assertNotIn("secret_ref", rendered)
        self.assertEqual(driver.probe_calls, 1)

    def test_disabled_connector_never_calls_driver_probe(self):
        driver = FakeProbeDriver(
            outcome=DriverProbeOutcome(
                status="unavailable",
                failure=ProbeFailure("provider_error", "should_not_run"),
            )
        )
        result = probe_connector(
            _config(enabled=False),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result.status, "disabled")
        self.assertEqual(driver.probe_calls, 0)

    def test_driver_without_probe_interface_fails_as_structured_health(self):
        from idkmesh.connector_registry import StaticFakeDriver

        driver = StaticFakeDriver(
            kind="agent",
            driver_id="fake-probe-agent",
            driver_version="0.1",
            capabilities=DriverCapabilities(
                capability_tiers=frozenset({"T1"}),
                task_classes=frozenset({"coder"}),
            ),
        )
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.failure.kind, "driver_error")
        self.assertEqual(result.failure.code, "probe_interface_missing")

    def test_probe_exception_is_normalized_without_raw_provider_text(self):
        class ExplodingDriver(FakeProbeDriver):
            def probe(self, config):
                raise RuntimeError("Authorization: bearer super-secret-value")

        driver = ExplodingDriver()
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        rendered = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.failure.code, "probe_exception")
        self.assertNotIn("super-secret-value", rendered)
        self.assertNotIn("Authorization", rendered)

    def test_capability_exception_is_normalized_without_raw_provider_text(self):
        class ExplodingCapabilities(FakeProbeDriver):
            def declared_capabilities(self, config):
                raise RuntimeError("X-Api-Key: another-secret-value")

        driver = ExplodingCapabilities()
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        rendered = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.failure.code, "capability_declaration_failed")
        self.assertEqual(result.observed_capabilities.to_dict()["tiers"], [])
        self.assertNotIn("another-secret-value", rendered)
        self.assertNotIn("X-Api-Key", rendered)

    def test_invalid_probe_outcome_fails_closed(self):
        class BadProbeDriver(FakeProbeDriver):
            def probe(self, config):
                self.probe_calls += 1
                return {"status": "healthy"}

        driver = BadProbeDriver()
        result = probe_connector(
            _config(),
            _registry(driver),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.failure.code, "invalid_probe_outcome")

    def test_healthy_probe_cannot_carry_failure(self):
        with self.assertRaisesRegex(ValueError, "healthy"):
            DriverProbeOutcome(
                status="healthy",
                failure=ProbeFailure("provider_error", "bad_state"),
            )

    def test_unavailable_probe_requires_failure(self):
        with self.assertRaisesRegex(ValueError, "requires a failure"):
            DriverProbeOutcome(status="unavailable")

    def test_warning_and_failure_codes_reject_free_form_provider_text(self):
        with self.assertRaisesRegex(ValueError, "safe symbolic code"):
            DriverProbeOutcome(status="degraded", warnings=("Authorization: secret",))
        with self.assertRaisesRegex(ValueError, "safe symbolic code"):
            ProbeFailure("provider_error", "token leaked here")

    def test_checked_at_is_explicit_and_required(self):
        driver = FakeProbeDriver()
        with self.assertRaisesRegex(ValueError, "checked_at"):
            probe_connector(_config(), _registry(driver), checked_at="")


if __name__ == "__main__":
    unittest.main()
