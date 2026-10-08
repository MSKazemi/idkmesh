"""Read-only public projection of persisted connector-control metadata.

The local metadata store intentionally supports legacy/free-form rows for CLI
compatibility. HTTP must not serialize those rows verbatim: this module
projects only the canonical secret-free connector summary and fails closed
when a stored row does not match that contract.
"""

from __future__ import annotations

import base64
import json
import math
from typing import Any, Mapping

from idkmesh.connector_store import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    LocalMetadataStore,
)

_CURSOR_KIND = "connector-control-connection-list-cursor-v1"
_RESOURCE_FIELDS = frozenset({
    "id", "kind", "driver", "enabled", "auth_ref_configured",
    "capability_tiers", "task_classes", "tools", "candidate_types",
    "max_risk", "external_processing", "project_spend_usd_max",
    "max_concurrency",
})
_ARRAY_FIELDS = ("capability_tiers", "task_classes", "tools", "candidate_types")


class ConnectorControlReadError(RuntimeError):
    """Stable read-model error safe to expose without stored row data."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _invalid_record() -> None:
    raise ConnectorControlReadError(
        "connection_record_invalid",
        "stored connection metadata is not a canonical public connection resource",
    )


def _require_text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        _invalid_record()
    return value


def _string_array(value: Any) -> list[str]:
    if not isinstance(value, list):
        _invalid_record()
    if any(not isinstance(item, str) or not item for item in value):
        _invalid_record()
    if len(set(value)) != len(value):
        _invalid_record()
    return list(value)


def _resource(stored_id: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != _RESOURCE_FIELDS:
        _invalid_record()
    if raw.get("id") != stored_id:
        _invalid_record()
    result: dict[str, Any] = {
        "id": _require_text(raw["id"]),
        "kind": _require_text(raw["kind"]),
        "driver": _require_text(raw["driver"]),
        "max_risk": _require_text(raw["max_risk"]),
    }
    for field in ("enabled", "auth_ref_configured", "external_processing"):
        if not isinstance(raw[field], bool):
            _invalid_record()
        result[field] = raw[field]
    for field in _ARRAY_FIELDS:
        result[field] = _string_array(raw[field])
    spend = raw["project_spend_usd_max"]
    if (
        not isinstance(spend, (int, float))
        or isinstance(spend, bool)
        or not math.isfinite(spend)
        or spend < 0
    ):
        _invalid_record()
    result["project_spend_usd_max"] = spend
    concurrency = raw["max_concurrency"]
    if (
        not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or concurrency < 1
    ):
        _invalid_record()
    result["max_concurrency"] = concurrency
    return result


def _encode_cursor(after_id: str) -> str:
    payload = json.dumps(
        {"kind": _CURSOR_KIND, "after": after_id},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> str:
    if not isinstance(cursor, str) or not cursor:
        raise ConnectorControlReadError(
            "invalid_cursor", "cursor must be a non-empty service-issued value"
        )
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
    except Exception as exc:
        raise ConnectorControlReadError(
            "invalid_cursor", "cursor is not a value this service issued"
        ) from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "after"}
        or value.get("kind") != _CURSOR_KIND
        or not isinstance(value.get("after"), str)
        or not value["after"]
    ):
        raise ConnectorControlReadError(
            "invalid_cursor", "cursor is not a value this service issued"
        )
    return value["after"]


class ConnectorControlReadService:
    """Bounded read service over persisted secret-free connector metadata."""

    def __init__(self, store: LocalMetadataStore) -> None:
        self.store = store

    def list_connections(
        self, *, limit: int = DEFAULT_LIST_LIMIT, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not (1 <= limit <= MAX_LIST_LIMIT)
        ):
            raise ConnectorControlReadError(
                "invalid_limit",
                f"limit must be an integer between 1 and {MAX_LIST_LIMIT}",
            )
        after = None if cursor is None else _decode_cursor(cursor)
        rows, has_more = self.store.list_connections_page(
            limit=limit, after=after
        )
        items = [_resource(stored_id, raw) for stored_id, raw in rows]
        next_cursor = _encode_cursor(items[-1]["id"]) if has_more else None
        return items, next_cursor
