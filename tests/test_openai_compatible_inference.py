import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_inference import (
    ChatCompletionRequest,
    ChatMessage,
    OpenAICompatibleChatService,
    parse_chat_completion,
)


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.config = OpenAICompatibleModelConfig(
            connection_id="model-main",
            base_url="https://example.com/v1",
            model="model-a",
            allowed_models=frozenset({"model-a"}),
        )

    def request_json(self, method, path, *, body=None):
        self.calls.append((method, path, body))
        return self.response


def _response(**overrides):
    payload = {
        "id": "chatcmpl-1",
        "model": "model-a",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Result text",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 3,
            "total_tokens": 13,
        },
    }
    payload.update(overrides)
    return payload


class OpenAICompatibleInferenceTests(unittest.TestCase):
    def test_request_is_narrow_non_streaming_text_chat(self):
        client = FakeClient(_response())
        service = OpenAICompatibleChatService(client)
        result = service.complete(
            ChatCompletionRequest(
                messages=(
                    ChatMessage("system", "Follow the task."),
                    ChatMessage("user", "Return a short result."),
                ),
                temperature=0.2,
                max_tokens=100,
            )
        )
        self.assertEqual(result.text, "Result text")
        method, path, body = client.calls[0]
        self.assertEqual((method, path), ("POST", "/chat/completions"))
        self.assertEqual(body["model"], "model-a")
        self.assertFalse(body["stream"])
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(body["max_tokens"], 100)

    def test_result_retains_small_canonical_metadata(self):
        result = parse_chat_completion(
            _response(),
            connection_id="model-main",
            configured_model="model-a",
        )
        self.assertEqual(result.response_id, "chatcmpl-1")
        self.assertEqual(result.model, "model-a")
        self.assertEqual(result.text, "Result text")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.usage.prompt_tokens, 10)
        self.assertEqual(result.usage.completion_tokens, 3)
        self.assertEqual(result.usage.total_tokens, 13)
        self.assertEqual(result.choice_count, 1)

    def test_provider_specific_reasoning_fields_are_not_retained(self):
        response = _response()
        response["choices"][0]["message"]["reasoning_content"] = "hidden trace"
        response["provider_extra"] = {"thoughts": "hidden provider trace"}
        result = parse_chat_completion(
            response,
            connection_id="model-main",
            configured_model="model-a",
        )
        self.assertFalse(hasattr(result, "reasoning_content"))
        self.assertFalse(hasattr(result, "provider_extra"))
        self.assertNotIn("hidden trace", repr(result))

    def test_model_identity_can_fall_back_to_config_when_omitted(self):
        response = _response()
        del response["model"]
        result = parse_chat_completion(
            response,
            connection_id="model-main",
            configured_model="model-a",
        )
        self.assertEqual(result.model, "model-a")

    def test_missing_usage_is_allowed(self):
        response = _response()
        del response["usage"]
        result = parse_chat_completion(
            response,
            connection_id="model-main",
            configured_model="model-a",
        )
        self.assertIsNone(result.usage.prompt_tokens)
        self.assertIsNone(result.usage.completion_tokens)
        self.assertIsNone(result.usage.total_tokens)

    def test_usage_must_be_nonnegative_and_consistent(self):
        bad_usage = [
            {"prompt_tokens": -1},
            {"prompt_tokens": True},
            {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 12},
            "bad",
        ]
        for usage in bad_usage:
            with self.subTest(usage=usage):
                response = _response(usage=usage)
                with self.assertRaises(ConnectorError) as caught:
                    parse_chat_completion(
                        response,
                        connection_id="model-main",
                        configured_model="model-a",
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_choice_zero_is_required_and_duplicate_indices_fail(self):
        cases = [
            _response(choices=[]),
            _response(
                choices=[
                    {
                        "index": 1,
                        "message": {"role": "assistant", "content": "x"},
                    }
                ]
            ),
            _response(
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "x"},
                    },
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "y"},
                    },
                ]
            ),
        ]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(ConnectorError) as caught:
                    parse_chat_completion(
                        response,
                        connection_id="model-main",
                        configured_model="model-a",
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_message_must_be_assistant_text(self):
        bad_messages = [
            None,
            {"role": "user", "content": "wrong role"},
            {"role": "assistant", "content": None},
        ]
        for message in bad_messages:
            response = _response()
            response["choices"][0]["message"] = message
            with self.subTest(message=message):
                with self.assertRaises(ConnectorError) as caught:
                    parse_chat_completion(
                        response,
                        connection_id="model-main",
                        configured_model="model-a",
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_request_roles_and_parameters_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "role"):
            ChatMessage("tool", "not in initial portable subset")

        with self.assertRaisesRegex(ValueError, "temperature"):
            ChatCompletionRequest(
                messages=(ChatMessage("user", "hi"),),
                temperature=float("nan"),
            )

        with self.assertRaisesRegex(ValueError, "max_tokens"):
            ChatCompletionRequest(
                messages=(ChatMessage("user", "hi"),),
                max_tokens=0,
            )

        with self.assertRaisesRegex(ValueError, "messages"):
            ChatCompletionRequest(messages=())

    def test_multiple_choices_are_counted_but_choice_zero_is_canonical(self):
        response = _response()
        response["choices"].append(
            {
                "index": 1,
                "message": {"role": "assistant", "content": "alternate"},
                "finish_reason": "stop",
            }
        )
        result = parse_chat_completion(
            response,
            connection_id="model-main",
            configured_model="model-a",
        )
        self.assertEqual(result.text, "Result text")
        self.assertEqual(result.choice_count, 2)


if __name__ == "__main__":
    unittest.main()
