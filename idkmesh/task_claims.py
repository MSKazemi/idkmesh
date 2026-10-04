"""Local atomic human/agent claims and occupancy-safe recovery (C10-D/E).

All coordinators must share one LocalMetadataStore on supported local storage.
Trusted identity/policy adapters supply authority; issue text cannot do so.
No method starts/stops a worker, verifies an artifact, accepts it, or merges.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import sqlite3
import time
from typing import Any, Callable

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import ScopedResourceRef
from idkmesh.work_unit_binding import canonical_digest


class TaskClaimError(RuntimeError):
    """Stable fail-closed coordination error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _text(value: str, field: str) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > 512
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise TaskClaimError("invalid_input", f"invalid {field}")
    return value


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise TaskClaimError("invalid_input", f"invalid {field}")
    return value


@dataclass(frozen=True, slots=True)
class ClaimBinding:
    work_unit_digest: str
    source_revision: str
    inputs_digest: str

    def __post_init__(self) -> None:
        _digest(self.work_unit_digest, "work_unit_digest")
        _digest(self.inputs_digest, "inputs_digest")
        if (not isinstance(self.source_revision, str)
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", self.source_revision)):
            raise TaskClaimError("invalid_input", "invalid source_revision")


@dataclass(frozen=True, slots=True)
class TaskClaimPolicy:
    """Trusted, immutable per-logical-task limits; durations are seconds.

    Defaults are pilot choices, not a learned optimum. Humans need explicitly
    agreed longer check-ins; policy can permit windows up to seven days.
    """

    concurrent_slots: int = 1
    max_attempts: int = 3
    ack_seconds: int = 300
    lease_seconds: int = 300
    progress_seconds: int = 1800
    hard_seconds: int = 86400
    competition_reason: str | None = None
    risk: str = "low"
    data_classification: str = "public"

    def __post_init__(self) -> None:
        for field, low, high in (
            ("concurrent_slots", 1, 3), ("max_attempts", 1, 32),
            ("ack_seconds", 1, 604800), ("lease_seconds", 1, 604800),
            ("progress_seconds", 1, 604800), ("hard_seconds", 1, 604800),
        ):
            value = getattr(self, field)
            if type(value) is not int or not low <= value <= high:
                raise TaskClaimError("invalid_input", f"{field} must be {low}..{high}")
        if self.max_attempts < self.concurrent_slots:
            raise TaskClaimError("invalid_input", "max_attempts must cover all slots")
        if self.concurrent_slots > 1 and self.competition_reason is None:
            raise TaskClaimError("invalid_input", "competition needs an explicit reason")
        if self.competition_reason is not None:
            _text(self.competition_reason, "competition_reason")
        if not isinstance(self.risk, str) or self.risk not in {"low", "medium", "high", "critical"}:
            raise TaskClaimError("invalid_input", "invalid risk")
        if (not isinstance(self.data_classification, str)
                or self.data_classification not in {"public", "internal", "confidential", "restricted"}):
            raise TaskClaimError("invalid_input", "invalid data_classification")


@dataclass(frozen=True, slots=True)
class TaskClaim:
    task: ScopedResourceRef
    request_id: str
    request_digest: str
    slot: int
    epoch: int
    owner: dict[str, str]
    binding: ClaimBinding
    state: str
    created_at: int
    acknowledged_at: int | None
    ack_by: int
    lease_until: int
    progress_by: int
    hard_until: int
    occupancy: str
    operation_id: str | None
    execution_reference: str | None
    submission_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "idkmesh-task-claim", "schema_version": "0.1",
            "task": self.task.to_dict(), "request_id": self.request_id,
            "request_digest": self.request_digest, "slot": self.slot,
            "epoch": self.epoch, "owner": dict(self.owner),
            "binding": asdict(self.binding), "state": self.state,
            "created_at": self.created_at, "acknowledged_at": self.acknowledged_at,
            "ack_by": self.ack_by, "lease_until": self.lease_until,
            "progress_by": self.progress_by, "hard_until": self.hard_until,
            "occupancy": self.occupancy, "operation_id": self.operation_id,
            "execution_reference": self.execution_reference,
            "submission_digest": self.submission_digest,
            "authority": {"executes_worker": False, "accepts_candidate": False, "merge": False},
        }


