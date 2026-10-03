"""Store/service tests for retained run evidence and mixed-store run reads.

Covers ADR-0024: ``ProductSpineRunStore.get_run_evidence`` serves the evidence
report an idempotent offline run retained, after re-verifying its digest;
``status``/``list`` read the offline result kind as well as CLI runs; and the
run list is restricted to Product Spine kinds so a foreign row in the shared
``runs`` table can no longer break the page or its pagination.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_idempotency import (
    IdempotentOfflineProductSpineService,
)
from idkmesh.product_spine_run_store import (
    ProductSpineRunStore,
    ProductSpineRunStoreError,
)
from idkmesh.work_unit_binding import canonical_digest


def _load_sibling(name: str):
    """Import a sibling test module by path (``tests/`` is not a package)."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_idem = _load_sibling("test_product_spine_idempotency")

CREATED = "2026-10-02T00:00:00Z"
SOURCE = "0123456789abcdef0123456789abcdef01234567"
ADMISSION_KIND = "product-spine-idempotency-admission"
TAMPER_MARKER = "TAMPERED-MARKER-do-not-serve"


# ---- shared helpers (also imported by tests/test_control_tower_run_evidence) --


def seed_offline_run(db: Path, root: Path, *, key: str = "idem/offline-run"):
    """Run the idempotent offline spine once; returns its persisted result.

    The completed row retains the full evidence report next to a projection
    whose ``evidence_report_digest`` it must equal.
    """
    work = _idem._work_unit()
    attempt = _idem._attempt(work, root / "candidate-a")
    wrapper = IdempotentOfflineProductSpineService(
        service=_idem._offline_service([]),
        store=LocalMetadataStore(db),
    )
    return _idem._execute(wrapper, work=work, attempt=attempt, key=key)


