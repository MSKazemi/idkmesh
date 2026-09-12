#!/usr/bin/env python3
"""E040: review capacity as a carrying-capacity feedback loop.

IDKMesh's ACE design uses a logistic capacity governor to reduce reproduction
pressure when review load rises.  This module isolates that mechanism in a tiny,
deterministic queue model so the feedback can be falsified before it is treated
as an operational policy.

The model is deliberately narrow:

* ``potential_arrivals`` is the amount of new review work that could be admitted
  per step if no gate existed;
* ``service`` is reviewer capacity per step;
* ``load`` is unfinished review work;
* ``open-loop`` admits all potential work;
* ``logistic`` admits ``potential_arrivals * Capacity(load)`` where

      Capacity(load) = 1 / (1 + exp((load - K) / tau)).

No random number generator, network access, GitHub mutation, or production ACE
state is used.  The output is research evidence only and grants no authority to
change admission, merge, or community policy.
"""

from __future__ import annotations

import argparse
import json
import math
from statistics import mean
from typing import Dict, Iterable, List, Sequence

EXPERIMENT_ID = "E040"
EXPERIMENT = "review-capacity-carrying-capacity-v1"

DEFAULT_K = 8.0
DEFAULT_TAU = 2.0
DEFAULT_SERVICE = 1.0
DEFAULT_STEPS = 200
DEFAULT_POTENTIAL_ARRIVALS = (0.5, 1.0, 2.0, 3.0, 4.0)
POLICIES = ("open-loop", "logistic")


def _nonnegative(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite value >= 0")
    return float(value)


def capacity(load: float, k: float = DEFAULT_K, tau: float = DEFAULT_TAU) -> float:
    """Return the ACE logistic capacity multiplier in ``[0, 1]``.

    The numerically stable branches avoid overflow for very large positive or
    negative ``(load - k) / tau``.
    """

    load = _nonnegative("load", load)
    k = _nonnegative("k", k)
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("tau must be a finite value > 0")

    z = (load - k) / tau
    if z >= 0:
        exp_neg = math.exp(-z)
        return exp_neg / (1.0 + exp_neg)
    exp_pos = math.exp(z)
    return 1.0 / (1.0 + exp_pos)


def equilibrium_load(
    potential_arrivals: float,
    service: float,
    k: float = DEFAULT_K,
    tau: float = DEFAULT_TAU,
) -> float:
    """Closed-form non-negative equilibrium for the logistic queue.

    At an interior equilibrium, admitted work equals service capacity:

    ``potential_arrivals * Capacity(load) = service``.

    If reviewer service can already absorb the gated arrivals at zero backlog,
    the queue equilibrium is the boundary value ``0``.
    """

    potential_arrivals = _nonnegative("potential_arrivals", potential_arrivals)
    service = _nonnegative("service", service)
    k = _nonnegative("k", k)
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("tau must be a finite value > 0")
    if service == 0:
        if potential_arrivals == 0:
            return 0.0
        return math.inf
    if potential_arrivals == 0:
        return 0.0
    if potential_arrivals * capacity(0.0, k, tau) <= service:
        return 0.0

    ratio_minus_one = potential_arrivals / service - 1.0
    if ratio_minus_one <= 0:
        return 0.0
    return max(0.0, k + tau * math.log(ratio_minus_one))


def simulate(
    policy: str,
    *,
    potential_arrivals: float,
    service: float = DEFAULT_SERVICE,
    steps: int = DEFAULT_STEPS,
    initial_load: float = 0.0,
    k: float = DEFAULT_K,
    tau: float = DEFAULT_TAU,
) -> Dict[str, object]:
    """Run one deterministic queue trajectory and return aggregate metrics."""

    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}; got {policy!r}")
    potential_arrivals = _nonnegative("potential_arrivals", potential_arrivals)
    service = _nonnegative("service", service)
    load = _nonnegative("initial_load", initial_load)
    k = _nonnegative("k", k)
    if not isinstance(steps, int) or isinstance(steps, bool) or steps <= 0:
        raise ValueError("steps must be an integer > 0")
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("tau must be a finite value > 0")

    loads: List[float] = []
    gates: List[float] = []
    total_admitted = 0.0
    total_reviewed = 0.0
    peak_load = load

    for _ in range(steps):
        gate = 1.0 if policy == "open-loop" else capacity(load, k, tau)
        admitted = potential_arrivals * gate
        available = load + admitted
        reviewed = min(service, available)
        load = max(0.0, available - reviewed)

        gates.append(gate)
        loads.append(load)
        total_admitted += admitted
        total_reviewed += reviewed
        peak_load = max(peak_load, load)

    potential_total = potential_arrivals * steps
    queue_area = sum(loads)
    delay_proxy = queue_area / total_reviewed if total_reviewed > 0 else 0.0
    predicted = (
        equilibrium_load(potential_arrivals, service, k, tau)
        if policy == "logistic"
        else None
    )

    return {
        "policy": policy,
        "potential_arrivals_per_step": potential_arrivals,
        "service_per_step": service,
        "steps": steps,
        "k": k,
        "tau": tau,
        "initial_load": initial_load,
        "final_load": round(load, 9),
        "peak_load": round(peak_load, 9),
        "mean_load": round(mean(loads), 9),
        "mean_gate": round(mean(gates), 9),
        "total_potential_arrivals": round(potential_total, 9),
        "total_admitted": round(total_admitted, 9),
        "total_throttled": round(max(0.0, potential_total - total_admitted), 9),
        "total_reviewed": round(total_reviewed, 9),
        "queue_area": round(queue_area, 9),
        "delay_proxy_steps_per_reviewed_unit": round(delay_proxy, 9),
        "predicted_equilibrium_load": (
            None if predicted is None else round(predicted, 9)
        ),
    }


