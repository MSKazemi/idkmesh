from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import (
    ProductSpineRunStore,
    ProductSpineRunStoreError,
    run_create_request_digest,
)


SHA = "0123456789abcdef0123456789abcdef01234567"


def _run(**overrides):
    values = {
        "run_id": "run/cli-1",
        "request_digest": "sha256:" + "a" * 64,
        "project_id": "project.test",
        "work_unit_id": "work/test-1",
        "work_unit_version": 1,
        "work_unit_digest": "sha256:" + "b" * 64,
        "source_revision": SHA,
        "authority_mode": "agent_candidate",
        "routing_policy_version": "c1-v0.1",
        "state": "proposed",
    }
    values.update(overrides)
    return ProductSpineRun(**values)


class ProductSpineRunStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite"
        self.service = ProductSpineRunStore(
            LocalMetadataStore(self.path)
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_create_persists_strict_proposed_projection(self):
        run = _run()
        result = self.service.create(
            run,
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        self.assertTrue(result.created)
        self.assertFalse(result.replayed)
        self.assertEqual(result.run, run)
        self.assertEqual(
            result.create_request_digest,
            run_create_request_digest(run),
        )
        projection = result.to_dict()
        self.assertFalse(
            projection["provider_execution_terminated"]
        )
        self.assertFalse(projection["candidate_accepted"])
        self.assertFalse(projection["merge_authority"])

    def test_exact_replay_after_restart_returns_existing_run(self):
        first = self.service.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        restarted = ProductSpineRunStore(
            LocalMetadataStore(self.path)
        )
        second = restarted.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:31:00Z",
        )
        self.assertFalse(second.created)
        self.assertTrue(second.replayed)
        self.assertEqual(second.run, first.run)

    def test_same_key_with_changed_projection_conflicts(self):
        self.service.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "idempotency",
        ):
            self.service.create(
                _run(project_id="project.changed"),
                idempotency_key="cli-request-1",
                created_at="2026-09-24T15:31:00Z",
            )

    def test_create_rejects_non_proposed_projection(self):
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "proposed",
        ):
            self.service.create(
                _run(
                    state="previewed",
                ),
                idempotency_key="cli-request-1",
                created_at="2026-09-24T15:30:00Z",
            )

    def test_status_reconstructs_strict_projection(self):
        self.service.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        status = self.service.status("run/cli-1")
        self.assertEqual(status.run.state, "proposed")
        self.assertEqual(
            status.idempotency_key,
            "cli-request-1",
        )

    def test_cancel_uses_product_spine_transition_and_is_idempotent(self):
        self.service.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        first = self.service.cancel(
            "run/cli-1",
            updated_at="2026-09-24T15:31:00Z",
        )
        self.assertEqual(first.run.state, "cancelled")
        self.assertFalse(first.to_dict()["provider_execution_terminated"])

        second = self.service.cancel(
            "run/cli-1",
            updated_at="2026-09-24T15:32:00Z",
        )
        self.assertEqual(second.run.state, "cancelled")

    def test_cancel_rejects_terminal_decided_run(self):
        decided = _run(
            state="decided",
            admitted_connectors=("agent-a",),
            evidence_report_digest="sha256:" + "c" * 64,
            human_decision_record_digest="sha256:" + "d" * 64,
        )
        # Model an already-retained canonical run without using create(), which
        # intentionally accepts only proposed state.
        digest = run_create_request_digest(decided)
        LocalMetadataStore(self.path).admit_run(
            run_id=decided.run_id,
            idempotency_key="product-spine-cli:create:terminal",
            request_digest=digest,
            state=decided.state,
            metadata={
                "schema_version": "0.1",
                "kind": "product-spine-cli-run",
                "create_request_digest": digest,
                "product_spine_request_digest": (
                    decided.request_digest
                ),
                "projection": decided.to_dict(),
            },
            created_at="2026-09-24T15:30:00Z",
        )
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "cancel",
        ):
            self.service.cancel(
                decided.run_id,
                updated_at="2026-09-24T15:31:00Z",
            )

    def test_unknown_and_foreign_run_fail_closed(self):
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "unknown run_id",
        ):
            self.service.status("run/missing")

        LocalMetadataStore(self.path).admit_run(
            run_id="run/foreign",
            idempotency_key="foreign",
            request_digest="sha256:" + "e" * 64,
            state="proposed",
            metadata={"kind": "other"},
            created_at="2026-09-24T15:30:00Z",
        )
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "not a C7-D",
        ):
            self.service.status("run/foreign")

    def test_tampered_projection_state_is_detected(self):
        self.service.create(
            _run(),
            idempotency_key="cli-request-1",
            created_at="2026-09-24T15:30:00Z",
        )
        store = LocalMetadataStore(self.path)
        record = store.get_run("run/cli-1")
        metadata = dict(record.metadata)
        projection = dict(metadata["projection"])
        projection["state"] = "previewed"
        metadata["projection"] = projection
        store.update_run(
            "run/cli-1",
            state="proposed",
            metadata=metadata,
            updated_at="2026-09-24T15:31:00Z",
        )
        with self.assertRaisesRegex(
            ProductSpineRunStoreError,
            "state differs",
        ):
            self.service.status("run/cli-1")

    def test_list_paginates_deterministically_and_matches_status(self):
        for i in range(3):
            self.service.create(
                _run(run_id=f"run/list-{i}"),
                idempotency_key=f"list-key-{i}",
                created_at="2026-09-24T15:30:00Z",
            )

        page1, cursor1 = self.service.list(limit=2)
        self.assertEqual(
            [run.run_id for run in page1], ["run/list-0", "run/list-1"]
        )
        self.assertIsNotNone(cursor1)

        page2, cursor2 = self.service.list(limit=2, cursor=cursor1)
        self.assertEqual([run.run_id for run in page2], ["run/list-2"])
        self.assertIsNone(cursor2)

        # The service and CLI/HTTP surfaces must never disagree about one
        # run's shape: a listed run is exactly what status() returns.
        self.assertEqual(
            page1[0].to_dict(),
            self.service.status("run/list-0").run.to_dict(),
        )

    def test_list_rejects_a_cursor_this_service_did_not_issue(self):
        with self.assertRaisesRegex(
            ProductSpineRunStoreError, "not a value this service issued"
        ):
            self.service.list(cursor="not-base64-json")

    def test_list_rejects_a_forged_but_validly_encoded_cursor(self):
        import base64
        import json

        forged = base64.urlsafe_b64encode(
            json.dumps({"kind": "some-other-kind", "after": "x"}).encode()
        ).decode("ascii")
        with self.assertRaisesRegex(
            ProductSpineRunStoreError, "not a value this service issued"
        ):
            self.service.list(cursor=forged)

    def test_list_of_an_empty_store_returns_no_runs_and_no_cursor(self):
        runs, cursor = self.service.list()
        self.assertEqual(runs, [])
        self.assertIsNone(cursor)

    def test_list_filters_by_project_id(self):
        self.service.create(
            _run(run_id="run/alpha-1", project_id="project.alpha"),
            idempotency_key="k1", created_at="2026-09-24T15:30:00Z",
        )
        self.service.create(
            _run(run_id="run/beta-1", project_id="project.beta"),
            idempotency_key="k2", created_at="2026-09-24T15:30:00Z",
        )

        runs, _ = self.service.list(project_id="project.alpha")
        self.assertEqual([r.run_id for r in runs], ["run/alpha-1"])

    def test_list_rejects_an_unrecognized_state(self):
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.list(state="not-a-real-state")
        self.assertEqual(ctx.exception.code, "invalid_state")

    def test_list_filters_by_a_recognized_state(self):
        self.service.create(
            _run(run_id="run/gamma-1"),
            idempotency_key="k3", created_at="2026-09-24T15:30:00Z",
        )
        runs, _ = self.service.list(state="proposed")
        self.assertEqual([r.run_id for r in runs], ["run/gamma-1"])
        runs, _ = self.service.list(state="cancelled")
        self.assertEqual(runs, [])


    def _seed_work_units(self):
        for index, (run_id, wu, version) in enumerate(
            [
                ("run/w-1", "work/a", 1),
                ("run/w-2", "work/a", 2),
                ("run/w-3", "work/b", 1),
                ("run/w-4", "work/c", 1),
            ]
        ):
            self.service.create(
                _run(
                    run_id=run_id,
                    work_unit_id=wu,
                    work_unit_version=version,
                    project_id="project.alpha" if wu != "work/c" else "project.beta",
                ),
                idempotency_key=f"wu-{index}",
                created_at="2026-10-01T00:00:00Z",
            )

    def test_list_work_units_derives_resources_from_runs(self):
        self._seed_work_units()

        items, next_cursor = self.service.list_work_units()

        self.assertIsNone(next_cursor)
        self.assertEqual([i["id"] for i in items], ["work/a", "work/b", "work/c"])
        self.assertEqual(items[0]["run_count"], 2)
        self.assertEqual(
            [r["version"] for r in items[0]["revisions"]], [1, 2]
        )

    def test_list_work_units_paginates_and_filters_by_project(self):
        self._seed_work_units()

        page1, cursor = self.service.list_work_units(limit=2)
        page2, last = self.service.list_work_units(limit=2, cursor=cursor)

        self.assertEqual([i["id"] for i in page1], ["work/a", "work/b"])
        self.assertEqual([i["id"] for i in page2], ["work/c"])
        self.assertIsNone(last)
        beta, _ = self.service.list_work_units(project_id="project.beta")
        self.assertEqual([i["id"] for i in beta], ["work/c"])

    def test_work_unit_cursor_rejects_a_run_list_cursor(self):
        self._seed_work_units()
        _, run_cursor = self.service.list(limit=1)
        self.assertIsNotNone(run_cursor)

        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.list_work_units(cursor=run_cursor)

        self.assertEqual(ctx.exception.code, "invalid_cursor")

    def test_list_work_units_rejects_a_bad_limit_and_garbage_cursor(self):
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.list_work_units(limit=0)
        self.assertEqual(ctx.exception.code, "invalid_limit")
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.list_work_units(cursor="not-a-cursor")
        self.assertEqual(ctx.exception.code, "invalid_cursor")

    def test_get_work_unit_found_and_not_found(self):
        self._seed_work_units()

        resource = self.service.get_work_unit("work/a")
        self.assertEqual(resource["run_count"], 2)

        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.get_work_unit("work/missing")
        self.assertEqual(ctx.exception.code, "work_unit_not_found")
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.get_work_unit("")
        self.assertEqual(ctx.exception.code, "invalid_work_unit_id")

    def test_work_unit_read_model_carries_no_selection_or_body(self):
        self._seed_work_units()

        resource = self.service.get_work_unit("work/a")

        self.assertEqual(set(resource), {"id", "run_count", "revisions"})
        for forbidden in ("latest", "current", "preferred", "body"):
            self.assertNotIn(forbidden, resource)


    def test_get_project_zero_fills_every_canonical_state(self):
        from idkmesh.product_spine import RUN_STATES

        self._seed_work_units()

        project = self.service.get_project("project.alpha")

        self.assertEqual(
            set(project),
            {"project_id", "run_count", "runs_by_state", "work_unit_count"},
        )
        self.assertEqual(project["run_count"], 3)
        self.assertEqual(project["work_unit_count"], 2)
        self.assertEqual(set(project["runs_by_state"]), set(RUN_STATES))
        self.assertEqual(project["runs_by_state"]["proposed"], 3)
        self.assertEqual(project["runs_by_state"]["cancelled"], 0)
        self.assertEqual(
            sum(project["runs_by_state"].values()), project["run_count"]
        )

    def test_get_project_reflects_a_state_change(self):
        self._seed_work_units()
        self.service.cancel("run/w-1", updated_at="2026-10-01T01:00:00Z")

        project = self.service.get_project("project.alpha")

        self.assertEqual(project["runs_by_state"]["proposed"], 2)
        self.assertEqual(project["runs_by_state"]["cancelled"], 1)

    def test_get_project_not_found_and_invalid(self):
        self._seed_work_units()
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.get_project("project.missing")
        self.assertEqual(ctx.exception.code, "project_not_found")
        with self.assertRaises(ProductSpineRunStoreError) as ctx:
            self.service.get_project("")
        self.assertEqual(ctx.exception.code, "invalid_project_id")

    def test_project_read_model_carries_no_rollup(self):
        self._seed_work_units()
        project = self.service.get_project("project.alpha")
        for forbidden in ("health", "status", "score", "latest", "state"):
            self.assertNotIn(forbidden, project)


if __name__ == "__main__":
    unittest.main()
