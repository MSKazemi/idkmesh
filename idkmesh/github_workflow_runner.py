"""C8-E runner behind the generated ``idkmesh-*.yml`` GitHub workflow wrappers.

The four wrappers rendered by ``idkmesh init --github`` (C8-D) each run exactly
one command, ``python -m idkmesh.cli github-workflow <phase>``, and pass event
data only through ``IDKMESH_*`` environment variables. This module is the
implementation of that environment contract.

Authority is deliberately narrow:

* ``preview`` is read-only. It reads one issue (REST, or an offline JSON
  document), reads ``.idkmesh/project.json`` from the trusted checkout, and
  derives a WorkUnit preview with :mod:`idkmesh.github_issue_preview`. Authority
  fields come from project policy, never from the issue.
* ``status`` is read-only. It reads one run's durable ledger records (offline
  JSON, or the dedicated ledger branch through a transport that refuses every
  mutation), projects the latest record into the bounded status body, and
  appends that body to the job summary when GitHub provides one. It publishes
  no issue comment, because the comment path needs a retained idempotency store
  that a stateless Actions runner does not have.
* ``dispatch`` and ``verify`` fail closed before reading anything. The explicit
  dispatch boundary needs retained webhook-delivery state, actor authorization
  and a provider connector; verification needs an independent verifier. None of
  those can be backed by a stateless runner yet, so these phases refuse with
  ``dispatch_unavailable`` / ``verify_unavailable`` rather than succeeding
  vacuously.

Nothing here reads a provider secret, mutates GitHub, pushes, accepts a
candidate, or merges. The only credential read is the workflow's own
``IDKMESH_GITHUB_TOKEN``, used for the fixed GitHub API host and never echoed.
The module is stdlib-only because the generated wrappers install nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    GitHubIssueSnapshot,
    GitHubIssueWorkPolicy,
    parse_github_issue_snapshot,
    preview_github_issue_work_unit,
)
from idkmesh.github_issue_source import GitHubRestIssueSource
from idkmesh.github_ledger_github_store import (
    DEFAULT_LEDGER_BRANCH,
    GitHubLedgerBranchStore,
    GitHubLedgerRemoteError,
    GitHubRestGitDataTransport,
)
from idkmesh.github_ledger_serialization import (
    GitHubLedgerSerializationError,
    serialize_github_ledger_chain,
)
from idkmesh.github_status_comment import render_github_run_status_comment
from idkmesh.github_status_update import GitHubRunStatus


SCHEMA_VERSION = "0.1"
RESULT_KIND = "idkmesh-github-workflow-result"
PHASES = ("preview", "dispatch", "verify", "status")

# Stable error codes. They are part of the runner's documented contract.
ERROR_CODES = frozenset(
    {
        "invalid_environment",
        "project_policy_missing",
        "project_policy_invalid",
        "preview_scope_unconfigured",
        "event_issue_mismatch",
        "issue_unavailable",
        "preview_refused",
        "ledger_unavailable",
        "ledger_invalid",
        "ledger_run_not_found",
        "read_only_violation",
        "dispatch_unavailable",
        "verify_unavailable",
    }
)

PROJECT_POLICY_PATH = ".idkmesh/project.json"
PREVIEW_SCOPE_KEY = "github_issue_preview"
# Never a WorkUnit write target, whatever the project configures.
ALWAYS_FORBIDDEN_PATHS = (".github/**", ".idkmesh/**")

_MAX_JSON_BYTES = 1024 * 1024
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_ISSUE_RE = re.compile(r"[1-9][0-9]{0,9}\Z")
_ACTIONS_RUN_RE = re.compile(r"[0-9]{1,20}\Z")
_GIT_SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_RUN_REFERENCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_RISK_CLASSES = ("low", "medium", "high", "critical")


class GitHubWorkflowError(Exception):
    """A fail-closed runner refusal with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown runner error code: {code}")
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _env(environ: Mapping[str, str], name: str, *, required: bool = True) -> str | None:
    value = environ.get(name)
    if value is None or value == "":
        if required:
            raise GitHubWorkflowError(
                "invalid_environment", f"{name} is required"
            )
        return None
    if not isinstance(value, str) or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise GitHubWorkflowError(
            "invalid_environment", f"{name} contains control characters"
        )
    return value


def _matching(environ: Mapping[str, str], name: str, pattern: re.Pattern[str]) -> str:
    value = _env(environ, name)
    assert value is not None
    if pattern.fullmatch(value) is None:
        raise GitHubWorkflowError(
            "invalid_environment", f"{name} has an unsupported format"
        )
    return value


