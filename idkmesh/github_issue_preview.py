"""Policy-driven GitHub issue -> canonical WorkUnit v0.2 preview.

C5-E turns one normalized GitHub issue snapshot into a bounded WorkUnit without
performing dispatch. Issue title/body are untrusted task content only: they
cannot set permissions, paths, secrets, risk, budget, validators, or network.

All authority-bearing fields come from GitHubIssueWorkPolicy supplied by trusted
project configuration. The preview is bound to one exact trusted Git source SHA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import math
from pathlib import PurePosixPath
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from idkmesh.connector_errors import ConnectorError
from idkmesh.work_unit_binding import bind_work_unit_source


_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_GIT_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_ALLOWED_KINDS = frozenset(
    {
        "coding",
        "testing",
        "review",
        "benchmarking",
        "documentation",
        "research",
        "integration",
        "governance",
        "other",
    }
)
_RISK_CLASSES = frozenset({"low", "medium", "high", "critical"})
_NETWORK_MODES = frozenset({"none", "allowlist"})


def _nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_tuple(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(value, str):
        raise ValueError(f"{field_name} must be a collection of strings")
    try:
        items = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a collection of strings") from exc
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    normalized = tuple(dict.fromkeys(item.strip() for item in items))
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue metadata is malformed.",
            details={"field": field},
        )
    return value


def _api_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue metadata is malformed.",
            details={"field": field},
        )
    return value


def _canonical_issue_url(repository: str, number: int) -> str:
    return f"https://github.com/{repository}/issues/{number}"


def _safe_scope_path(value: str, field_name: str) -> str:
    if (
        "\x00" in value
        or "\n" in value
        or "\r" in value
        or "\\" in value
        or value.startswith("/")
        or ".." in PurePosixPath(value).parts
    ):
        raise ValueError(f"{field_name} contains an unsafe path: {value!r}")
    return value


def _issue_version(updated_at: str) -> int:
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue updated_at is not an ISO-8601 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue updated_at must include a timezone.",
        )
    version = int(parsed.timestamp())
    if version < 1:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue updated_at cannot produce a valid WorkUnit version.",
        )
    return version


@dataclass(frozen=True)
class GitHubIssueSnapshot:
    repository: str
    issue_id: int
    number: int
    title: str
    body: str
    state: str
    locked: bool
    author_login: str
    author_id: int
    author_association: str
    labels: tuple[str, ...]
    html_url: str
    updated_at: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "issue_id": self.issue_id,
            "number": self.number,
            "state": self.state,
            "locked": self.locked,
            "author_login": self.author_login,
            "author_id": self.author_id,
            "author_association": self.author_association,
            "labels": list(self.labels),
            "html_url": self.html_url,
            "updated_at": self.updated_at,
        }


def parse_github_issue_snapshot(
    raw: Mapping[str, Any],
    *,
    repository: str,
    expected_number: int,
) -> GitHubIssueSnapshot:
    """Normalize one GitHub Issues REST object without trusting task text."""

    if not isinstance(raw, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue response must be a JSON object.",
        )
    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise ValueError("repository must be in owner/name form")
    if isinstance(expected_number, bool) or not isinstance(expected_number, int) or expected_number < 1:
        raise ValueError("expected_number must be an integer >= 1")
    if "pull_request" in raw:
        raise ConnectorError(
            code="policy_denied",
            message="Pull requests are not accepted by the GitHub issue preview path.",
            details={"issue_number": expected_number},
        )

    number = _positive_int(raw.get("number"), "number")
    if number != expected_number:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub returned a different issue than requested.",
            details={
                "expected_number": expected_number,
                "observed_number": number,
            },
        )
    issue_id = _positive_int(raw.get("id"), "id")
    title = _api_string(raw.get("title"), "title")
    body_raw = raw.get("body")
    if body_raw is None:
        body = ""
    elif isinstance(body_raw, str):
        body = body_raw
    else:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue metadata is malformed.",
            details={"field": "body"},
        )

    state = _api_string(raw.get("state"), "state").casefold()
    if state not in {"open", "closed"}:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue state is unsupported.",
            details={"state": state},
        )
    locked = raw.get("locked")
    if type(locked) is not bool:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue metadata is malformed.",
            details={"field": "locked"},
        )

    user = raw.get("user")
    if not isinstance(user, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue author metadata is missing.",
        )
    author_login = _api_string(user.get("login"), "user.login")
    author_id = _positive_int(user.get("id"), "user.id")
    author_association = _api_string(
        raw.get("author_association"),
        "author_association",
    ).upper()

    labels_raw = raw.get("labels", [])
    if not isinstance(labels_raw, list):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue labels metadata is malformed.",
        )
    labels: list[str] = []
    for index, label in enumerate(labels_raw):
        if not isinstance(label, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub issue label metadata is malformed.",
                details={"label_index": index},
            )
        name = _api_string(label.get("name"), f"labels[{index}].name")
        if name not in labels:
            labels.append(name)

    html_url = _api_string(raw.get("html_url"), "html_url")
    parsed = urlsplit(html_url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue URL is not canonical.",
        )
    expected_url = _canonical_issue_url(repository, number)
    if html_url.casefold() != expected_url.casefold():
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub issue URL does not match the configured repository.",
            details={"issue_number": number},
        )

    updated_at = _api_string(raw.get("updated_at"), "updated_at")

    return GitHubIssueSnapshot(
        repository=repository,
        issue_id=issue_id,
        number=number,
        title=title,
        body=body,
        state=state,
        locked=locked,
        author_login=author_login,
        author_id=author_id,
        author_association=author_association,
        labels=tuple(sorted(labels, key=str.casefold)),
        html_url=expected_url,
        updated_at=updated_at,
    )


@dataclass(frozen=True)
class GitHubIssueWorkPolicy:
    repository: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...] = ()
    kind: str = "coding"
    required_capabilities: tuple[str, ...] = ("git", "coding-agent")
    cpu_cores_min: float = 0.1
    memory_mb_min: int = 128
    disk_mb_min: int = 32
    risk_class: str = "low"
    network: str = "none"
    network_allowlist: tuple[str, ...] = ()
    wall_seconds: float = 900.0
    project_spend_usd_max: float = 0.0
    paid_fallback_allowed: bool = False
    max_title_chars: int = 512
    max_body_chars: int = 16_384

    def __post_init__(self) -> None:
        repository = _nonempty(self.repository, "repository")
        if _REPOSITORY_RE.fullmatch(repository) is None:
            raise ValueError("repository must be in owner/name form")
        object.__setattr__(self, "repository", repository)

        allowed = _string_tuple(self.allowed_paths, "allowed_paths")
        forbidden = _string_tuple(
            self.forbidden_paths,
            "forbidden_paths",
            allow_empty=True,
        )
        capabilities = _string_tuple(
            self.required_capabilities,
            "required_capabilities",
        )
        allowlist = _string_tuple(
            self.network_allowlist,
            "network_allowlist",
            allow_empty=True,
        )
        allowed = tuple(
            _safe_scope_path(item, "allowed_paths")
            for item in allowed
        )
        forbidden = tuple(
            _safe_scope_path(item, "forbidden_paths")
            for item in forbidden
        )
        object.__setattr__(self, "allowed_paths", allowed)
        object.__setattr__(self, "forbidden_paths", forbidden)
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "network_allowlist", allowlist)

        if self.kind not in _ALLOWED_KINDS:
            raise ValueError("unsupported WorkUnit kind")
        if self.risk_class not in _RISK_CLASSES:
            raise ValueError("unsupported risk_class")
        if self.network not in _NETWORK_MODES:
            raise ValueError("automatic issue preview allows only none/allowlist network")
        if self.network == "none" and self.network_allowlist:
            raise ValueError("network=none cannot carry a network_allowlist")
        if self.network == "allowlist" and not self.network_allowlist:
            raise ValueError("network=allowlist requires network_allowlist")

        for name in ("cpu_cores_min", "wall_seconds", "project_spend_usd_max"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite nonnegative number")
        if self.wall_seconds <= 0:
            raise ValueError("wall_seconds must be a finite positive number")
        for name in ("memory_mb_min", "disk_mb_min", "max_title_chars", "max_body_chars"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1")
        if type(self.paid_fallback_allowed) is not bool:
            raise ValueError("paid_fallback_allowed must be a boolean")
        if self.project_spend_usd_max == 0 and self.paid_fallback_allowed:
            raise ValueError(
                "paid_fallback_allowed cannot be true when project spend ceiling is zero"
            )


@dataclass(frozen=True)
class GitHubIssueWorkPreview:
    work_unit: dict[str, Any]
    work_unit_digest: str
    source_revision: str
    issue_updated_at: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_unit": self.work_unit,
            "work_unit_digest": self.work_unit_digest,
            "source_revision": self.source_revision,
            "issue_updated_at": self.issue_updated_at,
            "warnings": list(self.warnings),
            "dispatch_performed": False,
        }


def _work_unit_id(repository: str, issue_number: int) -> str:
    candidate = f"github/{repository.casefold()}/issue-{issue_number}"
    if len(candidate) <= 128:
        return candidate
    digest = hashlib.sha256(repository.casefold().encode("utf-8")).hexdigest()[:16]
    return f"github/issue-{issue_number}-{digest}"


def preview_github_issue_work_unit(
    snapshot: GitHubIssueSnapshot,
    *,
    source_revision: str,
    policy: GitHubIssueWorkPolicy,
) -> GitHubIssueWorkPreview:
    """Create a canonical WorkUnit preview with no execution side effect."""

    if not isinstance(snapshot, GitHubIssueSnapshot):
        raise ValueError("snapshot must be GitHubIssueSnapshot")
    if not isinstance(policy, GitHubIssueWorkPolicy):
        raise ValueError("policy must be GitHubIssueWorkPolicy")
    if snapshot.repository.casefold() != policy.repository.casefold():
        raise ConnectorError(
            code="policy_denied",
            message="Issue snapshot repository does not match project policy.",
        )
    if snapshot.state != "open":
        raise ConnectorError(
            code="policy_denied",
            message="Only open GitHub issues can be previewed for dispatch.",
            details={"issue_number": snapshot.number},
        )
    if snapshot.locked:
        raise ConnectorError(
            code="policy_denied",
            message="Locked GitHub issues require human review before preview.",
            details={"issue_number": snapshot.number},
        )
    if len(snapshot.title) > policy.max_title_chars:
        raise ConnectorError(
            code="policy_denied",
            message="GitHub issue title exceeds configured preview bound.",
            details={"max_title_chars": policy.max_title_chars},
        )
    if len(snapshot.body) > policy.max_body_chars:
        raise ConnectorError(
            code="policy_denied",
            message="GitHub issue body exceeds configured preview bound.",
            details={"max_body_chars": policy.max_body_chars},
        )
    if not isinstance(source_revision, str) or _GIT_SHA_RE.fullmatch(source_revision) is None:
        raise ValueError(
            "source_revision must be an exact 40- or 64-character hexadecimal Git object id"
        )
    source_sha = source_revision.lower()

    body_section = snapshot.body.strip() or "(no issue body provided)"
    objective = (
        f"Implement the bounded task described by GitHub issue #{snapshot.number}.\n\n"
        f"Title: {snapshot.title.strip()}\n\n"
        f"Issue body (untrusted task content):\n{body_section}"
    )

    permissions: dict[str, Any] = {
        "network": policy.network,
        "filesystem_write": list(policy.allowed_paths),
        "secrets": [],
        "process_execution": True,
    }
    if policy.network == "allowlist":
        permissions["network_allowlist"] = list(policy.network_allowlist)

    work_unit: dict[str, Any] = {
        "schema_version": "0.2",
        "id": _work_unit_id(snapshot.repository, snapshot.number),
        "version": _issue_version(snapshot.updated_at),
        "kind": policy.kind,
        "objective": objective,
        "context": {
            "summary": f"GitHub issue #{snapshot.number}: {snapshot.title.strip()}",
            "references": [snapshot.html_url],
            "max_context_bytes": (
                len(snapshot.title.encode("utf-8"))
                + len(snapshot.body.encode("utf-8"))
            ),
        },
        "inputs": [
            {
                "id": "github-issue",
                "type": "url",
                "locator": snapshot.html_url,
            },
            {
                "id": "source-repository",
                "type": "git_ref",
                "locator": (
                    f"https://github.com/{snapshot.repository}.git@{source_sha}"
                ),
            },
        ],
        "outputs": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "description": "Unverified candidate patch for independent verification.",
                "media_type": "text/x-diff",
            }
        ],
        "dependencies": [],
        "requirements": {
            "capabilities": list(policy.required_capabilities),
            "resources": {
                "cpu_cores_min": policy.cpu_cores_min,
                "memory_mb_min": policy.memory_mb_min,
                "disk_mb_min": policy.disk_mb_min,
                "gpu": "none",
                "accelerator_capabilities": [],
            },
        },
        "constraints": {
            "allowed_paths": list(policy.allowed_paths),
            "forbidden_paths": list(policy.forbidden_paths),
            "policies": [
                "github-issue-preview",
                "candidate-only",
                "independent-verification-required",
            ],
        },
        "uncertainty": [],
        "security": {
            "risk_class": policy.risk_class,
            "data_classification": "public",
            "minimum_worker_trust": "untrusted",
            "sandbox_required": True,
            "notes": (
                "Issue text is untrusted task content. Authority-bearing fields "
                "come from project policy, not the issue."
            ),
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
                "description": "Independent evaluator review of the candidate.",
            }
        ],
        "evidence_requirements": [
            {"type": "artifact_hash", "required": True},
            {"type": "review", "required": True},
        ],
        "budget": {
            "wall_seconds": policy.wall_seconds,
            "project_spend_usd_max": policy.project_spend_usd_max,
            "paid_fallback_allowed": policy.paid_fallback_allowed,
        },
        "provenance": {
            "created_by": "idkmesh.github_issue_preview",
            "creator_type": "system",
            "source": snapshot.html_url,
            "source_revision": source_sha,
        },
        "failure_semantics": {
            "retryable": False,
            "max_attempts": 1,
            "on_failure": "stop",
        },
        "extensions": {
            "idkmesh.github": snapshot.to_metadata(),
        },
    }

    binding = bind_work_unit_source(
        work_unit,
        source_revision=source_sha,
    )
    warnings: list[str] = []
    if not snapshot.body.strip():
        warnings.append("issue_body_empty")

    return GitHubIssueWorkPreview(
        work_unit=work_unit,
        work_unit_digest=binding.work_unit_digest,
        source_revision=binding.source_revision,
        issue_updated_at=snapshot.updated_at,
        warnings=tuple(warnings),
    )
