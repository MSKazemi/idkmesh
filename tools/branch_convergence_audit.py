#!/usr/bin/env python3
"""Read-only branch convergence audit for IDKMesh.

The auditor classifies repository branches using two independent facts:

1. pull-request state for the branch; and
2. commit ancestry relative to the default branch.

It never merges, deletes, pushes, approves, or changes repository settings.
Its purpose is to distinguish work that is already integrated from work that
needs review, extraction, or a clean current-main replacement.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
USER_AGENT = "idkmesh-branch-convergence-audit/0.1"


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequestRef:
    number: int
    state: str
    merged: bool
    draft: bool
    head_sha: str
    base_ref: str
    updated_at: str | None


@dataclass(frozen=True)
class Comparison:
    status: str
    ahead_by: int
    behind_by: int


@dataclass(frozen=True)
class BranchDecision:
    branch: str
    state: str
    recommendation: str
    direct_merge_allowed: bool
    cleanup_eligible: bool
    comparison_status: str
    ahead_by: int
    behind_by: int
    pull_requests: tuple[int, ...]
    notes: tuple[str, ...]


def _no_unique_commits(comparison: Comparison) -> bool:
    return comparison.ahead_by == 0 and comparison.status in {"behind", "identical"}


def classify_branch(
    *,
    branch: str,
    default_branch: str,
    comparison: Comparison,
    prs: list[PullRequestRef],
) -> BranchDecision:
    """Classify one branch without performing any repository mutation."""

    if branch == default_branch:
        return BranchDecision(
            branch=branch,
            state="canonical",
            recommendation="keep canonical branch",
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=tuple(sorted(pr.number for pr in prs)),
            notes=("canonical state is never treated as a source branch",),
        )

    open_prs = [pr for pr in prs if pr.state == "open"]
    merged_prs = [pr for pr in prs if pr.merged]
    closed_unmerged_prs = [pr for pr in prs if pr.state == "closed" and not pr.merged]

    if len(open_prs) > 1:
        return BranchDecision(
            branch=branch,
            state="ambiguous-open-prs",
            recommendation="block integration until one canonical PR remains",
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=tuple(sorted(pr.number for pr in prs)),
            notes=("multiple open PRs reference the same branch",),
        )

    if len(open_prs) == 1:
        pr = open_prs[0]
        if pr.draft:
            return BranchDecision(
                branch=branch,
                state="active-draft-pr",
                recommendation="keep branch; satisfy explicit PR blockers before merge review",
                direct_merge_allowed=False,
                cleanup_eligible=False,
                comparison_status=comparison.status,
                ahead_by=comparison.ahead_by,
                behind_by=comparison.behind_by,
                pull_requests=tuple(sorted(item.number for item in prs)),
                notes=(
                    f"open draft PR #{pr.number}",
                    "if exact-SHA evidence is bound to this head, moving the branch invalidates that evidence",
                ),
            )
        return BranchDecision(
            branch=branch,
            state="active-review-pr",
            recommendation="use the PR merge gate; never merge the branch directly",
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=tuple(sorted(item.number for item in prs)),
            notes=(f"open review PR #{pr.number}",),
        )

    # A merged PR is the strongest cleanup signal. Squash merges deliberately
    # break simple ancestry, so PR merged state takes precedence over compare
    # status when deciding whether a source branch needs to be merged again.
    if merged_prs:
        return BranchDecision(
            branch=branch,
            state="integrated-via-pr",
            recommendation="do not merge again; delete branch after provenance/evidence references are durable",
            direct_merge_allowed=False,
            cleanup_eligible=True,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=tuple(sorted(item.number for item in prs)),
            notes=(
                "at least one PR from this branch is already merged",
                "squash-merged branches may still appear divergent by ancestry",
            ),
        )

    if closed_unmerged_prs:
        if _no_unique_commits(comparison):
            return BranchDecision(
                branch=branch,
                state="closed-unmerged-no-unique-commits",
                recommendation="delete branch; there is no unique branch work left to integrate",
                direct_merge_allowed=False,
                cleanup_eligible=True,
                comparison_status=comparison.status,
                ahead_by=comparison.ahead_by,
                behind_by=comparison.behind_by,
                pull_requests=tuple(sorted(item.number for item in prs)),
                notes=("closed unmerged PR history remains the durable record",),
            )

        evidence_sensitive = branch.startswith("acceptance/") or "/reference" in branch
        state = (
            "closed-unmerged-evidence-branch"
            if evidence_sensitive
            else "closed-unmerged-unique-work"
        )
        recommendation = (
            "inspect evidence/provenance references, then delete or extract only the still-useful artifact onto current main"
            if evidence_sensitive
            else "review unique commits; extract useful pieces into a clean current-main PR or delete as superseded"
        )
        return BranchDecision(
            branch=branch,
            state=state,
            recommendation=recommendation,
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=tuple(sorted(item.number for item in prs)),
            notes=(
                "closed-unmerged history must not be bulk-merged into main",
                "preserve negative results and unique provenance before cleanup",
            ),
        )

    if _no_unique_commits(comparison):
        return BranchDecision(
            branch=branch,
            state="orphan-no-unique-commits",
            recommendation="delete branch after confirming no external workflow depends on the branch name",
            direct_merge_allowed=False,
            cleanup_eligible=True,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=(),
            notes=("branch has no PR and no commits ahead of main",),
        )

    if comparison.status == "ahead" and comparison.behind_by == 0:
        return BranchDecision(
            branch=branch,
            state="orphan-clean-ahead",
            recommendation="inspect ownership/context and open a normal PR; do not direct-merge",
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=(),
            notes=("branch contains unique commits on top of current main ancestry",),
        )

    if comparison.status == "diverged":
        return BranchDecision(
            branch=branch,
            state="orphan-diverged",
            recommendation="build a clean replacement from current main and transplant only reviewed unique work",
            direct_merge_allowed=False,
            cleanup_eligible=False,
            comparison_status=comparison.status,
            ahead_by=comparison.ahead_by,
            behind_by=comparison.behind_by,
            pull_requests=(),
            notes=("direct merge would combine stale ancestry with unique work",),
        )

    return BranchDecision(
        branch=branch,
        state="unknown",
        recommendation="hold; inspect manually before any merge or deletion",
        direct_merge_allowed=False,
        cleanup_eligible=False,
        comparison_status=comparison.status,
        ahead_by=comparison.ahead_by,
        behind_by=comparison.behind_by,
        pull_requests=tuple(sorted(item.number for item in prs)),
        notes=("comparison/PR state did not match a known safe branch state",),
    )


class GitHubClient:
    def __init__(self, token: str | None) -> None:
        self.token = token

    def get(self, url: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AuditError(f"GitHub API HTTP {exc.code} for {url}: {detail[:500]}") from exc
        except (URLError, TimeoutError) as exc:
            raise AuditError(f"GitHub API request failed for {url}: {exc}") from exc

    def paged(self, path: str) -> list[Any]:
        items: list[Any] = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{API_ROOT}{path}{separator}per_page=100&page={page}")
            if not isinstance(payload, list):
                raise AuditError(f"expected list response for {path}")
            items.extend(payload)
            if len(payload) < 100:
                break
            page += 1
        return items


def _same_repo_prs(prs: list[dict[str, Any]], repo: str) -> dict[str, list[PullRequestRef]]:
    by_branch: dict[str, list[PullRequestRef]] = defaultdict(list)
    for pr in prs:
        head = pr.get("head") or {}
        head_repo = head.get("repo") or {}
        if head_repo.get("full_name") != repo:
            continue
        ref = head.get("ref")
        sha = head.get("sha")
        if not isinstance(ref, str) or not isinstance(sha, str):
            continue
        by_branch[ref].append(
            PullRequestRef(
                number=int(pr["number"]),
                state=str(pr.get("state", "unknown")),
                merged=pr.get("merged_at") is not None,
                draft=bool(pr.get("draft", False)),
                head_sha=sha,
                base_ref=str((pr.get("base") or {}).get("ref", "")),
                updated_at=pr.get("updated_at"),
            )
        )
    return by_branch


def _compare(client: GitHubClient, repo: str, base: str, head: str) -> Comparison:
    owner, name = repo.split("/", 1)
    base_ref = quote(base, safe="/")
    head_ref = quote(head, safe="/")
    payload = client.get(
        f"{API_ROOT}/repos/{quote(owner)}/{quote(name)}/compare/{base_ref}...{head_ref}"
    )
    return Comparison(
        status=str(payload.get("status", "unknown")),
        ahead_by=int(payload.get("ahead_by", 0)),
        behind_by=int(payload.get("behind_by", 0)),
    )


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Branch Convergence Audit",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Default branch: `{report['default_branch']}`",
        f"- Default branch protected: `{str(report['default_branch_protected']).lower()}`",
        f"- Branches observed: **{report['summary']['total_branches']}**",
        f"- Cleanup-eligible: **{report['summary']['cleanup_eligible']}**",
        f"- Direct branch merge allowed: **0**",
        "",
        "The audit is advisory/read-only. A branch is never a merge unit by itself; normal pull-request review is the integration boundary.",
        "",
        "## State counts",
        "",
        "| State | Count |",
        "| --- | ---: |",
    ]
    for state, count in sorted(report["summary"]["states"].items()):
        lines.append(f"| `{state}` | {count} |")

    lines.extend(
        [
            "",
            "## Branch decisions",
            "",
            "| Branch | State | Ahead | Behind | PRs | Recommendation |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for item in report["branches"]:
        prs = ", ".join(f"#{number}" for number in item["pull_requests"]) or "-"
        recommendation = item["recommendation"].replace("|", "\\|")
        lines.append(
            f"| `{item['branch']}` | `{item['state']}` | {item['ahead_by']} | "
            f"{item['behind_by']} | {prs} | {recommendation} |"
        )
    lines.extend(
        [
            "",
            "## Merge discipline",
            "",
            "1. Integrate through a PR, not by directly merging arbitrary branch refs.",
            "2. A merged PR means the source branch must not be merged again, even when squash history makes it look divergent.",
            "3. Closed-unmerged divergent branches are extraction/replacement candidates, not bulk-merge candidates.",
            "4. Exact-SHA acceptance/evidence branches must not move without invalidating or refreshing bound evidence.",
            "5. Branch cleanup is separate from correctness: delete only after durable PR/evidence provenance is preserved.",
        ]
    )
    return "\n".join(lines) + "\n"


def audit(repo: str, default_branch: str, token: str | None) -> dict[str, Any]:
    if repo.count("/") != 1:
        raise AuditError("--repo must use owner/name form")

    owner, name = repo.split("/", 1)
    client = GitHubClient(token)
    branches = client.paged(f"/repos/{quote(owner)}/{quote(name)}/branches")
    prs = client.paged(f"/repos/{quote(owner)}/{quote(name)}/pulls?state=all")
    pr_by_branch = _same_repo_prs(prs, repo)

    protected_payload = client.get(
        f"{API_ROOT}/repos/{quote(owner)}/{quote(name)}/branches/{quote(default_branch, safe='/')}"
    )
    default_protected = bool(protected_payload.get("protected", False))

    decisions: list[BranchDecision] = []
    for raw in sorted(branches, key=lambda value: str(value.get("name", ""))):
        branch = str(raw.get("name", ""))
        if not branch:
            continue
        if branch == default_branch:
            comparison = Comparison("identical", 0, 0)
        else:
            comparison = _compare(client, repo, default_branch, branch)
        decisions.append(
            classify_branch(
                branch=branch,
                default_branch=default_branch,
                comparison=comparison,
                prs=pr_by_branch.get(branch, []),
            )
        )

    state_counts = Counter(item.state for item in decisions)
    report = {
        "schema_version": "0.1",
        "repository": repo,
        "default_branch": default_branch,
        "default_branch_protected": default_protected,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority": {
            "read_only": True,
            "merge": False,
            "delete_branch": False,
            "approve": False,
            "repository_settings": False,
        },
        "summary": {
            "total_branches": len(decisions),
            "non_default_branches": max(0, len(decisions) - 1),
            "cleanup_eligible": sum(item.cleanup_eligible for item in decisions),
            "states": dict(sorted(state_counts.items())),
        },
        "branches": [asdict(item) for item in decisions],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repository in owner/name form")
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="environment variable containing a read-only GitHub token",
    )
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env)
    try:
        report = audit(args.repo, args.default_branch, token)
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    md_text = _render_markdown(report)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(md_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
