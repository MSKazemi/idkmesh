#!/usr/bin/env python3
"""Deterministically classify GitHub issues into model-capability and authority lanes.

The router is intentionally provider-neutral. It chooses a capability tier first;
provider/model selection happens later from a dated catalog. Repository authority
is a separate axis so an issue can require human evidence even when an LLM could
technically produce text or code related to it.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}
TIER_LABELS = {
    "T0": "model:t0-deterministic",
    "T1": "model:t1-small",
    "T2": "model:t2-standard",
    "T3": "model:t3-strong",
    "T4": "model:t4-peak",
    "NONE": "model:none",
}
AUTHORITY_LABELS = {
    "agent": "authority:agent-candidate",
    "human_required": "authority:human-required",
    "human_gate_then_agent": "authority:human-gate",
    "deterministic": "authority:deterministic",
}

PATH_RE = re.compile(r"`([^`]+(?:/[^`]+|\.(?:py|yml|yaml|json|md|toml|ini)))`")
ISSUE_REF_RE = re.compile(r"(?:#|PR\s*#?)\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Route:
    issue_number: int | None
    tier: str | None
    authority: str
    score: int
    confidence: str
    reasons: list[str]
    recommended_lane: str
    labels: list[str]
    source: str


def _contains_any(text: str, phrases: Iterable[str]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for phrase in phrases:
        needle = phrase.lower()
        for match in re.finditer(re.escape(needle), lowered):
            clause_start = max(
                lowered.rfind(".", 0, match.start()),
                lowered.rfind(";", 0, match.start()),
                lowered.rfind("\n", 0, match.start()),
            )
            prefix = lowered[clause_start + 1 : match.start()]
            # Do not escalate on explicit negative-scope statements such as
            # "no schema changes" or "do not change workflows".
            if re.search(r"\b(?:no|not|never|without|do not|must not|avoid)\b.{0,64}$", prefix):
                continue
            hits.append(phrase)
            break
    return hits


def _max_tier(left: str, right: str) -> str:
    return left if TIER_ORDER[left] >= TIER_ORDER[right] else right


def _score_to_tier(score: int) -> str:
    if score <= 2:
        return "T1"
    if score <= 5:
        return "T2"
    if score <= 8:
        return "T3"
    return "T4"


def _jules_queue_label(policy: dict[str, Any]) -> str:
    """Return the queue label from the provider policy, never a code literal."""
    value = (
        policy.get("provider_examples", {})
        .get("jules", {})
        .get("queue_label")
    )
    if not value:
        raise ValueError("routing policy is missing provider_examples.jules.queue_label")
    return str(value)


def _jules_veto_hits(
    issue_labels: Iterable[str],
    dispatch_policy: dict[str, Any] | None,
) -> list[str]:
    """Return dispatcher hard-veto labels already present on one issue."""
    if dispatch_policy is None:
        return []
    blocked = dispatch_policy.get("blocked_labels")
    if not isinstance(blocked, list):
        raise ValueError("dispatch policy blocked_labels must be a list")
    current = {str(label).casefold() for label in issue_labels}
    return sorted(
        str(label)
        for label in blocked
        if str(label).casefold() in current
    )


def _recommended_lane(tier: str | None, authority: str, text: str) -> str:
    if authority == "human_required":
        return "human"
    if authority == "deterministic":
        return "deterministic-ci"
    if authority == "human_gate_then_agent":
        return f"human-gate-then-{(tier or 'T4').lower()}"
    if tier in {"T1", "T2"} and any(
        token in text.lower() for token in ("test", "tool", "bug", "docs", "documentation", "generator")
    ):
        return "jules-or-equivalent"
    if tier == "T4":
        return "peak-model-plus-independent-reviewer"
    if tier == "T3":
        return "strong-coding-agent"
    return "small-or-standard-coding-agent"


def classify_issue(
    issue: dict[str, Any],
    policy: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    dispatch_policy: dict[str, Any] | None = None,
) -> Route:
    number_raw = issue.get("number", issue.get("issue_number"))
    number = int(number_raw) if number_raw not in (None, "") else None
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    labels_raw = issue.get("labels") or []
    labels: list[str] = []
    for label in labels_raw:
        if isinstance(label, str):
            labels.append(label)
        elif isinstance(label, dict) and label.get("name"):
            labels.append(str(label["name"]))
    text = f"{title}\n{body}\n{' '.join(labels)}"
    jules_veto_hits = _jules_veto_hits(labels, dispatch_policy)

    override = None
    if overrides and number is not None:
        override = (overrides.get("issues") or {}).get(str(number))
    if override:
        tier = override.get("tier")
        authority = override["authority"]
        reasons = [f"explicit current-repository route: {override['reason']}"]
        route_labels = [AUTHORITY_LABELS[authority]]
        route_labels.append(TIER_LABELS[tier] if tier else TIER_LABELS["NONE"])
        if override.get("jules_eligible"):
            if jules_veto_hits:
                reasons.append(
                    "Jules hard veto labels: " + ", ".join(jules_veto_hits)
                )
            else:
                route_labels.append(_jules_queue_label(policy))
        lane = override.get("recommended_lane") or _recommended_lane(tier, authority, text)
        return Route(number, tier, authority, 0, "high", reasons, lane, route_labels, "override")

    phrases = policy["phrases"]
    human_hits = _contains_any(text, phrases["human_required"])
    deterministic_hits = _contains_any(text, phrases["deterministic"])

    # Human evidence/review is an authority rule, not a measure of model skill.
    if human_hits:
        tier = None
        authority = "human_required"
        reasons = [f"human-evidence signal: {', '.join(human_hits[:3])}"]
        return Route(
            number,
            tier,
            authority,
            0,
            "high",
            reasons,
            "human",
            [TIER_LABELS["NONE"], AUTHORITY_LABELS[authority]],
            "rules",
        )

    if deterministic_hits:
        authority = "deterministic"
        return Route(
            number,
            "T0",
            authority,
            0,
            "high",
            [f"deterministic/workflow-maintained signal: {', '.join(deterministic_hits[:3])}"],
            "deterministic-ci",
            [TIER_LABELS["T0"], AUTHORITY_LABELS[authority]],
            "rules",
        )

    score = 0
    reasons: list[str] = []
    floor = "T1"

    for tier_name in ("T4", "T3", "T2"):
        hits = _contains_any(text, phrases[tier_name])
        if hits:
            floor = _max_tier(floor, tier_name)
            reasons.append(f"{tier_name} floor signals: {', '.join(hits[:4])}")

    length = len(body)
    if length >= 7000:
        score += 2
        reasons.append("large issue specification")
    elif length >= 2500:
        score += 1
        reasons.append("moderate issue specification")

    checklist_count = body.count("- [ ]") + body.count("- [x]") + body.count("- [X]")
    if checklist_count >= 16:
        score += 2
        reasons.append("large acceptance/dependency checklist")
    elif checklist_count >= 6:
        score += 1
        reasons.append("multi-step acceptance/dependency checklist")

    paths = set(PATH_RE.findall(text))
    if len(paths) >= 8:
        score += 2
        reasons.append("many explicit repository surfaces")
    elif len(paths) >= 3:
        score += 1
        reasons.append("multiple explicit repository surfaces")

    refs = ISSUE_REF_RE.findall(text)
    if len(refs) >= 8:
        score += 2
        reasons.append("high dependency/reference coupling")
    elif len(refs) >= 3:
        score += 1
        reasons.append("cross-issue/PR coupling")

    section_count = body.count("\n## ")
    if section_count >= 8:
        score += 2
        reasons.append("broad multi-section scope")
    elif section_count >= 4:
        score += 1
        reasons.append("multi-section scope")

    high_reasoning_hits = _contains_any(text, phrases["reasoning_heavy"])
    if high_reasoning_hits:
        score += 3
        reasons.append(f"reasoning-heavy signals: {', '.join(high_reasoning_hits[:3])}")

    sensitive_hits = _contains_any(text, phrases["sensitive"])
    if sensitive_hits:
        score += 3
        floor = _max_tier(floor, "T3")
        reasons.append(f"high-impact/sensitive signals: {', '.join(sensitive_hits[:3])}")

    if "good first issue" in title.lower() and not sensitive_hits:
        score = max(0, score - 2)
        reasons.append("explicitly bounded good-first-issue scope")

    tier = _max_tier(floor, _score_to_tier(score))
    authority = "agent"
    confidence = "medium" if not reasons else "high"
    lane = _recommended_lane(tier, authority, text)
    route_labels = [TIER_LABELS[tier], AUTHORITY_LABELS[authority]]
    if tier in {"T1", "T2"} and lane == "jules-or-equivalent":
        if jules_veto_hits:
            reasons.append(
                "Jules hard veto labels: " + ", ".join(jules_veto_hits)
            )
        else:
            route_labels.append(_jules_queue_label(policy))

    return Route(number, tier, authority, score, confidence, reasons or ["default bounded issue"], lane, route_labels, "rules")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def issue_from_event(path: str | Path) -> dict[str, Any]:
    event = load_json(path)
    issue = dict(event.get("issue") or {})
    if "number" not in issue and event.get("issue", {}).get("number") is None:
        issue["number"] = event.get("number")
    return issue


def _current_label_names(issue: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for label in issue.get("labels") or []:
        if isinstance(label, str):
            names.append(label)
        elif isinstance(label, dict) and label.get("name"):
            names.append(str(label["name"]))
    return sorted(set(names))


def _route_dict(route: Route, issue: dict[str, Any]) -> dict[str, Any]:
    data = asdict(route)
    data["model_label"] = TIER_LABELS[route.tier] if route.tier else TIER_LABELS["NONE"]
    data["authority_label"] = AUTHORITY_LABELS[route.authority]
    data["current_labels"] = _current_label_names(issue)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="config/llm-routing-policy.json")
    parser.add_argument(
        "--dispatch-policy",
        default="config/jules-dispatch.json",
        help="Jules dispatcher policy used for hard-veto queue suppression",
    )
    parser.add_argument("--overrides", default="config/issue-model-routing-overrides.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--event", help="GitHub event JSON containing an issue")
    source.add_argument("--issues", help="JSON array from `gh issue list --json ...`")
    source.add_argument("--issue-json", help="single issue JSON file")
    args = parser.parse_args()

    policy = load_json(args.policy)
    dispatch_policy = load_json(args.dispatch_policy)
    overrides = load_json(args.overrides) if Path(args.overrides).exists() else None

    if args.event:
        issue = issue_from_event(args.event)
        route = classify_issue(issue, policy, overrides, dispatch_policy)
        print(json.dumps(_route_dict(route, issue), sort_keys=True))
        return 0
    if args.issue_json:
        issue = load_json(args.issue_json)
        route = classify_issue(issue, policy, overrides, dispatch_policy)
        print(json.dumps(_route_dict(route, issue), sort_keys=True))
        return 0

    issues = load_json(args.issues)
    if not isinstance(issues, list):
        raise SystemExit("--issues must point to a JSON array")
    routes = [
        _route_dict(
            classify_issue(issue, policy, overrides, dispatch_policy),
            issue,
        )
        for issue in issues
    ]
    print(json.dumps({"routes": routes}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
