"""Local conformance for readiness-checked claims; synthetic identities only.

Each refusal below exists only in ``idkmesh.executor_admission``: a plain
readiness report followed by an unchecked claim would pass these scenarios.
No live identity, provider, worker, verification or integration occurs.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

from jsonschema import Draft202012Validator

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.coordination_preflight import (
    DependencyGraph, DependencyProjection, PrerequisiteObservation,
)
from idkmesh.enterprise_authz import ActorContext, AuthorizationPolicy
from idkmesh.executor_admission import ExecutorAdmission, ExecutorAdmissionError
from idkmesh.task_claims import (
    LocalTaskClaims, TaskClaimError, TaskClaimPolicy,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope


ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "examples/work-units/composability/coding.work-unit.json").read_text())
SCOPE = TenantScope("tenant-a", "project-a")
REVISION = "a" * 40


def _unit(node, requires=()):
    unit = deepcopy(BASE)
    unit["id"] = node
    unit["provenance"]["source_revision"] = REVISION
    unit["dependencies"] = [{"work_unit_id": target, "relationship": "requires"} for target in requires]
    return unit


def _graph(units):
    return DependencyGraph(SCOPE, units, source_revisions={unit["id"]: REVISION for unit in units})


def _task_ref(node):
    return ScopedResourceRef(SCOPE, "task", node)


def _actor(name="alice", *, roles=("worker",), actor_type="human"):
    return ActorContext(
        principal_id="actor:" + name, actor_type=actor_type, issuer="test-adapter",
        roles=frozenset(roles), scopes=(SCOPE,), data_clearance="restricted",
        identity_revision="test:1",
    )


def _observation(projection, node="task-a", *, sequence=1, state="integrated", **kwargs):
    defaults = dict(scope=SCOPE, event_id=f"event-{node}-{sequence}", sequence=sequence,
                    binding=projection.graph.bindings[node], state=state,
                    inputs_digest=projection.readiness()[node].inputs_digest or "sha256:" + "0" * 64)
    if state == "integrated":
        defaults.update(integrated_revision="b" * 40, artifacts_digest="sha256:" + "c" * 64,
                        verification_reference="fixture:independent-evidence",
                        integration_reference="fixture:human-decision")
    return PrerequisiteObservation(**{**defaults, **kwargs})


class ExecutorAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.units = [_unit("task-a"), _unit("task-b", ("task-a",)), _unit("task-z")]
        self.projection = DependencyProjection(_graph(self.units))
        self.now = 1000
        self.claims = LocalTaskClaims(
            LocalMetadataStore(Path(self.temp.name) / "control.sqlite3"),
            AuthorizationPolicy.enterprise_baseline(), clock=lambda: self.now)
        self.gate = ExecutorAdmission(self.projection, self.claims)
        self.worker = _actor()
        self.dispatcher = _actor("dispatcher", roles=("dispatcher",))
        self.policy = TaskClaimPolicy(ack_seconds=10, lease_seconds=30,
                                      progress_seconds=60, hard_seconds=100)
        for node in ("task-b", "task-z"):
            self.claims.configure_task(_task_ref(node), self.dispatcher, self.policy)

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises((ExecutorAdmissionError, TaskClaimError)) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def observe(self, node="task-a", **kwargs):
        return self.gate.observe(_observation(self.projection, node, **kwargs))

    def admit(self, node="task-b", request_id="request-1", actor=None):
        return self.gate.admit(node, _task_ref(node), actor or self.worker, request_id=request_id)

    def acknowledge(self, grant):
        return self.claims.update_owner(grant.task, self.worker, request_id=grant.request_id,
                                        epoch=grant.epoch, operation="acknowledge")

    def reserve(self, grant, *, epoch=None, node="task-b", task=None):
        return self.gate.reserve_execution(node, task or _task_ref("task-b"),
                                           self.dispatcher, self.worker,
                                           request_id=grant.request_id,
                                           epoch=grant.epoch if epoch is None else epoch)

    def submit(self, grant, *, epoch=None, actor=None, artifact_digest="sha256:" + "e" * 64,
               node="task-b", task=None):
        return self.gate.submit(node, task or _task_ref("task-b"), actor or self.worker,
                                request_id=grant.request_id,
                                epoch=grant.epoch if epoch is None else epoch,
                                artifact_digest=artifact_digest)

    def test_admission_binds_the_exact_ready_input_snapshot(self):
        self.observe()
        state = self.projection.readiness()["task-b"]
        grant, report = self.admit()
        self.assertTrue(report["created"])
        self.assertEqual(report["phase"], "admission")
        self.assertEqual(grant.binding.inputs_digest, state.inputs_digest)
        self.assertEqual(report["inputs_digest"], state.inputs_digest)
        self.assertEqual(report["binding"], self.projection.graph.bindings["task-b"].to_dict())
        self.assertEqual(report["claim"]["task"], _task_ref("task-b").to_dict())
        self.assertTrue(all(value is False for value in report["authority"].values()))

    def test_blocked_task_is_refused_before_any_claim_exists(self):
        self.assert_code("task_not_ready", self.admit)
        with self.assertRaises(ExecutorAdmissionError) as caught:
            self.admit()
        self.assertIn("prerequisite_missing:task-a", str(caught.exception))
        self.assertEqual(self.claims.snapshot(_task_ref("task-b"), self.dispatcher), ())

    def test_unknown_work_unit_is_refused(self):
        self.assert_code("unknown_work_unit", self.admit, "missing")

    def test_task_identity_scope_must_match_the_graph(self):
        outsider = ScopedResourceRef(TenantScope("tenant-b", "project-a"), "task", "task-b")
        self.assert_code("scope_mismatch", self.gate.admit, "task-b", outsider,
                         self.worker, request_id="request-1")
        wrong_type = ScopedResourceRef(SCOPE, "run", "task-b")
        self.assert_code("invalid_input", self.gate.admit, "task-b", wrong_type,
                         self.worker, request_id="request-1")

    def test_already_integrated_task_is_not_admitted_again(self):
        self.observe("task-a")
        self.observe("task-b")
        self.assertTrue(self.projection.readiness()["task-b"].satisfied)
        self.assert_code("task_already_integrated", self.admit)

    def test_exact_admission_replay_returns_the_retained_grant_without_renewal(self):
        self.observe()
        grant, _ = self.admit()
        self.now += 5
        replay, report = self.admit()
        self.assertFalse(report["created"])
        self.assertEqual(replay.to_dict(), grant.to_dict())

    def test_admission_requires_a_trusted_task_policy(self):
        self.assert_code("task_not_configured", self.admit, "task-a")

    def test_upstream_change_before_dispatch_is_refused_without_a_dispatch_intent(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        self.observe(sequence=2, artifacts_digest="sha256:" + "d" * 64)
        self.assert_code("inputs_changed", self.reserve, grant)
        record = self.claims.snapshot(_task_ref("task-b"), self.dispatcher)[0]
        self.assertEqual(record.occupancy, "none")
        self.assertIsNone(record.operation_id)

    def test_upstream_change_before_submission_is_refused(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        self.reserve(grant)
        self.observe(sequence=2, artifacts_digest="sha256:" + "d" * 64)
        self.assert_code("inputs_changed", self.submit, grant)
        self.assertIsNone(self.claims.snapshot(
            _task_ref("task-b"), self.dispatcher)[0].submission_digest)

    def test_current_inputs_record_a_fenced_submission_and_replay_is_idempotent(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        reserved, report = self.reserve(grant)
        self.assertEqual(report["phase"], "execution-reservation")
        self.assertEqual(reserved.occupancy, "unknown")
        submitted, report = self.submit(grant)
        self.assertEqual(report["phase"], "submission")
        self.assertTrue(report["created"])
        self.assertEqual(submitted.submission_digest, "sha256:" + "e" * 64)
        replay, report = self.submit(grant)
        self.assertFalse(report["created"])
        self.assertEqual(replay.submission_digest, submitted.submission_digest)

    def test_unrelated_branch_change_leaves_the_task_current(self):
        self.observe()
        grant, _ = self.admit("task-z", request_id="request-z")
        self.claims.update_owner(_task_ref("task-z"), self.worker,
                                 request_id="request-z", epoch=grant.epoch,
                                 operation="acknowledge")
        self.observe("task-a")
        self.observe("task-a", sequence=2, artifacts_digest="sha256:" + "d" * 64)
        reserved, _ = self.gate.reserve_execution(
            "task-z", _task_ref("task-z"), self.dispatcher, self.worker,
            request_id="request-z", epoch=grant.epoch)
        self.assertEqual(reserved.occupancy, "unknown")

    def test_claim_bound_to_another_work_unit_is_refused(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        self.assert_code("binding_mismatch", self.reserve, grant, node="task-a")
        self.assert_code("binding_mismatch", self.submit, grant, node="task-a")

    def test_replayed_dispatch_intent_is_not_a_new_reservation(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        reserved, _ = self.reserve(grant)
        replay, report = self.reserve(grant)
        self.assertFalse(report["created"])
        self.assertEqual(replay.operation_id, reserved.operation_id)
        # A stale-input replay is refused, while the retained intent stays inspectable.
        self.observe(sequence=2, artifacts_digest="sha256:" + "d" * 64)
        self.assert_code("inputs_changed", self.reserve, grant)
        self.assertEqual(self.claims.snapshot(
            _task_ref("task-b"), self.dispatcher)[0].occupancy, "unknown")

    def test_stale_epoch_non_owner_and_unknown_request_are_refused(self):
        self.observe()
        grant, _ = self.admit()
        self.acknowledge(grant)
        self.assert_code("stale_claim", self.reserve, grant, epoch=grant.epoch + 1)
        self.assert_code("claim_owner_denied", self.submit, grant, actor=_actor("bob"))
        self.assert_code("claim_not_found", self.gate.reserve_execution,
                         "task-b", _task_ref("task-b"), self.dispatcher, self.worker,
                         request_id="no-such-request", epoch=grant.epoch)
        self.assert_code("claim_not_found", self.gate.submit, "task-b", _task_ref("task-b"),
                         self.worker, request_id="no-such-request", epoch=grant.epoch,
                         artifact_digest="sha256:" + "e" * 64)

    def test_concurrent_admission_across_humans_and_agents_admits_one(self):
        self.observe()
        start = threading.Event()

        def attempt(index):
            start.wait(10)
            actor = _actor(str(index), actor_type="human" if index % 2 else "service")
            try:
                grant, report = self.admit(request_id=f"race-{index}", actor=actor)
                return report["created"], grant.epoch
            except TaskClaimError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(attempt, index) for index in range(20)]
            start.set()
            results = [future.result(timeout=30) for future in futures]
        admitted = [value for value in results if isinstance(value, tuple)]
        self.assertEqual(len(admitted), 1)
        self.assertTrue(admitted[0][0])
        self.assertEqual(results.count("task_capacity_reserved"), 19)
        self.assertEqual(len(self.claims.snapshot(_task_ref("task-b"), self.dispatcher)), 1)

    def test_reports_conform_to_the_versioned_schema_and_keep_the_authority_ceiling(self):
        schema = json.loads((ROOT / "schemas/executor-admission-v0.1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.observe()
        grant, admission = self.admit()
        self.acknowledge(grant)
        _, reservation = self.reserve(grant)
        _, submission = self.submit(grant)
        for report in (admission, reservation, submission):
            with self.subTest(phase=report["phase"]):
                validator.validate(report)
                self.assertTrue(all(value is False for value in report["authority"].values()))

    def test_demo_reports_are_schema_valid(self):
        spec = importlib.util.spec_from_file_location(
            "admission_demo", ROOT / "examples/coordination/admission_demo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document = module.demo()
        schema = json.loads((ROOT / "schemas/executor-admission-v0.1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        self.assertEqual(document["evidence_class"], "synthetic_fixture")
        self.assertEqual(document["blocked_admission_refusal"], "task_not_ready")
        self.assertEqual(document["stale_submission_refusal"], "inputs_changed")
        for name in ("admission", "execution_reservation", "submission"):
            with self.subTest(report=name):
                self.assertEqual(list(validator.iter_errors(document[name])), [])


class ExecutorAdmissionHardeningTests(unittest.TestCase):
    """Regression shape: each test fails against an unchecked claim-after-report."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.projection = DependencyProjection(
            _graph([_unit("task-a"), _unit("task-b", ("task-a",))]))
        self.claims = LocalTaskClaims(
            LocalMetadataStore(Path(self.temp.name) / "control.sqlite3"),
            AuthorizationPolicy.enterprise_baseline(), clock=lambda: 1000)
        self.gate = ExecutorAdmission(self.projection, self.claims)
        self.worker = _actor()
        self.dispatcher = _actor("dispatcher", roles=("dispatcher",))
        self.task = _task_ref("task-b")
        self.claims.configure_task(self.task, self.dispatcher, TaskClaimPolicy())

    def test_report_metadata_is_not_authority_and_binds_one_graph_snapshot(self):
        self.gate.observe(_observation(self.projection, "task-a"))
        grant, report = self.gate.admit("task-b", self.task, self.worker, request_id="request-1")
        self.assertEqual(report["claim"]["authority"],
                         {"executes_worker": False, "accepts_candidate": False, "merge": False})
        self.assertEqual(report["graph_digest"], self.projection.graph.digest)
        changed = DependencyProjection(
            _graph([_unit("task-a"), _unit("task-b", ("task-a",)), _unit("task-extra")]))
        self.assertNotEqual(changed.graph.digest, report["graph_digest"])

    def test_direct_projection_mutation_still_fails_closed_at_the_recheck(self):
        self.gate.observe(_observation(self.projection, "task-a"))
        grant, _ = self.gate.admit("task-b", self.task, self.worker, request_id="request-1")
        self.claims.update_owner(grant.task, self.worker, request_id=grant.request_id,
                                 epoch=grant.epoch, operation="acknowledge")
        # Bypass gate.observe deliberately: the gate cannot lock out direct
        # mutation, but the recheck must still refuse the stale snapshot.
        self.projection.observe(_observation(
            self.projection, "task-a", sequence=2, artifacts_digest="sha256:" + "f" * 64))
        with self.assertRaises(ExecutorAdmissionError) as caught:
            self.gate.reserve_execution("task-b", self.task, self.dispatcher, self.worker,
                                        request_id=grant.request_id, epoch=grant.epoch)
        self.assertEqual(caught.exception.code, "inputs_changed")


if __name__ == "__main__":
    unittest.main()
