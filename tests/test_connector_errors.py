import json
import unittest

from idkmesh.connector_errors import (
    ERROR_CODES,
    ConnectorError,
    connector_error,
    sanitize_error_details,
)


class ConnectorErrorTests(unittest.TestCase):
    def test_all_documented_codes_construct(self):
        for code in sorted(ERROR_CODES):
            with self.subTest(code=code):
                error = ConnectorError(code=code, message="failure")
                self.assertEqual(error.code, code)

    def test_unknown_code_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown connector error code"):
            ConnectorError(code="provider_confused", message="failure")

    def test_retry_defaults_are_conservative(self):
        self.assertTrue(
            ConnectorError(code="rate_limited", message="retry later").is_retryable
        )
        self.assertTrue(
            ConnectorError(code="provider_unavailable", message="offline").is_retryable
        )
        self.assertTrue(
            ConnectorError(code="timeout", message="timed out").is_retryable
        )
        self.assertFalse(
            ConnectorError(code="authentication_error", message="bad auth").is_retryable
        )
        self.assertFalse(
            ConnectorError(code="verification_failed", message="bad result").is_retryable
        )

    def test_retryability_can_be_explicitly_overridden(self):
        error = ConnectorError(
            code="rate_limited",
            message="provider says do not retry",
            retryable=False,
        )
        self.assertFalse(error.is_retryable)

    def test_envelope_matches_api_shape_and_is_strict_json(self):
        error = ConnectorError(
            code="rate_limited",
            message="Connector is temporarily rate limited.",
            connection_id="jules-main",
            run_id="run-123",
            details={"retry_after_seconds": 120},
        )
        envelope = error.to_envelope()
        self.assertEqual(
            envelope,
            {
                "error": {
                    "code": "rate_limited",
                    "message": "Connector is temporarily rate limited.",
                    "retryable": True,
                    "connection_id": "jules-main",
                    "run_id": "run-123",
                    "details": {"retry_after_seconds": 120},
                }
            },
        )
        json.dumps(envelope, allow_nan=False, sort_keys=True)

    def test_sensitive_detail_keys_are_redacted_recursively(self):
        sentinel = "super-secret-provider-value"
        safe = sanitize_error_details(
            {
                "request": {
                    "Authorization": f"Bearer {sentinel}",
                    "headers": {
                        "X-API-Key": sentinel,
                        "safe": "request-42",
                    },
                },
                "access_token": sentinel,
            }
        )
        rendered = json.dumps(safe, sort_keys=True)
        self.assertNotIn(sentinel, rendered)
        self.assertEqual(safe["access_token"], "[REDACTED]")
        self.assertEqual(safe["request"]["Authorization"], "[REDACTED]")
        self.assertEqual(safe["request"]["headers"]["X-API-Key"], "[REDACTED]")
        self.assertEqual(safe["request"]["headers"]["safe"], "request-42")

    def test_authorization_shaped_values_are_redacted_even_under_safe_key(self):
        safe = sanitize_error_details({"upstream_message": "Bearer abc123"})
        self.assertEqual(safe["upstream_message"], "[REDACTED]")

    def test_exception_string_never_contains_details(self):
        sentinel = "secret-value"
        error = ConnectorError(
            code="authentication_error",
            message="Authentication failed.",
            details={"token": sentinel, "request_id": "req-7"},
        )
        self.assertEqual(str(error), "Authentication failed.")
        self.assertNotIn(sentinel, str(error))
        self.assertNotIn("req-7", str(error))

    def test_nonfinite_and_non_json_detail_values_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            ConnectorError(
                code="provider_unavailable",
                message="bad number",
                details={"latency": float("nan")},
            )

        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            ConnectorError(
                code="provider_unavailable",
                message="bad object",
                details={"value": object()},
            )

    def test_non_string_detail_key_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "keys"):
            sanitize_error_details({7: "value"})

    def test_factory_uses_same_sanitizing_boundary(self):
        error = connector_error(
            "authentication_error",
            "Authentication failed.",
            connection_id="jules-main",
            details={"password": "do-not-leak"},
        )
        self.assertIsInstance(error, ConnectorError)
        self.assertEqual(
            error.to_envelope()["error"]["details"]["password"],
            "[REDACTED]",
        )


if __name__ == "__main__":
    unittest.main()
