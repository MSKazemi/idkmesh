#!/usr/bin/env python3
"""Combine persistent Bayesian evidence with recomputed live repository guards.

This module does not choose merges or approvals. It answers one narrower question:
are the historical confidence bounds and current live guardrails jointly healthy
enough that a *stronger bounded, non-integrating experiment* may be considered?

Hard current blockers are conjunctive: historical fitness can never compensate
for an unprotected canonical branch, missing review coverage, supply-chain guard,
or other blocker emitted by the live repository observatory.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

from evolution_math import beta_lower_confidence, beta_mean, beta_variance, clamp01


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _posterior_bounds(history: Mapping[str, Any], math_policy: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    beliefs = history.get("beliefs") or {}
    z = float(math_policy["bayesian"]["confidence_z"])
    result: dict[str, dict[str, float]] = {}
    for dimension in ("verification_strength", "risk_debt"):
        belief = beliefs.get(dimension)
        if not isinstance(belief, Mapping):
            raise ValueError(f"history missing Bayesian belief: {dimension}")
        alpha = float(belief["alpha"])
        beta = float(belief["beta"])
        mean = beta_mean(alpha, beta)
        variance = beta_variance(alpha, beta)
        result[dimension] = {
            "mean": mean,
            "lower": beta_lower_confidence(alpha, beta, z),
            "upper": clamp01(mean + z * math.sqrt(variance)),
            "alpha": alpha,
            "beta": beta,
        }
    return result


def evaluate(
    history: Mapping[str, Any],
    math_policy: Mapping[str, Any],
    live: Mapping[str, Any],
    live_policy: Mapping[str, Any],
) -> dict[str, Any]:
    posterior = _posterior_bounds(history, math_policy)
    homeostasis = math_policy["homeostasis"]
    verification_floor = clamp01(
        float(homeostasis["targets"]["verification_strength"])
        - float(homeostasis["scales"]["verification_strength"])
    )
    risk_ceiling = clamp01(
        float(homeostasis["targets"]["risk_debt"])
        + float(homeostasis["scales"]["risk_debt"])
    )

    blockers = [str(value) for value in live.get("blockers") or []]
    live_mode = str(live.get("mode") or "UNKNOWN")
    live_signals = live.get("signals") or {}
    review_capacity = float(live_signals.get("review_capacity", 0.0))
    minimum_capacity = float(live_policy["targets"]["minimum_capacity"])

    hard_guard_pass = live_mode != "GUARD" and not blockers
    history_confidence_pass = (
        posterior["verification_strength"]["lower"] >= verification_floor
        and posterior["risk_debt"]["upper"] <= risk_ceiling
    )
    capacity_pass = review_capacity >= minimum_capacity
    bounded_experiment_escalation_candidate = bool(
        hard_guard_pass
        and history_confidence_pass
        and capacity_pass
        and live_mode in {"EXPLORE", "ONBOARD", "INTEGRATE"}
    )

    return {
        "version": 1,
        "control_model": "conjunctive-history-live-v1",
        "live_mode": live_mode,
        "hard_blockers": blockers,
        "hard_guard_pass": hard_guard_pass,
        "history_confidence_pass": history_confidence_pass,
        "capacity_pass": capacity_pass,
        "thresholds": {
            "verification_lower_floor": verification_floor,
            "risk_upper_ceiling": risk_ceiling,
            "minimum_review_capacity": minimum_capacity,
        },
        "posterior": posterior,
        "live_review_capacity": review_capacity,
        "bounded_experiment_escalation_candidate": bounded_experiment_escalation_candidate,
        "non_compensation_rule": "live hard blockers cannot be offset by historical Bayesian fitness or confidence",
        "authority": {
            "recommendation_only": True,
            "integration_authority": False,
            "approval_authority": False,
            "merge_authority": False,
            "branch_mutation_authority": False,
            "spending_authority": False,
        },
    }


def render(result: Mapping[str, Any]) -> str:
    verification = result["posterior"]["verification_strength"]
    risk = result["posterior"]["risk_debt"]
    blockers = "\n".join(f"- `{value}`" for value in result["hard_blockers"]) or "- none"
    return f"""# Conjunctive Evolution Control

The persistent Bayesian observer and the recomputed live repository observatory are evaluated together. Historical confidence cannot compensate for a failed current hard guard.

## Result

- Live mode: **{result['live_mode']}**
- Hard guard pass: **{str(bool(result['hard_guard_pass'])).lower()}**
- Bayesian confidence pass: **{str(bool(result['history_confidence_pass'])).lower()}**
- Review-capacity pass: **{str(bool(result['capacity_pass'])).lower()}**
- Stronger bounded experiment may be considered: **{str(bool(result['bounded_experiment_escalation_candidate'])).lower()}**
- Integration authority: **false**

## Bayesian conservative bounds

- Verification posterior mean: `{verification['mean']:.3f}`
- Verification lower bound: `{verification['lower']:.3f}` (required >= `{result['thresholds']['verification_lower_floor']:.3f}`)
- Risk-debt posterior mean: `{risk['mean']:.3f}`
- Risk-debt upper bound: `{risk['upper']:.3f}` (required <= `{result['thresholds']['risk_upper_ceiling']:.3f}`)
- Live review capacity: `{result['live_review_capacity']:.3f}` (required >= `{result['thresholds']['minimum_review_capacity']:.3f}`)

## Live blockers

{blockers}

## Rule

`{result['non_compensation_rule']}`

This result can only widen or narrow the class of **bounded non-integrating experiments** worth considering. It cannot approve, merge, mutate branches, spend money, or create constitutional authority.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="state/evolution-state.json")
    parser.add_argument("--math-policy", default="state/evolution-math-policy.json")
    parser.add_argument("--live", default="results/evolution/evolution-decision.json")
    parser.add_argument("--live-policy", default="config/evolution-policy-v1.json")
    parser.add_argument("--output", default="results/evolution/conjunctive-control.json")
    parser.add_argument("--report", default="results/evolution/CONJUNCTIVE_CONTROL_REPORT.md")
    args = parser.parse_args()
    result = evaluate(
        load_json(args.history),
        load_json(args.math_policy),
        load_json(args.live),
        load_json(args.live_policy),
    )
    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render(result), encoding="utf-8")
    print(json.dumps({
        "live_mode": result["live_mode"],
        "hard_guard_pass": result["hard_guard_pass"],
        "history_confidence_pass": result["history_confidence_pass"],
        "bounded_experiment_escalation_candidate": result["bounded_experiment_escalation_candidate"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
