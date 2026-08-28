#!/usr/bin/env python3
"""Read-only GitHub activity observatory for IDKMesh.

Collects public repository collaboration signals and emits a normalized snapshot,
health report, and bounded self-evolution opportunities. It never writes to GitHub.
All issue/comment/review text is treated as untrusted data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SCHEMA_VERSION = "github-observation-v0.1"
USER_AGENT = "idkmesh-github-observatory/0.1"
RISK_WEIGHT = {"low": 0.15, "medium": 0.50, "high": 1.00, "constitutional": 2.00}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def age_days(value: str | None, now: dt.datetime) -> float:
    parsed = parse_time(value)
    if parsed is None:
        return 0.0
    return max(0.0, (now - parsed).total_seconds() / 86400.0)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def reaction_total(obj: dict[str, Any]) -> int:
    reactions = obj.get("reactions") or {}
    return int(reactions.get("total_count") or 0)


def normalize_text_event(obj: dict[str, Any], kind: str, parent_number: int) -> dict[str, Any]:
    body = obj.get("body") or ""
    user = obj.get("user") or {}
    return {
        "kind": kind,
        "id": obj.get("id"),
        "parent_number": parent_number,
        "author": user.get("login"),
        "author_association": obj.get("author_association"),
        "created_at": obj.get("created_at"),
        "updated_at": obj.get("updated_at"),
        "url": obj.get("html_url") or obj.get("url"),
        "reactions": reaction_total(obj),
        "body": body,
        "body_sha256": sha256_text(body),
        "untrusted_text": True,
    }


class GitHubClient:
    def __init__(self, repo: str, token: str | None, api_url: str = "https://api.github.com") -> None:
        self.repo = repo
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.unavailable: dict[str, str] = {}

    def _request(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
        url = f"{self.api_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"GitHub API {exc.code} for {path}: {message}") from exc

    def get(self, path: str, params: dict[str, Any] | None = None, *, optional: bool = False) -> Any:
        try:
            payload, _ = self._request(path, params)
            return payload
        except RuntimeError as exc:
            if optional:
                self.unavailable[path] = str(exc)
                return None
            raise

    def get_all(self, path: str, params: dict[str, Any] | None = None, *, max_pages: int = 10, optional: bool = False) -> list[Any]:
        base = dict(params or {})
        base["per_page"] = 100
        result: list[Any] = []
        for page in range(1, max_pages + 1):
            base["page"] = page
            payload = self.get(path, base, optional=optional)
            if payload is None:
                return result
            if not isinstance(payload, list):
                raise RuntimeError(f"Expected list from {path}, got {type(payload).__name__}")
            result.extend(payload)
            if len(payload) < 100:
                break
        return result


def review_capacity(open_prs: int, pending_review_prs: int, k: float = 8.0, tau: float = 2.0) -> float:
    load = open_prs + 0.75 * pending_review_prs
    return 1.0 / (1.0 + math.exp((load - k) / tau))


def opportunity_score(*, benefit: float, confidence: float, novelty: float, capacity: float, cost: float, risk: str) -> float:
    risk_cost = RISK_WEIGHT[risk]
    return (benefit * confidence * novelty * capacity) / (1.0 + cost + 2.0 * risk_cost)


def autonomy_ceiling(default_branch_protected: bool, ruleset_count: int) -> int:
    """Return the maximum autonomy level justified by external GitHub guards."""
    if not default_branch_protected or ruleset_count == 0:
        return 1
    return 2


def build_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    now = parse_time(snapshot["generated_at"]) or utcnow()
    metrics = snapshot["metrics"]
    protection = snapshot["repository"]["protection"]
    capacity = metrics["review_capacity"]
    candidates: list[dict[str, Any]] = []

    def add(candidate_id: str, title: str, reason: str, *, rule: str, risk: str, benefit: float, confidence: float, novelty: float = 1.0, cost: float = 0.5, evidence: list[str] | None = None, actuator: str = "recommend") -> None:
        candidates.append({
            "id": candidate_id,
            "rule": rule,
            "title": title,
            "reason": reason,
            "risk": risk,
            "actuator": actuator,
            "evidence": evidence or [],
            "score": round(opportunity_score(benefit=benefit, confidence=confidence, novelty=novelty, capacity=capacity, cost=cost, risk=risk), 6),
        })

    if not protection["default_branch_protected"] or protection["ruleset_count"] == 0:
        add(
            "guard-default-branch",
            "Define external merge guards before increasing autonomy",
            "The default branch is not protected by a branch rule/ruleset. Self-evolution should remain observe/recommend only until independent merge guards exist.",
            rule="GuardAutonomy",
            risk="constitutional",
            benefit=5.0,
            confidence=1.0,
            cost=1.0,
            evidence=["repository.protection"],
            actuator="manual-admin-change",
        )

    for item in snapshot["collaboration"]["items"]:
        if item["is_pull_request"]:
            if item["state"] == "open" and item["review_count"] == 0 and age_days(item["created_at"], now) >= 7:
                add(
                    f"request-review-pr-{item['number']}",
                    f"Review PR #{item['number']}: {item['title']}",
                    "Open pull request has aged without a submitted review.",
                    rule="RequestIndependentReview",
                    risk="low",
                    benefit=2.2,
                    confidence=0.95,
                    cost=0.2,
                    evidence=[item["url"]],
                    actuator="recommend-review",
                )
        else:
            if item["state"] == "open" and item["comment_count"] >= 3 and item["distinct_comment_authors"] >= 2:
                add(
                    f"synthesize-issue-{item['number']}",
                    f"Synthesize evidence in issue #{item['number']}",
                    "The issue has multiple independent discussion participants; summarize claims, evidence, disagreements, and unresolved questions before generating more work.",
                    rule="SynthesizeDiscussion",
                    risk="low",
                    benefit=2.5,
                    confidence=min(1.0, 0.55 + 0.1 * item["distinct_comment_authors"]),
                    novelty=1.0 / math.sqrt(1.0 + item["comment_count"] / 5.0),
                    cost=0.4,
                    evidence=[item["url"]],
                    actuator="recommend-summary",
                )
            if item["state"] == "open" and item["comment_count"] == 0 and age_days(item["created_at"], now) >= 30:
                add(
                    f"triage-stale-issue-{item['number']}",
                    f"Triage stale issue #{item['number']}",
                    "Open issue has no discussion for at least 30 days. Ask whether it needs clarification, decomposition, dependency links, or closure; do not auto-close.",
                    rule="TriageStaleWork",
                    risk="low",
                    benefit=1.2,
                    confidence=0.8,
                    cost=0.2,
                    evidence=[item["url"]],
                    actuator="recommend-triage",
                )

    failed = metrics.get("failed_workflow_runs", 0)
    if failed:
        add(
            "investigate-workflow-failures",
            "Investigate recent failed workflow runs",
            f"Observed {failed} failed/cancelled workflow runs in the sampled window.",
            rule="RepairVerification",
            risk="medium",
            benefit=3.0,
            confidence=1.0,
            cost=0.8,
            evidence=["automation.workflow_runs"],
            actuator="recommend-issue",
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def collect(repo: str, token: str | None, max_items: int) -> dict[str, Any]:
    client = GitHubClient(repo, token)
    now = utcnow()
    base = f"/repos/{repo}"
    repo_data = client.get(base)
    default_branch = repo_data["default_branch"]
    branch = client.get(f"{base}/branches/{urllib.parse.quote(default_branch, safe='')}")
    rulesets = client.get_all(f"{base}/rulesets", optional=True)

    raw_items = client.get_all(f"{base}/issues", {"state": "all", "sort": "updated", "direction": "desc"}, max_pages=max(1, math.ceil(max_items / 100)))[:max_items]
    items: list[dict[str, Any]] = []
    all_comments: list[dict[str, Any]] = []
    all_reviews: list[dict[str, Any]] = []
    all_review_comments: list[dict[str, Any]] = []

    for raw in raw_items:
        number = int(raw["number"])
        is_pr = "pull_request" in raw
        issue_comments = []
        if int(raw.get("comments") or 0) > 0:
            issue_comments = client.get_all(f"{base}/issues/{number}/comments", max_pages=5, optional=True)
            all_comments.extend(normalize_text_event(comment, "issue_comment", number) for comment in issue_comments)

        reviews: list[dict[str, Any]] = []
        review_comments: list[dict[str, Any]] = []
        if is_pr:
            reviews = client.get_all(f"{base}/pulls/{number}/reviews", max_pages=5, optional=True)
            review_comments = client.get_all(f"{base}/pulls/{number}/comments", max_pages=5, optional=True)
            for review in reviews:
                normalized = normalize_text_event(review, "pull_request_review", number)
                normalized["state"] = review.get("state")
                all_reviews.append(normalized)
            all_review_comments.extend(normalize_text_event(comment, "pull_request_review_comment", number) for comment in review_comments)

        labels = [label.get("name") for label in (raw.get("labels") or []) if isinstance(label, dict)]
        comment_authors = {((comment.get("user") or {}).get("login")) for comment in issue_comments}
        comment_authors.discard(None)
        items.append({
            "number": number,
            "title": raw.get("title"),
            "state": raw.get("state"),
            "is_pull_request": is_pr,
            "url": raw.get("html_url"),
            "author": (raw.get("user") or {}).get("login"),
            "author_association": raw.get("author_association"),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
            "closed_at": raw.get("closed_at"),
            "labels": labels,
            "assignees": [(a or {}).get("login") for a in (raw.get("assignees") or [])],
            "milestone": (raw.get("milestone") or {}).get("title") if raw.get("milestone") else None,
            "comment_count": len(issue_comments),
            "distinct_comment_authors": len(comment_authors),
            "reaction_count": reaction_total(raw),
            "review_count": len(reviews),
            "review_comment_count": len(review_comments),
            "body_sha256": sha256_text(raw.get("body") or ""),
            "body": raw.get("body") or "",
            "untrusted_text": True,
        })

    workflows_payload = client.get(f"{base}/actions/workflows", {"per_page": 100}, optional=True) or {}
    workflows = workflows_payload.get("workflows", []) if isinstance(workflows_payload, dict) else []
    runs_payload = client.get(f"{base}/actions/runs", {"per_page": 100}, optional=True) or {}
    workflow_runs = runs_payload.get("workflow_runs", []) if isinstance(runs_payload, dict) else []
    releases = client.get_all(f"{base}/releases", max_pages=3, optional=True)
    branches = client.get_all(f"{base}/branches", max_pages=3, optional=True)
    contributors = client.get_all(f"{base}/contributors", max_pages=3, optional=True)

    security: dict[str, Any] = {}
    for key, path in {
        "code_scanning_alerts": f"{base}/code-scanning/alerts",
        "dependabot_alerts": f"{base}/dependabot/alerts",
        "secret_scanning_alerts": f"{base}/secret-scanning/alerts",
    }.items():
        alerts = client.get_all(path, {"state": "open"}, max_pages=3, optional=True)
        security[key] = {"count": len(alerts), "sample": alerts[:20], "available": path not in client.unavailable}

    open_issues = [i for i in items if not i["is_pull_request"] and i["state"] == "open"]
    open_prs = [i for i in items if i["is_pull_request"] and i["state"] == "open"]
    pending_review_prs = [i for i in open_prs if i["review_count"] == 0]
    failed_runs = [r for r in workflow_runs if r.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required"}]
    completed_runs = [r for r in workflow_runs if r.get("status") == "completed"]
    successful_runs = [r for r in completed_runs if r.get("conclusion") == "success"]

    protected = bool(branch.get("protected"))
    protection = {
        "default_branch": default_branch,
        "default_branch_protected": protected,
        "ruleset_count": len(rulesets),
        "autonomy_ceiling": autonomy_ceiling(protected, len(rulesets)),
    }

    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "repository": {
            "full_name": repo,
            "visibility": repo_data.get("visibility"),
            "default_branch": default_branch,
            "language": repo_data.get("language"),
            "stars": repo_data.get("stargazers_count"),
            "forks": repo_data.get("forks_count"),
            "watchers": repo_data.get("subscribers_count"),
            "has_issues": repo_data.get("has_issues"),
            "has_projects": repo_data.get("has_projects"),
            "has_discussions": repo_data.get("has_discussions"),
            "has_pages": repo_data.get("has_pages"),
            "has_wiki": repo_data.get("has_wiki"),
            "protection": protection,
        },
        "collaboration": {
            "items": items,
            "issue_comments": all_comments,
            "pull_request_reviews": all_reviews,
            "pull_request_review_comments": all_review_comments,
        },
        "automation": {
            "workflows": [{"id": w.get("id"), "name": w.get("name"), "state": w.get("state"), "path": w.get("path")} for w in workflows],
            "workflow_runs": [{"id": r.get("id"), "name": r.get("name"), "event": r.get("event"), "status": r.get("status"), "conclusion": r.get("conclusion"), "created_at": r.get("created_at"), "updated_at": r.get("updated_at"), "html_url": r.get("html_url")} for r in workflow_runs],
        },
        "distribution": {
            "releases": [{"id": r.get("id"), "tag": r.get("tag_name"), "published_at": r.get("published_at"), "url": r.get("html_url")} for r in releases],
            "branches": [{"name": b.get("name"), "protected": b.get("protected")} for b in branches],
            "contributors": [{"login": c.get("login"), "contributions": c.get("contributions")} for c in contributors],
        },
        "security": security,
        "collection": {
            "max_items": max_items,
            "sampled_item_count": len(items),
            "text_is_untrusted": True,
            "unavailable_endpoints": client.unavailable,
        },
    }
    snapshot["metrics"] = {
        "open_issues": len(open_issues),
        "open_prs": len(open_prs),
        "pending_review_prs": len(pending_review_prs),
        "issue_comments": len(all_comments),
        "pull_request_reviews": len(all_reviews),
        "pull_request_review_comments": len(all_review_comments),
        "workflow_count": len(workflows),
        "sampled_workflow_runs": len(workflow_runs),
        "failed_workflow_runs": len(failed_runs),
        "workflow_success_rate": round(len(successful_runs) / len(completed_runs), 4) if completed_runs else None,
        "review_capacity": round(review_capacity(len(open_prs), len(pending_review_prs)), 6),
        "open_security_alerts": sum(int(value["count"]) for value in security.values() if value.get("available")),
    }
    snapshot["evolution_candidates"] = build_candidates(snapshot)
    return snapshot


def render_report(snapshot: dict[str, Any]) -> str:
    repo = snapshot["repository"]
    metrics = snapshot["metrics"]
    protection = repo["protection"]
    lines = [
        "# GitHub Reflex Observatory",
        "",
        f"Generated: `{snapshot['generated_at']}`",
        f"Repository: `{repo['full_name']}`",
        "",
        "## Safety posture",
        "",
        f"- Default branch: `{protection['default_branch']}`",
        f"- Default branch protected: **{protection['default_branch_protected']}**",
        f"- Repository rulesets: **{protection['ruleset_count']}**",
        f"- Maximum recommended autonomy level: **{protection['autonomy_ceiling']}** (0 observe, 1 recommend, 2 propose PR, 3 deterministic auto-merge)",
        "",
        "## Collaboration sensors",
        "",
        f"- Open issues in sample: **{metrics['open_issues']}**",
        f"- Open PRs in sample: **{metrics['open_prs']}**",
        f"- PRs with no submitted review: **{metrics['pending_review_prs']}**",
        f"- Collected issue/PR conversation comments: **{metrics['issue_comments']}**",
        f"- Collected PR reviews: **{metrics['pull_request_reviews']}**",
        f"- Collected inline review comments: **{metrics['pull_request_review_comments']}**",
        "",
        "Comments, review text, issue bodies, and PR bodies are preserved as **untrusted evidence**, never executable instructions and never correctness votes.",
        "",
        "## Verification / automation sensors",
        "",
        f"- Workflows: **{metrics['workflow_count']}**",
        f"- Sampled workflow runs: **{metrics['sampled_workflow_runs']}**",
        f"- Failed/cancelled sampled runs: **{metrics['failed_workflow_runs']}**",
        f"- Workflow success rate: **{metrics['workflow_success_rate']}**",
        f"- Review-capacity multiplier: **{metrics['review_capacity']}**",
        "",
        "## Ranked bounded evolution opportunities",
        "",
        "| Score | Risk | Rule | Opportunity | Actuator |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for candidate in snapshot["evolution_candidates"][:20]:
        lines.append(f"| {candidate['score']:.4f} | {candidate['risk']} | `{candidate['rule']}` | {candidate['title']} | `{candidate['actuator']}` |")
    if not snapshot["evolution_candidates"]:
        lines.append("| 0 | - | - | No deterministic opportunity detected | observe |")
    lines += [
        "",
        "## Collection limitations",
        "",
        f"- Issue/PR sample cap: `{snapshot['collection']['max_items']}`",
        f"- Items sampled: `{snapshot['collection']['sampled_item_count']}`",
        "- Security endpoints are best-effort and may be unavailable to the workflow token.",
        "- GitHub Discussions, Projects v2 fields, merge queues, deployments/environments, and external webhooks are mapped in the capability document but are not all collected by P0.",
        "- This workflow is read-only. It does not label, close, merge, push, or create repository objects.",
        "",
    ]
    unavailable = snapshot["collection"]["unavailable_endpoints"]
    if unavailable:
        lines.append("### Unavailable endpoints")
        lines.append("")
        for path in sorted(unavailable):
            lines.append(f"- `{path}`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: GITHUB_REPOSITORY)")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token (default: GITHUB_TOKEN)")
    parser.add_argument("--out-dir", default="artifacts/github-observatory")
    parser.add_argument("--max-items", type=int, default=300)
    args = parser.parse_args(argv)
    if not args.repo or "/" not in args.repo:
        parser.error("--repo owner/repo is required")

    snapshot = collect(args.repo, args.token, max(1, args.max_items))
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "github-observation.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "github-observatory.md").write_text(render_report(snapshot), encoding="utf-8")
    print(render_report(snapshot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
