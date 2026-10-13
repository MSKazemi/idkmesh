"""Issue #750: owner-triggered SQLite snapshots preserve durable state."""
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore, LocalStoreError
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore, ProductSpineRunStoreError

SHA = "0123456789abcdef0123456789abcdef01234567"


def _run(number):
    return ProductSpineRun(
        run_id=f"run/backup-{number}",
        request_digest="sha256:" + f"{number:x}" * 64,
        project_id="project.backup",
        work_unit_id=f"work/backup-{number}",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


class LocalOnlineBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = LocalMetadataStore(self.root / "source.sqlite")
        self.service = ProductSpineRunStore(self.store)

    def seed(self, number):
        self.service.create(
            _run(number),
            idempotency_key=f"backup-{number}",
            created_at="2026-10-13T10:00:00Z",
        )

    def test_backup_is_a_consistent_independent_snapshot(self):
        self.seed(1)
        self.seed(2)
        source_events, _ = self.service.list_events()
        target = self.root / "snapshot.sqlite"
        self.assertEqual(self.store.backup_to(target), target)
        self.seed(3)
        restored = ProductSpineRunStore(LocalMetadataStore(target))
        saved_events, _ = restored.list_events()
        self.assertEqual(saved_events, source_events)
        self.assertIsNotNone(restored.status("run/backup-1"))
        with self.assertRaises(ProductSpineRunStoreError) as missing:
            restored.status("run/backup-3")
        self.assertEqual(missing.exception.code, "run_not_found")
        self.assertEqual(len(self.service.list_events()[0]), 3)

    def test_does_not_overwrite_existing_backup_or_source(self):
        self.seed(1)
        target = self.root / "snapshot.sqlite"
        self.store.backup_to(target)
        old_contents = target.read_bytes()
        with self.assertRaises(LocalStoreError):
            self.store.backup_to(target)
        self.assertEqual(target.read_bytes(), old_contents)
        with self.assertRaises(LocalStoreError):
            self.store.backup_to(self.store.path)
        self.assertEqual(len(self.service.list_events()[0]), 1)

    def test_refuses_missing_directory_and_existing_symlink(self):
        self.seed(1)
        with self.assertRaises(LocalStoreError):
            self.store.backup_to(self.root / "no-such-directory" / "x.sqlite")
        link = self.root / "bad.sqlite"
        try:
            link.symlink_to(self.store.path)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported here")
        with self.assertRaises(LocalStoreError):
            self.store.backup_to(link)
        self.assertTrue(link.is_symlink())
