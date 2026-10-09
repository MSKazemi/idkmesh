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

from idkmesh.work_unit_binding import canonical_digest


SCHEMA_VERSION = 3
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200

# C10-D/E local coordination metadata. Ownership and external execution
# occupancy deliberately have different lifetimes (see LOCAL_TASK_CLAIMS_V0_1).
_CLAIMS_DDL = """
CREATE TABLE IF NOT EXISTS task_claim_policies (
    task_key TEXT PRIMARY KEY,
    policy_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_claim_slots (
    task_key TEXT NOT NULL REFERENCES task_claim_policies(task_key),
    slot INTEGER NOT NULL,
    epoch INTEGER NOT NULL,
    PRIMARY KEY (task_key, slot)
);
CREATE TABLE IF NOT EXISTS task_claims (
    task_key TEXT NOT NULL,
    request_id TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    slot INTEGER NOT NULL,
    epoch INTEGER NOT NULL,
    owner_json TEXT NOT NULL,
    binding_json TEXT NOT NULL,
    authorization_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active', 'released', 'expired')),
    created_at INTEGER NOT NULL,
    acknowledged_at INTEGER,
    ack_by INTEGER NOT NULL,
    lease_until INTEGER NOT NULL,
    progress_by INTEGER NOT NULL,
    hard_until INTEGER NOT NULL,
    occupancy TEXT NOT NULL CHECK (occupancy IN ('none', 'unknown', 'running', 'terminal')),
    operation_id TEXT,
    execution_reference TEXT,
    submission_digest TEXT,
    PRIMARY KEY (task_key, request_id),
    UNIQUE (task_key, slot, epoch),
    FOREIGN KEY (task_key, slot) REFERENCES task_claim_slots(task_key, slot)
);
CREATE TABLE IF NOT EXISTS task_claim_clock (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    last_epoch INTEGER NOT NULL
);
"""

_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    project_id TEXT NOT NULL,
    work_unit_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    attempt_id TEXT,
    envelope_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, sequence);
CREATE INDEX IF NOT EXISTS events_by_project ON events(project_id, sequence);
CREATE INDEX IF NOT EXISTS events_by_work_unit ON events(work_unit_id, sequence);
CREATE INDEX IF NOT EXISTS events_by_type ON events(event_type, sequence);
CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""

