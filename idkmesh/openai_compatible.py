"""Provider-neutral OpenAI-compatible model connection contract.

This C3-A slice validates static provider settings only. It performs no secret
resolution and no network I/O.

The contract is intentionally small enough to cover compatible Gemini, Ollama,
vLLM, OpenRouter, LiteLLM-style gateways, and similar endpoints without adding
provider names to coordinator logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


def _nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalized_base_url(value: object) -> str:
    base_url = _nonempty(value, "base_url").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain query or fragment components")
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("plain HTTP is allowed only for loopback model endpoints")
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )


def _positive_finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field_name} must be a positive finite number")
    return number


def _nonnegative_finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number >= 0")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be a finite number >= 0")
    return number


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be an integer >= 1")
    return value


def _string_set(
    values: Iterable[str] | frozenset[str],
    field_name: str,
) -> frozenset[str]:
    if isinstance(values, str):
        raise ValueError(
            f"{field_name} must be a collection of strings, not a string"
        )
    try:
        items = frozenset(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a collection of strings") from exc
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    return frozenset(item.strip() for item in items)


@dataclass(frozen=True)
class OpenAICompatibleModelConfig:
    """Static configuration for one OpenAI-compatible model endpoint.

    secret_ref is metadata only. The caller must resolve it outside this
    object and supply runtime credential material to the HTTP client in a later
    slice.
    """

    connection_id: str
    base_url: str
    model: str
    allowed_models: frozenset[str] = field(default_factory=frozenset)
    secret_ref: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 2 * 1024 * 1024
    external_processing: bool = True
    project_spend_usd_max: float = 0.0

    def __post_init__(self) -> None:
        connection_id = _nonempty(self.connection_id, "connection_id")
        base_url = _normalized_base_url(self.base_url)
        model = _nonempty(self.model, "model")
        allowed_models = _string_set(self.allowed_models, "allowed_models")
        if not allowed_models:
            allowed_models = frozenset({model})
        if model not in allowed_models:
            raise ValueError("model must be present in allowed_models")

        secret_ref = self.secret_ref
        if secret_ref is not None:
            secret_ref = _nonempty(secret_ref, "secret_ref")
            if any(character.isspace() for character in secret_ref):
                raise ValueError("secret_ref must not contain whitespace")

        if type(self.external_processing) is not bool:
            raise ValueError("external_processing must be a boolean")

        object.__setattr__(self, "connection_id", connection_id)
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "allowed_models", allowed_models)
        object.__setattr__(self, "secret_ref", secret_ref)
        object.__setattr__(
            self,
            "timeout_seconds",
            _positive_finite(self.timeout_seconds, "timeout_seconds"),
        )
        object.__setattr__(
            self,
            "max_response_bytes",
            _positive_int(self.max_response_bytes, "max_response_bytes"),
        )
        object.__setattr__(
            self,
            "project_spend_usd_max",
            _nonnegative_finite(
                self.project_spend_usd_max,
                "project_spend_usd_max",
            ),
        )

    @property
    def auth_required(self) -> bool:
        return self.secret_ref is not None

    def endpoint(self, path: str) -> str:
        """Build a relative API URL without allowing host/query overrides."""

        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if "://" in path or "?" in path or "#" in path:
            raise ValueError("path must be relative and contain no query or fragment")
        return self.base_url + path

    def with_model(self, model: str) -> "OpenAICompatibleModelConfig":
        """Return a copy selecting another already allowlisted model."""

        selected = _nonempty(model, "model")
        if selected not in self.allowed_models:
            raise ValueError("requested model is not allowlisted")
        return OpenAICompatibleModelConfig(
            connection_id=self.connection_id,
            base_url=self.base_url,
            model=selected,
            allowed_models=self.allowed_models,
            secret_ref=self.secret_ref,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
            external_processing=self.external_processing,
            project_spend_usd_max=self.project_spend_usd_max,
        )
