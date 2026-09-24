import hashlib
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
import unittest
from unittest.mock import patch

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_http import OpenAICompatibleHttpResponse
from idkmesh.openai_compatible_smoke import run_openai_compatible_smoke
from scripts.smoke_openai_compatible import main


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _config(*, secret_ref=None):
    return OpenAICompatibleModelConfig(
        connection_id="smoke-model",
        base_url="http://127.0.0.1:11434/v1",
        model="local-model",
        allowed_models=frozenset({"local-model"}),
        secret_ref=secret_ref,
        external_processing=False,
    )


def _transport(text="SMOKE OK"):
    model_payload = json.dumps(
        {"data": [{"id": "local-model"}]}
    ).encode()
    completion_payload = json.dumps(
        {
            "id": "chatcmpl-smoke",
            "model": "local-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
            },
        }
    ).encode()
    return SequenceTransport(
        [
            OpenAICompatibleHttpResponse(200, {}, model_payload),
            OpenAICompatibleHttpResponse(200, {}, completion_payload),
        ]
    )


class OpenAICompatibleSmokeTests(unittest.TestCase):
    def test_smoke_evidence_contains_digest_not_raw_completion(self):
        transport = _transport("sensitive-ish completion text")
        evidence = run_openai_compatible_smoke(
            _config(),
            checked_at="2026-09-24T00:00:00Z",
            transport=transport,
        )
        rendered = json.dumps(evidence.to_dict(), sort_keys=True)
        self.assertNotIn("sensitive-ish completion text", rendered)
        self.assertEqual(
            evidence.response_sha256,
            hashlib.sha256(
                b"sensitive-ish completion text"
            ).hexdigest(),
        )
        self.assertEqual(evidence.response_chars, 29)
        self.assertEqual(evidence.probe_status, "healthy")
        self.assertTrue(evidence.model_available)
        self.assertEqual(evidence.total_tokens, 7)

    def test_smoke_calls_models_then_chat_completion(self):
        transport = _transport()
        run_openai_compatible_smoke(
            _config(),
            checked_at="2026-09-24T00:00:00Z",
            transport=transport,
        )
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [
                "http://127.0.0.1:11434/v1/models",
                "http://127.0.0.1:11434/v1/chat/completions",
            ],
        )

    def test_missing_model_blocks_before_chat_completion(self):
        transport = SequenceTransport(
            [
                OpenAICompatibleHttpResponse(
                    200,
                    {},
                    b'{"data":[{"id":"other-model"}]}',
                )
            ]
        )
        with self.assertRaises(ConnectorError) as caught:
            run_openai_compatible_smoke(
                _config(),
                transport=transport,
            )
        self.assertEqual(caught.exception.code, "configuration_error")
        self.assertEqual(len(transport.calls), 1)

    def test_empty_completion_fails_closed(self):
        transport = _transport("")
        with self.assertRaises(ConnectorError) as caught:
            run_openai_compatible_smoke(
                _config(),
                transport=transport,
            )
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_cli_never_accepts_or_echoes_literal_api_key_option(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                [
                    "--base-url",
                    "https://example.com/v1",
                    "--model",
                    "model",
                    "--api-key",
                    "literal-secret",
                ]
            )
        self.assertEqual(code, 2)
        self.assertNotIn("literal-secret", stderr.getvalue())
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "configuration_error")

    def test_cli_missing_secret_env_reports_reference_not_value(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with redirect_stderr(stderr):
                code = main(
                    [
                        "--base-url",
                        "https://example.com/v1",
                        "--model",
                        "model",
                        "--secret-env",
                        "MISSING_MODEL_KEY",
                    ]
                )
        self.assertEqual(code, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(
            payload["error"]["details"]["secret_ref"],
            "env:MISSING_MODEL_KEY",
        )
        self.assertEqual(payload["error"]["code"], "authentication_error")
        self.assertIs(payload["error"]["retryable"], False)

    def test_cli_refuses_every_shape_that_could_echo_a_credential(self):
        secret = "sk-live-NEVER-ECHO-THIS"
        rejected_command_lines = (
            # a credential mistakenly passed as the --secret-env value
            ["--secret-env", secret],
            # a credential-looking option outside any enumerated denylist
            ["--key", secret],
            ["--apikey=" + secret],
            ["--openai-api-key", secret],
            # an unambiguous argparse abbreviation of --secret-env
            ["--secret", secret],
            # a bare token in option position
            [secret],
            # a value argparse's own type= conversion would quote back
            ["--timeout-seconds", secret],
            # the three flags the original enumerated guard covered
            ["--api-key", secret],
            ["--token", secret],
            ["--authorization", "Bearer " + secret],
        )
        for extra in rejected_command_lines:
            with self.subTest(extra=extra[0]):
                stderr = io.StringIO()
                with patch.dict(os.environ, {}, clear=True):
                    with redirect_stderr(stderr):
                        code = main(
                            [
                                "--base-url",
                                "https://example.com/v1",
                                "--model",
                                "model",
                                *extra,
                            ]
                        )
                rendered = stderr.getvalue()
                self.assertEqual(code, 2)
                self.assertNotIn(secret, rendered)
                payload = json.loads(rendered)
                self.assertEqual(
                    payload["error"]["code"],
                    "configuration_error",
                )

    def test_resolved_api_key_never_reaches_smoke_evidence(self):
        secret = "sk-live-RESOLVED-KEY-VALUE"
        transport = _transport("SMOKE OK")
        evidence = run_openai_compatible_smoke(
            _config(secret_ref="env:MODEL_API_KEY"),
            api_key=secret,
            checked_at="2026-09-24T00:00:00Z",
            transport=transport,
        )
        rendered = json.dumps(evidence.to_dict(), sort_keys=True)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("Authorization", rendered)
        # Positive control: the key really was sent on the wire, so the
        # assertion above is not vacuous.
        self.assertEqual(
            transport.calls[0]["headers"]["Authorization"],
            f"Bearer {secret}",
        )

    def test_cli_success_outputs_only_safe_evidence(self):
        stdout = io.StringIO()
        transport = _transport("do not print this completion")
        with patch(
            "scripts.smoke_openai_compatible.run_openai_compatible_smoke",
            return_value=run_openai_compatible_smoke(
                _config(),
                checked_at="2026-09-24T00:00:00Z",
                transport=transport,
            ),
        ):
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--base-url",
                        "http://127.0.0.1:11434/v1",
                        "--model",
                        "local-model",
                        "--local",
                    ]
                )
        self.assertEqual(code, 0)
        rendered = stdout.getvalue()
        self.assertNotIn("do not print this completion", rendered)
        payload = json.loads(rendered)
        self.assertEqual(
            payload["schema"],
            "idkmesh.openai_compatible_smoke/v1",
        )


if __name__ == "__main__":
    unittest.main()
