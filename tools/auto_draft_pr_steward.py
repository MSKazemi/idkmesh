from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

API_VERSION = "2022-11-28"
REPORT_SCHEMA = "auto-draft-pr-steward-report-v0.1"
MAX_PR_TITLE_LENGTH = 180
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status
        self.message = message
        self.body = body


@dataclass(frozen=True)
class Policy:
    enabled: bool
    not_before: datetime
    default_base: str
    managed_prefixes: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    infer_stacked_base: bool
    max_creations_per_run: int
    max_branch_pages: int
    max_pr_pages: int
    max_untracked_branches_per_run: int
    max_candidate_evaluations_per_run: int
    max_open_pr_heads_for_stack_inference: int
    minimum_rate_limit_remaining: int


@dataclass(frozen=True)
class Candidate:
    branch: str
    head_sha: str
    base: str
    status: str
    ahead_by: int
    behind_by: int


class GitHubClient:
    def __init__(self, repo: str, token: str, api_url: str = "https://api.github.com") -> None:
        if _REPOSITORY.fullmatch(repo) is None or any(
            component in {".", ".."} for component in repo.split("/")
        ):
            raise ValueError("repo must use owner/name form")
        self.repo = repo
        self.token = token
        self.api_url = api_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode()
        req = request.Request(
            self.api_url + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "idkmesh-auto-draft-pr-steward/0.1",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode()
        except error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                message = str(json.loads(raw).get("message", raw))
            except json.JSONDecodeError:
                message = raw
            raise GitHubApiError(exc.code, message, raw) from exc
        return json.loads(raw) if raw else None

    def _paginate(self, path: str, max_pages: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self._request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"expected list response for {path}")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise RuntimeError(f"pagination limit reached for {path}; refusing incomplete scan")

    def list_branches(self, max_pages: int) -> list[dict[str, Any]]:
        return self._paginate(f"/repos/{self.repo}/branches", max_pages)

    def list_pulls(self, max_pages: int) -> list[dict[str, Any]]:
        return self._paginate(
            f"/repos/{self.repo}/pulls?state=all&sort=updated&direction=desc", max_pages
        )

    def get_commit(self, sha: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{self.repo}/commits/{parse.quote(sha, safe='')}")

    def get_branch_head(self, branch: str) -> str:
        ref = parse.quote(branch, safe="")
        payload = self._request("GET", f"/repos/{self.repo}/branches/{ref}")
        return str((payload.get("commit") or {}).get("sha") or "")

    def rate_limit_remaining(self) -> int:
        payload = self._request("GET", "/rate_limit")
        core = ((payload.get("resources") or {}).get("core") or {})
        if core.get("remaining") is None:
            raise RuntimeError("GitHub rate-limit response did not include resources.core.remaining")
        return int(core["remaining"])

    def compare(self, base: str, head: str) -> dict[str, Any]:
        base = parse.quote(base, safe="")
        head = parse.quote(head, safe="")
        return self._request("GET", f"/repos/{self.repo}/compare/{base}...{head}")

    def create_draft_pr(self, title: str, head: str, base: str, body: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{self.repo}/pulls",
            {"title": title, "head": head, "base": base, "body": body, "draft": True},
        )


def parse_time(value: str) -> datetime:
    value = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def load_policy(path: Path) -> Policy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("policy must be a JSON object")
    if raw.get("schema_version") != "0.1":
        raise ValueError("unsupported policy schema_version")

    def boolean(name: str, default: bool) -> bool:
        value = raw.get(name, default)
        if type(value) is not bool:
            raise ValueError(f"{name} must be a boolean")
        return value

    def integer(name: str, default: int) -> int:
        value = raw.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        return value

    def strings(name: str) -> tuple[str, ...]:
        value = raw.get(name, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"{name} must be an array of strings")
        return tuple(value)

    default_base = raw.get("default_base", "main")
    if not isinstance(default_base, str):
        raise ValueError("default_base must be a string")
    policy = Policy(
        enabled=boolean("enabled", False),
        not_before=parse_time(str(raw["not_before"])),
        default_base=default_base,
        managed_prefixes=strings("managed_prefixes"),
        excluded_prefixes=strings("excluded_prefixes"),
        infer_stacked_base=boolean("infer_stacked_base", True),
        max_creations_per_run=integer("max_creations_per_run", 3),
        max_branch_pages=integer("max_branch_pages", 5),
        max_pr_pages=integer("max_pr_pages", 20),
        max_untracked_branches_per_run=integer("max_untracked_branches_per_run", 50),
        max_candidate_evaluations_per_run=integer("max_candidate_evaluations_per_run", 6),
        max_open_pr_heads_for_stack_inference=integer(
            "max_open_pr_heads_for_stack_inference", 50
        ),
        minimum_rate_limit_remaining=integer("minimum_rate_limit_remaining", 1500),
    )
    if not policy.default_base:
        raise ValueError("default_base must not be empty")
    if not policy.managed_prefixes:
        raise ValueError("managed_prefixes must not be empty")
    if any(not prefix for prefix in policy.managed_prefixes + policy.excluded_prefixes):
        raise ValueError("branch prefixes must not be empty")
    if set(policy.managed_prefixes) & set(policy.excluded_prefixes):
        raise ValueError("managed_prefixes and excluded_prefixes must not overlap")
    if policy.max_creations_per_run < 0:
        raise ValueError("max_creations_per_run must be non-negative")
    if policy.max_branch_pages <= 0 or policy.max_pr_pages <= 0:
        raise ValueError("pagination limits must be positive")
    if policy.max_untracked_branches_per_run <= 0:
        raise ValueError("max_untracked_branches_per_run must be positive")
    if policy.max_candidate_evaluations_per_run <= 0:
        raise ValueError("max_candidate_evaluations_per_run must be positive")
    if policy.max_open_pr_heads_for_stack_inference <= 0:
        raise ValueError("max_open_pr_heads_for_stack_inference must be positive")
    if policy.minimum_rate_limit_remaining < 0:
        raise ValueError("minimum_rate_limit_remaining must be non-negative")
    return policy


def is_managed(name: str, policy: Policy) -> bool:
    return (
        name != policy.default_base
        and not any(name.startswith(p) for p in policy.excluded_prefixes)
        and any(name.startswith(p) for p in policy.managed_prefixes)
    )


def same_repo_head(pr: dict[str, Any], repo: str) -> str | None:
    head = pr.get("head") or {}
    if (head.get("repo") or {}).get("full_name") != repo:
        return None
    return str(head.get("ref")) if head.get("ref") else None


def commit_time(commit: dict[str, Any]) -> datetime:
    metadata = commit.get("commit") or {}
    for role in ("committer", "author"):
        value = (metadata.get(role) or {}).get("date")
        if value:
            return parse_time(str(value))
    raise ValueError("commit has no timestamp")


def infer_base(client: Any, branch: str, default: str, open_heads: set[str]) -> str:
    best, distance = default, None
    for parent in sorted(open_heads - {branch, default}):
        comparison = client.compare(parent, branch)
        ahead = int(comparison.get("ahead_by") or 0)
        behind = int(comparison.get("behind_by") or 0)
        if comparison.get("status") == "ahead" and ahead > 0 and behind == 0:
            if distance is None or ahead < distance:
                best, distance = parent, ahead
    return best


def safe_ref_text(value: str) -> str:
    """Render a ref as inert text in GitHub Markdown and titles."""
    value = "".join(character if ord(character) >= 32 else "-" for character in value)
    value = value.replace("#", "issue-").replace("@", "at-")
    return html.escape(value, quote=True)


def title_for(branch: str) -> str:
    prefix, _, rest = branch.partition("/")
    prefix = safe_ref_text(prefix)
    label = re.sub(r"[-_]+", " ", safe_ref_text(rest or prefix)).strip()
    title = f"{prefix}: {label}" if rest else f"draft: {label}"
    if len(title) <= MAX_PR_TITLE_LENGTH:
        return title
    return title[: MAX_PR_TITLE_LENGTH - 3].rstrip() + "..."


def body_for(c: Candidate) -> str:
    branch = safe_ref_text(c.branch)
    base = safe_ref_text(c.base)
    return f"""## Summary

Automatically opened as a Draft coordination PR for branch '{branch}'. This is not merge authorization.

## Evidence and verification

The steward ran trusted code from main and did not check out or execute the candidate branch.

- Observed head SHA at planning: {c.head_sha}
- Selected base: {base}
- Compare: {c.status} (ahead {c.ahead_by}, behind {c.behind_by})
- Draft: true

## Related work / ACE lineage (optional)

- Refs:
- Closes on merge (leave blank unless intended):
- ACE-Seed:

## Community Impact

The branch remains the workspace; this Draft PR becomes the public coordination, review, and CI surface.

## AI/tool provenance

Created by repository automation from GitHub metadata. No correctness or merge-readiness claim is made.

## Risks / limitations

- Generated title/body may need refinement.
- Closed or superseded branches are not reopened automatically.
- Evidence, frozen, hold, and scratch lanes are excluded by policy.
- PR creation with the repository GITHUB_TOKEN does not itself start downstream workflow runs; a later ordinary branch push or human review-state action provides the normal check surface.
"""


def discover(client: Any, policy: Policy) -> list[Candidate]:
    if not policy.enabled:
        return []
    branches = client.list_branches(policy.max_branch_pages)
    pulls = client.list_pulls(policy.max_pr_pages)
    history: set[str] = set()
    open_heads: set[str] = set()
    for pr in pulls:
        head = same_repo_head(pr, client.repo)
        if head:
            history.add(head)
            if pr.get("state") == "open":
                open_heads.add(head)

    if (
        policy.infer_stacked_base
        and len(open_heads) > policy.max_open_pr_heads_for_stack_inference
    ):
        raise RuntimeError(
            "open PR head count exceeds max_open_pr_heads_for_stack_inference; "
            "refusing unbounded stack inference"
        )

    untracked: list[tuple[str, str]] = []
    for item in branches:
        branch = str(item.get("name", ""))
        if not is_managed(branch, policy) or branch in history:
            continue
        sha = str((item.get("commit") or {}).get("sha") or "")
        if sha:
            untracked.append((branch, sha))

    if len(untracked) > policy.max_untracked_branches_per_run:
        raise RuntimeError(
            "untracked managed branch count exceeds max_untracked_branches_per_run; "
            "refusing an unbounded scan"
        )

    new_branches: list[tuple[datetime, str, str]] = []
    for branch, sha in untracked:
        observed = commit_time(client.get_commit(sha))
        if observed >= policy.not_before:
            new_branches.append((observed, branch, sha))

    ordered = sorted(new_branches, key=lambda row: (row[0], row[1]))
    ordered = ordered[: policy.max_candidate_evaluations_per_run]

    result: list[Candidate] = []
    for _, branch, sha in ordered:
        base = policy.default_base
        if policy.infer_stacked_base:
            base = infer_base(client, branch, base, open_heads)
        comparison = client.compare(base, branch)
        ahead = int(comparison.get("ahead_by") or 0)
        if ahead <= 0:
            continue
        result.append(
            Candidate(
                branch,
                sha,
                base,
                str(comparison.get("status") or "unknown"),
                ahead,
                int(comparison.get("behind_by") or 0),
            )
        )
    return result


def disabled_result(dry_run: bool) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "candidate_count": None,
        "planned": [],
        "created": [],
        "skipped": [],
        "dry_run": dry_run,
        "rate_limit_remaining": None,
        "blocked_reason": "policy_disabled",
        "merge_authorized": False,
    }


def blocked_result(remaining: int, threshold: int, dry_run: bool) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "candidate_count": None,
        "planned": [],
        "created": [],
        "skipped": [],
        "dry_run": dry_run,
        "rate_limit_remaining": remaining,
        "blocked_reason": (
            f"github_api_budget_low: remaining={remaining}, required={threshold}"
        ),
        "merge_authorized": False,
    }