class _Common:
    """The four variables every wrapper phase passes."""

    def __init__(self, environ: Mapping[str, str]) -> None:
        root = _env(environ, "IDKMESH_PROJECT_ROOT")
        assert root is not None
        self.project_root = Path(root)
        self.repository = _matching(environ, "IDKMESH_REPOSITORY", _REPOSITORY_RE)
        self.base_sha = _matching(environ, "IDKMESH_BASE_SHA", _GIT_SHA_RE)
        self.actions_run_id = _matching(
            environ, "IDKMESH_RUN_ID", _ACTIONS_RUN_RE
        )


def _read_json_file(path: Path, *, what: str, code: str) -> Any:
    try:
        if path.is_symlink() or not path.is_file():
            raise GitHubWorkflowError(code, f"{what} is not a regular file")
        if path.stat().st_size > _MAX_JSON_BYTES:
            raise GitHubWorkflowError(code, f"{what} exceeds the size bound")
        return json.loads(path.read_text(encoding="utf-8"))
    except GitHubWorkflowError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubWorkflowError(code, f"{what} cannot be read as JSON") from exc


def _load_project_policy(root: Path) -> dict[str, Any]:
    """Read and sanity-check the trusted ``.idkmesh/project.json``.

    Structural checks only (the wrappers install no JSON-schema library); the
    full schema is enforced by ``scripts`` and tests. These checks are the ones
    this runner relies on for its own authority limits.
    """

    if not root.is_dir():
        raise GitHubWorkflowError(
            "invalid_environment", "IDKMESH_PROJECT_ROOT is not a directory"
        )
    path = root / PROJECT_POLICY_PATH
    if not path.exists():
        raise GitHubWorkflowError(
            "project_policy_missing", f"{PROJECT_POLICY_PATH} is missing"
        )
    manifest = _read_json_file(
        path, what=PROJECT_POLICY_PATH, code="project_policy_invalid"
    )
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "0.1":
        raise GitHubWorkflowError(
            "project_policy_invalid",
            f"{PROJECT_POLICY_PATH} must be a v0.1 ProjectManifest",
        )
    integration = manifest.get("integration_policy")
    if (
        not isinstance(integration, dict)
        or integration.get("automatic_merge_allowed") is not False
        or integration.get("human_decision_required") is not True
    ):
        raise GitHubWorkflowError(
            "project_policy_invalid",
            "the runner refuses projects that allow automatic merge or skip "
            "the human decision",
        )
    return manifest


def _preview_policy(manifest: Mapping[str, Any], repository: str) -> GitHubIssueWorkPolicy:
    kinds = manifest.get("allowed_work_unit_kinds")
    if not isinstance(kinds, list) or "coding" not in kinds:
        raise GitHubWorkflowError(
            "project_policy_invalid",
            "allowed_work_unit_kinds must include 'coding' to preview issues",
        )
    risk = manifest.get("risk_policy")
    ceiling = risk.get("maximum_autonomous_risk") if isinstance(risk, dict) else None
    if ceiling not in _RISK_CLASSES:
        raise GitHubWorkflowError(
            "project_policy_invalid",
            "risk_policy.maximum_autonomous_risk must be low, medium, high or "
            "critical to preview issues",
        )
    metadata = manifest.get("metadata")
    scope = metadata.get(PREVIEW_SCOPE_KEY) if isinstance(metadata, dict) else None
    if not isinstance(scope, dict) or not scope.get("allowed_paths"):
        raise GitHubWorkflowError(
            "preview_scope_unconfigured",
            f"set metadata.{PREVIEW_SCOPE_KEY}.allowed_paths in "
            f"{PROJECT_POLICY_PATH} to say where a previewed WorkUnit may write",
        )
    allowed = scope["allowed_paths"]
    forbidden = scope.get("forbidden_paths", [])
    if not all(isinstance(item, list) for item in (allowed, forbidden)):
        raise GitHubWorkflowError(
            "project_policy_invalid",
            f"metadata.{PREVIEW_SCOPE_KEY} paths must be lists of strings",
        )
    worker = manifest.get("worker_constraints")
    required_caps = worker.get("required_capabilities", []) if isinstance(worker, dict) else []
    if not isinstance(required_caps, list) or not all(
        isinstance(item, str) for item in required_caps
    ):
        raise GitHubWorkflowError(
            "project_policy_invalid",
            "worker_constraints.required_capabilities must be a list of strings",
        )
    try:
        return GitHubIssueWorkPolicy(
            repository=repository,
            allowed_paths=tuple(allowed),
            forbidden_paths=tuple(
                dict.fromkeys([*forbidden, *ALWAYS_FORBIDDEN_PATHS])
            ),
            required_capabilities=tuple(
                dict.fromkeys(["git", "coding-agent", *required_caps])
            ),
            risk_class=ceiling,
        )
    except ValueError as exc:
        raise GitHubWorkflowError("project_policy_invalid", str(exc)) from exc


