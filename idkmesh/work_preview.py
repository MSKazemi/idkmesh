"""C7-C: the offline ``idkmesh work preview`` command.

One local, read-only way to see the WorkUnit a GitHub issue would become,
without editing Python. It is a thin composition of existing seams and owns no
policy of its own:

* the issue is an offline GitHub REST issue object (``--issue-json``),
  normalized by :func:`parse_github_issue_snapshot`;
* authority fields come from the trusted ``.idkmesh/project.json`` through
  :func:`idkmesh.github_workflow_runner.load_preview_policy`, the same
  derivation the generated ``preview`` workflow uses;
* the WorkUnit comes from :func:`preview_github_issue_work_unit`, by default
  with the C13 Issue Form composition (``use_intake_form=True``), which can
  only narrow the policy-owned WorkUnit.

Nothing here reads the network, a credential, or an environment variable,
dispatches, persists, or writes any file. Issue text is untrusted task content
and is never printed by the human-readable renderer.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
import stat
from typing import Any

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    parse_github_issue_snapshot,
    preview_github_issue_work_unit,
)
from idkmesh.github_workflow_runner import GitHubWorkflowError, load_preview_policy


SCHEMA_VERSION = "0.1"
RESULT_KIND = "idkmesh-work-preview"

# Stable error codes. They are part of the command's documented contract.
ERROR_CODES = frozenset(
    {
        "invalid_argument",
        "issue_unreadable",
        "issue_invalid",
        "project_policy_missing",
        "project_policy_invalid",
        "preview_scope_unconfigured",
        "policy_denied",
    }
)

_MAX_ISSUE_BYTES = 1024 * 1024
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_GIT_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


class WorkPreviewError(Exception):
    """A fail-closed refusal with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown work preview error code: {code}")
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _strict_issue_document(path: Path) -> object:
    """Read one bounded, strict (no duplicate keys, no NaN) JSON file."""

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise WorkPreviewError(
                "issue_unreadable", f"issue snapshot is not a regular file: {path}"
            )
        with path.open("rb") as handle:
            payload = handle.read(_MAX_ISSUE_BYTES + 1)
    except FileNotFoundError as exc:
        raise WorkPreviewError(
            "issue_unreadable", f"issue snapshot not found: {path}"
        ) from exc
    except OSError as exc:
        raise WorkPreviewError(
            "issue_unreadable",
            f"cannot read issue snapshot {path}: {exc.strerror or type(exc).__name__}",
        ) from exc
    if len(payload) > _MAX_ISSUE_BYTES:
        raise WorkPreviewError(
            "issue_unreadable", "issue snapshot exceeds the 1 MiB local input limit"
        )
    try:
        return json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=no_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise WorkPreviewError(
            "issue_invalid", f"{path}: invalid strict JSON: {exc}"
        ) from exc


def run_work_preview(
    *,
    issue_json: Path,
    project_root: Path,
    repository: str,
    source_revision: str,
    issue_number: int | None = None,
    use_intake_form: bool = True,
) -> dict[str, Any]:
    """Derive one WorkUnit preview from local files; perform no dispatch."""

    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise WorkPreviewError("invalid_argument", "--repository must be OWNER/NAME")
    if (
        not isinstance(source_revision, str)
        or _GIT_SHA_RE.fullmatch(source_revision) is None
    ):
        raise WorkPreviewError(
            "invalid_argument",
            "--source-revision must be an exact 40- or 64-character hexadecimal "
            "Git object id",
        )
    if not project_root.is_dir():
        raise WorkPreviewError(
            "invalid_argument", f"--project-root is not a directory: {project_root}"
        )

    try:
        policy = load_preview_policy(project_root, repository)
    except GitHubWorkflowError as exc:
        # Codes are shared with the workflow runner by construction.
        code = exc.code if exc.code in ERROR_CODES else "project_policy_invalid"
        raise WorkPreviewError(code, exc.message) from exc

    raw = _strict_issue_document(issue_json)
    if issue_number is None:
        candidate = raw.get("number") if isinstance(raw, Mapping) else None
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 1:
            raise WorkPreviewError(
                "issue_invalid", "issue snapshot must carry an integer number >= 1"
            )
        issue_number = candidate

    try:
        snapshot = parse_github_issue_snapshot(
            raw, repository=repository, expected_number=issue_number
        )
        preview = preview_github_issue_work_unit(
            snapshot,
            source_revision=source_revision,
            policy=policy,
            use_intake_form=use_intake_form,
        )
    except ConnectorError as exc:
        code = "policy_denied" if exc.code == "policy_denied" else "issue_invalid"
        raise WorkPreviewError(code, exc.message) from exc
    except ValueError as exc:
        raise WorkPreviewError("invalid_argument", str(exc)) from exc

    return {
        "kind": RESULT_KIND,
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "issue_number": issue_number,
        "intake_form_enabled": use_intake_form,
        "preview": preview.to_dict(),
        "dispatch_performed": False,
        "github_mutation_performed": False,
        "secret_values_accessed": False,
    }


def render_work_preview_text(result: Mapping[str, Any]) -> str:
    """Human summary: identifiers, digests and configured paths only.

    Issue title and body are untrusted and never appear here. Strings that can
    originate from an Issue Form request (paths) are JSON-quoted so a control
    character cannot reach the terminal.
    """

    preview = result["preview"]
    work_unit = preview["work_unit"]
    constraints = work_unit["constraints"]

    def quoted(items: list[str]) -> str:
        return ", ".join(json.dumps(item) for item in items) or "none"

    lines = [
        "IDKMesh work preview: ok",
        f"repository: {result['repository']}",
        f"issue: #{result['issue_number']}",
        f"work unit: {work_unit['id']}",
        f"work unit digest: {preview['work_unit_digest']}",
        f"source revision: {preview['source_revision']}",
        f"kind: {work_unit['kind']}",
        f"risk class: {work_unit['security']['risk_class']}",
        f"allowed paths: {quoted(constraints['allowed_paths'])}",
        f"forbidden paths: {quoted(constraints['forbidden_paths'])}",
    ]
    intake = preview.get("intake")
    if intake is not None:
        lines.append(f"intake form: {intake['status']}")
    elif not result["intake_form_enabled"]:
        lines.append("intake form: disabled")
    for warning in preview["warnings"]:
        lines.append(f"warning: {warning}")
    lines.extend(
        [
            "dispatch performed: no",
            "GitHub mutations: no",
            "secret values accessed: no",
        ]
    )
    return "\n".join(lines)
