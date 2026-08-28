#!/usr/bin/env python3
"""Evidence-aware, dependency-free IDKMesh evolution observer.

This scorer is deliberately non-authoritative. It turns normalized GitHub events
into soft Bayesian evidence, measures diversity and homeostatic potential, writes
an append-only bounded event ledger, and emits a human-readable report.

The checked-in state is only a seed. GitHub Actions may restore the most recent
trusted-main checkpoint artifact before invoking this script; the script itself
never writes to GitHub, approves a change, or merges code.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evolution_math import (
    beta_lower_confidence,
    beta_mean,
    beta_update,
    beta_variance,
    clamp01,
    homeostatic_potential,
    lyapunov_accept,
    normalized_entropy,
)

DIMENSIONS = (
    "goal_clarity",
    "product_quality",
    "community_health",
    "verification_strength",
    "maintainability",
    "exploration_capacity",
    "risk_debt",
)


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def migrate_state(state: dict[str, Any], math_policy: dict[str, Any]) -> dict[str, Any]:
    """Migrate the old additive v1 state into a Bayesian v2 representation."""
    state.setdefault("fitness", {})
    if state.get("version", 1) < 2 or "beliefs" not in state:
        concentration = 8.0
        beliefs: dict[str, dict[str, float]] = {}
        for dimension in DIMENSIONS:
            mean = clamp01(float(state["fitness"].get(dimension, 0.5)))
            # Tiny offsets keep both Beta parameters strictly positive while
            # preserving the old mean to numerical precision.
            beliefs[dimension] = {
                "alpha": max(1e-6, mean * concentration),
                "beta": max(1e-6, (1.0 - mean) * concentration),
            }
        state["beliefs"] = beliefs
        state["version"] = 2

    fresh_alpha = float(math_policy["bayesian"]["fresh_alpha"])
    fresh_beta = float(math_policy["bayesian"]["fresh_beta"])
    for dimension in DIMENSIONS:
        state["beliefs"].setdefault(dimension, {"alpha": fresh_alpha, "beta": fresh_beta})
        state["fitness"][dimension] = beta_mean(
            float(state["beliefs"][dimension]["alpha"]),
            float(state["beliefs"][dimension]["beta"]),
        )

    state.setdefault("weights", {dimension: 1.0 for dimension in DIMENSIONS})
    state.setdefault("activity_counts", {"event_kinds": {}, "actors": {}})
    state["activity_counts"].setdefault("event_kinds", {})
    state["activity_counts"].setdefault("actors", {})
    state.setdefault("signals", {})
    state["signals"].setdefault("events_seen", 0)
    state["signals"].setdefault("event_entropy", 0.0)
    state["signals"].setdefault("actor_entropy", 0.0)
    state["signals"].setdefault("checkpoint_source", "repository-seed")
    state.setdefault("policy", {})
    state["policy"].setdefault("minimum_meaningful_delta", 0.01)
    state["policy"].setdefault("max_event_log_entries", 1000)
    state["policy"].setdefault("autonomous_merge", False)
    state["policy"].setdefault("constitutional_changes_require_review", True)
    return state


def fitness(state: dict[str, Any]) -> float:
    f = state["fitness"]
    w = state["weights"]
    positive = sum(float(w[d]) * float(f[d]) for d in DIMENSIONS if d != "risk_debt")
    risk = float(w["risk_debt"]) * float(f["risk_debt"])
    return round(positive - risk, 6)


def potential(state: dict[str, Any], math_policy: dict[str, Any]) -> float:
    h = math_policy["homeostasis"]
    return homeostatic_potential(
        {dimension: float(state["fitness"][dimension]) for dimension in DIMENSIONS},
        {dimension: float(h["targets"][dimension]) for dimension in DIMENSIONS},
        {dimension: float(h["scales"][dimension]) for dimension in DIMENSIONS},
        {dimension: float(h["weights"][dimension]) for dimension in DIMENSIONS},
    )


def normalize_event(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "kind": args.kind,
        "actor": args.actor or "unknown",
        "repository": args.repository or "unknown",
        "ref": args.ref or "",
        "run_id": args.run_id or "",
        "source": args.source or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def posterior_summary(state: dict[str, Any], z: float) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for dimension in DIMENSIONS:
        belief = state["beliefs"][dimension]
        alpha = float(belief["alpha"])
        beta = float(belief["beta"])
        mean = beta_mean(alpha, beta)
        variance = beta_variance(alpha, beta)
        lower = beta_lower_confidence(alpha, beta, z)
        upper = clamp01(mean + z * math.sqrt(variance))
        summary[dimension] = {
            "alpha": alpha,
            "beta": beta,
            "mean": mean,
            "variance": variance,
            "lower_confidence": lower,
            "upper_confidence": upper,
        }
    return summary


def update_activity_counts(state: dict[str, Any], event: dict[str, Any]) -> None:
    kinds = state["activity_counts"]["event_kinds"]
    actors = state["activity_counts"]["actors"]
    kinds[event["kind"]] = int(kinds.get(event["kind"], 0)) + 1
    actors[event["actor"]] = int(actors.get(event["actor"], 0)) + 1
    state["signals"]["event_entropy"] = round(normalized_entropy(kinds), 6)
    state["signals"]["actor_entropy"] = round(normalized_entropy(actors), 6)


def update_beliefs(state: dict[str, Any], evidence: dict[str, float], strength: float) -> None:
    for dimension, signed_evidence in evidence.items():
        if dimension not in DIMENSIONS:
            raise ValueError(f"unknown evolution dimension in policy: {dimension}")
        belief = state["beliefs"][dimension]
        alpha, beta = beta_update(
            float(belief["alpha"]),
            float(belief["beta"]),
            float(signed_evidence),
            strength=strength,
        )
        belief["alpha"] = alpha
        belief["beta"] = beta
        state["fitness"][dimension] = beta_mean(alpha, beta)


def recommend(
    event: dict[str, Any],
    delta: float,
    state: dict[str, Any],
    posterior: dict[str, dict[str, float]],
    homeostasis_improved: bool,
    math_policy: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    if event["kind"] == "workflow_run.failure":
        recs.append("Investigate the failed workflow before increasing automation authority.")
    if posterior["risk_debt"]["upper_confidence"] >= 0.65:
        recs.append("Risk-debt uncertainty is high; prioritize verification, rollback readiness, and bounded changes.")
    if posterior["community_health"]["lower_confidence"] < 0.40:
        recs.append("Community-health confidence is weak; improve a bounded newcomer path with explicit verification.")
    min_entropy = float(math_policy["diversity"]["minimum_normalized_entropy"])
    if int(state["signals"]["events_seen"]) >= 5 and float(state["signals"]["event_entropy"]) < min_entropy:
        recs.append("Observed event diversity is low; preserve exploration rather than overfitting to one activity type.")
    if not homeostasis_improved:
        recs.append("The Lyapunov-style homeostatic potential did not improve; treat the event as evidence, not proof of progress.")
    if delta <= 0:
        recs.append("Risk-adjusted scalar fitness did not increase; inspect the multidimensional posterior instead of forcing a positive narrative.")
    if not recs:
        recs.append("Continue collecting outcomes; posterior confidence should replace hand-authored assumptions over time.")
    return recs


def append_bounded_jsonl(path: Path, record: dict[str, Any], max_entries: int) -> None:
    if max_entries <= 0:
        raise ValueError("max_event_log_entries must be positive")
    existing: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
                existing.append(line)
    existing.append(json.dumps(record, sort_keys=True))
    existing = existing[-max_entries:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/evolution-state.json")
    parser.add_argument("--events", default="state/evolution-events.jsonl")
    parser.add_argument("--math-policy", default="state/evolution-math-policy.json")
    parser.add_argument("--report", default="EVOLUTION_REPORT.md")
    parser.add_argument("--kind", required=True)
    parser.add_argument("--actor")
    parser.add_argument("--repository")
    parser.add_argument("--ref")
    parser.add_argument("--run-id")
    parser.add_argument("--source")
    parser.add_argument("--checkpoint-source", default="repository-seed")
    args = parser.parse_args()

    math_policy = load_json(args.math_policy)
    state_path = Path(args.state)
    state = migrate_state(load_json(state_path), math_policy)
    event = normalize_event(args)
    state["signals"]["checkpoint_source"] = args.checkpoint_source

    before = fitness(state)
    potential_before = potential(state, math_policy)
    evidence = {
        key: float(value)
        for key, value in math_policy.get("event_evidence", {}).get(args.kind, {}).items()
    }
    update_beliefs(state, evidence, float(math_policy["bayesian"]["event_strength"]))
    update_activity_counts(state, event)

    after = fitness(state)
    delta = round(after - before, 6)
    potential_after = potential(state, math_policy)
    tolerance = float(math_policy["homeostasis"]["lyapunov_tolerance"])
    homeostasis_improved = lyapunov_accept(potential_before, potential_after, tolerance)
    z = float(math_policy["bayesian"]["confidence_z"])
    posterior = posterior_summary(state, z)

    state["updated_at"] = event["timestamp"]
    state["signals"]["events_seen"] = int(state["signals"]["events_seen"]) + 1
    state["signals"]["last_event"] = args.kind
    state["signals"]["last_actor"] = event["actor"]
    state["signals"]["last_score"] = after
    state["signals"]["last_delta"] = delta
    state["signals"]["homeostatic_potential"] = round(potential_after, 6)

    threshold = float(state["policy"]["minimum_meaningful_delta"])
    meaningful = delta > threshold and homeostasis_improved
    record = {
        "version": 2,
        **event,
        "checkpoint_source": args.checkpoint_source,
        "signed_soft_evidence": evidence,
        "fitness_before": before,
        "fitness_after": after,
        "fitness_delta": delta,
        "homeostatic_potential_before": round(potential_before, 6),
        "homeostatic_potential_after": round(potential_after, 6),
        "lyapunov_condition_satisfied": homeostasis_improved,
        "event_entropy": state["signals"]["event_entropy"],
        "actor_entropy": state["signals"]["actor_entropy"],
        "posterior": posterior,
        "meaningful_improvement": meaningful,
        "evidence_quality": "bayesian-soft-evidence",
    }

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_bounded_jsonl(Path(args.events), record, int(state["policy"]["max_event_log_entries"]))

    recs = recommend(event, delta, state, posterior, homeostasis_improved, math_policy)
    rows = "\n".join(
        f"| {d.replace('_', ' ').title()} | {posterior[d]['mean']:.3f} | "
        f"{posterior[d]['lower_confidence']:.3f} | {posterior[d]['upper_confidence']:.3f} | {float(state['weights'][d]):.2f} |"
        for d in DIMENSIONS
    )
    bullets = "\n".join(f"- {r}" for r in recs)
    report = f"""# IDKMesh Evolution Report

