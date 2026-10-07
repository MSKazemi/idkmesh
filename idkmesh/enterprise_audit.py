"""Tamper-evident enterprise audit ledger for E4 (#671).

This module is deliberately separate from ordinary logs and the Product Spine
lifecycle event stream. It records compact, fixed-shape security/audit evidence
derived from already-normalized enterprise identity and authorization objects.

The ledger is evidence only. Appending or exporting an audit event does not
authorize, execute, accept, integrate, push, or merge anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Callable, Mapping, Protocol, TextIO

from idkmesh.enterprise_authz import (
    ACTOR_TYPES,
    EFFECTS,
    ActorContext,
    AuthorizationDecision,
)
from idkmesh.tenant_scope import TenantScope


AUDIT_VERSION = "0.1"
AUDIT_KIND = "idkmesh-enterprise-audit-event"
SCHEMA_VERSION = 1
SERVICE_ACTOR_TYPES = frozenset(
    {"github_app", "github_actions", "service", "node"}
)
OUTCOMES = frozenset({"succeeded", "failed", "denied", "not_executed"})
RETENTION_STATES = frozenset(
    {"retain", "eligible_for_expiry", "legal_hold"}
)

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_REVISION_RE = re.compile(
    r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64}|"
    r"[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255})$"
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVENT_ID_RE = re.compile(r"^audit-[0-9]{12}$")


class EnterpriseAuditError(ValueError):
    """Stable fail-closed audit contract/store error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str) -> EnterpriseAuditError:
    return EnterpriseAuditError(code, message)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_digest(value: Any) -> str:
    payload = _canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise _fail(
            "invalid_identifier",
            f"{field} must be 1-256 safe identifier characters",
        )
    return value


