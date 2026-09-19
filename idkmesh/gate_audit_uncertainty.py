"""Finite-sample uncertainty for gate-audit panel metrics (issue #520).

``idkmesh/gate_audit.py`` reports panel error, mean verifier accuracy, mean
pairwise error correlation and effective votes as point estimates from one
fixed candidate sample. A small or unrepresentative sample can make those
numbers unstable even though each one looks precise to four decimal places.
This module adds an optional, deterministic bootstrap that quantifies that
instability. It changes nothing about the existing ``gate-audit-report-v0.1``
document: it activates only when a caller opts in, and its output lives in a
new ``gate-audit-report-v0.2`` document that a v0.1 consumer never sees.

**Method.** Nonparametric bootstrap, resampling whole *candidate rows* with
replacement — never individual verifier cells. Every replicate therefore
keeps the real cross-verifier dependence structure for whichever candidates
it happened to draw, which is the property the audit exists to measure;
resampling cells independently would destroy exactly that and manufacture a
false independence result. Confidence intervals are percentile intervals
using linear interpolation between order statistics (NumPy's ``"linear"``
method, R's type 7).

A fixed seed reproduces the identical interval on a fixed Python
interpreter. Across interpreter versions, ``mean_pairwise_error_correlation``
can differ in the last representable bit: it is computed through
``gate_audit.phi`` (unchanged v0.1 code, called thousands of times per
audit), whose float summation inherits whatever the ``sum()`` builtin does —
and that algorithm changed in Python 3.12 (compensated summation replaced
naive addition). This module's own averaging uses ``math.fsum``, stable
across versions, so the effect is confined to that one field.

**What this interval is conditional on.** A bootstrap interval describes
resampling stability of the *observed* candidate set, nothing more. It is a
valid inferential interval only under the assumption that the audited
candidates are exchangeable draws from the population the report's claim is
about; a set curated by difficulty, topic, recency, or any other selection
rule does not satisfy that, and the matrix alone cannot tell this module
whether it does. A narrow interval is evidence that the *panel numbers* are
stable under resampling — never evidence that the verifiers are independent,
and never evidence that the candidate set is representative.

**Failure modes, defined rather than left to numeric accident:**

- Fewer than ``MIN_CANDIDATES_FOR_INFERENCE`` non-probe candidates: the
  bootstrap is skipped outright (``sufficient_for_inference: false``, every
  metric section ``null``) rather than reporting a percentile interval built
  from too few distinct resamples to mean anything.
- A replicate where mean verifier accuracy does not exceed chance: its
  effective-votes contribution is undefined for that replicate — excluded
  from that metric's interval and counted in ``replicates_undefined``, not
  coerced to a misleading number.
- A replicate where no verifier pair has variance in both error vectors: its
  correlation contribution is undefined for that replicate — same treatment.
- If every replicate is undefined for a metric, its interval is ``null`` and
  a warning is emitted; the metric is never silently omitted.
- A replicate's effective-votes value can itself hit the same table-max
  censoring ``gate_audit.is_saturated`` defines for the point estimate; when
  the interval's upper bound lands there, ``ci_high_censored`` marks it so a
  reader cannot mistake a resolution limit for a resolved interval bound.

Zero panel error, a perfect verifier, and a small-but-sufficient candidate
count all fall out of this design without special-casing: a candidate set on
which the panel never errs resamples to panel error 0 in every replicate, so
its interval degenerates to a point rather than raising anything.
"""

from __future__ import annotations

import itertools
import math
import random
from typing import Any

from idkmesh.gate_audit import GateAuditInputError, effective_n, is_saturated, phi

SCHEMA_ID_V02 = "gate-audit-report-v0.2"
METHOD = ("candidate-level nonparametric bootstrap "
          "(percentile interval, linear interpolation)")
