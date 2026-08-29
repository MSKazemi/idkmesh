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
import re
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
TRUSTED_EVENT_SOURCES = frozenset({"issues", "push", "workflow_dispatch", "schedule"})
ADVISORY_EVENT_SOURCES = frozenset({"pull_request_target"})
EVENT_KIND_RE = re.compile(r"^[a-z_]+(?:\.[a-z_]+)+$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
EXPECTED_WEIGHTS = {
    "goal_clarity": 1.2,
    "product_quality": 1.0,
    "community_health": 1.3,
    "verification_strength": 1.3,
    "maintainability": 1.0,
    "exploration_capacity": 0.8,
    "risk_debt": 1.2,
}
EXPECTED_STATE_POLICY = {
    "minimum_meaningful_delta": 0.01,
    "max_event_log_entries": 1000,
    "autonomous_merge": False,
    "constitutional_changes_require_review": True,
}


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field}: expected finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: expected finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}: expected finite number")
    return number


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field}: expected non-negative integer")
    return value


def _count_map(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{field}: expected object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{field}: keys must be non-empty strings")
        result[key] = _non_negative_int(count, f"{field}.{key}")
    return result


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}: expected ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: expected ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}: timestamp must include timezone")
    return value


def validate_evolution_state(state: dict[str, Any]) -> None:
    """Reject malformed or internally inconsistent Bayesian checkpoints."""
    if state.get("version") != 2:
        raise ValueError("evolution state: unsupported version")
    expected = set(DIMENSIONS)
    for field in ("beliefs", "fitness", "weights"):
        value = state.get(field)
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"evolution state: {field} must contain exactly the configured dimensions")

    for dimension in DIMENSIONS:
        belief = state["beliefs"][dimension]
        if not isinstance(belief, dict):
            raise ValueError(f"beliefs.{dimension}: expected object")
        alpha = _finite_number(belief.get("alpha"), f"beliefs.{dimension}.alpha")
        beta = _finite_number(belief.get("beta"), f"beliefs.{dimension}.beta")
        if alpha <= 0 or beta <= 0:
            raise ValueError(f"beliefs.{dimension}: alpha and beta must be positive")
        observed = _finite_number(state["fitness"][dimension], f"fitness.{dimension}")
        if not 0.0 <= observed <= 1.0:
            raise ValueError(f"fitness.{dimension}: expected value in [0, 1]")
        if not math.isclose(observed, beta_mean(alpha, beta), rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"fitness.{dimension}: inconsistent with Bayesian belief")
        weight = _finite_number(state["weights"][dimension], f"weights.{dimension}")
        if weight != EXPECTED_WEIGHTS[dimension]:
            raise ValueError(f"weights.{dimension}: does not match version-2 policy")

    activity = state.get("activity_counts")
    if not isinstance(activity, dict):
        raise ValueError("activity_counts: expected object")
    kinds = _count_map(activity.get("event_kinds"), "activity_counts.event_kinds")
    actors = _count_map(activity.get("actors"), "activity_counts.actors")
    signals = state.get("signals")
    if not isinstance(signals, dict):
        raise ValueError("signals: expected object")
    events_seen = _non_negative_int(signals.get("events_seen"), "signals.events_seen")
    if sum(kinds.values()) != events_seen or sum(actors.values()) != events_seen:
        raise ValueError("signals.events_seen: inconsistent with activity counts")
    for dimension in DIMENSIONS:
        belief = state["beliefs"][dimension]
        concentration = float(belief["alpha"]) + float(belief["beta"])
        if concentration < 8.0 - 1e-9 or concentration > 8.0 + events_seen + 1e-9:
            raise ValueError(f"beliefs.{dimension}: concentration exceeds event lineage")
    for field in ("event_entropy", "actor_entropy"):
        value = _finite_number(signals.get(field), f"signals.{field}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"signals.{field}: expected value in [0, 1]")
    if not isinstance(signals.get("checkpoint_source"), str) or not signals["checkpoint_source"]:
        raise ValueError("signals.checkpoint_source: expected non-empty string")
    for field in ("last_score", "last_delta"):
        _finite_number(signals.get(field), f"signals.{field}")
    potential_value = signals.get("homeostatic_potential")
    if potential_value is not None and _finite_number(
        potential_value, "signals.homeostatic_potential"
    ) < 0:
        raise ValueError("signals.homeostatic_potential: expected non-negative value")
    updated_at = state.get("updated_at")
    if updated_at is not None:
        _timestamp(updated_at, "updated_at")

    policy = state.get("policy")
    if policy != EXPECTED_STATE_POLICY:
        raise ValueError("policy: does not match immutable version-2 authority policy")
    if events_seen > 0 and not math.isclose(
        float(signals["last_score"]), fitness(state), rel_tol=1e-9, abs_tol=1e-6
    ):
        raise ValueError("signals.last_score: inconsistent with Bayesian fitness")


def load_event_ledger(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ledger_path = Path(path)
    if not ledger_path.exists():
        return records
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected JSON object")
        records.append(value)
    return records


def validate_event_ledger(
    state: dict[str, Any],
    records: list[dict[str, Any]],
    allowed_sources: frozenset[str] = TRUSTED_EVENT_SOURCES,
) -> None:
    """Validate bounded event history and its lineage to the state counters."""
    maximum = int(state["policy"]["max_event_log_entries"])
    if len(records) > maximum:
        raise ValueError("event ledger exceeds configured bound")
    observed: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    bootstrap_seen = False
    for index, record in enumerate(records, start=1):
        version = record.get("version")
        if version == 1 and record.get("kind") == "bootstrap":
            if bootstrap_seen or index != 1:
                raise ValueError("event ledger bootstrap must appear at most once and first")
            bootstrap_seen = True
            continue
        if version != 2:
            raise ValueError(f"event ledger record {index}: unsupported version")
        for field in ("kind", "actor", "repository", "timestamp", "checkpoint_source"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise ValueError(f"event ledger record {index}: invalid {field}")
        if not EVENT_KIND_RE.fullmatch(record["kind"]):
            raise ValueError(f"event ledger record {index}: invalid kind")
        if not REPOSITORY_RE.fullmatch(record["repository"]):
            raise ValueError(f"event ledger record {index}: invalid repository")
        source = record.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError(f"event ledger record {index}: invalid event source")
        if source not in allowed_sources:
            raise ValueError(f"event ledger record {index}: untrusted event source")
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id.isdigit() or int(run_id) <= 0:
            raise ValueError(f"event ledger record {index}: invalid run_id")
        if not isinstance(record.get("ref"), str):
            raise ValueError(f"event ledger record {index}: invalid ref")
        _timestamp(record["timestamp"], f"event ledger record {index}.timestamp")
        evidence = record.get("signed_soft_evidence")
        if not isinstance(evidence, dict) or not set(evidence).issubset(DIMENSIONS):
            raise ValueError(f"event ledger record {index}: invalid signed_soft_evidence")
        for dimension, value in evidence.items():
            number = _finite_number(value, f"event ledger record {index}.evidence.{dimension}")
            if not -1.0 <= number <= 1.0:
                raise ValueError(f"event ledger record {index}: evidence outside [-1, 1]")
        before = _finite_number(record.get("fitness_before"), f"event ledger record {index}.fitness_before")
        after = _finite_number(record.get("fitness_after"), f"event ledger record {index}.fitness_after")
        delta = _finite_number(record.get("fitness_delta"), f"event ledger record {index}.fitness_delta")
        if not math.isclose(delta, after - before, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError(f"event ledger record {index}: inconsistent fitness delta")
        if previous is not None and not math.isclose(
            before, float(previous["fitness_after"]), rel_tol=1e-9, abs_tol=1e-6
        ):
            raise ValueError(f"event ledger record {index}: broken fitness lineage")
        posterior = record.get("posterior")
        if not isinstance(posterior, dict) or set(posterior) != set(DIMENSIONS):
            raise ValueError(f"event ledger record {index}: invalid posterior dimensions")
        for dimension in DIMENSIONS:
            summary = posterior[dimension]
            if not isinstance(summary, dict):
                raise ValueError(f"event ledger record {index}: invalid posterior")
            alpha = _finite_number(summary.get("alpha"), f"event ledger record {index}.posterior.{dimension}.alpha")
            beta = _finite_number(summary.get("beta"), f"event ledger record {index}.posterior.{dimension}.beta")
            mean = _finite_number(summary.get("mean"), f"event ledger record {index}.posterior.{dimension}.mean")
            if alpha <= 0 or beta <= 0 or not math.isclose(
                mean, beta_mean(alpha, beta), rel_tol=1e-9, abs_tol=1e-9
            ):
                raise ValueError(f"event ledger record {index}: inconsistent posterior")
            for field in ("variance", "lower_confidence", "upper_confidence"):
                value = _finite_number(
                    summary.get(field), f"event ledger record {index}.posterior.{dimension}.{field}"
                )
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"event ledger record {index}: invalid posterior {field}")
        for field in ("event_entropy", "actor_entropy"):
            value = _finite_number(record.get(field), f"event ledger record {index}.{field}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"event ledger record {index}: invalid {field}")
        for field in ("homeostatic_potential_before", "homeostatic_potential_after"):
            if _finite_number(record.get(field), f"event ledger record {index}.{field}") < 0:
                raise ValueError(f"event ledger record {index}: invalid {field}")
        if not isinstance(record.get("lyapunov_condition_satisfied"), bool):
            raise ValueError(f"event ledger record {index}: invalid Lyapunov result")
        if not isinstance(record.get("meaningful_improvement"), bool):
            raise ValueError(f"event ledger record {index}: invalid improvement result")
        if record.get("evidence_quality") != "bayesian-soft-evidence":
            raise ValueError(f"event ledger record {index}: invalid evidence quality")
        observed.append(record)
        previous = record

    events_seen = int(state["signals"]["events_seen"])
    if len(observed) != min(events_seen, maximum):
        raise ValueError("event ledger lineage does not match state event count")
    if observed:
        latest = observed[-1]
        if state["signals"].get("last_event") != latest["kind"]:
            raise ValueError("event ledger latest kind does not match state")
        if state["signals"].get("last_actor") != latest["actor"]:
            raise ValueError("event ledger latest actor does not match state")
        if state.get("updated_at") != latest["timestamp"]:
            raise ValueError("event ledger latest timestamp does not match state")
        if state["signals"].get("checkpoint_source") != latest["checkpoint_source"]:
            raise ValueError("event ledger checkpoint source does not match state")
        if not math.isclose(
            float(state["signals"]["last_score"]),
            float(latest["fitness_after"]),
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError("event ledger latest fitness does not match state")
        if not math.isclose(
            float(state["signals"]["last_delta"]),
            float(latest["fitness_delta"]),
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError("event ledger latest delta does not match state")
        if not math.isclose(
            float(state["signals"]["homeostatic_potential"]),
            float(latest["homeostatic_potential_after"]),
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError("event ledger latest potential does not match state")
        if not math.isclose(
            float(state["signals"]["event_entropy"]),
            float(latest["event_entropy"]),
            rel_tol=1e-9,
            abs_tol=1e-6,
        ) or not math.isclose(
            float(state["signals"]["actor_entropy"]),
            float(latest["actor_entropy"]),
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError("event ledger latest diversity does not match state")
        for dimension in DIMENSIONS:
            summary = latest["posterior"][dimension]
            belief = state["beliefs"][dimension]
            if not math.isclose(float(belief["alpha"]), float(summary["alpha"]), rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("event ledger posterior alpha does not match state")
            if not math.isclose(float(belief["beta"]), float(summary["beta"]), rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("event ledger posterior beta does not match state")


def migrate_state(state: dict[str, Any], math_policy: dict[str, Any]) -> dict[str, Any]:
    """Migrate the old additive v1 state into a Bayesian v2 representation."""
    version = state.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version not in {1, 2}:
        raise ValueError("evolution state: unsupported version")
    state.setdefault("fitness", {})
    if version == 1:
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
    elif not isinstance(state.get("beliefs"), dict):
        raise ValueError("evolution state: beliefs must be an object")

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
    ledger_records = load_event_ledger(args.events)
    validate_evolution_state(state)
    validate_event_ledger(state, ledger_records)
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

    next_records = (ledger_records + [record])[-int(state["policy"]["max_event_log_entries"]):]
    validate_evolution_state(state)
    # A pull_request_target run may report advisory PR metadata, but its
    # resulting artifact is never eligible as a canonical parent. Keep this
    # one-run exception explicit instead of weakening the validator's default.
    next_allowed_sources = TRUSTED_EVENT_SOURCES
    if event["source"] in ADVISORY_EVENT_SOURCES:
        next_allowed_sources |= ADVISORY_EVENT_SOURCES
    validate_event_ledger(state, next_records, next_allowed_sources)

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