def _revision(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _REVISION_RE.fullmatch(value):
        raise _fail(
            "invalid_revision",
            f"{field} must be an immutable revision/digest identifier",
        )
    return value


def _digest(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise _fail("invalid_digest", f"{field} must be sha256:<64 lowercase hex>")
    return value


def _epoch(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("invalid_epoch", f"{field} must be an integer >= 0")
    return value


def _retention_days(value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= 36500
    ):
        raise _fail(
            "invalid_retention",
            "retention_days must be an integer between 1 and 36500",
        )
    return value


def _strict_object(
    value: Any,
    *,
    fields: frozenset[str],
    field: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("invalid_event", f"{field} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing:
        raise _fail(
            "invalid_event",
            f"{field} missing fields: {', '.join(sorted(missing))}",
        )
    if unknown:
        raise _fail(
            "invalid_event",
            f"{field} has unknown fields: {', '.join(sorted(unknown))}",
        )
    return value


def _strict_json(text: str) -> dict[str, Any]:
    def reject_constant(token: str) -> Any:
        raise _fail("invalid_event_json", f"non-finite JSON value {token!r}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _fail("invalid_event_json", f"duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise _fail("invalid_event_json", str(exc)) from exc
    if not isinstance(value, dict):
        raise _fail("invalid_event_json", "audit event must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class AuditEventInput:
    """One privileged operation outcome before sequence/hash assignment."""

    occurred_at_epoch: int
    actor: ActorContext
    service: ActorContext
    decision: AuthorizationDecision
    resource_revision: str
    outcome: str
    run_id: str | None = None
    evidence_digest: str | None = None
    retention_days: int = 365

    def __post_init__(self) -> None:
        _epoch(self.occurred_at_epoch, "occurred_at_epoch")
        if not isinstance(self.actor, ActorContext):
            raise _fail("invalid_actor", "actor must be ActorContext")
        if not isinstance(self.service, ActorContext):
            raise _fail("invalid_service", "service must be ActorContext")
        if not isinstance(self.decision, AuthorizationDecision):
            raise _fail("invalid_decision", "decision must be AuthorizationDecision")

        if self.service.actor_type not in SERVICE_ACTOR_TYPES:
            raise _fail(
                "invalid_service",
                "service actor_type must be github_app, github_actions, service, or node",
            )
        if not self.service.authenticated or self.service.revoked:
            raise _fail(
                "invalid_service",
                "audit writer service identity must be authenticated and not revoked",
            )
        if (
            self.service.expires_at_epoch is not None
            and self.occurred_at_epoch >= self.service.expires_at_epoch
        ):
            raise _fail(
                "invalid_service",
                "audit writer service identity is expired",
            )

        if self.decision.principal_id != self.actor.principal_id:
            raise _fail(
                "actor_decision_mismatch",
                "decision principal does not match actor principal",
            )
        if self.decision.identity_revision != self.actor.identity_revision:
            raise _fail(
                "actor_decision_mismatch",
                "decision identity revision does not match actor",
            )
        if self.occurred_at_epoch < self.decision.evaluated_at_epoch:
            raise _fail(
                "invalid_timestamp",
                "audit event cannot occur before its authorization decision",
            )

        scope = TenantScope(
            self.decision.tenant_id,
            self.decision.project_id,
        )
        # The actor may legitimately be *outside* this scope: denied cross-tenant
        # attempts are exactly the kind of event an enterprise audit trail must
        # retain. Only the trusted service that writes the event must be bound
        # to the target scope.
        if not self.service.is_bound_to(scope):
            raise _fail(
                "service_scope_mismatch",
                "service is not bound to the decision tenant/project scope",
            )

        _revision(self.resource_revision, "resource_revision")
        if self.run_id is not None:
            _identifier(self.run_id, "run_id")
        _digest(self.evidence_digest, "evidence_digest", nullable=True)
        _retention_days(self.retention_days)

        if self.outcome not in OUTCOMES:
            raise _fail(
                "invalid_outcome",
                "outcome must be succeeded, failed, denied, or not_executed",
            )
        if self.decision.effect == "deny" and self.outcome not in {
            "denied",
            "not_executed",
        }:
            raise _fail(
                "outcome_decision_mismatch",
                "a denied authorization cannot record executed success/failure",
            )
        if (
            self.decision.effect == "requires_approval"
            and self.outcome != "not_executed"
        ):
            raise _fail(
                "outcome_decision_mismatch",
                "requires_approval must remain not_executed",
            )
        if self.decision.effect == "allow" and self.outcome == "denied":
            raise _fail(
                "outcome_decision_mismatch",
                "an allow decision cannot use the denied outcome",
            )


@dataclass(frozen=True, slots=True)
class AuditCheckpoint:
    event_count: int
    head_sequence: int
    head_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "head_sequence": self.head_sequence,
            "head_digest": self.head_digest,
        }


@dataclass(frozen=True, slots=True)
class AuditVerification:
    ok: bool
    event_count: int
    head_sequence: int
    head_digest: str | None
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "event_count": self.event_count,
            "head_sequence": self.head_sequence,
            "head_digest": self.head_digest,
            "errors": list(self.errors),
            "authority": {
                "authorizes_action": False,
                "canonical_state_write": False,
                "merge": False,
            },
        }


@dataclass(frozen=True, slots=True)
class AuditExportReceipt:
    exported_count: int
    first_sequence: int | None
    last_sequence: int | None
    last_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exported_count": self.exported_count,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "last_digest": self.last_digest,
        }


class AuditExportSink(Protocol):
    """Vendor-neutral sink boundary for SIEM/archive adapters."""

    def write_event(self, event: Mapping[str, Any]) -> None:
        """Write one already-validated canonical audit event."""


class JsonLinesAuditSink:
    """Deterministic NDJSON sink suitable for files/forwarders/SIEM shippers."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write_event(self, event: Mapping[str, Any]) -> None:
        self._stream.write(_canonical_json(dict(event)))
        self._stream.write("\n")


_ROOT_FIELDS = frozenset(
    {
        "kind",
        "schema_version",
        "event_id",
        "sequence",
        "occurred_at_epoch",
        "scope",
        "correlation",
        "actor",
        "service",
        "action",
        "resource",
        "authorization",
        "outcome",
        "evidence_digest",
        "retention",
        "previous_event_digest",
        "event_digest",
        "authority",
    }
)
_SCOPE_FIELDS = frozenset({"tenant_id", "project_id"})
_CORRELATION_FIELDS = frozenset({"request_id", "run_id"})
_IDENTITY_FIELDS = frozenset(
    {"principal_id", "actor_type", "issuer", "identity_revision"}
)
_RESOURCE_FIELDS = frozenset({"resource_type", "resource_id", "revision"})
_AUTHZ_FIELDS = frozenset(
    {
        "effect",
        "reason_code",
        "approved_by",
        "approval_reference",
        "policy_id",
        "policy_revision",
        "decision_digest",
    }
)
_RETENTION_FIELDS = frozenset(
    {"minimum_days", "eligible_after_epoch"}
)
_AUTHORITY_FIELDS = frozenset(
    {
        "audit_only",
        "authorizes_action",
        "canonical_state_write",
        "git_push",
        "merge",
    }
)


def validate_audit_event(event: Any) -> None:
    root = _strict_object(event, fields=_ROOT_FIELDS, field="$")
    if root["kind"] != AUDIT_KIND or root["schema_version"] != AUDIT_VERSION:
        raise _fail("invalid_event", "unsupported audit kind/schema version")

    sequence = root["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise _fail("invalid_event", "sequence must be an integer >= 1")
    event_id = root["event_id"]
    if not isinstance(event_id, str) or not _EVENT_ID_RE.fullmatch(event_id):
        raise _fail("invalid_event", "event_id is invalid")
    if event_id != f"audit-{sequence:012d}":
        raise _fail("invalid_event", "event_id does not match sequence")

    occurred = _epoch(root["occurred_at_epoch"], "occurred_at_epoch")
    scope = _strict_object(
        root["scope"], fields=_SCOPE_FIELDS, field="scope"
    )
    _identifier(scope["tenant_id"], "scope.tenant_id")
    _identifier(scope["project_id"], "scope.project_id")

    correlation = _strict_object(
        root["correlation"],
        fields=_CORRELATION_FIELDS,
        field="correlation",
    )
    _identifier(correlation["request_id"], "correlation.request_id")
    if correlation["run_id"] is not None:
        _identifier(correlation["run_id"], "correlation.run_id")

    for name in ("actor", "service"):
        identity = _strict_object(
            root[name],
            fields=_IDENTITY_FIELDS,
            field=name,
        )
        _identifier(identity["principal_id"], f"{name}.principal_id")
        if identity["actor_type"] not in ACTOR_TYPES:
            raise _fail("invalid_event", f"{name}.actor_type is invalid")
        if name == "service" and identity["actor_type"] not in SERVICE_ACTOR_TYPES:
            raise _fail("invalid_event", "service.actor_type is not a service type")
        _identifier(identity["issuer"], f"{name}.issuer")
        _identifier(
            identity["identity_revision"],
            f"{name}.identity_revision",
        )

    _identifier(root["action"], "action")
    resource = _strict_object(
        root["resource"],
        fields=_RESOURCE_FIELDS,
        field="resource",
    )
    _identifier(resource["resource_type"], "resource.resource_type")
    _identifier(resource["resource_id"], "resource.resource_id")
    _revision(resource["revision"], "resource.revision")

    authorization = _strict_object(
        root["authorization"],
        fields=_AUTHZ_FIELDS,
        field="authorization",
    )
    if authorization["effect"] not in EFFECTS:
        raise _fail("invalid_event", "authorization.effect is invalid")
    _identifier(authorization["reason_code"], "authorization.reason_code")
    if authorization["approved_by"] is not None:
        _identifier(authorization["approved_by"], "authorization.approved_by")
    if authorization["approval_reference"] is not None:
        _identifier(
            authorization["approval_reference"],
            "authorization.approval_reference",
        )
    _identifier(authorization["policy_id"], "authorization.policy_id")
    _identifier(
        authorization["policy_revision"],
        "authorization.policy_revision",
    )
    _digest(
        authorization["decision_digest"],
        "authorization.decision_digest",
    )

    if root["outcome"] not in OUTCOMES:
        raise _fail("invalid_event", "outcome is invalid")
    _digest(root["evidence_digest"], "evidence_digest", nullable=True)

    retention = _strict_object(
        root["retention"],
        fields=_RETENTION_FIELDS,
        field="retention",
    )
    days = _retention_days(retention["minimum_days"])
    eligible = _epoch(
        retention["eligible_after_epoch"],
        "retention.eligible_after_epoch",
    )
    if eligible != occurred + days * 86400:
        raise _fail(
            "invalid_event",
            "retention.eligible_after_epoch does not match minimum_days",
        )

    _digest(
        root["previous_event_digest"],
        "previous_event_digest",
        nullable=True,
    )
    _digest(root["event_digest"], "event_digest")

    authority = _strict_object(
        root["authority"],
        fields=_AUTHORITY_FIELDS,
        field="authority",
    )
    expected_authority = {
        "audit_only": True,
        "authorizes_action": False,
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
    }
    if dict(authority) != expected_authority:
        raise _fail("invalid_event", "audit authority ceiling is invalid")


def _event_from_input(
    item: AuditEventInput,
    *,
    sequence: int,
    previous_event_digest: str | None,
) -> dict[str, Any]:
    decision = item.decision
    body: dict[str, Any] = {
        "kind": AUDIT_KIND,
        "schema_version": AUDIT_VERSION,
        "event_id": f"audit-{sequence:012d}",
        "sequence": sequence,
        "occurred_at_epoch": item.occurred_at_epoch,
        "scope": {
            "tenant_id": decision.tenant_id,
            "project_id": decision.project_id,
        },
        "correlation": {
            "request_id": decision.request_id,
            "run_id": item.run_id,
        },
        "actor": {
            "principal_id": item.actor.principal_id,
            "actor_type": item.actor.actor_type,
            "issuer": item.actor.issuer,
            "identity_revision": item.actor.identity_revision,
        },
        "service": {
            "principal_id": item.service.principal_id,
            "actor_type": item.service.actor_type,
            "issuer": item.service.issuer,
            "identity_revision": item.service.identity_revision,
        },
        "action": decision.action,
        "resource": {
            "resource_type": decision.resource_type,
            "resource_id": decision.resource_id,
            "revision": item.resource_revision,
        },
        "authorization": {
            "effect": decision.effect,
            "reason_code": decision.code,
            "approved_by": decision.approved_by,
            "approval_reference": decision.approval_reference,
            "policy_id": decision.policy_id,
            "policy_revision": decision.policy_revision,
            "decision_digest": canonical_digest(decision.to_dict()),
        },
        "outcome": item.outcome,
        "evidence_digest": item.evidence_digest,
        "retention": {
            "minimum_days": item.retention_days,
            "eligible_after_epoch": (
                item.occurred_at_epoch + item.retention_days * 86400
            ),
        },
        "previous_event_digest": previous_event_digest,
        "authority": {
            "audit_only": True,
            "authorizes_action": False,
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        },
    }
    body["event_digest"] = canonical_digest(body)
    validate_audit_event(body)
    return body


class LocalEnterpriseAuditLedger:
    """Small SQLite append-only audit ledger with hash-chain verification."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        try:
            self._conn = sqlite3.connect(
                self.path,
                timeout=5.0,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            self._initialize()
        except sqlite3.Error as exc:
            raise _fail("audit_store_error", str(exc)) from exc

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "LocalEnterpriseAuditLedger":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _initialize(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise _fail(
                "unsupported_audit_store_version",
                f"store version {version} is newer than supported {SCHEMA_VERSION}",
            )
        if version == 0:
            self._conn.executescript(
                """
                CREATE TABLE enterprise_audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    occurred_at_epoch INTEGER NOT NULL,
                    previous_event_digest TEXT,
                    event_digest TEXT NOT NULL UNIQUE,
                    event_json TEXT NOT NULL
                );

                CREATE INDEX enterprise_audit_scope_idx
                    ON enterprise_audit_events(
                        tenant_id, project_id, sequence
                    );

                CREATE TRIGGER enterprise_audit_no_update
                BEFORE UPDATE ON enterprise_audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'enterprise audit ledger is append-only');
                END;

                CREATE TRIGGER enterprise_audit_no_delete
                BEFORE DELETE ON enterprise_audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'enterprise audit ledger is append-only');
                END;

                PRAGMA user_version = 1;
                """
            )
            self._conn.commit()
            return

        table = self._conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'enterprise_audit_events'
            """
        ).fetchone()
        if table is None:
            raise _fail(
                "corrupt_audit_store",
                "schema version is set but enterprise_audit_events is missing",
            )

    def append(self, item: AuditEventInput) -> dict[str, Any]:
        if not isinstance(item, AuditEventInput):
            raise _fail("invalid_input", "append requires AuditEventInput")

        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    """
                    SELECT sequence, event_digest
                    FROM enterprise_audit_events
                    ORDER BY sequence DESC
                    LIMIT 1
                    """
                ).fetchone()
                previous_sequence = 0 if row is None else int(row["sequence"])
                previous_digest = None if row is None else str(row["event_digest"])
                sequence = previous_sequence + 1
                event = _event_from_input(
                    item,
                    sequence=sequence,
                    previous_event_digest=previous_digest,
                )
                self._conn.execute(
                    """
                    INSERT INTO enterprise_audit_events(
                        sequence,
                        event_id,
                        tenant_id,
                        project_id,
                        occurred_at_epoch,
                        previous_event_digest,
                        event_digest,
                        event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sequence,
                        event["event_id"],
                        event["scope"]["tenant_id"],
                        event["scope"]["project_id"],
                        event["occurred_at_epoch"],
                        event["previous_event_digest"],
                        event["event_digest"],
                        _canonical_json(event),
                    ),
                )
                self._conn.commit()
                return event
            except EnterpriseAuditError:
                self._conn.rollback()
                raise
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise _fail("audit_store_error", str(exc)) from exc

    def _event_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        event = _strict_json(str(row["event_json"]))
        validate_audit_event(event)
        if event["sequence"] != int(row["sequence"]):
            raise _fail("corrupt_audit_store", "row/event sequence mismatch")
        if event["event_id"] != str(row["event_id"]):
            raise _fail("corrupt_audit_store", "row/event id mismatch")
        if event["event_digest"] != str(row["event_digest"]):
            raise _fail("corrupt_audit_store", "row/event digest mismatch")
        if event["previous_event_digest"] != row["previous_event_digest"]:
            raise _fail(
                "corrupt_audit_store",
                "row/event previous digest mismatch",
            )
        return event

    def list_events(
        self,
        *,
        after_sequence: int = 0,
        tenant_id: str,
        limit: int = 200,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence < 0
        ):
            raise _fail(
                "invalid_after_sequence",
                "after_sequence must be an integer >= 0",
            )
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise _fail("invalid_limit", "limit must be between 1 and 1000")
        _identifier(tenant_id, "tenant_id")
        if project_id is not None:
            _identifier(project_id, "project_id")

        clauses = ["sequence > ?", "tenant_id = ?"]
        params: list[Any] = [after_sequence, tenant_id]
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        params.append(limit)

        with self._lock:
            try:
                rows = self._conn.execute(
                    """
                    SELECT
                        sequence,
                        event_id,
                        previous_event_digest,
                        event_digest,
                        event_json
                    FROM enterprise_audit_events
                    WHERE """
                    + " AND ".join(clauses)
                    + " ORDER BY sequence ASC LIMIT ?",
                    tuple(params),
                ).fetchall()
            except sqlite3.Error as exc:
                raise _fail("audit_store_error", str(exc)) from exc
        return [self._event_from_row(row) for row in rows]

    def verify(
        self,
        *,
        expected_checkpoint: AuditCheckpoint | None = None,
    ) -> AuditVerification:
        with self._lock:
            try:
                rows = self._conn.execute(
                    """
                    SELECT
                        sequence,
                        event_id,
                        previous_event_digest,
                        event_digest,
                        event_json
                    FROM enterprise_audit_events
                    ORDER BY sequence ASC
                    """
                ).fetchall()
            except sqlite3.Error as exc:
                raise _fail("audit_store_error", str(exc)) from exc

        errors: list[str] = []
        previous_digest: str | None = None
        expected_sequence = 1
        head_sequence = 0
        head_digest: str | None = None

        for row in rows:
            sequence = int(row["sequence"])
            head_sequence = sequence
            head_digest = str(row["event_digest"])
            if sequence != expected_sequence:
                errors.append(
                    f"sequence_gap:expected={expected_sequence}:actual={sequence}"
                )
                expected_sequence = sequence
            expected_sequence += 1

            try:
                event = _strict_json(str(row["event_json"]))
                validate_audit_event(event)
            except EnterpriseAuditError as exc:
                errors.append(f"event_invalid:{sequence}:{exc.code}")
                previous_digest = str(row["event_digest"])
                continue

            if event["sequence"] != sequence:
                errors.append(f"row_sequence_mismatch:{sequence}")
            if event["event_id"] != str(row["event_id"]):
                errors.append(f"row_event_id_mismatch:{sequence}")
            if event["previous_event_digest"] != row["previous_event_digest"]:
                errors.append(f"row_previous_digest_mismatch:{sequence}")
            if event["event_digest"] != str(row["event_digest"]):
                errors.append(f"row_event_digest_mismatch:{sequence}")
            if event["previous_event_digest"] != previous_digest:
                errors.append(f"chain_link_mismatch:{sequence}")

            body = dict(event)
            stored_digest = body.pop("event_digest")
            computed = canonical_digest(body)
            if stored_digest != computed:
                errors.append(f"event_digest_mismatch:{sequence}")
            previous_digest = stored_digest

        if expected_checkpoint is not None:
            if not isinstance(expected_checkpoint, AuditCheckpoint):
                raise _fail(
                    "invalid_checkpoint",
                    "expected_checkpoint must be AuditCheckpoint",
                )
            if len(rows) != expected_checkpoint.event_count:
                errors.append(
                    "checkpoint_event_count_mismatch:"
                    f"expected={expected_checkpoint.event_count}:actual={len(rows)}"
                )
            if head_sequence != expected_checkpoint.head_sequence:
                errors.append(
                    "checkpoint_head_sequence_mismatch:"
                    f"expected={expected_checkpoint.head_sequence}:actual={head_sequence}"
                )
            if head_digest != expected_checkpoint.head_digest:
                errors.append("checkpoint_head_digest_mismatch")

        return AuditVerification(
            ok=not errors,
            event_count=len(rows),
            head_sequence=head_sequence,
            head_digest=head_digest,
            errors=tuple(errors),
        )

    def checkpoint(self) -> AuditCheckpoint:
        verification = self.verify()
        if not verification.ok:
            raise _fail(
                "audit_integrity_failure",
                "; ".join(verification.errors),
            )
        return AuditCheckpoint(
            event_count=verification.event_count,
            head_sequence=verification.head_sequence,
            head_digest=verification.head_digest,
        )

    def export_to_sink(
        self,
        sink: AuditExportSink,
        *,
        tenant_id: str,
        after_sequence: int = 0,
        limit: int = 1000,
        project_id: str | None = None,
    ) -> AuditExportReceipt:
        events = self.list_events(
            tenant_id=tenant_id,
            after_sequence=after_sequence,
            limit=limit,
            project_id=project_id,
        )
        for event in events:
            sink.write_event(event)

        if not events:
            return AuditExportReceipt(0, None, None, None)
        return AuditExportReceipt(
            exported_count=len(events),
            first_sequence=events[0]["sequence"],
            last_sequence=events[-1]["sequence"],
            last_digest=events[-1]["event_digest"],
        )


def retention_state(
    event: Mapping[str, Any],
    *,
    now_epoch: int,
    legal_hold_hook: Callable[[Mapping[str, Any]], bool] | None = None,
) -> str:
    """Return retention disposition without mutating or deleting the ledger.

    A legal-hold system can supply a hook backed by its own governed state.
    This module intentionally exposes no deletion API.
    """

    validate_audit_event(event)
    now = _epoch(now_epoch, "now_epoch")
    if legal_hold_hook is not None and bool(legal_hold_hook(event)):
        return "legal_hold"
    if now >= int(event["retention"]["eligible_after_epoch"]):
        return "eligible_for_expiry"
    return "retain"
