"""Offline aggregation for Auto Draft PR Steward report history.

The history layer is a bounded, deterministic evidence consumer. It never
contacts GitHub. Every source report is validated with the single-run contract,
assigned a semantic SHA-256 over canonical JSON, and aggregated into a
self-validating history document.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from idkmesh.steward_report import (
    REPOSITORY,
    SCHEMA_ID as REPORT_SCHEMA,
    StewardReportInputError,
    load_report,
    validate_report,
)

HISTORY_SCHEMA = "auto-draft-pr-steward-history-v0.1"
REPORT_FILENAME = "steward-report.json"

MAX_HISTORY_INPUTS = 128
MAX_HISTORY_REPORTS = 1000
MAX_DISCOVERY_DEPTH = 8
MAX_VISITED_DIRECTORIES = 10000

SEMANTIC_DIGEST_ALGORITHM = "sha256"
SEMANTIC_NORMALIZATION = "validated-canonical-json-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_STATUSES = {"completed", "blocked", "disabled"}

_TOP_KEYS = {
    "schema",
    "repository",
    "report_count",
    "first_generated_at",
    "last_generated_at",
    "status_counts",
    "outcome_totals",
    "api_budget",
    "policy",
    "integrity",
    "runs",
}
_RUN_KEYS = {
    "source",
    "generated_at",
    "status",
    "candidate_count",
    "planned",
    "created",
    "skipped",
    "head_moved",
    "pr_already_exists",
    "rate_limit_remaining",
    "blocked_reason",
    "policy_sha256",
    "report_sha256",
    "run_id",
    "run_attempt",
    "trusted_head_sha",
}


class StewardHistoryInputError(ValueError):
    """The selected reports cannot form one unambiguous history."""


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise StewardHistoryInputError("history timestamps must be non-empty strings")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise StewardHistoryInputError(
            f"history timestamp is not ISO-8601: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise StewardHistoryInputError(
            f"history timestamp must include a timezone: {value!r}"
        )
    return parsed


def _exact_keys(value: Any, expected: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StewardHistoryInputError(f"{where} must be an object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        raise StewardHistoryInputError(
            f"{where} is missing required keys: {', '.join(missing)}"
        )
    if extra:
        raise StewardHistoryInputError(
            f"{where} has unsupported keys for {HISTORY_SCHEMA}: "
            f"{', '.join(extra)}"
        )
    return value


def _nonnegative_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StewardHistoryInputError(
            f"{where} must be a non-negative integer"
        )
    return value


def _nullable_nonnegative_int(value: Any, where: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, where)


def _nullable_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise StewardHistoryInputError(
            f"{where} must be null or a non-empty string"
        )
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise StewardHistoryInputError(
            "history evidence must be strict JSON before hashing"
        ) from exc
    return rendered.encode("utf-8")


def semantic_report_sha256(report: dict[str, Any]) -> str:
    """Digest the validated semantic report, independent of source formatting."""
    try:
        validate_report(report)
    except StewardReportInputError as exc:
        raise StewardHistoryInputError(str(exc)) from exc
    return hashlib.sha256(_canonical_json_bytes(report)).hexdigest()


def _semantic_run_projection(run: dict[str, Any]) -> dict[str, Any]:
    """Return the path-independent run projection bound by history integrity."""
    return {key: run[key] for key in sorted(_RUN_KEYS - {"source"})}


def _semantic_run_order(run: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _parse_time(run["generated_at"]),
        run["run_id"] or "",
        run["run_attempt"] or "",
        run["report_sha256"],
        run["source"],
    )


def _input_set_sha256(repository: str, runs: list[dict[str, Any]]) -> str:
    projections = [_semantic_run_projection(run) for run in runs]
    projections.sort(
        key=lambda run: (
            _parse_time(run["generated_at"]),
            run["run_id"] or "",
            run["run_attempt"] or "",
            run["report_sha256"],
        )
    )
    manifest = {
        "schema": HISTORY_SCHEMA,
        "report_schema": REPORT_SCHEMA,
        "repository": repository,
        "reports": projections,
    }
    return hashlib.sha256(_canonical_json_bytes(manifest)).hexdigest()


def _add_discovered(
    discovered: dict[Path, Path],
    path: Path,
) -> None:
    resolved = path.resolve()
    discovered.setdefault(resolved, path)
    if len(discovered) > MAX_HISTORY_REPORTS:
        raise StewardHistoryInputError(
            "history discovery exceeded the bounded report limit "
            f"({MAX_HISTORY_REPORTS})"
        )


def discover_report_files(inputs: Iterable[str | Path]) -> list[Path]:
    """Resolve files/directories into a bounded, deterministic file list.

    Explicit files may use any filename. Directory discovery is conservative:
    only files named steward-report.json are considered, traversal does not
    follow directory symlinks, and depth/directory/report counts are bounded.
    """
    selected = list(inputs)
    if not selected:
        raise StewardHistoryInputError("at least one history input is required")
    if len(selected) > MAX_HISTORY_INPUTS:
        raise StewardHistoryInputError(
            "history input count exceeds the bounded limit "
            f"({MAX_HISTORY_INPUTS})"
        )

    discovered: dict[Path, Path] = {}
    visited_directories = 0

    for raw in selected:
        path = Path(raw)
        if path.is_file():
            _add_discovered(discovered, path)
            continue

        if path.is_dir():
            root = path
            for current, dirnames, filenames in os.walk(
                root,
                topdown=True,
                followlinks=False,
            ):
                visited_directories += 1
                if visited_directories > MAX_VISITED_DIRECTORIES:
                    raise StewardHistoryInputError(
                        "history discovery exceeded the bounded directory limit "
                        f"({MAX_VISITED_DIRECTORIES})"
                    )

                current_path = Path(current)
                try:
                    depth = len(current_path.relative_to(root).parts)
                except ValueError as exc:  # pragma: no cover - os.walk invariant
                    raise StewardHistoryInputError(
                        f"history discovery escaped selected root: {root}"
                    ) from exc

                dirnames.sort()
                filenames.sort()
                if depth >= MAX_DISCOVERY_DEPTH:
                    dirnames[:] = []

                if REPORT_FILENAME in filenames:
                    child = current_path / REPORT_FILENAME
                    if child.is_file():
                        _add_discovered(discovered, child)
            continue

        raise StewardHistoryInputError(f"input path does not exist: {path}")

    if not discovered:
        raise StewardHistoryInputError(
            f"no {REPORT_FILENAME} files were found in the selected inputs"
        )
    return [discovered[key] for key in sorted(discovered, key=lambda p: str(p))]


def _run_identity(report: dict[str, Any]) -> tuple[str, str] | None:
    provenance = report["provenance"]
    run_id = provenance["run_id"]
    run_attempt = provenance["run_attempt"]
    if run_id is None or run_attempt is None:
        return None
    return str(run_id), str(run_attempt)


def build_history(
    reports: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    if not reports:
        raise StewardHistoryInputError("at least one steward report is required")
    if len(reports) > MAX_HISTORY_REPORTS:
        raise StewardHistoryInputError(
            f"history report count exceeds the bounded limit ({MAX_HISTORY_REPORTS})"
        )

    validated: list[tuple[Path, dict[str, Any], str]] = []
    for path, report in reports:
        try:
            validate_report(report)
        except StewardReportInputError as exc:
            raise StewardHistoryInputError(f"{path}: {exc}") from exc
        validated.append((path, report, semantic_report_sha256(report)))

    repositories = {report["repository"] for _, report, _ in validated}
    if len(repositories) != 1:
        raise StewardHistoryInputError(
            "all reports in one history must belong to the same repository; "
            f"found: {', '.join(sorted(repositories))}"
        )
    repository = next(iter(repositories))

    seen_runs: dict[tuple[str, str], Path] = {}
    ordered: list[tuple[Path, dict[str, Any], str]] = []
    for path, report, report_digest in validated:
        identity = _run_identity(report)
        if identity is not None:
            previous = seen_runs.get(identity)
            if previous is not None:
                raise StewardHistoryInputError(
                    "duplicate GitHub workflow run identity "
                    f"{identity[0]}/{identity[1]} in {previous} and {path}"
                )
            seen_runs[identity] = path
        ordered.append((path, report, report_digest))

    ordered.sort(
        key=lambda item: (
            _parse_time(item[1]["generated_at"]),
            item[1]["provenance"]["run_id"] or "",
            item[1]["provenance"]["run_attempt"] or "",
            item[2],
            item[0].as_posix(),
        )
    )

    status_counts = {"completed": 0, "blocked": 0, "disabled": 0}
    totals = {
        "planned": 0,
        "created": 0,
        "skipped": 0,
        "head_moved": 0,
        "pr_already_exists": 0,
    }
    api_values: list[int] = []
    policy_digests: set[str] = set()
    policy_changes = 0
    previous_policy: str | None = None
    runs: list[dict[str, Any]] = []

    for path, report, report_digest in ordered:
        status = report["status"]
        status_counts[status] += 1

        summary = report["summary"]
        totals["planned"] += summary["planned"]
        totals["created"] += summary["created"]
        totals["skipped"] += summary["skipped"]

        head_moved = sum(
            1 for item in report["skipped"] if item["reason"] == "head_moved"
        )
        already_exists = sum(
            1
            for item in report["skipped"]
            if item["reason"] == "pr_already_exists"
        )
        totals["head_moved"] += head_moved
        totals["pr_already_exists"] += already_exists

        remaining = report["rate_limit_remaining"]
        if remaining is not None:
            api_values.append(remaining)

        digest = report["policy"]["sha256"]
        policy_digests.add(digest)
        if previous_policy is not None and digest != previous_policy:
            policy_changes += 1
        previous_policy = digest

        provenance = report["provenance"]
        runs.append(
            {
                "source": path.as_posix(),
                "generated_at": report["generated_at"],
                "status": status,
                "candidate_count": report["candidate_count"],
                "planned": summary["planned"],
                "created": summary["created"],
                "skipped": summary["skipped"],
                "head_moved": head_moved,
                "pr_already_exists": already_exists,
                "rate_limit_remaining": remaining,
                "blocked_reason": report["blocked_reason"],
                "policy_sha256": digest,
                "report_sha256": report_digest,
                "run_id": provenance["run_id"],
                "run_attempt": provenance["run_attempt"],
                "trusted_head_sha": provenance["trusted_head_sha"],
            }
        )

    first = runs[0]
    last = runs[-1]
    history = {
        "schema": HISTORY_SCHEMA,
        "repository": repository,
        "report_count": len(runs),
        "first_generated_at": first["generated_at"],
        "last_generated_at": last["generated_at"],
        "status_counts": status_counts,
        "outcome_totals": totals,
        "api_budget": {
            "observed_runs": len(api_values),
            "min_remaining": min(api_values) if api_values else None,
            "max_remaining": max(api_values) if api_values else None,
        },
        "policy": {
            "distinct_digests": len(policy_digests),
            "changes": policy_changes,
            "latest_sha256": last["policy_sha256"],
        },
        "integrity": {
            "algorithm": SEMANTIC_DIGEST_ALGORITHM,
            "semantic_normalization": SEMANTIC_NORMALIZATION,
            "input_set_sha256": _input_set_sha256(repository, runs),
        },
        "runs": runs,
    }
    return validate_history(history)


def validate_history(data: Any) -> dict[str, Any]:
    history = _exact_keys(data, _TOP_KEYS, "history")
    if history["schema"] != HISTORY_SCHEMA:
        raise StewardHistoryInputError(
            f"history schema must be {HISTORY_SCHEMA!r}"
        )

    repository = history["repository"]
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise StewardHistoryInputError(
            "history repository must use non-empty owner/name form"
        )

    runs = history["runs"]
    if not isinstance(runs, list) or not runs:
        raise StewardHistoryInputError("history runs must be a non-empty array")

    report_count = _nonnegative_int(history["report_count"], "history.report_count")
    if report_count < 1 or report_count != len(runs):
        raise StewardHistoryInputError(
            "history.report_count must equal the number of run records"
        )

    expected_status = {"completed": 0, "blocked": 0, "disabled": 0}
    expected_outcomes = {
        "planned": 0,
        "created": 0,
        "skipped": 0,
        "head_moved": 0,
        "pr_already_exists": 0,
    }
    api_values: list[int] = []
    policy_values: list[str] = []
    seen_identities: set[tuple[str, str]] = set()
    previous_order: tuple[Any, ...] | None = None

    for index, raw_run in enumerate(runs):
        run = _exact_keys(raw_run, _RUN_KEYS, f"history.runs[{index}]")
        source = run["source"]
        if not isinstance(source, str) or not source:
            raise StewardHistoryInputError(
                f"history.runs[{index}].source must be a non-empty string"
            )

        generated = run["generated_at"]
        _parse_time(generated)

        status = run["status"]
        if status not in _STATUSES:
            raise StewardHistoryInputError(
                f"history.runs[{index}].status is unsupported"
            )
        expected_status[status] += 1

        candidate_count = _nullable_nonnegative_int(
            run["candidate_count"],
            f"history.runs[{index}].candidate_count",
        )
        planned = _nonnegative_int(run["planned"], f"history.runs[{index}].planned")
        created = _nonnegative_int(run["created"], f"history.runs[{index}].created")
        skipped = _nonnegative_int(run["skipped"], f"history.runs[{index}].skipped")
        head_moved = _nonnegative_int(
            run["head_moved"],
            f"history.runs[{index}].head_moved",
        )
        already_exists = _nonnegative_int(
            run["pr_already_exists"],
            f"history.runs[{index}].pr_already_exists",
        )
        if head_moved + already_exists != skipped:
            raise StewardHistoryInputError(
                f"history.runs[{index}] skip-reason counts must equal skipped"
            )
        if created + skipped > planned:
            raise StewardHistoryInputError(
                f"history.runs[{index}] created + skipped exceeds planned"
            )
        if candidate_count is not None and planned > candidate_count:
            raise StewardHistoryInputError(
                f"history.runs[{index}].planned exceeds candidate_count"
            )

        expected_outcomes["planned"] += planned
        expected_outcomes["created"] += created
        expected_outcomes["skipped"] += skipped
        expected_outcomes["head_moved"] += head_moved
        expected_outcomes["pr_already_exists"] += already_exists

        remaining = _nullable_nonnegative_int(
            run["rate_limit_remaining"],
            f"history.runs[{index}].rate_limit_remaining",
        )
        if remaining is not None:
            api_values.append(remaining)

        blocked_reason = _nullable_string(
            run["blocked_reason"],
            f"history.runs[{index}].blocked_reason",
        )
        if status == "completed":
            if blocked_reason is not None or candidate_count is None:
                raise StewardHistoryInputError(
                    f"history.runs[{index}] completed state is inconsistent"
                )
        elif status == "disabled":
            if (
                blocked_reason != "policy_disabled"
                or candidate_count is not None
                or planned
                or created
                or skipped
            ):
                raise StewardHistoryInputError(
                    f"history.runs[{index}] disabled state is inconsistent"
                )
        else:
            if (
                not blocked_reason
                or blocked_reason == "policy_disabled"
                or candidate_count is not None
                or planned
                or created
                or skipped
            ):
                raise StewardHistoryInputError(
                    f"history.runs[{index}] blocked state is inconsistent"
                )

        policy_sha = run["policy_sha256"]
        report_sha = run["report_sha256"]
        if not isinstance(policy_sha, str) or not _SHA256.fullmatch(policy_sha):
            raise StewardHistoryInputError(
                f"history.runs[{index}].policy_sha256 must be lowercase SHA-256"
            )
        if not isinstance(report_sha, str) or not _SHA256.fullmatch(report_sha):
            raise StewardHistoryInputError(
                f"history.runs[{index}].report_sha256 must be lowercase SHA-256"
            )
        policy_values.append(policy_sha)

        run_id = _nullable_string(run["run_id"], f"history.runs[{index}].run_id")
        run_attempt = _nullable_string(
            run["run_attempt"],
            f"history.runs[{index}].run_attempt",
        )
        if (run_id is None) != (run_attempt is None):
            raise StewardHistoryInputError(
                f"history.runs[{index}] run_id and run_attempt must be paired"
            )
        if run_id is not None:
            identity = (run_id, run_attempt or "")
            if identity in seen_identities:
                raise StewardHistoryInputError(
                    "history contains duplicate GitHub workflow run identity "
                    f"{run_id}/{run_attempt}"
                )
            seen_identities.add(identity)

        trusted_head = _nullable_string(
            run["trusted_head_sha"],
            f"history.runs[{index}].trusted_head_sha",
        )
        if trusted_head is not None and not _SHA40.fullmatch(trusted_head):
            raise StewardHistoryInputError(
                f"history.runs[{index}].trusted_head_sha must be lowercase "
                "40-hex Git SHA"
            )

        order = _semantic_run_order(run)
        if previous_order is not None and order < previous_order:
            raise StewardHistoryInputError(
                "history runs must use deterministic semantic ordering"
            )
        previous_order = order

    if history["first_generated_at"] != runs[0]["generated_at"]:
        raise StewardHistoryInputError(
            "history.first_generated_at must match the first run"
        )
    if history["last_generated_at"] != runs[-1]["generated_at"]:
        raise StewardHistoryInputError(
            "history.last_generated_at must match the last run"
        )

    status_counts = _exact_keys(
        history["status_counts"],
        set(expected_status),
        "history.status_counts",
    )
    for key, expected in expected_status.items():
        if _nonnegative_int(status_counts[key], f"history.status_counts.{key}") != expected:
            raise StewardHistoryInputError(
                f"history.status_counts.{key} does not match run records"
            )

    outcomes = _exact_keys(
        history["outcome_totals"],
        set(expected_outcomes),
        "history.outcome_totals",
    )
    for key, expected in expected_outcomes.items():
        if _nonnegative_int(outcomes[key], f"history.outcome_totals.{key}") != expected:
            raise StewardHistoryInputError(
                f"history.outcome_totals.{key} does not match run records"
            )

    api = _exact_keys(
        history["api_budget"],
        {"observed_runs", "min_remaining", "max_remaining"},
        "history.api_budget",
    )
    if _nonnegative_int(api["observed_runs"], "history.api_budget.observed_runs") != len(api_values):
        raise StewardHistoryInputError(
            "history.api_budget.observed_runs does not match run records"
        )
    expected_min = min(api_values) if api_values else None
    expected_max = max(api_values) if api_values else None
    if api["min_remaining"] != expected_min or api["max_remaining"] != expected_max:
        raise StewardHistoryInputError(
            "history API budget min/max does not match run records"
        )

    policy = _exact_keys(
        history["policy"],
        {"distinct_digests", "changes", "latest_sha256"},
        "history.policy",
    )
    expected_distinct = len(set(policy_values))
    expected_changes = sum(
        1
        for previous, current in zip(policy_values, policy_values[1:])
        if current != previous
    )
    if _nonnegative_int(policy["distinct_digests"], "history.policy.distinct_digests") != expected_distinct:
        raise StewardHistoryInputError(
            "history.policy.distinct_digests does not match run records"
        )
    if _nonnegative_int(policy["changes"], "history.policy.changes") != expected_changes:
        raise StewardHistoryInputError(
            "history.policy.changes does not match chronological run records"
        )
    if policy["latest_sha256"] != policy_values[-1]:
        raise StewardHistoryInputError(
            "history.policy.latest_sha256 must match the latest run"
        )

    integrity = _exact_keys(
        history["integrity"],
        {"algorithm", "semantic_normalization", "input_set_sha256"},
        "history.integrity",
    )
    if integrity["algorithm"] != SEMANTIC_DIGEST_ALGORITHM:
        raise StewardHistoryInputError(
            f"history.integrity.algorithm must be {SEMANTIC_DIGEST_ALGORITHM!r}"
        )
    if integrity["semantic_normalization"] != SEMANTIC_NORMALIZATION:
        raise StewardHistoryInputError(
            "history.integrity.semantic_normalization is unsupported"
        )
    digest = integrity["input_set_sha256"]
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise StewardHistoryInputError(
            "history.integrity.input_set_sha256 must be lowercase SHA-256"
        )
    expected_digest = _input_set_sha256(repository, runs)
    if digest != expected_digest:
        raise StewardHistoryInputError(
            "history.integrity.input_set_sha256 does not match run evidence"
        )

    return history


def load_history(inputs: Iterable[str | Path]) -> dict[str, Any]:
    files = discover_report_files(inputs)
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        try:
            report = load_report(path)
        except (OSError, ValueError) as exc:
            raise StewardHistoryInputError(str(exc)) from exc
        reports.append((path, report))
    return build_history(reports)


def render_history_json(history: dict[str, Any], *, pretty: bool = False) -> str:
    validate_history(history)
    return json.dumps(
        history,
        indent=2 if pretty else None,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=None if pretty else (",", ":"),
    )


def render_history_text(history: dict[str, Any], *, details: bool = False) -> str:
    validate_history(history)
    statuses = history["status_counts"]
    outcomes = history["outcome_totals"]
    api = history["api_budget"]
    policy = history["policy"]
    integrity = history["integrity"]

    lines = [
        "IDKMesh Auto Draft PR Steward History",
        f"Repository: {history['repository']}",
        f"Reports: {history['report_count']}",
        f"Window: {history['first_generated_at']} -> {history['last_generated_at']}",
        (
            "Run states: "
            f"completed={statuses['completed']}, "
            f"blocked={statuses['blocked']}, "
            f"disabled={statuses['disabled']}"
        ),
        (
            "Outcomes: "
            f"planned={outcomes['planned']}, "
            f"created={outcomes['created']}, "
            f"skipped={outcomes['skipped']}, "
            f"head_moved={outcomes['head_moved']}, "
            f"pr_already_exists={outcomes['pr_already_exists']}"
        ),
        (
            "API budget observations: "
            f"runs={api['observed_runs']}, "
            f"min={api['min_remaining']}, max={api['max_remaining']}"
        ),
        (
            "Policy: "
            f"distinct_digests={policy['distinct_digests']}, "
            f"changes={policy['changes']}, "
            f"latest_sha256={policy['latest_sha256']}"
        ),
        f"Input set SHA-256: {integrity['input_set_sha256']}",
        "Authority: history is offline evidence only; no GitHub mutation path",
    ]

    if details:
        lines.extend(["", "Runs:"])
        for run in history["runs"]:
            blocked = (
                f", blocked={run['blocked_reason']}"
                if run["blocked_reason"]
                else ""
            )
            lines.append(
                "  - "
                f"{run['generated_at']} {run['status']} "
                f"planned={run['planned']} created={run['created']} "
                f"skipped={run['skipped']} api={run['rate_limit_remaining']} "
                f"report_sha256={run['report_sha256']}"
                f"{blocked} source={json.dumps(run['source'], ensure_ascii=False)}"
            )
    return "\n".join(lines) + "\n"
