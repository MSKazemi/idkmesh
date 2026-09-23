#!/usr/bin/env python3
"""Targeted AVE policy study after the first cumulative ablation.

This experiment isolates the policy combination suggested by the first
ablation signal: verifier-family diversity + risk-adaptive verification +
verification backpressure, with known-bad probes kept diagnostic rather than
used for positive routing trust.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Dict, Mapping, Sequence

import adaptive_verification_ecology_ablation as ablation


TARGETED_POLICIES = (
    ablation.policy_by_name("plus-verifier-diversity"),
    ablation.Policy(
        "diversity-risk-no-probes",
        niche=True,
        posterior_routing=True,
        temperature=True,
        verifier_diversity=True,
        risk_adaptive=True,
    ),
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


def run_targeted(
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
        [
            ablation.environment_by_name(name)
            for name in environment_names
        ]
        if environment_names
        else list(ablation.ENVIRONMENTS)
    )

    summary: Dict[str, Dict[str, Mapping[str, float]]] = {}
    for environment in environments:
        summary[environment.name] = {}
        for policy in TARGETED_POLICIES:
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
            summary[environment.name][policy.name] = (
                ablation.summarize(rows)
            )

    return {
        "experiment": "adaptive-verification-ecology-targeted-v0",
        "model_warning": (
            "Synthetic targeted experiment; not empirical evidence."
        ),
        "seed_start": seed_start,
        "seeds": seeds,
        "workers": workers,
        "epochs": epochs,
        "verifiers": verifier_count,
        "policies": [asdict(policy) for policy in TARGETED_POLICIES],
        "environments": [
            asdict(environment)
            for environment in environments
        ],
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
        choices=tuple(
            environment.name
            for environment in ablation.ENVIRONMENTS
        ),
    )
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    if min(args.seeds, args.workers, args.epochs, args.verifiers) <= 0:
        parser.error(
            "seeds, workers, epochs, and verifiers must be positive"
        )

    payload = run_targeted(
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