def cli_run(run_id: str = "run/cli-1", project_id: str = "project.test"):
    return ProductSpineRun(
        run_id=run_id,
        request_digest="sha256:" + "a" * 64,
        project_id=project_id,
        work_unit_id="work/test-1",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SOURCE,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


def rewrite_metadata(db: Path, run_id: str, mutate) -> None:
    """Edit a stored row's metadata in place (simulates tampering/corruption)."""
    conn = sqlite3.connect(db)
    try:
        with conn:
            row = conn.execute(
                "SELECT metadata_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            assert row is not None, f"no such run row: {run_id}"
            metadata = json.loads(row[0])
            mutate(metadata)
            conn.execute(
                "UPDATE runs SET metadata_json = ? WHERE run_id = ?",
                (json.dumps(metadata), run_id),
            )
    finally:
        conn.close()


def add_foreign_rows(store: LocalMetadataStore) -> list[str]:
    """Rows in the shared ``runs`` table that are not Product Spine runs."""
    ids = []
    # Admission-only reservation (the offline service crashed before finishing).
    store.admit_run(
        run_id="a-foreign-admission",
        idempotency_key="foreign-key-a",
        request_digest="sha256:" + "1" * 64,
        state="proposed",
        metadata={"schema_version": "0.1", "kind": ADMISSION_KIND},
        created_at=CREATED,
    )
    ids.append("a-foreign-admission")
    # Execution-error row written by the offline idempotent service.
    store.admit_run(
        run_id="p-foreign-error",
        idempotency_key="foreign-key-p",
        request_digest="sha256:" + "2" * 64,
        state="proposed",
        metadata={"schema_version": "0.1", "kind": ADMISSION_KIND},
        created_at=CREATED,
    )
    store.update_run(
        "p-foreign-error",
        state="execution_error",
        metadata={
            "schema_version": "0.1",
            "kind": ADMISSION_KIND,
            "phase": "execution_error",
            "error_code": "synthetic",
        },
        updated_at=CREATED,
    )
    ids.append("p-foreign-error")
    # A different writer family sharing the table (GitHub dispatch).
    store.admit_run(
        run_id="y-foreign-github",
        idempotency_key="foreign-key-y",
        request_digest="sha256:" + "3" * 64,
        state="dispatched",
        metadata={"schema_version": "0.1", "kind": "github-explicit-dispatch-result"},
        created_at=CREATED,
    )
    ids.append("y-foreign-github")
    # A row with no kind at all.
    store.admit_run(
        run_id="z-foreign-nokind",
        idempotency_key="foreign-key-z",
        request_digest="sha256:" + "4" * 64,
        state="proposed",
        metadata={"anything": "else"},
        created_at=CREATED,
    )
    ids.append("z-foreign-nokind")
    return ids


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-run-evidence-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "state.sqlite"
        self.store = LocalMetadataStore(self.db)
        self.service = ProductSpineRunStore(self.store)


class RunEvidenceServiceTests(_StoreCase):
    def test_returns_the_retained_report_byte_for_byte_with_its_digest(self) -> None:
        result = seed_offline_run(self.db, self.root)

        served = self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(
            set(served),
            {"run_id", "evidence_report_digest", "evidence_report"},
        )
        self.assertEqual(served["run_id"], result.run.run_id)
        self.assertEqual(served["evidence_report"], result.evidence_report)
        self.assertEqual(
            json.dumps(served["evidence_report"], sort_keys=True),
            json.dumps(result.evidence_report, sort_keys=True),
        )
        self.assertEqual(
            served["evidence_report_digest"], result.run.evidence_report_digest
        )
        self.assertEqual(
            canonical_digest(served["evidence_report"]),
            served["evidence_report_digest"],
        )

    def test_a_cli_created_run_has_no_evidence(self) -> None:
        self.service.create(
            cli_run(), idempotency_key="cli-1", created_at=CREATED
        )

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence("run/cli-1")

        self.assertEqual(caught.exception.code, "evidence_not_available")

    def test_a_null_projection_digest_means_not_available(self) -> None:
        result = seed_offline_run(self.db, self.root)

        def clear_digest(metadata):
            metadata["projection"]["evidence_report_digest"] = None

        rewrite_metadata(self.db, result.run.run_id, clear_digest)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_not_available")

    def test_a_missing_retained_report_means_not_available(self) -> None:
        result = seed_offline_run(self.db, self.root)
        rewrite_metadata(
            self.db,
            result.run.run_id,
            lambda metadata: metadata.pop("evidence_report"),
        )

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_not_available")

    def test_unknown_and_invalid_run_ids(self) -> None:
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence("offline/never-created")
        self.assertEqual(caught.exception.code, "run_not_found")
        for bad in ("", 123, None):
            with self.assertRaises(ProductSpineRunStoreError) as caught:
                self.service.get_run_evidence(bad)
            self.assertEqual(caught.exception.code, "invalid_run_id", repr(bad))

    def test_an_altered_report_fails_closed_and_is_never_served(self) -> None:
        result = seed_offline_run(self.db, self.root)

        def alter(metadata):
            metadata["evidence_report"]["warnings"].append(TAMPER_MARKER)

        rewrite_metadata(self.db, result.run.run_id, alter)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_integrity_error")
        self.assertNotIn(TAMPER_MARKER, str(caught.exception))

    def test_a_report_that_is_not_an_object_fails_closed(self) -> None:
        result = seed_offline_run(self.db, self.root)

        def replace(metadata):
            metadata["evidence_report"] = "not an object"

        rewrite_metadata(self.db, result.run.run_id, replace)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_integrity_error")

    def test_an_invalid_projection_fails_closed(self) -> None:
        result = seed_offline_run(self.db, self.root)

        def break_projection(metadata):
            metadata["projection"]["state"] = "no-such-state"

        rewrite_metadata(self.db, result.run.run_id, break_projection)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_integrity_error")

    def test_a_replaced_but_internally_consistent_report_is_still_refused(self) -> None:
        # Swapping in a different report whose own digest is valid still fails:
        # it must equal the digest the run projection committed to.
        result = seed_offline_run(self.db, self.root)

        def swap(metadata):
            other = dict(metadata["evidence_report"])
            other["warnings"] = ["a different but well-formed report"]
            metadata["evidence_report"] = other

        rewrite_metadata(self.db, result.run.run_id, swap)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(result.run.run_id)

        self.assertEqual(caught.exception.code, "evidence_integrity_error")


class OfflineRunReadTests(_StoreCase):
    def test_status_restores_an_offline_result_row(self) -> None:
        result = seed_offline_run(self.db, self.root)
        record = self.store.get_run(result.run.run_id)
        assert record is not None

        persisted = self.service.status(result.run.run_id)

        self.assertEqual(persisted.run.run_id, result.run.run_id)
        self.assertEqual(persisted.run.to_dict(), result.run.to_dict())
        self.assertEqual(persisted.create_request_digest, record.request_digest)
        self.assertEqual(persisted.idempotency_key, "idem/offline-run")
        self.assertFalse(persisted.created)
        self.assertFalse(persisted.replayed)

    def test_status_refuses_an_offline_row_with_a_mismatched_digest(self) -> None:
        result = seed_offline_run(self.db, self.root)

        def break_digest(metadata):
            metadata["idempotency_request_digest"] = "sha256:" + "0" * 64

        rewrite_metadata(self.db, result.run.run_id, break_digest)

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.status(result.run.run_id)

        self.assertEqual(caught.exception.code, "persisted_state_corrupt")

    def test_status_still_refuses_a_row_that_is_not_a_product_spine_run(self) -> None:
        add_foreign_rows(self.store)

        for run_id in ("a-foreign-admission", "y-foreign-github", "z-foreign-nokind"):
            with self.assertRaises(ProductSpineRunStoreError) as caught:
                self.service.status(run_id)
            self.assertEqual(
                caught.exception.code, "not_product_spine_cli_run", run_id
            )

    def test_cli_runs_are_unchanged_by_the_tolerant_restore(self) -> None:
        created = self.service.create(
            cli_run(), idempotency_key="cli-1", created_at=CREATED
        )

        status = self.service.status("run/cli-1")

        self.assertEqual(status.run, created.run)
        self.assertEqual(
            status.create_request_digest, created.create_request_digest
        )
        self.assertEqual(status.idempotency_key, "cli-1")


class MixedStoreListTests(_StoreCase):
    def _seed_mixed(self):
        offline = seed_offline_run(self.db, self.root)
        self.service.create(
            cli_run(), idempotency_key="cli-1", created_at=CREATED
        )
        foreign = add_foreign_rows(self.store)
        return offline.run.run_id, "run/cli-1", foreign

    def test_list_returns_only_product_spine_runs_in_run_id_order(self) -> None:
        offline_id, cli_id, _ = self._seed_mixed()

        runs, next_cursor = self.service.list()

        self.assertEqual([run.run_id for run in runs], sorted([offline_id, cli_id]))
        self.assertIsNone(next_cursor)

    def test_list_does_not_fail_when_foreign_rows_are_present(self) -> None:
        # Before ADR-0024 one foreign row raised for the whole page.
        self._seed_mixed()

        runs, _ = self.service.list(limit=200)

        self.assertEqual(len(runs), 2)

    def test_keyset_paging_across_foreign_rows_yields_each_run_exactly_once(self) -> None:
        offline_id, cli_id, _ = self._seed_mixed()

        seen: list[str] = []
        cursor = None
        pages = 0
        while True:
            runs, cursor = self.service.list(limit=1, cursor=cursor)
            seen.extend(run.run_id for run in runs)
            pages += 1
            self.assertLessEqual(pages, 5, "paging did not terminate")
            if cursor is None:
                break

        self.assertEqual(seen, sorted([offline_id, cli_id]))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(pages, 2)

    def test_admission_only_and_execution_error_rows_are_excluded(self) -> None:
        self._seed_mixed()
        listed = {run.run_id for run in self.service.list(limit=200)[0]}

        for foreign in (
            "a-foreign-admission",
            "p-foreign-error",
            "y-foreign-github",
            "z-foreign-nokind",
        ):
            self.assertNotIn(foreign, listed)

    def test_state_and_project_filters_compose_with_the_kind_restriction(self) -> None:
        offline_id, cli_id, _ = self._seed_mixed()

        by_state, _ = self.service.list(state="awaiting_human_decision")
        self.assertEqual([run.run_id for run in by_state], [offline_id])

        by_project, _ = self.service.list(project_id="MSKazemi/idkmesh")
        self.assertEqual([run.run_id for run in by_project], [offline_id])

        cli_only, _ = self.service.list(project_id="project.test")
        self.assertEqual([run.run_id for run in cli_only], [cli_id])

        both, _ = self.service.list(
            state="awaiting_human_decision", project_id="project.test"
        )
        self.assertEqual(both, [])

        # A foreign row's state never leaks through a state filter.
        # (execution_error is not a canonical run state, so the service
        # rejects it; the store-level filter composes and returns nothing.)
        with self.assertRaises(ProductSpineRunStoreError) as invalid:
            self.service.list(state="execution_error")
        self.assertEqual(invalid.exception.code, "invalid_state")
        errored, _ = self.store.list_runs(
            state="execution_error",
            kinds=("product-spine-cli-run", "product-spine-idempotency-result"),
        )
        self.assertEqual(errored, [])

    def test_list_matches_status_for_every_listed_run(self) -> None:
        self._seed_mixed()

        for run in self.service.list(limit=200)[0]:
            self.assertEqual(self.service.status(run.run_id).run, run)


class ListRunsKindsTests(_StoreCase):
    def test_kinds_must_be_a_non_empty_tuple_of_non_empty_strings(self) -> None:
        for bad in ((), [], ["product-spine-cli-run"], "product-spine-cli-run", ("",)):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.store.list_runs(kinds=bad)

    def test_kinds_restricts_to_the_named_kinds(self) -> None:
        seed_offline_run(self.db, self.root)
        self.service.create(
            cli_run(), idempotency_key="cli-1", created_at=CREATED
        )
        add_foreign_rows(self.store)

        cli_only, _ = self.store.list_runs(kinds=("product-spine-cli-run",))
        self.assertEqual([record.run_id for record in cli_only], ["run/cli-1"])

        foreign, _ = self.store.list_runs(
            kinds=("github-explicit-dispatch-result",)
        )
        self.assertEqual([record.run_id for record in foreign], ["y-foreign-github"])

    def test_kinds_none_keeps_the_unrestricted_listing(self) -> None:
        seed_offline_run(self.db, self.root)
        add_foreign_rows(self.store)

        everything, _ = self.store.list_runs(limit=200)

        self.assertEqual(len(everything), 1 + 4)

    def test_kinds_composes_with_after_state_and_project(self) -> None:
        seed_offline_run(self.db, self.root)
        self.service.create(
            cli_run(), idempotency_key="cli-1", created_at=CREATED
        )
        kinds = ("product-spine-cli-run", "product-spine-idempotency-result")

        first, more = self.store.list_runs(limit=1, kinds=kinds)
        self.assertTrue(more)
        second, more = self.store.list_runs(
            limit=1, kinds=kinds, after=first[0].run_id
        )
        self.assertFalse(more)
        self.assertNotEqual(first[0].run_id, second[0].run_id)

        proposed, _ = self.store.list_runs(kinds=kinds, state="proposed")
        self.assertEqual([record.run_id for record in proposed], ["run/cli-1"])


if __name__ == "__main__":
    unittest.main()
