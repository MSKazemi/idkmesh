"""Exactly-once explicit GitHub dispatch boundary for C5-G.

This service is called only after:
- authenticated webhook normalization;
- durable delivery-run reservation;
- WorkUnit preview;
- canonical routing;
- explicit actor/role authorization.

It reserves a separate dispatch identity *before* external work. Exact replay
returns the retained provider reference without calling the dispatcher again.
A retained incomplete/error reservation fails closed for recovery rather than
risking duplicate provider work.

The injected dispatcher is the provider-neutral connector boundary. This module
contains no provider-name branches and grants no verification, acceptance,
push, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    RunRecord,
)
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorization,
)
from idkmesh.work_unit_binding import canonical_digest


_SCHEMA_VERSION = "0.1"
_ADMISSION_KIND = "github-explicit-dispatch-admission"
_RESULT_KIND = "github-explicit-dispatch-result"
_ERROR_KIND = "github-explicit-dispatch-error"
_PARENT_KIND = "github-webhook-delivery-admission"

_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_GIT_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")


class GitHubDispatchConflict(RuntimeError):
    pass


class GitHubDispatchRecoveryRequired(RuntimeError):
    pass


class GitHubDispatchExecutionError(RuntimeError):
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


@dataclass(frozen=True, slots=True)
class GitHubExplicitDispatchRequest:
    project_id: str
    delivery_run_id: str
    delivery_id: str
    delivery_request_digest: str
    issue_number: int
    work_unit_id: str
    work_unit_version: int
    work_unit_digest: str
    source_revision: str
    routing_digest: str
    routing_policy_version: str
    selected_connection_id: str
    policy_revision: str

    def __post_init__(self) -> None:
        for field in (
            "project_id",
            "delivery_run_id",
            "delivery_id",
            "work_unit_id",
            "routing_policy_version",
            "selected_connection_id",
            "policy_revision",
        ):
            _text(getattr(self, field), field)
        for field in (
            "delivery_request_digest",
            "work_unit_digest",
            "routing_digest",
        ):
            _digest(getattr(self, field), field)
        if (
            isinstance(self.issue_number, bool)
            or not isinstance(self.issue_number, int)
            or self.issue_number < 1
        ):
            raise ValueError("issue_number must be an integer >= 1")
        if (
            isinstance(self.work_unit_version, bool)
            or not isinstance(self.work_unit_version, int)
            or self.work_unit_version < 1
        ):
            raise ValueError(
                "work_unit_version must be an integer >= 1"
            )
        if (
            not isinstance(self.source_revision, str)
            or _GIT_SHA_RE.fullmatch(self.source_revision) is None
        ):
            raise ValueError(
                "source_revision must be an exact 40/64-character Git object id"
            )
        object.__setattr__(
            self,
            "source_revision",
            self.source_revision.lower(),
        )

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "project_id": self.project_id,
            "delivery_run_id": self.delivery_run_id,
            "delivery_id": self.delivery_id,
            "delivery_request_digest": self.delivery_request_digest,
            "issue_number": self.issue_number,
            "work_unit": {
                "id": self.work_unit_id,
                "version": self.work_unit_version,
                "digest": self.work_unit_digest,
                "source_revision": self.source_revision,
            },
            "routing": {
                "digest": self.routing_digest,
                "policy_version": self.routing_policy_version,
                "selected_connection_id": self.selected_connection_id,
            },
            "policy_revision": self.policy_revision,
        }


@dataclass(frozen=True, slots=True)
class GitHubExplicitDispatchResult:
    dispatch_run_id: str
    request_digest: str
    provider_reference: str
    selected_connection_id: str
    created: bool
    replayed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_run_id": self.dispatch_run_id,
            "request_digest": self.request_digest,
            "provider_reference": self.provider_reference,
            "selected_connection_id": self.selected_connection_id,
            "created": self.created,
            "replayed": self.replayed,
            "candidate_accepted": False,
            "merge_authority": False,
        }


def github_dispatch_request_digest(
    request: GitHubExplicitDispatchRequest,
    authorization: GitHubDispatchAuthorization,
) -> str:
    if not isinstance(request, GitHubExplicitDispatchRequest):
        raise TypeError(
            "request must be GitHubExplicitDispatchRequest"
        )
    if not isinstance(
        authorization,
        GitHubDispatchAuthorization,
    ):
        raise TypeError(
            "authorization must be GitHubDispatchAuthorization"
        )
    return canonical_digest(
        {
            "schema_version": _SCHEMA_VERSION,
            "kind": _ADMISSION_KIND,
            "request": request.semantic_payload(),
            "authorization": {
                "delivery_id": authorization.delivery_id,
                "repository": authorization.repository,
                "issue_number": authorization.issue_number,
                "actor_id": authorization.actor_id,
                "actor_login": authorization.actor_login,
                "actor_role": authorization.actor_role,
                "label_name": authorization.label_name,
                "installation_id": authorization.installation_id,
            },
        }
    )


def _dispatch_idempotency_key(
    request: GitHubExplicitDispatchRequest,
) -> str:
    return "github-dispatch:" + request.delivery_run_id


def _dispatch_run_id(
    idempotency_key: str,
    request_digest: str,
) -> str:
    digest = canonical_digest(
        {
            "idempotency_key": idempotency_key,
            "request_digest": request_digest,
        }
    )
    return "github-dispatch/" + digest[7:31]


def _parent_delivery_record(
    store: LocalMetadataStore,
    request: GitHubExplicitDispatchRequest,
    authorization: GitHubDispatchAuthorization,
) -> RunRecord:
    record = store.get_run(request.delivery_run_id)
    if record is None:
        raise GitHubDispatchConflict(
            "delivery run does not exist"
        )
    metadata = record.metadata
    if (
        metadata.get("schema_version") != _SCHEMA_VERSION
        or metadata.get("kind") != _PARENT_KIND
    ):
        raise GitHubDispatchConflict(
            "delivery run is not a GitHub webhook admission"
        )
    if record.request_digest != request.delivery_request_digest:
        raise GitHubDispatchConflict(
            "delivery request digest does not match retained run"
        )
    checks = {
        "delivery_id": request.delivery_id,
        "issue_number": request.issue_number,
        "sender_id": authorization.actor_id,
    }
    for key, expected in checks.items():
        if metadata.get(key) != expected:
            raise GitHubDispatchConflict(
                f"delivery run {key} does not match dispatch request"
            )
    retained_repository = metadata.get("repository")
    if (
        not isinstance(retained_repository, str)
        or retained_repository.casefold()
        != authorization.repository.casefold()
    ):
        raise GitHubDispatchConflict(
            "delivery repository does not match authorization"
        )
    return record


def _restore_dispatch_result(
    record: RunRecord,
    *,
    selected_connection_id: str,
) -> GitHubExplicitDispatchResult:
    metadata = record.metadata
    if (
        record.state == "dispatched"
        and metadata.get("schema_version") == _SCHEMA_VERSION
        and metadata.get("kind") == _RESULT_KIND
    ):
        provider_reference = metadata.get("provider_reference")
        connector_id = metadata.get("selected_connection_id")
        if (
            not isinstance(provider_reference, str)
            or not provider_reference
            or connector_id != selected_connection_id
        ):
            raise GitHubDispatchRecoveryRequired(
                "retained dispatch result is malformed"
            )
        return GitHubExplicitDispatchResult(
            dispatch_run_id=record.run_id,
            request_digest=record.request_digest,
            provider_reference=provider_reference,
            selected_connection_id=selected_connection_id,
            created=False,
            replayed=True,
        )

    raise GitHubDispatchRecoveryRequired(
        "dispatch identity is retained without a complete result; "
        "provider reconciliation is required before retry"
    )


def dispatch_github_run_once(
    *,
    store: LocalMetadataStore,
    authorization: GitHubDispatchAuthorization,
    request: GitHubExplicitDispatchRequest,
    dispatcher: Callable[
        [GitHubExplicitDispatchRequest],
        str,
    ],
    created_at: str,
    updated_at: str | None = None,
) -> GitHubExplicitDispatchResult:
    """Invoke the selected connector at most once for one delivery run."""

    if not isinstance(store, LocalMetadataStore):
        raise TypeError("store must be LocalMetadataStore")
    if not isinstance(
        authorization,
        GitHubDispatchAuthorization,
    ):
        raise TypeError(
            "authorization must be GitHubDispatchAuthorization"
        )
    if not authorization.authorized:
        raise GitHubDispatchConflict(
            "dispatch authorization is not satisfied"
        )
    if authorization.delivery_id != request.delivery_id:
        raise GitHubDispatchConflict(
            "authorization delivery does not match request"
        )
    if authorization.issue_number != request.issue_number:
        raise GitHubDispatchConflict(
            "authorization issue does not match request"
        )
    if not callable(dispatcher):
        raise TypeError("dispatcher must be callable")
    _text(created_at, "created_at")
    if updated_at is not None:
        _text(updated_at, "updated_at")

    _parent_delivery_record(
        store,
        request,
        authorization,
    )

    request_digest = github_dispatch_request_digest(
        request,
        authorization,
    )
    idempotency_key = _dispatch_idempotency_key(request)
    dispatch_run_id = _dispatch_run_id(
        idempotency_key,
        request_digest,
    )

    try:
        record, created = store.admit_run(
            run_id=dispatch_run_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            state="admitted",
            metadata={
                "schema_version": _SCHEMA_VERSION,
                "kind": _ADMISSION_KIND,
                "delivery_run_id": request.delivery_run_id,
                "delivery_id": request.delivery_id,
                "work_unit_digest": request.work_unit_digest,
                "routing_digest": request.routing_digest,
                "selected_connection_id": (
                    request.selected_connection_id
                ),
                "actor_id": authorization.actor_id,
                "actor_role": authorization.actor_role,
                "policy_revision": request.policy_revision,
            },
            created_at=created_at,
        )
    except LocalStoreConflict as exc:
        raise GitHubDispatchConflict(
            "dispatch idempotency key conflicts with a different request"
        ) from exc

    if not created:
        return _restore_dispatch_result(
            record,
            selected_connection_id=(
                request.selected_connection_id
            ),
        )

    try:
        provider_reference = dispatcher(request)
        provider_reference = _text(
            provider_reference,
            "provider_reference",
            max_length=1024,
        )
    except Exception as exc:
        store.update_run(
            dispatch_run_id,
            state="dispatch_error",
            metadata={
                "schema_version": _SCHEMA_VERSION,
                "kind": _ERROR_KIND,
                "delivery_run_id": request.delivery_run_id,
                "selected_connection_id": (
                    request.selected_connection_id
                ),
                "error_code": "dispatcher_failed",
            },
            updated_at=updated_at or created_at,
        )
        raise GitHubDispatchExecutionError(
            "selected connector dispatch failed"
        ) from exc

    stored = store.update_run(
        dispatch_run_id,
        state="dispatched",
        metadata={
            "schema_version": _SCHEMA_VERSION,
            "kind": _RESULT_KIND,
            "delivery_run_id": request.delivery_run_id,
            "delivery_id": request.delivery_id,
            "work_unit_digest": request.work_unit_digest,
            "source_revision": request.source_revision,
            "routing_digest": request.routing_digest,
            "selected_connection_id": (
                request.selected_connection_id
            ),
            "provider_reference": provider_reference,
            "actor_id": authorization.actor_id,
            "actor_role": authorization.actor_role,
            "policy_revision": request.policy_revision,
        },
        updated_at=updated_at or created_at,
    )

    return GitHubExplicitDispatchResult(
        dispatch_run_id=stored.run_id,
        request_digest=stored.request_digest,
        provider_reference=provider_reference,
        selected_connection_id=request.selected_connection_id,
        created=True,
        replayed=False,
    )
