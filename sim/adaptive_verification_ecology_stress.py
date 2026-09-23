#!/usr/bin/env python3
"""AVE-3 targeted synthetic stress grid for the remaining issue #621 gates.

This harness keeps the AVE-1 cumulative ablation frozen and varies one stress
axis at a time where possible. It is synthetic research, not production evidence.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Dict, Mapping, Sequence

import adaptive_verification_ecology_ablation as ablation


STRESS_POLICIES = (
    ablation.policy_by_name("capability-only"),
    ablation.policy_by_name("plus-verifier-diversity"),
    ablation.Policy(
        "ave-core",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        risk_adaptive=True,
        shadow_backpressure=True,
        price_aware_routing=True,
    ),
    ablation.policy_by_name("full-ave"),
)


STRESS_ENVIRONMENTS = (
    # Verifier-correlation grid; worker shocks held at the reference setting.
    ablation.Environment("verifier-corr-low", verifier_corr_scale=0.25),
    ablation.Environment("verifier-corr-medium", verifier_corr_scale=1.0),
    ablation.Environment("verifier-corr-high", verifier_corr_scale=1.75),
    # Worker-correlation grid; verifier correlation held at the reference setting.
    ablation.Environment(
        "worker-corr-low", worker_shock_rate=0.02, worker_shock_penalty=0.08
    ),
    ablation.Environment(
        "worker-corr-medium", worker_shock_rate=0.12, worker_shock_penalty=0.22
    ),
    ablation.Environment(
        "worker-corr-high", worker_shock_rate=0.28, worker_shock_penalty=0.30
    ),
    # Review-capacity grid.
    ablation.Environment("review-scarce", review_capacity_scale=0.60),
    ablation.Environment("review-medium", review_capacity_scale=1.0),
    ablation.Environment("review-abundant", review_capacity_scale=1.50),
    # Remaining stress mechanisms.
    ablation.Environment("dominant-provider", worker_quality_imbalance=0.18),
    ablation.Environment("workload-shift", workload_shift=True),
    ablation.Environment("provider-outage", worker_outage=True),
    ablation.Environment("verifier-outage", verifier_outage=True),
    ablation.Environment("selective-adversarial-verifier", selective_adversary=True),
)


def environment_by_name(name: str) -> ablation.Environment:
    for environment in STRESS_ENVIRONMENTS:
        if environment.name == name:
            return environment
    raise ValueError(f"unknown environment: {name}")


def run_stress(
    seed_start: int = 1,
    seeds: int = 20,
    workers: int = 24,
    epochs: int = 50,
    verifier_count: int = 12,
    environment_names: Sequence[str] | None = None,
) -> Dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    environments = (
        [environment_by_name(name) for name in environment_names]
        if environment_names
        else list(STRESS_ENVIRONMENTS)
    )
    summary: Dict[str, Dict[str, Mapping[str, float]]] = {}
    for environment in environments:
        summary[environment.name] = {}
        for policy in STRESS_POLICIES:
            rows = [
                ablation.run_policy(
                    policy,
                    environment,
                    seed=seed_start + offset,
                    workers=workers,
                    epochs=epochs,
                    verifier_count=verifier_count,
                )
                for offset in range(seeds)
            ]
            summary[environment.name][policy.name] = ablation.summarize(rows)
    return {
        "experiment": "adaptive-verification-ecology-stress-v0",
        "model_warning": "Synthetic stress-grid experiment; not empirical evidence.",
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "verifiers": verifier_count,
        "policies": [asdict(policy) for policy in STRESS_POLICIES],
        "environments": [asdict(environment) for environment in environments],
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--verifiers", type=int, default=12)
    parser.add_argument(
        "--environment",
        action="append",
        choices=tuple(environment.name for environment in STRESS_ENVIRONMENTS),
    )
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)
    if min(args.seeds, args.workers, args.epochs, args.verifiers) <= 0:
        parser.error("seeds, workers, epochs, and verifiers must be positive")
    payload = run_stress(
        seed_start=args.seed_start,
        seeds=args.seeds,
        workers=args.workers,
        epochs=args.epochs,
        verifier_count=args.verifiers,
        environment_names=args.environment,
    )
    print(json.dumps(payload, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
