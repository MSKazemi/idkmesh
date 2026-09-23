"""Narrow text-chat inference normalization for C3-C (#576).

This module uses the OpenAI-compatible HTTP client but keeps the canonical
result deliberately smaller than raw provider JSON. It retains answer text,
finish metadata, model identity, response identity, and token counts when
available. Provider-specific hidden reasoning fields, raw payloads, and headers
are not retained.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible_http import OpenAICompatibleClient


_ALLOWED_ROLES = {"system", "user", "assistant"}


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _nonnegative_int_or_none(value: Any, field: str, connection_id: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed usage metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in _ALLOWED_ROLES:
            raise ValueError("role must be system, user, or assistant")
        object.__setattr__(self, "content", _nonempty(self.content, "content"))


@dataclass(frozen=True)
class ChatCompletionRequest:
    messages: tuple[ChatMessage, ...]
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.messages, list):
            object.__setattr__(self, "messages", tuple(self.messages))
        if not isinstance(self.messages, tuple) or not self.messages:
            raise ValueError("messages must be a non-empty tuple of ChatMessage")
        if any(not isinstance(item, ChatMessage) for item in self.messages):
            raise ValueError("messages must contain only ChatMessage values")

        if self.temperature is not None:
            if (
                isinstance(self.temperature, bool)
                or not isinstance(self.temperature, (int, float))
                or not math.isfinite(float(self.temperature))
                or not 0 <= float(self.temperature) <= 2
            ):
                raise ValueError("temperature must be a finite number from 0 to 2")
            object.__setattr__(self, "temperature", float(self.temperature))

        if self.max_tokens is not None and (
            isinstance(self.max_tokens, bool)
            or not isinstance(self.max_tokens, int)
            or self.max_tokens < 1
        ):
            raise ValueError("max_tokens must be an integer >= 1 or None")

    def to_payload(self, *, model: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in self.messages
            ],
            "stream": False,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        return payload


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ChatCompletionResult:
    connection_id: str
    response_id: str | None
    model: str
    text: str
    finish_reason: str | None
    usage: ChatUsage
    choice_count: int


def _optional_string(
    value: Any,
    *,
    field: str,
    connection_id: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed completion metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _normalize_usage(raw: Any, *, connection_id: str) -> ChatUsage:
    if raw is None:
        return ChatUsage(None, None, None)
    if not isinstance(raw, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed usage metadata.",
            connection_id=connection_id,
        )

    prompt = _nonnegative_int_or_none(
        raw.get("prompt_tokens"),
        "usage.prompt_tokens",
        connection_id,
    )
    completion = _nonnegative_int_or_none(
        raw.get("completion_tokens"),
        "usage.completion_tokens",
        connection_id,
    )
    total = _nonnegative_int_or_none(
        raw.get("total_tokens"),
        "usage.total_tokens",
        connection_id,
    )
    if (
        total is not None
        and prompt is not None
        and completion is not None
        and total < prompt + completion
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned inconsistent usage metadata.",
            connection_id=connection_id,
        )
    return ChatUsage(prompt, completion, total)


def parse_chat_completion(
    raw: Mapping[str, Any],
    *,
    connection_id: str,
    configured_model: str,
) -> ChatCompletionResult:
    """Normalize one non-streaming text chat completion."""

    if not isinstance(raw, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed completion metadata.",
            connection_id=connection_id,
        )

    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned no chat completion choices.",
            connection_id=connection_id,
        )

    indexed: dict[int, Mapping[str, Any]] = {}
    for position, choice in enumerate(choices):
        if not isinstance(choice, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned malformed chat completion choice.",
                connection_id=connection_id,
                details={"choice_position": position},
            )
        index = choice.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned a choice with invalid index.",
                connection_id=connection_id,
                details={"choice_position": position},
            )
        if index in indexed:
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned duplicate choice indices.",
                connection_id=connection_id,
                details={"choice_index": index},
            )
        indexed[index] = choice

    if 0 not in indexed:
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint did not return choice index 0.",
            connection_id=connection_id,
        )

    selected = indexed[0]
    message = selected.get("message")
    if not isinstance(message, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed assistant message metadata.",
            connection_id=connection_id,
        )
    role = message.get("role")
    if role != "assistant":
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned a non-assistant completion message.",
            connection_id=connection_id,
            details={"role": role if isinstance(role, str) else "invalid"},
        )

    text = message.get("content")
    if not isinstance(text, str):
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint did not return text completion content.",
            connection_id=connection_id,
        )

    observed_model = raw.get("model")
    if observed_model is None:
        model = configured_model
    elif isinstance(observed_model, str) and observed_model.strip():
        model = observed_model
    else:
        raise ConnectorError(
            code="result_normalization_error",
            message="Model endpoint returned malformed model identity.",
            connection_id=connection_id,
        )

    return ChatCompletionResult(
        connection_id=connection_id,
        response_id=_optional_string(
            raw.get("id"),
            field="id",
            connection_id=connection_id,
        ),
        model=model,
        text=text,
        finish_reason=_optional_string(
            selected.get("finish_reason"),
            field="choices[0].finish_reason",
            connection_id=connection_id,
        ),
        usage=_normalize_usage(
            raw.get("usage"),
            connection_id=connection_id,
        ),
        choice_count=len(choices),
    )


class OpenAICompatibleChatService:
    """Execute one narrow non-streaming text completion."""

    def __init__(self, client: OpenAICompatibleClient) -> None:
        self._client = client

    def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        raw = self._client.request_json(
            "POST",
            "/chat/completions",
            body=request.to_payload(model=self._client.config.model),
        )
        return parse_chat_completion(
            raw,
            connection_id=self._client.config.connection_id,
            configured_model=self._client.config.model,
        )
