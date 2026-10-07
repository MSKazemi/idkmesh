"""Executor admission: readiness-checked claims with stale-input fences.

This closes the check/use race named by the coordination preflight slice: a
read-only readiness report does not authorize external work. Exact readiness
and authority are revalidated and the claim is acquired in one operation
before any external dispatch intent is retained, and the exact input snapshot
is checked again at canonical candidate submission.

It composes ``LocalTaskClaims`` (atomic admission, deadlines, fencing) with
``DependencyProjection`` (exact-input prerequisite readiness). The execution
binding is derived from the frozen graph and current readiness; callers cannot
supply one. The logical task identity (``ScopedResourceRef``) stays separate
from that execution binding, exactly as the coordination plan requires: a
stable task identity may outlive a rebase, and duplicate work resolves to one
identity through an explicit alias decision, not through a hash.

This library starts/stops no worker, dispatches nothing external, and grants
no verification, acceptance or integration authority.

Single-process boundary: prerequisite observations must be applied through
``ExecutorAdmission.observe()`` for the atomicity guarantee below. Mutating the
projection directly is not prevented, but it is still fail-closed at the
recheck points. This is a local conformance adapter, not a distributed
transaction or an authenticated evidence producer.
"""

from __future__ import annotations

import threading
from typing import Any

from idkmesh.coordination_preflight import DependencyProjection, TaskReadiness
from idkmesh.enterprise_authz import ActorContext
from idkmesh.task_claims import ClaimBinding, LocalTaskClaims, TaskClaim
from idkmesh.tenant_scope import ScopedResourceRef


