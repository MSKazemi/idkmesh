#!/usr/bin/env python3
"""Deterministic, dependency-free IDKMesh evolution scorer.

Consumes a small normalized event description (never a raw GitHub payload), updates
an in-repository state snapshot, appends an evidence record, and writes a Markdown
report. This is intentionally conservative: it observes and recommends; it does
not merge code or rewrite constitutional project files.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DIMENSIONS = (
    "goal_clarity",
    "product_quality",
    "community_health",
    "verification_strength",
    "maintainability",
    "exploration_capacity",
    "risk_debt",
)

# Small priors only. Evidence should eventually replace these hand-authored deltas.
EVENT_PRIORS: dict[str, dict[str, float]] = {
    "issues.opened": {"exploration_capacity": 0.010, "community_health": 0.005},
    "issues.closed": {"goal_clarity": 0.005, "maintainability": 0.005},
    "pull_request.opened": {"product_quality": 0.005, "community_health": 0.005},
    "pull_request.closed": {"maintainability": 0.003},
    "pull_request.merged": {
        "product_quality": 0.012,
        "community_health": 0.006,
        "verification_strength": 0.006,
        "risk_debt": 0.003,
    },
    "pull_request_review.submitted": {
        "verification_strength": 0.010,
        "community_health": 0.004,
    },
    "issue_comment.created": {"community_health": 0.003},
    "workflow_run.success": {"verification_strength": 0.006},
    "workflow_run.failure": {"verification_strength": -0.004, "risk_debt": 0.012},
    "schedule.audit": {"maintainability": 0.002},
    "workflow_dispatch.manual": {"exploration_capacity": 0.003},
}


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def fitness(state: dict[str, Any]) -> float:
    f = state["fitness"]
    w = state["weights"]
    positive = sum(w[d] * f[d] for d in DIMENSIONS if d != "risk_debt")
    risk = w["risk_debt"] * f["risk_debt"]
    return round(positive - risk, 6)


def normalize_event(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "kind": args.kind,
        "actor": args.actor or "unknown",
        "repository": args.repository or "unknown",
        "ref": args.ref or "",
        "run_id": args.run_id or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def recommend(kind: str, delta: float, state: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    if kind == "workflow_run.failure":
        recs.append("Investigate the failed workflow before increasing automation authority.")
    if state["fitness"]["risk_debt"] >= 0.65:
        recs.append("Prioritize risk/debt reduction over new feature fan-out.")
    if state["fitness"]["community_health"] < 0.45:
        recs.append("Create or improve a bounded newcomer task with explicit verification steps.")
    if delta <= 0:
        recs.append("Treat this event as evidence, not improvement; inspect why fitness did not increase.")
    if not recs:
        recs.append("Continue collecting evidence; do not infer causality from one event.")
    return recs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/evolution-state.json")
    parser.add_argument("--events", default="state/evolution-events.jsonl")
    parser.add_argument("--report", default="EVOLUTION_REPORT.md")
    parser.add_argument("--kind", required=True)
    parser.add_argument("--actor")
    parser.add_argument("--repository")
    parser.add_argument("--ref")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    before = fitness(state)
    event = normalize_event(args)
    priors = EVENT_PRIORS.get(args.kind, {})

    for dimension, change in priors.items():
        state["fitness"][dimension] = clamp(state["fitness"][dimension] + change)

    after = fitness(state)
    delta = round(after - before, 6)
    state["updated_at"] = event["timestamp"]
    state["signals"]["events_seen"] += 1
    state["signals"]["last_event"] = args.kind
    state["signals"]["last_actor"] = event["actor"]
    state["signals"]["last_score"] = after
    state["signals"]["last_delta"] = delta

    record = {
        "version": 1,
        **event,
        "prior_deltas": priors,
        "fitness_before": before,
        "fitness_after": after,
        "fitness_delta": delta,
        "evidence_quality": "prior-only",
    }

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with Path(args.events).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")

    recs = recommend(args.kind, delta, state)
    threshold = state["policy"]["minimum_meaningful_delta"]
    meaningful = delta > threshold
    rows = "\n".join(
        f"| {d.replace('_', ' ').title()} | {state['fitness'][d]:.3f} | {state['weights'][d]:.2f} |"
        for d in DIMENSIONS
    )
    bullets = "\n".join(f"- {r}" for r in recs)
    report = f"""# IDKMesh Evolution Report

Generated from normalized GitHub event evidence. Scores are experimental signals, not claims of causality.

## Latest event

- Kind: `{args.kind}`
- Actor: `{event['actor']}`
- Time: `{event['timestamp']}`
- Fitness before: `{before:.6f}`
- Fitness after: `{after:.6f}`
- Delta: `{delta:+.6f}`
- Meaningful improvement under current threshold (`>{threshold}`): **{str(meaningful).lower()}**
- Evidence quality: **prior-only**

## State

| Dimension | Value | Weight |
| --- | ---: | ---: |
{rows}

## Recommended next response

{bullets}

## Safety boundary

This scorer does not merge, approve, close, or rewrite constitutional files. Its outputs are inspectable evidence and recommendations. The priors in `scripts/evolution_score.py` must be challenged and calibrated against observed outcomes.
"""
    Path(args.report).write_text(report, encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
