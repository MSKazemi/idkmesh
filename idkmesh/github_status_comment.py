"""Idempotently maintain one GitHub issue/PR status comment per run.

C14-B is a human-visible projection over canonical run status. It preserves the
older C5-H immutable publication API and adds a separate create-or-update path:
one stable comment identity follows lifecycle changes without comment spam.

The projection grants no candidate selection, verification, human-decision,
repository-write, push, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request

from idkmesh.connector_errors import ConnectorError
from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    RunRecord,
)
from idkmesh.github_status_update import (
    GitHubIssueComment,
    GitHubRestIssueCommentTransport,
    GitHubRunStatus,
    _ACCEPT,
    _API_BASE,
    _API_VERSION,
    _comment_body,
    _issue_number,
    _repository,
)
from idkmesh.work_unit_binding import canonical_digest


_SCHEMA_VERSION = "0.1"
_KIND = "github-run-status-comment"
_MAX_BODY_BYTES = 4096


class GitHubStatusCommentRecoveryRequired(RuntimeError):
    """The projection cannot safely continue without reconciliation."""


class GitHubStatusCommentPublishError(RuntimeError):
    """A create/update request failed without broadening authority."""


class GitHubStatusCommentTransport(Protocol):
    def create_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        body: str,
    ) -> GitHubIssueComment:
        """Create one issue/PR comment."""

    def update_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        comment_id: int,
        body: str,
    ) -> GitHubIssueComment:
        """Update one retained issue/PR comment."""


def _safe_durable_url(repository: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("durable_evidence_url must be a non-empty string")
    if len(value) > 2048:
        raise ValueError("durable_evidence_url exceeds maximum length")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("durable_evidence_url contains control characters")
    allowed = (
        f"https://github.com/{repository}/",
        f"https://raw.githubusercontent.com/{repository}/",
    )
    if not value.startswith(allowed):
        raise ValueError(
            "durable_evidence_url must be an HTTPS URL inside the configured repository"
        )
    return value


def render_github_run_status_comment(
    status: GitHubRunStatus,
    *,
    durable_evidence_url: str | None = None,
) -> str:
    """Render the bounded mutable C14-B status-comment projection."""

    if not isinstance(status, GitHubRunStatus):
        raise TypeError("status must be GitHubRunStatus")
    evidence_url = _safe_durable_url(status.repository, durable_evidence_url)

    lines = [
        status.marker,
        "### IDKMesh run status",
        "",
        f"- Run: `{status.run_id}`",
        f"- State: `{status.state}`",
        f"- WorkUnit: `{status.work_unit_id}`",
        f"- WorkUnit digest: `{status.work_unit_digest}`",
        f"- Routing digest: `{status.routing_digest}`",
    ]
    if evidence_url is None:
        lines.append("- Durable evidence: not yet linked")
    else:
        lines.append(f"- Durable evidence: [open retained evidence]({evidence_url})")
    lines.extend(
        [
            "",
            "Authority remains blocked for automatic candidate selection, "
            "verification acceptance, Git push, and merge.",
            "",
            "_This comment is a presentation projection and may be updated as "
            "the canonical run state changes._",
        ]
    )
    body = "\n".join(lines)
    if len(body.encode("utf-8")) > _MAX_BODY_BYTES:
        raise ValueError("rendered GitHub status comment exceeds 4096 UTF-8 bytes")
    return body


def _identity_digest(status: GitHubRunStatus) -> str:
    return canonical_digest(
        {
            "schema_version": _SCHEMA_VERSION,
            "repository": status.repository,
            "issue_number": status.issue_number,
            "run_id": status.run_id,
        }
    )


def _content_digest(body: str) -> str:
    return canonical_digest({"body": body})


def _record_id(identity_digest: str) -> str:
    return "github-status-comment/" + identity_digest[7:31]


def _idempotency_key(identity_digest: str) -> str:
    return "github-status-comment:" + identity_digest[7:]


def _base_metadata(
    status: GitHubRunStatus,
    *,
    identity_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND,
        "repository": status.repository,
        "issue_number": status.issue_number,
        "source_run_id": status.run_id,
        "identity_digest": identity_digest,
    }


def _validate_record_identity(
    record: RunRecord,
    status: GitHubRunStatus,
    *,
    identity_digest: str,
) -> None:
    metadata = record.metadata
    expected = _base_metadata(status, identity_digest=identity_digest)
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise GitHubStatusCommentRecoveryRequired(
                "retained GitHub status-comment identity is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class GitHubStatusCommentSyncResult:
    publication_run_id: str
    comment_id: int
    comment_url: str
    content_digest: str
    action: str

    def __post_init__(self) -> None:
        if self.action not in {"created", "updated", "replayed"}:
            raise ValueError("action must be created, updated, or replayed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_run_id": self.publication_run_id,
            "comment_id": self.comment_id,
            "comment_url": self.comment_url,
            "content_digest": self.content_digest,
            "action": self.action,
            "github_mutation": (
                "none" if self.action == "replayed" else "issue_comment"
            ),
            "candidate_selected": False,
            "verification_accepted": False,
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        }


def _result_from_record(
    record: RunRecord,
    *,
    content_digest: str,
    action: str,
) -> GitHubStatusCommentSyncResult:
    comment_id = record.metadata.get("comment_id")
    comment_url = record.metadata.get("comment_url")
    if (
        isinstance(comment_id, bool)
        or not isinstance(comment_id, int)
        or comment_id < 1
        or not isinstance(comment_url, str)
        or not comment_url
    ):
        raise GitHubStatusCommentRecoveryRequired(
            "retained GitHub status-comment identity is malformed"
        )
    return GitHubStatusCommentSyncResult(
        publication_run_id=record.run_id,
        comment_id=comment_id,
        comment_url=comment_url,
        content_digest=content_digest,
        action=action,
    )


def _published_metadata(
    status: GitHubRunStatus,
    *,
    identity_digest: str,
    content_digest: str,
    comment: GitHubIssueComment,
) -> dict[str, Any]:
    metadata = _base_metadata(status, identity_digest=identity_digest)
    metadata.update(
        {
            "source_state": status.state,
            "content_digest": content_digest,
            "comment_id": comment.comment_id,
            "comment_url": comment.html_url,
        }
    )
    return metadata


def sync_github_run_status_comment(
    *,
    store: LocalMetadataStore,
    status: GitHubRunStatus,
    transport: GitHubStatusCommentTransport,
    created_at: str,
    updated_at: str | None = None,
    durable_evidence_url: str | None = None,
) -> GitHubStatusCommentSyncResult:
    """Create once, then idempotently update the same GitHub comment."""

    if not isinstance(store, LocalMetadataStore):
        raise TypeError("store must be LocalMetadataStore")
    if not isinstance(status, GitHubRunStatus):
        raise TypeError("status must be GitHubRunStatus")
    if not hasattr(transport, "create_issue_comment") or not hasattr(
        transport, "update_issue_comment"
    ):
        raise TypeError(
            "transport must implement create_issue_comment and update_issue_comment"
        )
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("created_at must be a non-empty string")
    if updated_at is not None and (
        not isinstance(updated_at, str) or not updated_at
    ):
        raise ValueError("updated_at must be a non-empty string when supplied")

    body = render_github_run_status_comment(
        status,
        durable_evidence_url=durable_evidence_url,
    )
    desired_digest = _content_digest(body)
    identity_digest = _identity_digest(status)
    record_id = _record_id(identity_digest)
    metadata = _base_metadata(status, identity_digest=identity_digest)
    metadata["pending_content_digest"] = desired_digest

    try:
        record, created = store.admit_run(
            run_id=record_id,
            idempotency_key=_idempotency_key(identity_digest),
            request_digest=identity_digest,
            state="create_reserved",
            metadata=metadata,
            created_at=created_at,
        )
    except LocalStoreConflict as exc:
        raise GitHubStatusCommentRecoveryRequired(
            "GitHub status-comment identity conflicts with retained state"
        ) from exc

    if created:
        try:
            comment = transport.create_issue_comment(
                repository=status.repository,
                issue_number=status.issue_number,
                body=body,
            )
            if not isinstance(comment, GitHubIssueComment):
                raise TypeError("transport returned invalid GitHubIssueComment")
        except Exception as exc:
            store.update_run(
                record_id,
                state="create_error",
                metadata=metadata,
                updated_at=updated_at or created_at,
                expected_state="create_reserved",
            )
            raise GitHubStatusCommentPublishError(
                "initial GitHub status-comment publication failed; "
                "reconciliation is required before retry"
            ) from exc

        stored = store.update_run(
            record_id,
            state="published",
            metadata=_published_metadata(
                status,
                identity_digest=identity_digest,
                content_digest=desired_digest,
                comment=comment,
            ),
            updated_at=updated_at or created_at,
            expected_state="create_reserved",
        )
        return _result_from_record(
            stored,
            content_digest=desired_digest,
            action="created",
        )

    _validate_record_identity(
        record,
        status,
        identity_digest=identity_digest,
    )

    if record.state in {"create_reserved", "create_error"}:
        raise GitHubStatusCommentRecoveryRequired(
            "initial GitHub status-comment publication is ambiguous; "
            "reconcile the retained marker/comment before continuing"
        )

    if record.state == "published":
        retained_digest = record.metadata.get("content_digest")
        if retained_digest == desired_digest:
            return _result_from_record(
                record,
                content_digest=desired_digest,
                action="replayed",
            )

        comment_id = record.metadata.get("comment_id")
        comment_url = record.metadata.get("comment_url")
        if (
            isinstance(comment_id, bool)
            or not isinstance(comment_id, int)
            or comment_id < 1
            or not isinstance(comment_url, str)
            or not comment_url
        ):
            raise GitHubStatusCommentRecoveryRequired(
                "published GitHub status-comment identity is malformed"
            )
        reservation = _base_metadata(
            status,
            identity_digest=identity_digest,
        )
        reservation.update(
            {
                "comment_id": comment_id,
                "comment_url": comment_url,
                "content_digest": retained_digest,
                "pending_content_digest": desired_digest,
                "pending_source_state": status.state,
            }
        )
        try:
            record = store.update_run(
                record_id,
                state="update_reserved",
                metadata=reservation,
                updated_at=updated_at or created_at,
                expected_state="published",
            )
        except LocalStoreConflict as exc:
            current = store.get_run(record_id)
            if (
                current is not None
                and current.state == "published"
                and current.metadata.get("content_digest") == desired_digest
            ):
                return _result_from_record(
                    current,
                    content_digest=desired_digest,
                    action="replayed",
                )
            raise GitHubStatusCommentRecoveryRequired(
                "GitHub status-comment update raced with another projection"
            ) from exc

    elif record.state == "update_reserved":
        if record.metadata.get("pending_content_digest") != desired_digest:
            raise GitHubStatusCommentRecoveryRequired(
                "a different GitHub status-comment update is already reserved"
            )
    else:
        raise GitHubStatusCommentRecoveryRequired(
            f"unsupported retained GitHub status-comment state {record.state!r}"
        )

    comment_id = record.metadata.get("comment_id")
    if (
        isinstance(comment_id, bool)
        or not isinstance(comment_id, int)
        or comment_id < 1
    ):
        raise GitHubStatusCommentRecoveryRequired(
            "reserved GitHub status-comment update has no valid comment id"
        )

    try:
        comment = transport.update_issue_comment(
            repository=status.repository,
            issue_number=status.issue_number,
            comment_id=comment_id,
            body=body,
        )
        if not isinstance(comment, GitHubIssueComment):
            raise TypeError("transport returned invalid GitHubIssueComment")
        if comment.comment_id != comment_id:
            raise ValueError("updated comment identity changed unexpectedly")
    except Exception as exc:
        # Keep update_reserved. Repeating PATCH for the same body/comment is
        # idempotent even when the previous response was lost.
        raise GitHubStatusCommentPublishError(
            "GitHub status-comment update failed; retry the same desired "
            "projection before advancing to a different one"
        ) from exc

    try:
        stored = store.update_run(
            record_id,
            state="published",
            metadata=_published_metadata(
                status,
                identity_digest=identity_digest,
                content_digest=desired_digest,
                comment=comment,
            ),
            updated_at=updated_at or created_at,
            expected_state="update_reserved",
        )
    except LocalStoreConflict as exc:
        current = store.get_run(record_id)
        if (
            current is not None
            and current.state == "published"
            and current.metadata.get("content_digest") == desired_digest
        ):
            return _result_from_record(
                current,
                content_digest=desired_digest,
                action="replayed",
            )
        raise GitHubStatusCommentRecoveryRequired(
            "GitHub status-comment update completed remotely but local "
            "projection reconciliation is required"
        ) from exc

    return _result_from_record(
        stored,
        content_digest=desired_digest,
        action="updated",
    )


class GitHubRestStatusCommentTransport(GitHubRestIssueCommentTransport):
    """Bounded GitHub REST create/update transport for issue or PR comments."""

    @staticmethod
    def _matches_target_url(
        *,
        repository: str,
        issue_number: int,
        html_url: str,
    ) -> bool:
        prefixes = (
            f"https://github.com/{repository}/issues/{issue_number}#issuecomment-",
            f"https://github.com/{repository}/pull/{issue_number}#issuecomment-",
        )
        return html_url.startswith(prefixes)

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
            context = self._opener(request, timeout=self._timeout)
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
                details={"max_response_bytes": self._max_response_bytes},
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
        try:
            comment = GitHubIssueComment(
                comment_id=decoded.get("id"),
                html_url=decoded.get("html_url"),
            )
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed status comment identity.",
                connection_id=self._connection_id,
            ) from exc
        if not self._matches_target_url(
            repository=repository,
            issue_number=issue_number,
            html_url=comment.html_url,
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub status comment URL does not match the configured issue/PR.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                },
            )
        return comment

    def update_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        comment_id: int,
        body: str,
    ) -> GitHubIssueComment:
        repository = _repository(repository)
        issue_number = _issue_number(issue_number)
        body = _comment_body(body)
        if (
            isinstance(comment_id, bool)
            or not isinstance(comment_id, int)
            or comment_id < 1
        ):
            raise ValueError("comment_id must be an integer >= 1")

        owner, name = repository.split("/", 1)
        url = (
            f"{_API_BASE}/repos/{owner}/{name}/issues/comments/{comment_id}"
        )
        payload = json.dumps(
            {"body": body},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            url,
            data=payload,
            method="PATCH",
            headers={
                "Accept": _ACCEPT,
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": self._user_agent,
                "X-GitHub-Api-Version": _API_VERSION,
            },
        )

        try:
            context = self._opener(request, timeout=self._timeout)
            with context as response:
                response_status = getattr(response, "status", 200)
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
            else:
                error_code = "provider_unavailable"
            raise ConnectorError(
                code=error_code,
                message="GitHub rejected the bounded status comment update.",
                connection_id=self._connection_id,
                details={
                    "status": code,
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
                },
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectorError(
                code="timeout",
                message="GitHub status comment update timed out.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
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
                message="GitHub status comment update failed.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
                },
            ) from exc
        except ConnectorError:
            raise
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub status comment update failed.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
                },
            ) from exc

        if response_status != 200:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub returned an unexpected status comment update response.",
                connection_id=self._connection_id,
                details={
                    "status": response_status,
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
                },
            )
        if len(raw) > self._max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub status comment update response exceeds configured bound.",
                connection_id=self._connection_id,
                details={"max_response_bytes": self._max_response_bytes},
            )

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed status comment update JSON.",
                connection_id=self._connection_id,
            ) from exc
        if not isinstance(decoded, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned non-object status comment update JSON.",
                connection_id=self._connection_id,
            )

        try:
            comment = GitHubIssueComment(
                comment_id=decoded.get("id"),
                html_url=decoded.get("html_url"),
            )
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed updated comment identity.",
                connection_id=self._connection_id,
            ) from exc
        if comment.comment_id != comment_id or not self._matches_target_url(
            repository=repository,
            issue_number=issue_number,
            html_url=comment.html_url,
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub updated comment identity does not match the configured issue.",
                connection_id=self._connection_id,
                details={
                    "repository": repository,
                    "issue_number": issue_number,
                    "comment_id": comment_id,
                },
            )
        return comment
