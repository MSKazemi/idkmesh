import json
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_client import (
    DEFAULT_BASE_URL,
    JulesClient,
    JulesHttpResponse,
)


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response or JulesHttpResponse(200, {}, b"{}")
        self.error = error
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class JulesClientTests(unittest.TestCase):
    def test_defaults_match_current_jules_alpha_api(self):
        client = JulesClient(api_key="runtime-key", transport=FakeTransport())
        self.assertEqual(client.base_url, "https://jules.googleapis.com/v1alpha")
        self.assertEqual(client.base_url, DEFAULT_BASE_URL)

    def test_auth_header_and_timeout_are_built_without_logging_key(self):
        transport = FakeTransport(JulesHttpResponse(200, {}, b'{"sources":[]}'))
        client = JulesClient(
            api_key="sentinel-secret",
            connection_id="jules-main",
            timeout_seconds=12.5,
            transport=transport,
        )
        result = client.get_json("/sources", query={"pageSize": 5})
        self.assertEqual(result, {"sources": []})
        call = transport.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(
            call["url"],
            "https://jules.googleapis.com/v1alpha/sources?pageSize=5",
        )
        self.assertEqual(call["headers"]["X-Goog-Api-Key"], "sentinel-secret")
        self.assertNotIn("Content-Type", call["headers"])
        self.assertEqual(call["timeout_seconds"], 12.5)
        self.assertNotIn("sentinel-secret", repr(client.__dict__.keys()))

    def test_post_uses_strict_json_and_content_type(self):
        transport = FakeTransport(JulesHttpResponse(200, {}, b'{"id":"123"}'))
        client = JulesClient(api_key="runtime-key", transport=transport)
        result = client.post_json(
            "/sessions",
            body={"requirePlanApproval": True, "prompt": "Add tests"},
        )
        self.assertEqual(result["id"], "123")
        call = transport.calls[0]
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertEqual(
            json.loads(call["body"].decode("utf-8")),
            {"prompt": "Add tests", "requirePlanApproval": True},
        )

    def test_invalid_request_json_fails_as_configuration_error(self):
        client = JulesClient(api_key="runtime-key", transport=FakeTransport())
        with self.assertRaises(ConnectorError) as caught:
            client.post_json("/sessions", body={"bad": float("nan")})
        self.assertEqual(caught.exception.code, "configuration_error")

    def test_http_statuses_map_to_shared_error_codes(self):
        expected = {
            400: "configuration_error",
            401: "authentication_error",
            403: "authorization_error",
            404: "not_found",
            409: "conflict",
            429: "rate_limited",
            500: "provider_unavailable",
            503: "provider_unavailable",
        }
        for status, code in expected.items():
            with self.subTest(status=status):
                transport = FakeTransport(
                    JulesHttpResponse(status, {}, b'{"error":{"message":"ignored"}}')
                )
                client = JulesClient(
                    api_key="sentinel-secret",
                    connection_id="jules-main",
                    transport=transport,
                )
                with self.assertRaises(ConnectorError) as caught:
                    client.get_json("/sources")
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.connection_id, "jules-main")
                self.assertNotIn("sentinel-secret", str(caught.exception))
                self.assertNotIn("ignored", str(caught.exception))

    def test_retry_after_is_retained_without_raw_provider_body(self):
        transport = FakeTransport(
            JulesHttpResponse(
                429,
                {"Retry-After": "120"},
                b'{"error":{"message":"provider detail must not leak"}}',
            )
        )
        client = JulesClient(api_key="runtime-key", transport=transport)
        with self.assertRaises(ConnectorError) as caught:
            client.get_json("/sessions")
        envelope = caught.exception.to_envelope()["error"]
        self.assertEqual(envelope["details"]["retry_after_seconds"], 120)
        self.assertEqual(envelope["details"]["http_status"], 429)
        self.assertNotIn("provider detail", json.dumps(envelope))

    def test_timeout_and_transport_failure_are_normalized(self):
        timeout_client = JulesClient(
            api_key="runtime-key",
            transport=FakeTransport(error=TimeoutError("raw timeout")),
        )
        with self.assertRaises(ConnectorError) as timeout:
            timeout_client.get_json("/sources")
        self.assertEqual(timeout.exception.code, "timeout")
        self.assertTrue(timeout.exception.is_retryable)

        offline_client = JulesClient(
            api_key="runtime-key",
            transport=FakeTransport(error=OSError("dns details")),
        )
        with self.assertRaises(ConnectorError) as offline:
            offline_client.get_json("/sources")
        self.assertEqual(offline.exception.code, "provider_unavailable")
        self.assertTrue(offline.exception.is_retryable)
        self.assertNotIn("dns details", str(offline.exception))

    def test_non_json_or_non_object_success_is_normalization_error(self):
        for body in (b"not-json", b'["array"]'):
            with self.subTest(body=body):
                client = JulesClient(
                    api_key="runtime-key",
                    transport=FakeTransport(JulesHttpResponse(200, {}, body)),
                )
                with self.assertRaises(ConnectorError) as caught:
                    client.get_json("/sources")
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_custom_transport_cannot_bypass_response_boundaries(self):
        oversized = JulesClient(
            api_key="runtime-key",
            max_response_bytes=2,
            transport=FakeTransport(JulesHttpResponse(200, {}, b"{}x")),
        )
        with self.assertRaises(ConnectorError) as too_large:
            oversized.get_json("/sources")
        self.assertEqual(
            too_large.exception.code,
            "result_normalization_error",
        )

        bad_status = JulesClient(
            api_key="runtime-key",
            transport=FakeTransport(JulesHttpResponse(True, {}, b"{}")),
        )
        with self.assertRaises(ConnectorError) as status:
            bad_status.get_json("/sources")
        self.assertEqual(status.exception.code, "result_normalization_error")

        bad_body = JulesClient(
            api_key="runtime-key",
            transport=FakeTransport(JulesHttpResponse(200, {}, "not-bytes")),
        )
        with self.assertRaises(ConnectorError) as body:
            bad_body.get_json("/sources")
        self.assertEqual(body.exception.code, "result_normalization_error")

    def test_empty_success_body_returns_empty_object(self):
        client = JulesClient(
            api_key="runtime-key",
            transport=FakeTransport(JulesHttpResponse(200, {}, b"")),
        )
        self.assertEqual(client.post_json("/sessions/123:approvePlan"), {})

    def test_path_cannot_override_base_url_or_query_builder(self):
        client = JulesClient(api_key="runtime-key", transport=FakeTransport())
        for path in (
            "sources",
            "https://evil.example/sources",
            "/sources?pageSize=100",
            "/sources#fragment",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    client.get_json(path)

    def test_plain_http_is_loopback_only(self):
        JulesClient(
            api_key="runtime-key",
            base_url="http://127.0.0.1:9999/v1alpha",
            transport=FakeTransport(),
        )
        with self.assertRaisesRegex(ValueError, "loopback"):
            JulesClient(
                api_key="runtime-key",
                base_url="http://example.com/v1alpha",
                transport=FakeTransport(),
            )

    def test_invalid_timeout_and_response_limit_fail_before_transport(self):
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            JulesClient(api_key="runtime-key", timeout_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "max_response_bytes"):
            JulesClient(api_key="runtime-key", max_response_bytes=0)

    def test_invalid_query_value_fails_before_transport(self):
        client = JulesClient(api_key="runtime-key", transport=FakeTransport())
        with self.assertRaisesRegex(ValueError, "query values"):
            client.get_json("/sources", query={"pageSize": True})


if __name__ == "__main__":
    unittest.main()
