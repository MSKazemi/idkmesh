import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from idkmesh.agent_presets import AgentPreset
from idkmesh.local_agent_runner import (
    DisposableGitWorkspace,
    LocalAgentRunResult,
    LocalRunnerError,
    ProcessLimits,
    minimal_environment,
    resolve_exact_revision,
    run_bounded_process,
    run_local_agent_preset,
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
            ("git", "-C", str(self.repo), "commit", "-q", "-m", "base"),
            check=True,
            env={**os.environ, "GIT_IDENTITY_OK": "1"},
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

    def test_both_output_streams_are_drained_and_capped(self):
        result = run_bounded_process(
            (
                sys.executable,
                "-c",
                "import os; os.write(1, b'x' * 2000000); os.write(2, b'y' * 2000000)",
            ),
            cwd=self.repo,
            limits=ProcessLimits(timeout_seconds=10, max_output_bytes=97),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.encode()), 97)
        self.assertEqual(len(result.stderr.encode()), 97)
        self.assertTrue(result.stdout_truncated)
        self.assertTrue(result.stderr_truncated)

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

    def test_oversized_stdin_fails_before_process_start(self):
        marker = Path(self.temp.name) / "started"
        with self.assertRaisesRegex(LocalRunnerError, "max_stdin_bytes"):
            run_bounded_process(
                (sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"),
                cwd=self.repo,
                stdin_text="abcd",
                limits=ProcessLimits(max_stdin_bytes=3),
            )
        self.assertFalse(marker.exists())

    def test_limits_reject_boolean_non_finite_and_non_integer_values(self):
        for kwargs in (
            {"timeout_seconds": True},
            {"timeout_seconds": float("inf")},
            {"timeout_seconds": float("nan")},
            {"max_output_bytes": True},
            {"max_output_bytes": 1.5},
            {"max_stdin_bytes": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ProcessLimits(**kwargs)

    def test_environment_names_and_values_are_validated(self):
        for name in ("bad-name", "A=B", ""):
            with self.subTest(name=name):
                with self.assertRaises(LocalRunnerError):
                    minimal_environment((name,), {})
        with self.assertRaises(LocalRunnerError):
            minimal_environment(("SAFE",), {"SAFE": "bad\x00value"})

    def test_result_is_json_safe(self):
        result = run_bounded_process(
            (sys.executable, "-c", "print('ok')"),
            cwd=self.repo,
        )
        decoded = json.loads(result.to_json())
        self.assertEqual(decoded["returncode"], 0)
        self.assertEqual(decoded["argv"][0], sys.executable)

    def test_run_local_agent_preset_stdin_transport(self):
        work_unit = {
            "id": "wu-stdin-1",
            "version": 1,
            "prompt": "Harmless WorkUnit task description",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        preset = AgentPreset(
            preset_id="test-agent-stdin",
            agent_family="python-agent",
            executable="python3",
            fixed_args=("-c", "import sys; print('REC:' + sys.stdin.read().strip())"),
            prompt_transport="stdin",
            model_connection_ref="model:local-test",
            execution_connection_ref="execution:bounded-local",
        )
        run_res = run_local_agent_preset(
            preset,
            work_unit,
            source_revision=self.sha,
            repository=self.repo,
        )
        self.assertIsInstance(run_res, LocalAgentRunResult)
        self.assertEqual(run_res.manifest["status"], "succeeded")
        self.assertEqual(run_res.manifest["work_unit_id"], "wu-stdin-1")
        self.assertIn("REC:Harmless WorkUnit task description", run_res.process_result.stdout)
        decoded_json = json.loads(run_res.to_json())
        self.assertEqual(decoded_json["manifest"]["id"], run_res.manifest["id"])

    def test_run_local_agent_preset_argument_transport(self):
        work_unit = {
            "id": "wu-arg-1",
            "version": 1,
            "prompt": "Prompt text for argument transport",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        preset = AgentPreset(
            preset_id="test-agent-arg",
            agent_family="python-agent",
            executable="python3",
            fixed_args=("-c", "import sys; print('ARG:' + sys.argv[2])"),
            prompt_transport="argument",
            prompt_arg="-p",
            model_connection_ref="model:local-test",
            execution_connection_ref="execution:bounded-local",
        )
        run_res = run_local_agent_preset(
            preset,
            work_unit,
            source_revision=self.sha,
            repository=self.repo,
        )
        self.assertEqual(run_res.manifest["status"], "succeeded")
        self.assertIn("ARG:Prompt text for argument transport", run_res.process_result.stdout)

    def test_run_local_agent_preset_file_transport(self):
        work_unit = {
            "id": "wu-file-1",
            "version": 1,
            "prompt": "Prompt text written to file",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        preset = AgentPreset(
            preset_id="test-agent-file",
            agent_family="python-agent",
            executable="python3",
            fixed_args=("-c", "import sys, pathlib; print('FILE:' + pathlib.Path(sys.argv[1]).read_text())"),
            prompt_transport="file",
            model_connection_ref="model:local-test",
            execution_connection_ref="execution:bounded-local",
        )
        run_res = run_local_agent_preset(
            preset,
            work_unit,
            source_revision=self.sha,
            repository=self.repo,
        )
        self.assertEqual(run_res.manifest["status"], "succeeded")
        self.assertIn("FILE:Prompt text written to file", run_res.process_result.stdout)

    def test_run_local_agent_preset_captures_diff_patch_and_artifacts(self):
        work_unit = {
            "id": "wu-patch-1",
            "version": 1,
            "prompt": "Modify hello.txt",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        preset = AgentPreset(
            preset_id="test-agent-patch",
            agent_family="python-agent",
            executable="python3",
            fixed_args=("-c", "open('hello.txt', 'w').write('candidate code change\\n')"),
            prompt_transport="stdin",
            model_connection_ref="model:local-test",
            execution_connection_ref="execution:bounded-local",
        )
        artifact_dir = Path(self.temp.name) / "artifacts"
        run_res = run_local_agent_preset(
            preset,
            work_unit,
            source_revision=self.sha,
            repository=self.repo,
            artifact_dir=artifact_dir,
        )
        self.assertEqual(run_res.manifest["status"], "succeeded")
        self.assertIn("candidate code change", run_res.patch_text)
        self.assertEqual(run_res.candidate.type, "artifact_bundle")
        self.assertTrue(artifact_dir.exists())

    def test_run_local_agent_preset_timeout_normalization(self):
        work_unit = {
            "id": "wu-timeout-1",
            "version": 1,
            "prompt": "Sleep longer than limit",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        preset = AgentPreset(
            preset_id="test-agent-timeout",
            agent_family="python-agent",
            executable="python3",
            fixed_args=("-c", "import time; time.sleep(2)"),
            prompt_transport="stdin",
            model_connection_ref="model:local-test",
            execution_connection_ref="execution:bounded-local",
        )
        run_res = run_local_agent_preset(
            preset,
            work_unit,
            source_revision=self.sha,
            repository=self.repo,
            limits=ProcessLimits(timeout_seconds=0.05),
        )
        self.assertEqual(run_res.manifest["status"], "timeout")
        self.assertTrue(run_res.process_result.timed_out)

    def test_run_local_agent_preset_invalid_preset_or_env_fails(self):
        work_unit = {
            "id": "wu-env-1",
            "version": 1,
            "prompt": "Test invalid preset",
            "provenance": {"source_revision": self.sha},
            "validators": [{"id": "pytest", "type": "command"}],
        }
        with self.assertRaises(LocalRunnerError):
            run_local_agent_preset(
                12345,  # type: ignore[arg-type]
                work_unit,
                source_revision=self.sha,
                repository=self.repo,
            )


if __name__ == "__main__":
    unittest.main()
