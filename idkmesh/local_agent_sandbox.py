"""Fail-closed local-agent sandbox admission and bubblewrap backend.

C4-D provides one concrete hostile-code boundary for Linux hosts with
bubblewrap installed. The initial backend supports network_policy="disabled"
only. Presets requiring model-only or allowlisted network access are rejected
until a backend can enforce those egress restrictions.

The sandbox:
- clears the inherited environment and restores only explicitly supplied values;
- mounts the host root read-only;
- hides /home, /root, /run, and /tmp behind private tmpfs mounts;
- bind-mounts only the disposable workspace read-write at /workspace;
- unshares network and other namespaces;
- drops capabilities;
- runs the maintainer-owned argv without a shell.

This module does not weaken AgentPreset validation and does not grant candidate
acceptance or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import Mapping

from idkmesh.agent_presets import AgentPreset
from idkmesh.local_agent_runner import (
    LocalRunnerError,
    ProcessLimits,
    ProcessResult,
    run_bounded_process,
)


class SandboxUnavailableError(LocalRunnerError):
    """Requested sandbox guarantee cannot be enforced on this host."""


@dataclass(frozen=True)
class SandboxAdmission:
    backend: str
    network_policy: str
    filesystem_isolated: bool
    network_isolated: bool
    environment_cleared: bool
    host_home_hidden: bool
    docker_socket_hidden: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "network_policy": self.network_policy,
            "filesystem_isolated": self.filesystem_isolated,
            "network_isolated": self.network_isolated,
            "environment_cleared": self.environment_cleared,
            "host_home_hidden": self.host_home_hidden,
            "docker_socket_hidden": self.docker_socket_hidden,
        }


def _validated_env(env: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not key:
            raise LocalRunnerError("sandbox environment names must be non-empty strings")
        if not isinstance(value, str) or "\x00" in value:
            raise LocalRunnerError(f"invalid sandbox environment value for {key}")
        normalized[key] = value
    return normalized


class BubblewrapSandbox:
    """Linux bubblewrap sandbox with fully disabled network."""

    backend_id = "bubblewrap-network-disabled-v1"

    def __init__(self, executable: str | None = None) -> None:
        selected = executable or shutil.which("bwrap")
        if selected is None:
            raise SandboxUnavailableError(
                "bubblewrap is required for the network-disabled local-agent sandbox"
            )
        path = Path(selected)
        if not path.is_absolute():
            resolved = shutil.which(selected)
            if resolved is None:
                raise SandboxUnavailableError("bubblewrap executable is unavailable")
            path = Path(resolved)
        self.executable = str(path)

    @classmethod
    def available(cls) -> bool:
        return sys.platform.startswith("linux") and shutil.which("bwrap") is not None

    def admit(self, preset: AgentPreset) -> SandboxAdmission:
        if not isinstance(preset, AgentPreset):
            raise ValueError("preset must be AgentPreset")
        if not preset.sandbox_required:
            raise SandboxUnavailableError("preset does not require a sandbox")
        if preset.network_policy != "disabled":
            raise SandboxUnavailableError(
                "bubblewrap backend only enforces network_policy=disabled; "
                f"requested {preset.network_policy}"
            )
        return SandboxAdmission(
            backend=self.backend_id,
            network_policy=preset.network_policy,
            filesystem_isolated=True,
            network_isolated=True,
            environment_cleared=True,
            host_home_hidden=True,
            docker_socket_hidden=True,
        )

    def build_argv(
        self,
        preset: AgentPreset,
        *,
        workspace: str | Path,
        env: Mapping[str, str],
        prompt_file: str | None = None,
    ) -> tuple[str, ...]:
        """Build one shell-free bubblewrap command after admission."""

        self.admit(preset)
        root = Path(workspace).resolve()
        if not root.is_dir():
            raise LocalRunnerError("sandbox workspace must be an existing directory")

        safe_env = _validated_env(env)
        command = list(preset.invocation_prefix())
        if preset.prompt_transport == "file":
            if not isinstance(prompt_file, str) or not prompt_file:
                raise LocalRunnerError("file prompt transport requires prompt_file")
            prompt_path = Path(prompt_file)
            if prompt_path.is_absolute() or ".." in prompt_path.parts:
                raise LocalRunnerError(
                    "prompt_file must be a workspace-relative path"
                )
            command.append(str(Path("/workspace") / prompt_path))
        elif prompt_file is not None:
            raise LocalRunnerError(
                "prompt_file is only valid for file prompt transport"
            )

        argv: list[str] = [
            self.executable,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--unshare-net",
            "--cap-drop",
            "ALL",
            "--ro-bind",
            "/",
            "/",
            "--tmpfs",
            "/home",
            "--tmpfs",
            "/root",
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(root),
            "/workspace",
            "--chdir",
            "/workspace",
            "--clearenv",
        ]

        # HOME points into the private tmpfs rather than any host home.
        argv.extend(("--dir", "/tmp/home", "--setenv", "HOME", "/tmp/home"))
        for key, value in sorted(safe_env.items()):
            argv.extend(("--setenv", key, value))

        argv.append("--")
        argv.extend(command)
        return tuple(argv)

    def run(
        self,
        preset: AgentPreset,
        *,
        workspace: str | Path,
        env: Mapping[str, str],
        limits: ProcessLimits | None = None,
        stdin_text: str | None = None,
        prompt_file: str | None = None,
    ) -> ProcessResult:
        """Run one admitted preset through the network-disabled sandbox."""

        argv = self.build_argv(
            preset,
            workspace=workspace,
            env=env,
            prompt_file=prompt_file,
        )
        # The outer bwrap process receives only PATH so it can start. Inner
        # process environment is reconstructed by --clearenv/--setenv.
        outer_env = {"PATH": os.environ.get("PATH", os.defpath)}
        return run_bounded_process(
            argv,
            cwd=workspace,
            limits=limits,
            env=outer_env,
            stdin_text=stdin_text,
        )
