"""One idempotent GitHub run/status reference for C5-H.

This module publishes one immutable, concise issue comment per IDKMesh run. It
reserves publication in LocalMetadataStore before GitHub mutation, so an exact
replay returns the retained comment reference without creating another comment.

If a publication reservation exists without a completed result, automatic
replay fails closed for reconciliation. This avoids duplicate public comments
after ambiguous network/process failure.

The public body contains no raw issue text, provider response, logs, credential,
secret value, candidate acceptance, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import socket
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from idkmesh.connector_errors import ConnectorError
from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    RunRecord,
)
from idkmesh.product_spine import RUN_STATES
from idkmesh.work_unit_binding import canonical_digest


_SCHEMA_VERSION = "0.1"
_ADMISSION_KIND = "github-run-status-admission"
_RESULT_KIND = "github-run-status-result"
_ERROR_KIND = "github-run-status-error"

_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ACCEPT = "application/vnd.github+json"

_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_DEFAULT_MAX_RESPONSE_BYTES = 256 * 1024


class GitHubStatusConflict(RuntimeError):
    pass


class GitHubStatusRecoveryRequired(RuntimeError):
    pass


class GitHubStatusPublishError(RuntimeError):
    pass


def _text(value: object, field: str, *, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > max_length:
        raise ValueError(f"{field} exceeds maximum length")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase sha256 digest")
    return value


def _repository(value: object) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("repository must be in owner/name form")
    return value


def _issue_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("issue_number must be an integer >= 1")
    return value


def _comment_body(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("body must be a non-empty string")
    if len(value.encode("utf-8")) > 4096:
        raise ValueError("body exceeds 4096 UTF-8 bytes")
    if any(
        (ord(char) < 32 and char not in {"\\n", "\\t"})
        or ord(char) == 127
        for char in value
    ):
        raise ValueError("body contains unsupported control characters")
    return value


@dataclass(frozen=True, slots=True)
class GitHubRunStatus:
    repository: str
    issue_number: int
    run_id: str
    state: str
    work_unit_id: str
    work_unit_digest: str
    routing_digest: str

    def __post_init__(self) -> None:
        _repository(self.repository)
        _issue_number(self.issue_number)
        for field in ("run_id", "work_unit_id"):
            value = _text(getattr(self, field), field, max_length=192)
            if _ID_RE.fullmatch(value) is None:
                raise ValueError(f"{field} contains unsupported characters")
        if self.state not in RUN_STATES:
            raise ValueError("state must be a Product Spine run state")
        _digest(self.work_unit_digest, "work_unit_digest")
        _digest(self.routing_digest, "routing_digest")

    @property
    def status_digest(self) -> str:
        return canonical_digest(
            {
                "schema_version": _SCHEMA_VERSION,
                "repository": self.repository,
                "issue_number": self.issue_number,
                "run_id": self.run_id,
                "state": self.state,
                "work_unit_id": self.work_unit_id,
                "work_unit_digest": self.work_unit_digest,
                "routing_digest": self.routing_digest,
            }
        )

    @property
    def marker(self) -> str:
        identity = hashlib.sha256(
            self.run_id.encode("utf-8")
        ).hexdigest()[:24]
        return f"<!-- idkmesh-run-status:v0.1:{identity} -->"

    def render_body(self) -> str:
        body = "\n".join(
            (
                self.marker,
                "### IDKMesh run status",
                "",
                f"- Run: `{self.run_id}`",
                f"- State: `{self.state}`",
                f"- WorkUnit: `{self.work_unit_id}`",
                f"- WorkUnit digest: `{self.work_unit_digest}`",
                f"- Routing digest: `{self.routing_digest}`",
                "",
                (
                    "Operational status only. Candidate verification, human "
                    "acceptance, push, and merge authority remain separate."
                ),
            )
        )
        if len(body.encode("utf-8")) > 4096:
            raise ValueError("rendered GitHub status body exceeds 4096 bytes")
        return body


@dataclass(frozen=True, slots=True)
class GitHubIssueComment:
    comment_id: int
    html_url: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.comment_id, bool)
            or not isinstance(self.comment_id, int)
            or self.comment_id < 1
        ):
            raise ValueError("comment_id must be an integer >= 1")
        _text(self.html_url, "html_url", max_length=2048)


class GitHubIssueCommentTransport(Protocol):
    def create_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        body: str,
    ) -> GitHubIssueComment:
        """Create exactly one issue comment."""


@dataclass(frozen=True, slots=True)
class GitHubRunStatusPublication:
    publication_run_id: str
    status_digest: str
    comment_id: int
    comment_url: str
    created: bool
    replayed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_run_id": self.publication_run_id,
            "status_digest": self.status_digest,
            "comment_id": self.comment_id,
            "comment_url": self.comment_url,
            "created": self.created,
            "replayed": self.replayed,
            "github_mutation": "issue_comment",
            "candidate_accepted": False,
            "merge_authority": False,
        }


def _publication_key(status: GitHubRunStatus) -> str:
    return "github-status:" + status.run_id


def _publication_run_id(key: str, digest: str) -> str:
    identity = canonical_digest(
        {
            "idempotency_key": key,
            "request_digest": digest,
        }
    )
    return "github-status/" + identity[7:31]


def _restore(record: RunRecord) -> GitHubRunStatusPublication:
    metadata = record.metadata
    if (
        record.state == "published"
        and metadata.get("schema_version") == _SCHEMA_VERSION
        and metadata.get("kind") == _RESULT_KIND
    ):
        comment_id = metadata.get("comment_id")
        comment_url = metadata.get("comment_url")
        if (
            isinstance(comment_id, bool)
            or not isinstance(comment_id, int)
            or comment_id < 1
            or not isinstance(comment_url, str)
            or not comment_url
        ):
            raise GitHubStatusRecoveryRequired(
                "retained GitHub status result is malformed"
            )
        return GitHubRunStatusPublication(
            publication_run_id=record.run_id,
            status_digest=record.request_digest,
            comment_id=comment_id,
            comment_url=comment_url,
            created=False,
            replayed=True,
        )
    raise GitHubStatusRecoveryRequired(
        "GitHub status publication is reserved but incomplete; "
        "manual/provider reconciliation is required"
    )


def publish_github_run_status_once(
    *,
    store: LocalMetadataStore,
    status: GitHubRunStatus,
    transport: GitHubIssueCommentTransport,
    created_at: str,
    updated_at: str | None = None,
) -> GitHubRunStatusPublication:
    """Publish one immutable status comment per run, exactly once locally."""

    if not isinstance(store, LocalMetadataStore):
        raise TypeError("store must be LocalMetadataStore")
    if not isinstance(status, GitHubRunStatus):
        raise TypeError("status must be GitHubRunStatus")
    if not hasattr(transport, "create_issue_comment"):
        raise TypeError(
            "transport must implement create_issue_comment"
        )
    _text(created_at, "created_at")
    if updated_at is not None:
        _text(updated_at, "updated_at")

    digest = status.status_digest
    key = _publication_key(status)
    publication_run_id = _publication_run_id(key, digest)

    try:
        record, created = store.admit_run(
            run_id=publication_run_id,
            idempotency_key=key,
            request_digest=digest,
            state="publication_reserved",
            metadata={
                "schema_version": _SCHEMA_VERSION,
                "kind": _ADMISSION_KIND,
                "repository": status.repository,
                "issue_number": status.issue_number,
                "source_run_id": status.run_id,
                "state": status.state,
                "work_unit_digest": status.work_unit_digest,
                "routing_digest": status.routing_digest,
            },
            created_at=created_at,
        )
    except LocalStoreConflict as exc:
        raise GitHubStatusConflict(
            "run already has a different GitHub status publication"
        ) from exc

    if not created:
        return _restore(record)

    try:
        comment = transport.create_issue_comment(
            repository=status.repository,
            issue_number=status.issue_number,
            body=status.render_body(),
        )
        if not isinstance(comment, GitHubIssueComment):
            raise TypeError(
                "transport returned invalid GitHubIssueComment"
            )
    except Exception as exc:
        store.update_run(
            publication_run_id,
            state="publication_error",
            metadata={
                "schema_version": _SCHEMA_VERSION,
                "kind": _ERROR_KIND,
                "source_run_id": status.run_id,
                "error_code": "github_comment_publish_failed",
            },
            updated_at=updated_at or created_at,
        )
        raise GitHubStatusPublishError(
            "GitHub run-status publication failed"
        ) from exc

    stored = store.update_run(
        publication_run_id,
        state="published",
        metadata={
            "schema_version": _SCHEMA_VERSION,
            "kind": _RESULT_KIND,
            "source_run_id": status.run_id,
            "repository": status.repository,
            "issue_number": status.issue_number,
            "state": status.state,
            "status_digest": digest,
            "comment_id": comment.comment_id,
            "comment_url": comment.html_url,
        },
        updated_at=updated_at or created_at,
    )

    return GitHubRunStatusPublication(
        publication_run_id=stored.run_id,
        status_digest=stored.request_digest,
        comment_id=comment.comment_id,
        comment_url=comment.html_url,
        created=True,
        replayed=False,
    )


def _token(value: str) -> str:
    value = _text(value, "token", max_length=4096)
    return value


def _timeout(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0 < float(value) <= 120
    ):
        raise ValueError("timeout_seconds must be finite and in (0, 120]")
    return float(value)


class GitHubRestIssueCommentTransport:
    """Bounded fixed-host GitHub REST transport for one issue-comment POST."""

    def __init__(
        self,
        *,
        token: str,
        timeout_seconds: float = 15,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        user_agent: str = "idkmesh/0.1",
        connection_id: str = "github-status",
    ) -> None:
        self._token = _token(token)
        self._timeout = _timeout(timeout_seconds)
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or not 1 <= max_response_bytes <= 1024 * 1024
        ):
            raise ValueError(
                "max_response_bytes must be in [1, 1048576]"
            )
        self._max_response_bytes = max_response_bytes
        if not callable(opener):
            raise ValueError("opener must be callable")
        self._opener = opener
        self._user_agent = _text(
            user_agent,
            "user_agent",
            max_length=256,
        )
        self._connection_id = _text(
            connection_id,
            "connection_id",
            max_length=128,
        )

    def create_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        body: str,
    ) -> GitHubIssueComment:
        repository = _repository(repository)
        issue_number = _issue_number(issue_number)
        body = _comment_body(body)

        owner, name = repository.split("/", 1)
        url = (
            f"{_API_BASE}/repos/{owner}/{name}/issues/"
            f"{issue_number}/comments"
        )
        payload = json.dumps(
            {"body": body},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        request = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Accept": _ACCEPT,
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": self._user_agent,
                "X-GitHub-Api-Version": _API_VERSION,
            },
        )

        try:
            context = self._opener(
                request,
                timeout=self._timeout,
            )
            with context as response:
                response_status = getattr(response, "status", 201)
                raw = response.read(self._max_response_bytes + 1)
        except HTTPError as exc:
            code = int(exc.code)
            if code == 401:
                error_code = "authentication_error"
            elif code == 403:
                error_code = "authorization_error"
            elif code == 404:
                error_code = "not_found"
            elif code == 429:
                error_code = "rate_limited"
            elif 500 <= code <= 599:
                error_code = "provider_unavailable"
            else:
                error_code = "provider_unavailable"
            raise ConnectorError(
                code=error_code,
                message="GitHub rejected the bounded status comment request.",
                connection_id=self._connection_id,
                details={
                    "status": code,
                    "repository": repository,
                    "issue_number": issue_number,
                },
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectorError(
                code="timeout",
                message="GitHub status comment request timed out.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                },
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            code = (
                "timeout"
                if isinstance(reason, (TimeoutError, socket.timeout))
                else "provider_unavailable"
            )
            raise ConnectorError(
                code=code,
                message="GitHub status comment request failed.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                },
            ) from exc
        except ConnectorError:
            raise
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub status comment request failed.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                },
            ) from exc

        if response_status != 201:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub returned an unexpected status comment response.",
                connection_id=self._connection_id,
                details={
                    "status": response_status,
                    "repository": repository,
                    "issue_number": issue_number,
                },
            )
        if len(raw) > self._max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub status comment response exceeds configured bound.",
                connection_id=self._connection_id,
                details={
                    "max_response_bytes": self._max_response_bytes,
                },
            )

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed status comment JSON.",
                connection_id=self._connection_id,
            ) from exc
        if not isinstance(decoded, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned non-object status comment JSON.",
                connection_id=self._connection_id,
            )

        comment_id = decoded.get("id")
        html_url = decoded.get("html_url")
        try:
            comment = GitHubIssueComment(
                comment_id=comment_id,
                html_url=html_url,
            )
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed status comment identity.",
                connection_id=self._connection_id,
            ) from exc
        expected_prefix = (
            f"https://github.com/{repository}/issues/"
            f"{issue_number}#issuecomment-"
        )
        if not comment.html_url.startswith(expected_prefix):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub status comment URL does not match the configured issue.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                },
            )
        return comment
