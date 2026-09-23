"""Jules Source lookup and repository/branch validation for C2-B (#575).

A Jules Source is provider metadata, not repository authority. This module
validates that the configured source resolves to the GitHub repository and
starting branch that IDKMesh already authorized.

No source is created or mutated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from idkmesh.connector_errors import ConnectorError


class JulesSourceClient(Protocol):
    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """Return one decoded Jules JSON object."""


@dataclass(frozen=True)
class JulesSource:
    name: str
    source_id: str
    github_owner: str
    github_repo: str
    is_private: bool | None
    default_branch: str | None
    branches: tuple[str, ...]


def _nonempty_string(value: Any, field: str, connection_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Source metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _source_request_path(source_name: str, connection_id: str) -> str:
    if (
        not isinstance(source_name, str)
        or not source_name.startswith("sources/")
        or len(source_name) <= len("sources/")
        or "?" in source_name
        or "#" in source_name
        or "://" in source_name
    ):
        raise ConnectorError(
            code="configuration_error",
            message="Configured Jules source name is invalid.",
            connection_id=connection_id,
        )
    return "/" + source_name


def parse_jules_source(
    raw: Mapping[str, Any],
    *,
    connection_id: str,
    expected_name: str | None = None,
) -> JulesSource:
    """Normalize one Jules Source response and fail closed on malformed fields."""

    if not isinstance(raw, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Source metadata.",
            connection_id=connection_id,
        )

    name = _nonempty_string(raw.get("name"), "name", connection_id)
    source_id = _nonempty_string(raw.get("id"), "id", connection_id)
    if expected_name is not None and name != expected_name:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a different Source than requested.",
            connection_id=connection_id,
            details={"requested_source": expected_name, "observed_source": name},
        )

    github_repo = raw.get("githubRepo")
    if not isinstance(github_repo, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules Source is missing GitHub repository metadata.",
            connection_id=connection_id,
            details={"source_name": name},
        )

    owner = _nonempty_string(github_repo.get("owner"), "githubRepo.owner", connection_id)
    repo = _nonempty_string(github_repo.get("repo"), "githubRepo.repo", connection_id)

    is_private = github_repo.get("isPrivate")
    if is_private is not None and type(is_private) is not bool:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Source privacy metadata.",
            connection_id=connection_id,
            details={"source_name": name},
        )

    default_branch = None
    default_raw = github_repo.get("defaultBranch")
    if default_raw is not None:
        if not isinstance(default_raw, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed default-branch metadata.",
                connection_id=connection_id,
                details={"source_name": name},
            )
        default_branch = _nonempty_string(
            default_raw.get("displayName"),
            "githubRepo.defaultBranch.displayName",
            connection_id,
        )

    branch_names: list[str] = []
    branches_raw = github_repo.get("branches", [])
    if not isinstance(branches_raw, list):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed branch metadata.",
            connection_id=connection_id,
            details={"source_name": name},
        )
    for index, branch in enumerate(branches_raw):
        if not isinstance(branch, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed branch metadata.",
                connection_id=connection_id,
                details={"source_name": name, "branch_index": index},
            )
        branch_name = _nonempty_string(
            branch.get("displayName"),
            f"githubRepo.branches[{index}].displayName",
            connection_id,
        )
        if branch_name not in branch_names:
            branch_names.append(branch_name)

    return JulesSource(
        name=name,
        source_id=source_id,
        github_owner=owner,
        github_repo=repo,
        is_private=is_private,
        default_branch=default_branch,
        branches=tuple(branch_names),
    )


class JulesSourceService:
    """Read and validate configured Jules Source metadata."""

    def __init__(self, client: JulesSourceClient, *, connection_id: str) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._client = client
        self._connection_id = connection_id

    def get_source(self, source_name: str) -> JulesSource:
        path = _source_request_path(source_name, self._connection_id)
        try:
            raw = self._client.get_json(path)
        except ConnectorError as exc:
            if exc.code == "not_found":
                raise ConnectorError(
                    code="source_not_connected",
                    message="Configured Jules source is not connected.",
                    connection_id=self._connection_id,
                    details={"source_name": source_name},
                ) from exc
            raise
        return parse_jules_source(
            raw,
            connection_id=self._connection_id,
            expected_name=source_name,
        )

    def validate_github_source(
        self,
        *,
        source_name: str,
        github_owner: str,
        github_repo: str,
        starting_branch: str,
    ) -> JulesSource:
        """Bind provider metadata to an already-authorized repository context."""

        for value, field in (
            (github_owner, "github_owner"),
            (github_repo, "github_repo"),
            (starting_branch, "starting_branch"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ConnectorError(
                    code="configuration_error",
                    message="Jules Source validation configuration is incomplete.",
                    connection_id=self._connection_id,
                    details={"field": field},
                )

        source = self.get_source(source_name)
        observed_repo = f"{source.github_owner}/{source.github_repo}"
        expected_repo = f"{github_owner}/{github_repo}"
        if (
            source.github_owner.casefold() != github_owner.casefold()
            or source.github_repo.casefold() != github_repo.casefold()
        ):
            raise ConnectorError(
                code="configuration_error",
                message="Configured Jules source does not match the authorized GitHub repository.",
                connection_id=self._connection_id,
                details={
                    "source_name": source.name,
                    "expected_repository": expected_repo,
                    "observed_repository": observed_repo,
                },
            )

        advertised = set(source.branches)
        if source.default_branch is not None:
            advertised.add(source.default_branch)
        if starting_branch not in advertised:
            raise ConnectorError(
                code="configuration_error",
                message="Configured Jules source does not advertise the authorized starting branch.",
                connection_id=self._connection_id,
                details={
                    "source_name": source.name,
                    "starting_branch": starting_branch,
                },
            )
        return source
