from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from idkmesh.agent_presets import AgentPreset
from idkmesh.local_agent_sandbox import (
    BubblewrapSandbox,
    SandboxUnavailableError,
)


def _preset(
    *,
    network_policy="disabled",
    prompt_transport="stdin",
    env_allowlist=(),
):
    kwargs = {
        "preset_id": "offline-agent",
        "agent_family": "offline-agent",
        "executable": "agent",
        "model_connection_ref": "model:offline",
        "execution_connection_ref": "execution:bwrap",
        "network_policy": network_policy,
        "prompt_transport": prompt_transport,
        "env_allowlist": env_allowlist,
    }
    if prompt_transport == "argument":
        kwargs["prompt_arg"] = "-p"
    return AgentPreset(**kwargs)


class LocalAgentSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_network_disabled_preset_is_admitted(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        admission = sandbox.admit(_preset())
        self.assertTrue(admission.filesystem_isolated)
        self.assertTrue(admission.network_isolated)
        self.assertTrue(admission.environment_cleared)
        self.assertTrue(admission.host_home_hidden)
        self.assertTrue(admission.docker_socket_hidden)
        self.assertEqual(
            admission.network_policy,
            "disabled",
        )

    def test_model_only_and_allowlisted_network_fail_closed(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        for policy in ("model_only", "allowlisted"):
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(
                    SandboxUnavailableError,
                    "only enforces",
                ):
                    sandbox.admit(_preset(network_policy=policy))

    def test_command_hides_host_sensitive_roots_and_clears_environment(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        argv = sandbox.build_argv(
            _preset(env_allowlist=("LANG",)),
            workspace=self.workspace,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        rendered = " ".join(argv)
        self.assertIn("--unshare-net", argv)
        self.assertIn("--clearenv", argv)
        self.assertIn("--cap-drop", argv)
        self.assertIn("--setenv LANG C.UTF-8", rendered)
        self.assertIn("--tmpfs /home", rendered)
        self.assertIn("--tmpfs /root", rendered)
        self.assertIn("--tmpfs /run", rendered)
        self.assertIn("--tmpfs /tmp", rendered)
        self.assertIn("--proc /proc", rendered)
        self.assertIn("--dev /dev", rendered)
        self.assertNotIn("--ro-bind / /", rendered)
        self.assertNotIn("/etc", argv)
        self.assertNotIn("/var", argv)
        self.assertNotIn("/opt", argv)
        self.assertIn("--bind", argv)
        self.assertIn("/workspace", argv)
        self.assertEqual(argv[-2:], ("--", "agent"))
        self.assertNotIn("GITHUB_TOKEN", rendered)
        self.assertNotIn("SSH_AUTH_SOCK", rendered)
        self.assertNotIn("DOCKER_HOST", rendered)

    def test_workspace_is_only_explicit_read_write_host_bind(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        argv = sandbox.build_argv(
            _preset(),
            workspace=self.workspace,
            env={"PATH": "/usr/bin"},
        )
        bind_positions = [
            index for index, token in enumerate(argv) if token == "--bind"
        ]
        self.assertEqual(len(bind_positions), 1)
        index = bind_positions[0]
        self.assertEqual(Path(argv[index + 1]), self.workspace.resolve())
        self.assertEqual(argv[index + 2], "/workspace")

    def test_prompt_file_must_stay_inside_workspace(self):
        preset = _preset(prompt_transport="file")
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        (self.workspace / "task.md").write_text("bounded prompt", encoding="utf-8")
        argv = sandbox.build_argv(
            preset,
            workspace=self.workspace,
            env={"PATH": "/usr/bin"},
            prompt_file="task.md",
        )
        self.assertEqual(argv[-2:], ("agent", "/workspace/task.md"))

        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (self.workspace / "escape").symlink_to(outside)

        for path in ("/etc/passwd", "../secret", "escape"):
            with self.subTest(path=path):
                with self.assertRaises(Exception):
                    sandbox.build_argv(
                        preset,
                        workspace=self.workspace,
                        env={"PATH": "/usr/bin"},
                        prompt_file=path,
                    )

    def test_non_file_prompt_rejects_prompt_file_argument(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        with self.assertRaisesRegex(Exception, "only valid"):
            sandbox.build_argv(
                _preset(),
                workspace=self.workspace,
                env={"PATH": "/usr/bin"},
                prompt_file="task.md",
            )

    def test_caller_cannot_inject_env_outside_preset_allowlist(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        with self.assertRaisesRegex(Exception, "outside preset allowlist"):
            sandbox.build_argv(
                _preset(),
                workspace=self.workspace,
                env={"PATH": "/usr/bin", "GITHUB_TOKEN": "secret"},
            )

    def test_reserved_environment_cannot_override_private_home(self):
        preset = AgentPreset(
            preset_id="offline-agent",
            agent_family="offline-agent",
            executable="agent",
            model_connection_ref="model:offline",
            execution_connection_ref="execution:bwrap",
            network_policy="disabled",
            env_allowlist=("HOME",),
        )
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        with self.assertRaisesRegex(Exception, "controller-owned"):
            sandbox.build_argv(
                preset,
                workspace=self.workspace,
                env={"PATH": "/usr/bin", "HOME": "/home/user"},
            )

    def test_invalid_environment_value_fails_before_command_build(self):
        sandbox = BubblewrapSandbox("/usr/bin/bwrap")
        with self.assertRaisesRegex(Exception, "environment value"):
            sandbox.build_argv(
                _preset(),
                workspace=self.workspace,
                env={"SAFE": "bad\x00value"},
            )

    def test_availability_requires_linux_and_bwrap(self):
        with patch(
            "idkmesh.local_agent_sandbox.sys.platform",
            "linux",
        ), patch(
            "idkmesh.local_agent_sandbox.shutil.which",
            return_value="/usr/bin/bwrap",
        ):
            self.assertTrue(BubblewrapSandbox.available())

        with patch(
            "idkmesh.local_agent_sandbox.shutil.which",
            return_value=None,
        ):
            self.assertFalse(BubblewrapSandbox.available())

    def test_missing_bwrap_fails_closed(self):
        with patch(
            "idkmesh.local_agent_sandbox.shutil.which",
            return_value=None,
        ):
            with self.assertRaises(SandboxUnavailableError):
                BubblewrapSandbox()


if __name__ == "__main__":
    unittest.main()
