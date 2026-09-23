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
    ProcessResult,
    SandboxCapabilities,
    SandboxLimits,
    minimal_environment,
    resolve_exact_revision,
    run_bounded_process,
    run_local_agent_preset,
)


class FakeSandbox:
    def __init__(self, *, behavior=None, capabilities=None):
        self.capabilities = capabilities or SandboxCapabilities(
            network_policy="disabled",
            process_tree_isolation=True,
            cpu_limit=True,
            memory_limit=True,
            disk_limit=True,
            process_limit=True,
            filesystem_isolation=True,
            credential_isolation=True,
        )
        self.behavior = behavior
        self.calls = []

    def run(self, argv, *, cwd, limits, env, stdin_text):
        self.calls.append(
            {
                "argv": tuple(argv),
                "cwd": Path(cwd),
                "limits": limits,
                "env": dict(env),
                "stdin_text": stdin_text,
            }
        )
        if self.behavior is not None:
            self.behavior(Path(cwd), tuple(argv), stdin_text)
        return ProcessResult(
            argv=tuple(argv),
            returncode=0,
            timed_out=False,
            duration_seconds=0.01,
            stdout="sandbox stdout\n",
            stderr="",
            stdout_truncated=False,
            stderr_truncated=False,
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


    def _canonical_work_unit(
        self,
        *,
        objective="Modify hello.txt safely",
        allowed_paths=None,
        forbidden_paths=None,
        network="none",
        network_allowlist=None,
    ):
        allowed_paths = ["hello.txt"] if allowed_paths is None else list(allowed_paths)
        forbidden_paths = [".github/**", "SECURITY.md"] if forbidden_paths is None else list(forbidden_paths)
        permissions = {
            "network": network,
            "network_allowlist": [] if network_allowlist is None else list(network_allowlist),
            "filesystem_write": allowed_paths,
            "secrets": [],
            "process_execution": True,
        }
        return {
            "schema_version": "0.2",
            "id": "local-agent/test-work-unit",
            "version": 1,
            "kind": "coding",
            "objective": objective,
            "inputs": [],
            "outputs": [
                {
                    "id": "candidate-patch",
                    "type": "patch",
                    "description": "Unverified local-agent candidate patch.",
                    "media_type": "text/x-diff",
                }
            ],
            "dependencies": [],
            "requirements": {
                "capabilities": ["git", "coding-agent"],
                "resources": {
                    "cpu_cores_min": 0.1,
                    "memory_mb_min": 64,
                    "disk_mb_min": 8,
                    "gpu": "none",
                    "accelerator_capabilities": [],
                },
            },
            "constraints": {
                "allowed_paths": allowed_paths,
                "forbidden_paths": forbidden_paths,
                "policies": ["candidate-only", "independent-verification-required"],
            },
            "uncertainty": [],
            "security": {
                "risk_class": "low",
                "data_classification": "public",
                "minimum_worker_trust": "untrusted",
                "sandbox_required": True,
            },
            "permissions": permissions,
            "verification_policy": {
                "strategy": "all_required",
                "independent_from_worker": True,
                "minimum_independent_verifiers": 1,
            },
            "validators": [
                {
                    "id": "independent-review",
                    "type": "review",
                    "required": True,
                }
            ],
            "evidence_requirements": [
                {"type": "artifact_hash", "required": True},
                {"type": "review", "required": True},
            ],
            "budget": {
                "wall_seconds": 20,
                "project_spend_usd_max": 0,
                "paid_fallback_allowed": False,
            },
            "provenance": {
                "created_by": "local-runner-test",
                "creator_type": "system",
                "source": "tests/test_local_agent_runner.py",
                "source_revision": self.sha,
            },
            "failure_semantics": {
                "retryable": False,
                "max_attempts": 1,
                "on_failure": "stop",
            },
        }

    def _sandbox_limits(self, **overrides):
        values = {
            "wall_seconds": 10,
            "cpu_seconds": 5,
            "memory_mb": 128,
            "disk_mb": 32,
            "max_processes": 8,
            "max_output_bytes": 4096,
            "max_stdin_bytes": 4096,
            "max_candidate_bytes": 64 * 1024,
        }
        values.update(overrides)
        return SandboxLimits(**values)

    def _test_preset(self, **overrides):
        values = {
            "preset_id": "test-local-agent",
            "agent_family": "test-agent",
            "executable": "test-agent",
            "prompt_transport": "stdin",
            "model_connection_ref": "model:local-test",
            "execution_connection_ref": "execution:test-sandbox",
            "network_policy": "disabled",
        }
        values.update(overrides)
        return AgentPreset(**values)

    def test_local_agent_boundary_uses_canonical_objective_and_durable_artifacts(self):
        def change(workspace, argv, stdin_text):
            self.assertEqual(stdin_text, "Modify hello.txt safely")
            (workspace / "hello.txt").write_text("candidate\n", encoding="utf-8")

        sandbox = FakeSandbox(behavior=change)
        artifact_dir = Path(self.temp.name) / "outside-artifacts"
        result = run_local_agent_preset(
            self._test_preset(),
            self._canonical_work_unit(),
            source_revision=self.sha,
            repository=self.repo,
            sandbox=sandbox,
            limits=self._sandbox_limits(),
            artifact_dir=artifact_dir,
        )

        self.assertIsInstance(result, LocalAgentRunResult)
        self.assertEqual(result.workspace_sha, self.sha)
        self.assertEqual(result.manifest["work_unit_id"], "local-agent/test-work-unit")
        self.assertEqual(result.manifest["status"], "succeeded")
        self.assertNotIn("model", result.manifest["worker"])
        self.assertNotIn(
            "tool_versions",
            result.manifest["provenance"]["environment"],
        )
        self.assertTrue(result.candidate.locator.startswith("file://"))
        patches = list(artifact_dir.glob("candidate-*.patch"))
        self.assertEqual(len(patches), 1)
        self.assertIn("candidate", patches[0].read_text(encoding="utf-8"))
        self.assertEqual(len(list(artifact_dir.glob("stdout-*.log"))), 1)
        self.assertEqual(sandbox.calls[0]["env"], {"PATH": os.defpath})

    def test_local_agent_boundary_supports_argument_transport_without_file_prompt(self):
        seen = {}

        def change(workspace, argv, stdin_text):
            seen["argv"] = argv
            seen["stdin"] = stdin_text
            (workspace / "hello.txt").write_text("argument candidate\n", encoding="utf-8")

        sandbox = FakeSandbox(behavior=change)
        result = run_local_agent_preset(
            self._test_preset(prompt_transport="argument", prompt_arg="--prompt"),
            self._canonical_work_unit(objective="Canonical objective"),
            source_revision=self.sha,
            repository=self.repo,
            sandbox=sandbox,
            limits=self._sandbox_limits(),
            artifact_dir=Path(self.temp.name) / "argument-artifacts",
        )
        self.assertEqual(result.manifest["status"], "succeeded")
        self.assertEqual(
            seen["argv"],
            ("test-agent", "--prompt", "Canonical objective"),
        )
        self.assertIsNone(seen["stdin"])

        with self.assertRaisesRegex(LocalRunnerError, "isolated sandbox input mount"):
            run_local_agent_preset(
                self._test_preset(prompt_transport="file"),
                self._canonical_work_unit(),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(),
                limits=self._sandbox_limits(),
                artifact_dir=Path(self.temp.name) / "file-artifacts",
            )

    def test_local_agent_boundary_fails_closed_on_sandbox_network_and_scope(self):
        weak = SandboxCapabilities(
            network_policy="disabled",
            process_tree_isolation=True,
            cpu_limit=True,
            memory_limit=False,
            disk_limit=True,
            process_limit=True,
            filesystem_isolation=True,
            credential_isolation=True,
        )
        with self.assertRaisesRegex(LocalRunnerError, "memory_limit"):
            run_local_agent_preset(
                self._test_preset(),
                self._canonical_work_unit(),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(capabilities=weak),
                limits=self._sandbox_limits(),
                artifact_dir=Path(self.temp.name) / "weak-artifacts",
            )

        with self.assertRaisesRegex(LocalRunnerError, "network policy"):
            run_local_agent_preset(
                self._test_preset(),
                self._canonical_work_unit(
                    network="allowlist",
                    network_allowlist=["model.example.invalid"],
                ),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(),
                limits=self._sandbox_limits(),
                artifact_dir=Path(self.temp.name) / "network-artifacts",
            )

        def escape(workspace, argv, stdin_text):
            (workspace / "outside.txt").write_text("escape\n", encoding="utf-8")

        with self.assertRaisesRegex(LocalRunnerError, "outside allowed scope"):
            run_local_agent_preset(
                self._test_preset(),
                self._canonical_work_unit(),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(behavior=escape),
                limits=self._sandbox_limits(),
                artifact_dir=Path(self.temp.name) / "scope-artifacts",
            )

    def test_local_agent_candidate_capture_is_bounded_and_includes_untracked_files(self):
        def create_untracked(workspace, argv, stdin_text):
            (workspace / "new.txt").write_text("new candidate\n", encoding="utf-8")

        artifact_dir = Path(self.temp.name) / "untracked-artifacts"
        result = run_local_agent_preset(
            self._test_preset(),
            self._canonical_work_unit(allowed_paths=["new.txt"]),
            source_revision=self.sha,
            repository=self.repo,
            sandbox=FakeSandbox(behavior=create_untracked),
            limits=self._sandbox_limits(),
            artifact_dir=artifact_dir,
        )
        patch = next(artifact_dir.glob("candidate-*.patch")).read_text(encoding="utf-8")
        self.assertIn("new.txt", patch)
        self.assertIn("new candidate", patch)
        self.assertTrue(result.candidate.locator.startswith("file://"))

        def huge_change(workspace, argv, stdin_text):
            (workspace / "hello.txt").write_text("x" * 5000, encoding="utf-8")

        with self.assertRaisesRegex(LocalRunnerError, "capture bounds"):
            run_local_agent_preset(
                self._test_preset(),
                self._canonical_work_unit(),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(behavior=huge_change),
                limits=self._sandbox_limits(max_candidate_bytes=128),
                artifact_dir=Path(self.temp.name) / "bounded-artifacts",
            )

    def test_local_agent_boundary_rejects_implicit_host_env_and_repo_artifacts(self):
        os.environ["SAFE_LOCAL_RUNNER_TEST"] = "should-not-leak"
        preset = self._test_preset(env_allowlist=("SAFE_LOCAL_RUNNER_TEST",))

        def change(workspace, argv, stdin_text):
            (workspace / "hello.txt").write_text("env candidate\n", encoding="utf-8")

        sandbox = FakeSandbox(behavior=change)
        run_local_agent_preset(
            preset,
            self._canonical_work_unit(),
            source_revision=self.sha,
            repository=self.repo,
            sandbox=sandbox,
            limits=self._sandbox_limits(),
            artifact_dir=Path(self.temp.name) / "env-artifacts",
        )
        self.assertNotIn("SAFE_LOCAL_RUNNER_TEST", sandbox.calls[0]["env"])

        with self.assertRaisesRegex(LocalRunnerError, "outside the canonical repository"):
            run_local_agent_preset(
                self._test_preset(),
                self._canonical_work_unit(),
                source_revision=self.sha,
                repository=self.repo,
                sandbox=FakeSandbox(behavior=change),
                limits=self._sandbox_limits(),
                artifact_dir=self.repo / "results" / "agent",
            )

    @unittest.skipUnless(os.name == "posix", "POSIX process-group cleanup test")
    def test_process_tree_cleanup_does_not_wait_for_background_child_pipes(self):
        started = __import__("time").monotonic()
        result = run_bounded_process(
            (
                sys.executable,
                "-c",
                (
                    "import subprocess,sys; "
                    "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],"
                    "stdout=sys.stdout,stderr=sys.stderr); "
                    "print('leader done')"
                ),
            ),
            cwd=self.repo,
            limits=ProcessLimits(timeout_seconds=5, max_output_bytes=1024),
        )
        elapsed = __import__("time").monotonic() - started
        self.assertEqual(result.returncode, 0)
        self.assertIn("leader done", result.stdout)
        self.assertLess(elapsed, 3.0)


if __name__ == "__main__":
    unittest.main()