def _check_event(path_value: str | None, issue_number: int) -> None:
    """Cross-check the event's issue number; its text is never read."""

    if path_value is None:
        return
    event = _read_json_file(
        Path(path_value), what="IDKMESH_EVENT_PATH", code="invalid_environment"
    )
    issue = event.get("issue") if isinstance(event, dict) else None
    if isinstance(issue, dict) and issue.get("number") != issue_number:
        raise GitHubWorkflowError(
            "event_issue_mismatch",
            "the triggering event concerns a different issue than "
            "IDKMESH_ISSUE_NUMBER",
        )


def _write_summary(environ: Mapping[str, str], text: str) -> bool:
    """Append to the Actions job summary when GitHub provides one."""

    path = _env(environ, "GITHUB_STEP_SUMMARY", required=False)
    if path is None:
        return False
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except OSError as exc:
        raise GitHubWorkflowError(
            "invalid_environment", "GITHUB_STEP_SUMMARY is not writable"
        ) from exc
    return True


def _preview_summary(issue_number: int, preview: Mapping[str, Any]) -> str:
    # Only identifiers, digests and project-configured paths: issue text is
    # untrusted and stays out of the summary.
    work_unit = preview["work_unit"]
    constraints = work_unit["constraints"]
    lines = [
        "### IDKMesh WorkUnit preview",
        "",
        f"- Issue: #{issue_number}",
        f"- WorkUnit: `{work_unit['id']}`",
        f"- WorkUnit digest: `{preview['work_unit_digest']}`",
        f"- Source revision: `{preview['source_revision']}`",
        f"- Allowed paths: {', '.join(f'`{p}`' for p in constraints['allowed_paths'])}",
        f"- Forbidden paths: {', '.join(f'`{p}`' for p in constraints['forbidden_paths'])}",
    ]
    lines.extend(f"- Warning: `{item}`" for item in preview["warnings"])
    lines.extend(
        [
            "",
            "Preview only: nothing was dispatched. Pass the digest above to the "
            "IDKMesh Dispatch workflow to request a candidate.",
        ]
    )
    return "\n".join(lines)


def _result(phase: str, common: _Common, **fields: Any) -> dict[str, Any]:
    return {
        "kind": RESULT_KIND,
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "repository": common.repository,
        "actions_run_id": common.actions_run_id,
        "base_sha": common.base_sha,
        **fields,
        "dispatch_performed": False,
        "github_mutation_performed": False,
        "secret_values_accessed": False,
    }


def run_preview(
    environ: Mapping[str, str],
    *,
    issue_json: Path | None = None,
    issue_source: Any = None,
) -> dict[str, Any]:
    """Derive a WorkUnit preview for one issue; perform no dispatch."""

    common = _Common(environ)
    issue_number = int(_matching(environ, "IDKMESH_ISSUE_NUMBER", _ISSUE_RE))
    _check_event(_env(environ, "IDKMESH_EVENT_PATH", required=False), issue_number)
    policy = _preview_policy(_load_project_policy(common.project_root), common.repository)

    try:
        if issue_json is not None:
            raw = _read_json_file(
                issue_json, what="the issue JSON document", code="invalid_environment"
            )
            snapshot: GitHubIssueSnapshot = parse_github_issue_snapshot(
                raw, repository=common.repository, expected_number=issue_number
            )
        else:
            source = issue_source
            if source is None:
                source = GitHubRestIssueSource(
                    token=_env(environ, "IDKMESH_GITHUB_TOKEN", required=False)
                )
            snapshot = source.get_issue_snapshot(
                repository=common.repository, issue_number=issue_number
            )
    except ConnectorError as exc:
        raise GitHubWorkflowError(
            "issue_unavailable", f"{exc.code}: {exc.message}"
        ) from exc
    except ValueError as exc:
        raise GitHubWorkflowError("invalid_environment", str(exc)) from exc

    try:
        preview = preview_github_issue_work_unit(
            snapshot, source_revision=common.base_sha, policy=policy
        )
    except ConnectorError as exc:
        raise GitHubWorkflowError(
            "preview_refused", f"{exc.code}: {exc.message}"
        ) from exc
    document = preview.to_dict()
    return _result(
        "preview",
        common,
        issue_number=issue_number,
        preview=document,
        summary_written=_write_summary(
            environ, _preview_summary(issue_number, document)
        ),
    )


class _ReadOnlyGitData:
    """Git-data transport that can read but never create or move anything."""

    _READS = frozenset(
        {"get_branch_head", "get_commit_tree", "get_tree", "get_blob"}
    )

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        if name not in self._READS:
            raise GitHubWorkflowError(
                "read_only_violation",
                f"status is read-only; refused Git-data call {name!r}",
            )
        return getattr(self._inner, name)


