#!/usr/bin/env python3
"""Offline ACE v1 generational policy controller.

This module is intentionally pure and GitHub-independent. It consumes a previous
strategy distribution, deduplicated descendant evidence, and review-load state,
then returns a deterministic next policy plus a bounded recommendation.

It does not call GitHub, create issues, merge pull requests, or grant permissions.
Phase B integration is intentionally gated by Issue #57.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence


STRATEGIES: tuple[str, ...] = (
    "reproduce",
    "challenge",
    "extend",
    "explain",
    "review",
    "onboard",
    "consolidate",
)

GROWTH_STRATEGIES: tuple[str, ...] = tuple(
    strategy for strategy in STRATEGIES if strategy != "consolidate"
)


@dataclass(frozen=True)
class Evidence:
    """One candidate descendant/outcome attributed to one ACE strategy.

    `verified_value` contributes to positive fitness only when `verified=True`.
    Reviewer/maintainer cost, latency, and public-write noise can still penalize
    a strategy when the candidate never becomes a verified descendant.
    """

    evidence_id: str
    strategy: str
    verified: bool
    verified_value: float = 0.0
    reviewer_minutes: float = 0.0
    maintainer_minutes: float = 0.0
    added_review_latency: float = 0.0
    public_writes: int = 0

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must be non-empty")
        if self.strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy: {self.strategy}")
        for name in (
            "verified_value",
            "reviewer_minutes",
            "maintainer_minutes",
            "added_review_latency",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.public_writes < 0:
            raise ValueError("public_writes must be non-negative")
        if not self.verified and self.verified_value != 0:
            raise ValueError("unverified evidence cannot contribute verified_value")


@dataclass(frozen=True)
class ControllerConfig:
    """Versioned mathematical knobs for the Phase-A policy update."""

    eta: float = 0.8
    mu: float = 0.07
    lambda_latency: float = 0.02
    lambda_noise: float = 0.15
    carrying_capacity_k: float = 8.0
    carrying_capacity_tau: float = 2.0
    consolidate_capacity_threshold: float = 0.45
    action_capacity_floor: float = 0.60
    max_public_actions: int = 1

    def __post_init__(self) -> None:
        if self.eta < 0:
            raise ValueError("eta must be non-negative")
        if not 0 <= self.mu <= 1:
            raise ValueError("mu must be in [0, 1]")
        if self.carrying_capacity_tau <= 0:
            raise ValueError("carrying_capacity_tau must be positive")
        if not 0 < self.consolidate_capacity_threshold <= 1:
            raise ValueError("consolidate_capacity_threshold must be in (0, 1]")
        if not 0 < self.action_capacity_floor <= 1:
            raise ValueError("action_capacity_floor must be in (0, 1]")
        # ACE v1 invariant from Issue #57: at most one public autonomous action.
        if self.max_public_actions not in (0, 1):
            raise ValueError("max_public_actions must be 0 or 1")


@dataclass(frozen=True)
class GenerationDecision:
    mode: str
    capacity: float
    r_community: float | None
    unique_evidence: int
    verified_descendants: int
    fitness: dict[str, float]
    previous_weights: dict[str, float]
    next_weights: dict[str, float]
    recommendation: str | None
    public_actions: tuple[str, ...]
    activation_gate_passed: bool
    actuation_enabled: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["public_actions"] = list(self.public_actions)
        return data


def uniform_weights() -> dict[str, float]:
    share = 1.0 / len(STRATEGIES)
    return {strategy: share for strategy in STRATEGIES}


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if set(weights) != set(STRATEGIES):
        missing = sorted(set(STRATEGIES) - set(weights))
        extra = sorted(set(weights) - set(STRATEGIES))
        raise ValueError(f"weights must match STRATEGIES; missing={missing}, extra={extra}")
    if any(float(value) < 0 for value in weights.values()):
        raise ValueError("weights must be non-negative")
    total = sum(float(value) for value in weights.values())
    if total <= 0:
        raise ValueError("weight total must be positive")
    return {strategy: float(weights[strategy]) / total for strategy in STRATEGIES}


def deduplicate_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    """Deduplicate evidence by stable ID and fail closed on conflicting reuse."""

    unique: dict[str, Evidence] = {}
    for item in items:
        prior = unique.get(item.evidence_id)
        if prior is None:
            unique[item.evidence_id] = item
        elif prior != item:
            raise ValueError(f"conflicting evidence for id {item.evidence_id!r}")
    return [unique[key] for key in sorted(unique)]


def carrying_capacity(review_load: float, config: ControllerConfig) -> float:
    if review_load < 0:
        raise ValueError("review_load must be non-negative")
    exponent = (review_load - config.carrying_capacity_k) / config.carrying_capacity_tau
    # Numerically stable logistic for the practical range of this controller.
    exponent = max(-60.0, min(60.0, exponent))
    return 1.0 / (1.0 + math.exp(exponent))


def compute_fitness(
    evidence: Sequence[Evidence], config: ControllerConfig
) -> dict[str, float]:
    """Compute evidence-only strategy fitness.

    Raw activity never creates positive numerator value. Only explicitly verified
    descendants contribute `verified_value`. Costs/noise may create negative
    fitness even when nothing was verified.
    """

    result: dict[str, float] = {}
    for strategy in STRATEGIES:
        relevant = [item for item in evidence if item.strategy == strategy]
        verified_value = sum(item.verified_value for item in relevant if item.verified)
        reviewer = sum(item.reviewer_minutes for item in relevant)
        maintainer = sum(item.maintainer_minutes for item in relevant)
        latency = sum(item.added_review_latency for item in relevant)
        noise = sum(item.public_writes for item in relevant)
        value_per_attention = verified_value / (1.0 + reviewer + maintainer)
        result[strategy] = (
            value_per_attention
            - config.lambda_latency * latency
            - config.lambda_noise * noise
        )
    return result


def replicator_mutator_update(
    previous_weights: Mapping[str, float],
    fitness: Mapping[str, float],
    config: ControllerConfig,
) -> dict[str, float]:
    previous = normalize_weights(previous_weights)
    if set(fitness) != set(STRATEGIES):
        raise ValueError("fitness must contain exactly the ACE strategies")

    mean_fitness = sum(float(fitness[strategy]) for strategy in STRATEGIES) / len(
        STRATEGIES
    )
    selected: dict[str, float] = {}
    for strategy in STRATEGIES:
        exponent = config.eta * (float(fitness[strategy]) - mean_fitness)
        exponent = max(-60.0, min(60.0, exponent))
        selected[strategy] = previous[strategy] * math.exp(exponent)
    selected = normalize_weights(selected)

    exploration = config.mu / len(STRATEGIES)
    mutated = {
        strategy: (1.0 - config.mu) * selected[strategy] + exploration
        for strategy in STRATEGIES
    }
    return normalize_weights(mutated)


def apply_capacity_gate(
    weights: Mapping[str, float], capacity: float, config: ControllerConfig
) -> dict[str, float]:
    """Shift probability toward consolidation under review overload.

    This is a safety/homeostasis transform, not learned positive fitness. It never
    drives any exploration strategy to zero.
    """

    gated = normalize_weights(weights)
    threshold = config.consolidate_capacity_threshold
    if capacity >= threshold:
        return gated

    pressure = max(0.0, min(1.0, (threshold - capacity) / threshold))
    transfer_fraction = 0.90 * pressure
    transferred = 0.0
    for strategy in GROWTH_STRATEGIES:
        amount = gated[strategy] * transfer_fraction
        gated[strategy] -= amount
        transferred += amount
    gated["consolidate"] += transferred
    return normalize_weights(gated)


def _select_mode(
    capacity: float,
    verified_descendants: int,
    eligible_parent_count: int,
    evidence_count: int,
    config: ControllerConfig,
) -> tuple[str, float | None]:
    if eligible_parent_count < 0:
        raise ValueError("eligible_parent_count must be non-negative")
    r_community = (
        verified_descendants / eligible_parent_count
        if eligible_parent_count > 0
        else None
    )

    if capacity < config.consolidate_capacity_threshold:
        return "CONSOLIDATE", r_community
    if evidence_count == 0:
        return "DORMANT", r_community
    if verified_descendants == 0:
        return "EXPLORE", r_community
    if r_community is not None and r_community >= 1.0 and capacity >= 0.65:
        return "GROW", r_community
    return "EXPLORE", r_community


def _recommend(
    mode: str,
    next_weights: Mapping[str, float],
    verified_descendants: int,
) -> str | None:
    if mode == "CONSOLIDATE":
        return "consolidate"
    if mode == "DORMANT" or verified_descendants == 0:
        return None
    # Stable tie-breaker follows the declared STRATEGIES order.
    candidates = GROWTH_STRATEGIES
    return max(candidates, key=lambda strategy: (next_weights[strategy], -STRATEGIES.index(strategy)))


def advance_generation(
    previous_weights: Mapping[str, float],
    evidence: Iterable[Evidence],
    *,
    review_load: float,
    eligible_parent_count: int,
    config: ControllerConfig | None = None,
    activation_gate_passed: bool = False,
    actuation_enabled: bool = False,
) -> GenerationDecision:
    """Advance one ACE generation deterministically.

    Phase A has no GitHub adapter. `public_actions` is therefore a model of the
    bounded action decision, useful for testing the hard gate before any future
    integration. A real actuator must remain disabled until Issue #57's external
    activation gates are reviewed and satisfied.
    """

    config = config or ControllerConfig()
    previous = normalize_weights(previous_weights)
    unique = deduplicate_evidence(evidence)
    fitness = compute_fitness(unique, config)
    learned = replicator_mutator_update(previous, fitness, config)
    capacity = carrying_capacity(review_load, config)
    next_weights = apply_capacity_gate(learned, capacity, config)
    verified_descendants = sum(1 for item in unique if item.verified)
    mode, r_community = _select_mode(
        capacity,
        verified_descendants,
        eligible_parent_count,
        len(unique),
        config,
    )
    recommendation = _recommend(mode, next_weights, verified_descendants)

    reasons: list[str] = []
    if not activation_gate_passed:
        reasons.append("activation gate not passed")
    if not actuation_enabled:
        reasons.append("actuation disabled")
    if capacity < config.action_capacity_floor:
        reasons.append("review capacity below action floor")
    if recommendation is None:
        reasons.append("no evidence-backed recommendation")
    if mode == "CONSOLIDATE":
        reasons.append("consolidation mode suppresses public growth actions")

    may_act = (
        activation_gate_passed
        and actuation_enabled
        and capacity >= config.action_capacity_floor
        and recommendation is not None
        and mode != "CONSOLIDATE"
        and config.max_public_actions == 1
    )
    public_actions: tuple[str, ...] = (recommendation,) if may_act else ()
    if len(public_actions) > 1:
        raise AssertionError("ACE public action budget exceeded")

    return GenerationDecision(
        mode=mode,
        capacity=capacity,
        r_community=r_community,
        unique_evidence=len(unique),
        verified_descendants=verified_descendants,
        fitness=fitness,
        previous_weights=previous,
        next_weights=next_weights,
        recommendation=recommendation,
        public_actions=public_actions,
        activation_gate_passed=activation_gate_passed,
        actuation_enabled=actuation_enabled,
        reason="; ".join(reasons) if reasons else "bounded action permitted by model",
    )


def fixture_scenarios() -> dict[str, dict[str, object]]:
    """Deterministic illustrative Phase-A fixtures, not empirical claims."""

    under = [
        Evidence(
            evidence_id=f"under-{index}",
            strategy="onboard" if index % 2 else "extend",
            verified=False,
            reviewer_minutes=1.0,
            public_writes=1,
        )
        for index in range(6)
    ]

    healthy: list[Evidence] = []
    healthy_strategies = (
        "reproduce",
        "reproduce",
        "reproduce",
        "reproduce",
        "challenge",
        "challenge",
        "extend",
        "extend",
        "explain",
        "review",
        "onboard",
        "reproduce",
    )
    for index, strategy in enumerate(healthy_strategies):
        healthy.append(
            Evidence(
                evidence_id=f"healthy-{index}",
                strategy=strategy,
                verified=True,
                verified_value=1.0,
                reviewer_minutes=0.25,
                maintainer_minutes=0.10,
                added_review_latency=0.05,
                public_writes=0,
            )
        )

    overload: list[Evidence] = []
    for index in range(12):
        overload.append(
            Evidence(
                evidence_id=f"overload-{index}",
                strategy="extend" if index % 2 else "reproduce",
                verified=True,
                verified_value=1.0,
                reviewer_minutes=2.0,
                maintainer_minutes=1.0,
                added_review_latency=1.0,
                public_writes=1,
            )
        )

    return {
        "under-reproduction": {
            "evidence": under,
            "review_load": 2.0,
            "eligible_parent_count": 10,
        },
        "healthy-reproduction": {
            "evidence": healthy,
            "review_load": 4.0,
            "eligible_parent_count": 10,
        },
        "overload": {
            "evidence": overload,
            "review_load": 16.0,
            "eligible_parent_count": 10,
        },
    }


def run_fixtures() -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for name, fixture in fixture_scenarios().items():
        decision = advance_generation(
            uniform_weights(),
            fixture["evidence"],  # type: ignore[arg-type]
            review_load=float(fixture["review_load"]),
            eligible_parent_count=int(fixture["eligible_parent_count"]),
            # Enable the hypothetical action path only to test that the
            # activation/capacity guards are effective in the pure model.
            activation_gate_passed=True,
            actuation_enabled=True,
        )
        output[name] = decision.to_dict()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="print deterministic under/healthy/overload fixture decisions as JSON",
    )
    args = parser.parse_args()
    if not args.fixtures:
        parser.error("Phase A currently supports --fixtures only")
    print(json.dumps(run_fixtures(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
