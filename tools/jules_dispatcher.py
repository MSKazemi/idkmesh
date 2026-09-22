#!/usr/bin/env python3
"""Safely dispatch bounded GitHub issues to Google Jules.

The repository uses two labels with different meanings:

- ``agent-ready`` is a maintainer/triager approval that the issue is bounded,
  suitable for a coding agent, and contains no human-only evidence requirement.
- ``jules`` is the execution signal consumed by the Google Labs Jules GitHub App.

This tool never decides from issue prose whether work is safe. It only acts on
explicit labels, applies deny-labels as a fail-closed veto, and caps the number
of open Jules issues so generation cannot outrun review capacity.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "jules-dispatch.json"


class DispatchError(RuntimeError):
    """Raised when the dispatcher cannot safely inspect or mutate GitHub state."""


def load_policy(path: pathlib.Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "queue_label",
        "dispatch_label",
        "max_in_flight",
        "max_dispatch_per_sweep",
        "blocked_labels",
        "priority_weights",
        "size_weights",
        "bonus_weights",
        "label_definitions",
    }
    missing = sorted(required - set(policy))
    if missing:
        raise DispatchError(f"dispatch policy is missing keys: {', '.join(missing)}")
    if int(policy["max_in_flight"]) < 1:
        raise DispatchError("max_in_flight must be at least 1")
    if int(policy["max_dispatch_per_sweep"]) < 1:
        raise DispatchError("max_dispatch_per_sweep must be at least 1")
    return policy


def label_names(issue: dict[str, Any]) -> set[str]:
    return {
        str(label.get("name", "")).casefold()
        for label in issue.get("labels", [])
        if isinstance(label, dict)
    }


def is_dispatchable(issue: dict[str, Any], policy: dict[str, Any]) -> bool:
    """Return whether a GitHub issue is eligible for automatic Jules dispatch."""
    if issue.get("pull_request"):
        return False
    if issue.get("state") != "open":
        return False

    labels = label_names(issue)
    queue_label = str(policy["queue_label"]).casefold()
    dispatch_label = str(policy["dispatch_label"]).casefold()
    blocked = {str(name).casefold() for name in policy["blocked_labels"]}

    return (
        queue_label in labels
        and dispatch_label not in labels
        and not labels.intersection(blocked)
    )


def score_issue(issue: dict[str, Any], policy: dict[str, Any]) -> int:
    """Score an already-eligible issue; higher values are dispatched first."""
    labels = label_names(issue)
    score = 0
    for field in ("priority_weights", "size_weights", "bonus_weights"):
        for name, weight in policy[field].items():
            if str(name).casefold() in labels:
                score += int(weight)
    return score


def select_candidates(
    issues: Iterable[dict[str, Any]],
    policy: dict[str, Any],
    *,
    slots: int,
    event_issue_number: int | None = None,
    max_dispatch: int | None = None,
) -> list[dict[str, Any]]:
    """Select a deterministic bounded batch from the eligible queue."""
    if slots <= 0:
        return []

    limit = min(
        slots,
        int(max_dispatch)
        if max_dispatch is not None
        else int(policy["max_dispatch_per_sweep"]),
    )
    if limit <= 0:
        return []

    candidates = [issue for issue in issues if is_dispatchable(issue, policy)]

    def sort_key(issue: dict[str, Any]) -> tuple[int, int, int]:
        number = int(issue["number"])
        event_rank = 0 if event_issue_number == number else 1
        return (event_rank, -score_issue(issue, policy), number)

    return sorted(candidates, key=sort_key)[:limit]


class GitHubAPI:
    """Small stdlib-only GitHub REST client for the dispatcher workflow."""

    def __init__(self, token: str, repository: str, api_url: str) -> None:
        if "/" not in repository:
            raise DispatchError("GITHUB_REPOSITORY must have owner/name form")
        self.token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self.repo_path = f"/repos/{repository}"

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | list[Any] | None = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "idkmesh-jules-dispatcher/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DispatchError(
                f"GitHub API {method} {path} failed with {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise DispatchError(f"GitHub API request failed: {exc}") from exc

    def paginate(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            query = dict(params)
            query.update({"per_page": 100, "page": page})
            encoded = urllib.parse.urlencode(query)
            batch = self.request("GET", f"{path}?{encoded}")
            if not isinstance(batch, list):
                raise DispatchError(f"expected list response from {path}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def list_labels(self) -> list[dict[str, Any]]:
        return self.paginate(f"{self.repo_path}/labels", {})

    def create_label(self, name: str, color: str, description: str) -> None:
        self.request(
            "POST",
            f"{self.repo_path}/labels",
            {"name": name, "color": color.lstrip("#"), "description": description},
        )

    def list_open_issues(self, label: str) -> list[dict[str, Any]]:
        return self.paginate(
            f"{self.repo_path}/issues",
            {"state": "open", "labels": label},
        )

    def add_labels(self, issue_number: int, labels: list[str]) -> None:
        self.request(
            "POST",
            f"{self.repo_path}/issues/{issue_number}/labels",
            {"labels": labels},
        )


def ensure_labels(
    api: GitHubAPI,
    policy: dict[str, Any],
    *,
    dry_run: bool = False,
) -> list[str]:
    """Create any policy labels missing from the repository; never rewrite existing ones."""
    existing = {
        str(label.get("name", "")).casefold() for label in api.list_labels()
    }
    created: list[str] = []

    for name, definition in policy["label_definitions"].items():
        if str(name).casefold() in existing:
            continue
        created.append(str(name))
        if not dry_run:
            api.create_label(
                str(name),
                str(definition["color"]),
                str(definition["description"]),
            )

    return created


def dispatch(
    api: GitHubAPI,
    policy: dict[str, Any],
    *,
    event_issue_number: int | None = None,
    max_dispatch: int | None = None,
    dry_run: bool = False,
) -> list[int]:
    """Fill available Jules capacity from the explicit agent-ready queue."""
    dispatch_label = str(policy["dispatch_label"])
    queue_label = str(policy["queue_label"])

    active = [
        issue
        for issue in api.list_open_issues(dispatch_label)
        if not issue.get("pull_request")
    ]
    slots = max(0, int(policy["max_in_flight"]) - len(active))
    if slots == 0:
        print(
            f"jules dispatcher: capacity full "
            f"({len(active)}/{policy['max_in_flight']} open dispatched issues)"
        )
        return []

    queued = api.list_open_issues(queue_label)
    selected = select_candidates(
        queued,
        policy,
        slots=slots,
        event_issue_number=event_issue_number,
        max_dispatch=max_dispatch,
    )

    numbers: list[int] = []
    for issue in selected:
        number = int(issue["number"])
        numbers.append(number)
        if not dry_run:
            api.add_labels(number, [dispatch_label])
        print(
            f"jules dispatcher: {'would dispatch' if dry_run else 'dispatched'} "
            f"#{number} score={score_issue(issue, policy)}"
        )

    if not numbers:
        print("jules dispatcher: no eligible agent-ready issues")
    return numbers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--policy",
        type=pathlib.Path,
        default=DEFAULT_POLICY,
        help="path to the dispatch policy JSON",
    )
    parser.add_argument("--init-labels", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--event-issue", type=int)
    parser.add_argument("--max-dispatch", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.init_labels and not args.dispatch:
        raise SystemExit("choose --init-labels and/or --dispatch")
    if args.max_dispatch is not None and args.max_dispatch < 1:
        raise SystemExit("--max-dispatch must be at least 1")

    policy = load_policy(args.policy)
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    api = GitHubAPI(token=token, repository=repository, api_url=api_url)

    try:
        if args.init_labels:
            created = ensure_labels(api, policy, dry_run=args.dry_run)
            if created:
                print("jules dispatcher: labels " + ", ".join(created))
            else:
                print("jules dispatcher: policy labels already exist")
        if args.dispatch:
            dispatch(
                api,
                policy,
                event_issue_number=args.event_issue,
                max_dispatch=args.max_dispatch,
                dry_run=args.dry_run,
            )
    except DispatchError as exc:
        print(f"jules dispatcher: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
