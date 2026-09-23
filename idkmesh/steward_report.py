"""Offline reader for Auto Draft PR Steward evidence.

The producer lives in the repository automation layer; this module is the
installable, read-only consumer. It intentionally uses only the Python standard
library so a report can be inspected on a clean `pip install idkmesh` without
GitHub credentials, network access, or the optional verification dependency.
"""

from __future__ import annotations

import json
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_ID = "auto-draft-pr-steward-report-v0.1"
MAX_REPORT_BYTES = 2 * 1024 * 1024
STATUSES = {"completed", "blocked", "disabled"}
SKIP_REASONS = {"head_moved", "pr_already_exists"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")

EXPECTED_AUTHORITY = {
    "draft_pr_create": True,
    "ready_for_review": False,
    "approve": False,
    "merge": False,
    "auto_merge": False,
    "delete_branch": False,
    "close_issue": False,
    "label_write": False,
    "contents_write": False,
    "repository_settings": False,
}

TOP_KEYS = {
    "schema",
    "repository",
    "generated_at",
    "status",
    "dry_run",
    "policy",
    "provenance",
    "authority",
    "candidate_count",
    "rate_limit_remaining",
    "blocked_reason",
    "summary",
    "planned",
    "created",
    "skipped",
}
CANDIDATE_KEYS = {"branch", "base", "head_sha", "ahead_by", "behind_by"}
CREATED_KEYS = CANDIDATE_KEYS | {"number", "url"}
SKIPPED_BASE_KEYS = CANDIDATE_KEYS | {"reason"}


class StewardReportInputError(ValueError):
    """The steward report cannot be interpreted safely as the v0.1 contract."""


_JSON_TYPE_NAMES = {
    dict: "an object",
    list: "an array",
    str: "a string",
    bool: "a boolean",
    int: "a number",
    float: "a number",
    type(None): "null",
}


def _type_name(value: Any) -> str:
    if isinstance(value, str) and not value:
        return "an empty string"
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StewardReportInputError(
            f"{where} must be a JSON object, got {_type_name(value)}"
        )
    return value


def _array(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise StewardReportInputError(
            f"{where} must be a JSON array, got {_type_name(value)}"
        )
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        raise StewardReportInputError(
            f"{where} is missing required keys: {', '.join(missing)}"
        )
    if extra:
        raise StewardReportInputError(
            f"{where} has unsupported keys for {SCHEMA_ID}: {', '.join(extra)}"
        )


def _string(value: Any, where: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        kind = "a non-empty string" if nonempty else "a string"
        raise StewardReportInputError(
            f"{where} must be {kind}, got {_type_name(value)}"
        )
    return value


def _nullable_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    return _string(value, where)


def _nonnegative_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StewardReportInputError(
            f"{where} must be a non-negative integer, got {value!r}"
        )
    return value


def _positive_int(value: Any, where: str) -> int:
    result = _nonnegative_int(value, where)
    if result < 1:
        raise StewardReportInputError(f"{where} must be at least 1")
    return result


def _nullable_nonnegative_int(value: Any, where: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, where)


def _sha(value: Any, where: str) -> str:
    text = _string(value, where)
    if not SHA40.fullmatch(text):
        raise StewardReportInputError(
            f"{where} must be a lowercase 40-hex Git commit SHA"
        )
    return text


def _timestamp(value: Any) -> str:
    text = _string(value, "'generated_at'")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise StewardReportInputError(
            f"'generated_at' is not an ISO-8601 timestamp: {text!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise StewardReportInputError(
            "'generated_at' must include a timezone offset or Z"
        )
    return text


def _candidate(value: Any, where: str) -> dict[str, Any]:
    item = _object(value, where)
    _exact_keys(item, CANDIDATE_KEYS, where)
    _string(item["branch"], f"{where}.branch")
    _string(item["base"], f"{where}.base")
    _sha(item["head_sha"], f"{where}.head_sha")
    _nonnegative_int(item["ahead_by"], f"{where}.ahead_by")
    _nonnegative_int(item["behind_by"], f"{where}.behind_by")
    return item


def _candidate_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return item["branch"], item["base"], item["head_sha"]


def _created(value: Any, where: str, repository: str) -> dict[str, Any]:
    item = _object(value, where)
    _exact_keys(item, CREATED_KEYS, where)
    core = {key: item[key] for key in CANDIDATE_KEYS}
    _candidate(core, where)
    number = _positive_int(item["number"], f"{where}.number")
    url = _string(item["url"], f"{where}.url")
    expected = f"https://github.com/{repository}/pull/{number}"
    if url != expected:
        raise StewardReportInputError(
            f"{where}.url must be the canonical PR URL {expected!r}, got {url!r}"
        )
    return item


def _skipped(value: Any, where: str) -> dict[str, Any]:
    item = _object(value, where)
    reason = item.get("reason")
    allowed = set(SKIPPED_BASE_KEYS)
    if reason == "head_moved":
        allowed.add("current_head_sha")
    _exact_keys(item, allowed, where)
    core = {key: item[key] for key in CANDIDATE_KEYS}
    _candidate(core, where)
    if reason not in SKIP_REASONS:
        raise StewardReportInputError(
            f"{where}.reason must be one of {sorted(SKIP_REASONS)}, got {reason!r}"
        )
    if reason == "head_moved":
        _sha(item["current_head_sha"], f"{where}.current_head_sha")
    return item


def validate_report(data: Any) -> dict[str, Any]:
    report = _object(data, "report")
    _exact_keys(report, TOP_KEYS, "report")

    if report["schema"] != SCHEMA_ID:
        raise StewardReportInputError(
            f"'schema' must be {SCHEMA_ID!r}, got {report['schema']!r}"
        )

    repository = _string(report["repository"], "'repository'")
    if not REPOSITORY.fullmatch(repository):
        raise StewardReportInputError(
            "'repository' must use non-empty owner/name form"
        )

    _timestamp(report["generated_at"])
    status = report["status"]
    if status not in STATUSES:
        raise StewardReportInputError(
            f"'status' must be one of {sorted(STATUSES)}, got {status!r}"
        )
    if not isinstance(report["dry_run"], bool):
        raise StewardReportInputError(
            f"'dry_run' must be a boolean, got {_type_name(report['dry_run'])}"
        )

    policy = _object(report["policy"], "'policy'")
    _exact_keys(policy, {"path", "sha256"}, "'policy'")
    _string(policy["path"], "'policy.path'")
    digest = _string(policy["sha256"], "'policy.sha256'")
    if not SHA256.fullmatch(digest):
        raise StewardReportInputError(
            "'policy.sha256' must be a lowercase 64-hex SHA-256 digest"
        )

    provenance = _object(report["provenance"], "'provenance'")
    _exact_keys(
        provenance,
        {"workflow", "run_id", "run_attempt", "trusted_head_sha"},
        "'provenance'",
    )
    for key in ("workflow", "run_id", "run_attempt"):
        _nullable_string(provenance[key], f"'provenance.{key}'")
    if provenance["trusted_head_sha"] is not None:
        _sha(provenance["trusted_head_sha"], "'provenance.trusted_head_sha'")

    authority = _object(report["authority"], "'authority'")
    _exact_keys(authority, set(EXPECTED_AUTHORITY), "'authority'")
    changed = [
        key
        for key, expected in EXPECTED_AUTHORITY.items()
        if authority.get(key) is not expected
    ]
    if changed:
        raise StewardReportInputError(
            "authority block does not match the read-only integration boundary; "
            f"unexpected capability values: {', '.join(changed)}"
        )

    candidate_count = _nullable_nonnegative_int(
        report["candidate_count"], "'candidate_count'"
    )
    _nullable_nonnegative_int(
        report["rate_limit_remaining"], "'rate_limit_remaining'"
    )
    blocked_reason = report["blocked_reason"]
    if blocked_reason is not None:
        _string(blocked_reason, "'blocked_reason'")

    planned_raw = _array(report["planned"], "'planned'")
    created_raw = _array(report["created"], "'created'")
    skipped_raw = _array(report["skipped"], "'skipped'")

    planned = [
        _candidate(item, f"planned[{index}]")
        for index, item in enumerate(planned_raw)
    ]
    created = [
        _created(item, f"created[{index}]", repository)
        for index, item in enumerate(created_raw)
    ]
    skipped = [
        _skipped(item, f"skipped[{index}]")
        for index, item in enumerate(skipped_raw)
    ]

    summary = _object(report["summary"], "'summary'")
    _exact_keys(summary, {"planned", "created", "skipped"}, "'summary'")
    expected_counts = {
        "planned": len(planned),
        "created": len(created),
        "skipped": len(skipped),
    }
    for key, expected in expected_counts.items():
        actual = _nonnegative_int(summary[key], f"'summary.{key}'")
        if actual != expected:
            raise StewardReportInputError(
                f"'summary.{key}' says {actual}, but the report contains {expected}"
            )

    planned_ids = [_candidate_identity(item) for item in planned]
    if len(set(planned_ids)) != len(planned_ids):
        raise StewardReportInputError("'planned' contains duplicate candidate identities")

    outcome_ids = [
        _candidate_identity(item) for item in created
    ] + [
        _candidate_identity(item) for item in skipped
    ]
    if len(set(outcome_ids)) != len(outcome_ids):
        raise StewardReportInputError(
            "a planned candidate appears in more than one created/skipped outcome"
        )
    missing_outcomes = sorted(set(outcome_ids) - set(planned_ids))
    if missing_outcomes:
        raise StewardReportInputError(
            "created/skipped outcome does not correspond to a planned candidate: "
            f"{missing_outcomes[0]!r}"
        )

    pr_numbers = [item["number"] for item in created]
    if len(set(pr_numbers)) != len(pr_numbers):
        raise StewardReportInputError("'created' contains duplicate PR numbers")

    if candidate_count is not None and len(planned) > candidate_count:
        raise StewardReportInputError(
            f"'planned' has {len(planned)} items but candidate_count is {candidate_count}"
        )

    if status == "completed":
        if blocked_reason is not None:
            raise StewardReportInputError(
                "completed report must have blocked_reason null"
            )
        if candidate_count is None:
            raise StewardReportInputError(
                "completed report must have an integer candidate_count"
            )
    elif status == "disabled":
        if blocked_reason != "policy_disabled":
            raise StewardReportInputError(
                "disabled report must use blocked_reason 'policy_disabled'"
            )
        if candidate_count is not None:
            raise StewardReportInputError(
                "disabled report must have candidate_count null"
            )
        if planned or created or skipped:
            raise StewardReportInputError(
                "disabled report cannot contain planned/created/skipped work"
            )
    else:
        if not blocked_reason or blocked_reason == "policy_disabled":
            raise StewardReportInputError(
                "blocked report must have a non-policy_disabled blocked_reason"
            )
        if candidate_count is not None:
            raise StewardReportInputError(
                "blocked report must have candidate_count null in v0.1"
            )
        if planned or created or skipped:
            raise StewardReportInputError(
                "blocked report cannot contain planned/created/skipped work in v0.1"
            )

    return report


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StewardReportInputError(
                f"duplicate JSON key {key!r} in one object; the report has no "
                "single portable meaning"
            )
        result[key] = value
    return result


def _reject_json_constant(token: str) -> Any:
    raise StewardReportInputError(
        f"report uses {token}, which is a Python extension and not valid JSON"
    )


def parse_report_text(text: str, *, source: str = "input") -> dict[str, Any]:
    text = text.removeprefix("\ufeff")
    try:
        data = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise StewardReportInputError(
            f"{source}: not valid JSON ({exc})"
        ) from exc
    except StewardReportInputError as exc:
        raise StewardReportInputError(f"{source}: {exc}") from exc
    try:
        return validate_report(data)
    except StewardReportInputError as exc:
        raise StewardReportInputError(f"{source}: {exc}") from exc


def load_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    file_stat = source.stat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise StewardReportInputError(
            f"{source}: steward report input must be a regular file"
        )
    if file_stat.st_size > MAX_REPORT_BYTES:
        raise StewardReportInputError(
            f"{source}: steward report exceeds the {MAX_REPORT_BYTES}-byte "
            "offline-reader limit"
        )

    with source.open("rb") as handle:
        payload = handle.read(MAX_REPORT_BYTES + 1)
    if len(payload) > MAX_REPORT_BYTES:
        raise StewardReportInputError(
            f"{source}: steward report exceeds the {MAX_REPORT_BYTES}-byte "
            "offline-reader limit"
        )
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StewardReportInputError(
            f"{source}: not UTF-8 text ({exc.reason} at byte {exc.start})"
        ) from exc
    return parse_report_text(text, source=str(source))


def _quoted(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render_summary(report: dict[str, Any], *, details: bool = False) -> str:
    validate_report(report)
    summary = report["summary"]
    authority = report["authority"]
    lines = [
        "IDKMesh Auto Draft PR Steward",
        f"Repository: {report['repository']}",
        f"Status: {report['status']}",
        f"Generated: {report['generated_at']}",
        f"Candidates: {report['candidate_count']}",
        f"Planned: {summary['planned']}",
        f"Created Draft PRs: {summary['created']}",
        f"Skipped: {summary['skipped']}",
        f"API remaining at start: {report['rate_limit_remaining']}",
        f"Blocked reason: {report['blocked_reason'] or 'none'}",
        (
            "Authority: draft-pr-create="
            f"{str(authority['draft_pr_create']).lower()}, "
            "merge=false, approve=false, auto-merge=false, "
            "branch-delete=false, contents-write=false"
        ),
    ]

    if details:
        if report["planned"]:
            lines.extend(["", "Planned candidates:"])
            for item in report["planned"]:
                lines.append(
                    "  - "
                    f"{_quoted(item['branch'])} -> {_quoted(item['base'])} "
                    f"(ahead={item['ahead_by']}, behind={item['behind_by']}, "
                    f"head={item['head_sha']})"
                )
        if report["created"]:
            lines.extend(["", "Created Draft PRs:"])
            for item in report["created"]:
                lines.append(
                    f"  - #{item['number']} {_quoted(item['branch'])}: {item['url']}"
                )
        if report["skipped"]:
            lines.extend(["", "Skipped candidates:"])
            for item in report["skipped"]:
                suffix = (
                    f", current_head={item['current_head_sha']}"
                    if "current_head_sha" in item
                    else ""
                )
                lines.append(
                    f"  - {_quoted(item['branch'])}: {item['reason']}"
                    f" (planned_head={item['head_sha']}{suffix})"
                )

    return "\n".join(lines) + "\n"