class ExecutorAdmissionError(RuntimeError):
    """Stable fail-closed admission error with an inspectable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ExecutorAdmission:
    """Local gate tying one ready input snapshot to one registered claim.

    Three phases, each revalidating the exact input snapshot recorded at
    admission:

    1. ``admit``: readiness -> derived binding -> atomic claim (one operation).
    2. ``reserve_execution``: recheck inputs, then retain the UNKNOWN external
       dispatch intent on the existing claim. Replay never renews or retries.
    3. ``submit``: recheck inputs, then fence the candidate digest on the
       existing claim. No verification or acceptance occurs here.

    Owner lifecycle operations (acknowledge, renew, progress, release) and
    trusted execution reconciliation remain on ``LocalTaskClaims``; this gate
    adds no clock or occupancy semantics of its own.
    """

    def __init__(self, projection: DependencyProjection, claims: LocalTaskClaims) -> None:
        if not isinstance(projection, DependencyProjection):
            raise TypeError("projection must be DependencyProjection")
        if not isinstance(claims, LocalTaskClaims):
            raise TypeError("claims must be LocalTaskClaims")
        self.projection = projection
        self.claims = claims
        self._lock = threading.Lock()

    def observe(self, observation: Any) -> bool:
        """Apply one trusted prerequisite observation atomically with admissions."""
        with self._lock:
            return self.projection.observe(observation)

    def _node(self, node: str) -> str:
        if node not in self.projection.graph.bindings:
            raise ExecutorAdmissionError("unknown_work_unit", "task is outside this graph")
        return node

    def _task(self, node: str, task: ScopedResourceRef) -> ScopedResourceRef:
        self._node(node)
        if not isinstance(task, ScopedResourceRef) or task.resource_type != "task":
            raise ExecutorAdmissionError("invalid_input", "task must be a scoped task resource")
        if task.scope != self.projection.graph.scope:
            raise ExecutorAdmissionError(
                "scope_mismatch", "task belongs to another tenant/project")
        return task

    def _binding(self, node: str, state: TaskReadiness) -> ClaimBinding | None:
        if state.inputs_digest is None:
            return None
        binding = self.projection.graph.bindings[node]
        return ClaimBinding(
            work_unit_digest=binding.work_unit_digest,
            source_revision=binding.source_revision,
            inputs_digest=state.inputs_digest,
        )

    def _grant(self, task: ScopedResourceRef, reader: ActorContext, request_id: str) -> TaskClaim:
        for record in self.claims.snapshot(task, reader):
            if record.request_id == request_id:
                return record
        raise ExecutorAdmissionError("claim_not_found", "no claim exists for this request identity")

    def _require_current(self, node: str, state: TaskReadiness, grant: TaskClaim) -> None:
        """Fail closed unless the admission-time input snapshot is still current."""
        if not state.ready:
            raise ExecutorAdmissionError(
                "task_not_ready", "blocked: " + ", ".join(state.blockers))
        derived = self._binding(node, state)
        if (derived.work_unit_digest != grant.binding.work_unit_digest
                or derived.source_revision != grant.binding.source_revision):
            raise ExecutorAdmissionError(
                "binding_mismatch", "claim is bound to a different WorkUnit/source revision")
        if derived.inputs_digest != grant.binding.inputs_digest:
            raise ExecutorAdmissionError(
                "inputs_changed",
                "the exact input snapshot moved since admission; claim a new attempt",
            )

    def admit(
        self, node: str, task: ScopedResourceRef, actor: ActorContext, *, request_id: str,
    ) -> tuple[TaskClaim, dict[str, Any]]:
        """Claim a ready task bound to its exact input snapshot in one operation.

        Exact replay returns the retained grant without renewal or a second
        attempt. Already integrated tasks and blocked tasks are refused before
        any claim record exists.
        """
        self._task(node, task)
        with self._lock:
            state = self.projection.readiness()[node]
            if state.satisfied:
                raise ExecutorAdmissionError(
                    "task_already_integrated",
                    "task has current integrated evidence; no new attempt is admitted",
                )
            if not state.ready:
                raise ExecutorAdmissionError(
                    "task_not_ready", "blocked: " + ", ".join(state.blockers))
            binding = self._binding(node, state)
            grant, created = self.claims.claim(task, actor, request_id=request_id, binding=binding)
            # Direct projection mutation could move inputs inside the call;
            # withdraw the fresh grant rather than leave a stale one holding the slot.
            current = self._binding(node, self.projection.readiness()[node])
            if current is None or current.inputs_digest != binding.inputs_digest:
                if created:
                    self.claims.update_owner(
                        task, actor, request_id=request_id, epoch=grant.epoch,
                        operation="release")
                raise ExecutorAdmissionError(
                    "inputs_changed",
                    "the input snapshot moved during admission; the grant was withdrawn",
                )
            return grant, self._report("admission", node, state, grant, created)

    def reserve_execution(
        self, node: str, task: ScopedResourceRef, dispatcher: ActorContext,
        owner: ActorContext, *, request_id: str, epoch: int,
        approver: ActorContext | None = None, approval_reference: str | None = None,
    ) -> tuple[TaskClaim, dict[str, Any]]:
        """Retain the UNKNOWN external dispatch intent only on current inputs.

        An exact replay returns the retained intent without authorizing a retry.
        A stale input snapshot is refused before any dispatch intent is written.
        """
        self._task(node, task)
        with self._lock:
            state = self.projection.readiness()[node]
            grant = self._grant(task, dispatcher, request_id)
            self._require_current(node, state, grant)
            reserved, created = self.claims.reserve_dispatch(
                task, dispatcher, owner, request_id=request_id,
                epoch=epoch, approver=approver, approval_reference=approval_reference)
            return reserved, self._report("execution-reservation", node, state, reserved, created)

    def submit(
        self, node: str, task: ScopedResourceRef, owner: ActorContext, *,
        request_id: str, epoch: int, artifact_digest: str,
        approver: ActorContext | None = None, approval_reference: str | None = None,
    ) -> tuple[TaskClaim, dict[str, Any]]:
        """Fence a candidate digest only against the admission-time inputs.

        Replaying the same digest is idempotent. Upstream input changes since
        admission are refused here so an old snapshot cannot justify a
        canonical submission; verification and acceptance are separate owners.
        """
        self._task(node, task)
        with self._lock:
            state = self.projection.readiness()[node]
            grant = self._grant(task, owner, request_id)
            self._require_current(node, state, grant)
            created = grant.submission_digest is None
            submitted = self.claims.record_submission(
                task, owner, request_id=request_id, epoch=epoch,
                artifact_digest=artifact_digest, approver=approver,
                approval_reference=approval_reference)
            return submitted, self._report("submission", node, state, submitted, created)

    def _report(
        self, phase: str, node: str, state: TaskReadiness, grant: TaskClaim, created: bool,
    ) -> dict[str, Any]:
        return {
            "kind": "idkmesh-executor-admission",
            "schema_version": "0.1",
            "phase": phase,
            "scope": self.projection.graph.scope.to_dict(),
            "graph_digest": self.projection.graph.digest,
            "observation_digest": self.projection.observation_digest,
            "work_unit_id": node,
            "binding": self.projection.graph.bindings[node].to_dict(),
            "inputs_digest": state.inputs_digest,
            "created": created,
            "claim": grant.to_dict(),
            # The report is metadata. The durable claim record is the
            # admission; neither grants verification, acceptance or merge.
            "authority": {
                "dispatch": False, "executes_worker": False,
                "accepts_candidate": False, "merge": False,
            },
        }