def _owner(actor: ActorContext) -> dict[str, str]:
    return {"principal_id": actor.principal_id, "issuer": actor.issuer,
            "actor_type": actor.actor_type}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class _SystemClock:
    def __init__(self) -> None:
        self.wall = int(time.time())
        self.monotonic = time.monotonic()
        self.last_wall = self.wall

    def __call__(self) -> int:
        wall = int(time.time())
        if wall < self.last_wall:
            raise TaskClaimError("clock_rollback", "coordinator wall clock moved backwards")
        self.last_wall = wall
        # A frozen/slow wall clock must not suspend running hard deadlines.
        return max(wall, self.wall + int(time.monotonic() - self.monotonic))


class LocalTaskClaims:
    """Trusted local coordinator adapter, not an authentication boundary.

    The injected clock is for deterministic conformance tests only. Clients
    cannot supply timestamps. Authorization is freshly evaluated inside the
    locked transaction, after waiting for other writers.
    """

    def __init__(
        self, store: LocalMetadataStore, authorization_policy: AuthorizationPolicy,
        *, clock: Callable[[], int] | None = None,
    ) -> None:
        if not isinstance(store, LocalMetadataStore):
            raise TypeError("store must be LocalMetadataStore")
        if not isinstance(authorization_policy, AuthorizationPolicy):
            raise TypeError("authorization_policy must be AuthorizationPolicy")
        self.store = store
        self.authorization_policy = authorization_policy
        self.clock = _SystemClock() if clock is None else clock

    def _now(self, conn: sqlite3.Connection) -> int:
        now = self.clock()
        if type(now) is not int or not 0 <= now < 2**62:
            raise TaskClaimError("invalid_clock", "coordinator clock must return epoch seconds")
        row = conn.execute("SELECT last_epoch FROM task_claim_clock WHERE singleton = 1").fetchone()
        if row is not None and now < row[0]:
            raise TaskClaimError("clock_rollback", "clock precedes persisted coordinator watermark")
        conn.execute(
            "INSERT INTO task_claim_clock VALUES (1, ?) "
            "ON CONFLICT(singleton) DO UPDATE SET last_epoch = excluded.last_epoch", (now,),
        )
        return now

    @staticmethod
    def _task(ref: ScopedResourceRef) -> None:
        if not isinstance(ref, ScopedResourceRef) or ref.resource_type != "task":
            raise TaskClaimError("invalid_input", "task must be a scoped task resource")

    @staticmethod
    def _policy(conn: sqlite3.Connection, ref: ScopedResourceRef) -> TaskClaimPolicy:
        row = conn.execute("SELECT policy_json FROM task_claim_policies WHERE task_key = ?",
                           (ref.storage_key,)).fetchone()
        if row is None:
            raise TaskClaimError("task_not_configured", "logical task has no trusted claim policy")
        try:
            return TaskClaimPolicy(**json.loads(row[0]))
        except (ValueError, TypeError) as exc:
            raise TaskClaimError("corrupt_policy", "stored task policy is invalid") from exc

    def _authorize(
        self, actor: ActorContext, action: str, ref: ScopedResourceRef,
        policy: TaskClaimPolicy, now: int, *, approver: ActorContext | None = None,
        approval_reference: str | None = None,
    ) -> dict[str, Any]:
        decision = authorize(AuthorizationRequest(
            request_id="task-claims:" + action, scope=ref.scope, resource=ref,
            actor=actor, action=action, risk=policy.risk,
            data_classification=policy.data_classification, evaluated_at_epoch=now,
            approver=approver, approval_reference=approval_reference,
        ), self.authorization_policy)
        if decision.effect != "allow":
            raise TaskClaimError(decision.code, decision.message)
        return decision.to_dict()

    @staticmethod
    def _expire(conn: sqlite3.Connection, ref: ScopedResourceRef, now: int) -> None:
        conn.execute(
            "UPDATE task_claims SET state = 'expired' WHERE task_key = ? AND state = 'active' "
            "AND (lease_until <= ? OR progress_by <= ? OR hard_until <= ? "
            "OR (acknowledged_at IS NULL AND ack_by <= ?))",
            (ref.storage_key, now, now, now, now),
        )

    @staticmethod
    def _record(ref: ScopedResourceRef, row: sqlite3.Row) -> TaskClaim:
        return TaskClaim(
            task=ref, request_id=row["request_id"], request_digest=row["request_digest"],
            slot=row["slot"], epoch=row["epoch"], owner=json.loads(row["owner_json"]),
            binding=ClaimBinding(**json.loads(row["binding_json"])), state=row["state"],
            created_at=row["created_at"], acknowledged_at=row["acknowledged_at"],
            ack_by=row["ack_by"], lease_until=row["lease_until"],
            progress_by=row["progress_by"], hard_until=row["hard_until"],
            occupancy=row["occupancy"], operation_id=row["operation_id"],
            execution_reference=row["execution_reference"],
            submission_digest=row["submission_digest"],
        )

    @classmethod
    def _get(cls, conn: sqlite3.Connection, ref: ScopedResourceRef, request_id: str) -> TaskClaim:
        row = conn.execute("SELECT * FROM task_claims WHERE task_key = ? AND request_id = ?",
                           (ref.storage_key, request_id)).fetchone()
        if row is None:
            raise TaskClaimError("claim_not_found", "no such claim in this scope")
        return cls._record(ref, row)

    @staticmethod
    def _current(conn: sqlite3.Connection, grant: TaskClaim, actor: ActorContext, epoch: int) -> None:
        if type(epoch) is not int or epoch != grant.epoch:
            raise TaskClaimError("stale_claim", "claim epoch does not match")
        if grant.owner != _owner(actor):
            raise TaskClaimError("claim_owner_denied", "only the recorded owner can use this grant")
        row = conn.execute("SELECT epoch FROM task_claim_slots WHERE task_key = ? AND slot = ?",
                           (grant.task.storage_key, grant.slot)).fetchone()
        if grant.state != "active" or row is None or row[0] != epoch:
            raise TaskClaimError("stale_claim", "grant expired, released or was superseded")

    def configure_task(
        self, task: ScopedResourceRef, actor: ActorContext, policy: TaskClaimPolicy,
        *, approver: ActorContext | None = None, approval_reference: str | None = None,
    ) -> bool:
        """Freeze task limits under dispatch authority; exact replay is harmless."""
        self._task(task)
        if not isinstance(policy, TaskClaimPolicy):
            raise TypeError("policy must be TaskClaimPolicy")
        payload = _json(asdict(policy))
        with self.store.transaction() as conn:
            now = self._now(conn)
            existing = conn.execute("SELECT policy_json FROM task_claim_policies WHERE task_key = ?",
                                    (task.storage_key,)).fetchone()
            # Evaluate existing risk/clearance first, preventing downgrade probes.
            effective = self._policy(conn, task) if existing is not None else policy
            self._authorize(actor, "dispatch", task, effective, now,
                            approver=approver, approval_reference=approval_reference)
            if existing is not None:
                if existing[0] != payload:
                    raise TaskClaimError("task_policy_conflict", "task policy is immutable")
                return False
            conn.execute("INSERT INTO task_claim_policies VALUES (?, ?)", (task.storage_key, payload))
            conn.executemany("INSERT INTO task_claim_slots VALUES (?, ?, 0)",
                             ((task.storage_key, slot) for slot in range(policy.concurrent_slots)))
            return True

    def claim(
        self, task: ScopedResourceRef, actor: ActorContext, *, request_id: str,
        binding: ClaimBinding,
    ) -> tuple[TaskClaim, bool]:
        """Return (grant, created); an exact replay NEVER renews or re-dispatches."""
        self._task(task)
        _text(request_id, "request_id")
        if not isinstance(binding, ClaimBinding):
            raise TypeError("binding must be ClaimBinding")
        with self.store.transaction() as conn:
            now = self._now(conn)
            policy = self._policy(conn, task)
            authorization = self._authorize(actor, "claim", task, policy, now)
            digest = canonical_digest({"task": task.to_dict(), "owner": _owner(actor),
                                       "binding": asdict(binding), "policy": asdict(policy)})
            self._expire(conn, task, now)
            old = conn.execute("SELECT * FROM task_claims WHERE task_key = ? AND request_id = ?",
                               (task.storage_key, request_id)).fetchone()
            if old is not None:
                if old["request_digest"] != digest:
                    raise TaskClaimError("request_conflict", "request identity has different content")
                return self._record(task, old), False
            count = conn.execute("SELECT COUNT(*) FROM task_claims WHERE task_key = ?",
                                 (task.storage_key,)).fetchone()[0]
            if count >= policy.max_attempts:
                raise TaskClaimError("attempt_budget_exhausted", "logical task lifetime budget exhausted")
            # A revoked writer may still occupy its slot through remote execution.
            slot = conn.execute(
                "SELECT s.slot, s.epoch FROM task_claim_slots s WHERE s.task_key = ? "
                "AND NOT EXISTS (SELECT 1 FROM task_claims c WHERE c.task_key = s.task_key "
                "AND c.slot = s.slot AND (c.state = 'active' OR c.occupancy IN ('unknown', 'running'))) "
                "ORDER BY s.slot LIMIT 1", (task.storage_key,),
            ).fetchone()
            if slot is None:
                raise TaskClaimError("task_capacity_reserved", "all logical task slots remain reserved")
            epoch = slot["epoch"] + 1
            conn.execute("UPDATE task_claim_slots SET epoch = ? WHERE task_key = ? AND slot = ?",
                         (epoch, task.storage_key, slot["slot"]))
            hard = now + policy.hard_seconds
            conn.execute(
                "INSERT INTO task_claims (task_key, request_id, request_digest, slot, epoch, "
                "owner_json, binding_json, authorization_json, state, created_at, ack_by, "
                "lease_until, progress_by, hard_until, occupancy) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, 'none')",
                (task.storage_key, request_id, digest, slot["slot"], epoch,
                 _json(_owner(actor)), _json(asdict(binding)), _json(authorization), now,
                 min(hard, now + policy.ack_seconds), min(hard, now + policy.lease_seconds),
                 min(hard, now + policy.progress_seconds), hard),
            )
            return self._get(conn, task, request_id), True

    def snapshot(self, task: ScopedResourceRef, actor: ActorContext) -> tuple[TaskClaim, ...]:
        """Return bounded history after recording deadline expiry."""
        self._task(task)
        with self.store.transaction() as conn:
            now = self._now(conn)
            self._authorize(actor, "read", task, self._policy(conn, task), now)
            self._expire(conn, task, now)
            rows = conn.execute("SELECT * FROM task_claims WHERE task_key = ? ORDER BY created_at, slot, epoch",
                                (task.storage_key,)).fetchall()
            return tuple(self._record(task, row) for row in rows)

    def update_owner(
        self, task: ScopedResourceRef, actor: ActorContext, *, request_id: str,
        epoch: int, operation: str,
    ) -> TaskClaim:
        """Acknowledge, renew liveness, report progress or release the current grant."""
        self._task(task)
        _text(request_id, "request_id")
        if not isinstance(operation, str) or operation not in {"acknowledge", "renew", "progress", "release"}:
            raise TaskClaimError("invalid_input", "invalid owner operation")
        with self.store.transaction() as conn:
            now = self._now(conn)
            policy = self._policy(conn, task)
            self._authorize(actor, "release" if operation == "release" else "claim", task, policy, now)
            self._expire(conn, task, now)
            grant = self._get(conn, task, request_id)
            self._current(conn, grant, actor, epoch)
            if operation == "acknowledge":
                field, value = "acknowledged_at", grant.acknowledged_at if grant.acknowledged_at is not None else now
            elif operation == "release":
                field, value = "state", "released"
            else:
                if grant.acknowledged_at is None:
                    raise TaskClaimError("acknowledgement_required", "acknowledge before updating deadlines")
                field = "lease_until" if operation == "renew" else "progress_by"
                seconds = policy.lease_seconds if operation == "renew" else policy.progress_seconds
                value = min(grant.hard_until, now + seconds)
            # field comes solely from the finite internal operation vocabulary.
            conn.execute(f"UPDATE task_claims SET {field} = ? WHERE task_key = ? AND request_id = ?",
                         (value, task.storage_key, request_id))
            return self._get(conn, task, request_id)

    def reserve_dispatch(
        self, task: ScopedResourceRef, dispatcher: ActorContext, owner: ActorContext,
        *, request_id: str, epoch: int, approver: ActorContext | None = None,
        approval_reference: str | None = None,
    ) -> tuple[TaskClaim, bool]:
        """Retain an UNKNOWN external-create intent; replay never authorizes a retry.

        A later executor must additionally enforce readiness, SCM, sandbox,
        connector, provider, CI, donor and zero-spend admission. This library
        does not claim to supply those checks or exactly-once provider effects.
        """
        self._task(task)
        _text(request_id, "request_id")
        with self.store.transaction() as conn:
            now = self._now(conn)
            policy = self._policy(conn, task)
            for actor, action in ((dispatcher, "dispatch"), (owner, "execute")):
                self._authorize(actor, action, task, policy, now,
                                approver=approver, approval_reference=approval_reference)
            self._expire(conn, task, now)
            grant = self._get(conn, task, request_id)
            if grant.operation_id is not None and type(epoch) is int and epoch == grant.epoch \
                    and grant.owner == _owner(owner):
                # Retained intent: replay stays readable after expiry; it never authorizes a retry.
                return grant, False
            self._current(conn, grant, owner, epoch)
            if grant.acknowledged_at is None:
                raise TaskClaimError("acknowledgement_required", "owner has not acknowledged")
            operation_id = canonical_digest({"task": task.storage_key, "slot": grant.slot,
                                             "epoch": grant.epoch, "binding": asdict(grant.binding)})
            conn.execute("UPDATE task_claims SET occupancy = 'unknown', operation_id = ? "
                         "WHERE task_key = ? AND request_id = ?",
                         (operation_id, task.storage_key, request_id))
            return self._get(conn, task, request_id), True

    def reconcile_execution(
        self, task: ScopedResourceRef, dispatcher: ActorContext, *, request_id: str,
        epoch: int, status: str, evidence_reference: str,
        approver: ActorContext | None = None, approval_reference: str | None = None,
    ) -> TaskClaim:
        """Trusted adapter evidence may confirm RUNNING or TERMINAL, even after expiry.

        Terminal includes conclusively not-created/stopped. Cancellation requests
        and timeouts are insufficient. Terminal is absorbing, so late events
        cannot resurrect an old reservation.
        """
        self._task(task)
        _text(request_id, "request_id")
        if not isinstance(status, str) or status not in {"running", "terminal"}:
            raise TaskClaimError("invalid_input", "reconciliation must confirm running or terminal")
        _text(evidence_reference, "evidence_reference")
        with self.store.transaction() as conn:
            now = self._now(conn)
            self._authorize(dispatcher, "dispatch", task, self._policy(conn, task), now,
                            approver=approver, approval_reference=approval_reference)
            self._expire(conn, task, now)
            grant = self._get(conn, task, request_id)
            if type(epoch) is not int or grant.epoch != epoch:
                raise TaskClaimError("stale_claim", "historical grant epoch does not match")
            if grant.operation_id is None:
                raise TaskClaimError("dispatch_intent_required", "no external execution was reserved")
            if grant.occupancy == "terminal":
                if status != "terminal" or evidence_reference != grant.execution_reference:
                    raise TaskClaimError("terminal_execution_conflict", "terminal evidence is immutable")
                return grant
            conn.execute("UPDATE task_claims SET occupancy = ?, execution_reference = ? "
                         "WHERE task_key = ? AND request_id = ?",
                         (status, evidence_reference, task.storage_key, request_id))
            return self._get(conn, task, request_id)

    def record_submission(
        self, task: ScopedResourceRef, actor: ActorContext, *, request_id: str,
        epoch: int, artifact_digest: str, approver: ActorContext | None = None,
        approval_reference: str | None = None,
    ) -> TaskClaim:
        """Atomically fence a worker's candidate digest; no verification/acceptance."""
        self._task(task)
        _text(request_id, "request_id")
        _digest(artifact_digest, "artifact_digest")
        with self.store.transaction() as conn:
            now = self._now(conn)
            self._authorize(actor, "execute", task, self._policy(conn, task), now,
                            approver=approver, approval_reference=approval_reference)
            self._expire(conn, task, now)
            grant = self._get(conn, task, request_id)
            self._current(conn, grant, actor, epoch)
            if grant.acknowledged_at is None:
                raise TaskClaimError("acknowledgement_required", "owner has not acknowledged")
            if grant.submission_digest not in {None, artifact_digest}:
                raise TaskClaimError("submission_conflict", "candidate digest is already bound")
            conn.execute("UPDATE task_claims SET submission_digest = ? WHERE task_key = ? AND request_id = ?",
                         (artifact_digest, task.storage_key, request_id))
            return self._get(conn, task, request_id)
