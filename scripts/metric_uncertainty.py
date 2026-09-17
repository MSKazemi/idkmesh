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

    A mathematically valid prior posterior with zero trials is *not* empirical
    evidence. Version 2 therefore exposes the empirical rate separately and
    labels a zero-trial result as prior-only while preserving the posterior
    fields for reproducibility and Bayesian composition.
    """
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if alpha_prior <= 0 or beta_prior <= 0:
        raise ValueError("Beta prior parameters must be positive")
    if not math.isfinite(alpha_prior) or not math.isfinite(beta_prior):
        raise ValueError("Beta prior parameters must be finite")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("z must be a positive finite value")

    alpha = alpha_prior + successes
    beta = beta_prior + (trials - successes)
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / (total * total * (total + 1.0))
    sd = math.sqrt(variance)
    low = max(0.0, mean - z * sd)
    high = min(1.0, mean + z * sd)
    prior_mass = alpha_prior + beta_prior
    empirical_rate = successes / trials if trials else None
    evidence_status = "observed" if trials else "prior_only_no_observations"

    return {
        "model": "beta-binomial-v2",
        "successes": successes,
        "trials": trials,
        "observed_sample_size": trials,
        "empirical_rate": round(empirical_rate, 6) if empirical_rate is not None else None,
        "evidence_status": evidence_status,
        "alpha_prior": alpha_prior,
        "beta_prior": beta_prior,
        "prior_pseudocount_mass": round(prior_mass, 6),
        "posterior_alpha": round(alpha, 6),
        "posterior_beta": round(beta, 6),
        "posterior_mean": round(mean, 6),
        "posterior_sd": round(sd, 6),
        "approx_interval_95": [round(low, 6), round(high, 6)],
        "posterior_concentration": round(total, 6),
        # Compatibility field retained from v1. This is prior + observed
        # concentration, not the number of empirical observations.
        "effective_sample_size": round(total, 6),
        "effective_sample_size_semantics": "beta_posterior_concentration_not_observed_sample_size",
        "interval_method": "normal-approximation-to-beta-posterior",
    }


def conservative_lower_bound(summary: dict[str, Any]) -> float:
    interval = summary.get("approx_interval_95")
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("summary lacks approx_interval_95")
    return float(interval[0])
