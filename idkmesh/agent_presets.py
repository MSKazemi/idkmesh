"""Maintainer-owned local coding-agent preset contract.

This module implements C4-A of issue #577. It describes allowed local-agent
invocations but deliberately does not execute them. Task/issue text is data;
it cannot choose executables, fixed arguments, environment names, network
policy, or sandbox authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from types import MappingProxyType
from typing import Iterable, Mapping

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_CONNECTION_REF = re.compile(r"^[a-z][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$")
_ENV = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PROMPT_TRANSPORTS = {"stdin", "argument", "file"}
NETWORK_POLICIES = {"disabled", "model_only", "allowlisted"}
FORBIDDEN_ENV_NAMES = frozenset(
    {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "SSH_AUTH_SOCK",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "DOCKER_HOST",
    }
)
_SECRET_ENV_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS")


def _tuple(values: Iterable[str] | tuple[str, ...]) -> tuple[str, ...]:
    return values if isinstance(values, tuple) else tuple(values)


@dataclass(frozen=True)
class AgentPreset:
    """Reviewable description of one allowlisted local coding-agent worker."""

    preset_id: str
    agent_family: str
    executable: str
    fixed_args: tuple[str, ...] = ()
    prompt_transport: str = "stdin"
    prompt_arg: str = ""
    model_connection_ref: str = ""
    execution_connection_ref: str = ""
    env_allowlist: tuple[str, ...] = ()
    network_policy: str = "disabled"
    sandbox_required: bool = True
    candidate_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixed_args", _tuple(self.fixed_args))
        object.__setattr__(self, "env_allowlist", _tuple(self.env_allowlist))

        if not _ID.fullmatch(self.preset_id):
            raise ValueError("preset_id must be a lowercase stable identifier")
        if not _ID.fullmatch(self.agent_family):
            raise ValueError("agent_family must be a lowercase stable identifier")
        if (
            not isinstance(self.executable, str)
            or not self.executable
            or self.executable in {".", ".."}
            or "/" in self.executable
            or "\\" in self.executable
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in self.executable)
        ):
            raise ValueError("executable must be one safe PATH-resolved argv token")
        executable_name = self.executable.casefold().removesuffix(".exe")
        if executable_name in {"sh", "bash", "zsh", "cmd", "powershell", "pwsh"}:
            raise ValueError("shell executables are not valid agent presets")
        if any(
            not isinstance(arg, str)
            or any(ord(char) < 32 or ord(char) == 127 for char in arg)
            for arg in self.fixed_args
        ):
            raise ValueError("fixed_args must contain plain argv tokens")
        if self.prompt_transport not in PROMPT_TRANSPORTS:
            raise ValueError(f"unknown prompt_transport: {self.prompt_transport}")
        if self.prompt_transport == "argument" and (
            not isinstance(self.prompt_arg, str)
            or not self.prompt_arg
            or any(char.isspace() or ord(char) < 32 for char in self.prompt_arg)
        ):
            raise ValueError("argument prompt transport requires prompt_arg")
        if self.prompt_transport != "argument" and self.prompt_arg:
            raise ValueError("prompt_arg is only valid for argument transport")
        if not isinstance(self.model_connection_ref, str) or not _CONNECTION_REF.fullmatch(
            self.model_connection_ref
        ):
            raise ValueError("model_connection_ref must be a stable namespaced reference")
        if not isinstance(
            self.execution_connection_ref, str
        ) or not _CONNECTION_REF.fullmatch(self.execution_connection_ref):
            raise ValueError("execution_connection_ref must be a stable namespaced reference")
        if self.network_policy not in NETWORK_POLICIES:
            raise ValueError(f"unknown network_policy: {self.network_policy}")
        if not self.sandbox_required:
            raise ValueError("local coding-agent presets must require a sandbox")
        if not self.candidate_only:
            raise ValueError("agent presets cannot receive acceptance authority")

        env_names = set(self.env_allowlist)
        invalid_env = sorted(name for name in env_names if not _ENV.fullmatch(name))
        if invalid_env:
            raise ValueError("invalid env allowlist name(s): " + ", ".join(invalid_env))
        forbidden = sorted(env_names.intersection(FORBIDDEN_ENV_NAMES))
        forbidden.extend(
            sorted(
                name
                for name in env_names
                if name.endswith(_SECRET_ENV_SUFFIXES) and name not in forbidden
            )
        )
        if forbidden:
            raise ValueError(
                "host/repository credential env names are forbidden: "
                + ", ".join(forbidden)
            )
        if len(env_names) != len(self.env_allowlist):
            raise ValueError("env_allowlist must not contain duplicates")

    def invocation_prefix(self) -> tuple[str, ...]:
        """Return only maintainer-owned argv; never includes task/prompt text."""
        return (self.executable, *self.fixed_args)

    def to_json(self) -> str:
        """Return deterministic JSON suitable for config/provenance digests."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


# These entries describe worker identities and safety boundaries only. Exact
# provider-specific command flags belong in separately reviewed preset updates
# after a smoke test against the pinned tool version.
_BUILTIN_PRESETS = {
    "goose-local": AgentPreset(
        preset_id="goose-local",
        agent_family="goose",
        executable="goose",
        model_connection_ref="model:local-default",
        execution_connection_ref="execution:bounded-local",
        network_policy="model_only",
    ),
    "antigravity-cli-free": AgentPreset(
        preset_id="antigravity-cli-free",
        agent_family="antigravity-cli",
        executable="agy",
        prompt_transport="argument",
        prompt_arg="-p",
        model_connection_ref="model:antigravity-personal",
        execution_connection_ref="execution:bounded-local",
        network_policy="model_only",
    ),
    "mini-swe-agent-local": AgentPreset(
        preset_id="mini-swe-agent-local",
        agent_family="mini-swe-agent",
        executable="mini",
        model_connection_ref="model:local-default",
        execution_connection_ref="execution:bounded-local",
        network_policy="model_only",
    ),
}

BUILTIN_AGENT_PRESETS: Mapping[str, AgentPreset] = MappingProxyType(_BUILTIN_PRESETS)


def get_builtin_preset(preset_id: str) -> AgentPreset:
    """Resolve only an allowlisted maintainer-owned preset."""
    try:
        return BUILTIN_AGENT_PRESETS[preset_id]
    except KeyError as exc:
        raise KeyError(f"unknown local agent preset: {preset_id}") from exc
