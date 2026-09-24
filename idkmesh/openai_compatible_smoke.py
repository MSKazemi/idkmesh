"""Secret-safe smoke evidence for OpenAI-compatible model endpoints.

The smoke path exercises both model discovery and one non-streaming text
completion while retaining only bounded metadata and a SHA-256 digest of the
returned text. It never includes an API key, prompt text, raw provider payload,
or raw completion text in the evidence record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_http import (
    OpenAICompatibleClient,
    OpenAICompatibleTransport,
)
from idkmesh.openai_compatible_inference import (
    ChatCompletionRequest,
    ChatMessage,
    OpenAICompatibleChatService,
)


SMOKE_SCHEMA = "idkmesh.openai_compatible_smoke/v1"


@dataclass(frozen=True)
class OpenAICompatibleSmokeEvidence:
    schema: str
    checked_at: str
    connection_id: str
    base_url: str
    configured_model: str
    observed_model: str
    probe_status: str
    model_available: bool
    finish_reason: str | None
    response_sha256: str
    response_chars: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "checked_at": self.checked_at,
            "connection_id": self.connection_id,
            "base_url": self.base_url,
            "configured_model": self.configured_model,
            "observed_model": self.observed_model,
            "probe_status": self.probe_status,
            "model_available": self.model_available,
            "finish_reason": self.finish_reason,
            "response_sha256": self.response_sha256,
            "response_chars": self.response_chars,
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_openai_compatible_smoke(
    config: OpenAICompatibleModelConfig,
    *,
    api_key: str | None = None,
    prompt: str = "Return a short plain-text acknowledgement.",
    checked_at: str | None = None,
    transport: OpenAICompatibleTransport | None = None,
) -> OpenAICompatibleSmokeEvidence:
    """Run one bounded probe + chat completion and return safe evidence."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if checked_at is not None and (
        not isinstance(checked_at, str) or not checked_at.strip()
    ):
        raise ValueError("checked_at must be a non-empty string or None")

    client = OpenAICompatibleClient(
        config,
        api_key=api_key,
        transport=transport,
    )
    probe = client.probe()
    if not probe.model_available:
        raise ConnectorError(
            code="configuration_error",
            message="Configured model was not observed during compatibility smoke.",
            connection_id=config.connection_id,
            details={"model_id": config.model},
        )

    result = OpenAICompatibleChatService(client).complete(
        ChatCompletionRequest(
            messages=(ChatMessage("user", prompt),),
            temperature=0,
            max_tokens=64,
        )
    )
    if not result.text:
        raise ConnectorError(
            code="result_normalization_error",
            message="Compatibility smoke returned empty completion text.",
            connection_id=config.connection_id,
        )

    return OpenAICompatibleSmokeEvidence(
        schema=SMOKE_SCHEMA,
        checked_at=checked_at or _utc_now(),
        connection_id=config.connection_id,
        base_url=config.base_url,
        configured_model=config.model,
        observed_model=result.model,
        probe_status=probe.status,
        model_available=probe.model_available,
        finish_reason=result.finish_reason,
        response_sha256=hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
        response_chars=len(result.text),
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
    )