def run(client: Any, policy: Policy, dry_run: bool = False) -> dict[str, Any]:
    if not policy.enabled:
        return disabled_result(dry_run)
    remaining = client.rate_limit_remaining()
    if remaining < policy.minimum_rate_limit_remaining:
        return blocked_result(remaining, policy.minimum_rate_limit_remaining, dry_run)

    candidates = discover(client, policy)
    planned: list[dict[str, Any]] = []
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for candidate in candidates[: policy.max_creations_per_run]:
        record = {
            "branch": candidate.branch,
            "base": candidate.base,
            "head_sha": candidate.head_sha,
            "ahead_by": candidate.ahead_by,
            "behind_by": candidate.behind_by,
        }
        planned.append(record)
        current_head = client.get_branch_head(candidate.branch)
        if current_head != candidate.head_sha:
            skipped.append(
                {
                    **record,
                    "reason": "head_moved",
                    "current_head_sha": current_head,
                }
            )
            continue
        if dry_run:
            continue
        try:
            pr = client.create_draft_pr(
                title=title_for(candidate.branch),
                head=candidate.branch,
                base=candidate.base,
                body=body_for(candidate),
            )
        except GitHubApiError as exc:
            detail = f"{exc.message} {exc.body}".lower()
            if exc.status == 422 and "pull request" in detail and "already exists" in detail:
                skipped.append({**record, "reason": "pr_already_exists"})
                continue
            if exc.status == 403:
                raise GitHubApiError(
                    403,
                    (
                        "Draft PR creation is forbidden for this token. The repository "
                        "must permit its GITHUB_TOKEN to create pull requests."
                    ),
                    exc.body,
                ) from exc
            raise
        number = pr.get("number")
        url = pr.get("html_url")
        if not isinstance(number, int) or number < 1:
            raise RuntimeError("created pull request response has no valid PR number")
        expected_url = f"https://github.com/{client.repo}/pull/{number}"
        if url != expected_url:
            raise RuntimeError("created pull request response has no canonical GitHub URL")
        created.append({**record, "number": number, "url": url})

    return {
        "schema_version": "0.1",
        "candidate_count": len(candidates),
        "planned": planned,
        "created": created,
        "skipped": skipped,
        "dry_run": dry_run,
        "rate_limit_remaining": remaining,
        "blocked_reason": None,
        "merge_authorized": False,
    }