SAMPLING_UNIT = "non_probe_candidate_row"
DEFAULT_REPLICATES = 2000
DEFAULT_CONFIDENCE_LEVEL = 0.95
MIN_REPLICATES = 100
MIN_CANDIDATES_FOR_INFERENCE = 5


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation quantile of an already-sorted, non-empty list.

    This is NumPy's default (``"linear"``) method and R's type 7: interpolate
    between the two order statistics bracketing position ``q * (n - 1)``. Any
    other method (nearest-rank, Hazen, etc.) would shift interval edges by a
    fraction of a replicate spacing — small, but a silently different
    estimator than the one this module documents.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    frac = pos - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _interval(values: list[float], confidence_level: float) -> tuple[float, float]:
    alpha = (1.0 - confidence_level) / 2.0
    ordered = sorted(values)
    return _quantile(ordered, alpha), _quantile(ordered, 1.0 - alpha)


def _metric_section(point: Any, replicate_values: list[float], replicates: int,
                     confidence_level: float, *, censor: bool = False
                     ) -> dict[str, Any]:
    used = len(replicate_values)
    section: dict[str, Any] = {
        "point": point,
        "ci_low": None,
        "ci_high": None,
        "replicates_used": used,
        "replicates_undefined": replicates - used,
    }
    if censor:
        section["ci_high_censored"] = False
    if used == 0:
        return section
    ci_low, ci_high = _interval(replicate_values, confidence_level)
    section["ci_low"] = ci_low
    section["ci_high"] = ci_high
    if censor:
        section["ci_high_censored"] = is_saturated(ci_high)
    return section


