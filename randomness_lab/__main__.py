from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import Worker
from .policies import POLICIES, make_policy
from .simulator import SimulationConfig, run_simulation


def _parse_workers(spec: str) -> list[Worker]:
    probabilities = [float(item.strip()) for item in spec.split(",") if item.strip()]
    if not probabilities:
        raise argparse.ArgumentTypeError("provide at least one worker success probability")
    try:
        return [
            Worker(name=f"worker-{index + 1}", success_probability=probability)
            for index, probability in enumerate(probabilities)
        ]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab",
        description="Run reproducible IDKMesh stochastic worker-selection experiments.",
    )
    parser.add_argument("--policy", choices=POLICIES, default="thompson")
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--error-correlation", type=float, default=0.0)
    parser.add_argument(
        "--workers",
        type=_parse_workers,
        default=_parse_workers("0.55,0.65,0.80"),
        help="comma-separated synthetic verified-success probabilities",
    )
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_simulation(
        workers=args.workers,
        policy=make_policy(args.policy),
        config=SimulationConfig(
            rounds=args.rounds,
            seed=args.seed,
            error_correlation=args.error_correlation,
        ),
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
