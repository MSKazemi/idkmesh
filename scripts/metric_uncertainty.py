#!/usr/bin/env python3
"""Small dependency-free uncertainty helpers for repository observables.

The first supported family is a Beta-Binomial model for bounded yes/no evidence,
such as independent-review coverage. This module is intentionally narrow: every
metric must declare an observation model rather than inheriting one generic
confidence number.
"""

from __future__ import annotations

import math
from typing import Any


def beta_binomial_summary(
    successes: int,
    trials: int,
    *,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    z: float = 1.96,
) -> dict[str, Any]:
    """Return an inspectable approximate posterior summary.

    Uses a Beta(alpha_prior + successes, beta_prior + failures) posterior.
    The interval is a normal approximation around the Beta posterior mean and
    variance, clipped to [0, 1]. It is intentionally labelled approximate so a
    future exact quantile implementation can replace it without changing the
    evidence semantics.
    """
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if alpha_prior <= 0 or beta_prior <= 0:
        raise ValueError("Beta prior parameters must be positive")

    alpha = alpha_prior + successes
    beta = beta_prior + (trials - successes)
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / (total * total * (total + 1.0))
    sd = math.sqrt(variance)
    low = max(0.0, mean - z * sd)
    high = min(1.0, mean + z * sd)

    return {
        "model": "beta-binomial-v1",
        "successes": successes,
        "trials": trials,
        "alpha_prior": alpha_prior,
        "beta_prior": beta_prior,
        "posterior_alpha": round(alpha, 6),
        "posterior_beta": round(beta, 6),
        "posterior_mean": round(mean, 6),
        "posterior_sd": round(sd, 6),
        "approx_interval_95": [round(low, 6), round(high, 6)],
        "effective_sample_size": round(total, 6),
        "interval_method": "normal-approximation-to-beta-posterior",
    }


def conservative_lower_bound(summary: dict[str, Any]) -> float:
    interval = summary.get("approx_interval_95")
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("summary lacks approx_interval_95")
    return float(interval[0])
