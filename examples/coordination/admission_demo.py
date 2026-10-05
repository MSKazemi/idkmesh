"""Reproduce readiness-checked admission, dispatch reservation and stale-input refusal.

Synthetic identities and observations only. No network, credentials, worker
execution, provider call, verification or integration occurs.
"""

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.coordination_preflight import (
    DependencyGraph, DependencyProjection, PrerequisiteObservation,
)
from idkmesh.enterprise_authz import ActorContext, AuthorizationPolicy
from idkmesh.executor_admission import ExecutorAdmission, ExecutorAdmissionError
from idkmesh.task_claims import LocalTaskClaims, TaskClaimPolicy
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope


def _actor(name, role):
    scope = TenantScope("demo", "synthetic-project")
    return ActorContext(principal_id="actor:" + name, actor_type="service",
                        issuer="synthetic-demo", roles=frozenset({role}),
                        scopes=(scope,), data_clearance="restricted",
                        identity_revision="demo:1")


def demo() -> dict:
    scope = TenantScope("demo", "synthetic-project")
    units = []
    for name in ("research", "coding", "testing", "review"):
        unit = json.loads((ROOT / f"examples/work-units/composability/{name}.work-unit.json").read_text())
        unit["provenance"]["source_revision"] = "a" * 40
        units.append(unit)
    graph = DependencyGraph(scope, units, source_revisions={unit["id"]: "a" * 40 for unit in units})
    projection = DependencyProjection(graph)
    coding = "issue15/example/coding"
    research = "issue15/example/research"

    with tempfile.TemporaryDirectory() as temp:
        claims = LocalTaskClaims(LocalMetadataStore(Path(temp) / "control.sqlite3"),
                                 AuthorizationPolicy.enterprise_baseline())
        gate = ExecutorAdmission(projection, claims)

        def observe(node, sequence, artifacts_digest):
            gate.observe(PrerequisiteObservation(
                scope, f"synthetic-event-{node}-{sequence}", sequence, graph.bindings[node],
                "integrated", projection.readiness()[node].inputs_digest,
                integrated_revision="b" * 40, artifacts_digest=artifacts_digest,
                verification_reference="synthetic:verifier-fixture",
                integration_reference="synthetic:human-decision-fixture"))

        dispatcher, worker = _actor("dispatcher", "dispatcher"), _actor("worker", "worker")
        # Logical task identity is separate from the WorkUnit execution binding.
        task = ScopedResourceRef(scope, "task", "synthetic-coding-task")
        claims.configure_task(task, dispatcher, TaskClaimPolicy())
        try:
            gate.admit(coding, task, worker, request_id="synthetic-request-1")
        except ExecutorAdmissionError as exc:
            blocked = exc.code
        observe(research, 1, "sha256:" + "c" * 64)
        grant, admission = gate.admit(coding, task, worker, request_id="synthetic-request-1")
        claims.update_owner(grant.task, worker, request_id=grant.request_id,
                            epoch=grant.epoch, operation="acknowledge")
        reserved, reservation = gate.reserve_execution(
            coding, task, dispatcher, worker, request_id=grant.request_id, epoch=grant.epoch)
        submitted, submission = gate.submit(
            coding, task, worker, request_id=grant.request_id, epoch=grant.epoch,
            artifact_digest="sha256:" + "e" * 64)
        # A changed upstream snapshot must refuse the canonical submission.
        observe(research, 2, "sha256:" + "d" * 64)
        try:
            gate.submit(coding, task, worker, request_id=grant.request_id, epoch=grant.epoch,
                        artifact_digest="sha256:" + "f" * 64)
            stale = "unexpectedly-accepted"
        except ExecutorAdmissionError as exc:
            stale = exc.code
        return {
            "evidence_class": "synthetic_fixture",
            "blocked_admission_refusal": blocked,
            "admission": admission,
            "execution_reservation": reservation,
            "submission": submission,
            "stale_submission_refusal": stale,
            "retained_occupancy": reserved.occupancy,
            "recorded_submission_digest": submitted.submission_digest,
        }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
