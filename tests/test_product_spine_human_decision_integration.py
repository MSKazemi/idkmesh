"""End-to-end evidence-to-decision seam of the Product Spine (#682 P0-H).

Drives the real modules together, with no stubs between them:

    idempotent offline spine -> SQLite run store
      -> ``idkmesh run evidence`` (CLI)           \\
      -> Control Tower HTTP + ControlTowerClient   > the same evidence digest
      -> HumanDecisionService -> append-only decision store

What it pins that no single-module suite does: the digest a human is shown by the
Control Tower (and by the CLI) is the digest the Human Decision service accepts;
a stale or swapped digest fails closed with nothing persisted; and recording a
decision is an authority-free write to the *decision* store only: the run row,
its events, and the served evidence are byte-for-byte unchanged and no process
(and so no ``git``) is spawned.

It deliberately does NOT assert that the run reaches ``decided``. Nothing moves
a persisted run out of ``awaiting_human_decision`` yet (ADR-0024 keeps offline
rows read-only, and the HTTP/authority adapter is still owed by #740), so the
test pins the current boundary instead of inventing the missing transition.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh.api_client import ControlTowerClient
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import create_server
from idkmesh.enterprise_authz import ActorContext
from idkmesh.human_decision_service import (
    HumanDecisionService,
    HumanDecisionServiceError,
    HumanDecisionStore,
)
from idkmesh.product_spine_run_store import ProductSpineRunStore
from idkmesh.tenant_scope import TenantScope
from idkmesh.work_unit_binding import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
EVALUATED_AT_EPOCH = 1_780_000_000
DECIDED_AT = "2026-10-08T00:00:00Z"


def _load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_spine_decision_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_helpers = _load_sibling("test_run_evidence_store")


def _human() -> ActorContext:
    return ActorContext(
        principal_id="reviewer@example.com",
        actor_type="human",
        issuer="tests",
        roles=frozenset({"reviewer"}),
        scopes=(TenantScope(tenant_id="tenant.test", project_id="project.test"),),
        data_clearance="internal",
        identity_revision="test-v1",
    )


class ProductSpineEvidenceToDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-spine-decision-")
        cls.root = Path(cls._tmp.name)
        cls.run_db = cls.root / "runs.sqlite3"
        cls.seeded = _helpers.seed_offline_run(cls.run_db, cls.root, key="idem/e2e-a")
        cls.other = _helpers.seed_offline_run(cls.run_db, cls.root, key="idem/e2e-b")
        cls.server = create_server(port=0, product_spine_store_path=str(cls.run_db))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls._tmp.cleanup()

    def setUp(self) -> None:
        self.run_id = self.seeded.run.run_id
        self.runs = ProductSpineRunStore(LocalMetadataStore(self.run_db))
        self.decisions = HumanDecisionStore(self.root / f"{self.id()}.decisions.sqlite3")
        self.service = HumanDecisionService(
            evidence_reader=self.runs, store=self.decisions
        )
        self.client = ControlTowerClient(
            f"http://127.0.0.1:{self.server.server_port}",
            self.server.ui_token,
            timeout=5.0,
        )

    # ---- helpers ---------------------------------------------------------------

    def cli_evidence(self, run_id: str) -> dict:
        out = io.StringIO()
        with contextlib.chdir(ROOT), contextlib.redirect_stdout(out):
            code = cli.main(
                ["run", "evidence", run_id, "--store", str(self.run_db), "--json"]
            )
        self.assertEqual(code, 0)
        return json.loads(out.getvalue())

    def request_for(self, evidence: dict, **overrides) -> dict:
        report = evidence["evidence_report"]
        value = {
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-request",
            "evidence_report": {
                "kind": report["kind"],
                "schema_version": report["schema_version"],
                "run_id": evidence["run_id"],
                "digest": evidence["evidence_report_digest"],
            },
            "selected_attempt_id": report["attempts"][0]["attempt_id"],
            "decision": "accept",
            "rationale": "The selected attempt is supported by the retained evidence.",
        }
        value.update(overrides)
        return value

    def record(self, request: dict, *, key: str = "e2e-decision-1"):
        return self.service.record(
            request,
            idempotency_key=key,
            actor=_human(),
            decided_at=DECIDED_AT,
            evaluated_at_epoch=EVALUATED_AT_EPOCH,
        )

    def run_snapshot(self) -> dict:
        conn = sqlite3.connect(self.run_db)
        try:
            rows = conn.execute("SELECT * FROM runs ORDER BY run_id").fetchall()
        finally:
            conn.close()
        events, _ = self.runs.list_events(limit=200)
        return {"rows": rows, "events": events}

    # ---- the happy path --------------------------------------------------------

    def test_the_digest_shown_by_cli_and_control_tower_is_the_digest_a_decision_binds(
        self,
    ) -> None:
        shown_by_cli = self.cli_evidence(self.run_id)
        shown_by_http = self.client.get_run_evidence(self.run_id).value

        self.assertEqual(
            shown_by_cli["evidence_report_digest"],
            shown_by_http["evidence_report_digest"],
        )
        self.assertEqual(
            shown_by_http["evidence_report_digest"],
            self.seeded.run.evidence_report_digest,
        )

        result = self.record(self.request_for(shown_by_http))
        record = result.decision_record

        self.assertTrue(result.created)
        self.assertEqual(
            record["evidence_report"]["digest"],
            shown_by_http["evidence_report_digest"],
        )
        self.assertEqual(record["evidence_report"]["run_id"], self.run_id)
        self.assertEqual(record["decision"], "accept")
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )
        # Replayable and inspectable: the stored record is exactly what was returned.
        self.assertEqual(self.decisions.list_for_run(self.run_id), [record])
        self.assertEqual(self.record(self.request_for(shown_by_http)).decision_record, record)
        self.assertEqual(len(self.decisions.list_for_run(self.run_id)), 1)

    def test_every_decision_value_binds_the_same_evidence_digest(self) -> None:
        evidence = self.client.get_run_evidence(self.run_id).value
        digests = set()
        for index, decision in enumerate(("accept", "reject", "escalate")):
            result = self.record(
                self.request_for(evidence, decision=decision),
                key=f"e2e-decision-{index}",
            )
            digests.add(result.decision_record["evidence_report"]["digest"])
        self.assertEqual(digests, {evidence["evidence_report_digest"]})

    # ---- recording a decision has no authority ---------------------------------

    def test_recording_a_decision_leaves_the_run_events_and_evidence_untouched(
        self,
    ) -> None:
        evidence = self.client.get_run_evidence(self.run_id).value
        before = self.run_snapshot()

        with mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            self.record(self.request_for(evidence))

        self.assertEqual(self.run_snapshot(), before)
        persisted = self.runs.status(self.run_id).run
        self.assertEqual(persisted.state, "awaiting_human_decision")
        self.assertIsNone(persisted.human_decision_record_digest)
        self.assertEqual(self.client.get_run_evidence(self.run_id).value, evidence)

    # ---- fail closed -----------------------------------------------------------

    def test_a_digest_swapped_from_another_run_is_rejected_and_nothing_is_stored(
        self,
    ) -> None:
        mine = self.client.get_run_evidence(self.run_id).value
        theirs = self.client.get_run_evidence(self.other.run.run_id).value
        self.assertNotEqual(
            mine["evidence_report_digest"], theirs["evidence_report_digest"]
        )
        swapped = self.request_for(mine)
        swapped["evidence_report"]["digest"] = theirs["evidence_report_digest"]

        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(swapped)

        self.assertEqual(caught.exception.code, "evidence_mismatch")
        self.assertEqual(self.decisions.list_for_run(self.run_id), [])

    def test_evidence_changed_after_it_was_shown_is_rejected_by_both_surfaces(
        self,
    ) -> None:
        # Own run (not shared with other tests) so the tamper cannot leak.
        seeded = _helpers.seed_offline_run(self.run_db, self.root, key="idem/e2e-stale")
        run_id = seeded.run.run_id
        shown = self.client.get_run_evidence(run_id).value
        request = self.request_for(shown)

        _helpers.rewrite_metadata(
            self.run_db,
            run_id,
            lambda metadata: metadata["evidence_report"]["warnings"].append("swapped"),
        )

        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(request, key="e2e-stale")
        self.assertEqual(caught.exception.code, "evidence_integrity_error")
        self.assertEqual(self.decisions.list_for_run(run_id), [])
        # The read surface the human trusted now refuses to serve it either.
        with self.assertRaises(Exception) as shown_again:
            self.client.get_run_evidence(run_id)
        self.assertEqual(
            getattr(shown_again.exception, "code", None), "evidence_integrity_error"
        )

    def test_a_run_that_retains_no_evidence_cannot_be_decided(self) -> None:
        self.runs.create(
            _helpers.cli_run("run/e2e-cli"),
            idempotency_key="e2e-cli",
            created_at="2026-10-02T00:00:00Z",
        )
        evidence = self.client.get_run_evidence(self.run_id).value
        request = self.request_for(evidence)
        request["evidence_report"]["run_id"] = "run/e2e-cli"

        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(request, key="e2e-no-evidence")

        self.assertEqual(caught.exception.code, "evidence_not_available")
        self.assertEqual(self.decisions.list_for_run("run/e2e-cli"), [])

    def test_the_http_digest_is_the_canonical_digest_of_the_bound_report(self) -> None:
        evidence = self.client.get_run_evidence(self.run_id).value
        self.assertEqual(
            canonical_digest(evidence["evidence_report"]),
            self.record(self.request_for(evidence)).decision_record["evidence_report"][
                "digest"
            ],
        )


if __name__ == "__main__":
    unittest.main()
