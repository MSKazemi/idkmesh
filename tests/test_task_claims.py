"""Local conformance evidence, including real SQLite races; no live identities."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from idkmesh.connector_store import LocalMetadataStore, LocalStoreError, SCHEMA_VERSION
from idkmesh.enterprise_authz import ActorContext, AuthorizationPolicy
from idkmesh.task_claims import ClaimBinding, LocalTaskClaims, TaskClaimError, TaskClaimPolicy
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope


SCOPE = TenantScope("tenant-a", "project-a")
TASK = ScopedResourceRef(SCOPE, "task", "logical-task-1")
BINDING = ClaimBinding("sha256:" + "a" * 64, "b" * 40, "sha256:" + "c" * 64)


def _actor(name="alice", *, roles=("worker",), actor_type="human", scope=SCOPE):
    return ActorContext(
        principal_id="actor:" + name, actor_type=actor_type, issuer="test-adapter",
        roles=frozenset(roles), scopes=(scope,), data_clearance="restricted",
        identity_revision="test:1",
    )


def _process_claim(path, index, queue):
    coordinator = LocalTaskClaims(LocalMetadataStore(path), AuthorizationPolicy.enterprise_baseline(),
                                  clock=lambda: 1000)
    try:
        grant, created = coordinator.claim(TASK, _actor(str(index)), request_id=str(index), binding=BINDING)
        queue.put(("created", grant.epoch, created))
    except TaskClaimError as exc:
        queue.put((exc.code, None, False))


class LocalTaskClaimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "control.sqlite3"
        self.now = 1000
        self.store = LocalMetadataStore(self.path)
        self.coordinator = self.restart()
        self.worker = _actor()
        self.dispatcher = _actor("dispatcher", roles=("dispatcher",))
        self.policy = TaskClaimPolicy(ack_seconds=10, lease_seconds=30, progress_seconds=60, hard_seconds=100)
        self.coordinator.configure_task(TASK, self.dispatcher, self.policy)

    def restart(self):
        return LocalTaskClaims(LocalMetadataStore(self.path), AuthorizationPolicy.enterprise_baseline(),
                               clock=lambda: self.now)

    def claim(self, request_id="request-1", *, actor=None, binding=BINDING, task=TASK):
        return self.coordinator.claim(task, actor or self.worker, request_id=request_id, binding=binding)[0]

    def update(self, grant, operation, *, actor=None):
        return self.coordinator.update_owner(grant.task, actor or self.worker,
                                             request_id=grant.request_id, epoch=grant.epoch,
                                             operation=operation)

    def reserve(self, grant):
        return self.coordinator.reserve_dispatch(TASK, self.dispatcher, self.worker,
                                                 request_id=grant.request_id, epoch=grant.epoch)

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(TaskClaimError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_100_distinct_human_agent_requests_admit_one_across_connections(self):
        coordinators = [self.restart() for _ in range(100)]
        start = threading.Event()

        def attempt(index):
            start.wait(10)
            actor = _actor(str(index), actor_type="human" if index % 2 else "service")
            binding = replace(BINDING, source_revision=f"{index:040x}")
            try:
                return coordinators[index].claim(TASK, actor, request_id=f"race-{index}", binding=binding)
            except TaskClaimError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(attempt, i) for i in range(100)]
            start.set()
            results = [future.result(timeout=30) for future in futures]
        admitted = [value for value in results if isinstance(value, tuple)]
        self.assertEqual(len(admitted), 1)
        self.assertTrue(admitted[0][1])
        self.assertEqual(results.count("task_capacity_reserved"), 99)
        self.assertEqual(len(self.restart().snapshot(TASK, self.dispatcher)), 1)

    def test_separate_coordinator_processes_share_the_same_limit(self):
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        self.addCleanup(queue.close)
        processes = [context.Process(target=_process_claim, args=(str(self.path), i, queue)) for i in range(4)]
        try:
            for process in processes:
                process.start()
            results = [queue.get(timeout=30) for _ in processes]
            for process in processes:
                process.join(30)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(sum(result[0] == "created" for result in results), 1)
            self.assertEqual(sum(result[0] == "task_capacity_reserved" for result in results), 3)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(5)

    def test_exact_replay_survives_restart_and_does_not_extend_deadlines(self):
        grant = self.claim()
        self.now += 5
        replay, created = self.restart().claim(TASK, self.worker, request_id=grant.request_id, binding=BINDING)
        self.assertFalse(created)
        self.assertEqual(replay.to_dict(), grant.to_dict())

    def test_replay_conflicts_on_owner_or_exact_execution_binding(self):
        self.claim()
        for actor, binding in ((self.worker, replace(BINDING, source_revision="d" * 40)),
                               (_actor("bob"), BINDING),
                               (replace(self.worker, issuer="other-issuer"), BINDING)):
            with self.subTest(actor=actor.principal_id, binding=binding.source_revision):
                self.assert_code("request_conflict", self.claim, actor=actor, binding=binding)

    def test_new_request_rebase_and_provider_identity_cannot_bypass_cap(self):
        self.claim()
        for index, actor_type in enumerate(("human", "provider", "github_actions")):
            self.assert_code("task_capacity_reserved", self.claim, f"other-{index}",
                             actor=_actor(str(index), actor_type=actor_type),
                             binding=replace(BINDING, source_revision="e" * 40))

    def test_scopes_have_independent_claims_but_cross_scope_access_is_denied(self):
        self.claim()
        scope = TenantScope("tenant-b", "project-a")
        task = ScopedResourceRef(scope, "task", TASK.resource_id)
        dispatcher = _actor("other-dispatcher", roles=("dispatcher",), scope=scope)
        worker = _actor("other-worker", scope=scope)
        self.coordinator.configure_task(task, dispatcher, self.policy)
        grant = self.claim("other", actor=worker, task=task)
        self.assertEqual(grant.epoch, 1)
        for function, args in ((self.coordinator.snapshot, (task, self.worker)),
                               (self.coordinator.claim, (task, self.worker))):
            kwargs = {"request_id": "probe", "binding": BINDING} if function == self.coordinator.claim else {}
            self.assert_code("actor_scope_denied", function, *args, **kwargs)
        self.assert_code("actor_scope_denied", self.coordinator.update_owner, task, self.worker,
                         request_id="other", epoch=1, operation="release")

    def test_unauthorized_revoked_expired_and_unauthenticated_claims_are_denied(self):
        cases = [(replace(self.worker, roles=frozenset({"reviewer"})), "role_denied"),
                 (replace(self.worker, revoked=True), "actor_revoked"),
                 (replace(self.worker, authenticated=False), "actor_unauthenticated"),
                 (replace(self.worker, expires_at_epoch=self.now), "actor_expired")]
        for actor, code in cases:
            self.assert_code(code, self.claim, actor=actor)
        self.assertEqual(self.coordinator.snapshot(TASK, self.dispatcher), ())

    def test_worker_cannot_configure_limits_and_configuration_is_immutable(self):
        task = ScopedResourceRef(SCOPE, "task", "unconfigured")
        self.assert_code("role_denied", self.coordinator.configure_task, task, self.worker, self.policy)
        self.assertFalse(self.coordinator.configure_task(TASK, self.dispatcher, self.policy))
        self.assert_code("task_policy_conflict", self.coordinator.configure_task, TASK, self.dispatcher,
                         replace(self.policy, max_attempts=10))
        self.assert_code("task_not_configured", self.claim, task=task)

    def test_non_owner_cannot_renew_release_or_submit_even_with_worker_role(self):
        grant = self.update(self.claim(), "acknowledge")
        for operation in ("acknowledge", "renew", "progress", "release"):
            self.assert_code("claim_owner_denied", self.update, grant, operation, actor=_actor("bob"))
        self.assert_code("claim_owner_denied", self.coordinator.record_submission, TASK, _actor("bob"),
                         request_id=grant.request_id, epoch=grant.epoch, artifact_digest=BINDING.inputs_digest)

    def test_identity_revocation_is_rechecked_after_admission(self):
        grant = self.claim()
        revoked = replace(self.worker, revoked=True)
        self.assert_code("actor_revoked", self.update, grant, "release", actor=revoked)
        self.assert_code("actor_revoked", self.coordinator.snapshot, TASK, revoked)

    def test_unacknowledged_owner_expires_at_ack_deadline(self):
        grant = self.claim()
        self.now = grant.ack_by
        self.assert_code("stale_claim", self.update, grant, "acknowledge")
        self.assertEqual(self.coordinator.snapshot(TASK, self.dispatcher)[0].state, "expired")
        new = self.claim("replacement")
        self.assertEqual(new.epoch, grant.epoch + 1)

    def test_each_deadline_expires_and_renewal_never_revives_an_expired_grant(self):
        for field in ("lease_until", "progress_by", "hard_until"):
            with self.subTest(field=field):
                task = ScopedResourceRef(SCOPE, "task", field)
                duration = field.replace("_until", "_seconds").replace("_by", "_seconds")
                limits = replace(self.policy, **{**dict(ack_seconds=100, lease_seconds=100,
                                                       progress_seconds=100), duration: 20})
                self.coordinator.configure_task(task, self.dispatcher, limits)
                grant = self.update(self.claim(field, task=task), "acknowledge")
                self.now = getattr(grant, field)
                self.assert_code("stale_claim", self.update, grant, "renew")
                self.assertEqual(self.coordinator.snapshot(task, self.dispatcher)[0].state, "expired")

    def test_heartbeat_does_not_extend_progress_and_no_update_extends_hard_deadline(self):
        grant = self.update(self.claim(), "acknowledge")
        hard = grant.hard_until
        for now in (1020, 1040, 1060, 1080):
            self.now = now
            progressed = self.update(grant, "progress")
            renewed = self.update(grant, "renew")
            self.assertEqual(renewed.progress_by, progressed.progress_by)
            self.assertEqual(renewed.hard_until, hard)
            self.assertLessEqual(renewed.lease_until, hard)
            self.assertLessEqual(progressed.progress_by, hard)
        self.now = hard
        self.assert_code("stale_claim", self.update, grant, "progress")

    def test_acknowledgement_required_before_renewal_dispatch_and_submission(self):
        grant = self.claim()
        self.assert_code("acknowledgement_required", self.update, grant, "renew")
        self.assert_code("acknowledgement_required", self.reserve, grant)
        self.assert_code("acknowledgement_required", self.coordinator.record_submission, TASK, self.worker,
                         request_id=grant.request_id, epoch=grant.epoch, artifact_digest=BINDING.inputs_digest)

    def test_release_reassigns_unused_slot_but_fences_old_owner(self):
        old = self.claim()
        self.update(old, "release")
        new = self.claim("new")
        self.assertEqual(new.epoch, old.epoch + 1)
        for operation in ("release", "acknowledge", "renew"):
            self.assert_code("stale_claim", self.update, old, operation)
        self.assert_code("stale_claim", self.coordinator.record_submission, TASK, self.worker,
                         request_id=old.request_id, epoch=old.epoch, artifact_digest=BINDING.inputs_digest)

    def test_unknown_dispatch_intent_is_durable_and_replay_does_not_start_again(self):
        grant = self.update(self.claim(), "acknowledge")
        reserved, created = self.reserve(grant)
        self.assertTrue(created)
        self.assertEqual(reserved.occupancy, "unknown")
        replay, created = self.restart().reserve_dispatch(TASK, self.dispatcher, self.worker,
                                                         request_id=grant.request_id, epoch=grant.epoch)
        self.assertFalse(created)
        self.assertEqual(replay.operation_id, reserved.operation_id)

    def test_release_keeps_unknown_execution_charged_until_terminal_confirmation(self):
        grant = self.update(self.claim(), "acknowledge")
        self.reserve(grant)
        released = self.update(grant, "release")
        self.assertEqual(released.occupancy, "unknown")
        self.assert_code("task_capacity_reserved", self.claim, "replacement")
        self.coordinator.reconcile_execution(TASK, self.dispatcher, request_id=grant.request_id,
                                             epoch=grant.epoch, status="terminal", evidence_reference="fixture:not-created")
        self.assertEqual(self.claim("replacement").epoch, grant.epoch + 1)

    def test_expiry_and_restart_do_not_free_unknown_or_running_execution(self):
        grant = self.update(self.claim(), "acknowledge")
        self.reserve(grant)
        self.now = grant.lease_until
        restarted = self.restart()
        self.assertEqual(restarted.snapshot(TASK, self.dispatcher)[0].state, "expired")
        self.assert_code("task_capacity_reserved", restarted.claim, TASK, _actor("replacement"),
                         request_id="replacement", binding=BINDING)
        restarted.reconcile_execution(TASK, self.dispatcher, request_id=grant.request_id,
                                       epoch=grant.epoch, status="running", evidence_reference="fixture:still-running")
        self.assert_code("task_capacity_reserved", self.claim, "replacement")
        self.assert_code("stale_claim", self.coordinator.record_submission, TASK, self.worker,
                         request_id=grant.request_id, epoch=grant.epoch, artifact_digest=BINDING.inputs_digest)
        restarted.reconcile_execution(TASK, self.dispatcher, request_id=grant.request_id,
                                       epoch=grant.epoch, status="terminal", evidence_reference="fixture:stopped")
        self.assertEqual(self.claim("replacement").epoch, grant.epoch + 1)

    def test_only_dispatch_authority_can_reconcile_and_terminal_is_absorbing(self):
        grant = self.update(self.claim(), "acknowledge")
        self.reserve(grant)
        kwargs = dict(request_id=grant.request_id, epoch=grant.epoch, status="terminal",
                      evidence_reference="fixture:terminal")
        self.assert_code("role_denied", self.coordinator.reconcile_execution, TASK, self.worker, **kwargs)
        terminal = self.coordinator.reconcile_execution(TASK, self.dispatcher, **kwargs)
        self.assertEqual(self.coordinator.reconcile_execution(TASK, self.dispatcher, **kwargs), terminal)
        self.assert_code("terminal_execution_conflict", self.coordinator.reconcile_execution, TASK,
                         self.dispatcher, **{**kwargs, "status": "running"})
        self.assert_code("stale_claim", self.coordinator.reconcile_execution, TASK,
                         self.dispatcher, **{**kwargs, "epoch": grant.epoch + 1})
        self.assert_code("role_denied", self.coordinator.reserve_dispatch, TASK, self.worker, self.worker,
                         request_id=grant.request_id, epoch=grant.epoch)

    def test_competition_is_bounded_and_epochs_are_per_slot(self):
        task = ScopedResourceRef(SCOPE, "task", "compete")
        policy = replace(self.policy, concurrent_slots=2, max_attempts=3, competition_reason="compare two designs")
        self.coordinator.configure_task(task, self.dispatcher, policy)
        first = self.claim("first", task=task)
        second = self.update(self.claim("second", actor=_actor("bob"), task=task), "acknowledge", actor=_actor("bob"))
        self.assertNotEqual(first.slot, second.slot)
        self.assert_code("task_capacity_reserved", self.claim, "third", task=task)
        self.update(first, "release")
        replacement = self.claim("third", task=task)
        self.assertEqual(replacement.slot, first.slot)
        self.assertEqual(replacement.epoch, first.epoch + 1)
        self.assertEqual(self.update(second, "renew", actor=_actor("bob")).epoch, second.epoch)

    def test_lifetime_attempt_limit_cannot_be_reset_by_release_expiry_or_rebase(self):
        for index in range(3):
            grant = self.claim(str(index), binding=replace(BINDING, source_revision=f"{index:040x}"))
            self.update(grant, "release")
        self.assert_code("attempt_budget_exhausted", self.claim, "fourth")
        replay, created = self.coordinator.claim(TASK, self.worker, request_id="0",
                                                binding=replace(BINDING, source_revision="0" * 40))
        self.assertFalse(created)
        self.assertEqual(replay.state, "released")

    def test_clock_rollback_after_restart_fails_closed_without_reviving_ownership(self):
        grant = self.claim()
        self.now = grant.ack_by
        self.coordinator.snapshot(TASK, self.dispatcher)
        self.now -= 1
        self.assert_code("clock_rollback", self.restart().snapshot, TASK, self.dispatcher)
        self.assert_code("clock_rollback", self.claim, "replacement")
        self.now += 1
        self.assertEqual(self.restart().snapshot(TASK, self.dispatcher)[0].state, "expired")

    def test_high_risk_execution_and_configuration_require_distinct_approval(self):
        task = ScopedResourceRef(SCOPE, "task", "high-risk")
        policy = replace(self.policy, risk="high")
        approver = _actor("approver", roles=("dispatcher",))
        self.assert_code("distinct_approval_required", self.coordinator.configure_task, task, self.dispatcher, policy)
        self.coordinator.configure_task(task, self.dispatcher, policy, approver=approver,
                                         approval_reference="fixture:config-approval")
        grant = self.update(self.claim("high", task=task), "acknowledge")
        self.assert_code("distinct_approval_required", self.coordinator.record_submission, task, self.worker,
                         request_id=grant.request_id, epoch=grant.epoch, artifact_digest=BINDING.inputs_digest)
        self.coordinator.record_submission(task, self.worker, request_id=grant.request_id, epoch=grant.epoch,
                                            artifact_digest=BINDING.inputs_digest, approver=approver,
                                            approval_reference="fixture:execution-approval")

    def test_submission_is_idempotent_candidate_metadata_with_no_acceptance_authority(self):
        grant = self.update(self.claim(), "acknowledge")
        kwargs = dict(request_id=grant.request_id, epoch=grant.epoch, artifact_digest=BINDING.inputs_digest)
        result = self.coordinator.record_submission(TASK, self.worker, **kwargs)
        self.assertEqual(self.coordinator.record_submission(TASK, self.worker, **kwargs), result)
        self.assertEqual(result.to_dict()["authority"],
                         {"executes_worker": False, "accepts_candidate": False, "merge": False})
        self.assert_code("submission_conflict", self.coordinator.record_submission, TASK, self.worker,
                         **{**kwargs, "artifact_digest": BINDING.work_unit_digest})

    def test_invalid_limits_bindings_and_epoch_are_rejected(self):
        for kwargs in ({"concurrent_slots": 50}, {"concurrent_slots": True}, {"max_attempts": 0},
                       {"concurrent_slots": 2}, {"lease_seconds": 0}, {"competition_reason": ""}):
            self.assert_code("invalid_input", TaskClaimPolicy, **kwargs)
        self.assert_code("invalid_input", ClaimBinding, "not-a-digest", "b" * 40, BINDING.inputs_digest)
        grant = self.claim()
        self.assert_code("stale_claim", self.coordinator.update_owner, TASK, self.worker,
                         request_id=grant.request_id, epoch=True, operation="release")

    def test_runtime_claim_snapshots_conform_to_versioned_schema(self):
        schema = json.loads((Path(__file__).parents[1] / "schemas/task-claim-v0.1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        grant = self.update(self.claim(), "acknowledge")
        self.reserve(grant)
        self.now = grant.lease_until
        for record in self.restart().snapshot(TASK, self.dispatcher):
            validator.validate(record.to_dict())
        terminal = self.coordinator.reconcile_execution(TASK, self.dispatcher, request_id=grant.request_id,
                                                         epoch=grant.epoch, status="terminal",
                                                         evidence_reference="fixture:terminal")
        validator.validate(terminal.to_dict())
        validator.validate(self.update(self.claim("new"), "release").to_dict())

    def test_default_clock_enforces_elapsed_time_and_detects_wall_rollback(self):
        with patch("idkmesh.task_claims.time.time", return_value=1000), \
                patch("idkmesh.task_claims.time.monotonic", return_value=50) as monotonic:
            coordinator = LocalTaskClaims(self.store, AuthorizationPolicy.enterprise_baseline())
            grant, _ = coordinator.claim(TASK, self.worker, request_id="clock", binding=BINDING)
            monotonic.return_value = 61
            self.assertEqual(coordinator.snapshot(TASK, self.dispatcher)[0].state, "expired")
            self.assertEqual(grant.ack_by, 1010)
            with patch("idkmesh.task_claims.time.time", return_value=999):
                self.assert_code("clock_rollback", coordinator.snapshot, TASK, self.dispatcher)

    def test_read_reconcile_and_configuration_cannot_cross_actor_scope(self):
        grant = self.update(self.claim(), "acknowledge")
        self.reserve(grant)
        outsider = _actor("outsider", roles=("dispatcher",), scope=TenantScope("tenant-b", "project-a"))
        self.assert_code("actor_scope_denied", self.coordinator.configure_task, TASK, outsider, self.policy)
        self.assert_code("actor_scope_denied", self.coordinator.reconcile_execution, TASK, outsider,
                         request_id=grant.request_id, epoch=grant.epoch, status="terminal",
                         evidence_reference="fixture:untrusted")
        self.assertEqual(self.coordinator.snapshot(TASK, self.dispatcher)[0].occupancy, "unknown")

    def test_upgrade_from_v2_preserves_existing_run_and_append_only_event(self):
        path = Path(self.temp.name) / "v2.sqlite3"
        store = LocalMetadataStore(path)
        event = {"occurred_at": "2026-10-04T00:00:00Z", "event_type": "run.created",
                 "authority_class": "local_control", "project_id": "project-a",
                 "work_unit_id": "wu-1", "run_id": "run-1", "principal": {"type": "unauthenticated_local", "id": "local-cli"},
                 "attempt_id": None, "source_revision": None, "evidence_reference": None, "payload": {"state": "proposed"}}
        record, _ = store.admit_run(run_id="run-1", idempotency_key="run-key", request_digest="digest",
                                    state="proposed", metadata={"retained": True},
                                    created_at="2026-10-04T00:00:00Z", event=event)
        with sqlite3.connect(path) as conn:
            for table in ("task_claims", "task_claim_slots", "task_claim_policies", "task_claim_clock"):
                conn.execute(f"DROP TABLE {table}")
            conn.execute("PRAGMA user_version = 2")
        upgraded = LocalMetadataStore(path)
        self.assertEqual(upgraded.get_run("run-1"), record)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM events")

    def test_adapter_transaction_rolls_back_on_failure(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction() as conn:
                conn.execute("INSERT INTO task_claim_clock VALUES (1, 9999) ON CONFLICT(singleton) DO UPDATE SET last_epoch=9999")
                raise RuntimeError("crash before commit")
        self.assertEqual(self.coordinator.snapshot(TASK, self.dispatcher), ())
        with self.assertRaises(LocalStoreError):
            with self.store.transaction() as conn:
                conn.execute("SELECT * FROM missing_table")
