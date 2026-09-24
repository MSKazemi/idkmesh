"""Authenticated, bounded GitHub webhook ingress for C5.

This module deliberately stops before WorkUnit preview, routing, authorization,
secret resolution, or dispatch. It turns one raw webhook request into a small
provider-neutral envelope only after the exact raw body passes GitHub's
HMAC-SHA256 signature check.

Issue/comment text is untrusted and is not retained in the normalized envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Iterable, Mapping

from idkmesh.connector_errors import ConnectorError


_DEFAULT_MAX_BODY_BYTES = 1024 * 1024
_MAX_BODY_BYTES_CEILING = 8 * 1024 * 1024

_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_EVENT_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_ACTION_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_DELIVERY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SIGNATURE_RE = re.compile(r"sha256=([0-9a-f]{64})\Z")

_DEFAULT_EVENT_ACTIONS: Mapping[str, frozenset[str]] = {
    "issues": frozenset(
        {
            "opened",
            "edited",
            "labeled",
            "unlabeled",
            "reopened",
            "closed",
        }
    ),
}


class _DuplicateJsonKey(ValueError):
    pass


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be an integer >= 1")
    return value


def _safe_text(
    value: Any,
    field: str,
    *,
    max_length: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not allow_empty and not value:
        raise ValueError(f"{field} must be non-empty")
    if len(value) > max_length:
        raise ValueError(f"{field} exceeds the maximum length")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _normalize_header_map(headers: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        raise ValueError("headers must be a mapping")
    normalized: dict[str, str] = {}
    for raw_name, raw_value in headers.items():
        if not isinstance(raw_name, str) or not raw_name:
            raise ValueError("header names must be non-empty strings")
        name = raw_name.casefold()
        if name in normalized:
            raise ValueError(
                f"ambiguous duplicate header after case normalization: {raw_name}"
            )
        value = _safe_text(
            raw_value,
            f"header {raw_name}",
            max_length=1024,
        )
        normalized[name] = value
    return normalized


def _secret_bytes(secret: str | bytes) -> bytes:
    if isinstance(secret, str):
        encoded = secret.encode("utf-8")
    elif isinstance(secret, bytes):
        encoded = bytes(secret)
    else:
        raise ValueError("webhook_secret must be str or bytes")
    if len(encoded) < 16:
        raise ValueError("webhook_secret must contain at least 16 bytes")
    return encoded


def _event_actions(
    configured: Mapping[str, Iterable[str]] | None,
) -> dict[str, frozenset[str]]:
    source = _DEFAULT_EVENT_ACTIONS if configured is None else configured
    if not isinstance(source, Mapping) or not source:
        raise ValueError("allowed_event_actions must be a non-empty mapping")

    result: dict[str, frozenset[str]] = {}
    for event, actions in source.items():
        if not isinstance(event, str) or _EVENT_RE.fullmatch(event) is None:
            raise ValueError("allowed event names must be canonical lowercase names")
        if isinstance(actions, (str, bytes)):
            raise ValueError("allowed actions must be an iterable of strings")
        normalized_actions: set[str] = set()
        try:
            iterator = iter(actions)
        except TypeError as exc:
            raise ValueError("allowed actions must be iterable") from exc
        for action in iterator:
            if not isinstance(action, str) or _ACTION_RE.fullmatch(action) is None:
                raise ValueError(
                    "allowed action names must be canonical lowercase names"
                )
            normalized_actions.add(action)
        if not normalized_actions:
            raise ValueError("each allowed event must have at least one action")
        result[event] = frozenset(normalized_actions)
    return result


@dataclass(frozen=True)
class GitHubWebhookEnvelope:
    """Minimal authenticated event identity; never a dispatch authorization."""

    delivery_id: str
    event: str
    action: str
    repository: str
    repository_id: int
    sender_login: str
    sender_id: int
    issue_number: int | None
    label_name: str | None
    installation_id: int | None
    payload_digest: str
    payload_bytes: int
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise ValueError("unsupported webhook envelope schema_version")
        if _DELIVERY_RE.fullmatch(self.delivery_id) is None:
            raise ValueError("delivery_id is not canonical")
        if _EVENT_RE.fullmatch(self.event) is None:
            raise ValueError("event is not canonical")
        if _ACTION_RE.fullmatch(self.action) is None:
            raise ValueError("action is not canonical")
        if _REPOSITORY_RE.fullmatch(self.repository) is None:
            raise ValueError("repository must be owner/name")
        _positive_int(self.repository_id, "repository_id")
        _safe_text(self.sender_login, "sender_login", max_length=128)
        _positive_int(self.sender_id, "sender_id")
        if self.issue_number is not None:
            _positive_int(self.issue_number, "issue_number")
        if self.label_name is not None:
            _safe_text(self.label_name, "label_name", max_length=100)
        if self.installation_id is not None:
            _positive_int(self.installation_id, "installation_id")
        if (
            not isinstance(self.payload_digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", self.payload_digest) is None
        ):
            raise ValueError("payload_digest must be a lowercase sha256 digest")
        if (
            isinstance(self.payload_bytes, bool)
            or not isinstance(self.payload_bytes, int)
            or self.payload_bytes < 0
        ):
            raise ValueError("payload_bytes must be an integer >= 0")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "delivery_id": self.delivery_id,
            "event": self.event,
            "action": self.action,
            "repository": self.repository,
            "repository_id": self.repository_id,
            "sender_login": self.sender_login,
            "sender_id": self.sender_id,
            "payload_digest": self.payload_digest,
            "payload_bytes": self.payload_bytes,
        }
        if self.issue_number is not None:
            result["issue_number"] = self.issue_number
        if self.label_name is not None:
            result["label_name"] = self.label_name
        if self.installation_id is not None:
            result["installation_id"] = self.installation_id
        return result


class GitHubWebhookReceiver:
    """Authenticate and normalize one bounded GitHub webhook request."""

    def __init__(
        self,
        *,
        expected_repository: str,
        webhook_secret: str | bytes,
        allowed_event_actions: Mapping[str, Iterable[str]] | None = None,
        connection_id: str = "github-webhook",
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
    ) -> None:
        if (
            not isinstance(expected_repository, str)
            or _REPOSITORY_RE.fullmatch(expected_repository) is None
        ):
            raise ValueError("expected_repository must be in owner/name form")
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        if (
            isinstance(max_body_bytes, bool)
            or not isinstance(max_body_bytes, int)
            or not 1 <= max_body_bytes <= _MAX_BODY_BYTES_CEILING
        ):
            raise ValueError(
                "max_body_bytes must be an integer from 1 to "
                f"{_MAX_BODY_BYTES_CEILING}"
            )

        self._expected_repository = expected_repository
        self._secret = _secret_bytes(webhook_secret)
        self._allowed_event_actions = _event_actions(allowed_event_actions)
        self._connection_id = connection_id
        self._max_body_bytes = max_body_bytes

    def receive(
        self,
        *,
        body: bytes,
        headers: Mapping[str, Any],
    ) -> GitHubWebhookEnvelope:
        """Verify the exact raw body before parsing or trusting any event field."""

        if not isinstance(body, bytes):
            raise ValueError("body must be exact raw bytes")
        if len(body) > self._max_body_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook body exceeds the configured size limit.",
                connection_id=self._connection_id,
                details={"max_body_bytes": self._max_body_bytes},
            )

        try:
            normalized_headers = _normalize_header_map(headers)
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook headers are malformed or ambiguous.",
                connection_id=self._connection_id,
            ) from exc

        signature = normalized_headers.get("x-hub-signature-256")
        delivery = normalized_headers.get("x-github-delivery")
        event = normalized_headers.get("x-github-event")
        if signature is None or delivery is None or event is None:
            raise ConnectorError(
                code="authentication_error",
                message="GitHub webhook authentication headers are incomplete.",
                connection_id=self._connection_id,
            )

        match = _SIGNATURE_RE.fullmatch(signature)
        if match is None:
            raise ConnectorError(
                code="authentication_error",
                message="GitHub webhook signature header is not canonical SHA-256.",
                connection_id=self._connection_id,
            )

        expected_signature = hmac.new(
            self._secret,
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, match.group(1)):
            raise ConnectorError(
                code="authentication_error",
                message="GitHub webhook signature verification failed.",
                connection_id=self._connection_id,
            )

        if _DELIVERY_RE.fullmatch(delivery) is None:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook delivery identifier is malformed.",
                connection_id=self._connection_id,
            )
        if _EVENT_RE.fullmatch(event) is None:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook event name is malformed.",
                connection_id=self._connection_id,
            )
        allowed_actions = self._allowed_event_actions.get(event)
        if allowed_actions is None:
            raise ConnectorError(
                code="policy_denied",
                message="GitHub webhook event is not allowlisted.",
                connection_id=self._connection_id,
                details={"event": event},
            )

        try:
            payload = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_json_object,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook body is not strict UTF-8 JSON.",
                connection_id=self._connection_id,
            ) from exc
        if not isinstance(payload, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook JSON root must be an object.",
                connection_id=self._connection_id,
            )

        try:
            action = payload["action"]
            if (
                not isinstance(action, str)
                or _ACTION_RE.fullmatch(action) is None
            ):
                raise ValueError("action")
            if action not in allowed_actions:
                raise ConnectorError(
                    code="policy_denied",
                    message="GitHub webhook action is not allowlisted for this event.",
                    connection_id=self._connection_id,
                    details={"event": event, "action": action},
                )

            repository = payload["repository"]
            sender = payload["sender"]
            if not isinstance(repository, Mapping) or not isinstance(sender, Mapping):
                raise ValueError("repository/sender")

            observed_repository = repository["full_name"]
            if (
                not isinstance(observed_repository, str)
                or _REPOSITORY_RE.fullmatch(observed_repository) is None
            ):
                raise ValueError("repository.full_name")
            if (
                observed_repository.casefold()
                != self._expected_repository.casefold()
            ):
                raise ConnectorError(
                    code="conflict",
                    message="GitHub webhook repository does not match the configured project.",
                    connection_id=self._connection_id,
                    details={
                        "expected_repository": self._expected_repository,
                        "observed_repository": observed_repository,
                    },
                )

            repository_id = _positive_int(
                repository["id"],
                "repository.id",
            )
            sender_login = _safe_text(
                sender["login"],
                "sender.login",
                max_length=128,
            )
            sender_id = _positive_int(sender["id"], "sender.id")

            issue_number: int | None = None
            label_name: str | None = None
            if event == "issues":
                issue = payload["issue"]
                if not isinstance(issue, Mapping):
                    raise ValueError("issue")
                issue_number = _positive_int(
                    issue["number"],
                    "issue.number",
                )
                if action in {"labeled", "unlabeled"}:
                    label = payload["label"]
                    if not isinstance(label, Mapping):
                        raise ValueError("label")
                    label_name = _safe_text(
                        label["name"],
                        "label.name",
                        max_length=100,
                    )

            installation_id: int | None = None
            installation = payload.get("installation")
            if installation is not None:
                if not isinstance(installation, Mapping):
                    raise ValueError("installation")
                installation_id = _positive_int(
                    installation["id"],
                    "installation.id",
                )
        except ConnectorError:
            raise
        except (KeyError, ValueError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook payload is missing required normalized identity fields.",
                connection_id=self._connection_id,
            ) from exc

        return GitHubWebhookEnvelope(
            delivery_id=delivery,
            event=event,
            action=action,
            repository=self._expected_repository,
            repository_id=repository_id,
            sender_login=sender_login,
            sender_id=sender_id,
            issue_number=issue_number,
            label_name=label_name,
            installation_id=installation_id,
            payload_digest="sha256:" + hashlib.sha256(body).hexdigest(),
            payload_bytes=len(body),
        )
