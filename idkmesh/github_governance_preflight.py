"""Read-only GitHub governance preflight for C12 / issue 607.

Consumes normalized trusted observations plus the canonical C12-A policy.
It never mutates GitHub administration, reads secret values, or grants merge,
verification, acceptance, or dispatch authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from idkmesh.github_governance_policy import (
    CONDITIONS,
    build_github_governance_policy,
)

OBSERVATION_VERSION = "0.1"
REPORT_VERSION = "0.1"
MAX_OBSERVATION_BYTES = 256 * 1024
MAX_WORKFLOW_BYTES = 512 * 1024


class GitHubGovernancePreflightError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


SECTIONS: dict[str, frozenset[str]] = {
    "repository_rules": frozenset({
        "pull_request_integration", "force_push_blocked",
        "branch_deletion_blocked", "narrow_bypass_actors",
        "required_checks_enforced", "risk_review_required",
        "codeowner_review_required", "stable_ci_checks_present",
    }),
    "environment_settings": frozenset({"approval_required", "prevent_self_review"}),
    "codeowners": frozenset({"configured", "sensitive_paths_covered"}),
    "connector_configuration": frozenset({"uses_oidc"}),
    "workflow_source": frozenset({
        "actions_default_contents_read", "checkout_persist_credentials_disabled",
        "immutable_security_actions", "untrusted_pr_secret_isolation",
        "environment_bound", "oidc_token_permission",
    }),
}
ALLOWED_TOP = frozenset({"schema_version", "conditions", "unknown_reasons", *SECTIONS})

GUARD_INPUTS: dict[str, tuple[tuple[str, str], ...]] = {
    "actions-default-contents-read": (("workflow_source", "actions_default_contents_read"),),
    "branch-deletion-blocked": (("repository_rules", "branch_deletion_blocked"),),
    "checkout-persist-credentials-disabled": (("workflow_source", "checkout_persist_credentials_disabled"),),
    "codeowner-review-enforced": (
        ("codeowners", "configured"), ("codeowners", "sensitive_paths_covered"),
        ("repository_rules", "codeowner_review_required"),
    ),
    "force-push-blocked": (("repository_rules", "force_push_blocked"),),
    "high-risk-environment-approval": (
        ("workflow_source", "environment_bound"),
        ("environment_settings", "approval_required"),
    ),
    "immutable-security-actions": (("workflow_source", "immutable_security_actions"),),
    "narrow-bypass-actors": (("repository_rules", "narrow_bypass_actors"),),
    "pull-request-integration": (("repository_rules", "pull_request_integration"),),
    "required-checks-enforced": (("repository_rules", "required_checks_enforced"),),
    "risk-review-required": (("repository_rules", "risk_review_required"),),
    "untrusted-pr-secret-isolation": (("workflow_source", "untrusted_pr_secret_isolation"),),
    "environment-self-review-prevented": (("environment_settings", "prevent_self_review"),),
    "sensitive-path-codeowners": (
        ("codeowners", "configured"), ("codeowners", "sensitive_paths_covered"),
    ),
    "stable-ci-checks-present": (("repository_rules", "stable_ci_checks_present"),),
    "oidc-short-lived-cloud-auth": (
        ("connector_configuration", "uses_oidc"),
        ("workflow_source", "oidc_token_permission"),
    ),
}

CODEOWNERS_PATTERNS = (
    ".github/workflows/**", ".idkmesh/**", "idkmesh/*security*.py",
    "idkmesh/*governance*.py", "idkmesh/*evaluator*.py", "schemas/**",
    "docs/security/**", "pyproject.toml",
)
OWNER_RE = re.compile(r"@[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_.-]+)?\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses\s*:\s*['\"]?([^'\"#\s]+)", re.MULTILINE)
CHECKOUT_RE = re.compile(
    r"^\s*-\s*uses\s*:\s*['\"]?actions/checkout@[^'\"#\s]+['\"]?[^\n]*",
    re.MULTILINE,
)
SECRET_EXPR_RE = re.compile(r"\$\{\{[^}]*\bsecrets\b", re.IGNORECASE)
CLOUD_SECRET_RE = re.compile(
    r"\$\{\{[^}]*\bsecrets\s*(?:\.\s*|\[\s*['\"])"
    r"(?:AWS_SECRET_ACCESS_KEY|AZURE_CLIENT_SECRET|"
    r"GOOGLE_APPLICATION_CREDENTIALS|GCP_SERVICE_ACCOUNT_KEY)",
    re.IGNORECASE,
)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise GitHubGovernancePreflightError("duplicate_json_key", f"duplicate key {key!r}")
        out[key] = value
    return out


def parse_observation_text(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise GitHubGovernancePreflightError(
            "invalid_observation_text", "observation must be UTF-8 JSON text"
        )
    if len(text.encode("utf-8")) > MAX_OBSERVATION_BYTES:
        raise GitHubGovernancePreflightError("observation_too_large", "observation exceeds size limit")
    try:
        payload = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda x: (_ for _ in ()).throw(GitHubGovernancePreflightError("invalid_json_constant", x)))
    except GitHubGovernancePreflightError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise GitHubGovernancePreflightError("invalid_observation_json", "observation must be valid JSON") from exc
    return validate_observation(payload)


def load_observation_file(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise GitHubGovernancePreflightError("observation_too_large", "observation exceeds size limit")
    try:
        return parse_observation_text(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise GitHubGovernancePreflightError("observation_not_utf8", "observation must be UTF-8") from exc


def _bool_map(name: str, value: object, allowed: frozenset[str]) -> dict[str, bool | None]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise GitHubGovernancePreflightError("invalid_observation_section", f"{name} must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise GitHubGovernancePreflightError("unknown_observation_field", f"{name}: {', '.join(unknown)}")
    out: dict[str, bool | None] = {}
    for key, item in value.items():
        if item is not None and not isinstance(item, bool):
            raise GitHubGovernancePreflightError("invalid_observation_value", f"{name}.{key} must be true, false, or null")
        out[key] = item
    return out


def validate_observation(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GitHubGovernancePreflightError("invalid_observation", "root must be an object")
    unknown = sorted(set(payload) - ALLOWED_TOP)
    if unknown:
        raise GitHubGovernancePreflightError("unknown_observation_field", ", ".join(unknown))
    if payload.get("schema_version") != OBSERVATION_VERSION:
        raise GitHubGovernancePreflightError("unsupported_observation_version", f"expected {OBSERVATION_VERSION}")
    out: dict[str, Any] = {"schema_version": OBSERVATION_VERSION}
    for name, allowed in SECTIONS.items():
        out[name] = _bool_map(name, payload.get(name), allowed)
    out["conditions"] = _bool_map("conditions", payload.get("conditions"), CONDITIONS)
    reasons = payload.get("unknown_reasons", {})
    if not isinstance(reasons, dict) or any(not isinstance(v, str) or not v.strip() for v in reasons.values()):
        raise GitHubGovernancePreflightError("invalid_unknown_reasons", "unknown_reasons must map guard codes to text")
    codes = {guard.code for guard in build_github_governance_policy().guards}
    extra = sorted(set(reasons) - codes)
    if extra:
        raise GitHubGovernancePreflightError("unknown_guard_code", ", ".join(extra))
    out["unknown_reasons"] = dict(sorted(reasons.items()))
    return out


def evaluate_governance(operation: str, observation: Mapping[str, Any]) -> dict[str, Any]:
    doc = validate_observation(dict(observation))
    policy = build_github_governance_policy()
    rows: list[dict[str, Any]] = []
    for guard in policy.guards_for(operation):
        values = [doc["conditions"].get(c) for c in guard.conditions]
        if any(v is False for v in values):
            status, observed, reason = "NOT_APPLICABLE", None, "condition not active"
        elif any(v is None for v in values):
            missing = [c for c, v in zip(guard.conditions, values) if v is None]
            status = "UNKNOWN" if guard.requirement == "required" else "WARN"
            observed = None
            reason = "condition not observed: " + ", ".join(missing)
        else:
            paths = GUARD_INPUTS.get(guard.code)
            if paths is None:
                raise GitHubGovernancePreflightError("unmapped_policy_guard", guard.code)
            observed_values = [doc[s].get(k) for s, k in paths]
            observed = False if any(v is False for v in observed_values) else True if all(v is True for v in observed_values) else None
            if observed is True:
                status, reason = "PASS", "observed guard is satisfied"
            elif observed is False:
                status = "FAIL" if guard.requirement == "required" else "WARN"
                reason = "observed guard is not satisfied"
            else:
                status = "UNKNOWN" if guard.requirement == "required" else "WARN"
                default_reason = (
                    "required observation is unavailable"
                    if guard.requirement == "required"
                    else f"{guard.requirement} observation is unavailable"
                )
                reason = doc["unknown_reasons"].get(guard.code, default_reason)
        rows.append({
            "code": guard.code, "requirement": guard.requirement, "status": status,
            "observed": observed, "summary": guard.summary, "availability": guard.availability,
            "conditions": list(guard.conditions), "reason": reason,
        })
    statuses = {row["status"] for row in rows}
    blocking = any(
        row["requirement"] == "required"
        and row["status"] in {"FAIL", "UNKNOWN"}
        for row in rows
    )
    overall = "FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return {
        "kind": "idkmesh-github-governance-preflight", "schema_version": REPORT_VERSION,
        "policy_version": policy.version, "profile": policy.profile, "operation": operation,
        "status": overall, "operation_allowed": not blocking,
        "automatic_admin_mutation": False, "ruleset_proves_independent_review": False,
        "guards": rows,
    }


def require_governance(operation: str, observation: Mapping[str, Any]) -> dict[str, Any]:
    report = evaluate_governance(operation, observation)
    if not report["operation_allowed"]:
        raise GitHubGovernancePreflightError("governance_preflight_blocked", f"{operation} blocked by {report['status']}")
    return report


def _permission_blocks(
    text: str,
) -> list[tuple[int, dict[str, str] | str]]:
    lines = text.splitlines()
    blocks: list[tuple[int, dict[str, str] | str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^( *)permissions\s*:\s*([^#]*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1))
        scalar = match.group(2).strip().strip("'\"")
        if scalar:
            blocks.append((indent, scalar))
            continue
        values: dict[str, str] = {}
        for later in lines[index + 1 :]:
            if not later.strip() or later.lstrip().startswith("#"):
                continue
            later_indent = len(later) - len(later.lstrip(" "))
            if later_indent <= indent:
                break
            item = re.match(
                r"^\s*([A-Za-z0-9_-]+)\s*:\s*([^#]+?)\s*$", later
            )
            if item:
                values[item.group(1)] = item.group(2).strip().strip("'\"")
        blocks.append((indent, values))
    return blocks


def _permissions(text: str) -> tuple[bool, bool]:
    blocks = _permission_blocks(text)
    broad_scalar = any(
        indent in {0, 4}
        and isinstance(value, str)
        and value in {"read-all", "write-all"}
        for indent, value in blocks
    )
    contents_read = (
        any(
            indent == 0
            and isinstance(value, dict)
            and value.get("contents") == "read"
            for indent, value in blocks
        )
        and not broad_scalar
    )
    id_token = any(
        indent in {0, 4}
        and isinstance(value, dict)
        and value.get("id-token") == "write"
        for indent, value in blocks
    )
    return contents_read, id_token


def _has_pr_trigger(text: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(
            r"^( *)['\"]?on['\"]?\s*:\s*([^#]*?)\s*$", line
        )
        if not match:
            continue
        indent = len(match.group(1))
        scalar = match.group(2).strip().strip("'\"")
        if scalar and re.search(r"\bpull_request(?:_target)?\b", scalar):
            return True
        if scalar:
            continue
        for later in lines[index + 1 :]:
            if not later.strip() or later.lstrip().startswith("#"):
                continue
            later_indent = len(later) - len(later.lstrip(" "))
            if later_indent <= indent:
                break
            if re.match(r"^\s*pull_request(?:_target)?\s*:", later):
                return True
        return False
    return False


def _has_job_environment(text: str) -> bool:
    lines = text.splitlines()
    jobs_index = None
    jobs_indent = None
    for index, line in enumerate(lines):
        match = re.match(r"^( *)jobs\s*:\s*(?:#.*)?$", line)
        if match:
            jobs_index = index
            jobs_indent = len(match.group(1))
            break
    if jobs_index is None or jobs_indent is None:
        return False

    job_indent: int | None = None
    index = jobs_index + 1
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= jobs_indent:
            break
        if job_indent is None:
            job_indent = indent
        if indent != job_indent:
            index += 1
            continue
        if not re.match(r"^\s*[A-Za-z0-9_-]+\s*:\s*(?:#.*)?$", line):
            index += 1
            continue

        end = index + 1
        direct_indent: int | None = None
        while end < len(lines):
            later = lines[end]
            if not later.strip() or later.lstrip().startswith("#"):
                end += 1
                continue
            later_indent = len(later) - len(later.lstrip(" "))
            if later_indent <= job_indent:
                break
            if direct_indent is None or later_indent < direct_indent:
                direct_indent = later_indent
            end += 1

        if direct_indent is not None:
            for later in lines[index + 1 : end]:
                if not later.strip() or later.lstrip().startswith("#"):
                    continue
                later_indent = len(later) - len(later.lstrip(" "))
                if later_indent == direct_indent and re.match(
                    r"^\s*environment\s*:", later
                ):
                    return True
        index = end
    return False


def _immutable(ref: str) -> bool:
    if ref.startswith("./"):
        return True
    if ref.startswith("docker://"):
        return re.fullmatch(
            r"docker://[^@\s]+@sha256:[0-9a-fA-F]{64}", ref
        ) is not None
    return "@" in ref and SHA_RE.fullmatch(ref.rsplit("@", 1)[1]) is not None


def lint_workflow_text(text: str, *, label: str = "workflow") -> dict[str, Any]:
    if not isinstance(text, str):
        raise GitHubGovernancePreflightError(
            "invalid_workflow_source", f"{label}: workflow source must be UTF-8 text"
        )
    if not text.strip() or len(text.encode("utf-8")) > MAX_WORKFLOW_BYTES or "\t" in text:
        raise GitHubGovernancePreflightError("invalid_workflow_source", f"{label}: invalid or oversized workflow source")
    findings: list[dict[str, Any]] = []
    contents_read, id_token = _permissions(text)
    if not contents_read:
        findings.append({"code": "actions-default-contents-read", "message": "permissions must default contents to read and avoid read-all/write-all grants"})
    refs = [match.group(1) for match in USES_RE.finditer(text)]
    immutable = all(_immutable(ref) for ref in refs)
    for ref in refs:
        if not _immutable(ref):
            findings.append({"code": "immutable-security-actions", "message": f"not pinned to immutable revision: {ref}"})
    checkout_safe = True
    for match in CHECKOUT_RE.finditer(text):
        rest = text[match.end():]
        next_step = re.search(r"(?m)^\s*-\s+", rest)
        block = rest[: next_step.start()] if next_step else rest
        if not re.search(r"(?m)^\s*persist-credentials:\s*false\s*(?:#.*)?$", block):
            checkout_safe = False
            findings.append({"code": "checkout-persist-credentials-disabled", "message": "checkout must set persist-credentials: false"})
    pr = _has_pr_trigger(text)
    secrets = bool(SECRET_EXPR_RE.search(text)) or bool(
        re.search(
            r"(?m)^\s*secrets:\s*['\"]?inherit['\"]?\s*(?:#.*)?$",
            text,
        )
    )
    privileged_head = "pull_request_target" in text and (
        "github.event.pull_request.head" in text or "github.head_ref" in text
    )
    isolated = not (pr and (secrets or privileged_head))
    if not isolated:
        findings.append({"code": "untrusted-pr-secret-isolation", "message": "PR-triggered untrusted code cannot share secret-bearing or privileged head execution"})
    environment_bound = _has_job_environment(text)
    return {
        "label": label,
        "workflow_source": {
            "actions_default_contents_read": contents_read,
            "checkout_persist_credentials_disabled": checkout_safe,
            "immutable_security_actions": immutable,
            "untrusted_pr_secret_isolation": isolated,
            "environment_bound": environment_bound,
            "oidc_token_permission": id_token,
        },
        "findings": findings,
    }


def lint_workflow_file(path: str | Path) -> dict[str, Any]:
    return lint_workflow_text(Path(path).read_text(encoding="utf-8"), label=str(path))


def merge_workflow_lints(observation: Mapping[str, Any], reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    doc = validate_observation(dict(observation))
    if not reports:
        return doc
    for field in SECTIONS["workflow_source"]:
        values = [report.get("workflow_source", {}).get(field) for report in reports]
        if not all(isinstance(v, bool) for v in values):
            raise GitHubGovernancePreflightError("invalid_workflow_lint_report", field)
        doc["workflow_source"][field] = all(values)
    return doc


def render_codeowners_recommendation(owner: str) -> str:
    if OWNER_RE.fullmatch(owner or "") is None:
        raise GitHubGovernancePreflightError("invalid_codeowner", "owner must be explicit @user or @org/team")
    return "\n".join(["# IDKMesh C12 sensitive-path recommendation.", *[f"{path} {owner}" for path in CODEOWNERS_PATTERNS]]) + "\n"


def oidc_preflight(text: str) -> dict[str, Any]:
    report = lint_workflow_text(text, label="oidc-workflow")
    long_lived = bool(CLOUD_SECRET_RE.search(text))
    token = report["workflow_source"]["oidc_token_permission"]
    return {
        "status": "PASS" if token and not long_lived else "FAIL",
        "oidc_token_permission": token,
        "long_lived_cloud_secret_reference": long_lived,
        "note": "shape check only; no cloud authentication is attempted",
    }
