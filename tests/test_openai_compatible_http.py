import json
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_http import (
    OpenAICompatibleClient,
    OpenAICompatibleHttpResponse,
)


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response or OpenAICompatibleHttpResponse(
            200,
            {},
            b'{"data":[]}',
        )
        self.error = error
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _config(**overrides):
    kwargs = {
        "connection_id": "model-main",
        "base_url": "https://example.com/v1",
        "model": "model-a",
        "allowed_models": frozenset({"model-a", "model-b"}),
        "secret_ref": "env:MODEL_KEY",
    }
    kwargs.update(overrides)
    return OpenAICompatibleModelConfig(**kwargs)


class OpenAICompatibleProbeTests(unittest.TestCase):
    def test_required_runtime_credential_fails_before_transport(self):
        with self.assertRaises(ConnectorError) as caught:
            OpenAICompatibleClient(_config(), transport=FakeTransport())
        self.assertEqual(caught.exception.code, "authentication_error")

    def test_bearer_header_is_runtime_only(self):
        transport = FakeTransport(
            OpenAICompatibleHttpResponse(
                200,
                {},
                b'{"data":[{"id":"model-a"}]}',
            )
        )
        client = OpenAICompatibleClient(
            _config(),
            api_key="sentinel-runtime-key",
            transport=transport,
        )
        result = client.probe()
        self.assertEqual(result.status, "healthy")
        call = transport.calls[0]
        self.assertEqual(call["url"], "https://example.com/v1/models")
        self.assertEqual(
            call["headers"]["Authorization"],
            "Bearer sentinel-runtime-key",
        )
        self.assertNotIn("sentinel-runtime-key", str(result))

    def test_local_no_secret_endpoint_sends_no_authorization(self):
        transport = FakeTransport(
            OpenAICompatibleHttpResponse(
                200,
                {},
                b'{"data":[{"id":"local-model"}]}',
            )
        )
        config = OpenAICompatibleModelConfig(
            connection_id="ollama-local",
            base_url="http://127.0.0.1:11434/v1",
            model="local-model",
            external_processing=False,
        )
        result = OpenAICompatibleClient(
            config,
            transport=transport,
        ).probe()
        self.assertEqual(result.status, "healthy")
        self.assertNotIn("Authorization", transport.calls[0]["headers"])

    def test_probe_is_degraded_when_allowlisted_model_is_not_observed(self):
        transport = FakeTransport(
            OpenAICompatibleHttpResponse(
                200,
                {},
                b'{"data":[{"id":"model-b"}]}',
            )
        )
        result = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=transport,
        ).probe()
        self.assertEqual(result.status, "degraded")
        self.assertFalse(result.model_available)
        self.assertIn("configured_model_not_observed", result.warnings)

    def test_model_ids_are_deduplicated_and_sorted(self):
        transport = FakeTransport(
            OpenAICompatibleHttpResponse(
                200,
                {},
                b'{"data":[{"id":"z"},{"id":"a"},{"id":"z"}]}',
            )
        )
        client = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=transport,
        )
        self.assertEqual(client.list_models(), ("a", "z"))

    def test_malformed_model_list_fails_closed(self):
        payloads = [
            {},
            {"data": "bad"},
            {"data": ["bad"]},
            {"data": [{"id": ""}]},
            {"data": [{"id": 7}]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                client = OpenAICompatibleClient(
                    _config(),
                    api_key="key",
                    transport=FakeTransport(
                        OpenAICompatibleHttpResponse(
                            200,
                            {},
                            json.dumps(payload).encode(),
                        )
                    ),
                )
                with self.assertRaises(ConnectorError) as caught:
                    client.list_models()
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

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
                client = OpenAICompatibleClient(
                    _config(),
                    api_key="sentinel",
                    transport=FakeTransport(
                        OpenAICompatibleHttpResponse(
                            status,
                            {"Retry-After": "45"},
                            b'{"error":{"message":"raw provider detail"}}',
                        )
                    ),
                )
                with self.assertRaises(ConnectorError) as caught:
                    client.list_models()
                self.assertEqual(caught.exception.code, code)
                rendered = json.dumps(caught.exception.to_envelope())
                self.assertNotIn("sentinel", rendered)
                self.assertNotIn("raw provider detail", rendered)

    def test_rate_limit_retains_only_safe_retry_metadata(self):
        client = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=FakeTransport(
                OpenAICompatibleHttpResponse(
                    429,
                    {"Retry-After": "120"},
                    b'{"error":{"message":"ignored"}}',
                )
            ),
        )
        with self.assertRaises(ConnectorError) as caught:
            client.list_models()
        details = caught.exception.to_envelope()["error"]["details"]
        self.assertEqual(details, {"http_status": 429, "retry_after_seconds": 120})

    def test_timeout_and_transport_failure_are_normalized(self):
        timeout = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=FakeTransport(error=TimeoutError("raw timeout")),
        )
        with self.assertRaises(ConnectorError) as caught_timeout:
            timeout.list_models()
        self.assertEqual(caught_timeout.exception.code, "timeout")

        offline = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=FakeTransport(error=OSError("raw DNS detail")),
        )
        with self.assertRaises(ConnectorError) as caught_offline:
            offline.list_models()
        self.assertEqual(
            caught_offline.exception.code,
            "provider_unavailable",
        )
        self.assertNotIn("DNS", str(caught_offline.exception))

    def test_custom_transport_cannot_bypass_response_boundaries(self):
        cases = [
            OpenAICompatibleHttpResponse(True, {}, b"{}"),
            OpenAICompatibleHttpResponse(200, {}, "not-bytes"),
        ]
        for response in cases:
            with self.subTest(response=response):
                client = OpenAICompatibleClient(
                    _config(),
                    api_key="key",
                    transport=FakeTransport(response),
                )
                with self.assertRaises(ConnectorError) as caught:
                    client.list_models()
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

        oversized = OpenAICompatibleClient(
            _config(max_response_bytes=2),
            api_key="key",
            transport=FakeTransport(
                OpenAICompatibleHttpResponse(200, {}, b"{}x")
            ),
        )
        with self.assertRaises(ConnectorError) as caught:
            oversized.list_models()
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_non_json_success_fails_closed(self):
        client = OpenAICompatibleClient(
            _config(),
            api_key="key",
            transport=FakeTransport(
                OpenAICompatibleHttpResponse(200, {}, b"not-json")
            ),
        )
        with self.assertRaises(ConnectorError) as caught:
            client.list_models()
        self.assertEqual(caught.exception.code, "result_normalization_error")


if __name__ == "__main__":
    unittest.main()