# ADR-0023: the envelope fields a producer supplies; the store adds the
# sequence, the derived event_id, schema_version, kind and payload_digest.
_EVENT_STRING_FIELDS = (
    "occurred_at", "event_type", "authority_class",
    "project_id", "work_unit_id", "run_id",
)
_EVENT_FIELDS = frozenset(
    _EVENT_STRING_FIELDS
    + ("principal", "attempt_id", "source_revision",
       "evidence_reference", "payload")
)
EVENT_SCHEMA_VERSION = "0.1"
EVENT_KIND = "idkmesh-event"
# The published envelope's vocabulary (schemas/idkmesh-event-v0.1.schema.json),
# enforced here so a producer cannot persist an event that GET /events would
# then serve as schema-invalid (ADR-0023).
EVENT_TYPES = frozenset({"run.created", "run.cancelled"})
EVENT_AUTHORITY_CLASSES = frozenset(
    {
        "local_control",
        "worker_observation",
        "verifier_recommendation",
        "human_decision",
    }
)
_EVENT_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z\Z"
)
_EVENT_SOURCE_REVISION = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")

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
    try:
        conn = sqlite3.connect(path, timeout=30.0)
    except sqlite3.Error as exc:
        raise LocalStoreError(f"database error: {exc}") from exc
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as exc:
        conn.close()
        raise LocalStoreError(f"database error: {exc}") from exc
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
    except sqlite3.Error as exc:
        # A locked, unreadable or corrupt database is a store fault; callers
        # and the HTTP layer handle LocalStoreError, not raw sqlite3 errors.
        raise LocalStoreError(f"database error: {exc}") from exc
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
                conn.executescript(_EVENTS_DDL)
                conn.executescript(_CLAIMS_DDL)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif current < SCHEMA_VERSION:
                # Additive v1/v2 upgrades preserve all existing run/event rows.
                conn.executescript(_EVENTS_DDL)
                conn.executescript(_CLAIMS_DDL)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Serialize a trusted local metadata composition across processes.

        The adapter must read, validate and mutate within this transaction.
        This is not a worker-facing SQL interface or a distributed lock.
        """
        with _session(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            yield conn

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

    def list_connections_page(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        after: str | None = None,
    ) -> tuple[list[tuple[str, Mapping[str, Any]]], bool]:
        """Return one bounded page ordered by persisted connection id.

        The database identity is returned with each decoded metadata object
        so an API projection can reject legacy/free-form rows whose public
        id disagrees with the key under which the row was persisted.
        """
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not (1 <= limit <= MAX_LIST_LIMIT)
        ):
            raise ValueError(
                f"limit must be an integer between 1 and {MAX_LIST_LIMIT}"
            )
        if after is not None:
            self._require_text(after, "after")

        sql = "SELECT connection_id, metadata_json FROM connections "
        params: list[Any] = []
        if after is not None:
            sql += "WHERE connection_id > ? "
            params.append(after)
        sql += "ORDER BY connection_id ASC LIMIT ?"
        params.append(limit + 1)
        with _session(self.path) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        has_more = len(rows) > limit
        return [
            (row["connection_id"], _load_metadata(row["metadata_json"]))
            for row in rows[:limit]
        ], has_more

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
        event: Mapping[str, Any] | None = None,
    ) -> tuple[RunRecord, bool]:
        """Atomically admit a run.

        Returns (record, created). The same idempotency key with the same request
        digest returns the already-admitted run. The same key with a different
        digest fails closed.

        ``event``, when given, is appended in the same transaction as the new
        run row (ADR-0023): both commit or neither does. An idempotent replay
        returns the existing run and appends nothing.
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
        normalised_event = self._normalise_event(event, run_id=run_id)

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
            if normalised_event is not None:
                self._append_event(conn, normalised_event)
            conn.commit()
            return record, True
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise LocalStoreConflict("run identity conflicts with existing record") from exc
        except sqlite3.Error as exc:
            conn.rollback()
            raise LocalStoreError(f"database error: {exc}") from exc
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

    def list_runs(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        after: str | None = None,
        state: str | None = None,
        project_id: str | None = None,
        kinds: tuple[str, ...] | None = None,
    ) -> tuple[list[RunRecord], bool]:
        """Deterministic keyset-paginated run listing, ordered by run_id.

        ``kinds``, when given, restricts the listing to rows whose stored
        ``kind`` is one of those values (ADR-0024). The shared ``runs`` table
        also holds admission, error and GitHub rows that are not Product Spine
        runs; an explicit kind set excludes them deterministically instead of
        letting one foreign row fail the whole page.

        Returns ``(page, has_more)``. Ordering by the primary key rather than
        ``created_at`` avoids ties (two runs can share a timestamp; run_id is
        unique by construction) and avoids the offset-pagination hazard
        section 10 of the API conventions warns against for mutable streams:
        a run inserted between two list calls can never shift an already
        returned row out from under a caller paging by ``after=<run_id>``.

        ``state`` filters on the indexed column directly. ``project_id``
        filters via ``json_extract`` on the stored projection, since
        project_id is not (yet) its own indexed column; fine at the local
        development-store scale this store targets (module docstring).
        Both are bounded, explicitly-named filters -- section 11 of the API
        conventions requires an unknown filter to fail explicitly rather
        than silently match everything, which is enforced by callers only
        ever passing these two named parameters, never an arbitrary column.
        """
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not (1 <= limit <= MAX_LIST_LIMIT)
        ):
            raise ValueError(
                f"limit must be an integer between 1 and {MAX_LIST_LIMIT}"
            )
        if after is not None:
            self._require_text(after, "after")
        if state is not None:
            self._require_text(state, "state")
        if project_id is not None:
            self._require_text(project_id, "project_id")
        if kinds is not None:
            if (
                not isinstance(kinds, tuple)
                or not kinds
                or not all(isinstance(kind, str) and kind for kind in kinds)
            ):
                raise ValueError("kinds must be a non-empty tuple of strings")

        clauses = []
        params: list[Any] = []
        if kinds is not None:
            marks = ",".join("?" for _ in kinds)
            clauses.append(f"json_extract(metadata_json, '$.kind') IN ({marks})")
            params.extend(kinds)
        if after is not None:
            clauses.append("run_id > ?")
            params.append(after)
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        if project_id is not None:
            clauses.append(
                "json_extract(metadata_json, '$.projection.project_id') = ?"
            )
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit + 1)

        with _session(self.path) as conn:
            rows = conn.execute(
                f"""
                SELECT run_id, idempotency_key, request_digest, state,
                       metadata_json, created_at, updated_at
                FROM runs
                {where}
                ORDER BY run_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        has_more = len(rows) > limit
        page = rows[:limit]
        return (
            [
                RunRecord(
                    run_id=row["run_id"],
                    idempotency_key=row["idempotency_key"],
                    request_digest=row["request_digest"],
                    state=row["state"],
                    metadata=_load_metadata(row["metadata_json"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in page
            ],
            has_more,
        )

    # ADR-0021: WorkUnit and project read models are derived on demand from the
    # run projections already stored. No WorkUnit body or project record exists,
    # so nothing here may claim more than the stored references say.
    _WU_ID = "json_extract(metadata_json, '$.projection.work_unit.id')"
    _WU_VERSION = "json_extract(metadata_json, '$.projection.work_unit.version')"
    _WU_DIGEST = "json_extract(metadata_json, '$.projection.work_unit.digest')"
    _WU_SOURCE = (
        "json_extract(metadata_json, '$.projection.work_unit.source_revision')"
    )
    _PROJECT = "json_extract(metadata_json, '$.projection.project_id')"

    def _derived_revisions(
        self,
        conn: sqlite3.Connection,
        work_unit_ids: list[str],
        project_id: str | None,
    ) -> dict[str, list[dict[str, Any]]]:
        if not work_unit_ids:
            return {}
        marks = ",".join("?" for _ in work_unit_ids)
        params: list[Any] = list(work_unit_ids)
        project_clause = ""
        if project_id is not None:
            project_clause = f"AND {self._PROJECT} = ?"
            params.append(project_id)
        rows = conn.execute(
            f"""
            SELECT {self._WU_ID} AS wu_id,
                   {self._WU_VERSION} AS version,
                   {self._WU_DIGEST} AS digest,
                   {self._WU_SOURCE} AS source_revision,
                   COUNT(*) AS run_count
            FROM runs
            WHERE {self._WU_ID} IN ({marks}) {project_clause}
            GROUP BY wu_id, version, digest, source_revision
            ORDER BY wu_id ASC, version ASC, digest ASC, source_revision ASC
            """,
            params,
        ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["wu_id"], []).append(
                {
                    "version": row["version"],
                    "digest": row["digest"],
                    "source_revision": row["source_revision"],
                    "run_count": row["run_count"],
                }
            )
        return grouped

    @staticmethod
    def _work_unit_resource(
        work_unit_id: str, revisions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "id": work_unit_id,
            "run_count": sum(item["run_count"] for item in revisions),
            "revisions": revisions,
        }

    def list_work_units(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        after: str | None = None,
        project_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Deterministic keyset-paginated WorkUnit listing, ordered by id.

        One item per distinct WorkUnit id, derived from stored run references
        (ADR-0021). When ``project_id`` is given, ``run_count`` values count
        only that project's runs. Returns ``(page, has_more)``.
        """
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not (1 <= limit <= MAX_LIST_LIMIT)
        ):
            raise ValueError(
                f"limit must be an integer between 1 and {MAX_LIST_LIMIT}"
            )
        if after is not None:
            self._require_text(after, "after")
        if project_id is not None:
            self._require_text(project_id, "project_id")

        clauses = [f"{self._WU_ID} IS NOT NULL"]
        params: list[Any] = []
        if after is not None:
            clauses.append(f"{self._WU_ID} > ?")
            params.append(after)
        if project_id is not None:
            clauses.append(f"{self._PROJECT} = ?")
            params.append(project_id)
        params.append(limit + 1)

        with _session(self.path) as conn:
            id_rows = conn.execute(
                f"""
                SELECT DISTINCT {self._WU_ID} AS wu_id
                FROM runs
                WHERE {' AND '.join(clauses)}
                ORDER BY wu_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
            has_more = len(id_rows) > limit
            ids = [row["wu_id"] for row in id_rows[:limit]]
            grouped = self._derived_revisions(conn, ids, project_id)
        return (
            [self._work_unit_resource(wu, grouped.get(wu, [])) for wu in ids],
            has_more,
        )

    def get_work_unit(self, work_unit_id: str) -> dict[str, Any] | None:
        """The derived WorkUnit resource for one id, or None if no run uses it."""
        self._require_text(work_unit_id, "work_unit_id")
        with _session(self.path) as conn:
            grouped = self._derived_revisions(conn, [work_unit_id], None)
        revisions = grouped.get(work_unit_id)
        if not revisions:
            return None
        return self._work_unit_resource(work_unit_id, revisions)

    def get_project_counts(self, project_id: str) -> dict[str, Any] | None:
        """Derived per-project counts, or None if no run names the project.

        Returns ``{"project_id", "run_count", "state_counts",
        "work_unit_count"}`` where ``state_counts`` holds only the states that
        occur (the service zero-fills the canonical set). ADR-0021: no project
        record exists, so this is purely a count over stored runs.
        """
        self._require_text(project_id, "project_id")
        with _session(self.path) as conn:
            state_rows = conn.execute(
                f"""
                SELECT state, COUNT(*) AS n
                FROM runs
                WHERE {self._PROJECT} = ?
                GROUP BY state
                ORDER BY state ASC
                """,
                (project_id,),
            ).fetchall()
            if not state_rows:
                return None
            distinct = conn.execute(
                f"""
                SELECT COUNT(DISTINCT {self._WU_ID}) AS n
                FROM runs
                WHERE {self._PROJECT} = ? AND {self._WU_ID} IS NOT NULL
                """,
                (project_id,),
            ).fetchone()
        return {
            "project_id": project_id,
            "run_count": sum(row["n"] for row in state_rows),
            "state_counts": {row["state"]: row["n"] for row in state_rows},
            "work_unit_count": distinct["n"],
        }

    def update_run(
        self,
        run_id: str,
        *,
        state: str,
        metadata: Mapping[str, Any],
        updated_at: str,
        event: Mapping[str, Any] | None = None,
        expected_state: str | None = None,
    ) -> RunRecord:
        """Update a run (and optionally append its event) atomically.

        ``expected_state``, when given, makes the update conditional on the run
        still being in that state: a concurrent writer that already changed it
        gets ``LocalStoreConflict`` and no event is appended, so two racing
        callers cannot both record the same transition (ADR-0023).
        """
        self._require_text(run_id, "run_id")
        if expected_state is not None:
            self._require_text(expected_state, "expected_state")
        self._require_text(state, "state")
        self._require_text(updated_at, "updated_at")
        payload = _dump_metadata(metadata)
        normalised_event = self._normalise_event(event, run_id=run_id)

        with _session(self.path) as conn:
            where = "run_id = ?"
            params: list[Any] = [state, payload, updated_at, run_id]
            if expected_state is not None:
                where += " AND state = ?"
                params.append(expected_state)
            cursor = conn.execute(
                f"""
                UPDATE runs
                SET state = ?, metadata_json = ?, updated_at = ?
                WHERE {where}
                """,
                params,
            )
            if cursor.rowcount != 1:
                exists = conn.execute(
                    "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if exists is not None and expected_state is not None:
                    raise LocalStoreConflict(
                        f"run {run_id} is no longer in state {expected_state}"
                    )
                raise LocalStoreError(f"unknown run_id: {run_id}")
            if normalised_event is not None:
                self._append_event(conn, normalised_event)
            record = self._get_run_with_conn(conn, run_id)
        if record is None:
            raise LocalStoreError("updated run could not be re-read")
        return record

    # ---- ADR-0023: canonical append-only event source ----------------------

    @classmethod
    def _normalise_event(
        cls,
        event: Mapping[str, Any] | None,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Validate a producer-supplied event; ``None`` means "emit nothing".

        Raises ValueError for a malformed event so the caller's transaction
        rolls back before any row is written. ``occurred_at`` must be supplied:
        the store never reads a clock to invent a timestamp.
        """
        if event is None:
            return None
        if not isinstance(event, Mapping):
            raise ValueError("event must be a mapping")
        unknown = set(event) - _EVENT_FIELDS
        missing = _EVENT_FIELDS - set(event)
        if unknown or missing:
            raise ValueError(
                "event fields mismatch: "
                f"missing={sorted(missing)} unknown={sorted(unknown)}"
            )
        result: dict[str, Any] = {}
        for field in _EVENT_STRING_FIELDS:
            result[field] = cls._require_text(event[field], f"event.{field}")
        if result["event_type"] not in EVENT_TYPES:
            raise ValueError(f"event.event_type must be one of {sorted(EVENT_TYPES)}")
        if result["authority_class"] not in EVENT_AUTHORITY_CLASSES:
            raise ValueError(
                "event.authority_class must be one of "
                f"{sorted(EVENT_AUTHORITY_CLASSES)}"
            )
        if _EVENT_TIMESTAMP.match(result["occurred_at"]) is None:
            raise ValueError("event.occurred_at must be a UTC timestamp ending in Z")
        if run_id is not None and result["run_id"] != run_id:
            raise ValueError(
                "event.run_id must equal the run the event is committed with"
            )
        principal = event["principal"]
        if (
            not isinstance(principal, Mapping)
            or set(principal) != {"type", "id"}
        ):
            raise ValueError("event.principal must be {type, id}")
        result["principal"] = {
            "type": cls._require_text(principal["type"], "event.principal.type"),
            "id": cls._require_text(principal["id"], "event.principal.id"),
        }
        for field in ("attempt_id", "source_revision"):
            value = event[field]
            result[field] = (
                None if value is None else cls._require_text(value, f"event.{field}")
            )
        if (
            result["source_revision"] is not None
            and _EVENT_SOURCE_REVISION.match(result["source_revision"]) is None
        ):
            raise ValueError(
                "event.source_revision must be a 40 or 64 character hex digest"
            )
        reference = event["evidence_reference"]
        if reference is None:
            result["evidence_reference"] = None
        else:
            if not isinstance(reference, Mapping) or set(reference) != {
                "kind", "digest",
            }:
                raise ValueError("event.evidence_reference must be {kind, digest}")
            result["evidence_reference"] = {
                "kind": cls._require_text(
                    reference["kind"], "event.evidence_reference.kind"
                ),
                "digest": cls._require_text(
                    reference["digest"], "event.evidence_reference.digest"
                ),
            }
        payload = event["payload"]
        if not isinstance(payload, Mapping):
            raise ValueError("event.payload must be an object")
        # Reuses the store's secret-free, JSON-safe validation.
        result["payload"] = json.loads(_dump_metadata(payload))
        return result

    @staticmethod
    def _append_event(conn: sqlite3.Connection, event: dict[str, Any]) -> int:
        envelope = dict(event)
        envelope["payload_digest"] = canonical_digest(event["payload"])
        cursor = conn.execute(
            """
            INSERT INTO events(
                occurred_at, event_type, project_id, work_unit_id, run_id,
                attempt_id, envelope_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["occurred_at"],
                event["event_type"],
                event["project_id"],
                event["work_unit_id"],
                event["run_id"],
                event["attempt_id"],
                json.dumps(
                    envelope, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False,
                ),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def event_id_for(sequence: int) -> str:
        """The stable id of the event at ``sequence`` (unique in the stream)."""
        return f"evt-{sequence:012d}"

    @classmethod
    def _event_from_row(cls, row: sqlite3.Row) -> dict[str, Any]:
        try:
            envelope = json.loads(row["envelope_json"])
        except ValueError as exc:
            raise LocalStoreError(f"stored event is not valid JSON: {exc}") from exc
        if not isinstance(envelope, dict):
            raise LocalStoreError("stored event is not an object")
        sequence = int(row["sequence"])
        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "kind": EVENT_KIND,
            "event_id": cls.event_id_for(sequence),
            "sequence": sequence,
            **envelope,
        }

    def latest_event_sequence(self) -> int:
        """Sequence of the newest event, or 0 when the stream is empty."""
        with _session(self.path) as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS latest FROM events"
            ).fetchone()
        return int(row["latest"])

    def list_events(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        after_sequence: int = 0,
        project_id: str | None = None,
        run_id: str | None = None,
        work_unit_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Events with ``sequence > after_sequence``, ascending; ``(page, has_more)``.

        Keyset-paginated on the sequence, so a reader that has seen N has seen
        every committed event up to N (SQLite serialises writers). Filters are
        exact matches on the indexed columns.
        """
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not (1 <= limit <= MAX_LIST_LIMIT)
        ):
            raise ValueError(
                f"limit must be an integer between 1 and {MAX_LIST_LIMIT}"
            )
        if (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence < 0
        ):
            raise ValueError("after_sequence must be a non-negative integer")
        clauses = ["sequence > ?"]
        params: list[Any] = [after_sequence]
        for column, value in (
            ("project_id", project_id),
            ("run_id", run_id),
            ("work_unit_id", work_unit_id),
            ("event_type", event_type),
        ):
            if value is not None:
                self._require_text(value, column)
                clauses.append(f"{column} = ?")
                params.append(value)
        params.append(limit + 1)
        with _session(self.path) as conn:
            rows = conn.execute(
                f"""
                SELECT sequence, envelope_json
                FROM events
                WHERE {' AND '.join(clauses)}
                ORDER BY sequence ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        has_more = len(rows) > limit
        return [self._event_from_row(row) for row in rows[:limit]], has_more
