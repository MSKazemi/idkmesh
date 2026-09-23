"""Deterministic GitHub bootstrap file plan for C8-A (#663).

This module defines what a future idkmesh init --github bootstrap owns and
which operations remain repository-owner responsibilities. It performs no
filesystem writes, network calls, GitHub mutation, secret access, or workflow
execution.

The file plan is intentionally useful before rendering exists:

- C8-B can expose it as dry-run output.
- C8-C can render the project/config/DomainPack entries.
- C8-D can render the thin workflow wrappers.
- C8-F can enforce the ownership/overwrite rules on re-run.

A generated file may describe a future execution effect, for example explicit
candidate dispatch, but no bootstrap file grants integration or merge
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


BOOTSTRAP_PLAN_VERSION = "0.1"

OWNERSHIP_CLASSES = frozenset({"user_seed", "idkmesh_managed"})
BOOTSTRAP_PHASES = frozenset({"C8-C", "C8-D"})
OVERWRITE_POLICIES = frozenset(
    {
        "create_if_absent",
        "replace_if_generated_digest_matches",
    }
)
EXECUTION_EFFECTS = frozenset(
    {
        "none",
        "candidate_dispatch",
        "verification",
        "publication",
    }
)

_FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SEMVER_NUMBER = r"(?:0|[1-9][0-9]*)"
_SEMVER_PRERELEASE_ID = (
    r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
)
_RELEASE_TAG = re.compile(
    rf"v{_SEMVER_NUMBER}\.{_SEMVER_NUMBER}\.{_SEMVER_NUMBER}"
    rf"(?:-{_SEMVER_PRERELEASE_ID}(?:\.{_SEMVER_PRERELEASE_ID})*)?\Z"
)
_SAFE_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")


class BootstrapPlanError(ValueError):
    """Fail-closed bootstrap-plan validation error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _repo_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise BootstrapPlanError("invalid_path", "repository path must be non-empty")
    if (
        value.startswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise BootstrapPlanError("invalid_path", f"unsafe repository path: {value!r}")
    parts = value.split("/")
    if any(
        part in {"", ".", ".."} or part.casefold() == ".git"
        for part in parts
    ):
        raise BootstrapPlanError("invalid_path", f"unsafe repository path: {value!r}")
    return value


def _pinned_idkmesh_ref(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise BootstrapPlanError(
            "unpinned_idkmesh_ref",
            "an explicit release tag or full Git SHA is required",
        )
    if _FULL_SHA.fullmatch(value) or _RELEASE_TAG.fullmatch(value):
        return value
    raise BootstrapPlanError(
        "unpinned_idkmesh_ref",
        "use a vMAJOR.MINOR.PATCH release tag or full 40-character lowercase Git SHA",
    )


def _default_branch(value: object) -> str:
    if not isinstance(value, str) or _SAFE_BRANCH.fullmatch(value) is None:
        raise BootstrapPlanError("invalid_default_branch", "unsupported branch name")
    parts = value.split("/")
    if (
        any(part.startswith(".") or part.endswith((".", ".lock")) for part in parts)
        or value.endswith("/")
        or "//" in value
        or ".." in value
        or "@{" in value
    ):
        raise BootstrapPlanError("invalid_default_branch", "unsupported branch name")
    return value


@dataclass(frozen=True)
class BootstrapFileSpec:
    """One planned repository file and its update/authority contract."""

    path: str
    ownership: str
    phase: str
    overwrite_policy: str
    purpose: str
    render_source: str
    execution_effect: str = "none"
    secret_values_allowed: bool = False
    integration_authority: bool = False

    def __post_init__(self) -> None:
        _repo_path(self.path)
        if self.ownership not in OWNERSHIP_CLASSES:
            raise BootstrapPlanError(
                "invalid_ownership",
                f"{self.path}: unknown ownership class {self.ownership!r}",
            )
        if self.phase not in BOOTSTRAP_PHASES:
            raise BootstrapPlanError(
                "invalid_phase",
                f"{self.path}: unknown bootstrap phase {self.phase!r}",
            )
        if self.overwrite_policy not in OVERWRITE_POLICIES:
            raise BootstrapPlanError(
                "invalid_overwrite_policy",
                f"{self.path}: unknown overwrite policy",
            )
        if (
            self.ownership == "user_seed"
            and self.overwrite_policy != "create_if_absent"
        ):
            raise BootstrapPlanError(
                "unsafe_user_overwrite",
                f"{self.path}: user_seed files must be create_if_absent",
            )
        if (
            self.ownership == "idkmesh_managed"
            and self.overwrite_policy != "replace_if_generated_digest_matches"
        ):
            raise BootstrapPlanError(
                "unsafe_managed_overwrite",
                f"{self.path}: managed files require generated-digest matching",
            )
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise BootstrapPlanError(
                "invalid_purpose",
                f"{self.path}: purpose must be non-empty",
            )
        if not isinstance(self.render_source, str) or not self.render_source.strip():
            raise BootstrapPlanError(
                "invalid_render_source",
                f"{self.path}: render source must be non-empty",
            )
        if self.execution_effect not in EXECUTION_EFFECTS:
            raise BootstrapPlanError(
                "invalid_execution_effect",
                f"{self.path}: unknown execution effect {self.execution_effect!r}",
            )
        if self.secret_values_allowed is not False:
            raise BootstrapPlanError(
                "secret_values_forbidden",
                f"{self.path}: generated files may contain references, never secret values",
            )
        if self.integration_authority is not False:
            raise BootstrapPlanError(
                "integration_authority_forbidden",
                f"{self.path}: bootstrap files cannot grant integration/merge authority",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ownership": self.ownership,
            "phase": self.phase,
            "overwrite_policy": self.overwrite_policy,
            "purpose": self.purpose,
            "render_source": self.render_source,
            "execution_effect": self.execution_effect,
            "secret_values_allowed": self.secret_values_allowed,
            "integration_authority": self.integration_authority,
        }


@dataclass(frozen=True)
class OwnerAction:
    """A setup action intentionally left outside automatic bootstrap authority."""

    code: str
    summary: str
    reason: str
    requires_repository_owner: bool = True
    automatic: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{1,63}", self.code
        ):
            raise BootstrapPlanError("invalid_owner_action", "invalid owner action code")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise BootstrapPlanError(
                "invalid_owner_action",
                f"{self.code}: summary must be non-empty",
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise BootstrapPlanError(
                "invalid_owner_action",
                f"{self.code}: reason must be non-empty",
            )
        if self.requires_repository_owner is not True or self.automatic is not False:
            raise BootstrapPlanError(
                "owner_action_must_remain_manual",
                f"{self.code}: owner-only setup must not become automatic",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "summary": self.summary,
            "reason": self.reason,
            "requires_repository_owner": self.requires_repository_owner,
            "automatic": self.automatic,
        }


@dataclass(frozen=True)
class GitHubBootstrapPlan:
    """Immutable, deterministic plan consumed by later C8 render/apply slices."""

    plan_version: str
    idkmesh_ref: str
    default_branch: str
    files: tuple[BootstrapFileSpec, ...]
    owner_actions: tuple[OwnerAction, ...]

    def __post_init__(self) -> None:
        if self.plan_version != BOOTSTRAP_PLAN_VERSION:
            raise BootstrapPlanError(
                "unsupported_plan_version",
                f"expected bootstrap plan {BOOTSTRAP_PLAN_VERSION}",
            )
        _pinned_idkmesh_ref(self.idkmesh_ref)
        _default_branch(self.default_branch)

        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise BootstrapPlanError("duplicate_path", "bootstrap file paths must be unique")

        action_codes = [item.code for item in self.owner_actions]
        if len(action_codes) != len(set(action_codes)):
            raise BootstrapPlanError(
                "duplicate_owner_action",
                "owner action codes must be unique",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_version": self.plan_version,
            "idkmesh_ref": self.idkmesh_ref,
            "default_branch": self.default_branch,
            "files": [item.to_dict() for item in self.files],
            "owner_actions": [item.to_dict() for item in self.owner_actions],
        }


def _managed(
    path: str,
    phase: str,
    purpose: str,
    render_source: str,
    *,
    execution_effect: str = "none",
) -> BootstrapFileSpec:
    return BootstrapFileSpec(
        path=path,
        ownership="idkmesh_managed",
        phase=phase,
        overwrite_policy="replace_if_generated_digest_matches",
        purpose=purpose,
        render_source=render_source,
        execution_effect=execution_effect,
    )


def _user_seed(
    path: str,
    phase: str,
    purpose: str,
    render_source: str,
) -> BootstrapFileSpec:
    return BootstrapFileSpec(
        path=path,
        ownership="user_seed",
        phase=phase,
        overwrite_policy="create_if_absent",
        purpose=purpose,
        render_source=render_source,
    )


def build_github_bootstrap_plan(
    *,
    idkmesh_ref: str,
    default_branch: str = "main",
) -> GitHubBootstrapPlan:
    """Build the canonical no-server GitHub bootstrap plan.

    The function is pure: it reads no files, environment variables, network
    endpoints, or repository settings.
    """

    pinned_ref = _pinned_idkmesh_ref(idkmesh_ref)
    branch = _default_branch(default_branch)

    files = (
        _managed(
            ".github/workflows/idkmesh-dispatch.yml",
            "C8-D",
            "Explicit candidate-generation dispatch wrapper with least-privilege permissions.",
            "template:c8-d/idkmesh-dispatch.yml",
            execution_effect="candidate_dispatch",
        ),
        _managed(
            ".github/workflows/idkmesh-preview.yml",
            "C8-D",
            "Read-only issue/WorkUnit preview and deterministic route explanation wrapper.",
            "template:c8-d/idkmesh-preview.yml",
        ),
        _managed(
            ".github/workflows/idkmesh-status.yml",
            "C8-D",
            "Read-only/publication-safe GitHub status and evidence summary wrapper.",
            "template:c8-d/idkmesh-status.yml",
            execution_effect="publication",
        ),
        _managed(
            ".github/workflows/idkmesh-verify.yml",
            "C8-D",
            "Independent verification wrapper over an exact candidate revision.",
            "template:c8-d/idkmesh-verify.yml",
            execution_effect="verification",
        ),
        _managed(
            ".idkmesh/README.md",
            "C8-C",
            "Explain generated project configuration, ownership rules, and safe re-run behavior.",
            "template:c8-c/idkmesh-readme.md",
        ),
        _user_seed(
            ".idkmesh/connections.json",
            "C8-C",
            "Project connector profile seed containing capability policy and secret references only.",
            "template:c8-c/connections.json",
        ),
        _managed(
            ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json",
            "C8-C",
            "Repository-local copy of the software-engineering DomainPack required by ProjectManifest v0.1.",
            (
                f"idkmesh:{pinned_ref}:"
                "examples/domain-packs/software-engineering-v0.1.domain-pack.json"
            ),
        ),
        _user_seed(
            ".idkmesh/project.json",
            "C8-C",
            "ProjectManifest seed that binds this repository to local DomainPacks and protected human integration.",
            "template:c8-c/project.json",
        ),
    )

    owner_actions = (
        OwnerAction(
            code="authorize-provider-apps",
            summary="Install or authorize only the provider/agent apps the project chooses to use.",
            reason="Third-party app authorization changes repository trust and cannot be inferred safely.",
        ),
        OwnerAction(
            code="configure-branch-protection",
            summary=f"Protect the {branch!r} integration branch with project-appropriate rules.",
            reason="Bootstrap may inspect/report governance later but must not silently mutate admin policy.",
        ),
        OwnerAction(
            code="configure-provider-secrets",
            summary="Create provider secret values in GitHub Secrets or approved external secret storage.",
            reason="Generated files contain secret references only; bootstrap never creates or reads secret values.",
        ),
        OwnerAction(
            code="configure-secret-environments",
            summary="Configure approval-protected GitHub Environments for secret-bearing/high-risk operations when required.",
            reason="Environment reviewers and protection rules are repository-owner governance decisions.",
        ),
    )

    return GitHubBootstrapPlan(
        plan_version=BOOTSTRAP_PLAN_VERSION,
        idkmesh_ref=pinned_ref,
        default_branch=branch,
        files=tuple(sorted(files, key=lambda item: item.path)),
        owner_actions=tuple(sorted(owner_actions, key=lambda item: item.code)),
    )
