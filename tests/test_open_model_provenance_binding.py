"""The producer's model identity must be observed, never asserted.

Before this binding existed, `--image` was a free-form string and the probe
stamped hardcoded constants into every ResultManifest. Building an image around
different weights therefore produced evidence naming a model that had never run,
with nothing in the artifact to reveal the substitution. These tests pin the
properties that make that impossible.
"""

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


probe = _load("open_model_benchmark_probe", "tools/open_model_benchmark_probe.py")
generator = _load("open_model_text_generator", "tools/open_model_text_generator.py")

KNOWN_DIGEST = next(iter(probe.MODEL_REGISTRY))


class ResolveModelIdentityTests(unittest.TestCase):
    def test_registered_digest_resolves_to_its_recorded_name(self):
        resolved = probe.resolve_model_identity({"model_identity": {"snapshot_digest": KNOWN_DIGEST}})
        self.assertEqual(resolved["name"], probe.MODEL_REGISTRY[KNOWN_DIGEST]["name"])
        self.assertEqual(resolved["revision"], probe.MODEL_REGISTRY[KNOWN_DIGEST]["revision"])
        self.assertEqual(resolved["observed"]["snapshot_digest"], KNOWN_DIGEST)

    def test_missing_identity_block_is_a_harness_failure(self):
        # ProbeError, not ProducerOutcome: a malformed candidate is a measurable
        # experiment result, but evidence that cannot name its own model is not.
        with self.assertRaises(probe.ProbeError):
            probe.resolve_model_identity({})

    def test_missing_or_malformed_digest_is_rejected(self):
        for identity in ({}, {"snapshot_digest": None}, {"snapshot_digest": "md5:abc"}):
            with self.assertRaises(probe.ProbeError):
                probe.resolve_model_identity({"model_identity": identity})

    def test_unregistered_digest_is_rejected_rather_than_relabelled(self):
        # This is the substitution case: unknown weights must never inherit the
        # name of the model that happens to be hardcoded.
        with self.assertRaises(probe.ProbeError) as caught:
            probe.resolve_model_identity({"model_identity": {"snapshot_digest": "sha256:" + "0" * 64}})
        self.assertIn("MODEL_REGISTRY", str(caught.exception))

    def test_expected_digest_mismatch_aborts(self):
        with self.assertRaises(probe.ProbeError):
            probe.resolve_model_identity(
                {"model_identity": {"snapshot_digest": KNOWN_DIGEST}},
                "sha256:" + "1" * 64,
            )

    def test_expected_digest_match_is_accepted(self):
        resolved = probe.resolve_model_identity(
            {"model_identity": {"snapshot_digest": KNOWN_DIGEST}}, KNOWN_DIGEST
        )
        self.assertEqual(resolved["observed"]["snapshot_digest"], KNOWN_DIGEST)


class NoAssertedIdentityTests(unittest.TestCase):
    def test_probe_source_carries_no_hardcoded_model_constants(self):
        # Regression guard for the original defect: identity may not be spelled
        # out in the host source, because the host cannot observe it.
        source = (ROOT / "tools/open_model_benchmark_probe.py").read_text(encoding="utf-8")
        self.assertNotIn("MODEL_NAME", source)
        self.assertNotIn("MODEL_REVISION", source)
        # The manifest id must be derived from the resolved slug, not written in.
        self.assertNotIn("open-model-qwen25coder05b", source)

    def test_worker_id_follows_the_resolved_model(self):
        self.assertTrue(probe.default_worker_id("some-model").endswith("/some-model"))
        self.assertNotEqual(probe.default_worker_id("a"), probe.default_worker_id("b"))


class SnapshotIdentityTests(unittest.TestCase):
    def test_digest_covers_file_names_not_just_bytes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.bin").write_bytes(b"one")
            (root / "b.bin").write_bytes(b"two")
            first = generator.snapshot_identity(root)["snapshot_digest"]
            # Same bytes, different names: a rename must change the fingerprint.
            (root / "a.bin").rename(root / "c.bin")
            second = generator.snapshot_identity(root)["snapshot_digest"]
        self.assertNotEqual(first, second)

    def test_digest_changes_when_weights_change(self):
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "w.bin").write_bytes(b"weights-v1")
            first = generator.snapshot_identity(root)["snapshot_digest"]
            (root / "w.bin").write_bytes(b"weights-v2")
            second = generator.snapshot_identity(root)["snapshot_digest"]
        self.assertNotEqual(first, second)

    def test_digest_is_stable_for_identical_content(self):
        import tempfile

        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                (root / "w.bin").write_bytes(b"weights")
                (root / "config.json").write_text(json.dumps({"model_type": "qwen2"}))
                digests.append(generator.snapshot_identity(root)["snapshot_digest"])
        self.assertEqual(digests[0], digests[1])

    def test_config_fields_are_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "config.json").write_text(
                json.dumps({"architectures": ["Qwen2ForCausalLM"], "model_type": "qwen2", "hidden_size": 896})
            )
            identity = generator.snapshot_identity(root)
        self.assertEqual(identity["architectures"], ["Qwen2ForCausalLM"])
        self.assertEqual(identity["model_type"], "qwen2")
        self.assertEqual(identity["hidden_size"], 896)

    def test_unreadable_config_does_not_abort_the_fingerprint(self):
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "w.bin").write_bytes(b"weights")
            (root / "config.json").write_text("{not json")
            identity = generator.snapshot_identity(root)
        self.assertTrue(identity["snapshot_digest"].startswith("sha256:"))
        self.assertIsNone(identity["model_type"])


class SelfTestTests(unittest.TestCase):
    def test_probe_self_test_passes(self):
        self.assertEqual(probe.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