def _ledger_records(
    environ: Mapping[str, str],
    common: _Common,
    manifest: Mapping[str, Any],
    run_reference: str,
    *,
    ledger_records: Path | None,
    transport: Any,
) -> tuple[dict[str, Any], ...]:
    if ledger_records is not None:
        raw = _read_json_file(
            ledger_records, what="the ledger records document", code="invalid_environment"
        )
        if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
            raise GitHubWorkflowError(
                "ledger_invalid", "ledger records must be a JSON array of objects"
            )
        return tuple(item for item in raw if item.get("run_id") == run_reference)

    if transport is None:
        token = _env(environ, "IDKMESH_GITHUB_TOKEN", required=False)
        if token is None:
            raise GitHubWorkflowError(
                "invalid_environment",
                "IDKMESH_GITHUB_TOKEN is required to read the ledger branch",
            )
        try:
            transport = GitHubRestGitDataTransport(token=token)
        except ValueError as exc:
            raise GitHubWorkflowError("invalid_environment", str(exc)) from exc
    guarded = _ReadOnlyGitData(transport)
    integration = manifest.get("integration_policy", {})
    branch = integration.get("target_branch") if isinstance(integration, dict) else None
    try:
        # Observe first: GitHubLedgerBranchStore initializes a missing ledger
        # branch, which is a write status must never perform.
        if guarded.get_branch_head(
            repository=common.repository, branch=DEFAULT_LEDGER_BRANCH
        ) is None:
            raise GitHubWorkflowError(
                "ledger_unavailable",
                f"the {DEFAULT_LEDGER_BRANCH} branch does not exist yet",
            )
        store = GitHubLedgerBranchStore(
            repository=common.repository,
            transport=guarded,
            default_branch=branch if isinstance(branch, str) else "main",
        )
        return store.read_run_records(run_reference)
    except GitHubLedgerSerializationError as exc:
        raise GitHubWorkflowError("ledger_invalid", str(exc)) from exc
    except GitHubLedgerRemoteError as exc:
        raise GitHubWorkflowError("ledger_unavailable", str(exc)) from exc
    except ValueError as exc:
        raise GitHubWorkflowError("ledger_unavailable", str(exc)) from exc


def run_status(
    environ: Mapping[str, str],
    *,
    ledger_records: Path | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Project one run's latest ledger record into the bounded status body."""

    common = _Common(environ)
    issue_number = int(_matching(environ, "IDKMESH_ISSUE_NUMBER", _ISSUE_RE))
    run_reference = _matching(environ, "IDKMESH_RUN_REFERENCE", _RUN_REFERENCE_RE)
    manifest = _load_project_policy(common.project_root)
    records = _ledger_records(
        environ,
        common,
        manifest,
        run_reference,
        ledger_records=ledger_records,
        transport=transport,
    )
    if not records:
        raise GitHubWorkflowError(
            "ledger_run_not_found", f"no ledger records for run {run_reference!r}"
        )
    try:
        chain = serialize_github_ledger_chain(records)
        latest = records[-1]
        if latest["repository"].casefold() != common.repository.casefold():
            raise GitHubWorkflowError(
                "ledger_invalid", "the ledger run belongs to a different repository"
            )
        status = GitHubRunStatus(
            repository=common.repository,
            issue_number=issue_number,
            run_id=run_reference,
            state=latest["event"]["state"],
            work_unit_id=latest["work_unit"]["id"],
            work_unit_digest=latest["work_unit"]["digest"],
            routing_digest=latest["routing"]["routing_digest"],
        )
    except GitHubLedgerSerializationError as exc:
        raise GitHubWorkflowError("ledger_invalid", str(exc)) from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise GitHubWorkflowError(
            "ledger_invalid", "the latest ledger record cannot be projected"
        ) from exc

    body = render_github_run_status_comment(status)
    summary_written = _write_summary(environ, body)
    return _result(
        "status",
        common,
        issue_number=issue_number,
        run_reference=run_reference,
        state=status.state,
        ledger_records=len(chain),
        status_digest=status.status_digest,
        body=body,
        summary_written=summary_written,
        comment_published=False,
    )


def run_unavailable(phase: str) -> dict[str, Any]:
    """Refuse an execution-authority phase no existing primitive can back."""

    if phase == "dispatch":
        raise GitHubWorkflowError(
            "dispatch_unavailable",
            "stateless explicit dispatch is not implemented: it needs retained "
            "delivery state, actor authorization and a provider connector",
        )
    if phase == "verify":
        raise GitHubWorkflowError(
            "verify_unavailable",
            "stateless independent verification is not implemented",
        )
    raise ValueError(f"not an execution-authority phase: {phase}")
