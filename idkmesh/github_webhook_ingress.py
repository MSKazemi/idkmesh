"""Authenticated, repository-bound GitHub webhook ingress for C5-A/B.

Webhook payloads are untrusted input even after signature verification. This
module verifies the exact raw bytes with X-Hub-Signature-256, rejects malformed
or duplicate-key JSON, binds the event to one configured repository, and emits
a small normalized envelope.

It performs no routing, secret resolution, run creation, repository mutation, or
merge action.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Mapping

from idkmesh.connector_errors import ConnectorError


DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024
DEFAULT_ALLOWED_EVENTS = frozenset({"issues", "issue_comment", "pull_request"})

_DELIVERY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_EVENT_RE = re.compile(r"[a-z0-9_]{1,64}\Z")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SIGNATURE_RE = re.compile(r"sha256=([0-9a-fA-F]{64})\Z")
_ASSOCIATIONS = frozenset(
    {
        "COLLABORATOR",
        "CONTRIBUTOR",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
        "MEMBER",
        "NONE",
        "OWNER",
    }
)


class _DuplicateJsonKey(ValueError):
    pass


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    found: str | None = None
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("webhook headers must be string pairs")
        if key.casefold() != expected:
            continue
        if found is not None:
            raise ConnectorError(
                code="configuration_error",
                message="GitHub webhook contains a duplicate security header.",
            )
        found = value
    return found


def _nonempty_string(
    value: Any,
    *,
    field: str,
    connection_id: str | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook contains malformed metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _positive_int(
    value: Any,
    *,
    field: str,
    connection_id: str | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook contains malformed metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def verify_github_webhook_signature(
    body: bytes,
    signature_header: str | None,
    *,
    secret: str | bytes,
    connection_id: str | None = None,
) -> None:
    """Verify GitHub X-Hub-Signature-256 without exposing secret material."""

    if not isinstance(body, bytes):
        raise ValueError("webhook body must be bytes")
    if isinstance(secret, str):
        secret_bytes = secret.encode("utf-8")
    elif isinstance(secret, bytes):
        secret_bytes = secret
    else:
        raise ValueError("webhook secret must be str or bytes")
    if not secret_bytes:
        raise ValueError("webhook secret must not be empty")

    if not isinstance(signature_header, str):
        raise ConnectorError(
            code="authentication_error",
            message="GitHub webhook signature is missing or invalid.",
            connection_id=connection_id,
        )
    matched = _SIGNATURE_RE.fullmatch(signature_header.strip())
    if matched is None:
        raise ConnectorError(
            code="authentication_error",
            message="GitHub webhook signature is missing or invalid.",
            connection_id=connection_id,
        )

    expected = hmac.new(secret_bytes, body, hashlib.sha256).hexdigest()
    observed = matched.group(1).lower()
    if not hmac.compare_digest(expected, observed):
        raise ConnectorError(
            code="authentication_error",
            message="GitHub webhook signature is missing or invalid.",
            connection_id=connection_id,
        )


@dataclass(frozen=True)
class GitHubWebhookEnvelope:
    delivery_id: str
    event: str
    action: str
    repository: str
    repository_id: int
    sender_login: str
    sender_id: int
    sender_type: str
    author_association: str | None
    subject_number: int | None
    label_name: str | None
    payload_digest: str

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "delivery_id": self.delivery_id,
            "event": self.event,
            "action": self.action,
            "repository": self.repository,
            "repository_id": self.repository_id,
            "sender": {
                "login": self.sender_login,
                "id": self.sender_id,
                "type": self.sender_type,
            },
            "payload_digest": self.payload_digest,
        }
        if self.author_association is not None:
            result["author_association"] = self.author_association
        if self.subject_number is not None:
            result["subject_number"] = self.subject_number
        if self.label_name is not None:
            result["label_name"] = self.label_name
        return result


def _normalize_author_association(
    payload: Mapping[str, Any],
    event: str,
    *,
    connection_id: str | None,
) -> str | None:
    if event in {"issues", "issue_comment"}:
        subject = payload.get("comment") if event == "issue_comment" else payload.get("issue")
    else:
        subject = payload.get("pull_request")

    if not isinstance(subject, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook is missing event subject metadata.",
            connection_id=connection_id,
        )
    raw = subject.get("author_association")
    if raw is None:
        return None
    association = _nonempty_string(
        raw,
        field=f"{event}.author_association",
        connection_id=connection_id,
    ).upper()
    if association not in _ASSOCIATIONS:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook contains an unknown author association.",
            connection_id=connection_id,
            details={"association": association},
        )
    return association


def _subject_number(
    payload: Mapping[str, Any],
    event: str,
    *,
    connection_id: str | None,
) -> int | None:
    if event in {"issues", "issue_comment"}:
        issue = payload.get("issue")
        if not isinstance(issue, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook is missing issue metadata.",
                connection_id=connection_id,
            )
        return _positive_int(
            issue.get("number"),
            field="issue.number",
            connection_id=connection_id,
        )
    if event == "pull_request":
        pull_request = payload.get("pull_request")
        if not isinstance(pull_request, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub webhook is missing pull-request metadata.",
                connection_id=connection_id,
            )
        number = pull_request.get("number", payload.get("number"))
        return _positive_int(
            number,
            field="pull_request.number",
            connection_id=connection_id,
        )
    return None


def parse_github_webhook(
    headers: Mapping[str, str],
    body: bytes,
    *,
    secret: str | bytes,
    expected_repository: str,
    allowed_events: frozenset[str] = DEFAULT_ALLOWED_EVENTS,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    connection_id: str | None = None,
) -> GitHubWebhookEnvelope:
    """Verify and normalize one GitHub webhook request."""

    if not isinstance(headers, Mapping):
        raise ValueError("headers must be a mapping")
    if not isinstance(body, bytes):
        raise ValueError("webhook body must be bytes")
    if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes < 1:
        raise ValueError("max_body_bytes must be an integer >= 1")
    if len(body) > max_body_bytes:
        raise ConnectorError(
            code="policy_denied",
            message="GitHub webhook body exceeds configured size limit.",
            connection_id=connection_id,
            details={"max_body_bytes": max_body_bytes},
        )
    if (
        not isinstance(expected_repository, str)
        or _REPOSITORY_RE.fullmatch(expected_repository) is None
    ):
        raise ValueError("expected_repository must be in owner/name form")
    if isinstance(allowed_events, str) or not isinstance(allowed_events, frozenset):
        raise ValueError("allowed_events must be a frozenset of event names")
    if any(
        not isinstance(event, str) or _EVENT_RE.fullmatch(event) is None
        for event in allowed_events
    ):
        raise ValueError("allowed_events contains an invalid event name")

    signature = _header(headers, "X-Hub-Signature-256")
    verify_github_webhook_signature(
        body,
        signature,
        secret=secret,
        connection_id=connection_id,
    )

    content_type = _header(headers, "Content-Type")
    if content_type is not None:
        media_type = content_type.split(";", 1)[0].strip().casefold()
        if media_type != "application/json":
            raise ConnectorError(
                code="configuration_error",
                message="GitHub webhook Content-Type must be application/json.",
                connection_id=connection_id,
            )

    delivery_id = _header(headers, "X-GitHub-Delivery")
    event = _header(headers, "X-GitHub-Event")
    if not isinstance(delivery_id, str) or _DELIVERY_RE.fullmatch(delivery_id) is None:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook delivery identity is missing or invalid.",
            connection_id=connection_id,
        )
    if not isinstance(event, str) or _EVENT_RE.fullmatch(event) is None:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook event identity is missing or invalid.",
            connection_id=connection_id,
        )
    if event not in allowed_events:
        raise ConnectorError(
            code="policy_denied",
            message="GitHub webhook event type is not enabled.",
            connection_id=connection_id,
            details={"event": event},
        )

    try:
        decoded = body.decode("utf-8")
        payload = json.loads(
            decoded,
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook body is not strict UTF-8 JSON.",
            connection_id=connection_id,
        ) from exc
    if not isinstance(payload, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook body must be a JSON object.",
            connection_id=connection_id,
        )

    action = _nonempty_string(
        payload.get("action"),
        field="action",
        connection_id=connection_id,
    )

    repository = payload.get("repository")
    if not isinstance(repository, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook is missing repository metadata.",
            connection_id=connection_id,
        )
    full_name = _nonempty_string(
        repository.get("full_name"),
        field="repository.full_name",
        connection_id=connection_id,
    )
    if _REPOSITORY_RE.fullmatch(full_name) is None:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook repository identity is malformed.",
            connection_id=connection_id,
        )
    if full_name.casefold() != expected_repository.casefold():
        raise ConnectorError(
            code="policy_denied",
            message="GitHub webhook repository is not configured for this ingress.",
            connection_id=connection_id,
            details={"observed_repository": full_name},
        )
    repository_id = _positive_int(
        repository.get("id"),
        field="repository.id",
        connection_id=connection_id,
    )

    sender = payload.get("sender")
    if not isinstance(sender, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub webhook is missing sender metadata.",
            connection_id=connection_id,
        )
    sender_login = _nonempty_string(
        sender.get("login"),
        field="sender.login",
        connection_id=connection_id,
    )
    sender_id = _positive_int(
        sender.get("id"),
        field="sender.id",
        connection_id=connection_id,
    )
    sender_type = _nonempty_string(
        sender.get("type"),
        field="sender.type",
        connection_id=connection_id,
    )

    label_name = None
    if event == "issues" and action in {"labeled", "unlabeled"}:
        label = payload.get("label")
        if not isinstance(label, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub label event is missing label metadata.",
                connection_id=connection_id,
            )
        label_name = _nonempty_string(
            label.get("name"),
            field="label.name",
            connection_id=connection_id,
        )

    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    return GitHubWebhookEnvelope(
        delivery_id=delivery_id,
        event=event,
        action=action,
        repository=expected_repository,
        repository_id=repository_id,
        sender_login=sender_login,
        sender_id=sender_id,
        sender_type=sender_type,
        author_association=_normalize_author_association(
            payload,
            event,
            connection_id=connection_id,
        ),
        subject_number=_subject_number(
            payload,
            event,
            connection_id=connection_id,
        ),
        label_name=label_name,
        payload_digest=digest,
    )
