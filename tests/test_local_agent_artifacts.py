import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from idkmesh.local_agent_artifacts import (
    ArtifactCaptureLimits,
    capture_local_agent_artifacts,
)
from idkmesh.local_agent_runner import (
    LocalRunnerError,
    ProcessResult,
    resolve_exact_revision,
)


def _result(stdout="worker out\n", stderr="worker err\n"):
    return ProcessResult(
        argv=("agent",),
        returncode=0,
        timed_out=False,
        duration_seconds=1.0,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
    )


class LocalAgentArtifactCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(("git", "init", "-q", str(self.repo)), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"),
            check=True,
        )
        subprocess.run(
            ("git", "-C", str(self.repo), "config", "user.name", "IDKMesh Test"),
            check=True,
        )
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "."), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "commit", "-q", "-m", "base"),
            check=True,
            env={**os.environ, "GIT_IDENTITY_OK": "1"},
        )
        self.sha = resolve_exact_revision(self.repo, "HEAD")

        self.workspace = self.root / "workspace"
        subprocess.run(
            (
                "git",
                "-C",
                str(self.repo),
                "worktree",
                "add",
                "--detach",
                str(self.workspace),
                self.sha,
            ),
            check=True,
            stdout=subprocess.DEVNULL,
        )
        self.output = self.root / "controller-output"

    def tearDown(self):
        subprocess.run(
            (
                "git",
                "-C",
                str(self.repo),
                "worktree",
                "remove",
                "--force",
                str(self.workspace),
            ),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.temp.cleanup()

    def test_capture_produces_content_addressed_bundle(self):
        (self.workspace / "tracked.txt").write_text("candidate\n", encoding="utf-8")
        (self.workspace / "new.txt").write_text("new file\n", encoding="utf-8")
        (self.workspace / "test-report.txt").write_text("tests passed\n", encoding="utf-8")

        captured = capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.output,
            process_result=_result(),
            include_paths=("test-report.txt",),
        )

        self.assertEqual(captured.source_sha, self.sha)
        self.assertEqual(captured.untracked_files, 2)
        self.assertEqual(captured.included_artifacts, ("test-report.txt",))
        self.assertTrue(captured.bundle.reference.digest.startswith("sha256:"))
        self.assertEqual(
            captured.bundle.reference.media_type,
            "application/vnd.idkmesh.local-agent-candidate+zip",
        )
        self.assertTrue(captured.bundle.reference.locator.startswith("file://"))

        bundle_path = self.output / "candidate-bundle.zip"
        with zipfile.ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("candidate.patch", names)
            self.assertIn("logs/stdout.txt", names)
            self.assertIn("logs/stderr.txt", names)
            self.assertIn("workspace/untracked/new.txt", names)
            self.assertIn("artifacts/test-report.txt", names)
            patch = archive.read("candidate.patch").decode()
            self.assertIn("-base", patch)
            self.assertIn("+candidate", patch)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["source_sha"], self.sha)

    def test_bundle_does_not_inline_duration_or_argv_authority(self):
        capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.output,
            process_result=_result(),
        )
        with zipfile.ZipFile(self.output / "candidate-bundle.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
        self.assertNotIn("duration_seconds", manifest["process"])
        self.assertNotIn("argv", manifest["process"])

    def test_source_revision_must_be_exact_object_id(self):
        with self.assertRaisesRegex(LocalRunnerError, "exact"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision="HEAD",
                output_root=self.output,
                process_result=_result(),
            )

    def test_output_root_must_be_outside_worker_workspace(self):
        with self.assertRaisesRegex(LocalRunnerError, "outside"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.workspace / "worker-controlled",
                process_result=_result(),
            )


    def test_output_root_must_be_outside_canonical_repository(self):
        forbidden_output = self.repo / "controller-output"
        with self.assertRaisesRegex(LocalRunnerError, "canonical repository"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=forbidden_output,
                process_result=_result(),
            )
        self.assertFalse(forbidden_output.exists())

    def test_existing_bundle_is_never_overwritten(self):
        self.output.mkdir(parents=True)
        existing = self.output / "candidate-bundle.zip"
        existing.write_bytes(b"retained-evidence")

        with self.assertRaisesRegex(LocalRunnerError, "never overwritten"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
            )

        self.assertEqual(existing.read_bytes(), b"retained-evidence")

    def test_workspace_git_rebinding_fails_closed(self):
        other = self.root / "other"
        other.mkdir()
        subprocess.run(("git", "init", "-q", str(other)), check=True)
        (self.workspace / ".git").write_text(
            f"gitdir: {other / '.git'}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(LocalRunnerError, "expected repository"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
            )

    def test_rebinding_to_a_clone_holding_the_source_sha_fails_closed(self):
        """A clone resolves the same SHA, so only the common-dir check can fail."""
        clone = self.root / "clone"
        subprocess.run(
            ("git", "clone", "-q", "--no-local", str(self.repo), str(clone)),
            check=True,
        )
        self.assertEqual(resolve_exact_revision(clone, self.sha), self.sha)
        (self.workspace / ".git").write_text(
            f"gitdir: {clone / '.git'}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(LocalRunnerError, "expected repository"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
            )

    def test_committed_candidate_is_captured_against_controller_source_sha(self):
        """A worker that commits its work cannot hide the candidate diff."""
        (self.workspace / "tracked.txt").write_text("candidate\n", encoding="utf-8")
        subprocess.run(
            ("git", "-C", str(self.workspace), "add", "tracked.txt"),
            check=True,
        )
        subprocess.run(
            ("git", "-C", str(self.workspace), "commit", "-q", "-m", "worker commit"),
            check=True,
            env={**os.environ, "GIT_IDENTITY_OK": "1"},
        )
        head = resolve_exact_revision(self.workspace, "HEAD")
        self.assertNotEqual(head, self.sha)

        captured = capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.output,
            process_result=_result(),
        )
        self.assertEqual(captured.source_sha, self.sha)
        with zipfile.ZipFile(self.output / "candidate-bundle.zip") as archive:
            patch = archive.read("candidate.patch").decode()
            manifest = json.loads(archive.read("manifest.json"))
        self.assertIn("-base", patch)
        self.assertIn("+candidate", patch)
        self.assertEqual(manifest["source_sha"], self.sha)

    def test_identical_input_reproduces_the_same_bundle_digest(self):
        """The recorded digest must be replayable, not a one-off observation."""
        (self.workspace / "tracked.txt").write_text("candidate\n", encoding="utf-8")
        (self.workspace / "new.txt").write_text("new file\n", encoding="utf-8")

        first = capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.root / "out-first",
            process_result=_result(),
        )
        second = capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.root / "out-second",
            process_result=_result(),
        )
        self.assertEqual(first.bundle.reference.digest, second.bundle.reference.digest)
        first_bytes = (self.root / "out-first" / "candidate-bundle.zip").read_bytes()
        second_bytes = (self.root / "out-second" / "candidate-bundle.zip").read_bytes()
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(
            first.bundle.reference.digest,
            "sha256:" + hashlib.sha256(first_bytes).hexdigest(),
        )

        # Two captures a second apart would still agree by luck, so pin the
        # entry metadata that makes the bytes independent of the wall clock.
        with zipfile.ZipFile(self.root / "out-first" / "candidate-bundle.zip") as archive:
            for info in archive.infolist():
                self.assertEqual(
                    info.date_time,
                    (1980, 1, 1, 0, 0, 0),
                    f"{info.filename} carries a wall-clock timestamp",
                )
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.external_attr, 0o100644 << 16)

        # Positive control: a different candidate must not reproduce the digest.
        (self.workspace / "new.txt").write_text("different\n", encoding="utf-8")
        third = capture_local_agent_artifacts(
            workspace=self.workspace,
            repository=self.repo,
            source_revision=self.sha,
            output_root=self.root / "out-third",
            process_result=_result(),
        )
        self.assertNotEqual(first.bundle.reference.digest, third.bundle.reference.digest)

    def test_non_utf8_git_capture_fails_closed(self):
        """Replaced bytes must never be content-addressed as the candidate."""
        (self.workspace / "tracked.txt").write_bytes(b"caf\xe9 latin-1\n")
        with self.assertRaisesRegex(LocalRunnerError, "not valid UTF-8"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
            )
        self.assertFalse((self.output / "candidate-bundle.zip").exists())

    def test_untracked_symlink_is_rejected(self):
        target = self.root / "outside-secret.txt"
        target.write_text("outside", encoding="utf-8")
        (self.workspace / "escape").symlink_to(target)
        with self.assertRaisesRegex(LocalRunnerError, "symlink"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
            )

    def test_file_and_bundle_limits_fail_closed(self):
        (self.workspace / "large.bin").write_bytes(b"x" * 20)
        with self.assertRaisesRegex(LocalRunnerError, "max_file_bytes"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                limits=ArtifactCaptureLimits(
                    max_file_bytes=10,
                    max_bundle_bytes=1024,
                ),
            )

    def test_patch_limit_fails_closed(self):
        (self.workspace / "tracked.txt").write_text("x" * 1000, encoding="utf-8")
        with self.assertRaisesRegex(LocalRunnerError, "byte limit"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                limits=ArtifactCaptureLimits(max_patch_bytes=40),
            )

    def test_too_many_untracked_files_fail_closed(self):
        (self.workspace / "a.txt").write_text("a", encoding="utf-8")
        (self.workspace / "b.txt").write_text("b", encoding="utf-8")
        with self.assertRaisesRegex(LocalRunnerError, "too many"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                limits=ArtifactCaptureLimits(max_untracked_files=1),
            )

    def test_include_paths_must_not_be_one_string(self):
        with self.assertRaisesRegex(ValueError, "iterable"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                include_paths="test-report.txt",
            )

    def test_explicit_artifact_path_traversal_fails_closed(self):
        with self.assertRaisesRegex(LocalRunnerError, "relative"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                include_paths=("../outside.txt",),
            )

    def test_bundle_name_must_be_safe_filename(self):
        with self.assertRaisesRegex(ValueError, "safe"):
            capture_local_agent_artifacts(
                workspace=self.workspace,
                repository=self.repo,
                source_revision=self.sha,
                output_root=self.output,
                process_result=_result(),
                bundle_name="../escape.zip",
            )


if __name__ == "__main__":
    unittest.main()
