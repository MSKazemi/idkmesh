"""Read-only C13 GitHub Issue Form normalization and policy-bounded WorkUnit preview.

Form text is untrusted. Malformed form-looking issues fail closed; ordinary
(non-form) issues retain the existing generic preview. This module does not
fetch issues, execute commands, select providers, dispatch, verify, or merge.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    GitHubIssueSnapshot,
    GitHubIssueWorkPolicy,
    GitHubIssueWorkPreview,
    preview_github_issue_work_unit,
)
from idkmesh.work_unit_binding import bind_work_unit_source


# Match labels/ordering from config/github-workunit-intake-v0.1.json. The
# contract test guards this copy for installed-package/offline use.
FORM_FIELDS = (
    ("objective", "Objective"),
    ("task_class", "Task class"),
    ("expected_outputs", "Expected outputs"),
    ("requested_allowed_paths", "Requested allowed paths"),
    ("requested_forbidden_paths", "Forbidden or sensitive paths"),
    ("dependencies", "Dependencies or blockers"),
    ("acceptance_checks", "Acceptance checks"),
    ("risk_hint", "Risk hint"),
    ("data_sensitivity_hint", "Data sensitivity hint"),
    ("external_processing_hint", "External processing hint"),
    ("human_review_hint", "Human review or decision requirement"),
    ("preferred_connector_hint", "Preferred connector"),
    ("safety_acknowledgement", "Safety acknowledgement"),
)
ACKNOWLEDGEMENT = (
    "I understand this issue is an untrusted proposal and cannot grant "
    "execution, secret, dispatch, verification, human-decision, or merge authority."
)
HEADINGS = re.compile(r"(?m)^### ([^\r\n]+)\r?\n")
LIST_BULLET = re.compile(r"^[-*] +")
DEPENDENCY = re.compile(r"^(requires|blocked_by|informs):\s*(\S.*)$")
PATH_COMPONENT = re.compile(r"[A-Za-z0-9_.@+*?\[\]{}-]+\Z")
ENUMS = {
    "task_class": (
        "coding", "testing", "review", "benchmarking", "documentation",
        "research", "integration", "governance", "other",
    ),
    "risk_hint": ("low", "medium", "high", "critical", "unspecified"),
    "data_sensitivity_hint": (
        "public", "internal", "confidential", "restricted", "unspecified",
    ),
    "external_processing_hint": ("forbidden", "allowed", "unspecified"),
    "human_review_hint": ("required", "preferred", "unspecified"),
}
AUTHORITY_CEILING = {
    key: False for key in (
        "policy_authority", "secret_authority", "command_authority",
        "network_authority", "filesystem_authority",
        "connector_selection_authority", "dispatch_authority",
        "verification_authority", "integration_authority",
    )
}


class IntakeFormatError(ValueError):
    """A public, bounded reason code; never includes submitted issue text."""


def _lines(value: str, *, limit: int, max_length: int, required: bool) -> list[str]:
    if value.strip() == "_No response_":
        value = ""
    items = []
    for line in value.splitlines():
        item = LIST_BULLET.sub("", line.strip()).strip()
        if item:
            items.append(item)
    if len(items) > limit or (required and not items):
        raise IntakeFormatError("invalid_list_size")
    if len(set(items)) != len(items) or any(len(x) > max_length for x in items):
        raise IntakeFormatError("invalid_list_item")
    return items


def _safe_path(path: str) -> None:
    if (
        len(path) > 512 or not path or path.startswith("/")
        or path.endswith("/") or "\\" in path or "//" in path
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
        or any(part in ("", ".", "..") or not PATH_COMPONENT.fullmatch(part)
               for part in path.split("/"))
    ):
        raise IntakeFormatError("unsafe_path_hint")


def parse_github_workunit_form(body: str) -> dict[str, Any] | None:
    """Normalize the exact GitHub-generated form layout; None means not a form.

    GitHub renders `### Label` headings and `_No response_` for empty optional
    fields. Even a genuine-looking form has no authorization value. Unknown,
    reordered, missing or duplicate headings fail closed rather than guessing.
    """
    if not isinstance(body, str):
        raise TypeError("body must be a string")
    headings = list(HEADINGS.finditer(body))
    labels = [label for _, label in FORM_FIELDS]
    if not any(match.group(1) in labels for match in headings):
        return None
    if len(body) > 16_384:
        raise IntakeFormatError("form_body_too_long")
    if body[:headings[0].start()].strip():
        raise IntakeFormatError("unexpected_form_preamble")
    if [match.group(1) for match in headings] != labels:
        raise IntakeFormatError("invalid_form_sections")
    fields = {
        field_id: body[headings[i].end(): (
            headings[i + 1].start() if i + 1 < len(headings) else len(body)
        )].strip()
        for i, (field_id, _) in enumerate(FORM_FIELDS)
    }
    if fields["safety_acknowledgement"] != f"- [X] {ACKNOWLEDGEMENT}" and (
        fields["safety_acknowledgement"] != f"- [x] {ACKNOWLEDGEMENT}"
    ):
        raise IntakeFormatError("missing_safety_acknowledgement")

    objective = fields["objective"]
    if not objective or objective == "_No response_" or len(objective) > 12_000:
        raise IntakeFormatError("invalid_objective")
    for field, enum in ENUMS.items():
        if fields[field] not in enum:
            raise IntakeFormatError("invalid_" + field)

    expected = _lines(fields["expected_outputs"], limit=32, max_length=500, required=True)
    allowed = _lines(fields["requested_allowed_paths"], limit=64, max_length=512, required=True)
    forbidden = _lines(fields["requested_forbidden_paths"], limit=64, max_length=512, required=False)
    checks = _lines(fields["acceptance_checks"], limit=32, max_length=1000, required=True)
    for path in (*allowed, *forbidden):
        _safe_path(path)

    dependencies = []
    for item in _lines(fields["dependencies"], limit=32, max_length=512, required=False):
        match = DEPENDENCY.fullmatch(item)
        if match is None or len(match.group(2)) > 512:
            raise IntakeFormatError("invalid_dependency_relation")
        dependencies.append({"relation": match.group(1), "reference": match.group(2)})

    preferred = fields["preferred_connector_hint"]
    if preferred == "_No response_":
        preferred = ""
    if len(preferred) > 128 or "\n" in preferred or "\r" in preferred:
        raise IntakeFormatError("invalid_preferred_connector")

    return {
        "schema_version": "0.1",
        "kind": "idkmesh-github-workunit-intake",
        "objective": objective,
        "task_class": fields["task_class"],
        "expected_outputs": expected,
        "requested_allowed_paths": allowed,
        "requested_forbidden_paths": forbidden,
        "dependencies": dependencies,
        "acceptance_checks": checks,
        "risk_hint": fields["risk_hint"],
        "data_sensitivity_hint": fields["data_sensitivity_hint"],
        "external_processing_hint": fields["external_processing_hint"],
        "human_review_hint": fields["human_review_hint"],
        "preferred_connector_hint": preferred or None,
        "authority_ceiling": dict(AUTHORITY_CEILING),
    }


def _narrow_scope(requested: list[str], trusted: tuple[str, ...]) -> list[str]:
    """Conservative subset check, not generic glob intersection or union.

    Supports literal trusted scopes and directory/** trusted scopes. More
    complex trusted glob grammars are not inferred from requester-controlled
    patterns; matching them requires an exact match or a future proven policy.
    """
    scoped = []
    for hint in requested:
        if hint in trusted:
            scoped.append(hint)
            continue
        is_directory_glob = hint.endswith("/**") and hint.count("*") == 2
        is_literal = not any(c in hint for c in "*?[]{}")
        if not (is_literal or is_directory_glob):
            raise IntakeFormatError("unprovable_allowed_scope")
        if not any(
            policy_path.endswith("/**")
            and hint.startswith(policy_path[:-2])
            and len(hint) > len(policy_path[:-2])
            for policy_path in trusted
        ):
            raise IntakeFormatError("requested_scope_outside_policy")
        scoped.append(hint)
    return scoped


def preview_github_workunit_form(
    snapshot: GitHubIssueSnapshot, *, source_revision: str,
    policy: GitHubIssueWorkPolicy,
) -> GitHubIssueWorkPreview:
    """Return a non-dispatching canonical preview; malformed forms are denied.

    For non-form issues, preserve the existing generic preview byte-for-byte.
    For a complete form, only narrowing/restrictive changes are permitted.
    The proposed connector, dependency, and checks stay untrusted metadata.
    """
    baseline = preview_github_issue_work_unit(
        snapshot, source_revision=source_revision, policy=policy
    )
    try:
        intake = parse_github_workunit_form(snapshot.body)
        if intake is None:
            if snapshot.title.lstrip().casefold().startswith("[workunit]") and HEADINGS.search(snapshot.body):
                raise IntakeFormatError("unrecognized_form_sections")
            return baseline
        scoped = _narrow_scope(intake["requested_allowed_paths"], policy.allowed_paths)
    except IntakeFormatError as exc:
        raise ConnectorError(
            code="policy_denied",
            message="Malformed or unprovable WorkUnit Issue Form requires human correction.",
            details={"reason": str(exc)},
        ) from exc

    work = deepcopy(baseline.work_unit)
    work["constraints"]["allowed_paths"] = scoped
    work["permissions"]["filesystem_write"] = list(scoped)
    work["constraints"]["forbidden_paths"] = list(dict.fromkeys(
        [*policy.forbidden_paths, *intake["requested_forbidden_paths"]]
    ))
    risk = ("low", "medium", "high", "critical")
    if intake["risk_hint"] != "unspecified":
        work["security"]["risk_class"] = max(
            (policy.risk_class, intake["risk_hint"]), key=risk.index
        )
    sensitivity = ("public", "internal", "confidential", "restricted")
    if intake["data_sensitivity_hint"] != "unspecified":
        work["security"]["data_classification"] = max(
            (work["security"]["data_classification"], intake["data_sensitivity_hint"]),
            key=sensitivity.index,
        )
    if intake["external_processing_hint"] == "forbidden":
        work["permissions"]["network"] = "none"
        work["permissions"].pop("network_allowlist", None)
    # This extension never becomes a policy/validator/command/connector choice.
    work["extensions"]["idkmesh.github_workunit_form_v0_1"] = intake
    binding = bind_work_unit_source(work, source_revision=baseline.source_revision)
    warnings = [*baseline.warnings, "untrusted_structured_form"]
    if intake["task_class"] != policy.kind:
        warnings.append("task_class_did_not_override_policy")
    if intake["preferred_connector_hint"]:
        warnings.append("preferred_connector_not_selected")
    if intake["external_processing_hint"] == "forbidden":
        warnings.append("external_processing_requires_downstream_policy_enforcement")
    return GitHubIssueWorkPreview(
        work_unit=work,
        work_unit_digest=binding.work_unit_digest,
        source_revision=binding.source_revision,
        issue_updated_at=baseline.issue_updated_at,
        warnings=tuple(warnings),
    )
