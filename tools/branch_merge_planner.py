#!/usr/bin/env python3
"""Build a deterministic branch-to-main convergence plan from an IDKMesh branch audit.

This planner is intentionally non-authoritative. It converts the branch lifecycle
states produced by ``tools/branch_convergence_audit.py`` into ordered action lanes:

- PR integration review;
- stale-work extraction / clean-current-main replacement;
- evidence preservation;
- explicit draft/ambiguity holds; and
- branch retirement.

It never interprets a branch as directly mergeable and never emits merge approval.
A real PR must still satisfy the repository's conjunctive merge gate and an
external integration decision before it may reach ``main``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


class PlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class StatePolicy:
    lane: str
    next_action: str
    integration_candidate: bool = False
    retirement_candidate: bool = False


STATE_POLICY: dict[str, StatePolicy] = {
    "canonical": StatePolicy(
        "canonical",
        "keep canonical branch; never treat main as an integration source",
    ),
    "active-review-pr": StatePolicy(
        "pr-integration-review",
        "evaluate the PR hard gates; if every gate passes, integrate only through the exact-head PR and then recompute the plan",
        integration_candidate=True,
    ),
    "active-draft-pr": StatePolicy(
        "hold",
        "preserve branch and satisfy the draft PR's explicit blockers before integration review",
    ),
    "open-pr-head-mismatch": StatePolicy(
        "hold",
        "fail closed; refresh PR metadata and evidence against the current exact branch head",
    ),
    "ambiguous-open-prs": StatePolicy(
        "hold",
        "fail closed until one canonical open PR remains for the branch",
    ),
    "integrated-via-pr": StatePolicy(
        "retirement",
        "never merge again; retire only after exact-head and provenance/reference revalidation",
        retirement_candidate=True,
    ),
    "post-merge-branch-moved": StatePolicy(
        "extract-or-retire",
        "inspect only commits added after the merged PR head; open a bounded current-main PR for useful delta or retire the extra work",
    ),
    "closed-unmerged-no-unique-commits": StatePolicy(
        "retirement",
        "retire after exact-head/reference revalidation; no unique work remains to integrate",
        retirement_candidate=True,
    ),
    "closed-unmerged-evidence-branch": StatePolicy(
        "evidence-preservation",
        "preserve durable positive/negative evidence first; then retire or extract only still-useful artifacts onto current main",
    ),
    "closed-unmerged-unique-work": StatePolicy(
        "extract-or-retire",
        "review the unique delta; rebuild useful semantics on current main with fresh CI/evidence or retire as superseded",
    ),
    "orphan-no-unique-commits": StatePolicy(
        "retirement",
        "retire after confirming no workflow, document, or exact-SHA evidence depends on the branch ref",
        retirement_candidate=True,
    ),
    "orphan-clean-ahead": StatePolicy(
        "extract-or-retire",
        "inspect ownership/context and open a normal PR from the branch or a clean current-main replacement; never direct-merge the ref",
    ),
    "orphan-diverged": StatePolicy(
        "extract-or-retire",
        "build a clean replacement from current main and transplant only reviewed useful semantics; never merge stale ancestry wholesale",
    ),
    "unknown": StatePolicy(
        "hold",
        "insufficient evidence: hold until manually classified",
    ),
}


LANE_ORDER = {
    "pr-integration-review": 0,
    "extract-or-retire": 1,
    "evidence-preservation": 2,
    "hold": 3,
    "retirement": 4,
    "canonical": 5,
}


@dataclass(frozen=True)
class PlanItem:
    branch: str
    head_sha: str | None
    state: str
    lane: str
    next_action: str
    pull_requests: tuple[int, ...]
    ahead_by: int
    behind_by: int
    integration_candidate: bool
    retirement_candidate: bool
    direct_branch_merge_allowed: bool
    merge_authorized: bool
    exact_head_revalidation_required: bool


def _as_int(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{field} must be an integer") from exc
    if result < 0:
        raise PlanError(f"{field} must be non-negative")
    return result


def _validate_audit(audit: dict[str, Any]) -> None:
    if not isinstance(audit, dict):
        raise PlanError("audit input must be a JSON object")
    if not isinstance(audit.get("repository"), str) or not audit["repository"]:
        raise PlanError("audit repository is missing")
    if not isinstance(audit.get("default_branch"), str) or not audit["default_branch"]:
        raise PlanError("audit default_branch is missing")
    authority = audit.get("authority")
    if not isinstance(authority, dict):
        raise PlanError("audit authority block is missing")
    if authority.get("merge") is not False:
        raise PlanError("audit must not have merge authority")
    if authority.get("read_only") is not True:
        raise PlanError("audit must be read-only")
    branches = audit.get("branches")
    if not isinstance(branches, list):
        raise PlanError("audit branches must be a list")


def _plan_item(raw: dict[str, Any]) -> PlanItem:
    if not isinstance(raw, dict):
        raise PlanError("every audit branch entry must be an object")
    branch = raw.get("branch")
    state = raw.get("state")
    if not isinstance(branch, str) or not branch:
        raise PlanError("branch entry is missing branch name")
    if not isinstance(state, str) or state not in STATE_POLICY:
        raise PlanError(f"unsupported branch state for {branch}: {state!r}")
    if raw.get("direct_merge_allowed") is not False:
        raise PlanError(f"branch {branch} unexpectedly permits direct merge")

    prs_raw = raw.get("pull_requests", [])
    if not isinstance(prs_raw, list):
        raise PlanError(f"pull_requests for {branch} must be a list")
    try:
        pull_requests = tuple(sorted(int(value) for value in prs_raw))
    except (TypeError, ValueError) as exc:
        raise PlanError(f"pull_requests for {branch} must contain integers") from exc

    head_sha = raw.get("head_sha")
    if head_sha is not None and not isinstance(head_sha, str):
        raise PlanError(f"head_sha for {branch} must be a string or null")

    policy = STATE_POLICY[state]
    return PlanItem(
        branch=branch,
        head_sha=head_sha,
        state=state,
        lane=policy.lane,
        next_action=policy.next_action,
        pull_requests=pull_requests,
        ahead_by=_as_int(raw.get("ahead_by", 0), field=f"{branch}.ahead_by"),
        behind_by=_as_int(raw.get("behind_by", 0), field=f"{branch}.behind_by"),
        integration_candidate=policy.integration_candidate,
        retirement_candidate=policy.retirement_candidate,
        direct_branch_merge_allowed=False,
        merge_authorized=False,
        exact_head_revalidation_required=state != "canonical",
    )


def _sort_key(item: PlanItem) -> tuple[int, int, int, str]:
    # Within a lane, inspect the most divergent/stale branches first so conflict
    # debt is surfaced early. This ordering is advisory and never overrides gates.
    return (
        LANE_ORDER[item.lane],
        -item.behind_by,
        -item.ahead_by,
        item.branch,
    )


def build_plan(audit: dict[str, Any]) -> dict[str, Any]:
    _validate_audit(audit)
    items = [_plan_item(raw) for raw in audit["branches"]]
    items.sort(key=_sort_key)

    lanes = Counter(item.lane for item in items)
    states = Counter(item.state for item in items)
    integration = [item.branch for item in items if item.integration_candidate]
    retirement = [item.branch for item in items if item.retirement_candidate]
    preparation = [
        item.branch
        for item in items
        if item.lane in {"extract-or-retire", "evidence-preservation"}
    ]
    holds = [item.branch for item in items if item.lane == "hold"]

    return {
        "schema_version": "0.1",
        "repository": audit["repository"],
        "default_branch": audit["default_branch"],
        "source_audit_generated_at": audit.get("generated_at"),
        "source_audit_schema_version": audit.get("schema_version"),
        "default_branch_protected": bool(audit.get("default_branch_protected", False)),
        "authority": {
            "read_only": True,
            "direct_branch_merge": False,
            "merge_authorization": False,
            "approval": False,
            "delete_branch": False,
            "repository_settings": False,
        },
        "merge_gate": {
            "kind": "conjunctive_external_gate",
            "planner_evaluates_final_gate": False,
            "requirements": [
                "pr_open",
                "not_draft",
                "exact_expected_head",
                "not_superseded",
                "bounded_understood_diff",
                "dependencies_integrated_or_explicitly_independent",
                "required_checks_green_for_exact_head",
                "evidence_current_for_exact_head",
                "required_independent_review_satisfied",
                "authority_invariants_satisfied",
                "base_revalidated_after_previous_merge",
            ],
        },
        "transaction_rule": (
            "after every integration into main, discard previous eligibility and recompute the branch audit and merge plan"
        ),
        "summary": {
            "total_branches": len(items),
            "integration_review_candidates": len(integration),
            "preparation_or_evidence_queue": len(preparation),
            "holds": len(holds),
            "retirement_candidates": len(retirement),
            "states": dict(sorted(states.items())),
            "lanes": dict(sorted(lanes.items())),
        },
        "queues": {
            "integration_review": integration,
            "preparation_or_evidence": preparation,
            "holds": holds,
            "retirement": retirement,
        },
        "items": [asdict(item) for item in items],
    }


def _table(plan: dict[str, Any], lane: str, title: str) -> list[str]:
    rows = [item for item in plan["items"] if item["lane"] == lane]
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["None in this snapshot.", ""])
        return lines
    lines.extend(
        [
            "| Branch | State | Ahead | Behind | PRs | Next action |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for item in rows:
        prs = ", ".join(f"#{number}" for number in item["pull_requests"]) or "-"
        action = item["next_action"].replace("|", "\\|")
        lines.append(
            f"| `{item['branch']}` | `{item['state']}` | {item['ahead_by']} | {item['behind_by']} | {prs} | {action} |"
        )
    lines.append("")
    return lines


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# Branch Merge / Convergence Plan",
        "",
        f"- Repository: `{plan['repository']}`",
        f"- Default branch: `{plan['default_branch']}`",
        f"- Default branch protected: `{str(plan['default_branch_protected']).lower()}`",
        f"- Branches observed: **{summary['total_branches']}**",
        f"- PR integration-review candidates: **{summary['integration_review_candidates']}**",
        f"- Preparation/evidence queue: **{summary['preparation_or_evidence_queue']}**",
        f"- Holds: **{summary['holds']}**",
        f"- Retirement candidates: **{summary['retirement_candidates']}**",
        "- Direct branch merges authorized: **0**",
        "",
        "This is a read-only execution plan. `integration-review candidate` does not mean merge-ready; the exact-head PR must still pass every conjunctive merge gate and receive the required external integration decision.",
        "",
        "## Transaction rule",
        "",
        "After **every** accepted merge into `main`, discard the old eligibility snapshot, rerun the branch audit, rebuild this plan, and re-evaluate dependencies/evidence against the new base.",
        "",
        "## Conjunctive merge gate",
        "",
        "```text",
        "MergeEligible(p) =",
        "    p.open",
        "    AND NOT p.draft",
        "    AND p.head_is_exactly_expected",
        "    AND p.not_superseded",
        "    AND p.diff_is_bounded_and_understood",
        "    AND p.dependencies_are_integrated_or_explicitly_independent",
        "    AND p.required_checks_are_green_for_exact_head",
        "    AND p.evidence_is_current_for_exact_head",
        "    AND p.required_independent_review_is_satisfied",
        "    AND p.authority_invariants_are_satisfied",
        "    AND p.base_was_revalidated_after_previous_merge",
        "```",
        "",
        "No priority score can compensate for a false hard gate.",
        "",
    ]
    lines.extend(_table(plan, "pr-integration-review", "Lane A — PR integration review"))
    lines.extend(_table(plan, "extract-or-retire", "Lane B — Extract useful stale work or retire"))
    lines.extend(_table(plan, "evidence-preservation", "Lane C — Preserve evidence before retirement/extraction"))
    lines.extend(_table(plan, "hold", "Lane D — Explicit holds"))
    lines.extend(_table(plan, "retirement", "Lane E — Retirement candidates"))
    lines.extend(
        [
            "## Execution discipline",
            "",
            "1. Never bulk-merge stale refs to reduce branch count.",
            "2. Use a PR as the integration transaction; use its exact head SHA when executing the final merge.",
            "3. Integrate dependency roots before dependents; stacked PRs must be retargeted/revalidated when parents land.",
            "4. For stale unique branches, transplant only still-useful semantics onto current `main` and rerun evidence.",
            "5. Preserve failed/negative evidence before deleting evidence branches.",
            "6. Treat merged-PR source branches as cleanup, never as a second merge opportunity.",
            "7. Keep exact-SHA/frozen branches unchanged until their evidence gate is completed or deliberately invalidated and rerun.",
            "8. Recompute after every merge because `main` changed.",
            "",
        ]
    )
    return "\n".join(lines)


def self_test() -> None:
    audit = {
        "schema_version": "0.2",
        "repository": "example/repo",
        "default_branch": "main",
        "default_branch_protected": False,
        "generated_at": "2026-08-28T00:00:00Z",
        "authority": {
            "read_only": True,
            "merge": False,
            "delete_branch": False,
            "approve": False,
            "repository_settings": False,
        },
        "branches": [
            {
                "branch": "main",
                "head_sha": "a" * 40,
                "state": "canonical",
                "direct_merge_allowed": False,
                "ahead_by": 0,
                "behind_by": 0,
                "pull_requests": [],
            },
            {
                "branch": "feature/review",
                "head_sha": "b" * 40,
                "state": "active-review-pr",
                "direct_merge_allowed": False,
                "ahead_by": 2,
                "behind_by": 0,
                "pull_requests": [7],
            },
            {
                "branch": "feature/merged",
                "head_sha": "c" * 40,
                "state": "integrated-via-pr",
                "direct_merge_allowed": False,
                "ahead_by": 1,
                "behind_by": 3,
                "pull_requests": [4],
            },
            {
                "branch": "experiment/evidence",
                "head_sha": "d" * 40,
                "state": "closed-unmerged-evidence-branch",
                "direct_merge_allowed": False,
                "ahead_by": 1,
                "behind_by": 8,
                "pull_requests": [9],
            },
        ],
    }
    plan = build_plan(audit)
    assert plan["summary"]["integration_review_candidates"] == 1
    assert plan["queues"]["integration_review"] == ["feature/review"]
    assert plan["queues"]["retirement"] == ["feature/merged"]
    assert plan["authority"]["merge_authorization"] is False
    assert all(item["merge_authorized"] is False for item in plan["items"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self-test")

    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--input-json", required=True, type=Path)
    plan_parser.add_argument("--output-json", type=Path)
    plan_parser.add_argument("--output-md", type=Path)

    args = parser.parse_args(argv)
    if args.command == "self-test":
        self_test()
        print("branch merge planner self-test: PASS")
        return 0

    try:
        audit = json.loads(args.input_json.read_text(encoding="utf-8"))
        plan = build_plan(audit)
    except (OSError, json.JSONDecodeError, PlanError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(plan)
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
