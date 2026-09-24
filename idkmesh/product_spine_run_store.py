"""Durable bounded Product Spine run control for the C7-D CLI.

This module persists only canonical ProductSpineRun projections through the
existing LocalMetadataStore. It does not dispatch connectors or workers.

Create:
- accepts only a strict ProductSpineRun in state="proposed";
- atomically reserves a namespaced idempotency key;
- exact replay returns the existing projection;
- conflicting replay fails closed.

Status:
- strictly reconstructs the retained ProductSpineRun and checks store/projection
  state and identity consistency.

Cancel:
- applies the canonical Product Spine transition to "cancelled";
- performs no provider cancellation, process termination, GitHub mutation,
  verification, acceptance, push, or merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    LocalStoreError,
    RunRecord,
)
from idkmesh.product_spine import (
    ProductSpineError,
    ProductSpineRun,
    projection_from_mapping,
)
from idkmesh.work_unit_binding import canonical_digest


SCHEMA_VERSION = "0.1"
_RECORD_KIND = "product-spine-cli-run"
_IDEMPOTENCY_PREFIX = "product-spine-cli:create:"


class ProductSpineRunStoreError(RuntimeError):
    """Stable bounded run-control error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PersistedProductSpineRun:
    run: ProductSpineRun
    idempotency_key: str
    create_request_digest: str
    created: bool
    replayed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "idempotency_key": self.idempotency_key,
            "create_request_digest": self.create_request_digest,
            "created": self.created,
            "replayed": self.replayed,
            "provider_execution_terminated": False,
            "candidate_accepted": False,
            "merge_authority": False,
        }


def _idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductSpineRunStoreError(
            "invalid_idempotency_key",
            "idempotency key must be a non-empty string",
        )
    value = value.strip()
    if len(value) > 256:
        raise ProductSpineRunStoreError(
            "invalid_idempotency_key",
            "idempotency key exceeds 256 characters",
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ProductSpineRunStoreError(
            "invalid_idempotency_key",
            "idempotency key contains control characters",
        )
    return value


def _timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductSpineRunStoreError(
            "invalid_timestamp",
            f"{field} must be a non-empty string",
        )
    text = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ProductSpineRunStoreError(
            "invalid_timestamp",
            f"{field} contains control characters",
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductSpineRunStoreError(
            "invalid_timestamp",
            f"{field} must be an ISO-8601 timestamp",
        ) from exc
    if parsed.tzinfo is None:
        raise ProductSpineRunStoreError(
            "invalid_timestamp",
            f"{field} must include a timezone",
        )
    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _projection(
    value: ProductSpineRun | Mapping[str, Any],
) -> ProductSpineRun:
    if isinstance(value, ProductSpineRun):
        return value
    if not isinstance(value, Mapping):
        raise ProductSpineRunStoreError(
            "invalid_projection",
            "run projection must be a ProductSpineRun or mapping",
        )
    try:
        return projection_from_mapping(value)
    except ProductSpineError as exc:
        raise ProductSpineRunStoreError(
            "invalid_projection",
            str(exc),
        ) from exc


def run_create_request_digest(run: ProductSpineRun) -> str:
    if not isinstance(run, ProductSpineRun):
        raise TypeError("run must be ProductSpineRun")
    return canonical_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": _RECORD_KIND,
            "projection": run.to_dict(),
        }
    )


def _metadata(
    run: ProductSpineRun,
    *,
    create_request_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": _RECORD_KIND,
        "create_request_digest": create_request_digest,
        "product_spine_request_digest": run.request_digest,
        "projection": run.to_dict(),
    }


