#!/usr/bin/env python3
"""Deterministic ACE generational policy controller.

Phase A / shadow mode implementation for issue #57.

The controller deliberately separates three evidence layers:

1. ``parents`` -- an independent matured-parent inventory for the denominator;
2. ``lineage_receipts`` -- prevalidated causal receipts compatible with the
   ACE lineage protocol from PR #48 / issue #25;
3. ``strategy_outcomes`` -- measured value/cost observations linked to a
   lineage identity for policy-fitness learning.

This prevents a lineage record from inventing maintainer time, latency, noise,
or utility value, and prevents an arbitrary strategy-outcome row from becoming
causal proof by itself.

The controller does not call GitHub, create issues/comments, approve, merge, or
mutate the repository. Phase A models a bounded public action only when both
explicit actuation and external activation gates are true. Overload always
suppresses that modeled public action.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

STRATEGIES = (
    "reproduce",
    "challenge",
    "extend",
    "explain",
    "review",
    "onboard",
    "consolidate",
)

GROWTH_STRATEGIES = tuple(strategy for strategy in STRATEGIES if strategy != "consolidate")
LINEAGE_STATUSES = {"candidate", "merged", "verified", "rejected"}
CONSOLIDATE_CAPACITY_THRESHOLD = 0.45
ACTION_CAPACITY_FLOOR = 0.60
EVIDENCE_FORMAT = "ace-lineage-receipts+strategy-outcomes-v1"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any, name: str, minimum: float | None = None) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} must be numeric")
    result = float(value)
    _require(math.isfinite(result), f"{name} must be finite")
    if minimum is not None:
        _require(result >= minimum, f"{name} must be >= {minimum}")
    return result


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    _require(snapshot.get("version") == 1, "snapshot version must be 1")

    weights = snapshot.get("weights")
    _require(isinstance(weights, dict), "weights must be an object")
    _require(set(weights) == set(STRATEGIES), "weights must contain exactly the canonical strategies")
    total = 0.0
    for strategy in STRATEGIES:
        total += _number(weights[strategy], f"weights.{strategy}", 0.0)
    _require(total > 0.0, "strategy weights must have positive total mass")

    capacity = snapshot.get("capacity")
    _require(isinstance(capacity, dict), "capacity must be an object")
    _number(snapshot.get("review_load"), "review_load", 0.0)
    _number(capacity.get("K"), "capacity.K", 0.0)
    _require(_number(capacity.get("tau"), "capacity.tau", 0.0) > 0.0, "capacity.tau must be > 0")

    policy = snapshot.get("policy")
    _require(isinstance(policy, dict), "policy must be an object")
    eta = _number(policy.get("eta"), "policy.eta", 0.0)
    mu = _number(policy.get("mu"), "policy.mu", 0.0)
    _require(eta <= 10.0, "policy.eta is unreasonably large")
    _require(0.0 <= mu < 1.0, "policy.mu must be in [0, 1)")
    _number(policy.get("lambda_latency", 0.0), "policy.lambda_latency", 0.0)
    _number(policy.get("lambda_noise", 0.0), "policy.lambda_noise", 0.0)
    budget = policy.get("public_write_budget", 1)
    _require(isinstance(budget, int) and not isinstance(budget, bool), "public_write_budget must be an integer")
    _require(0 <= budget <= 1, "public_write_budget must be 0 or 1 in ACE v1")
    _require(isinstance(policy.get("actuation_enabled", False), bool), "actuation_enabled must be boolean")
    _require(
        isinstance(policy.get("activation_gate_passed", False), bool),
        "activation_gate_passed must be boolean",
    )

    parents = snapshot.get("parents", [])
    receipts = snapshot.get("lineage_receipts", [])
    outcomes = snapshot.get("strategy_outcomes", [])
    _require(isinstance(parents, list), "parents must be a list")
    _require(isinstance(receipts, list), "lineage_receipts must be a list")
    _require(isinstance(outcomes, list), "strategy_outcomes must be a list")
    _require("descendants" not in snapshot, "legacy descendants input is not canonical; use lineage_receipts + strategy_outcomes")

    parent_ids: set[str] = set()
    for index, parent in enumerate(parents):
        _require(isinstance(parent, dict), f"parents[{index}] must be an object")
        parent_id = parent.get("id")
        _require(isinstance(parent_id, str) and parent_id, f"parents[{index}].id must be non-empty")
        _require(parent_id not in parent_ids, f"duplicate parent id: {parent_id}")
        parent_ids.add(parent_id)
        _require(isinstance(parent.get("verified", False), bool), f"parents[{index}].verified must be boolean")
        _require(isinstance(parent.get("matured", False), bool), f"parents[{index}].matured must be boolean")

    receipt_ids: set[str] = set()
    for index, receipt in enumerate(receipts):
        _require(isinstance(receipt, dict), f"lineage_receipts[{index}] must be an object")
        identity = receipt.get("identity")
        _require(isinstance(identity, str) and identity, f"lineage_receipts[{index}].identity must be non-empty")
        _require(identity not in receipt_ids, f"duplicate lineage identity: {identity}")
        receipt_ids.add(identity)

        parent = receipt.get("parent")
        _require(isinstance(parent, str) and parent, f"lineage_receipts[{index}].parent must be non-empty")
        if parent_ids:
            _require(parent in parent_ids, f"lineage receipt {identity} references unknown parent {parent}")

        for field in ("seed", "descendant", "descendant_type", "recorded_at"):
            _require(
                isinstance(receipt.get(field), str) and receipt.get(field),
                f"lineage_receipts[{index}].{field} must be non-empty",
            )
        status = receipt.get("status")
        _require(status in LINEAGE_STATUSES, f"lineage_receipts[{index}].status invalid")
        verified = receipt.get("verified")
        _require(isinstance(verified, bool), f"lineage_receipts[{index}].verified must be boolean")
        _require(verified == (status == "verified"), f"lineage receipt {identity} verified flag disagrees with status")
        _number(receipt.get("reviewer_minutes", 0.0), f"lineage_receipts[{index}].reviewer_minutes", 0.0)

    outcome_ids: set[str] = set()
    for index, outcome in enumerate(outcomes):
        _require(isinstance(outcome, dict), f"strategy_outcomes[{index}] must be an object")
        identity = outcome.get("lineage_identity")
        _require(isinstance(identity, str) and identity, f"strategy_outcomes[{index}].lineage_identity must be non-empty")
        _require(identity in receipt_ids, f"strategy outcome references unknown lineage identity {identity}")
        _require(identity not in outcome_ids, f"duplicate strategy outcome for lineage identity: {identity}")
        outcome_ids.add(identity)
        _require(outcome.get("strategy") in STRATEGIES, f"strategy_outcomes[{index}].strategy is not canonical")
        _number(outcome.get("value", 0.0), f"strategy_outcomes[{index}].value", 0.0)
        _number(outcome.get("maintainer_minutes", 0.0), f"strategy_outcomes[{index}].maintainer_minutes", 0.0)
        _number(outcome.get("added_review_latency_hours", 0.0), f"strategy_outcomes[{index}].added_review_latency_hours", 0.0)
        _number(outcome.get("unproductive_public_writes", 0.0), f"strategy_outcomes[{index}].unproductive_public_writes", 0.0)
        _require(
            "reviewer_minutes" not in outcome,
            f"strategy_outcomes[{index}] must not duplicate reviewer_minutes from the lineage receipt",
        )


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    _require(total > 0.0, "cannot normalize zero strategy mass")
    return {strategy: weights[strategy] / total for strategy in STRATEGIES}


def carrying_capacity(review_load: float, K: float, tau: float) -> float:
    # Equivalent to 1 / (1 + exp((L-K)/tau)), rearranged for numeric safety.
    x = (review_load - K) / tau
    if x >= 0:
        z = math.exp(-x)
        return z / (1.0 + z)
    z = math.exp(x)
    return 1.0 / (1.0 + z)


def _receipt_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {receipt["identity"]: receipt for receipt in snapshot.get("lineage_receipts", [])}


def strategy_fitness(snapshot: dict[str, Any]) -> dict[str, float]:
    policy = snapshot["policy"]
    lambda_latency = float(policy.get("lambda_latency", 0.0))
    lambda_noise = float(policy.get("lambda_noise", 0.0))
    receipts = _receipt_index(snapshot)

    out: dict[str, float] = {}
    for strategy in STRATEGIES:
        rows = [row for row in snapshot.get("strategy_outcomes", []) if row["strategy"] == strategy]

        verified_value = sum(
            float(row.get("value", 0.0))
            for row in rows
            if receipts[row["lineage_identity"]]["status"] == "verified"
        )
        attention = sum(
            float(receipts[row["lineage_identity"]].get("reviewer_minutes", 0.0))
            + float(row.get("maintainer_minutes", 0.0))
            for row in rows
        )
        latency = sum(float(row.get("added_review_latency_hours", 0.0)) for row in rows)
        noise = sum(float(row.get("unproductive_public_writes", 0.0)) for row in rows)

        # A strategy outcome cannot create positive benefit unless its linked
        # canonical lineage receipt is verified. Costs can still be observed.
        benefit = verified_value / (1.0 + attention)
        out[strategy] = benefit - lambda_latency * latency - lambda_noise * noise
    return out


def update_weights(snapshot: dict[str, Any], fitness: dict[str, float]) -> dict[str, float]:
    current = normalize_weights({strategy: float(snapshot["weights"][strategy]) for strategy in STRATEGIES})
    eta = float(snapshot["policy"]["eta"])
    mu = float(snapshot["policy"]["mu"])
    mean_fitness = sum(current[s] * fitness[s] for s in STRATEGIES)

    selected: dict[str, float] = {}
    for strategy in STRATEGIES:
        exponent = eta * (fitness[strategy] - mean_fitness)
        exponent = max(-60.0, min(60.0, exponent))
        selected[strategy] = current[strategy] * math.exp(exponent)

    selected = normalize_weights(selected)
    n = len(STRATEGIES)
    mutated = {
        strategy: (1.0 - mu) * selected[strategy] + mu / n
        for strategy in STRATEGIES
    }
    return normalize_weights(mutated)


def apply_capacity_homeostasis(weights: dict[str, float], capacity: float) -> dict[str, float]:
    """Bias policy mass toward consolidation when review capacity is unhealthy."""

    gated = normalize_weights(dict(weights))
    if capacity >= CONSOLIDATE_CAPACITY_THRESHOLD:
        return gated

    pressure = max(
        0.0,
        min(1.0, (CONSOLIDATE_CAPACITY_THRESHOLD - capacity) / CONSOLIDATE_CAPACITY_THRESHOLD),
    )
    transfer_fraction = 0.90 * pressure
    transferred = 0.0
    for strategy in GROWTH_STRATEGIES:
        amount = gated[strategy] * transfer_fraction
        gated[strategy] -= amount
        transferred += amount
    gated["consolidate"] += transferred
    return normalize_weights(gated)


def reproduction_number(snapshot: dict[str, Any]) -> tuple[float, int, int]:
    parents = [p for p in snapshot.get("parents", []) if p.get("verified") and p.get("matured")]
    verified_receipts = [
        receipt for receipt in snapshot.get("lineage_receipts", [])
        if receipt.get("status") == "verified" and receipt.get("verified") is True
    ]
    denominator = len(parents)
    numerator = len(verified_receipts)
    if denominator == 0:
        return 0.0, numerator, denominator
    return numerator / denominator, numerator, denominator


def select_mode(snapshot: dict[str, Any], capacity: float, r_c: float, verified_descendants: int, matured_parents: int) -> str:
    review_load = float(snapshot["review_load"])
    K = float(snapshot["capacity"]["K"])

    if review_load > K or capacity < CONSOLIDATE_CAPACITY_THRESHOLD:
        return "CONSOLIDATE"
    if matured_parents == 0:
        return "DORMANT"
    if verified_descendants == 0:
        return "EXPLORE"
    if r_c < 1.0 and capacity >= 0.65:
        return "EXPLORE"
    if r_c >= 1.0 and capacity >= 0.65:
        return "GROW"
    return "DORMANT"


def choose_recommendation(mode: str, weights: dict[str, float]) -> str | None:
    if mode == "CONSOLIDATE":
        return "consolidate"
    if mode not in {"EXPLORE", "GROW"}:
        return None
    candidates = [s for s in STRATEGIES if s != "consolidate"]
    return max(candidates, key=lambda s: (weights[s], -STRATEGIES.index(s)))


def evaluate(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    review_load = float(snapshot["review_load"])
    K = float(snapshot["capacity"]["K"])
    tau = float(snapshot["capacity"]["tau"])
    capacity = carrying_capacity(review_load, K, tau)
    fitness = strategy_fitness(snapshot)
    learned_weights = update_weights(snapshot, fitness)
    weights = apply_capacity_homeostasis(learned_weights, capacity)
    r_c, verified_descendants, matured_parents = reproduction_number(snapshot)
    mode = select_mode(snapshot, capacity, r_c, verified_descendants, matured_parents)
    recommendation = choose_recommendation(mode, weights)

    policy = snapshot["policy"]
    activation_gate_passed = bool(policy.get("activation_gate_passed", False))
    actuation_enabled = bool(policy.get("actuation_enabled", False))
    public_write_budget = int(policy.get("public_write_budget", 1))
    public_action = None
    may_model_action = (
        activation_gate_passed
        and actuation_enabled
        and public_write_budget > 0
        and capacity >= ACTION_CAPACITY_FLOOR
        and mode != "CONSOLIDATE"
        and recommendation is not None
    )
    if may_model_action:
        public_action = {
            "strategy": recommendation,
            "max_public_writes": 1,
            "note": "Proposal only. A separately reviewed GitHub integration decides whether/how to actuate.",
        }

    return {
        "version": 1,
        "evidence_format": EVIDENCE_FORMAT,
        "mode": mode,
        "capacity": round(capacity, 8),
        "review_load": review_load,
        "carrying_capacity_K": K,
        "R_community": round(r_c, 8),
        "verified_descendants": verified_descendants,
        "eligible_matured_verified_parents": matured_parents,
        "strategy_fitness": {s: round(fitness[s], 10) for s in STRATEGIES},
        "next_weights": {s: round(weights[s], 10) for s in STRATEGIES},
        "recommendation": recommendation,
        "activation_gate_passed": activation_gate_passed,
        "actuation_enabled": actuation_enabled,
        "public_write_budget": public_write_budget,
        "public_action": public_action,
        "evidence_rule": (
            "Causal reproduction comes only from verified lineage receipts; positive strategy value comes only from measured outcomes linked to a verified receipt."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", help="Generation snapshot JSON")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    result = evaluate(snapshot)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
