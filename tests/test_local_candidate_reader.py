import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from idkmesh.local_candidate_reader import (
    LocalArtifactBundleReader,
    LocalArtifactResolutionError,
)


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class LocalArtifactBundleReaderTests(unittest.TestCase):
    def test_regular_file_becomes_content_addressed_candidate(self):
        payload = b"diff --git a/x b/x\n+verified candidate\n"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate.patch"
            candidate.write_bytes(payload)

            result = LocalArtifactBundleReader(
                root,
                max_bytes=1024,
            ).resolve(
                relative_path="candidate.patch",
                media_type="text/x-diff",
            )

            self.assertEqual(result.size_bytes, len(payload))
            self.assertEqual(result.reference.type, "artifact_bundle")
            self.assertEqual(result.reference.digest, _digest(payload))
            self.assertEqual(result.reference.media_type, "text/x-diff")
            self.assertEqual(result.reference.locator, candidate.resolve().as_uri())

    def test_expected_digest_is_checked_against_observed_bytes(self):
        payload = b"candidate"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bundle.bin").write_bytes(payload)
            reader = LocalArtifactBundleReader(root, max_bytes=1024)

            ok = reader.resolve(
                relative_path="bundle.bin",
                expected_digest=_digest(payload),
            )
            self.assertEqual(ok.reference.digest, _digest(payload))

            with self.assertRaisesRegex(
                LocalArtifactResolutionError,
                "does not match",
            ):
                reader.resolve(
                    relative_path="bundle.bin",
                    expected_digest="sha256:" + "0" * 64,
                )

    def test_size_limit_fails_closed_before_large_file_is_accepted(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "too-large.bin").write_bytes(b"x" * 33)
            reader = LocalArtifactBundleReader(root, max_bytes=32)

            with self.assertRaisesRegex(
                LocalArtifactResolutionError,
                "size limit",
            ):
                reader.resolve(relative_path="too-large.bin")

    def test_parent_traversal_and_absolute_paths_are_rejected_before_read(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside.bin"
            outside.write_bytes(b"outside")
            reader = LocalArtifactBundleReader(workspace, max_bytes=1024)

            with self.assertRaises(ValueError):
                reader.resolve(relative_path="../outside.bin")
            with self.assertRaises(ValueError):
                reader.resolve(relative_path=str(outside.resolve()))

    def test_directory_is_not_a_candidate_bundle(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dir").mkdir()
            reader = LocalArtifactBundleReader(root, max_bytes=1024)
            with self.assertRaisesRegex(
                LocalArtifactResolutionError,
                "regular file",
            ):
                reader.resolve(relative_path="dir")

    def test_symlink_alias_is_rejected_when_platform_supports_symlinks(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.bin"
            target.write_bytes(b"candidate")
            alias = root / "alias.bin"
            try:
                alias.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this platform")

            reader = LocalArtifactBundleReader(root, max_bytes=1024)
            with self.assertRaisesRegex(
                LocalArtifactResolutionError,
                "symlinks",
            ):
                reader.resolve(relative_path="alias.bin")

    def test_invalid_expected_digest_fails_before_candidate_resolution(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bundle.bin").write_bytes(b"candidate")
            reader = LocalArtifactBundleReader(root, max_bytes=1024)
            for digest in ("", "sha1:" + "0" * 40, "sha256:" + "A" * 64):
                with self.subTest(digest=digest):
                    with self.assertRaises(ValueError):
                        reader.resolve(
                            relative_path="bundle.bin",
                            expected_digest=digest,
                        )

    def test_resolution_carries_no_acceptance_or_verification_authority(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bundle.bin").write_bytes(b"candidate")
            result = LocalArtifactBundleReader(root, max_bytes=1024).resolve(
                relative_path="bundle.bin"
            )
            for field in (
                "run_state",
                "accepted",
                "verified",
                "merge_authorized",
                "integration_authorized",
            ):
                self.assertFalse(hasattr(result, field))
                self.assertFalse(hasattr(result.reference, field))

    def test_reader_configuration_is_explicit_and_bounded(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for limit in (0, -1, True, 1.5):
                with self.subTest(limit=limit):
                    with self.assertRaises(ValueError):
                        LocalArtifactBundleReader(root, max_bytes=limit)

            with self.assertRaises(ValueError):
                LocalArtifactBundleReader(root / "missing", max_bytes=1)


if __name__ == "__main__":
    unittest.main()
