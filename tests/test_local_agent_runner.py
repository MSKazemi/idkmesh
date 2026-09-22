import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from idkmesh.local_agent_runner import (
    DisposableGitWorkspace,
    LocalRunnerError,
    ProcessLimits,
    minimal_environment,
    resolve_exact_revision,
    run_bounded_process,
)


class LocalAgentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
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
        (self.repo / "hello.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "hello.txt"), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "commit", "-q", "-m", "base"), check=True
        )
        self.sha = resolve_exact_revision(self.repo, "HEAD")

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_sha_workspace_is_disposable(self):
        with DisposableGitWorkspace(self.repo, self.sha) as workspace:
            path = workspace.path
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
            self.assertEqual(resolve_exact_revision(path, "HEAD"), self.sha)
            (path / "hello.txt").write_text("candidate\n", encoding="utf-8")
        self.assertFalse(path.exists())
        self.assertEqual(
            (self.repo / "hello.txt").read_text(encoding="utf-8"), "base\n"
        )

    def test_invalid_revision_fails_closed(self):
        with self.assertRaises(LocalRunnerError):
            with DisposableGitWorkspace(self.repo, "--upload-pack=evil"):
                pass

    def test_minimal_environment_does_not_inherit_credentials(self):
        source = {
            "PATH": "/bin",
            "SAFE_MODEL_ENDPOINT": "http://127.0.0.1:11434",
            "GITHUB_TOKEN": "secret",
            "SSH_AUTH_SOCK": "/tmp/ssh",
        }
        env = minimal_environment(("SAFE_MODEL_ENDPOINT",), source)
        self.assertEqual(
            env,
            {"PATH": "/bin", "SAFE_MODEL_ENDPOINT": "http://127.0.0.1:11434"},
        )

    def test_process_output_is_capped(self):
        result = run_bounded_process(
            (sys.executable, "-c", "print('x' * 1000)"),
            cwd=self.repo,
            limits=ProcessLimits(timeout_seconds=5, max_output_bytes=40),
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)
        self.assertTrue(result.stdout_truncated)
        self.assertLessEqual(len(result.stdout.encode()), 40)

    def test_process_timeout_is_normalized(self):
        result = run_bounded_process(
            (sys.executable, "-c", "import time; time.sleep(2)"),
            cwd=self.repo,
            limits=ProcessLimits(timeout_seconds=0.05, max_output_bytes=100),
        )
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.returncode)

    def test_stdin_is_data_not_shell(self):
        marker = Path(self.temp.name) / "should-not-exist"
        hostile = f"; touch {marker}"
        result = run_bounded_process(
            (
                sys.executable,
                "-c",
                "import sys; print(sys.stdin.read())",
            ),
            cwd=self.repo,
            stdin_text=hostile,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(hostile, result.stdout)
        self.assertFalse(marker.exists())

    def test_result_is_json_safe(self):
        result = run_bounded_process(
            (sys.executable, "-c", "print('ok')"),
            cwd=self.repo,
        )
        decoded = json.loads(result.to_json())
        self.assertEqual(decoded["returncode"], 0)
        self.assertEqual(decoded["argv"][0], sys.executable)


if __name__ == "__main__":
    unittest.main()
