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


_BETA_CF_MAX_ITERATIONS = 256
_BETA_CF_EPSILON = 3.0e-14
_BETA_CF_TINY = 1.0e-300
_BETA_QUANTILE_ITERATIONS = 80
_EQUAL_TAIL_MASS = 0.95
_EQUAL_TAIL_LOWER_PROBABILITY = (1.0 - _EQUAL_TAIL_MASS) / 2.0
_EQUAL_TAIL_UPPER_PROBABILITY = 1.0 - _EQUAL_TAIL_LOWER_PROBABILITY
_LEGACY_NORMAL_Z_95 = 1.96


def _beta_continued_fraction(alpha: float, beta: float, x: float) -> float:
    """Evaluate the continued fraction used by the regularized incomplete beta."""
    combined = alpha + beta
    alpha_plus_one = alpha + 1.0
    alpha_minus_one = alpha - 1.0
    c = 1.0
    d = 1.0 - combined * x / alpha_plus_one
    if abs(d) < _BETA_CF_TINY:
        d = _BETA_CF_TINY
    d = 1.0 / d
    value = d

    for iteration in range(1, _BETA_CF_MAX_ITERATIONS + 1):
        doubled = 2 * iteration
        coefficient = (
            iteration
            * (beta - iteration)
            * x
            / ((alpha_minus_one + doubled) * (alpha + doubled))
        )
        d = 1.0 + coefficient * d
        if abs(d) < _BETA_CF_TINY:
            d = _BETA_CF_TINY
        c = 1.0 + coefficient / c
        if abs(c) < _BETA_CF_TINY:
            c = _BETA_CF_TINY
        d = 1.0 / d
        value *= d * c

        coefficient = -(
            (alpha + iteration)
            * (combined + iteration)
            * x
            / ((alpha + doubled) * (alpha_plus_one + doubled))
        )
        d = 1.0 + coefficient * d
        if abs(d) < _BETA_CF_TINY:
            d = _BETA_CF_TINY
        c = 1.0 + coefficient / c
        if abs(c) < _BETA_CF_TINY:
            c = _BETA_CF_TINY
        d = 1.0 / d
        delta = d * c
        value *= delta
        if abs(delta - 1.0) <= _BETA_CF_EPSILON:
            return value

    raise ArithmeticError("regularized incomplete beta did not converge")


def _regularized_beta(x: float, alpha: float, beta: float) -> float:
    """Return I_x(alpha, beta) without an external numerical dependency."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    log_scale = (
        math.lgamma(alpha + beta)
        - math.lgamma(alpha)
        - math.lgamma(beta)
        + alpha * math.log(x)
        + beta * math.log1p(-x)
    )
    scale = math.exp(log_scale)

    if x < (alpha + 1.0) / (alpha + beta + 2.0):
        value = scale * _beta_continued_fraction(alpha, beta, x) / alpha
    else:
        value = 1.0 - scale * _beta_continued_fraction(beta, alpha, 1.0 - x) / beta
    return min(1.0, max(0.0, value))


def _beta_quantile(probability: float, alpha: float, beta: float) -> float:
    """Invert the regularized Beta CDF by deterministic bisection."""
    if probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0

    low = 0.0
    high = 1.0
    for _ in range(_BETA_QUANTILE_ITERATIONS):
        midpoint = (low + high) / 2.0
        if _regularized_beta(midpoint, alpha, beta) < probability:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0


def beta_binomial_summary(
    successes: int,
    trials: int,
    *,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    z: float = _LEGACY_NORMAL_Z_95,
) -> dict[str, Any]:
    """Return an inspectable Beta posterior summary for bounded evidence.

    The authoritative uncertainty interval is the exact equal-tail 95% credible
    interval of the Beta(alpha_prior + successes, beta_prior + failures)
    posterior. It is computed dependency-free by inverting the regularized
    incomplete beta function.

    ``z`` is retained only to reproduce the v1/v2 normal-approximation field.
    When it differs from 1.96, the generic ``legacy_normal_interval`` remains
    available but ``approx_interval_95`` becomes ``None`` so a non-95% interval
    cannot be mislabeled as 95% evidence.

    A mathematically valid prior posterior with zero trials is *not* empirical
    evidence. The summary therefore exposes the empirical rate separately and
    labels a zero-trial result as prior-only while preserving posterior fields
    for reproducibility and Bayesian composition.
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

    approximate_low = max(0.0, mean - z * sd)
    approximate_high = min(1.0, mean + z * sd)
    legacy_normal_interval = [round(approximate_low, 6), round(approximate_high, 6)]
    legacy_is_95 = math.isclose(z, _LEGACY_NORMAL_Z_95, rel_tol=0.0, abs_tol=1.0e-12)
    legacy_reference_mass = math.erf(z / math.sqrt(2.0))

    credible_low = _beta_quantile(_EQUAL_TAIL_LOWER_PROBABILITY, alpha, beta)
    credible_high = _beta_quantile(_EQUAL_TAIL_UPPER_PROBABILITY, alpha, beta)

    prior_mass = alpha_prior + beta_prior
    empirical_rate = successes / trials if trials else None
    evidence_status = "observed" if trials else "prior_only_no_observations"

    return {
        "model": "beta-binomial-v3",
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
        "credible_interval_95": [round(credible_low, 6), round(credible_high, 6)],
        "interval_method": "equal-tail-beta-posterior",
        "interval_mass": _EQUAL_TAIL_MASS,
        "legacy_normal_interval": legacy_normal_interval,
        "legacy_normal_z": z,
        "legacy_normal_reference_mass": round(legacy_reference_mass, 6),
        "approx_interval_95": legacy_normal_interval if legacy_is_95 else None,
        "approx_interval_method": "normal-approximation-to-beta-posterior",
        "posterior_concentration": round(total, 6),
        # Compatibility field retained from v1. This is prior + observed
        # concentration, not the number of empirical observations.
        "effective_sample_size": round(total, 6),
        "effective_sample_size_semantics": "beta_posterior_concentration_not_observed_sample_size",
    }


def conservative_lower_bound(summary: dict[str, Any]) -> float:
    interval = summary.get("credible_interval_95")
    if interval is None:
        interval = summary.get("approx_interval_95")
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("summary lacks a supported 95% posterior interval")
    return float(interval[0])
