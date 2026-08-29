#!/usr/bin/env python3
"""Collect a bounded, public-metadata snapshot for the IDKMesh evolution observer.

The collector deliberately does not store issue/PR/comment bodies. Natural-language
GitHub content is treated as untrusted input; only bounded structural signals such
as labels and same-repository ``#N`` references are retained.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.github.com"
REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9_])#([1-9][0-9]*)")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)")
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
OBSERVATION_UNAVAILABLE_EXIT = 75


class GitHubObservationUnavailable(RuntimeError):
    """The live API cannot currently provide a complete observation."""


def _is_bot(login: str | None, user_type: str | None = None) -> bool:
    value = (login or "").lower()
    return user_type == "Bot" or value.endswith("[bot]") or value in {"github-actions", "github-actions[bot]"}


def references_from_text(text: str | None, limit: int = 32) -> list[int]:
    """Return deduplicated bounded same-repository numeric references."""
    if not text:
        return []
    refs: list[int] = []
    seen: set[int] = set()
    for match in REFERENCE_RE.finditer(text):
        value = int(match.group(1))
        if value in seen:
            continue
        seen.add(value)
        refs.append(value)
        if len(refs) >= limit:
            break
    return refs


def scan_workflow_pins(root: Path) -> dict[str, Any]:
    workflow_dir = root / ".github" / "workflows"
    total = 0
    pinned = 0
    floating: list[dict[str, str]] = []
    if not workflow_dir.exists():
        return {"external_uses": 0, "pinned_uses": 0, "pin_ratio": 1.0, "floating": []}

    for path in sorted(workflow_dir.glob("*.y*ml")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = USES_RE.match(line)
            if not match:
                continue
            value = match.group(1)
            if value.startswith("./") or value.startswith("docker://") or "@" not in value:
                continue
            action, ref = value.rsplit("@", 1)
            total += 1
            if SHA40_RE.fullmatch(ref):
                pinned += 1
            else:
                floating.append({"file": str(path.relative_to(root)), "action": action, "ref": ref})
    ratio = 1.0 if total == 0 else pinned / total
    return {
        "external_uses": total,
        "pinned_uses": pinned,
        "pin_ratio": round(ratio, 6),
        "floating": floating[:100],
    }


def scan_project_memory(root: Path) -> dict[str, Any]:
    conversations = sorted((root / "docs" / "conversations").glob("*.md"))
    rules = root / "PROJECT_RULES.md"
    rule_present = False
    if rules.exists():
        text = rules.read_text(encoding="utf-8", errors="replace")
        rule_present = "Mandatory chat-to-repository preservation" in text
    return {
        "conversation_records": len(conversations),
        "preservation_rule_present": rule_present,
        "completeness_claim": False,
    }


def _request_json(path: str, token: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API}{path}"
    if params:
        url += "?" + urlencode(params)
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "idkmesh-evolution-observer/1",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # nosec: B310 - fixed GitHub API origin
            return json.load(response)
    except HTTPError as error:
        body = error.read(16_384).decode("utf-8", errors="replace").lower()
        remaining = error.headers.get("X-RateLimit-Remaining") if error.headers else None
        rate_limited = (
            error.code == 403
            and (
                remaining == "0"
                or "rate limit exceeded" in body
                or "secondary rate limit" in body
            )
        )
        if rate_limited:
            raise GitHubObservationUnavailable(
                f"GitHub API rate limit prevented a complete observation at {path}"
            ) from error
        raise


def _request_all(path: str, token: str, params: dict[str, Any] | None = None, max_pages: int = 5) -> tuple[list[Any], bool]:
    base = dict(params or {})
    base["per_page"] = 100
    items: list[Any] = []
    for page in range(1, max_pages + 1):
        base["page"] = page
        batch = _request_json(path, token, base)
        if not isinstance(batch, list):
            raise RuntimeError(f"expected list from GitHub API {path}")
        items.extend(batch)
        if len(batch) < 100:
            return items, False
    return items, True


def _labels(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for label in item.get("labels") or []:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            values.append(label["name"].strip().lower())
    return sorted(set(values))


def _age_hours(created_at: str | None, now: datetime) -> float:
    if not created_at:
        return 0.0
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return max(0.0, (now - created).total_seconds() / 3600.0)


def _normalize_issue(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "number": int(item["number"]),
        "kind": "issue",
        "labels": _labels(item),
        "references": references_from_text(item.get("body")),
        "age_hours": round(_age_hours(item.get("created_at"), now), 3),
    }


def _normalize_pr(
    item: dict[str, Any],
    now: datetime,
    reviews: list[dict[str, Any]],
    reviews_truncated: bool = False,
) -> dict[str, Any]:
    author = ((item.get("user") or {}).get("login") or "").lower()
    head_sha = str((item.get("head") or {}).get("sha") or "")
    independent_reviewers: set[str] = set()
    independent_approvers: set[str] = set()
    latest_by_reviewer: dict[str, tuple[tuple[str, int], dict[str, Any]]] = {}
    for review in [] if reviews_truncated else reviews:
        user = review.get("user") or {}
        login = (user.get("login") or "").lower()
        if not login or login == author or _is_bot(login, user.get("type")):
            continue
        if not head_sha or str(review.get("commit_id") or "") != head_sha:
            continue
        review_id = review.get("id")
        order = (
            str(review.get("submitted_at") or ""),
            review_id if isinstance(review_id, int) and not isinstance(review_id, bool) else 0,
        )
        if login not in latest_by_reviewer or order >= latest_by_reviewer[login][0]:
            latest_by_reviewer[login] = (order, review)
    for login, (_, review) in latest_by_reviewer.items():
        state = str(review.get("state") or "").upper()
        if state not in {"APPROVED", "CHANGES_REQUESTED"}:
            continue
        independent_reviewers.add(login)
        if state == "APPROVED":
            independent_approvers.add(login)
    return {
        "number": int(item["number"]),
        "kind": "pull_request",
        "draft": bool(item.get("draft")),
        "labels": _labels(item),
        "references": references_from_text(item.get("body")),
        "age_hours": round(_age_hours(item.get("created_at"), now), 3),
        "independent_review_count": len(independent_reviewers),
        "independent_approval_count": len(independent_approvers),
    }


def collect(repository: str, token: str, root: Path, event_kind: str, run_id: str) -> dict[str, Any]:
    owner, name = repository.split("/", 1)
    now = datetime.now(timezone.utc)
    repo = _request_json(f"/repos/{owner}/{name}", token)
    default_branch = repo["default_branch"]
    branch = _request_json(f"/repos/{owner}/{name}/branches/{default_branch}", token)

    issue_items, issues_truncated = _request_all(
        f"/repos/{owner}/{name}/issues", token, {"state": "open", "sort": "updated", "direction": "desc"}
    )
    raw_issues = [item for item in issue_items if "pull_request" not in item]
    raw_pulls, pulls_truncated = _request_all(
        f"/repos/{owner}/{name}/pulls", token, {"state": "open", "sort": "updated", "direction": "desc"}
    )
    raw_closed_pulls, closed_truncated = _request_all(
        f"/repos/{owner}/{name}/pulls", token, {"state": "closed", "sort": "updated", "direction": "desc"}, max_pages=2
    )
    recent_comment_since = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    raw_comments, comments_truncated = _request_all(
        f"/repos/{owner}/{name}/issues/comments",
        token,
        {"sort": "created", "direction": "desc", "since": recent_comment_since},
        max_pages=2,
    )
    raw_branches, branches_truncated = _request_all(f"/repos/{owner}/{name}/branches", token, max_pages=3)

    reviews_by_pr: dict[int, list[dict[str, Any]]] = {}
    truncated_review_prs: set[int] = set()
    for pull in raw_pulls[:25]:
        pull_number = int(pull["number"])
        reviews, reviews_truncated = _request_all(
            f"/repos/{owner}/{name}/pulls/{pull_number}/reviews", token, max_pages=5
        )
        reviews_by_pr[pull_number] = reviews
        if reviews_truncated:
            truncated_review_prs.add(pull_number)

    open_issues = [_normalize_issue(item, now) for item in raw_issues]
    open_prs = [
        _normalize_pr(
            item,
            now,
            reviews_by_pr.get(int(item["number"]), []),
            int(item["number"]) in truncated_review_prs,
        )
        for item in raw_pulls
    ]

    external: set[str] = set()
    owner_login = str((repo.get("owner") or {}).get("login") or owner).lower()

    def observe_user(user: dict[str, Any] | None) -> None:
        user = user or {}
        login = str(user.get("login") or "").lower()
        if login and login != owner_login and not _is_bot(login, user.get("type")):
            external.add(login)

    for item in raw_issues:
        observe_user(item.get("user"))
    for item in raw_pulls:
        observe_user(item.get("user"))
    recent_cutoff = now - timedelta(days=30)
    recent_merged = 0
    for item in raw_closed_pulls:
        merged_at = item.get("merged_at")
        if not merged_at:
            continue
        merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        if merged < recent_cutoff:
            continue
        recent_merged += 1
        observe_user(item.get("user"))
    for reviews in reviews_by_pr.values():
        for review in reviews:
            observe_user(review.get("user"))
    for comment in raw_comments:
        observe_user(comment.get("user"))

    snapshot = {
        "version": 1,
        "collected_at": now.isoformat(),
        "source": {
            "repository": repository,
            "default_branch": default_branch,
            "event_kind": event_kind,
            "run_id": run_id,
            "github_api_version": "2022-11-28",
            "natural_language_input_trusted": False,
        },
        "integration": {"main_protected": bool(branch.get("protected"))},
        "open_issues": open_issues,
        "open_pull_requests": open_prs,
        "recent_merged_pull_requests_30d": recent_merged,
        "external_participant_count": len(external),
        "branch_count": len(raw_branches),
        "workflow_supply_chain": scan_workflow_pins(root),
        "project_memory": scan_project_memory(root),
        "collection": {
            "issues_truncated": issues_truncated,
            "pulls_truncated": pulls_truncated,
            "closed_pulls_truncated": closed_truncated,
            "branches_truncated": branches_truncated,
            "comments_truncated": comments_truncated,
            "review_history_truncated_prs": sorted(truncated_review_prs),
            "external_participant_comment_window_days": 30,
            "reviewed_prs_capped_at": 25,
            "review_pages_per_pr_capped_at": 5,
        }
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect bounded GitHub evidence for the evolution observer")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--event-kind", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="results/evolution/repository-snapshot.json")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required for live snapshot collection")
    try:
        snapshot = collect(args.repository, token, Path(args.root).resolve(), args.event_kind, args.run_id)
    except GitHubObservationUnavailable as error:
        print(f"observation unavailable: {error}", file=sys.stderr)
        return OBSERVATION_UNAVAILABLE_EXIT
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "open_prs": len(snapshot["open_pull_requests"]), "open_issues": len(snapshot["open_issues"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
