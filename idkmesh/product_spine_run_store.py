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

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping

from idkmesh.connector_store import (
    DEFAULT_LIST_LIMIT,
    LocalMetadataStore,
    LocalStoreConflict,
    LocalStoreError,
    RunRecord,
)
from idkmesh.product_spine import (
    RUN_STATES,
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


_CURSOR_KIND = "product-spine-run-list-cursor-v1"


_WORK_UNIT_CURSOR_KIND = "product-spine-work-unit-list-cursor-v1"
_EVENT_CURSOR_KIND = "product-spine-event-list-cursor-v1"

# ADR-0023: the canonical event vocabulary. v0.1 emits only run.created and
# run.cancelled, both with authority class local_control; the other classes are
# reserved so a recommendation is never mistaken for a decision.
EVENT_TYPES = frozenset({"run.created", "run.cancelled"})
EVENT_AUTHORITY_CLASSES = frozenset(
    {
        "local_control",
        "worker_observation",
        "verifier_recommendation",
        "human_decision",
    }
)
_LOCAL_PRINCIPAL = {"type": "unauthenticated_local", "id": "local-cli"}
DEFAULT_EVENTS_AFTER_LIMIT = 200


def _encode_cursor(after_run_id: str, kind: str = _CURSOR_KIND) -> str:
    """Opaque next-page cursor: callers must treat this as a token, never
    construct or parse one themselves (API Conventions v0.1 section 10).

    ``kind`` namespaces the token so a cursor issued for one listing is
    rejected by another."""
    payload = json.dumps(
        {"kind": kind, "after": after_run_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str, kind: str = _CURSOR_KIND) -> str:
    if not isinstance(cursor, str) or not cursor:
        raise ProductSpineRunStoreError(
            "invalid_cursor", "cursor must be a non-empty string"
        )
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
    except Exception as exc:
        raise ProductSpineRunStoreError(
            "invalid_cursor", "cursor is not a value this service issued"
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("kind") != kind
        or not isinstance(payload.get("after"), str)
        or not payload["after"]
    ):
        raise ProductSpineRunStoreError(
            "invalid_cursor", "cursor is not a value this service issued"
        )
    return payload["after"]


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


def _run_event(
    run: ProductSpineRun,
    *,
    event_type: str,
    occurred_at: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the producer-side fields of a canonical event for ``run``.

    ``occurred_at`` is the validated timestamp the caller already supplied for
    the state change, never a clock read (ADR-0023). The store adds the
    sequence, event id and payload digest.
    """
    projection = run.to_dict()
    return {
        "occurred_at": occurred_at,
        "event_type": event_type,
        "principal": dict(_LOCAL_PRINCIPAL),
        "authority_class": "local_control",
        "project_id": projection["project_id"],
        "work_unit_id": projection["work_unit"]["id"],
        "run_id": projection["run_id"],
        "attempt_id": None,
        "source_revision": projection["work_unit"]["source_revision"],
        "evidence_reference": None,
        "payload": dict(payload),
    }


def _sequence_from_cursor(cursor: str) -> int:
    after = _decode_cursor(cursor, _EVENT_CURSOR_KIND)
    if not after.isdigit():
        raise ProductSpineRunStoreError(
            "invalid_cursor", "cursor is not a value this service issued"
        )
    return int(after)


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
                event=_run_event(
                    active,
                    event_type="run.created",
                    occurred_at=timestamp,
                    payload={
                        "state": active.state,
                        "request_digest": digest,
                    },
                ),
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

    def list(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        cursor: str | None = None,
        state: str | None = None,
        project_id: str | None = None,
    ) -> tuple[list[ProductSpineRun], str | None]:
        """Deterministic keyset-paginated run listing.

        Returns ``(runs, next_cursor)``; ``next_cursor`` is ``None`` on the
        last page. The cursor is opaque -- see ``_encode_cursor`` -- and
        raises ``ProductSpineRunStoreError("invalid_cursor", ...)`` for
        anything this service did not itself issue. ``state``, if given,
        must be one of the canonical ``RUN_STATES``; an unrecognized value
        fails explicitly with ``invalid_state`` rather than silently
        matching zero rows (API Conventions v0.1 section 11).
        """
        if state is not None and state not in RUN_STATES:
            raise ProductSpineRunStoreError(
                "invalid_state",
                f"state must be one of {sorted(RUN_STATES)}",
            )
        after = _decode_cursor(cursor) if cursor is not None else None
        try:
            records, has_more = self._store.list_runs(
                limit=limit, after=after, state=state, project_id=project_id,
            )
        except ValueError as exc:
            raise ProductSpineRunStoreError("invalid_limit", str(exc)) from exc
        runs = [_restore(record) for record in records]
        next_cursor = _encode_cursor(records[-1].run_id) if has_more else None
        return runs, next_cursor

    def list_work_units(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        cursor: str | None = None,
        project_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Derived WorkUnit listing (ADR-0021), ordered by WorkUnit id.

        Returns ``(work_units, next_cursor)``. The cursor is opaque, namespaced
        to this listing, and fails closed with ``invalid_cursor`` for anything
        this service did not issue.
        """
        after = (
            _decode_cursor(cursor, _WORK_UNIT_CURSOR_KIND)
            if cursor is not None
            else None
        )
        try:
            items, has_more = self._store.list_work_units(
                limit=limit, after=after, project_id=project_id,
            )
        except ValueError as exc:
            raise ProductSpineRunStoreError("invalid_limit", str(exc)) from exc
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc
        next_cursor = (
            _encode_cursor(items[-1]["id"], _WORK_UNIT_CURSOR_KIND)
            if has_more
            else None
        )
        return items, next_cursor

    def get_work_unit(self, work_unit_id: str) -> dict[str, Any]:
        """One derived WorkUnit resource, or ``work_unit_not_found``."""
        if not isinstance(work_unit_id, str) or not work_unit_id:
            raise ProductSpineRunStoreError(
                "invalid_work_unit_id",
                "work_unit_id must be a non-empty string",
            )
        try:
            resource = self._store.get_work_unit(work_unit_id)
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc
        if resource is None:
            raise ProductSpineRunStoreError(
                "work_unit_not_found",
                f"no stored run references work unit: {work_unit_id}",
            )
        return resource

    def get_project(self, project_id: str) -> dict[str, Any]:
        """One derived project summary (ADR-0021), or ``project_not_found``.

        ``runs_by_state`` lists every canonical run state, zero-filled, so the
        shape is identical for every project. No health or status rollup is
        computed: counts only, nothing selected.
        """
        if not isinstance(project_id, str) or not project_id:
            raise ProductSpineRunStoreError(
                "invalid_project_id",
                "project_id must be a non-empty string",
            )
        try:
            counts = self._store.get_project_counts(project_id)
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc
        if counts is None:
            raise ProductSpineRunStoreError(
                "project_not_found",
                f"no stored run references project: {project_id}",
            )
        return {
            "project_id": counts["project_id"],
            "run_count": counts["run_count"],
            "runs_by_state": {
                state: counts["state_counts"].get(state, 0)
                for state in sorted(RUN_STATES)
            },
            "work_unit_count": counts["work_unit_count"],
        }

    @staticmethod
    def _check_event_type(event_type: str | None) -> None:
        if event_type is not None and event_type not in EVENT_TYPES:
            raise ProductSpineRunStoreError(
                "invalid_event_type",
                f"event_type must be one of {sorted(EVENT_TYPES)}",
            )

    def list_events(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        cursor: str | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
        work_unit_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Canonical events (ADR-0023), ascending by sequence.

        Returns ``(events, next_cursor)``. The cursor is opaque, scoped to this
        listing, and fails closed with ``invalid_cursor``. An unknown
        ``event_type`` fails with ``invalid_event_type`` rather than matching
        nothing (API Conventions v0.1 section 11).
        """
        self._check_event_type(event_type)
        after = _sequence_from_cursor(cursor) if cursor is not None else 0
        try:
            events, has_more = self._store.list_events(
                limit=limit,
                after_sequence=after,
                project_id=project_id,
                run_id=run_id,
                work_unit_id=work_unit_id,
                event_type=event_type,
            )
        except ValueError as exc:
            raise ProductSpineRunStoreError("invalid_limit", str(exc)) from exc
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc
        next_cursor = (
            _encode_cursor(str(events[-1]["sequence"]), _EVENT_CURSOR_KIND)
            if has_more
            else None
        )
        return events, next_cursor

    def events_after(
        self,
        sequence: int,
        *,
        limit: int = DEFAULT_EVENTS_AFTER_LIMIT,
        project_id: str | None = None,
        run_id: str | None = None,
        work_unit_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Events with ``sequence > sequence`` (the SSE resume primitive)."""
        self._check_event_type(event_type)
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ProductSpineRunStoreError(
                "invalid_sequence", "sequence must be a non-negative integer"
            )
        try:
            events, _ = self._store.list_events(
                limit=limit,
                after_sequence=sequence,
                project_id=project_id,
                run_id=run_id,
                work_unit_id=work_unit_id,
                event_type=event_type,
            )
        except ValueError as exc:
            raise ProductSpineRunStoreError("invalid_limit", str(exc)) from exc
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc
        return events

    def latest_event_sequence(self) -> int:
        """Sequence of the newest event (0 if none): the live-tail position."""
        try:
            return self._store.latest_event_sequence()
        except LocalStoreError as exc:
            raise ProductSpineRunStoreError("store_error", str(exc)) from exc

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
                event=_run_event(
                    cancelled,
                    event_type="run.cancelled",
                    occurred_at=timestamp,
                    payload={
                        "previous_state": current.run.state,
                        "state": cancelled.state,
                    },
                ),
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
