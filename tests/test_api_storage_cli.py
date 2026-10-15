"""``idkmesh api-storage`` drives the #750 storage-operations library from the CLI.

Every test runs the real ``idkmesh.cli.main`` against temp directories. The
contract under test: verbs that could write are dry runs unless ``--apply`` is
given, integrity findings exit 1, refused or unusable requests exit 2, and a
failure is one ``error: CODE: message`` line, never a traceback.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from idkmesh import cli
from idkmesh.human_decision_service import HumanDecisionStore

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-15T00:00:00Z"


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(["api-storage", *argv])
        except SystemExit as exc:  # argparse usage errors
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StorageCliCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.migrations = self.dir / "migrations"
        self.migrations.mkdir()
        (self.migrations / "0001_runs.sql").write_text(
            "CREATE TABLE runs (id TEXT PRIMARY KEY);\n", encoding="utf-8")
        (self.migrations / "0002_events.sql").write_text(
            "CREATE TABLE events (seq INTEGER PRIMARY KEY, run_id TEXT);\n",
            encoding="utf-8")
        self.db = self.dir / "state.sqlite"

    def assert_clean_failure(self, code: int, expected: int, err: str, name: str) -> None:
        self.assertEqual(code, expected, err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith(f"error: {name}: "), err)
        self.assertNotIn("Traceback", err)

    def migrate(self) -> None:
        code, _, err = run_cli(
            "apply-migrations", str(self.db), "--migrations", str(self.migrations),
            "--apply")
        self.assertEqual(code, 0, err)

    def listing(self) -> list[str]:
        return sorted(p.name for p in self.dir.iterdir())


class MigrationCliTests(StorageCliCase):
    def test_plan_is_read_only_even_for_a_database_that_does_not_exist(self) -> None:
        before = self.listing()
        code, out, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.migrations),
            "--json")
        self.assertEqual((code, err), (0, ""))
        plan = json.loads(out)["result"]["plan"]
        self.assertEqual(
            [s["version"] for s in plan["pending"]], [1, 2])
        self.assertEqual(self.listing(), before)
        self.assertFalse(self.db.exists())

    def test_apply_without_the_flag_is_a_dry_run(self) -> None:
        before = self.listing()
        code, out, _ = run_cli(
            "apply-migrations", str(self.db), "--migrations", str(self.migrations),
            "--json")
        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(document["dry_run"])
        self.assertEqual(len(document["result"]["plan"]["pending"]), 2)
        self.assertEqual(self.listing(), before)
        code, text, _ = run_cli(
            "apply-migrations", str(self.db), "--migrations", str(self.migrations))
        self.assertEqual(code, 0)
        self.assertTrue(text.startswith("dry run: "), text)

    def test_apply_migrates_then_a_rerun_has_nothing_pending(self) -> None:
        self.migrate()
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            conn.close()
        self.assertLessEqual(
            {"runs", "events", "idkmesh_schema_migrations"}, names)
        digest = sha(self.db)
        code, out, _ = run_cli(
            "apply-migrations", str(self.db), "--migrations", str(self.migrations),
            "--apply", "--json")
        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertFalse(document["dry_run"])
        self.assertEqual(document["result"]["plan"]["pending"], [])
        self.assertEqual(sha(self.db), digest)

    def test_edited_history_is_an_integrity_failure(self) -> None:
        self.migrate()
        (self.migrations / "0001_runs.sql").write_text(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, extra TEXT);\n",
            encoding="utf-8")
        digest = sha(self.db)
        for verb, extra in (("plan-migrations", ()), ("apply-migrations", ("--apply",))):
            code, _, err = run_cli(
                verb, str(self.db), "--migrations", str(self.migrations), *extra)
            self.assert_clean_failure(code, 1, err, "checksum_mismatch")
        self.assertEqual(sha(self.db), digest)

    def test_legacy_schema_is_refused_until_adoption_is_explicit(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
        conn.execute("PRAGMA user_version = 1")
        conn.close()
        args = ("--migrations", str(self.migrations))
        code, _, err = run_cli("apply-migrations", str(self.db), *args, "--apply")
        self.assert_clean_failure(code, 2, err, "unmanaged_schema")
        digest = sha(self.db)
        code, out, _ = run_cli(
            "apply-migrations", str(self.db), *args, "--adopt-existing", "--json")
        plan = json.loads(out)["result"]["plan"]
        self.assertEqual(
            (code, [s["version"] for s in plan["adopt"]],
             [s["version"] for s in plan["pending"]]),
            (0, [1], [2]))
        self.assertEqual(sha(self.db), digest, "adoption dry run changed the file")
        code, _, err = run_cli(
            "apply-migrations", str(self.db), *args, "--adopt-existing", "--apply")
        self.assertEqual((code, err), (0, ""))

    def test_bad_migration_directories_are_refused_with_exit_2(self) -> None:
        (self.migrations / "0004_gap.sql").write_text("SELECT 1;", encoding="utf-8")
        code, _, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.migrations))
        self.assert_clean_failure(code, 2, err, "invalid_migrations")
        (self.migrations / "0004_gap.sql").unlink()
        (self.migrations / "notes.sql").write_text("SELECT 1;", encoding="utf-8")
        code, _, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.migrations))
        self.assert_clean_failure(code, 2, err, "invalid_migrations")
        code, _, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.dir / "absent"))
        self.assert_clean_failure(code, 2, err, "invalid_migrations")

    def test_symlinked_database_and_missing_parent_are_refused(self) -> None:
        self.migrate()
        link = self.dir / "link.sqlite"
        os.symlink(self.db, link)
        code, _, err = run_cli(
            "plan-migrations", str(link), "--migrations", str(self.migrations))
        self.assert_clean_failure(code, 2, err, "unsafe_path")
        code, _, err = run_cli(
            "apply-migrations", str(self.dir / "no" / "db.sqlite"),
            "--migrations", str(self.migrations), "--apply")
        self.assert_clean_failure(code, 2, err, "unsafe_path")
        self.assertFalse((self.dir / "no").exists())

    def test_a_file_that_is_not_a_database_is_a_controlled_failure(self) -> None:
        self.db.write_bytes(b"not a sqlite database" * 30)
        code, _, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.migrations))
        self.assert_clean_failure(code, 2, err, "store_error")

    def test_json_failures_are_one_stable_object_on_stderr(self) -> None:
        code, out, err = run_cli(
            "plan-migrations", str(self.db), "--migrations", str(self.dir / "absent"),
            "--json")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(json.loads(err)["error"]["code"], "invalid_migrations")
        self.assertFalse(json.loads(err)["ok"])


class BackupCliTests(StorageCliCase):
    def setUp(self) -> None:
        super().setUp()
        self.migrate()
        conn = sqlite3.connect(self.db)
        with conn:
            conn.execute("INSERT INTO runs VALUES ('run-1')")
        conn.close()
        self.backups = self.dir / "backups"
        self.backups.mkdir()
        self.backup = self.backups / "state-1.sqlite"

    def take_backup(self) -> None:
        code, _, err = run_cli("backup", str(self.db), str(self.backup), "--apply")
        self.assertEqual((code, err), (0, ""))

    def test_backup_is_a_dry_run_until_applied(self) -> None:
        code, out, _ = run_cli("backup", str(self.db), str(self.backup), "--json")
        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(document["dry_run"])
        self.assertEqual(list(self.backups.iterdir()), [])
        self.take_backup()
        self.assertEqual(
            sorted(p.name for p in self.backups.iterdir()),
            ["state-1.sqlite", "state-1.sqlite.manifest.json"])

    def test_backup_never_overwrites_an_existing_backup(self) -> None:
        self.take_backup()
        digest = sha(self.backup)
        for flags in ((), ("--apply",)):
            code, _, err = run_cli("backup", str(self.db), str(self.backup), *flags)
            self.assert_clean_failure(code, 2, err, "destination_exists")
        self.assertEqual(sha(self.backup), digest)

    def test_verify_reports_the_digest_and_row_counts(self) -> None:
        self.take_backup()
        code, out, err = run_cli("verify-backup", str(self.backup), "--json")
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)["result"]
        self.assertEqual(result["row_counts"]["runs"], 1)
        self.assertEqual(result["database_schema_version"], 2)
        self.assertRegex(result["backup_digest"], r"^sha256:[0-9a-f]{64}$")
        code, _, err = run_cli(
            "verify-backup", str(self.backup), "--max-schema-version", "1")
        self.assert_clean_failure(code, 2, err, "schema_newer_than_code")

    def test_a_corrupted_backup_fails_verification_with_exit_1(self) -> None:
        self.take_backup()
        data = bytearray(self.backup.read_bytes())
        data[-5] ^= 0xFF
        self.backup.write_bytes(bytes(data))
        code, out, err = run_cli("verify-backup", str(self.backup))
        self.assert_clean_failure(code, 1, err, "backup_digest_mismatch")
        self.assertEqual(out, "")

    def test_a_tampered_manifest_fails_verification_with_exit_1(self) -> None:
        self.take_backup()
        manifest = Path(str(self.backup) + ".manifest.json")
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["row_counts"]["runs"] = 99
        manifest.write_text(json.dumps(document), encoding="utf-8")
        code, _, err = run_cli("verify-backup", str(self.backup))
        self.assert_clean_failure(code, 1, err, "manifest_digest_mismatch")

    def test_missing_files_are_exit_2_not_a_finding(self) -> None:
        code, _, err = run_cli("verify-backup", str(self.backup))
        self.assert_clean_failure(code, 2, err, "backup_missing")
        self.take_backup()
        Path(str(self.backup) + ".manifest.json").unlink()
        code, _, err = run_cli("verify-backup", str(self.backup))
        self.assert_clean_failure(code, 2, err, "manifest_missing")

    def test_restore_is_a_dry_run_until_applied(self) -> None:
        self.take_backup()
        target = self.dir / "restored.sqlite"
        code, out, _ = run_cli("restore", str(self.backup), str(target), "--json")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["dry_run"])
        self.assertFalse(target.exists())
        code, _, err = run_cli("restore", str(self.backup), str(target), "--apply")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(sha(target), sha(self.backup))
        self.assertEqual(oct(target.stat().st_mode & 0o777), "0o600")
        self.assertEqual([p for p in self.dir.iterdir() if p.name.endswith(".restoring")], [])

    def test_restore_refuses_to_overwrite_an_existing_target(self) -> None:
        self.take_backup()
        target = self.dir / "existing.sqlite"
        target.write_bytes(b"precious")
        for flags in ((), ("--apply",)):
            code, _, err = run_cli("restore", str(self.backup), str(target), *flags)
            self.assert_clean_failure(code, 2, err, "target_exists")
        self.assertEqual(target.read_bytes(), b"precious")

    def test_restore_refuses_a_symlink_target_and_leaves_its_destination(self) -> None:
        self.take_backup()
        victim = self.dir / "victim.sqlite"
        victim.write_bytes(b"precious")
        link = self.dir / "link.sqlite"
        os.symlink(victim, link)
        code, _, err = run_cli("restore", str(self.backup), str(link), "--apply")
        self.assert_clean_failure(code, 2, err, "unsafe_path")
        self.assertEqual(victim.read_bytes(), b"precious")

    def test_restore_of_a_corrupt_backup_writes_nothing(self) -> None:
        self.take_backup()
        data = bytearray(self.backup.read_bytes())
        data[-5] ^= 0xFF
        self.backup.write_bytes(bytes(data))
        target = self.dir / "restored.sqlite"
        code, _, err = run_cli("restore", str(self.backup), str(target), "--apply")
        self.assert_clean_failure(code, 1, err, "backup_digest_mismatch")
        self.assertFalse(target.exists())
        self.assertFalse(Path(str(target) + ".restoring").exists())

    def test_restore_needs_an_existing_parent_directory(self) -> None:
        self.take_backup()
        code, _, err = run_cli(
            "restore", str(self.backup), str(self.dir / "no" / "r.sqlite"), "--apply")
        self.assert_clean_failure(code, 2, err, "unsafe_path")


class RetentionCliTests(StorageCliCase):
    def write_records(self) -> Path:
        path = self.dir / "records.json"
        path.write_text(json.dumps({"records": [
            {"record_id": "evidence-1", "record_class": "essential",
             "created_at": "2020-01-01T00:00:00Z"},
            {"record_id": "probe-old", "record_class": "expendable",
             "created_at": "2026-01-01T00:00:00Z"},
            {"record_id": "probe-decided", "record_class": "expendable",
             "created_at": "2026-01-01T00:00:00Z", "run_id": "run/decided"},
            {"record_id": "claim-new", "record_class": "ephemeral",
             "created_at": "2026-10-14T00:00:00Z"},
        ]}), encoding="utf-8")
        return path

    def decisions_store(self) -> Path:
        path = self.dir / "decisions.sqlite"
        HumanDecisionStore(path)
        conn = sqlite3.connect(path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO human_decisions VALUES (?,?,?,?,?,?,?,?)",
                    ("d1", "k1", "sha256:" + "1" * 64, "run/decided",
                     "sha256:" + "e" * 64, "{}", "sha256:" + "2" * 64,
                     "2026-10-01T00:00:00Z"))
        finally:
            conn.close()
        return path

    def retention(self, *extra: str) -> tuple[int, str, str]:
        return run_cli(
            "plan-retention", "--records", str(self.write_records()),
            "--expendable-days", "30", "--ephemeral-days", "7", "--now", NOW, *extra)

    def test_plan_expires_only_unreferenced_old_expendables_and_deletes_nothing(self) -> None:
        store = self.decisions_store()
        records = self.write_records()
        before = (sha(store), sha(records))
        code, out, err = self.retention("--decisions-store", str(store), "--json")
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)["result"]
        got = {d["record_id"]: (d["action"], d["reason"]) for d in result["decisions"]}
        self.assertEqual(got, {
            "evidence-1": ("keep", "retained_class"),
            "probe-old": ("expire", "past_retention"),
            "probe-decided": ("keep", "referenced_by_human_decision"),
            "claim-new": ("keep", "within_retention"),
        })
        self.assertEqual(result["counts"], {"expire": 1, "keep": 3})
        self.assertIs(result["applied"], False)
        self.assertEqual((sha(store), sha(records)), before)

    def test_output_is_deterministic_for_a_fixed_now(self) -> None:
        first = self.retention("--assume-no-decisions", "--json")
        second = self.retention("--assume-no-decisions", "--json")
        self.assertEqual(first, second)
        code, text, _ = self.retention("--assume-no-decisions")
        self.assertEqual(code, 0)
        self.assertIn("nothing was deleted", text)
        self.assertIn("expire\tprobe-old\tpast_retention", text)

    def test_opting_out_of_decisions_expires_the_decided_probe_too(self) -> None:
        _, out, _ = self.retention("--assume-no-decisions", "--json")
        got = {d["record_id"]: d["action"] for d in json.loads(out)["result"]["decisions"]}
        self.assertEqual(got["probe-decided"], "expire")

    def test_a_mistyped_or_unreadable_decisions_store_is_never_unreferenced(self) -> None:
        code, _, err = self.retention("--decisions-store", str(self.dir / "typo.sqlite"))
        self.assert_clean_failure(code, 2, err, "store_error")
        bad = self.dir / "bad.sqlite"
        bad.write_bytes(b"not sqlite" * 40)
        code, _, err = self.retention("--decisions-store", str(bad))
        self.assert_clean_failure(code, 2, err, "store_error")

    def test_a_decision_source_must_be_chosen_exactly_once(self) -> None:
        records = str(self.write_records())
        base = ("plan-retention", "--records", records,
                "--expendable-days", "30", "--ephemeral-days", "7")
        for extra in ((), ("--assume-no-decisions", "--decisions-store", "x")):
            code, out, err = run_cli(*base, *extra)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("usage:", err)

    def test_bad_arguments_and_inputs_exit_2(self) -> None:
        records = self.write_records()
        for bad in ("0", "-3"):
            code, _, err = run_cli(
                "plan-retention", "--records", str(records), "--expendable-days", bad,
                "--ephemeral-days", "7", "--assume-no-decisions")
            self.assert_clean_failure(code, 2, err, "invalid_policy")
        code, _, err = run_cli(
            "plan-retention", "--records", str(records), "--expendable-days", "x",
            "--ephemeral-days", "7", "--assume-no-decisions")
        self.assertEqual(code, 2)
        self.assertIn("invalid int value", err)
        code, _, err = self.retention("--assume-no-decisions", "--now", "yesterday")
        self.assert_clean_failure(code, 2, err, "invalid_timestamp")
        garbled = self.dir / "garbled.json"
        garbled.write_text("{not json", encoding="utf-8")
        code, _, err = run_cli(
            "plan-retention", "--records", str(garbled), "--expendable-days", "30",
            "--ephemeral-days", "7", "--assume-no-decisions")
        self.assert_clean_failure(code, 2, err, "invalid_records")
        garbled.write_text(json.dumps([{"record_id": "a", "record_class": "bogus",
                                         "created_at": NOW}]), encoding="utf-8")
        code, _, err = run_cli(
            "plan-retention", "--records", str(garbled), "--expendable-days", "30",
            "--ephemeral-days", "7", "--assume-no-decisions")
        self.assert_clean_failure(code, 2, err, "invalid_record")
        garbled.write_text(json.dumps([{"record_id": "a", "surprise": 1}]),
                           encoding="utf-8")
        code, _, err = run_cli(
            "plan-retention", "--records", str(garbled), "--expendable-days", "30",
            "--ephemeral-days", "7", "--assume-no-decisions")
        self.assert_clean_failure(code, 2, err, "invalid_records")

    def test_group_without_a_verb_is_a_usage_error(self) -> None:
        code, _, err = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("usage:", err)


class StorageCliProcessTests(StorageCliCase):
    def test_exit_codes_survive_a_real_process_boundary(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        base = [sys.executable, "-m", "idkmesh.cli", "api-storage"]
        ok = subprocess.run(
            [*base, "plan-migrations", str(self.db), "--migrations", str(self.migrations)],
            capture_output=True, text=True, env=env, cwd=self.dir, timeout=60)
        self.assertEqual((ok.returncode, ok.stderr), (0, ""))
        missing = subprocess.run(
            [*base, "verify-backup", str(self.dir / "nope.sqlite")],
            capture_output=True, text=True, env=env, cwd=self.dir, timeout=60)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(
            missing.stderr, "error: backup_missing: backup file does not exist\n")


if __name__ == "__main__":
    unittest.main()
