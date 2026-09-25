"""Restart-safe local SQLite metadata/idempotency store for C1-F (#616).

This store is for development-mode connector control metadata. It is not the
GitHub-native durable ledger required by #597 and it is not canonical
application state.

The store persists compact, secret-free metadata only. Large logs/artifacts and
raw provider credentials are outside its contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping


SCHEMA_VERSION = 1

_ENV_SECRET_REF = re.compile(r"env:[A-Za-z_][A-Za-z0-9_]{0,127}\Z")

_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "client_secret",
    "credential",
    "password",
    "secret",
    "token",
)


class LocalStoreError(RuntimeError):
    pass


class LocalStoreConflict(LocalStoreError):
    pass


class UnsafeMetadataError(LocalStoreError):
    pass


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    idempotency_key: str
    request_digest: str
    state: str
    metadata: Mapping[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "idempotency_key": self.idempotency_key,
            "request_digest": self.request_digest,
            "state": self.state,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _session(path: Path) -> Iterator[sqlite3.Connection]:
    """Open one connection, commit/rollback its transaction, then always close it.

    ``sqlite3.Connection.__exit__`` commits or rolls back the transaction but
    does not close the connection, so a bare ``with _connect(path) as conn``
    leaks a connection (and file descriptor) on every call.
    """

    conn = _connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _safe_key(key: object) -> str:
    text = str(key)
    normalized = text.lower().replace("-", "_")
    if normalized == "secret_ref" or normalized.endswith("_secret_ref"):
        return text
    if any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS):
        raise UnsafeMetadataError(
            f"sensitive metadata key is not persistable: {text}"
        )
    return text


def _validate_json_safe(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnsafeMetadataError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            safe_key = _safe_key(key)
            normalized = safe_key.lower().replace("-", "_")
            if normalized == "secret_ref" or normalized.endswith("_secret_ref"):
                if (
                    not isinstance(child, str)
                    or _ENV_SECRET_REF.fullmatch(child) is None
                ):
                    raise UnsafeMetadataError(
                        f"secret reference at {path}.{safe_key} must use env:NAME"
                    )
            result[safe_key] = _validate_json_safe(child, f"{path}.{safe_key}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _validate_json_safe(child, f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    raise UnsafeMetadataError(
        f"unsupported metadata type at {path}: {type(value).__name__}"
    )


def _dump_metadata(metadata: Mapping[str, Any] | None) -> str:
    safe = _validate_json_safe({} if metadata is None else metadata)
    return json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_metadata(raw: str) -> Mapping[str, Any]:
    # A corrupt row is corrupt store input and must surface as a store error.
    # Raising json.JSONDecodeError here escaped every caller: it is a ValueError,
    # so neither the store nor the CLI caught it, and a single bad row crashed
    # with a traceback instead of a stable error code. Widening a caller to
    # ValueError is not the fix -- ConnectorProfileError is also a ValueError, so
    # that would reclassify every profile fault as a store fault.
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise LocalStoreError(f"stored metadata is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LocalStoreError("stored metadata is not an object")
    return value


class LocalMetadataStore:
    """Small SQLite store for connector/probe/route/run control metadata."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _migrate(self) -> None:
        with _session(self.path) as conn:
            current = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if current > SCHEMA_VERSION:
                raise LocalStoreError(
                    f"database schema version {current} is newer than supported {SCHEMA_VERSION}"
                )
            if current == 0:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS connections (
                        connection_id TEXT PRIMARY KEY,
                        metadata_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS probes (
                        connection_id TEXT NOT NULL,
                        checked_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        PRIMARY KEY (connection_id, checked_at)
                    );

                    CREATE TABLE IF NOT EXISTS routes (
                        route_id TEXT PRIMARY KEY,
                        request_digest TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        request_digest TEXT NOT NULL,
                        state TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS idempotency (
                        idempotency_key TEXT PRIMARY KEY,
                        request_digest TEXT NOT NULL,
                        run_id TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (run_id) REFERENCES runs(run_id)
                    );
                    """
                )
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _require_text(value: str, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        return value

    def record_connection(
        self,
        connection_id: str,
        *,
        metadata: Mapping[str, Any],
        updated_at: str,
    ) -> None:
        self._require_text(connection_id, "connection_id")
        self._require_text(updated_at, "updated_at")
        payload = _dump_metadata(metadata)
        with _session(self.path) as conn:
            conn.execute(
                """
                INSERT INTO connections(connection_id, metadata_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (connection_id, payload, updated_at),
            )

    def get_connection(self, connection_id: str) -> Mapping[str, Any] | None:
        self._require_text(connection_id, "connection_id")
        with _session(self.path) as conn:
            row = conn.execute(
                "SELECT metadata_json FROM connections WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
        return None if row is None else _load_metadata(row["metadata_json"])

    def list_connections(self) -> list[Mapping[str, Any]]:
        with _session(self.path) as conn:
            rows = conn.execute(
                "SELECT metadata_json FROM connections ORDER BY connection_id ASC"
            ).fetchall()
        return [_load_metadata(row["metadata_json"]) for row in rows]

    def record_probe(
        self,
        connection_id: str,
        *,
        checked_at: str,
        status: str,
        metadata: Mapping[str, Any],
    ) -> None:
        self._require_text(connection_id, "connection_id")
        self._require_text(checked_at, "checked_at")
        self._require_text(status, "status")
        payload = _dump_metadata(metadata)

        with _session(self.path) as conn:
            existing = conn.execute(
                """
                SELECT status, metadata_json
                FROM probes
                WHERE connection_id = ? AND checked_at = ?
                """,
                (connection_id, checked_at),
            ).fetchone()
            if existing is not None:
                if existing["status"] == status and existing["metadata_json"] == payload:
                    return
                raise LocalStoreConflict(
                    "probe identity already exists with different content"
                )
            conn.execute(
                """
                INSERT INTO probes(connection_id, checked_at, status, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (connection_id, checked_at, status, payload),
            )

    def latest_probe(self, connection_id: str) -> Mapping[str, Any] | None:
        self._require_text(connection_id, "connection_id")
        with _session(self.path) as conn:
            row = conn.execute(
                """
                SELECT checked_at, status, metadata_json
                FROM probes
                WHERE connection_id = ?
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                (connection_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "connection_id": connection_id,
            "checked_at": row["checked_at"],
            "status": row["status"],
            "metadata": _load_metadata(row["metadata_json"]),
        }

    def record_route(
        self,
        route_id: str,
        *,
        request_digest: str,
        metadata: Mapping[str, Any],
        created_at: str,
    ) -> None:
        self._require_text(route_id, "route_id")
        self._require_text(request_digest, "request_digest")
        self._require_text(created_at, "created_at")
        payload = _dump_metadata(metadata)

        with _session(self.path) as conn:
            existing = conn.execute(
                """
                SELECT request_digest, metadata_json, created_at
                FROM routes
                WHERE route_id = ?
                """,
                (route_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["request_digest"] == request_digest
                    and existing["metadata_json"] == payload
                    and existing["created_at"] == created_at
                ):
                    return
                raise LocalStoreConflict(
                    "route_id already exists with different content"
                )
            conn.execute(
                """
                INSERT INTO routes(route_id, request_digest, metadata_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (route_id, request_digest, payload, created_at),
            )

    def get_route(self, route_id: str) -> Mapping[str, Any] | None:
        self._require_text(route_id, "route_id")
        with _session(self.path) as conn:
            row = conn.execute(
                """
                SELECT request_digest, metadata_json, created_at
                FROM routes
                WHERE route_id = ?
                """,
                (route_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "route_id": route_id,
            "request_digest": row["request_digest"],
            "metadata": _load_metadata(row["metadata_json"]),
            "created_at": row["created_at"],
        }

    def admit_run(
        self,
        *,
        run_id: str,
        idempotency_key: str,
        request_digest: str,
        state: str,
        metadata: Mapping[str, Any],
        created_at: str,
    ) -> tuple[RunRecord, bool]:
        """Atomically admit a run.

        Returns (record, created). The same idempotency key with the same request
        digest returns the already-admitted run. The same key with a different
        digest fails closed.
        """

        for value, field in (
            (run_id, "run_id"),
            (idempotency_key, "idempotency_key"),
            (request_digest, "request_digest"),
            (state, "state"),
            (created_at, "created_at"),
        ):
            self._require_text(value, field)
        payload = _dump_metadata(metadata)

        conn = _connect(self.path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT request_digest, run_id
                FROM idempotency
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise LocalStoreConflict(
                        "idempotency key already exists with different request digest"
                    )
                record = self._get_run_with_conn(conn, existing["run_id"])
                if record is None:
                    raise LocalStoreError("idempotency row points to missing run")
                conn.commit()
                return record, False

            conn.execute(
                """
                INSERT INTO runs(
                    run_id, idempotency_key, request_digest, state,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    idempotency_key,
                    request_digest,
                    state,
                    payload,
                    created_at,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO idempotency(idempotency_key, request_digest, run_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (idempotency_key, request_digest, run_id, created_at),
            )
            record = self._get_run_with_conn(conn, run_id)
            if record is None:
                raise LocalStoreError("new run could not be re-read")
            conn.commit()
            return record, True
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise LocalStoreConflict("run identity conflicts with existing record") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_run_with_conn(
        self,
        conn: sqlite3.Connection,
        run_id: str,
    ) -> RunRecord | None:
        row = conn.execute(
            """
            SELECT run_id, idempotency_key, request_digest, state,
                   metadata_json, created_at, updated_at
            FROM runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return RunRecord(
            run_id=row["run_id"],
            idempotency_key=row["idempotency_key"],
            request_digest=row["request_digest"],
            state=row["state"],
            metadata=_load_metadata(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_run(self, run_id: str) -> RunRecord | None:
        self._require_text(run_id, "run_id")
        with _session(self.path) as conn:
            return self._get_run_with_conn(conn, run_id)

    def update_run(
        self,
        run_id: str,
        *,
        state: str,
        metadata: Mapping[str, Any],
        updated_at: str,
    ) -> RunRecord:
        self._require_text(run_id, "run_id")
        self._require_text(state, "state")
        self._require_text(updated_at, "updated_at")
        payload = _dump_metadata(metadata)

        with _session(self.path) as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET state = ?, metadata_json = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (state, payload, updated_at, run_id),
            )
            if cursor.rowcount != 1:
                raise LocalStoreError(f"unknown run_id: {run_id}")
            record = self._get_run_with_conn(conn, run_id)
        if record is None:
            raise LocalStoreError("updated run could not be re-read")
        return record
