#!/usr/bin/env python3
"""Collect a bounded, pseudonymized GitHub history for collaboration metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.evolution_snapshot import (
        GitHubObservationUnavailable,
        _is_bot,
        _request_json,
    )
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from evolution_snapshot import GitHubObservationUnavailable, _is_bot, _request_json


OBSERVATION_UNAVAILABLE_EXIT = 75
COLLECTOR = "github-collaboration-window-v0.2"
OWNERSHIP_MODEL = "last_merged_toucher_within_window-v1"
STRUCTURAL_DEBT_MODEL = "deterministic_observatory_attributed_to_last_toucher-v1"
REVIEW_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "COMMENTED"})
CONCLUSIVE_CHECK_CONCLUSIONS = frozenset(
    {"success", "failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}
)
RequestJSON = Callable[[str, str, dict[str, Any] | None], Any]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _pseudonym(login: str, repository: str) -> str:
    digest = hashlib.sha256(f"{repository.lower()}:{login.lower()}".encode()).hexdigest()
    return f"actor:{digest[:16]}"


def _bounded_list(
    request_json: RequestJSON,
    path: str,
    token: str,
    params: dict[str, Any],
    field: str | None = None,
    *,
    allow_full_page: bool = False,
) -> list[dict[str, Any]]:
    payload = request_json(path, token, params)
    rows = payload.get(field) if field and isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"GitHub response for {path} must contain a list")
    if not allow_full_page and len(rows) >= int(params.get("per_page", 100)):
        raise GitHubObservationUnavailable(f"GitHub history at {path} exceeds the bounded page")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"GitHub response for {path} contains a non-object item")
    return rows


def _review_ready_at(pull: dict[str, Any], timeline: list[dict[str, Any]]) -> str | None:
    events = sorted(
        (
            row.get("created_at")
            for row in timeline
            if row.get("event") == "ready_for_review" and isinstance(row.get("created_at"), str)
        ),
    )
    if events:
        return events[0]
    if pull.get("draft") is True:
        return None
    created = pull.get("created_at")
    return created if isinstance(created, str) else None


def _independent_reviews(
    pull: dict[str, Any],
    reviews: list[dict[str, Any]],
    repository: str,
    cutoff: datetime,
    review_ready_at: str | None,
) -> tuple[list[str], str | None]:
    author = str((pull.get("user") or {}).get("login") or "")
    observed: list[tuple[datetime, str]] = []
    ready_time = (
        datetime.fromisoformat(review_ready_at.replace("Z", "+00:00"))
        if review_ready_at is not None
        else None
    )
    for review in reviews:
        user = review.get("user") or {}
        login = user.get("login")
        submitted = review.get("submitted_at")
        state = str(review.get("state") or "").upper()
        if not isinstance(login, str) or not isinstance(submitted, str):
            continue
        if state not in REVIEW_STATES or login.lower() == author.lower() or _is_bot(login, user.get("type")):
            continue
        if state == "COMMENTED" and not str(review.get("body") or "").strip():
            continue
        timestamp = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
        if timestamp <= cutoff:
            observed.append((timestamp, _pseudonym(login, repository)))
    observed.sort()
    eligible = [row for row in observed if ready_time is not None and row[0] >= ready_time]
    first = eligible[0][0].isoformat().replace("+00:00", "Z") if eligible else None
    return sorted({actor for _, actor in observed}), first


def _changed_paths(
    request_json: RequestJSON, repository: str, number: int, token: str
) -> tuple[list[str], bool]:
    """Return the paths a pull request changed and whether the page saturated.

    A pull request with 100 or more changed files exceeds one bounded page. The
    collector keeps the partial observation rather than failing the whole window,
    but flags it so no downstream metric can silently treat it as complete.
    """
    rows = _bounded_list(
        request_json,
        f"/repos/{repository}/pulls/{number}/files",
        token,
        {"per_page": 100},
        allow_full_page=True,
    )
    paths: list[str] = []
    for row in rows:
        filename = row.get("filename")
        if isinstance(filename, str) and filename:
            paths.append(filename)
    return sorted(set(paths)), len(rows) >= 100


def _finding_id(finding: dict[str, Any]) -> str:
    """Derive a stable identifier for a deterministic observatory finding.

    The identity is the (category, path, line) triple the producer already emits,
    so the same repository state yields the same identifier on any machine and the
    identifier stays stable when unrelated findings appear or disappear.
    """
    category = str(finding.get("category") or "")
    source_path = str(finding.get("source_path") or "")
    line = int(finding.get("line") or 0)
    digest = hashlib.sha256(f"{category}|{source_path}|{line}".encode()).hexdigest()
    return f"debt:{digest[:16]}"


def _load_structural_debt(report: Path | None) -> list[dict[str, Any]]:
    """Read deterministic structural-debt findings from an observatory report."""
    if report is None:
        return []
    payload = json.loads(report.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), "structural debt report must be a JSON object")
    findings = payload.get("findings")
    _require(isinstance(findings, list), "structural debt report must contain findings")
    loaded: list[dict[str, Any]] = []
    for finding in findings:
        _require(isinstance(finding, dict), "each structural debt finding must be an object")
        source_path = finding.get("source_path")
        _require(
            isinstance(source_path, str) and source_path,
            "each structural debt finding requires a source_path",
        )
        loaded.append(
            {
                "id": _finding_id(finding),
                "category": str(finding.get("category") or "uncategorized"),
                "severity": str(finding.get("severity") or "unknown"),
                "source_path": source_path,
            }
        )
    return loaded


def _attribute_structural_debt(
    findings: list[dict[str, Any]], touched: dict[str, list[int]]
) -> tuple[dict[int, list[str]], list[dict[str, Any]]]:
    """Attach each finding to the last pull request in the window that touched it.

    A finding whose path was never touched inside the bounded window is left
    unattributed rather than assigned to an arbitrary pull request. The caller
    reports those separately so the observable cannot understate the inventory
    without saying so.
    """
    attributed: dict[int, list[str]] = defaultdict(list)
    unattributed: list[dict[str, Any]] = []
    for finding in findings:
        numbers = touched.get(finding["source_path"])
        if not numbers:
            unattributed.append(finding)
            continue
        attributed[max(numbers)].append(finding["id"])
    return {number: sorted(set(ids)) for number, ids in attributed.items()}, unattributed


def _ci_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    conclusive = [
        row
        for row in checks
        if row.get("status") == "completed"
        and str(row.get("conclusion")).lower() in CONCLUSIVE_CHECK_CONCLUSIONS
    ]
    passed = sum(str(row.get("conclusion")).lower() == "success" for row in conclusive)
    return {"passed": passed, "total": len(conclusive)}


def collect(
    repository: str,
    token: str,
    *,
    max_pull_requests: int = 50,
    request_json: RequestJSON = _request_json,
    now: datetime | None = None,
    structural_debt_report: Path | None = None,
) -> dict[str, Any]:
    _require("/" in repository and repository.count("/") == 1, "repository must be owner/name")
    _require(1 <= max_pull_requests <= 99, "max_pull_requests must be in [1, 99]")
    cutoff = now or datetime.now(timezone.utc)
    _require(cutoff.tzinfo is not None, "cutoff must include a timezone")

    rate = request_json("/rate_limit", token, None)
    remaining = int((((rate or {}).get("resources") or {}).get("core") or {}).get("remaining", 0))
    required_budget = 4 * max_pull_requests + 10
    if remaining < required_budget:
        raise GitHubObservationUnavailable(
            f"GitHub API budget {remaining} is below required reserve {required_budget}"
        )

    owner = repository.split("/", 1)[0].lower()
    pulls = _bounded_list(
        request_json,
        f"/repos/{repository}/pulls",
        token,
        {"state": "all", "sort": "created", "direction": "desc", "per_page": max_pull_requests},
        allow_full_page=True,
    )
    normalized: list[dict[str, Any]] = []
    contribution_times: dict[str, list[str]] = defaultdict(list)
    # Ownership is a within-window model: a path is owned by the author of the most
    # recent merged pull request that changed it. Iterating in ascending number order
    # means `owner_of_path` always holds the state as of the pull request being read,
    # so a pull request is never attributed ownership it only acquired by merging.
    owner_of_path: dict[str, str] = {}
    touched_by: dict[str, list[int]] = defaultdict(list)
    saturated_file_lists: list[int] = []

    for pull in sorted(pulls, key=lambda row: int(row["number"])):
        number = int(pull["number"])
        author_user = pull.get("user") or {}
        author = author_user.get("login")
        _require(isinstance(author, str) and author, f"pull request {number} is missing an author")
        timeline = _bounded_list(
            request_json,
            f"/repos/{repository}/issues/{number}/timeline",
            token,
            {"per_page": 100},
        )
        reviews = _bounded_list(
            request_json,
            f"/repos/{repository}/pulls/{number}/reviews",
            token,
            {"per_page": 100},
        )
        head_sha = str((pull.get("head") or {}).get("sha") or "")
        _require(head_sha, f"pull request {number} is missing its head SHA")
        checks = _bounded_list(
            request_json,
            f"/repos/{repository}/commits/{head_sha}/check-runs",
            token,
            {"filter": "latest", "per_page": 100},
            "check_runs",
        )
        ready_at = _review_ready_at(pull, timeline)
        reviewer_ids, first_review = _independent_reviews(
            pull, reviews, repository, cutoff, ready_at
        )
        changed_paths, saturated = _changed_paths(request_json, repository, number, token)
        if saturated:
            saturated_file_lists.append(number)
        # One attribution per changed file, so a pull request that touches many files
        # owned by one actor weighs on concentration as heavily as the change it made.
        changed_file_owners = [
            owner_of_path[path] for path in changed_paths if path in owner_of_path
        ]
        for path in changed_paths:
            touched_by[path].append(number)
        normalized.append(
            {
                "number": number,
                "author": _pseudonym(author, repository),
                "created_at": pull["created_at"],
                "review_ready_at": ready_at,
                "first_independent_review_at": first_review,
                "closed_at": pull.get("closed_at"),
                "review_ready": pull.get("state") == "open" and pull.get("draft") is False,
                "independent_reviewers": reviewer_ids,
                "changed_file_owners": changed_file_owners,
                "changed_file_count": len(changed_paths),
                "changed_files_truncated": saturated,
                "unattributed_changed_files": len(changed_paths) - len(changed_file_owners),
                "ci_checks": _ci_counts(checks),
                "structural_debt_finding_ids": [],
            }
        )
        merged_at = pull.get("merged_at")
        if (
            isinstance(merged_at, str)
            and author.lower() != owner
            and not _is_bot(author, author_user.get("type"))
        ):
            contribution_times[_pseudonym(author, repository)].append(merged_at)
        if isinstance(merged_at, str):
            for path in changed_paths:
                owner_of_path[path] = _pseudonym(author, repository)

    contributors = [
        {"login": actor, "meaningful_contributions": sorted(set(timestamps))}
        for actor, timestamps in sorted(contribution_times.items())
    ]

    debt_findings = _load_structural_debt(structural_debt_report)
    attributed, unattributed = _attribute_structural_debt(debt_findings, touched_by)
    for row in normalized:
        row["structural_debt_finding_ids"] = attributed.get(row["number"], [])

    limitations = [
        "bounded_recent_window_not_complete_repository_history",
        "merged_pull_request_is_the_only_meaningful_contribution_proxy",
        "ownership_is_last_merged_toucher_inside_the_window_not_repository_history",
    ]
    if structural_debt_report is None:
        limitations.append("structural_debt_inventory_not_collected")
    if unattributed:
        limitations.append("structural_debt_findings_outside_the_window_are_unattributed")
    if saturated_file_lists:
        limitations.append("changed_file_list_saturated_the_bounded_page_for_some_pull_requests")

    # The inventory is only complete when a deterministic report was supplied *and*
    # every finding in it reached a pull request. An unattributed finding would make
    # the downstream count an undercount, and claiming completeness over an
    # undercount would be a false statement about the repository.
    inventory_complete = bool(structural_debt_report is not None and not unattributed)

    cutoff_text = cutoff.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "version": 1,
        "repository": repository,
        "cutoff_at": cutoff_text,
        "inventory_complete": inventory_complete,
        "pull_requests": normalized,
        "contributors": contributors,
        "collection": {
            "method": COLLECTOR,
            "window": "most_recent_pull_requests_by_creation",
            "maximum_pull_requests": max_pull_requests,
            "observed_pull_requests": len(normalized),
            "api_budget_at_start": remaining,
            "raw_bodies_retained": False,
            "actor_logins_retained": False,
            "strategy_outcomes_classified": False,
            "ownership": {
                "model": OWNERSHIP_MODEL,
                "attributed_files": sum(
                    len(row["changed_file_owners"]) for row in normalized
                ),
                "unattributed_files": sum(
                    row["unattributed_changed_files"] for row in normalized
                ),
                "saturated_file_lists": sorted(saturated_file_lists),
            },
            "structural_debt": {
                "model": STRUCTURAL_DEBT_MODEL,
                "report_supplied": structural_debt_report is not None,
                "findings_loaded": len(debt_findings),
                "findings_attributed": sum(len(ids) for ids in attributed.values()),
                "findings_unattributed": len(unattributed),
                "unattributed_paths": sorted(
                    {finding["source_path"] for finding in unattributed}
                ),
                "index": [
                    {
                        "id": finding["id"],
                        "category": finding["category"],
                        "severity": finding["severity"],
                        "source_path": finding["source_path"],
                    }
                    for finding in sorted(debt_findings, key=lambda row: row["id"])
                ],
            },
            "limitations": sorted(limitations),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pull-requests", type=int, default=50)
    parser.add_argument(
        "--structural-debt-report",
        type=Path,
        default=None,
        help=(
            "observatory.json emitted by tools/idkgraph_observatory.py; its "
            "deterministic findings are attributed to the last pull request in the "
            "window that changed the finding's path"
        ),
    )
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    try:
        snapshot = collect(
            args.repository,
            token,
            max_pull_requests=args.max_pull_requests,
            structural_debt_report=args.structural_debt_report,
        )
    except GitHubObservationUnavailable as error:
        print(f"observation unavailable: {error}", file=sys.stderr)
        return OBSERVATION_UNAVAILABLE_EXIT
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "pull_requests": len(snapshot["pull_requests"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
