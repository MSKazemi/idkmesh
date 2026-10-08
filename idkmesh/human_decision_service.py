"""Immutable Human Decision application service for API issue #740.

This module is deliberately transport-neutral.  A network HTTP adapter is not
enabled here: API_CONVENTIONS_V0_1 requires a trusted authenticated principal
and policy authorization for durable mutations, while the current local
Control Tower token is explicitly *not* such a principal.

The service consumes a trusted :class:`ActorContext`, an already-verified
Product Spine evidence reader, and a small append-only SQLite decision store.
It never dispatches work, changes canonical project state, pushes Git, or
merges code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Protocol

from idkmesh.enterprise_authz import ActorContext
from idkmesh.work_unit_binding import canonical_digest


REQUEST_KIND = "idkmesh-human-decision-request"
RESPONSE_KIND = "idkmesh-human-decision-response"
RECORD_KIND = "idkmesh-human-decision-record"
SCHEMA_VERSION = "0.1"
API_VERSION = "v1"
KNOWN_DECISIONS = frozenset({"accept", "reject", "escalate"})
_AUTHORITY = {
    "canonical_state_write": False,
    "git_push": False,
    "merge": False,
}
_IDEMPOTENCY_RE = re.compile(r"^[\x21-\x7e]{1,256}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DECISION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,127}$")


class HumanDecisionServiceError(RuntimeError):
    """Stable application error for decision recording."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EvidenceReader(Protocol):
    def get_run_evidence(self, run_id: str) -> Mapping[str, Any]:
        """Return run_id, evidence_report_digest and evidence_report."""


@dataclass(frozen=True, slots=True)
class PersistedHumanDecision:
    decision_record: Mapping[str, Any]
    decision_record_digest: str
    created: bool
    replayed: bool

    def response(self) -> dict[str, Any]:
        return {
            "api_version": API_VERSION,
            "schema_version": SCHEMA_VERSION,
            "kind": RESPONSE_KIND,
            "ok": True,
            "decision_record": dict(self.decision_record),
            "decision_record_digest": self.decision_record_digest,
        }


class HumanDecisionStore:
    """Append-only local decision/idempotency store.

    The store has its own schema version so it does not silently mutate the
    connector-control database migration contract.  A caller may still place
    it beside the Product Spine database as a separate file.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise HumanDecisionServiceError("store_error", f"database error: {exc}") from exc

    def _migrate(self) -> None:
        conn = self._connect()
        try:
            with conn:
                current = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if current > self.SCHEMA_VERSION:
                    raise HumanDecisionServiceError(
                        "store_version_unsupported",
                        f"decision-store schema version {current} is newer than "
                        f"supported {self.SCHEMA_VERSION}",
                    )
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS human_decisions (
                        decision_id TEXT PRIMARY KEY,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        request_digest TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        evidence_report_digest TEXT NOT NULL,
                        decision_record_json TEXT NOT NULL,
                        decision_record_digest TEXT NOT NULL,
                        decided_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS human_decisions_by_run
                    ON human_decisions(run_id, decided_at, decision_id);

                    CREATE TRIGGER IF NOT EXISTS human_decisions_no_update
                    BEFORE UPDATE ON human_decisions
                    BEGIN SELECT RAISE(ABORT, 'human decisions are append-only'); END;

                    CREATE TRIGGER IF NOT EXISTS human_decisions_no_delete
                    BEFORE DELETE ON human_decisions
                    BEGIN SELECT RAISE(ABORT, 'human decisions are append-only'); END;
                    """
                )
                conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        except HumanDecisionServiceError:
            raise
        except sqlite3.Error as exc:
            raise HumanDecisionServiceError("store_error", f"database error: {exc}") from exc
        finally:
            conn.close()

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            record = json.loads(row["decision_record_json"])
        except (TypeError, ValueError) as exc:
            raise HumanDecisionServiceError(
                "persisted_state_corrupt", "stored decision record is not valid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise HumanDecisionServiceError(
                "persisted_state_corrupt", "stored decision record is not an object"
            )
        observed = canonical_digest(record)
        if observed != row["decision_record_digest"]:
            raise HumanDecisionServiceError(
                "persisted_state_corrupt",
                "stored decision record digest does not match stored content",
            )
        return record

    def create(
        self,
        *,
        idempotency_key: str,
        request_digest: str,
        decision_record: Mapping[str, Any],
    ) -> PersistedHumanDecision:
        record = dict(decision_record)
        record_json = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        record_digest = canonical_digest(record)
        decision_id = record["decision_id"]
        run_id = record["evidence_report"]["run_id"]
        evidence_digest = record["evidence_report"]["digest"]
        decided_at = record["decided_at"]

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT decision_id, idempotency_key, request_digest, run_id,
                       evidence_report_digest, decision_record_json,
                       decision_record_digest, decided_at
                FROM human_decisions
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise HumanDecisionServiceError(
                        "idempotency_conflict",
                        "idempotency key already exists with a different request digest",
                    )
                stored = self._record_from_row(existing)
                if stored["decision_id"] != existing["decision_id"]:
                    raise HumanDecisionServiceError(
                        "persisted_state_corrupt",
                        "stored decision identity does not match stored record",
                    )
                conn.commit()
                return PersistedHumanDecision(
                    decision_record=stored,
                    decision_record_digest=existing["decision_record_digest"],
                    created=False,
                    replayed=True,
                )

            try:
                conn.execute(
                    """
                    INSERT INTO human_decisions(
                        decision_id, idempotency_key, request_digest, run_id,
                        evidence_report_digest, decision_record_json,
                        decision_record_digest, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        idempotency_key,
                        request_digest,
                        run_id,
                        evidence_digest,
                        record_json,
                        record_digest,
                        decided_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise HumanDecisionServiceError(
                    "decision_identity_conflict",
                    "decision identity conflicts with an existing immutable record",
                ) from exc
            conn.commit()
            return PersistedHumanDecision(
                decision_record=record,
                decision_record_digest=record_digest,
                created=True,
                replayed=False,
            )
        except HumanDecisionServiceError:
            conn.rollback()
            raise
        except sqlite3.Error as exc:
            conn.rollback()
            raise HumanDecisionServiceError("store_error", f"database error: {exc}") from exc
        finally:
            conn.close()

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        if not isinstance(run_id, str) or not run_id:
            raise HumanDecisionServiceError(
                "invalid_run_id", "run_id must be a non-empty string"
            )
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT decision_id, idempotency_key, request_digest, run_id,
                       evidence_report_digest, decision_record_json,
                       decision_record_digest, decided_at
                FROM human_decisions
                WHERE run_id = ?
                ORDER BY decided_at ASC, decision_id ASC
                """,
                (run_id,),
            ).fetchall()
            return [self._record_from_row(row) for row in rows]
        except HumanDecisionServiceError:
            raise
        except sqlite3.Error as exc:
            raise HumanDecisionServiceError("store_error", f"database error: {exc}") from exc
        finally:
            conn.close()


