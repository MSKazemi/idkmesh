"""Jules Session creation with explicit SCM revision binding for C2-C (#575).

Jules currently accepts a GitHub starting branch in SourceContext. The public
v1alpha API does not document a commit-SHA field for Session creation. IDKMesh
therefore preserves exact-source semantics by requiring trusted SCM evidence
that the selected starting branch is pinned to the requested revision before a
Session can be created.

This module does not create that branch, approve plans, observe activities, or
accept provider output.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from idkmesh.connector_errors import ConnectorError


_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_ALLOWED_AUTOMATION_MODES = {None, "AUTO_CREATE_PR"}


class JulesSessionClient(Protocol):
    def post_json(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST one Jules JSON request."""


class JulesSourceValidator(Protocol):
    def validate_github_source(
        self,
        *,
        source_name: str,
        github_owner: str,
        github_repo: str,
        starting_branch: str,
    ) -> Any:
        """Verify a configured Jules Source against repository authority."""


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ScmRevisionBinding:
    """Trusted SCM observation that a branch resolves to one exact revision."""

    github_owner: str
    github_repo: str
    branch: str
    revision: str
    verified: bool

    def __post_init__(self) -> None:
        for name in ("github_owner", "github_repo", "branch"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        revision = _nonempty(self.revision, "revision")
        if _REVISION_RE.fullmatch(revision) is None:
            raise ValueError("revision must be a 40- or 64-character hexadecimal digest")
        object.__setattr__(self, "revision", revision.lower())
        if type(self.verified) is not bool:
            raise ValueError("verified must be a boolean")


@dataclass(frozen=True)
class JulesSessionRequest:
    work_unit_id: str
    prompt: str
    title: str
    source_name: str
    binding: ScmRevisionBinding
    automation_mode: str | None = None

    def __post_init__(self) -> None:
        for name in ("work_unit_id", "prompt", "title", "source_name"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        if self.automation_mode not in _ALLOWED_AUTOMATION_MODES:
            raise ValueError("unsupported Jules automation_mode")


@dataclass(frozen=True)
class JulesSessionHandle:
    session_name: str
    session_id: str
    work_unit_id: str
    source_name: str
    starting_branch: str
    requested_source_revision: str
    revision_binding: str
    require_plan_approval: bool
    automation_mode: str | None
    repository: str
    state: str | None = None
    url: str | None = None


def _response_string(
    value: Any,
    *,
    field: str,
    connection_id: str,
    required: bool = True,
) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Session metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _parse_created_session(
    raw: Mapping[str, Any],
    *,
    request: JulesSessionRequest,
    connection_id: str,
) -> JulesSessionHandle:
    name = _response_string(
        raw.get("name"),
        field="name",
        connection_id=connection_id,
    )
    session_id = _response_string(
        raw.get("id"),
        field="id",
        connection_id=connection_id,
    )
    assert name is not None and session_id is not None
    if not name.startswith("sessions/") or len(name) <= len("sessions/"):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned an invalid Session resource name.",
            connection_id=connection_id,
        )

    source_context = raw.get("sourceContext")
    if not isinstance(source_context, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules Session response is missing SourceContext.",
            connection_id=connection_id,
        )
    observed_source = _response_string(
        source_context.get("source"),
        field="sourceContext.source",
        connection_id=connection_id,
    )
    repo_context = source_context.get("githubRepoContext")
    if not isinstance(repo_context, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules Session response is missing GitHubRepoContext.",
            connection_id=connection_id,
        )
    observed_branch = _response_string(
        repo_context.get("startingBranch"),
        field="sourceContext.githubRepoContext.startingBranch",
        connection_id=connection_id,
    )

    if observed_source != request.source_name or observed_branch != request.binding.branch:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules Session response does not match the requested source context.",
            connection_id=connection_id,
            details={
                "requested_source": request.source_name,
                "observed_source": observed_source,
                "requested_branch": request.binding.branch,
                "observed_branch": observed_branch,
            },
        )

    state = _response_string(
        raw.get("state"),
        field="state",
        connection_id=connection_id,
        required=False,
    )
    url = _response_string(
        raw.get("url"),
        field="url",
        connection_id=connection_id,
        required=False,
    )

    return JulesSessionHandle(
        session_name=name,
        session_id=session_id,
        work_unit_id=request.work_unit_id,
        source_name=request.source_name,
        starting_branch=request.binding.branch,
        requested_source_revision=request.binding.revision,
        revision_binding="scm_pinned_branch",
        require_plan_approval=True,
        automation_mode=request.automation_mode,
        repository=f"{request.binding.github_owner}/{request.binding.github_repo}",
        state=state,
        url=url,
    )


class JulesSessionService:
    """Create one Jules Session only after repository/source admission."""

    def __init__(
        self,
        client: JulesSessionClient,
        source_validator: JulesSourceValidator,
        *,
        connection_id: str,
    ) -> None:
        self._connection_id = _nonempty(connection_id, "connection_id")
        self._client = client
        self._source_validator = source_validator

    def create_session(self, request: JulesSessionRequest) -> JulesSessionHandle:
        if not request.binding.verified:
            raise ConnectorError(
                code="policy_denied",
                message="Jules Session creation requires verified SCM revision binding.",
                connection_id=self._connection_id,
                details={
                    "work_unit_id": request.work_unit_id,
                    "revision_binding": "unverified",
                },
            )

        self._source_validator.validate_github_source(
            source_name=request.source_name,
            github_owner=request.binding.github_owner,
            github_repo=request.binding.github_repo,
            starting_branch=request.binding.branch,
        )

        payload: dict[str, Any] = {
            "prompt": request.prompt,
            "title": request.title,
            "sourceContext": {
                "source": request.source_name,
                "githubRepoContext": {
                    "startingBranch": request.binding.branch,
                },
            },
            # Jules defaults to automatic plan approval. IDKMesh deliberately
            # overrides that provider default for the initial connector.
            "requirePlanApproval": True,
        }
        if request.automation_mode is not None:
            payload["automationMode"] = request.automation_mode

        raw = self._client.post_json("/sessions", body=payload)
        return _parse_created_session(
            raw,
            request=request,
            connection_id=self._connection_id,
        )