def run_experiment(
    potential_arrivals: Sequence[float] = DEFAULT_POTENTIAL_ARRIVALS,
    *,
    service: float = DEFAULT_SERVICE,
    steps: int = DEFAULT_STEPS,
    k: float = DEFAULT_K,
    tau: float = DEFAULT_TAU,
) -> Dict[str, object]:
    """Compare open-loop and logistic admission over the same arrival ladder."""

    if not potential_arrivals:
        raise ValueError("potential_arrivals must contain at least one value")

    rows: List[Dict[str, object]] = []
    for arrival_rate in potential_arrivals:
        arrival_rate = _nonnegative("potential_arrivals item", arrival_rate)
        open_loop = simulate(
            "open-loop",
            potential_arrivals=arrival_rate,
            service=service,
            steps=steps,
            k=k,
            tau=tau,
        )
        logistic = simulate(
            "logistic",
            potential_arrivals=arrival_rate,
            service=service,
            steps=steps,
            k=k,
            tau=tau,
        )
        rows.append(
            {
                "potential_arrivals_per_step": arrival_rate,
                "open_loop": open_loop,
                "logistic": logistic,
                "final_load_reduction": round(
                    float(open_loop["final_load"]) - float(logistic["final_load"]),
                    9,
                ),
            }
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "status": "deterministic_toy_model",
        "policy_activation_allowed": False,
        "configuration": {
            "service_per_step": service,
            "steps": steps,
            "k": k,
            "tau": tau,
            "potential_arrivals_per_step": list(potential_arrivals),
        },
        "rows": rows,
        "interpretation_guard": (
            "This experiment tests the feedback shape only. It does not calibrate "
            "human review capacity, predict contributor behavior, or authorize "
            "production ACE admission decisions."
        ),
    }


def _parse_arrivals(values: Iterable[float] | None) -> Sequence[float]:
    parsed = tuple(values or DEFAULT_POTENTIAL_ARRIVALS)
    if not parsed:
        raise ValueError("at least one --potential-arrivals value is required")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--potential-arrivals",
        type=float,
        action="append",
        help="Potential review-work arrivals per step; repeat for a ladder.",
    )
    parser.add_argument("--service", type=float, default=DEFAULT_SERVICE)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--k", type=float, default=DEFAULT_K)
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_experiment(
        _parse_arrivals(args.potential_arrivals),
        service=args.service,
        steps=args.steps,
        k=args.k,
        tau=args.tau,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