def _restore(
    record: RunRecord,
    *,
    expected_idempotency_key: str | None = None,
) -> ProductSpineRun:
    metadata = record.metadata
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("schema_version") != SCHEMA_VERSION
        or metadata.get("kind") != _RECORD_KIND
    ):
        raise ProductSpineRunStoreError(
            "not_product_spine_cli_run",
            "stored run is not a C7-D Product Spine CLI run",
        )
    if metadata.get("create_request_digest") != record.request_digest:
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored create request digest does not match atomic run record",
        )
    if (
        expected_idempotency_key is not None
        and record.idempotency_key != expected_idempotency_key
    ):
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored idempotency key differs from replay request",
        )

    projection = metadata.get("projection")
    if not isinstance(projection, Mapping):
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored Product Spine projection is missing",
        )
    try:
        run = projection_from_mapping(projection)
    except ProductSpineError as exc:
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            str(exc),
        ) from exc

    if run.run_id != record.run_id:
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored projection run_id differs from atomic run record",
        )
    if run.state != record.state:
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored projection state differs from atomic run record",
        )
    if metadata.get("product_spine_request_digest") != run.request_digest:
        raise ProductSpineRunStoreError(
            "persisted_state_corrupt",
            "stored Product Spine request digest differs from projection",
        )
    return run


class ProductSpineRunStore:
    """Small application service for durable proposed/status/cancel control."""

    def __init__(self, store: LocalMetadataStore) -> None:
        if not isinstance(store, LocalMetadataStore):
            raise TypeError("store must be LocalMetadataStore")
        self._store = store

    def create(
        self,
        run: ProductSpineRun | Mapping[str, Any],
        *,
        idempotency_key: str,
        created_at: str,
    ) -> PersistedProductSpineRun:
        active = _projection(run)
        if active.state != "proposed":
            raise ProductSpineRunStoreError(
                "create_requires_proposed",
                "run create accepts only state='proposed'",
            )

        caller_key = _idempotency_key(idempotency_key)
        stored_key = _IDEMPOTENCY_PREFIX + caller_key
        timestamp = _timestamp(created_at, "created_at")
        digest = run_create_request_digest(active)

        try:
            record, created = self._store.admit_run(
                run_id=active.run_id,
                idempotency_key=stored_key,
                request_digest=digest,
                state=active.state,
                metadata=_metadata(
                    active,
                    create_request_digest=digest,
                ),
                created_at=timestamp,
            )
        except LocalStoreConflict as exc:
            raise ProductSpineRunStoreError(
                "idempotency_conflict",
                str(exc),
            ) from exc

        restored = _restore(
            record,
            expected_idempotency_key=stored_key,
        )
        return PersistedProductSpineRun(
            run=restored,
            idempotency_key=caller_key,
            create_request_digest=digest,
            created=created,
            replayed=not created,
        )

    def status(self, run_id: str) -> PersistedProductSpineRun:
        if not isinstance(run_id, str) or not run_id:
            raise ProductSpineRunStoreError(
                "invalid_run_id",
                "run_id must be a non-empty string",
            )
        try:
            record = self._store.get_run(run_id)
        except (LocalStoreError, ValueError) as exc:
            raise ProductSpineRunStoreError(
                "store_error",
                str(exc),
            ) from exc
        if record is None:
            raise ProductSpineRunStoreError(
                "run_not_found",
                f"unknown run_id: {run_id}",
            )
        run = _restore(record)
        caller_key = record.idempotency_key
        if caller_key.startswith(_IDEMPOTENCY_PREFIX):
            caller_key = caller_key[len(_IDEMPOTENCY_PREFIX):]
        return PersistedProductSpineRun(
            run=run,
            idempotency_key=caller_key,
            create_request_digest=record.request_digest,
            created=False,
            replayed=False,
        )

    def cancel(
        self,
        run_id: str,
        *,
        updated_at: str,
    ) -> PersistedProductSpineRun:
        current = self.status(run_id)
        timestamp = _timestamp(updated_at, "updated_at")

        if current.run.state == "cancelled":
            return current

        try:
            cancelled = current.run.transition("cancelled")
        except ProductSpineError as exc:
            raise ProductSpineRunStoreError(
                "cancel_not_allowed",
                str(exc),
            ) from exc

        try:
            record = self._store.update_run(
                run_id,
                state=cancelled.state,
                metadata=_metadata(
                    cancelled,
                    create_request_digest=current.create_request_digest,
                ),
                updated_at=timestamp,
            )
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError(
                "store_error",
                str(exc),
            ) from exc

        restored = _restore(record)
        return PersistedProductSpineRun(
            run=restored,
            idempotency_key=current.idempotency_key,
            create_request_digest=current.create_request_digest,
            created=False,
            replayed=False,
        )