discover_candidates = discover
run_steward = run


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_sha(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized if re.fullmatch(r"[0-9a-f]{40}", normalized) else None


def build_report(
    result: dict[str, Any],
    *,
    repo: str,
    policy_path: Path,
    generated_at: str | None = None,
    env: dict[str, str] | os._Environ[str] | None = None,
) -> dict[str, Any]:
    environment = os.environ if env is None else env
    policy_bytes = policy_path.read_bytes()
    blocked = result.get("blocked_reason")
    if blocked == "policy_disabled":
        status = "disabled"
    elif blocked:
        status = "blocked"
    else:
        status = "completed"

    return {
        "schema": REPORT_SCHEMA,
        "repository": repo,
        "generated_at": generated_at or _utc_now_text(),
        "status": status,
        "dry_run": bool(result.get("dry_run", False)),
        "policy": {
            "path": str(policy_path),
            "sha256": hashlib.sha256(policy_bytes).hexdigest(),
        },
        "provenance": {
            "workflow": environment.get("GITHUB_WORKFLOW"),
            "run_id": environment.get("GITHUB_RUN_ID"),
            "run_attempt": environment.get("GITHUB_RUN_ATTEMPT"),
            "trusted_head_sha": _optional_sha(environment.get("GITHUB_SHA")),
        },
        "authority": {
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
        },
        "candidate_count": result.get("candidate_count"),
        "rate_limit_remaining": result.get("rate_limit_remaining"),
        "blocked_reason": blocked,
        "summary": {
            "planned": len(result.get("planned", [])),
            "created": len(result.get("created", [])),
            "skipped": len(result.get("skipped", [])),
        },
        "planned": list(result.get("planned", [])),
        "created": list(result.get("created", [])),
        "skipped": list(result.get("skipped", [])),
    }


def render_report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _md_text(value: Any) -> str:
    return html.escape(str(value), quote=True).replace("|", "&#124;").replace("\n", " ")


def _md_code(value: Any) -> str:
    return f"<code>{_md_text(value)}</code>"


def render_report_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Auto Draft PR Steward Report",
        "",
        f"- Repository: {_md_code(report['repository'])}",
        f"- Status: **{_md_text(report['status'])}**",
        f"- Generated at: {_md_code(report['generated_at'])}",
        f"- Policy SHA-256: `{report['policy']['sha256']}`",
        f"- API remaining at start: `{report['rate_limit_remaining']}`",
        f"- Candidate count: `{report['candidate_count']}`",
        f"- Planned: **{summary['planned']}**",
        f"- Created: **{summary['created']}**",
        f"- Skipped: **{summary['skipped']}**",
        f"- Blocked reason: {_md_code(report['blocked_reason'] or 'none')}",
        "- Merge authorized: **false**",
        "",
        "This report is decision-support/evidence only. The steward may create bounded Draft PRs but cannot approve, promote, merge, enable auto-merge, delete branches, close issues, write repository contents, or change repository settings.",
        "",
    ]

    if report["planned"]:
        lines.extend(
            [
                "## Planned candidates",
                "",
                "| Branch | Base | Ahead | Behind | Head |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for item in report["planned"]:
            lines.append(
                f"| {_md_code(item['branch'])} | {_md_code(item['base'])} | "
                f"{item['ahead_by']} | {item['behind_by']} | `{item['head_sha']}` |"
            )
        lines.append("")

    if report["created"]:
        lines.extend(
            [
                "## Created Draft PRs",
                "",
                "| PR | Branch | Base | Head |",
                "| ---: | --- | --- | --- |",
            ]
        )
        for item in report["created"]:
            lines.append(
                f"| #{item['number']} | {_md_code(item['branch'])} | "
                f"{_md_code(item['base'])} | {_md_code(item['head_sha'])} |"
            )
        lines.append("")

    if report["skipped"]:
        lines.extend(
            [
                "## Skipped candidates",
                "",
                "| Branch | Base | Reason | Planned head | Current head |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in report["skipped"]:
            lines.append(
                f"| {_md_code(item['branch'])} | {_md_code(item['base'])} | "
                f"{_md_code(item['reason'])} | {_md_code(item['head_sha'])} | "
                f"{_md_code(item.get('current_head_sha', '-'))} |"
            )
        lines.append("")

    provenance = report["provenance"]
    lines.extend(
        [
            "## Provenance",
            "",
            f"- Workflow: {_md_code(provenance['workflow'] or 'local')}",
            f"- Run ID: {_md_code(provenance['run_id'] or 'n/a')}",
            f"- Run attempt: {_md_code(provenance['run_attempt'] or 'n/a')}",
            f"- Trusted workflow head: {_md_code(provenance['trusted_head_sha'] or 'n/a')}",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_output_paths(
    policy_path: Path,
    output_json: Path | None,
    output_md: Path | None,
    summary_file: Path | None,
) -> None:
    claimed: dict[str, str] = {}
    policy_real = os.path.realpath(policy_path)
    for label, path in (
        ("--output-json", output_json),
        ("--output-md", output_md),
        ("--summary-file", summary_file),
    ):
        if path is None:
            continue
        real = os.path.realpath(path)
        if real == policy_real:
            raise ValueError(f"{label} must not overwrite the policy file")
        previous = claimed.get(real)
        if previous:
            raise ValueError(f"{label} and {previous} must use different paths")
        claimed[real] = label


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_summary(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "## Auto Draft PR Steward",
        "",
        f"- candidates: {result['candidate_count']}",
        f"- planned: {len(result['planned'])}",
        f"- created: {len(result['created'])}",
        f"- skipped: {len(result.get('skipped', []))}",
        f"- API remaining at start: {result.get('rate_limit_remaining')}",
        f"- blocked: {result.get('blocked_reason') or 'false'}",
        "- merge authorized: false",
    ]
    lines += [
        f"- planned: {safe_ref_text(str(p['branch']))} -> "
        f"{safe_ref_text(str(p['base']))}"
        for p in result["planned"]
    ]
    lines += [
        f"- skipped: {safe_ref_text(str(p['branch']))} "
        f"({safe_ref_text(str(p['reason']))})"
        for p in result.get("skipped", [])
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary-file", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)
    try:
        _validate_output_paths(
            args.policy, args.output_json, args.output_md, args.summary_file
        )
    except ValueError as exc:
        print(f"auto-draft-pr steward configuration error: {exc}", file=sys.stderr)
        return 2
    if not args.token:
        print("GITHUB_TOKEN or --token is required", file=sys.stderr)
        return 2
    try:
        policy = load_policy(args.policy)
        result = run(
            GitHubClient(args.repo, args.token, args.api_url),
            policy,
            args.dry_run,
        )
        report = build_report(result, repo=args.repo, policy_path=args.policy)
        if args.output_json:
            _write_text(args.output_json, render_report_json(report))
        if args.output_md:
            _write_text(args.output_md, render_report_markdown(report))
        if args.summary_file:
            append_summary(args.summary_file, result)
    except (GitHubApiError, RuntimeError, ValueError, OSError) as exc:
        print(f"auto-draft-pr steward failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
