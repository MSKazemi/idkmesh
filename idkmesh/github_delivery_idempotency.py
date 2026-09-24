"""Restart-safe GitHub delivery admission for C5-C.

This module composes the authenticated GitHubWebhookEnvelope with the existing
LocalMetadataStore run-idempotency primitive. It creates no second webhook
ledger.

One normalized delivery identity reserves one deterministic Product-Spine-style
run record before preview/routing/secret materialization/external work:

    same idempotency key + same normalized request digest
      -> return the existing run

    same idempotency key + different normalized request digest
      -> fail closed

The retained metadata is compact and contains no raw webhook body, signature,
issue title/body, credential, or secret value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    RunRecord,
)
from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope
from idkmesh.work_unit_binding import canonical_digest


_ADMISSION_SCHEMA_VERSION = "0.1"
_ADMISSION_KIND = "github-webhook-delivery-admission"


class GitHubDeliveryConflict(RuntimeError):
    """A delivery identity was reused for different normalized content."""


@dataclass(frozen=True, slots=True)
class GitHubDeliveryAdmission:
    record: RunRecord
    request_digest: str
    idempotency_key: str
    created: bool

    @property
    def replayed(self) -> bool:
        return not self.created

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.record.run_id,
            "state": self.record.state,
            "request_digest": self.request_digest,
            "idempotency_key": self.idempotency_key,
            "created": self.created,
            "replayed": self.replayed,
        }


def github_delivery_idempotency_key(
    envelope: GitHubWebhookEnvelope,
) -> str:
    """Return the durable delivery namespace used for atomic run admission."""

    if not isinstance(envelope, GitHubWebhookEnvelope):
        raise TypeError("envelope must be GitHubWebhookEnvelope")
    return (
        "github-webhook:"
        + str(envelope.repository_id)
        + ":"
        + envelope.delivery_id
    )


def github_delivery_request_digest(
    envelope: GitHubWebhookEnvelope,
) -> str:
    """Digest all normalized request identity relevant before dispatch."""

    if not isinstance(envelope, GitHubWebhookEnvelope):
        raise TypeError("envelope must be GitHubWebhookEnvelope")
    return canonical_digest(
        {
            "schema_version": _ADMISSION_SCHEMA_VERSION,
            "kind": _ADMISSION_KIND,
            "envelope": envelope.to_dict(),
        }
    )


def _run_id(
    *,
    idempotency_key: str,
    request_digest: str,
) -> str:
    identity = canonical_digest(
        {
            "idempotency_key": idempotency_key,
            "request_digest": request_digest,
        }
    )
    return "github/" + identity[7:31]


def _metadata(envelope: GitHubWebhookEnvelope) -> dict[str, Any]:
    return {
        "schema_version": _ADMISSION_SCHEMA_VERSION,
        "kind": _ADMISSION_KIND,
        "repository": envelope.repository,
        "repository_id": envelope.repository_id,
        "delivery_id": envelope.delivery_id,
        "event": envelope.event,
        "action": envelope.action,
        "sender_login": envelope.sender_login,
        "sender_id": envelope.sender_id,
        "issue_number": envelope.issue_number,
        "label_name": envelope.label_name,
        "installation_id": envelope.installation_id,
        "payload_digest": envelope.payload_digest,
        "payload_bytes": envelope.payload_bytes,
    }


def admit_github_delivery(
    *,
    store: LocalMetadataStore,
    envelope: GitHubWebhookEnvelope,
    received_at: str,
) -> GitHubDeliveryAdmission:
    """Reserve one normalized GitHub delivery before any external work."""

    if not isinstance(store, LocalMetadataStore):
        raise TypeError("store must be LocalMetadataStore")
    if not isinstance(envelope, GitHubWebhookEnvelope):
        raise TypeError("envelope must be GitHubWebhookEnvelope")
    if not isinstance(received_at, str) or not received_at:
        raise ValueError("received_at must be a non-empty string")

    idempotency_key = github_delivery_idempotency_key(envelope)
    request_digest = github_delivery_request_digest(envelope)
    run_id = _run_id(
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )

    try:
        record, created = store.admit_run(
            run_id=run_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            state="proposed",
            metadata=_metadata(envelope),
            created_at=received_at,
        )
    except LocalStoreConflict as exc:
        raise GitHubDeliveryConflict(
            "GitHub delivery identity was reused with different normalized content"
        ) from exc

    return GitHubDeliveryAdmission(
        record=record,
        request_digest=request_digest,
        idempotency_key=idempotency_key,
        created=created,
    )