def _require_idempotency_key(value: Any) -> str:
    if not isinstance(value, str) or _IDEMPOTENCY_RE.fullmatch(value) is None:
        raise HumanDecisionServiceError(
            "invalid_idempotency_key",
            "idempotency key must contain 1-256 visible ASCII characters",
        )
    return value


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise HumanDecisionServiceError(
            "invalid_decided_at", "decided_at must be an ISO-8601 UTC timestamp ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise HumanDecisionServiceError(
            "invalid_decided_at", "decided_at must be a valid ISO-8601 UTC timestamp"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise HumanDecisionServiceError(
            "invalid_decided_at", "decided_at must resolve to UTC"
        )
    return value


def _validate_actor(actor: Any, *, evaluated_at_epoch: int) -> ActorContext:
    if not isinstance(actor, ActorContext):
        raise HumanDecisionServiceError(
            "principal_required", "a trusted ActorContext is required"
        )
    if actor.actor_type != "human":
        raise HumanDecisionServiceError(
            "principal_type_denied",
            "the v0.1 Human Decision service accepts only a trusted human principal",
        )
    if not actor.authenticated:
        raise HumanDecisionServiceError(
            "principal_unauthenticated", "principal is not authenticated"
        )
    if actor.revoked:
        raise HumanDecisionServiceError("principal_revoked", "principal is revoked")
    if actor.expires_at_epoch is not None and evaluated_at_epoch >= actor.expires_at_epoch:
        raise HumanDecisionServiceError("principal_expired", "principal is expired")
    return actor


def _validate_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise HumanDecisionServiceError("invalid_request", "request must be an object")
    expected = {
        "schema_version",
        "kind",
        "evidence_report",
        "selected_attempt_id",
        "decision",
        "rationale",
    }
    unknown = sorted(set(request) - expected)
    missing = sorted(expected - set(request))
    if missing:
        raise HumanDecisionServiceError(
            "invalid_request", "missing fields: " + ", ".join(missing)
        )
    if unknown:
        raise HumanDecisionServiceError(
            "invalid_request", "unknown fields: " + ", ".join(unknown)
        )
    if request["schema_version"] != SCHEMA_VERSION or request["kind"] != REQUEST_KIND:
        raise HumanDecisionServiceError(
            "invalid_request", "unsupported human-decision request kind/version"
        )
    if request["decision"] not in KNOWN_DECISIONS:
        raise HumanDecisionServiceError(
            "invalid_decision",
            "decision must be one of: " + ", ".join(sorted(KNOWN_DECISIONS)),
        )
    rationale = request["rationale"]
    if not isinstance(rationale, str) or not rationale.strip():
        raise HumanDecisionServiceError(
            "invalid_rationale", "rationale must be a non-empty string"
        )

    evidence = request["evidence_report"]
    if not isinstance(evidence, Mapping) or set(evidence) != {
        "kind", "schema_version", "run_id", "digest"
    }:
        raise HumanDecisionServiceError(
            "invalid_evidence_reference",
            "evidence_report must contain exactly kind, schema_version, run_id, digest",
        )
    if evidence["kind"] != "idkmesh-run-evidence-report" or evidence["schema_version"] != "0.1":
        raise HumanDecisionServiceError(
            "invalid_evidence_reference", "unsupported evidence report kind/version"
        )
    if not isinstance(evidence["run_id"], str) or not evidence["run_id"]:
        raise HumanDecisionServiceError(
            "invalid_evidence_reference", "evidence report run_id must be non-empty"
        )
    if not isinstance(evidence["digest"], str) or _DIGEST_RE.fullmatch(evidence["digest"]) is None:
        raise HumanDecisionServiceError(
            "invalid_evidence_reference", "evidence report digest is invalid"
        )

    selected = request["selected_attempt_id"]
    if selected is not None and (not isinstance(selected, str) or not selected):
        raise HumanDecisionServiceError(
            "invalid_selected_attempt", "selected_attempt_id must be null or non-empty"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REQUEST_KIND,
        "evidence_report": dict(evidence),
        "selected_attempt_id": selected,
        "decision": request["decision"],
        "rationale": rationale,
    }


def _decision_id(idempotency_key: str, request_digest: str) -> str:
    material = {
        "kind": "idkmesh-human-decision-identity",
        "idempotency_key": idempotency_key,
        "request_digest": request_digest,
    }
    digest = canonical_digest(material).removeprefix("sha256:")
    value = f"decision.{digest}"
    if _DECISION_ID_RE.fullmatch(value) is None:  # defensive contract guard
        raise HumanDecisionServiceError("internal_error", "derived decision id is invalid")
    return value


class HumanDecisionService:
    """Validate, bind and immutably persist an authorized human decision."""

    def __init__(
        self,
        *,
        evidence_reader: EvidenceReader,
        store: HumanDecisionStore,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._store = store

    def record(
        self,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
        actor: ActorContext,
        decided_at: str,
        evaluated_at_epoch: int,
    ) -> PersistedHumanDecision:
        caller_key = _require_idempotency_key(idempotency_key)
        if isinstance(evaluated_at_epoch, bool) or not isinstance(evaluated_at_epoch, int) or evaluated_at_epoch < 0:
            raise HumanDecisionServiceError(
                "invalid_evaluation_time", "evaluated_at_epoch must be an integer >= 0"
            )
        trusted_actor = _validate_actor(actor, evaluated_at_epoch=evaluated_at_epoch)
        timestamp = _validate_timestamp(decided_at)
        normalized = _validate_request(request)
        request_digest = canonical_digest(normalized)

        expected = normalized["evidence_report"]
        try:
            retained = self._evidence_reader.get_run_evidence(expected["run_id"])
        except HumanDecisionServiceError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "evidence_unavailable")
            raise HumanDecisionServiceError(code, str(exc)) from exc

        report = retained.get("evidence_report")
        retained_digest = retained.get("evidence_report_digest")
        if not isinstance(report, Mapping) or retained_digest != canonical_digest(report):
            raise HumanDecisionServiceError(
                "evidence_integrity_error",
                "retained evidence is missing or fails its canonical digest check",
            )
        if retained_digest != expected["digest"]:
            raise HumanDecisionServiceError(
                "evidence_mismatch",
                "request is not bound to the exact retained evidence report digest",
            )
        if (
            report.get("kind") != expected["kind"]
            or report.get("schema_version") != expected["schema_version"]
            or report.get("run_id") != expected["run_id"]
        ):
            raise HumanDecisionServiceError(
                "evidence_mismatch",
                "request evidence identity does not match retained evidence",
            )

        selected = normalized["selected_attempt_id"]
        if selected is not None:
            attempts = report.get("attempts")
            if not isinstance(attempts, list) or selected not in {
                item.get("attempt_id")
                for item in attempts
                if isinstance(item, Mapping)
            }:
                raise HumanDecisionServiceError(
                    "selected_attempt_not_found",
                    "selected_attempt_id is not present in the retained evidence report",
                )

        record = {
            "schema_version": SCHEMA_VERSION,
            "kind": RECORD_KIND,
            "decision_id": _decision_id(caller_key, request_digest),
            "evidence_report": dict(expected),
            "selected_attempt_id": selected,
            "decision": normalized["decision"],
            "rationale": normalized["rationale"],
            "decider": {
                "id": trusted_actor.principal_id,
                "type": "human",
            },
            "decided_at": timestamp,
            "authority": dict(_AUTHORITY),
        }
        return self._store.create(
            idempotency_key=caller_key,
            request_digest=request_digest,
            decision_record=record,
        )
