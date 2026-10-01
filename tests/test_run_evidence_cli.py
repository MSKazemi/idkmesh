"""CLI tests for ``idkmesh run evidence`` and mixed-store run reads (ADR-0024).

Not yet executed: written in a develop-only pass. The offline-spine fixture
helpers are borrowed from ``test_product_spine_idempotency.py`` by file path so
this module does not depend on how pytest puts ``tests/`` on ``sys.path``.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_idempotency import (
    IdempotentOfflineProductSpineService,
)
from idkmesh.product_spine_run_store import ProductSpineRunStore


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"


def _load_idempotency_fixtures():
    path = ROOT / "tests" / "test_product_spine_idempotency.py"
    spec = importlib.util.spec_from_file_location(
        "_idempotency_fixtures_for_evidence_cli", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


FIXTURES = _load_idempotency_fixtures()


def _cli_run(run_id: str = "run/cli-no-evidence") -> ProductSpineRun:
    return ProductSpineRun(
        run_id=run_id,
        request_digest="sha256:" + "a" * 64,
        project_id="project.test",
        work_unit_id="work/cli-1",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


class RunEvidenceCliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def seed_offline_run(self, tmp: str, db: Path):
        """Complete one idempotent offline run that retains its evidence."""
        work = FIXTURES._work_unit()
        attempt = FIXTURES._attempt(work, Path(tmp) / "candidate-a")
        wrapper = IdempotentOfflineProductSpineService(
            service=FIXTURES._offline_service([]),
            store=LocalMetadataStore(db),
        )
        return FIXTURES._execute(wrapper, work=work, attempt=attempt)

    def seed_cli_run(self, db: Path, run_id: str = "run/cli-no-evidence"):
        ProductSpineRunStore(LocalMetadataStore(db)).create(
            _cli_run(run_id),
            idempotency_key=f"cli-{run_id}",
            created_at="2026-10-02T00:00:00Z",
        )

    # ---- run evidence ----------------------------------------------------

    def test_json_output_is_the_retained_report_and_its_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            result = self.seed_offline_run(tmp, db)

            proc = self.run_cli(
                "run", "evidence", result.run.run_id,
                "--store", str(db), "--json",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(
                set(payload),
                {"run_id", "evidence_report_digest", "evidence_report"},
            )
            self.assertEqual(payload["run_id"], result.run.run_id)
            self.assertEqual(
                payload["evidence_report_digest"],
                result.run.evidence_report_digest,
            )
            self.assertEqual(payload["evidence_report"], result.evidence_report)
            # Compact, sorted, single line.
            self.assertEqual(proc.stdout.count("\n"), 1)
            self.assertEqual(
                proc.stdout.strip(),
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )

    def test_text_output_reports_only_what_the_report_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            result = self.seed_offline_run(tmp, db)
            report = result.evidence_report

            proc = self.run_cli(
                "run", "evidence", result.run.run_id, "--store", str(db)
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = proc.stdout.splitlines()
            self.assertEqual(lines[0], f"run: {result.run.run_id}")
            self.assertEqual(
                lines[1],
                f"evidence_report_digest: {result.run.evidence_report_digest}",
            )
            self.assertEqual(
                lines[2], f"attempts: {len(report.get('attempts', []))}"
            )
            decision = report.get("human_decision")
            if isinstance(decision, dict) and "status" in decision:
                self.assertIn(
                    f"human_decision_status: {decision['status']}", lines
                )
            else:
                self.assertFalse(
                    any(line.startswith("human_decision_status") for line in lines)
                )

    def test_a_cli_created_run_has_no_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            self.seed_cli_run(db)

            proc = self.run_cli(
                "run", "evidence", "run/cli-no-evidence",
                "--store", str(db), "--json",
            )

            self.assertEqual(proc.returncode, 2)
            error = json.loads(proc.stderr)["error"]
            self.assertEqual(error["code"], "evidence_not_available")

    def test_text_mode_error_names_the_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            self.seed_cli_run(db)

            proc = self.run_cli(
                "run", "evidence", "run/cli-no-evidence", "--store", str(db)
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn("evidence_not_available", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_an_unknown_run_is_run_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            self.seed_cli_run(db)

            proc = self.run_cli(
                "run", "evidence", "run/does-not-exist",
                "--store", str(db), "--json",
            )

            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "run_not_found"
            )

    def test_a_tampered_report_is_refused_and_never_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            result = self.seed_offline_run(tmp, db)
            store = LocalMetadataStore(db)
            record = store.get_run(result.run.run_id)
            assert record is not None
            metadata = deepcopy(dict(record.metadata))
            metadata["evidence_report"]["warnings"].append(
                "tampered-after-persistence"
            )
            store.update_run(
                record.run_id,
                state=record.state,
                metadata=metadata,
                updated_at="2026-10-02T00:05:00Z",
            )

            proc = self.run_cli(
                "run", "evidence", result.run.run_id,
                "--store", str(db), "--json",
            )

            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"],
                "evidence_integrity_error",
            )
            self.assertNotIn("tampered-after-persistence", proc.stdout)

    def test_help_says_read_only_and_digest_verified(self):
        proc = self.run_cli("run", "evidence", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = " ".join(proc.stdout.split()).lower()
        self.assertIn("read-only", text)
        self.assertIn("digest", text)
        self.assertIn("--store", proc.stdout)
        self.assertIn("--json", proc.stdout)

    # ---- mixed-store reads (ADR-0024 decisions 4 and 5) -------------------

    def test_run_list_on_a_mixed_store_lists_exactly_the_product_spine_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            result = self.seed_offline_run(tmp, db)
            self.seed_cli_run(db)
            LocalMetadataStore(db).admit_run(
                run_id="github/dispatch-1",
                idempotency_key="github:dispatch-1",
                request_digest="sha256:" + "c" * 64,
                state="proposed",
                metadata={"kind": "github-other"},
                created_at="2026-10-02T00:00:00Z",
            )

            proc = self.run_cli(
                "run", "list", "--store", str(db), "--json"
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(
                sorted(item["run_id"] for item in payload["items"]),
                sorted([result.run.run_id, "run/cli-no-evidence"]),
            )
            self.assertIsNone(payload["page"]["next_cursor"])

    def test_a_completed_offline_run_is_readable_with_run_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            result = self.seed_offline_run(tmp, db)

            proc = self.run_cli(
                "run", "status", result.run.run_id,
                "--store", str(db), "--json",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["run"]["run_id"], result.run.run_id)
            self.assertEqual(
                payload["run"]["evidence_report_digest"],
                result.run.evidence_report_digest,
            )


if __name__ == "__main__":
    unittest.main()
