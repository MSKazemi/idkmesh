"""Deterministic serialization for the C9 GitHub-native durable ledger.

This module is deliberately pure and stdlib-only. It turns one already-shaped
``github-ledger-record-v0.1`` mapping into canonical bytes/digest metadata and
verifies complete append-only record chains. It performs no filesystem, Git,
GitHub, provider, dispatch, verification, acceptance, or integration action.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import re
from typing import Any

from idkmesh.work_unit_binding import canonical_digest


SCHEMA_VERSION = "0.1"
RECORD_KIND = "idkmesh-github-ledger-record"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_AUTHORITY_FIELDS = frozenset(
    {
        "dispatch",
        "verification",
        "acceptance",
        "canonical_state_write",
        "git_push",
        "integration",
        "merge",
    }
)


class GitHubLedgerSerializationError(ValueError):
    """Fail-closed record/chain error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class SerializedGitHubLedgerRecord:
    """One canonical ledger record ready for an immutable Git blob."""

    sequence: int
    record_id: str
    record_digest: str
    content: bytes


def _json_value(value: Any, field: str = "record") -> Any:
    """Return a plain JSON value while rejecting ambiguous/non-schema types."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise GitHubLedgerSerializationError(
            "non_canonical_number",
            (
                f"{field} contains a floating-point value; "
                "ledger v0.1 uses integer-only numbers"
            ),
        )
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise GitHubLedgerSerializationError(
                    "invalid_json_key",
                    f"{field} contains a non-string object key",
                )
            result[key] = _json_value(item, f"{field}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_json_value(item, f"{field}[]") for item in value]
    raise GitHubLedgerSerializationError(
        "non_json_value",
        f"{field} contains unsupported value type {type(value).__name__}",
    )


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubLedgerSerializationError(
            "invalid_record",
            f"{field} must be a JSON object",
        )
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GitHubLedgerSerializationError(
            "invalid_record",
            f"{field} must be an integer >= 1",
        )
    return value


def _sha256(
    value: Any,
    field: str,
    *,
    nullable: bool = False,
) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise GitHubLedgerSerializationError(
            "invalid_record",
            f"{field} must be a canonical sha256 digest",
        )
    return value


def _validate_semantics(record: dict[str, Any]) -> None:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise GitHubLedgerSerializationError(
            "unsupported_schema_version",
            f"expected schema_version {SCHEMA_VERSION!r}",
        )
    if record.get("kind") != RECORD_KIND:
        raise GitHubLedgerSerializationError(
            "invalid_kind",
            f"expected kind {RECORD_KIND!r}",
        )

    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not record_id:
        raise GitHubLedgerSerializationError(
            "invalid_record",
            "record_id must be a non-empty string",
        )

    sequence = _positive_int(
        record.get("ledger_sequence"),
        "ledger_sequence",
    )
    previous = _sha256(
        record.get("previous_record_digest"),
        "previous_record_digest",
        nullable=True,
    )
    if sequence == 1 and previous is not None:
        raise GitHubLedgerSerializationError(
            "invalid_chain_position",
            "ledger_sequence=1 requires previous_record_digest=null",
        )
    if sequence > 1 and previous is None:
        raise GitHubLedgerSerializationError(
            "invalid_chain_position",
            "ledger_sequence>1 requires previous_record_digest",
        )

    idempotency = _object(record.get("idempotency"), "idempotency")
    idempotency_attempt = _positive_int(
        idempotency.get("attempt_number"),
        "idempotency.attempt_number",
    )

    routing = _object(record.get("routing"), "routing")
    selected_connection = routing.get("selected_connection_id")
    if selected_connection is not None and not isinstance(
        selected_connection, str
    ):
        raise GitHubLedgerSerializationError(
            "invalid_record",
            "routing.selected_connection_id must be a string or null",
        )

    attempt = record.get("attempt")
    if attempt is not None:
        attempt_obj = _object(attempt, "attempt")
        attempt_number = _positive_int(
            attempt_obj.get("attempt_number"),
            "attempt.attempt_number",
        )
        if attempt_number != idempotency_attempt:
            raise GitHubLedgerSerializationError(
                "attempt_number_mismatch",
                (
                    "attempt.attempt_number must equal "
                    "idempotency.attempt_number"
                ),
            )
        connector_id = attempt_obj.get("connector_id")
        if selected_connection is None or connector_id != selected_connection:
            raise GitHubLedgerSerializationError(
                "attempt_connector_mismatch",
                (
                    "attempt.connector_id must equal "
                    "routing.selected_connection_id"
                ),
            )

    authority = _object(record.get("authority"), "authority")
    if set(authority) != _AUTHORITY_FIELDS:
        raise GitHubLedgerSerializationError(
            "authority_forbidden",
            (
                "ledger authority must contain exactly the v0.1 "
                "no-authority fields"
            ),
        )
    enabled = sorted(
        key for key, value in authority.items() if value is not False
    )
    if enabled:
        raise GitHubLedgerSerializationError(
            "authority_forbidden",
            (
                "ledger records cannot enable authority fields: "
                + ", ".join(enabled)
            ),
        )


def _canonical_text(
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    normalized = _json_value(record)
    if not isinstance(normalized, dict):
        raise GitHubLedgerSerializationError(
            "invalid_record",
            "ledger record must be a JSON object",
        )
    _validate_semantics(normalized)
    text = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return normalized, text


def serialize_github_ledger_record(
    record: Mapping[str, Any],
) -> SerializedGitHubLedgerRecord:
    """Canonicalize one v0.1 record without mutating it.

    ``record_digest`` is SHA-256 over the repository's frozen canonical JSON
    bytes *without* a line terminator. ``content`` is exactly those bytes plus
    one LF, which makes the Git blob POSIX-text friendly without changing the
    canonical object digest used by ``previous_record_digest``.
    """

    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")
    normalized, text = _canonical_text(record)
    canonical = text.encode("utf-8")
    return SerializedGitHubLedgerRecord(
        sequence=normalized["ledger_sequence"],
        record_id=normalized["record_id"],
        record_digest=canonical_digest(normalized),
        content=canonical + b"\n",
    )


def serialize_github_ledger_chain(
    records: Iterable[Mapping[str, Any]],
) -> tuple[SerializedGitHubLedgerRecord, ...]:
    """Serialize and verify one complete append-only run chain.

    A complete chain starts at sequence 1, has no gaps, stays bound to the same
    repository/project/run/WorkUnit identity, uses unique record/event ids, and
    links every record to the actual digest of its predecessor.
    """

    if isinstance(records, (str, bytes, bytearray, Mapping)):
        raise TypeError("records must be an iterable of record mappings")

    serialized: list[SerializedGitHubLedgerRecord] = []
    identity: tuple[Any, ...] | None = None
    seen_record_ids: set[str] = set()
    seen_event_ids: set[str] = set()
    previous_digest: str | None = None

    for expected_sequence, record in enumerate(records, start=1):
        item = serialize_github_ledger_record(record)
        if item.sequence != expected_sequence:
            raise GitHubLedgerSerializationError(
                "sequence_gap",
                (
                    f"expected ledger_sequence {expected_sequence}, "
                    f"got {item.sequence}"
                ),
            )

        normalized, _ = _canonical_text(record)
        work_unit = _object(normalized.get("work_unit"), "work_unit")
        actual_identity = (
            normalized.get("repository"),
            normalized.get("project_id"),
            normalized.get("run_id"),
            work_unit.get("id"),
            work_unit.get("version"),
            work_unit.get("digest"),
            work_unit.get("source_revision"),
        )
        if identity is None:
            identity = actual_identity
        elif actual_identity != identity:
            raise GitHubLedgerSerializationError(
                "chain_identity_changed",
                (
                    "repository/project/run/WorkUnit identity changed "
                    "within one ledger chain"
                ),
            )

        event = _object(normalized.get("event"), "event")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise GitHubLedgerSerializationError(
                "invalid_record",
                "event.event_id must be a non-empty string",
            )
        if item.record_id in seen_record_ids:
            raise GitHubLedgerSerializationError(
                "duplicate_record_id",
                f"duplicate record_id: {item.record_id}",
            )
        if event_id in seen_event_ids:
            raise GitHubLedgerSerializationError(
                "duplicate_event_id",
                f"duplicate event.event_id: {event_id}",
            )

        declared_previous = normalized.get("previous_record_digest")
        if declared_previous != previous_digest:
            raise GitHubLedgerSerializationError(
                "previous_digest_mismatch",
                (
                    "previous_record_digest does not match the canonical "
                    "digest of the preceding record"
                ),
            )

        seen_record_ids.add(item.record_id)
        seen_event_ids.add(event_id)
        serialized.append(item)
        previous_digest = item.record_digest

    if not serialized:
        raise GitHubLedgerSerializationError(
            "empty_chain",
            "a complete ledger chain must contain at least one record",
        )
    return tuple(serialized)
