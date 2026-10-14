"""Migration, retention and backup/restore primitives (issue #750, API-13).

Covers ``idkmesh/api_storage_ops.py``: a checksummed forward-only migration
runner whose apply is atomic (including a real process crash mid-migration), a
retention planner that cannot expire evidence a Human Decision refers to, and a
digest-bound backup/verify/restore procedure with negative cases.

Class-based on purpose: the repository's documented test counts guard
module-level ``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from idkmesh import api_storage_ops as ops
from idkmesh.api_storage_ops import (
    DecisionReferences,
    MigrationStep,
    RetentionRecord,
    StorageOpsError,
)
from idkmesh.connector_store import SCHEMA_VERSION, LocalMetadataStore
from idkmesh.human_decision_service import HumanDecisionStore
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SHA = "0123456789abcdef0123456789abcdef01234567"

STEPS = (
    MigrationStep(1, "create_notes", "CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);"),
    MigrationStep(
        2,
        "add_tags",
        "CREATE TABLE tags (id INTEGER PRIMARY KEY, note_id INTEGER);\n"
        "CREATE INDEX tags_by_note ON tags(note_id);",
    ),
    MigrationStep(3, "seed_note", "INSERT INTO notes(body) VALUES ('seeded');"),
)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tables(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        conn.close()


def _version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


class _TmpCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-storage-ops-")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.db = self.dir / "state.sqlite"


class MigrationRunnerTests(_TmpCase):
    def test_apply_creates_schema_ledger_and_version(self) -> None:
        plan = ops.apply_migrations(self.db, STEPS)
        self.assertEqual([s.version for s in plan.pending], [1, 2, 3])
        self.assertEqual(_version(self.db), 3)
        conn = sqlite3.connect(self.db)
        try:
            rows = conn.execute(
                f"SELECT version, name, checksum FROM {ops.MIGRATION_LEDGER_TABLE} ORDER BY 1"
            ).fetchall()
            self.assertEqual(conn.execute("SELECT body FROM notes").fetchall(), [("seeded",)])
        finally:
            conn.close()
        self.assertEqual([r[0] for r in rows], [1, 2, 3])
        self.assertEqual([r[2] for r in rows], [s.checksum for s in STEPS])

    def test_reapplying_is_a_no_op(self) -> None:
        ops.apply_migrations(self.db, STEPS)
        before = _file_sha(self.db)
        plan = ops.apply_migrations(self.db, STEPS)
        self.assertEqual(plan.pending, ())
        self.assertEqual(_file_sha(self.db), before)

    def test_an_older_database_upgrades_with_only_the_missing_steps(self) -> None:
        ops.apply_migrations(self.db, STEPS[:2])
        plan = ops.apply_migrations(self.db, STEPS)
        self.assertEqual([s.version for s in plan.pending], [3])
        self.assertEqual(_version(self.db), 3)

    def test_dry_run_reports_the_plan_and_writes_nothing(self) -> None:
        plan = ops.plan_migrations(self.db, STEPS)
        self.assertEqual(plan.to_dict()["pending"][0]["checksum"], STEPS[0].checksum)
        self.assertFalse(self.db.exists())
        ops.apply_migrations(self.db, STEPS[:1])
        before = _file_sha(self.db)
        plan = ops.plan_migrations(self.db, STEPS)
        self.assertEqual([s.version for s in plan.pending], [2, 3])
        self.assertEqual(_file_sha(self.db), before)
        self.assertEqual(_version(self.db), 1)

    def test_error_in_a_later_step_rolls_back_every_step(self) -> None:
        ops.apply_migrations(self.db, STEPS[:1])
        before = _file_sha(self.db)
        bad = STEPS[:2] + (
            MigrationStep(3, "broken", "CREATE TABLE ok_t(x); SELECT * FROM missing;"),
        )
        with self.assertRaises(StorageOpsError) as caught:
            ops.apply_migrations(self.db, bad)
        self.assertEqual(caught.exception.code, "migration_failed")
        self.assertEqual(_version(self.db), 1)
        self.assertEqual(_tables(self.db), {"notes", ops.MIGRATION_LEDGER_TABLE})
        self.assertEqual(_file_sha(self.db), before)

    def test_exception_after_a_step_leaves_the_previous_schema(self) -> None:
        ops.apply_migrations(self.db, STEPS[:1])

        def explode(step: MigrationStep) -> None:
            if step.version == 2:
                raise RuntimeError("simulated crash after step 2")

        with self.assertRaises(RuntimeError):
            ops.apply_migrations(self.db, STEPS, after_step=explode)
        self.assertEqual(_version(self.db), 1)
        self.assertNotIn("tags", _tables(self.db))
        # Recovery: the same migration then applies cleanly.
        ops.apply_migrations(self.db, STEPS)
        self.assertEqual(_version(self.db), 3)

    def test_a_real_process_crash_mid_migration_is_rolled_back(self) -> None:
        ops.apply_migrations(self.db, STEPS[:1])
        script = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "from idkmesh.api_storage_ops import MigrationStep, apply_migrations\n"
            "steps = [\n"
            "  MigrationStep(1, 'create_notes',"
            " 'CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);'),\n"
            "  MigrationStep(2, 'add_tags',"
            " 'CREATE TABLE tags (id INTEGER PRIMARY KEY, note_id INTEGER);\\n"
            "CREATE INDEX tags_by_note ON tags(note_id);'),\n"
            "  MigrationStep(3, 'seed_note', \"INSERT INTO notes(body) VALUES ('seeded');\"),\n"
            "]\n"
            "def die(step):\n"
            "    if step.version == 2:\n"
            "        os._exit(9)\n"
            "apply_migrations(Path(sys.argv[1]), steps, after_step=die)\n"
        )
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
        proc = subprocess.run(
            [sys.executable, "-c", script, str(self.db)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 9, proc.stderr)
        # The killed process may have left a hot journal; the next open rolls it back.
        self.assertEqual(_version(self.db), 1)
        self.assertEqual(_tables(self.db), {"notes", ops.MIGRATION_LEDGER_TABLE})
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            conn.close()
        ops.apply_migrations(self.db, STEPS)
        self.assertEqual(_version(self.db), 3)

    def test_editing_an_applied_step_is_refused(self) -> None:
        ops.apply_migrations(self.db, STEPS)
        edited = (STEPS[0], MigrationStep(2, "add_tags", "CREATE TABLE tags (x);"), STEPS[2])
        with self.assertRaises(StorageOpsError) as caught:
            ops.apply_migrations(self.db, edited)
        self.assertEqual(caught.exception.code, "checksum_mismatch")
        with self.assertRaises(StorageOpsError) as dry:
            ops.plan_migrations(self.db, edited)
        self.assertEqual(dry.exception.code, "checksum_mismatch")

    def test_line_endings_do_not_change_the_checksum(self) -> None:
        self.assertEqual(ops.sql_checksum("A;\nB;"), ops.sql_checksum("A;\r\nB;\r\n"))
        self.assertNotEqual(ops.sql_checksum("A;"), ops.sql_checksum("B;"))

    def test_a_newer_database_is_refused_and_untouched(self) -> None:
        ops.apply_migrations(self.db, STEPS)
        before = _file_sha(self.db)
        with self.assertRaises(StorageOpsError) as caught:
            ops.apply_migrations(self.db, STEPS[:2])
        self.assertEqual(caught.exception.code, "schema_newer_than_code")
        self.assertEqual(_file_sha(self.db), before)

    def test_ledger_tampering_fails_closed(self) -> None:
        ops.apply_migrations(self.db, STEPS)
        conn = sqlite3.connect(self.db)
        try:
            with conn:
                conn.execute(f"DELETE FROM {ops.MIGRATION_LEDGER_TABLE} WHERE version = 2")
        finally:
            conn.close()
        with self.assertRaises(StorageOpsError) as gap:
            ops.apply_migrations(self.db, STEPS)
        self.assertEqual(gap.exception.code, "ledger_gap")
        conn = sqlite3.connect(self.db)
        try:
            with conn:
                conn.execute(f"DELETE FROM {ops.MIGRATION_LEDGER_TABLE} WHERE version = 3")
                conn.execute(
                    f"INSERT INTO {ops.MIGRATION_LEDGER_TABLE} VALUES (2, 'add_tags', ?, 0)",
                    (STEPS[1].checksum,),
                )
        finally:
            conn.close()
        with self.assertRaises(StorageOpsError) as mismatch:
            ops.apply_migrations(self.db, STEPS)
        self.assertEqual(mismatch.exception.code, "ledger_version_mismatch")

    def test_unmanaged_schema_needs_explicit_adoption(self) -> None:
        LocalMetadataStore(self.db)
        self.assertEqual(_version(self.db), SCHEMA_VERSION)
        legacy = tuple(
            MigrationStep(i, f"legacy_v{i}", f"SELECT {i};") for i in range(1, SCHEMA_VERSION + 1)
        ) + (MigrationStep(SCHEMA_VERSION + 1, "ops_note", "CREATE TABLE ops_note (k TEXT);"),)
        with self.assertRaises(StorageOpsError) as caught:
            ops.apply_migrations(self.db, legacy)
        self.assertEqual(caught.exception.code, "unmanaged_schema")
        self.assertEqual(_version(self.db), SCHEMA_VERSION)
        plan = ops.plan_migrations(self.db, legacy, adopt_existing=True)
        self.assertEqual(len(plan.adopt), SCHEMA_VERSION)
        ops.apply_migrations(self.db, legacy, adopt_existing=True)
        self.assertEqual(_version(self.db), SCHEMA_VERSION + 1)
        self.assertIn("ops_note", _tables(self.db))
        self.assertIn("runs", _tables(self.db))
        conn = sqlite3.connect(self.db)
        try:
            adopted = conn.execute(
                f"SELECT COUNT(*) FROM {ops.MIGRATION_LEDGER_TABLE} WHERE adopted = 1"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(adopted, SCHEMA_VERSION)

    def test_step_definitions_are_validated(self) -> None:
        for bad in (
            (),
            (MigrationStep(2, "gap", "SELECT 1;"),),
            (MigrationStep(1, "", "SELECT 1;"),),
            (MigrationStep(1, "empty", "  "),),
            (MigrationStep(True, "bool", "SELECT 1;"),),  # type: ignore[arg-type]
        ):
            with self.subTest(bad=bad), self.assertRaises(StorageOpsError) as caught:
                ops.plan_migrations(self.db, bad)
            self.assertEqual(caught.exception.code, "invalid_migrations")

    def test_steps_may_not_control_transactions_or_the_version(self) -> None:
        statements = (
            "COMMIT;",
            "PRAGMA user_version = 99;",
            "BEGIN;",
            "ATTACH 'x' AS y;",
            "VACUUM;",
        )
        for index, sql in enumerate(statements):
            with self.subTest(sql=sql):
                db = self.dir / f"bad{index}.sqlite"
                step = MigrationStep(1, "bad", "CREATE TABLE t(x);\n" + sql)
                with self.assertRaises(StorageOpsError) as caught:
                    ops.apply_migrations(db, (step,))
                self.assertEqual(caught.exception.code, "invalid_migrations")
                self.assertEqual(_version(db), 0)
                self.assertNotIn("t", _tables(db))

    def test_unterminated_sql_is_refused_before_any_change(self) -> None:
        with self.assertRaises(StorageOpsError) as caught:
            ops.apply_migrations(self.db, (MigrationStep(1, "cut", "CREATE TABLE t(x)"),))
        self.assertEqual(caught.exception.code, "invalid_migrations")
        self.assertEqual(_version(self.db), 0)


class RetentionTests(unittest.TestCase):
    POLICY = {"expendable": 30, "ephemeral": 7, "essential": None, "configuration": None}
    NOW = "2026-10-14T00:00:00Z"

    def decide(self, records, references=DecisionReferences(), policy=None):
        out = ops.evaluate_retention(
            records, policy or self.POLICY, now=self.NOW, references=references
        )
        return {d.record_id: (d.action, d.reason) for d in out}

    def test_old_expendable_expires_and_recent_is_kept(self) -> None:
        got = self.decide(
            [
                RetentionRecord("old", "expendable", "2026-08-01T00:00:00Z"),
                RetentionRecord("new", "expendable", "2026-10-10T00:00:00Z"),
                RetentionRecord("lease", "ephemeral", "2026-10-01T00:00:00Z"),
            ]
        )
        self.assertEqual(got["old"], ("expire", "past_retention"))
        self.assertEqual(got["new"], ("keep", "within_retention"))
        self.assertEqual(got["lease"], ("expire", "past_retention"))

    def test_essential_and_configuration_are_never_expired(self) -> None:
        got = self.decide(
            [
                RetentionRecord("ev", "essential", "2000-01-01T00:00:00Z"),
                RetentionRecord("cfg", "configuration", "2000-01-01T00:00:00Z"),
            ]
        )
        self.assertEqual(got["ev"], ("keep", "retained_class"))
        self.assertEqual(got["cfg"], ("keep", "retained_class"))

    def test_a_policy_cannot_put_an_age_limit_on_essential_records(self) -> None:
        for klass in ("essential", "configuration"):
            with self.subTest(klass=klass), self.assertRaises(StorageOpsError) as caught:
                ops.validate_retention_policy(dict(self.POLICY, **{klass: 1}))
            self.assertEqual(caught.exception.code, "invalid_policy")

    def test_evidence_referenced_by_a_decision_is_never_expired(self) -> None:
        refs = DecisionReferences(
            run_ids=frozenset({"run/decided"}),
            evidence_digests=frozenset({"sha256:" + "a" * 64}),
        )
        got = self.decide(
            [
                RetentionRecord(
                    "by-run", "expendable", "2000-01-01T00:00:00Z", run_id="run/decided"
                ),
                RetentionRecord(
                    "by-digest",
                    "ephemeral",
                    "2000-01-01T00:00:00Z",
                    evidence_digest="sha256:" + "a" * 64,
                ),
                RetentionRecord(
                    "unrelated",
                    "expendable",
                    "2000-01-01T00:00:00Z",
                    run_id="run/other",
                    evidence_digest="sha256:" + "b" * 64,
                ),
            ],
            refs,
        )
        self.assertEqual(got["by-run"], ("keep", "referenced_by_human_decision"))
        self.assertEqual(got["by-digest"], ("keep", "referenced_by_human_decision"))
        self.assertEqual(got["unrelated"], ("expire", "past_retention"))

    def test_a_record_without_identity_fields_is_not_matched_by_none(self) -> None:
        got = self.decide([RetentionRecord("plain", "expendable", "2000-01-01T00:00:00Z")])
        self.assertEqual(got["plain"], ("expire", "past_retention"))

    def test_fail_closed_inputs(self) -> None:
        cases = {
            "unknown class": [RetentionRecord("x", "weird", "2026-01-01T00:00:00Z")],
            "bad time": [RetentionRecord("x", "expendable", "yesterday")],
            "naive time": [RetentionRecord("x", "expendable", "2026-01-01T00:00:00")],
            "duplicate": [RetentionRecord("x", "expendable", "2026-01-01T00:00:00Z")] * 2,
            "not a record": [{"record_id": "x"}],
        }
        for label, records in cases.items():
            with self.subTest(label), self.assertRaises(StorageOpsError):
                ops.evaluate_retention(records, self.POLICY, now=self.NOW)  # type: ignore[arg-type]
        bad_policies = (
            {},
            {"expendable": 0, "ephemeral": 7},
            {**self.POLICY, "extra": 1},
            {**self.POLICY, "expendable": True},
            {**self.POLICY, "ephemeral": None},
        )
        for bad_policy in bad_policies:
            with self.subTest(policy=bad_policy), self.assertRaises(StorageOpsError):
                ops.validate_retention_policy(bad_policy)  # type: ignore[arg-type]
        with self.assertRaises(StorageOpsError):
            ops.evaluate_retention([], self.POLICY, now="2026-10-14T00:00:00")

    def test_future_dated_records_are_kept(self) -> None:
        got = self.decide([RetentionRecord("f", "expendable", "2027-01-01T00:00:00Z")])
        self.assertEqual(got["f"], ("keep", "created_in_future"))

    def test_evaluation_is_deterministic_and_preserves_input_order(self) -> None:
        records = [RetentionRecord(f"r{i}", "expendable", "2026-01-01T00:00:00Z") for i in range(5)]
        first = ops.evaluate_retention(records, self.POLICY, now=self.NOW)
        second = ops.evaluate_retention(records, self.POLICY, now=self.NOW)
        self.assertEqual(first, second)
        self.assertEqual([d.record_id for d in first], [r.record_id for r in records])


class DecisionReferenceReaderTests(_TmpCase):
    def test_missing_store_means_no_decisions(self) -> None:
        self.assertEqual(
            ops.decision_references_from_store(self.dir / "none.sqlite"), DecisionReferences()
        )

    def test_references_come_from_a_real_decision_store_without_modifying_it(self) -> None:
        path = self.dir / "decisions.sqlite"
        HumanDecisionStore(path)
        conn = sqlite3.connect(path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO human_decisions VALUES (?,?,?,?,?,?,?,?)",
                    (
                        "d1",
                        "k1",
                        "sha256:" + "1" * 64,
                        "run/decided",
                        "sha256:" + "e" * 64,
                        "{}",
                        "sha256:" + "2" * 64,
                        "2026-10-01T00:00:00Z",
                    ),
                )
        finally:
            conn.close()
        before = _file_sha(path)
        refs = ops.decision_references_from_store(path)
        self.assertEqual(refs.run_ids, frozenset({"run/decided"}))
        self.assertEqual(refs.evidence_digests, frozenset({"sha256:" + "e" * 64}))
        self.assertEqual(_file_sha(path), before)
        got = ops.evaluate_retention(
            [
                RetentionRecord(
                    "probe-of-decided-run",
                    "expendable",
                    "2000-01-01T00:00:00Z",
                    run_id="run/decided",
                )
            ],
            RetentionTests.POLICY,
            now=RetentionTests.NOW,
            references=refs,
        )
        self.assertEqual(got[0].action, "keep")

    def test_an_unreadable_decision_store_fails_closed(self) -> None:
        path = self.dir / "decisions.sqlite"
        path.write_bytes(b"this is not a sqlite database" * 20)
        with self.assertRaises(StorageOpsError) as caught:
            ops.decision_references_from_store(path)
        self.assertEqual(caught.exception.code, "store_error")
        empty = self.dir / "no_table.sqlite"
        sqlite3.connect(empty).close()
        with self.assertRaises(StorageOpsError):
            ops.decision_references_from_store(empty)


def _run(index: int) -> ProductSpineRun:
    return ProductSpineRun(
        run_id=f"run/ops-{index}",
        request_digest="sha256:" + f"{index:x}" * 64,
        project_id="project.ops",
        work_unit_id=f"work/ops-{index}",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


class BackupRestoreTests(_TmpCase):
    def seed(self) -> ProductSpineRunStore:
        service = ProductSpineRunStore(LocalMetadataStore(self.db))
        for index in (1, 2, 3):
            service.create(
                _run(index), idempotency_key=f"ops-{index}", created_at="2026-10-10T10:00:00Z"
            )
        return service

    def snapshot(self, path: Path):
        service = ProductSpineRunStore(LocalMetadataStore(path))
        events, _ = service.list_events()
        return events, service.list()

    def backup(self) -> Path:
        self.seed()
        return ops.create_backup(self.db, self.dir / "backup.sqlite")

    def test_backup_verify_restore_round_trip_reconstructs_the_same_records(self) -> None:
        manifest = self.backup()
        backup = self.dir / "backup.sqlite"
        self.assertEqual(manifest, ops.manifest_path_for(backup))
        report = ops.verify_backup(backup)
        self.assertEqual(report.database_schema_version, SCHEMA_VERSION)
        self.assertEqual(report.row_counts["runs"], 3)
        self.assertEqual(report.row_counts["events"], 3)
        document = json.loads(manifest.read_text())
        self.assertEqual(document["backup_digest"], "sha256:" + _file_sha(backup))

        target = self.dir / "restored" / "state.sqlite"
        target.parent.mkdir()
        ops.restore_backup(backup, target, max_supported_schema_version=SCHEMA_VERSION)
        self.assertEqual(self.snapshot(target), self.snapshot(self.db))
        self.assertFalse(list(target.parent.glob("*.restoring")))

    def test_backup_refuses_existing_destination_and_leaves_no_partial(self) -> None:
        self.seed()
        dest = self.dir / "b.sqlite"
        ops.create_backup(self.db, dest)
        with self.assertRaises(StorageOpsError) as caught:
            ops.create_backup(self.db, dest)
        self.assertEqual(caught.exception.code, "destination_exists")
        self.assertEqual(
            sorted(p.name for p in self.dir.glob("b.sqlite*")),
            ["b.sqlite", "b.sqlite.manifest.json"],
        )
        with self.assertRaises(StorageOpsError):
            ops.create_backup(self.db, self.db)
        with self.assertRaises(StorageOpsError):
            ops.create_backup(self.dir / "absent.sqlite", self.dir / "x.sqlite")

    def test_backup_does_not_follow_a_symlink_destination(self) -> None:
        self.seed()
        victim = self.dir / "victim.txt"
        victim.write_text("keep me")
        link = self.dir / "link.sqlite"
        link.symlink_to(victim)
        with self.assertRaises(StorageOpsError) as caught:
            ops.create_backup(self.db, link)
        self.assertEqual(caught.exception.code, "unsafe_path")
        self.assertEqual(victim.read_text(), "keep me")

    def test_backup_files_are_private(self) -> None:
        manifest = self.backup()
        for path in (self.dir / "backup.sqlite", manifest):
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_a_flipped_byte_in_the_backup_is_detected(self) -> None:
        self.backup()
        backup = self.dir / "backup.sqlite"
        data = bytearray(backup.read_bytes())
        data[len(data) // 2] ^= 0xFF
        backup.write_bytes(bytes(data))
        with self.assertRaises(StorageOpsError) as caught:
            ops.verify_backup(backup)
        self.assertEqual(caught.exception.code, "backup_digest_mismatch")
        target = self.dir / "t.sqlite"
        with self.assertRaises(StorageOpsError):
            ops.restore_backup(backup, target)
        self.assertFalse(target.exists())

    def test_a_substituted_backup_with_a_stale_manifest_is_detected(self) -> None:
        self.backup()
        backup = self.dir / "backup.sqlite"
        other = self.dir / "other.sqlite"
        ProductSpineRunStore(LocalMetadataStore(other))
        backup.write_bytes(other.read_bytes())
        with self.assertRaises(StorageOpsError) as caught:
            ops.verify_backup(backup)
        self.assertEqual(caught.exception.code, "backup_digest_mismatch")

    def test_an_edited_manifest_is_detected(self) -> None:
        manifest = self.backup()
        document = json.loads(manifest.read_text())
        document["row_counts"]["runs"] = 99
        manifest.write_text(json.dumps(document))
        with self.assertRaises(StorageOpsError) as caught:
            ops.verify_backup(self.dir / "backup.sqlite")
        self.assertEqual(caught.exception.code, "manifest_digest_mismatch")

    def test_manifest_must_have_exactly_the_specified_fields_and_name(self) -> None:
        manifest = self.backup()
        good = json.loads(manifest.read_text())
        manifest.write_text(json.dumps(dict(good, extra="x")))
        with self.assertRaises(StorageOpsError) as caught:
            ops.verify_backup(self.dir / "backup.sqlite")
        self.assertEqual(caught.exception.code, "manifest_invalid")
        manifest.write_text("not json")
        with self.assertRaises(StorageOpsError) as bad:
            ops.verify_backup(self.dir / "backup.sqlite")
        self.assertEqual(bad.exception.code, "manifest_invalid")
        manifest.write_text(json.dumps(good))
        renamed = self.dir / "renamed.sqlite"
        (self.dir / "backup.sqlite").rename(renamed)
        manifest.rename(ops.manifest_path_for(renamed))
        with self.assertRaises(StorageOpsError) as name:
            ops.verify_backup(renamed)
        self.assertEqual(name.exception.code, "manifest_invalid")
        with self.assertRaises(StorageOpsError) as missing:
            ops.verify_backup(self.dir / "nope.sqlite")
        self.assertEqual(missing.exception.code, "backup_missing")

    def test_a_correctly_digested_but_corrupt_database_fails_the_integrity_check(self) -> None:
        self.backup()
        backup = self.dir / "backup.sqlite"
        backup.write_bytes(b"garbage" * 500)
        body = {
            "kind": ops.BACKUP_MANIFEST_KIND,
            "schema_version": ops.BACKUP_MANIFEST_VERSION,
            "backup_file": backup.name,
            "backup_digest": "sha256:" + _file_sha(backup),
            "backup_size": backup.stat().st_size,
            "database_schema_version": 3,
            "row_counts": {},
        }
        document = dict(body, manifest_digest=ops._manifest_digest(body))
        ops.manifest_path_for(backup).write_text(json.dumps(document))
        with self.assertRaises(StorageOpsError) as caught:
            ops.verify_backup(backup)
        self.assertEqual(caught.exception.code, "backup_corrupt")

    def test_a_newer_schema_backup_is_refused_when_a_ceiling_is_given(self) -> None:
        self.backup()
        with self.assertRaises(StorageOpsError) as caught:
            ops.restore_backup(
                self.dir / "backup.sqlite",
                self.dir / "t.sqlite",
                max_supported_schema_version=SCHEMA_VERSION - 1,
            )
        self.assertEqual(caught.exception.code, "schema_newer_than_code")
        self.assertFalse((self.dir / "t.sqlite").exists())

    def test_restore_refuses_to_overwrite_without_replace(self) -> None:
        self.backup()
        existing = self.dir / "live.sqlite"
        existing.write_bytes(b"live data")
        with self.assertRaises(StorageOpsError) as caught:
            ops.restore_backup(self.dir / "backup.sqlite", existing)
        self.assertEqual(caught.exception.code, "target_exists")
        self.assertEqual(existing.read_bytes(), b"live data")

    def test_replace_removes_stale_wal_and_sidecars(self) -> None:
        self.backup()
        live = self.dir / "live.sqlite"
        live.write_bytes(b"old")
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(live) + suffix).write_bytes(b"stale")
        ops.restore_backup(self.dir / "backup.sqlite", live, replace=True)
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(Path(str(live) + suffix).exists())
        self.assertEqual(_version(live), SCHEMA_VERSION)

    def test_a_crash_during_restore_keeps_the_old_target_and_no_staging_file(self) -> None:
        self.backup()
        live = self.dir / "live.sqlite"
        live.write_bytes(b"old live data")
        with mock.patch.object(ops.os, "replace", side_effect=OSError("disk gone")):
            with self.assertRaises(StorageOpsError) as caught:
                ops.restore_backup(self.dir / "backup.sqlite", live, replace=True)
        self.assertEqual(caught.exception.code, "restore_failed")
        self.assertEqual(live.read_bytes(), b"old live data")
        self.assertFalse(list(self.dir.glob("*.restoring")))

    def test_restore_does_not_follow_a_symlink_target(self) -> None:
        self.backup()
        victim = self.dir / "victim.txt"
        victim.write_text("keep me")
        link = self.dir / "link.sqlite"
        link.symlink_to(victim)
        with self.assertRaises(StorageOpsError) as caught:
            ops.restore_backup(self.dir / "backup.sqlite", link, replace=True)
        self.assertEqual(caught.exception.code, "unsafe_path")
        self.assertEqual(victim.read_text(), "keep me")

    def test_a_backup_taken_while_another_connection_is_open_is_consistent(self) -> None:
        self.seed()
        other = sqlite3.connect(self.db)
        try:
            ops.create_backup(self.db, self.dir / "live.sqlite")
        finally:
            other.close()
        report = ops.verify_backup(self.dir / "live.sqlite")
        self.assertEqual(report.row_counts["runs"], 3)


if __name__ == "__main__":
    unittest.main()