def _validate_params(replicates: int, seed: int, confidence_level: float) -> None:
    if isinstance(replicates, bool) or not isinstance(replicates, int) \
            or replicates < MIN_REPLICATES:
        raise GateAuditInputError(
            f"bootstrap replicates must be an integer >= {MIN_REPLICATES} "
            f"(fewer cannot resolve a percentile interval); got {replicates!r}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise GateAuditInputError(f"bootstrap seed must be an integer, got {seed!r}")
    if (isinstance(confidence_level, bool)
            or not isinstance(confidence_level, (int, float))
            or not math.isfinite(confidence_level)
            or not (0.0 < confidence_level < 1.0)):
        raise GateAuditInputError(
            "bootstrap confidence_level must be a number in (0, 1), got "
            f"{confidence_level!r}")


def compute(data: dict[str, Any], *, quorum: float, point_estimates: dict[str, Any],
            replicates: int = DEFAULT_REPLICATES, seed: int,
            confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
            ) -> tuple[dict[str, Any], list[str]]:
    """Bootstrap the panel metrics from an already-validated verdict matrix.

    ``data`` must already have passed ``gate_audit.validate_input``.
    ``point_estimates`` carries the exact values already computed by
    ``gate_audit.audit`` (``panel_error``, ``mean_verifier_accuracy``,
    ``mean_pairwise_error_correlation``, ``effective_votes``) so the reported
    point never drifts from a second computation of the same statistic.

    Returns ``(uncertainty, warnings)``: a JSON-serializable object for the
    report's ``uncertainty`` field, and warning strings to merge into
    ``report.warnings``.
    """
    _validate_params(replicates, seed, confidence_level)

    candidates = data["candidates"]
    verifiers = data["verifiers"]
    non_probe = [c for c in candidates if not c.get("probe", False)]
    truth = {c["id"]: c["ground_truth"] for c in candidates}
    n = len(non_probe)
    n_verifiers = len(verifiers)

    warnings: list[str] = []

    if n < MIN_CANDIDATES_FOR_INFERENCE:
        warnings.append(
            f"bootstrap uncertainty skipped: {n} non-probe candidate(s) is "
            f"below the minimum of {MIN_CANDIDATES_FOR_INFERENCE} needed for "
            "a resampling distribution to mean anything")
        return {
            "method": METHOD,
            "sampling_unit": SAMPLING_UNIT,
            "confidence_level": confidence_level,
            "replicates": replicates,
            "seed": seed,
            "non_probe_candidates": n,
            "min_candidates_for_inference": MIN_CANDIDATES_FOR_INFERENCE,
            "sufficient_for_inference": False,
            "panel_error": None,
            "mean_verifier_accuracy": None,
            "mean_pairwise_error_correlation": None,
            "effective_votes": None,
        }, warnings

    # Per-(verifier, candidate) correctness and the original panel decision
    # depend only on the fixed verdict matrix, never on which candidates a
    # replicate happens to draw — precomputed once so each replicate pays
    # only for the resampling itself, not for re-parsing the matrix.
    error_bits: list[list[int]] = [
        [0 if ver["verdicts"][c["id"]] == truth[c["id"]] else 1 for c in non_probe]
        for ver in verifiers
    ]
    panel_wrong: list[int] = []
    for c in non_probe:
        accept_votes = sum(
            1 for ver in verifiers if ver["verdicts"][c["id"]] == "accept")
        accepted = accept_votes > quorum * n_verifiers
        wrong = (accepted and c["ground_truth"] == "reject") or (
            not accepted and c["ground_truth"] == "accept")
        panel_wrong.append(1 if wrong else 0)

    rng = random.Random(seed)
    panel_error_values: list[float] = []
    accuracy_values: list[float] = []
    correlation_values: list[float] = []
    effective_votes_values: list[float] = []

    for _ in range(replicates):
        draw = [rng.randrange(n) for _ in range(n)]

        accuracies = []
        vectors = []
        for bits in error_bits:
            errs = [bits[i] for i in draw]
            vectors.append(errs)
            accuracies.append(1.0 - sum(errs) / n)
        # math.fsum, not the sum() builtin: sum() started using compensated
        # (Neumaier) summation for floats in Python 3.12, so the same
        # replicate can round to a different last bit on 3.11 vs 3.12/3.13 —
        # a real cross-version determinism break this project's protected
        # gate would actually hit (it runs both). math.fsum's algorithm has
        # been stable across all supported versions.
        mean_accuracy_rep = math.fsum(accuracies) / n_verifiers
        accuracy_values.append(mean_accuracy_rep)

        pair_values = []
        for a, b in itertools.combinations(range(n_verifiers), 2):
            value = phi(vectors[a], vectors[b])
            if not math.isnan(value):
                pair_values.append(value)
        if pair_values:
            correlation_values.append(math.fsum(pair_values) / len(pair_values))

        panel_error_rep = sum(panel_wrong[i] for i in draw) / n
        panel_error_values.append(panel_error_rep)

        if mean_accuracy_rep > 0.5:
            eff = effective_n(panel_error_rep, mean_accuracy_rep, quorum)
            if math.isfinite(eff):
                effective_votes_values.append(eff)

    sections = {
        "panel_error": _metric_section(
            point_estimates["panel_error"], panel_error_values, replicates,
            confidence_level),
        "mean_verifier_accuracy": _metric_section(
            point_estimates["mean_verifier_accuracy"], accuracy_values,
            replicates, confidence_level),
        "mean_pairwise_error_correlation": _metric_section(
            point_estimates["mean_pairwise_error_correlation"],
            correlation_values, replicates, confidence_level),
        "effective_votes": _metric_section(
            point_estimates["effective_votes"], effective_votes_values,
            replicates, confidence_level, censor=True),
    }

    if sections["mean_pairwise_error_correlation"]["replicates_used"] == 0:
        warnings.append(
            "bootstrap correlation interval is undefined for every "
            "replicate (fewer than two verifiers, or no verifier pair ever "
            "had variance in both error vectors on the resampled candidates)")
    if sections["effective_votes"]["replicates_used"] == 0:
        warnings.append(
            "bootstrap effective-votes interval is undefined for every "
            "replicate (mean verifier accuracy never exceeded chance on the "
            "resampled candidates)")

    uncertainty = {
        "method": METHOD,
        "sampling_unit": SAMPLING_UNIT,
        "confidence_level": confidence_level,
        "replicates": replicates,
        "seed": seed,
        "non_probe_candidates": n,
        "min_candidates_for_inference": MIN_CANDIDATES_FOR_INFERENCE,
        "sufficient_for_inference": True,
        "panel_error": sections["panel_error"],
        "mean_verifier_accuracy": sections["mean_verifier_accuracy"],
        "mean_pairwise_error_correlation": sections["mean_pairwise_error_correlation"],
        "effective_votes": sections["effective_votes"],
    }
    return uncertainty, warnings
