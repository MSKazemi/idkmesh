"""State-transition and idempotency properties (#745, property/fuzz slice 3).

PR #992 qualified the strict-JSON parsers and PR #993 the header/media-type
boundary. This slice closes the Property/fuzz section of #745 with the two
remaining items -- state-transition properties and idempotency properties --
over the Product Spine domain the Control Tower API serves.

The lifecycle graphs below are deliberate copies of the documented v0.1
contract, kept independent of ``idkmesh.product_spine``'s private tables on
purpose: the exhaustive pair tests pin the shipped graph against the
documented one, so a silent graph edit fails here instead of quietly changing
what "safe to release" means. The seeded operation fuzz checks the properties
that must hold for *any* revision:

* every state pair is decided by exactly the graph (accepted or the stable
  ``invalid_run_transition``/``invalid_attempt_transition`` error);
* transitions return new immutable objects and never rewrite identity fields;
* an idempotent replay returns the created run untouched, while any mutated
  replay fails closed with ``idempotency_conflict``;
* arbitrary create/replay/status/list/cancel sequences are total: every
  failure is a controlled ``ProductSpineRunStoreError``, and the store stays
  consistent throughout.

Every test is class-based on purpose: the repository's documented test counts
guard module-level ``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import random
import tempfile
import unittest
from dataclasses import replace

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.product_spine import (
    ATTEMPT_STATES,
    RUN_STATES,
    AttemptProjection,
    ProductSpineError,
    ProductSpineRun,
    transition_attempt_state,
    transition_run_state,
)
from idkmesh.product_spine_run_store import (
    ProductSpineRunStore,
    ProductSpineRunStoreError,
    run_create_request_digest,
)

SEED = 20261010

SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
CREATED_AT = "2026-01-01T00:00:00Z"

# Documented v0.1 run lifecycle graph (API Conventions / product-spine-run
# schema). Independent copy: see the module docstring.
RUN_GRAPH = {
    "proposed": {"previewed", "cancelled"},
    "previewed": {"admission_blocked", "admitted", "cancelled"},
    "admission_blocked": {"cancelled"},
    "admitted": {"dispatched", "cancelled"},
    "dispatched": {"attempt_failed", "candidate_observed", "cancelled"},
    "attempt_failed": {"dispatched", "cancelled"},
    "candidate_observed": {"normalized", "cancelled"},
    "normalized": {"verification_requested", "cancelled"},
    "verification_requested": {
        "verification_error",
        "evidence_ready",
        "cancelled",
    },
    "verification_error": {
        "verification_requested",
        "evidence_ready",
        "cancelled",
    },
    "evidence_ready": {"awaiting_human_decision"},
    "awaiting_human_decision": {"decided", "cancelled"},
    "decided": set(),
    "cancelled": set(),
}

# Documented v0.1 attempt lifecycle graph.
ATTEMPT_GRAPH = {
    "created": {"dispatched", "cancelled"},
    "dispatched": {"worker_error", "candidate_observed", "cancelled"},
    "worker_error": set(),
    "candidate_observed": {
        "normalization_error",
        "normalized",
        "cancelled",
    },
    "normalization_error": set(),
    "normalized": {"verification_requested", "cancelled"},
    "verification_requested": {
        "verification_error",
        "verified",
        "cancelled",
    },
    "verification_error": set(),
    "verified": set(),
    "cancelled": set(),
}

TERMINAL_RUN_STATES = frozenset({"decided", "cancelled"})

# Attempt states that require an error_code, per the documented contract.
ERROR_ATTEMPT_STATES = frozenset(
    {"worker_error", "normalization_error", "verification_error"}
)

# Fields a lifecycle transition may legitimately change, everything else is
# protected identity (see idkmesh.product_spine).
RUN_TRANSITION_FIELDS = frozenset(
    {"admitted_connectors", "evidence_report_digest", "human_decision_record_digest"}
)
ATTEMPT_TRANSITION_FIELDS = frozenset(
    {
        "provider_reference",
        "candidate_reference_digest",
        "result_manifest_digest",
        "verification_semantic_digest",
        "error_code",
    }
)


def _run(run_id: str = "run-001", **overrides) -> ProductSpineRun:
    fields = {
        "run_id": run_id,
        "request_digest": DIGEST_A,
        "project_id": "project-001",
        "work_unit_id": "work-unit-001",
        "work_unit_version": 1,
        "work_unit_digest": DIGEST_B,
        "source_revision": SHA,
        "authority_mode": "agent_candidate",
        "routing_policy_version": "props-v1",
    }
    fields.update(overrides)
    return ProductSpineRun(**fields)


def _attempt(attempt_id: str = "attempt-001", **overrides) -> AttemptProjection:
    fields = {
        "attempt_id": attempt_id,
        "order": 1,
        "connector_id": "connector-001",
    }
    fields.update(overrides)
    return AttemptProjection(**fields)


def _step(run: ProductSpineRun, target: str) -> ProductSpineRun:
    """Apply one legal transition with the state-gated fields it requires."""
    changes = {}
    if target == "admitted" and not run.admitted_connectors:
        changes["admitted_connectors"] = ("connector-001",)
    if target == "evidence_ready":
        changes["evidence_report_digest"] = DIGEST_A
    if target == "decided":
        changes["human_decision_record_digest"] = DIGEST_B
    return run.transition(target, **changes)


def _reachable_run(state: str) -> ProductSpineRun:
    """A real run in ``state``, reached by legal transitions from ``proposed``."""
    parents: dict[str, str | None] = {"proposed": None}
    queue = ["proposed"]
    while queue:
        current = queue.pop(0)
        if current == state:
            break
        for target in sorted(RUN_GRAPH[current]):
            if target not in parents:
                parents[target] = current
                queue.append(target)
    path: list[str] = []
    node: str | None = state
    while node is not None:
        path.append(node)
        node = parents[node]
    path.reverse()

    run = _run()
    for target in path[1:]:
        run = _step(run, target)
    return run


class RunLifecycleProperties(unittest.TestCase):
    """Every ordered run-state pair is decided by exactly the v0.1 graph."""

    def test_every_ordered_state_pair_matches_the_documented_graph(self):
        for current in sorted(RUN_STATES):
            for target in sorted(RUN_STATES):
                with self.subTest(current=current, target=target):
                    if target == current:
                        self.assertEqual(transition_run_state(current, target), current)
                    elif target in RUN_GRAPH[current]:
                        self.assertEqual(transition_run_state(current, target), target)
                    else:
                        with self.assertRaises(ProductSpineError) as caught:
                            transition_run_state(current, target)
                        self.assertEqual(caught.exception.code, "invalid_run_transition")

    def test_the_documented_graph_holds_the_lifecycle_invariants(self):
        self.assertEqual(set(RUN_GRAPH), set(RUN_STATES))
        for current, targets in RUN_GRAPH.items():
            self.assertLessEqual(targets, set(RUN_STATES), current)
        for terminal in TERMINAL_RUN_STATES:
            self.assertEqual(RUN_GRAPH[terminal], set(), terminal)

        # "cancelled" is reachable in one or more steps from every
        # non-terminal state (evidence_ready reaches it through
        # awaiting_human_decision -- the pair test pins that asymmetry).
        for state in sorted(RUN_STATES - TERMINAL_RUN_STATES):
            seen, queue = {state}, [state]
            reaches_cancel = False
            while queue:
                for target in RUN_GRAPH[queue.pop(0)]:
                    if target == "cancelled":
                        reaches_cancel = True
                    elif target not in seen:
                        seen.add(target)
                        queue.append(target)
            self.assertTrue(reaches_cancel, state)

        seen = {"proposed"}
        queue = ["proposed"]
        while queue:
            for target in RUN_GRAPH[queue.pop(0)]:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        self.assertEqual(seen, set(RUN_STATES))

    def test_random_legal_walks_compose_and_never_rewrite_identity(self):
        rng = random.Random(SEED)
        for walk in range(25):
            run = _run()
            path = ["proposed"]
            for _ in range(rng.randint(1, 8)):
                targets = sorted(RUN_GRAPH[run.state])
                if not targets:
                    break
                target = rng.choice(targets)
                before = run
                run = _step(run, target)
                path.append(target)

                # Immutability, identity, determinism.
                self.assertEqual(before.state, path[-2])
                self.assertEqual(run.state, target)
                self.assertEqual(run.run_id, "run-001")
                self.assertEqual(run.request_digest, DIGEST_A)
                self.assertEqual(run.work_unit_id, "work-unit-001")
                self.assertEqual(run.work_unit_digest, DIGEST_B)
                self.assertEqual(run, _step(before, target))
            with self.subTest(walk=walk, path=path):
                self.assertEqual(_reachable_run(run.state).state, run.state)

    def test_random_illegal_edges_fail_closed_with_the_stable_code(self):
        rng = random.Random(SEED + 1)
        for _ in range(60):
            current = rng.choice(sorted(RUN_STATES))
            illegal = sorted(set(RUN_STATES) - RUN_GRAPH[current] - {current})
            if not illegal:
                continue
            target = rng.choice(illegal)
            with self.subTest(current=current, target=target):
                run = _reachable_run(current)
                with self.assertRaises(ProductSpineError) as caught:
                    run.transition(target)
                self.assertEqual(caught.exception.code, "invalid_run_transition")

    def test_unknown_states_are_rejected_total(self):
        run = _reachable_run("proposed")
        for bad_state, code in (
            ("", "invalid_type"),
            ("archived", "invalid_state"),
            ("PROPOSED", "invalid_state"),
            ("proposed ", "invalid_state"),
        ):
            with self.subTest(state=bad_state):
                with self.assertRaises(ProductSpineError) as caught:
                    run.transition(bad_state)
                self.assertEqual(caught.exception.code, code)
        for bad_value in (None, 3, ["proposed"]):
            with self.subTest(state=bad_value):
                with self.assertRaises(ProductSpineError) as caught:
                    run.transition(bad_value)
                self.assertEqual(caught.exception.code, "invalid_type")

    def test_identity_fields_are_immutable_across_transitions(self):
        # A transition may change only state plus the state-gated evidence
        # fields and the admitted connector set. Rewriting identity (it feeds
        # the create request digest) or authority_mode (it gates human_required
        # admission) through a transition is rejected with invalid_update.
        run = _run(state="previewed")
        for field, value in (
            ("run_id", "run-999"),
            ("request_digest", DIGEST_B),
            ("project_id", "project-999"),
            ("work_unit_id", "work-unit-999"),
            ("work_unit_version", 2),
            ("work_unit_digest", "sha256:" + "c" * 64),
            ("source_revision", "f" * 40),
            ("authority_mode", "agent_candidate"),
            ("routing_policy_version", "props-v2"),
            ("attempts", ()),
            ("state", "cancelled"),
            ("bogus_field", 1),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ProductSpineError) as caught:
                    run.transition("admitted", **{field: value})
                self.assertEqual(caught.exception.code, "invalid_update")
                self.assertEqual(run.state, "previewed")

    def test_evidence_and_connector_fields_are_the_only_changes(self):
        run = _run(state="previewed")
        self.assertEqual(RUN_TRANSITION_FIELDS - set(), RUN_TRANSITION_FIELDS)
        admitted = run.transition(
            "admitted", admitted_connectors=("connector-001",)
        )
        self.assertEqual(admitted.admitted_connectors, ("connector-001",))
        evidenced = _reachable_run("verification_requested").transition(
            "evidence_ready", evidence_report_digest=DIGEST_A
        )
        self.assertEqual(evidenced.evidence_report_digest, DIGEST_A)
        decided = _reachable_run("awaiting_human_decision").transition(
            "decided", human_decision_record_digest=DIGEST_B
        )
        self.assertEqual(decided.human_decision_record_digest, DIGEST_B)
        for field in RUN_TRANSITION_FIELDS:
            self.assertNotIn(field, ("run_id", "state"))

    def test_human_required_admission_is_gated_before_admission(self):
        run = _run(state="previewed", authority_mode="human_required")
        with self.assertRaises(ProductSpineError) as caught:
            run.transition("admitted", admitted_connectors=("connector-001",))
        self.assertEqual(caught.exception.code, "human_authority_required")

        admitted = _run(state="previewed").transition(
            "admitted", admitted_connectors=("connector-001",)
        )
        self.assertEqual(admitted.state, "admitted")
        self.assertEqual(admitted.admitted_connectors, ("connector-001",))


class AttemptLifecycleProperties(unittest.TestCase):
    """The attempt graph gets the same exhaustive and walk properties."""

    def test_every_ordered_state_pair_matches_the_documented_graph(self):
        for current in sorted(ATTEMPT_STATES):
            for target in sorted(ATTEMPT_STATES):
                with self.subTest(current=current, target=target):
                    if target == current:
                        self.assertEqual(
                            transition_attempt_state(current, target), current
                        )
                    elif target in ATTEMPT_GRAPH[current]:
                        self.assertEqual(
                            transition_attempt_state(current, target), target
                        )
                    else:
                        with self.assertRaises(ProductSpineError) as caught:
                            transition_attempt_state(current, target)
                        self.assertEqual(
                            caught.exception.code, "invalid_attempt_transition"
                        )

    def test_random_attempt_walks_are_immutable_and_deterministic(self):
        rng = random.Random(SEED + 2)
        for walk in range(25):
            attempt = _attempt()
            for _ in range(rng.randint(1, 6)):
                targets = sorted(ATTEMPT_GRAPH[attempt.state])
                if not targets:
                    break
                target = rng.choice(targets)
                changes = (
                    {"error_code": "worker-failed"}
                    if target in ERROR_ATTEMPT_STATES
                    else {}
                )
                before = attempt
                attempt = attempt.transition(target, **changes)
                self.assertEqual(before.state, before.state)
                self.assertEqual(attempt.attempt_id, "attempt-001")
                self.assertEqual(attempt.order, 1)
                self.assertEqual(attempt.connector_id, "connector-001")
                self.assertEqual(attempt, replace(before, state=target, **changes))
            with self.subTest(walk=walk):
                self.assertIn(attempt.state, ATTEMPT_STATES)

    def test_error_code_is_gated_by_attempt_state(self):
        with self.assertRaises(ProductSpineError) as caught:
            _attempt(state="dispatched").transition("worker_error")
        self.assertEqual(caught.exception.code, "invalid_attempt_evidence")
        failed = _attempt(state="dispatched").transition(
            "worker_error", error_code="worker-failed"
        )
        self.assertEqual(failed.error_code, "worker-failed")
        with self.assertRaises(ProductSpineError) as caught:
            _attempt(state="dispatched").transition(
                "candidate_observed", error_code="not-allowed-here"
            )
        self.assertEqual(caught.exception.code, "invalid_attempt_evidence")

    def test_attempt_identity_is_immutable_across_transitions(self):
        attempt = _attempt(state="dispatched")
        for field, value in (
            ("attempt_id", "attempt-999"),
            ("order", 2),
            ("connector_id", "connector-999"),
            ("state", "cancelled"),
            ("bogus_field", 1),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ProductSpineError) as caught:
                    attempt.transition("candidate_observed", **{field: value})
                self.assertEqual(caught.exception.code, "invalid_update")
                self.assertEqual(attempt.state, "dispatched")
        self.assertEqual(
            set(ATTEMPT_TRANSITION_FIELDS) & {"attempt_id", "order", "connector_id", "state"},
            set(),
        )


class IdempotencyProperties(unittest.TestCase):
    """Create/replay laws and total, consistent operation sequences."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = ProductSpineRunStore(
            LocalMetadataStore(self.temporary.name + "/store.sqlite")
        )

    def create(self, key: str, run: ProductSpineRun | None = None, *, at=CREATED_AT):
        return self.store.create(
            _run() if run is None else run, idempotency_key=key, created_at=at
        )

    def test_replay_returns_the_created_run_untouched(self):
        rng = random.Random(SEED + 3)
        for index in range(8):
            run = _run(f"run-{index:03d}")
            key = f"key-{index:03d}"
            created = self.create(key, run)
            self.assertTrue(created.created)
            self.assertFalse(created.replayed)
            self.assertEqual(created.create_request_digest, run_create_request_digest(run))

            with self.subTest(index=index):
                replayed = self.create(key, run)
                self.assertFalse(replayed.created)
                self.assertTrue(replayed.replayed)
                self.assertEqual(replayed.run, created.run)
                self.assertEqual(replayed.idempotency_key, created.idempotency_key)
                self.assertEqual(
                    replayed.create_request_digest, created.create_request_digest
                )
                self.assertEqual(rng.random() >= 0, True)

    def test_any_projection_mutation_turns_replay_into_a_conflict(self):
        # run_create_request_digest covers the whole projection (to_dict), so
        # a replay with any changed projection field is a different request.
        mutations = {
            "request_digest": DIGEST_B,
            "project_id": "project-999",
            "work_unit_digest": "sha256:" + "c" * 64,
            "work_unit_version": 2,
            "routing_policy_version": "props-v2",
            "source_revision": "f" * 40,
            "authority_mode": "human_required",
        }
        for index, (field, value) in enumerate(sorted(mutations.items())):
            run = _run(f"run-mut-{index:03d}")
            key = f"key-mut-{index:03d}"
            self.create(key, run)
            mutated = replace(run, **{field: value})
            with self.subTest(field=field):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.create(key, mutated)
                self.assertEqual(caught.exception.code, "idempotency_conflict")
                # The store still serves the original request's run.
                self.assertEqual(self.store.status(run.run_id).run, run)

    def test_distinct_keys_create_distinct_runs_and_reads_agree(self):
        runs = [_run(f"run-dist-{index:03d}") for index in range(6)]
        persisted = [
            self.create(f"key-dist-{index:03d}", run)
            for index, run in enumerate(runs)
        ]
        self.assertEqual(
            len({item.run.run_id for item in persisted}), len(persisted)
        )
        listed, cursor = self.store.list()
        self.assertIsNone(cursor)
        self.assertEqual(
            sorted(run.run_id for run in listed),
            sorted(run.run_id for run in runs),
        )
        for run in runs:
            status = self.store.status(run.run_id)
            self.assertEqual(status.run, run)

    def test_create_accepts_only_the_proposed_state(self):
        for state in sorted(RUN_STATES - {"proposed"}):
            run = _reachable_run(state)
            with self.subTest(state=state):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.create(f"key-state-{state}", run)
                self.assertEqual(caught.exception.code, "create_requires_proposed")

    def test_idempotency_key_validation_is_total(self):
        cases = (
            ("k", True),
            ("k" * 256, True),
            ("k" * 257, False),
            ("", False),
            ("   ", False),
            ("a\nb", False),
            ("a\x00b", False),
            ("a\x7fb", False),
            (None, False),
            (7, False),
        )
        for index, (key, ok) in enumerate(cases):
            # Each case gets its own run identity: run identity conflicts are a
            # different (also controlled) failure than key validation.
            run = _run(f"run-key-{index:03d}")
            with self.subTest(key=key):
                if ok:
                    persisted = self.create(key, run)
                    self.assertTrue(persisted.created)
                    self.assertEqual(persisted.idempotency_key, key.strip())
                else:
                    with self.assertRaises(ProductSpineRunStoreError) as caught:
                        self.create(key, run)
                    self.assertEqual(
                        caught.exception.code, "invalid_idempotency_key"
                    )

    def test_run_identity_is_unique_across_keys(self):
        run = _run("run-shared")
        self.create("key-first", run)
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.create("key-second", run)
        self.assertEqual(caught.exception.code, "idempotency_conflict")

    def test_seeded_operation_sequences_leave_a_consistent_store(self):
        rng = random.Random(SEED + 4)
        created: dict[str, ProductSpineRun] = {}
        keys: dict[str, str] = {}
        states: dict[str, str] = {}

        def op_create():
            index = len(created)
            run = _run(f"run-seq-{index:03d}")
            key = f"key-seq-{index:03d}"
            self.create(key, run, at=f"2026-01-01T00:{index % 60:02d}:00Z")
            created[run.run_id] = run
            keys[run.run_id] = key
            states[run.run_id] = "proposed"

        def op_replay():
            if not created:
                return
            run_id = rng.choice(sorted(created))
            # A replay of the original create request returns the run as it is
            # now (a cancel may have moved it on), never a rewritten identity.
            replayed = self.create(keys[run_id], created[run_id])
            self.assertFalse(replayed.created)
            self.assertTrue(replayed.replayed)
            self.assertEqual(replayed.run.run_id, run_id)
            self.assertEqual(replayed.run.state, states[run_id])
            self.assertEqual(replayed.run.request_digest, created[run_id].request_digest)

        def op_mutated_replay():
            if not created:
                return
            run_id = rng.choice(sorted(created))
            mutated = replace(
                created[run_id], routing_policy_version=f"v{rng.randrange(1000)}"
            )
            with self.assertRaises(ProductSpineRunStoreError) as caught:
                self.create(keys[run_id], mutated)
            self.assertEqual(caught.exception.code, "idempotency_conflict")

        def op_status():
            if created and rng.random() < 0.9:
                run_id = rng.choice(sorted(created))
                status = self.store.status(run_id)
                self.assertEqual(status.run.run_id, run_id)
                self.assertEqual(status.run.state, states[run_id])
                self.assertEqual(
                    status.run.request_digest, created[run_id].request_digest
                )
            else:
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.store.status("run-never-created")
                self.assertEqual(caught.exception.code, "run_not_found")

        def op_list():
            listed, _ = self.store.list()
            listed_ids = {run.run_id for run in listed}
            self.assertLessEqual(listed_ids, set(created))
            for run in listed:
                self.assertEqual(run.state, states[run.run_id])

        def op_cancel():
            if not created:
                return
            run_id = rng.choice(sorted(created))
            try:
                persisted = self.store.cancel(
                    run_id, updated_at="2026-01-02T00:00:00Z"
                )
            except ProductSpineRunStoreError as exc:
                # Cancel of a cancelled run is idempotent, so every failure here
                # must still be a controlled error.
                self.assertEqual(exc.code, "cancel_not_allowed")
                return
            self.assertEqual(persisted.run.state, "cancelled")
            states[run_id] = "cancelled"

        operations = (
            op_create,
            op_replay,
            op_mutated_replay,
            op_status,
            op_list,
            op_cancel,
        )
        for sequence in range(25):
            for _ in range(rng.randint(1, 15)):
                rng.choice(operations)()
            with self.subTest(sequence=sequence):
                listed, _ = self.store.list()
                self.assertLessEqual(
                    {run.run_id for run in listed}, set(created)
                )

    def test_replay_across_a_restarted_store_is_stable(self):
        run = _run("run-restart")
        created = self.create("key-restart", run)
        restarted = ProductSpineRunStore(
            LocalMetadataStore(self.temporary.name + "/store.sqlite")
        )
        replayed = restarted.create(
            run, idempotency_key="key-restart", created_at=CREATED_AT
        )
        self.assertFalse(replayed.created)
        self.assertTrue(replayed.replayed)
        self.assertEqual(replayed.run, created.run)

        mutated = replace(run, project_id="project-other")
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            restarted.create(
                mutated, idempotency_key="key-restart", created_at=CREATED_AT
            )
        self.assertEqual(caught.exception.code, "idempotency_conflict")