Generated from normalized GitHub event evidence. The posterior is an experimental control signal, not a causal claim.

## Latest event

- Kind: `{args.kind}`
- Source: `{event['source'] or 'n/a'}`
- Actor: `{event['actor']}`
- Time: `{event['timestamp']}`
- Checkpoint source: `{args.checkpoint_source}`
- Risk-adjusted fitness before: `{before:.6f}`
- Risk-adjusted fitness after: `{after:.6f}`
- Delta: `{delta:+.6f}`
- Homeostatic potential before: `{potential_before:.6f}`
- Homeostatic potential after: `{potential_after:.6f}`
- Lyapunov-style non-increase within tolerance `{tolerance}`: **{str(homeostasis_improved).lower()}**
- Meaningful improvement (`delta > {threshold}` AND homeostasis condition): **{str(meaningful).lower()}**
- Event-type entropy: `{float(state['signals']['event_entropy']):.3f}`
- Actor entropy: `{float(state['signals']['actor_entropy']):.3f}`
- Evidence quality: **bayesian-soft-evidence**

## Bayesian state

| Dimension | Posterior mean | 95% lower approx. | 95% upper approx. | Utility weight |
| --- | ---: | ---: | ---: | ---: |
{rows}

For positive dimensions, the lower bound is the conservative confidence signal. For `risk_debt`, the upper bound is the conservative risk signal.

## Recommended next response

{bullets}

## Mathematical/safety boundary

- Event mappings are signed **soft evidence**, not additive declarations that an activity caused improvement.
- Bayesian confidence grows only through accumulated observations/checkpoints.
- Homeostatic potential prevents a scalar fitness increase from automatically being called healthy.
- Diversity metrics reveal concentration but do not manufacture independence.
- This workflow has no merge/approval/repository-write authority.
- Policy/evidence mappings remain versioned hypotheses and must be calibrated against real downstream outcomes.
"""
    Path(args.report).write_text(report, encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
