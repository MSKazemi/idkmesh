import unittest

from idkmesh.openai_compatible import OpenAICompatibleModelConfig


class OpenAICompatibleModelConfigTests(unittest.TestCase):
    def test_gemini_compatible_endpoint_contract(self):
        config = OpenAICompatibleModelConfig(
            connection_id="gemini-compatible",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            model="gemini-example",
            allowed_models=frozenset({"gemini-example", "gemini-other"}),
            secret_ref="env:GEMINI_API_KEY",
            external_processing=True,
            project_spend_usd_max=0,
        )
        self.assertEqual(
            config.base_url,
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )
        self.assertTrue(config.auth_required)
        self.assertEqual(
            config.endpoint("/models"),
            "https://generativelanguage.googleapis.com/v1beta/openai/models",
        )

    def test_ollama_loopback_contract_needs_no_secret(self):
        config = OpenAICompatibleModelConfig(
            connection_id="ollama-local",
            base_url="http://127.0.0.1:11434/v1/",
            model="local-model",
            external_processing=False,
        )
        self.assertEqual(config.base_url, "http://127.0.0.1:11434/v1")
        self.assertFalse(config.auth_required)
        self.assertEqual(config.allowed_models, frozenset({"local-model"}))

    def test_non_loopback_plain_http_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            OpenAICompatibleModelConfig(
                connection_id="unsafe",
                base_url="http://example.com/v1",
                model="model",
            )

    def test_base_url_rejects_embedded_credentials_query_and_fragment(self):
        cases = [
            "https://user:pass@example.com/v1",
            "https://example.com/v1?x=1",
            "https://example.com/v1#fragment",
            "example.com/v1",
        ]
        for base_url in cases:
            with self.subTest(base_url=base_url):
                with self.assertRaises(ValueError):
                    OpenAICompatibleModelConfig(
                        connection_id="bad",
                        base_url=base_url,
                        model="model",
                    )

    def test_model_must_be_allowlisted(self):
        with self.assertRaisesRegex(ValueError, "allowed_models"):
            OpenAICompatibleModelConfig(
                connection_id="provider",
                base_url="https://example.com/v1",
                model="model-b",
                allowed_models=frozenset({"model-a"}),
            )

    def test_model_switch_stays_inside_allowlist(self):
        config = OpenAICompatibleModelConfig(
            connection_id="provider",
            base_url="https://example.com/v1/",
            model="model-a",
            allowed_models=frozenset({"model-a", "model-b"}),
        )
        switched = config.with_model("model-b")
        self.assertEqual(switched.model, "model-b")
        self.assertEqual(switched.allowed_models, config.allowed_models)

        with self.assertRaisesRegex(ValueError, "allowlisted"):
            config.with_model("model-c")

    def test_allowlist_rejects_string_and_non_string_entries(self):
        with self.assertRaisesRegex(ValueError, "not a string"):
            OpenAICompatibleModelConfig(
                connection_id="provider",
                base_url="https://example.com/v1",
                model="model",
                allowed_models="model",
            )
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            OpenAICompatibleModelConfig(
                connection_id="provider",
                base_url="https://example.com/v1",
                model="model",
                allowed_models={"model", 7},
            )

    def test_secret_reference_is_metadata_not_credential_material(self):
        config = OpenAICompatibleModelConfig(
            connection_id="provider",
            base_url="https://example.com/v1",
            model="model",
            secret_ref="env:MODEL_KEY",
        )
        self.assertEqual(config.secret_ref, "env:MODEL_KEY")
        self.assertTrue(config.auth_required)

        with self.assertRaisesRegex(ValueError, "whitespace"):
            OpenAICompatibleModelConfig(
                connection_id="provider",
                base_url="https://example.com/v1",
                model="model",
                secret_ref="env:BAD KEY",
            )

    def test_timeout_response_limit_and_spend_fail_closed(self):
        bad_values = [
            ("timeout_seconds", 0),
            ("timeout_seconds", float("nan")),
            ("max_response_bytes", 0),
            ("project_spend_usd_max", -1),
            ("project_spend_usd_max", float("inf")),
        ]
        for field_name, value in bad_values:
            with self.subTest(field_name=field_name, value=value):
                kwargs = {
                    "connection_id": "provider",
                    "base_url": "https://example.com/v1",
                    "model": "model",
                    field_name: value,
                }
                with self.assertRaises(ValueError):
                    OpenAICompatibleModelConfig(**kwargs)

    def test_external_processing_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            OpenAICompatibleModelConfig(
                connection_id="provider",
                base_url="https://example.com/v1",
                model="model",
                external_processing=1,
            )

    def test_endpoint_path_cannot_override_origin_or_add_query(self):
        config = OpenAICompatibleModelConfig(
            connection_id="provider",
            base_url="https://example.com/v1",
            model="model",
        )
        for path in (
            "models",
            "https://evil.example/models",
            "/models?limit=10",
            "/models#x",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    config.endpoint(path)


if __name__ == "__main__":
    unittest.main()
