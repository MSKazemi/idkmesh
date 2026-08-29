import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import checkpoint_manifest as cm


REPOSITORY = "MSKazemi/idkmesh"
WORKFLOW = "evolution-loop.yml"
RUN_ID = 12345
HEAD_SHA = "a" * 40
EVENT_NAME = "workflow_dispatch"


class CheckpointManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state.json"
        self.events = self.root / "events.jsonl"
        self.state.write_text('{"version": 2}\n', encoding="utf-8")
        self.events.write_text('{"kind": "push"}\n', encoding="utf-8")
        self.files = {
            "evolution-state.json": self.state,
            "evolution-events.jsonl": self.events,
        }

    def build(self, **overrides):
        fields = {
            "repository": REPOSITORY,
            "workflow": WORKFLOW,
            "run_id": RUN_ID,
            "head_sha": HEAD_SHA,
            "event_name": EVENT_NAME,
            "parent_run_id": 12000,
            "files": self.files,
        }
        fields.update(overrides)
        return cm.build_manifest(**fields)

    def verify(self, manifest, **overrides):
        fields = {
            "repository": REPOSITORY,
            "workflow": WORKFLOW,
            "run_id": RUN_ID,
            "head_sha": HEAD_SHA,
            "event_name": EVENT_NAME,
            "parent_run_id": 12000,
            "files": self.files,
        }
        fields.update(overrides)
        cm.verify_manifest(manifest, **fields)

    def test_round_trip_binds_provenance_and_named_file_content(self):
        manifest = self.build()
        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual(12000, manifest["provenance"]["parent_run_id"])
        self.assertEqual(
            ["evolution-events.jsonl", "evolution-state.json"],
            [entry["name"] for entry in manifest["files"]],
        )
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in manifest["files"]))
        path = self.root / "checkpoint-manifest.json"
        cm.write_manifest(path, manifest)
        self.verify(cm.load_manifest(path))

    def test_optional_parent_is_bound(self):
        manifest = self.build(parent_run_id=None)
        self.verify(manifest, parent_run_id=None)
        with self.assertRaisesRegex(cm.ManifestError, "parent_run_id"):
            self.verify(manifest, parent_run_id=12000)

    def test_parent_must_precede_run(self):
        with self.assertRaisesRegex(cm.ManifestError, "earlier run"):
            self.build(parent_run_id=RUN_ID)

        # Consumers can still validate all externally discoverable run
        # provenance when the producing run's optional parent is unknown.
        fields = {
            "repository": REPOSITORY,
            "workflow": WORKFLOW,
            "run_id": RUN_ID,
            "head_sha": HEAD_SHA,
            "event_name": EVENT_NAME,
            "files": self.files,
        }
        cm.verify_manifest(self.build(), **fields)

    def test_rejects_unknown_schema_and_malformed_manifest(self):
        manifest = self.build()
        manifest["schema_version"] = 99
        with self.assertRaisesRegex(cm.ManifestError, "unsupported"):
            self.verify(manifest)
        manifest["schema_version"] = True
        with self.assertRaisesRegex(cm.ManifestError, "unsupported"):
            self.verify(manifest)

        path = self.root / "broken.json"
        path.write_text("{not-json", encoding="utf-8")
        with self.assertRaisesRegex(cm.ManifestError, "cannot load manifest"):
            cm.load_manifest(path)

        malformed = self.build()
        malformed["files"][0]["extra"] = True
        with self.assertRaisesRegex(cm.ManifestError, "unexpected or missing"):
            self.verify(malformed)

    def test_rejects_every_provenance_mismatch(self):
        manifest = self.build()
        cases = {
            "repository": "someone/else",
            "workflow": "other.yml",
            "run_id": 54321,
            "head_sha": "b" * 40,
            "event_name": "push",
            "parent_run_id": 11999,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(cm.ManifestError, field):
                    self.verify(manifest, **{field: value})

    def test_rejects_duplicate_and_unsafe_file_specs(self):
        with self.assertRaisesRegex(cm.ManifestError, "duplicate file name"):
            cm.parse_file_specs([f"state={self.state}", f"state={self.events}"])
        with self.assertRaisesRegex(cm.ManifestError, "duplicate file path"):
            cm.parse_file_specs([f"state={self.state}", f"alias={self.state}"])
        for name in ("../state", "/state", "nested/../state", "nested\\state", ".", "line\nbreak", ""):
            with self.subTest(name=name):
                with self.assertRaises(cm.ManifestError):
                    cm.parse_file_specs([f"{name}={self.state}"])
        with self.assertRaisesRegex(cm.ManifestError, "NAME=PATH"):
            cm.parse_file_specs(["state.json"])

    def test_rejects_duplicate_and_unsafe_manifest_names(self):
        manifest = self.build()
        duplicate = copy.deepcopy(manifest)
        duplicate["files"].append(copy.deepcopy(duplicate["files"][0]))
        with self.assertRaisesRegex(cm.ManifestError, "duplicate"):
            self.verify(duplicate)
        unsafe = copy.deepcopy(manifest)
        unsafe["files"][0]["name"] = "../outside"
        with self.assertRaisesRegex(cm.ManifestError, "unsafe"):
            self.verify(unsafe)

    def test_rejects_missing_file_and_file_set_mismatch(self):
        manifest = self.build()
        self.events.unlink()
        with self.assertRaisesRegex(cm.ManifestError, "missing regular file"):
            self.verify(manifest)
        with self.assertRaisesRegex(cm.ManifestError, "file set"):
            self.verify(manifest, files={"evolution-state.json": self.state})

    def test_rejects_size_and_hash_mismatch(self):
        manifest = self.build()
        self.state.write_text("different length", encoding="utf-8")
        with self.assertRaisesRegex(cm.ManifestError, "size mismatch"):
            self.verify(manifest)

        self.state.write_text('{"version": 3}\n', encoding="utf-8")
        with self.assertRaisesRegex(cm.ManifestError, "SHA-256 mismatch"):
            self.verify(manifest)

    def test_cli_create_and_verify(self):
        path = self.root / "manifest.json"
        common = [
            "--manifest",
            str(path),
            "--repository",
            REPOSITORY,
            "--workflow",
            WORKFLOW,
            "--run-id",
            str(RUN_ID),
            "--head-sha",
            HEAD_SHA,
            "--event-name",
            EVENT_NAME,
            "--file",
            f"state.json={self.state}",
        ]
        self.assertEqual(0, cm.main(["create", *common]))
        self.assertEqual(0, cm.main(["verify", *common]))
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNone(value["provenance"]["parent_run_id"])

    def test_cli_can_verify_without_knowing_optional_parent(self):
        path = self.root / "manifest.json"
        common = [
            "--manifest",
            str(path),
            "--repository",
            REPOSITORY,
            "--workflow",
            WORKFLOW,
            "--run-id",
            str(RUN_ID),
            "--head-sha",
            HEAD_SHA,
            "--event-name",
            EVENT_NAME,
            "--file",
            f"state.json={self.state}",
        ]
        self.assertEqual(0, cm.main(["create", *common, "--parent-run-id", "12000"]))
        self.assertEqual(0, cm.main(["verify", *common]))


if __name__ == "__main__":
    unittest.main()
