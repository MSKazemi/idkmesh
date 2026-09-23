"""Marginal verifier evidence analysis for an existing review panel.

This module implements the first bounded product/research slice of issue #693.
It answers a deliberately narrow question:

    given a fixed ground-truthed verdict matrix and an already-selected panel,
    what changed historically when one additional verifier was added under the
    exact same gate rule?

The result is diagnostic decision support. It does not select a verifier,
dispatch work, create an EvaluatorPlan, accept a candidate, or grant merge
authority.

The implementation intentionally reuses idkmesh.gate_audit mathematics and
input validation. Headline contribution metrics exclude seeded known-bad probes;
probe effects are reported separately so a probe cannot silently improve or
degrade the ordinary panel estimate.

"Marginal evidence contribution" is contextual, not an intrinsic property of a
verifier. It depends on the current panel, candidate corpus, quorum rule, and
finite sample. A different panel or corpus can produce a different result.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable

from idkmesh import gate_audit

SCHEMA_ID = "marginal-evidence-report-v0.1"
AUTHORITY = "diagnostic_only"
MIN_REPLICATES = 100
DEFAULT_REPLICATES = 2000
DEFAULT_CONFIDENCE_LEVEL = 0.95
MIN_CANDIDATES_FOR_INFERENCE = 5
BOOTSTRAP_METHOD = (
    "paired candidate-level nonparametric bootstrap "
    "(percentile interval, linear interpolation)"
)
SAMPLING_UNIT = "non_probe_candidate_row"


class MarginalEvidenceInputError(ValueError):
    """The marginal-evidence request violates its explicit input contract."""


def _normalize_ids(
    name: str, values: Iterable[str] | None, *, allow_empty: bool = False
) -> tuple[str, ...]:
    if values is None:
        if allow_empty:
            return ()
        raise MarginalEvidenceInputError(f"{name} must be provided")
    if isinstance(values, (str, bytes)):
        raise MarginalEvidenceInputError(
            f"{name} must be a collection of verifier ids, not one string"
        )
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            raise MarginalEvidenceInputError(
                f"{name}[{index}] must be a non-empty string"
            )
        if value in seen:
            raise MarginalEvidenceInputError(
                f"{name} contains duplicate verifier id {value!r}"
            )
        seen.add(value)
        result.append(value)
    if not result and not allow_empty:
        raise MarginalEvidenceInputError(f"{name} must contain at least one verifier id")
    return tuple(result)


def _validate_bootstrap(bootstrap: dict[str, Any] | None) -> dict[str, Any] | None:
    if bootstrap is None:
        return None
    if not isinstance(bootstrap, dict):
        raise MarginalEvidenceInputError("bootstrap must be an object or null")

    unknown = sorted(
        set(bootstrap) - {"replicates", "seed", "confidence_level"}
    )
    if unknown:
        raise MarginalEvidenceInputError(
            "bootstrap contains unsupported key(s): " + ", ".join(unknown)
        )

    replicates = bootstrap.get("replicates", DEFAULT_REPLICATES)
    seed = bootstrap.get("seed", 0)
    confidence_level = bootstrap.get(
        "confidence_level", DEFAULT_CONFIDENCE_LEVEL
    )

    if (
        isinstance(replicates, bool)
        or not isinstance(replicates, int)
        or replicates < MIN_REPLICATES
    ):
        raise MarginalEvidenceInputError(
            f"bootstrap replicates must be an integer >= {MIN_REPLICATES}; "
            f"got {replicates!r}"
        )
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise MarginalEvidenceInputError(
            f"bootstrap seed must be an integer; got {seed!r}"
        )
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not (0.0 < confidence_level < 1.0)
    ):
        raise MarginalEvidenceInputError(
            "bootstrap confidence_level must be a finite number in (0, 1); "
            f"got {confidence_level!r}"
        )

    return {
        "replicates": replicates,
        "seed": seed,
        "confidence_level": float(confidence_level),
    }


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _subset_data(data: dict[str, Any], verifier_ids: tuple[str, ...]) -> dict[str, Any]:
    wanted = set(verifier_ids)
    selected = [ver for ver in data["verifiers"] if ver["id"] in wanted]
    subset = {key: value for key, value in data.items() if key != "verifiers"}
    subset["verifiers"] = selected
    return subset


def _non_probe_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in data["candidates"] if not c.get("probe", False)]


def _truth(data: dict[str, Any]) -> dict[str, str]:
    return {c["id"]: c["ground_truth"] for c in data["candidates"]}


def _verifier_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ver["id"]: ver for ver in data["verifiers"]}


def _panel_accepts(accept_votes: int, total: int, quorum: float) -> bool:
    return accept_votes > quorum * total


def _panel_decisions(
    data: dict[str, Any], verifier_ids: tuple[str, ...]
) -> dict[str, bool]:
    by_id = _verifier_map(data)
    quorum = float(data.get("quorum", 0.5))
    decisions: dict[str, bool] = {}
    for cand in _non_probe_candidates(data):
        accept_votes = sum(
            1
            for verifier_id in verifier_ids
            if by_id[verifier_id]["verdicts"][cand["id"]] == "accept"
        )
        decisions[cand["id"]] = _panel_accepts(
            accept_votes, len(verifier_ids), quorum
        )
    return decisions


def _candidate_error_vector(
    data: dict[str, Any], verifier_id: str
) -> list[int]:
    by_id = _verifier_map(data)
    verifier = by_id[verifier_id]
    truth = _truth(data)
    return [
        0 if verifier["verdicts"][cand["id"]] == truth[cand["id"]] else 1
        for cand in _non_probe_candidates(data)
    ]


def _pairwise_correlations(
    data: dict[str, Any],
    current_verifier_ids: tuple[str, ...],
    candidate_verifier_id: str,
) -> tuple[list[dict[str, Any]], float | None]:
    candidate_errors = _candidate_error_vector(data, candidate_verifier_id)
    rows: list[dict[str, Any]] = []
    measured: list[float] = []

    for current_id in current_verifier_ids:
        value = gate_audit.phi(
            candidate_errors, _candidate_error_vector(data, current_id)
        )
        correlation = None if math.isnan(value) else value
        rows.append(
            {
                "current_verifier_id": current_id,
                "error_correlation": correlation,
            }
        )
        if correlation is not None:
            measured.append(correlation)

    mean = (math.fsum(measured) / len(measured)) if measured else None
    return rows, mean


def _panel_truth_state(accepted: bool, ground_truth: str) -> bool:
    return (accepted and ground_truth == "accept") or (
        not accepted and ground_truth == "reject"
    )


def _candidate_transition_counts(
    data: dict[str, Any],
    current_verifier_ids: tuple[str, ...],
    augmented_verifier_ids: tuple[str, ...],
    candidate_verifier_id: str,
) -> dict[str, int]:
    current = _panel_decisions(data, current_verifier_ids)
    augmented = _panel_decisions(data, augmented_verifier_ids)
    by_id = _verifier_map(data)
    truth = _truth(data)
    verifier = by_id[candidate_verifier_id]

    unique_correct = 0
    unique_error = 0
    changed = 0
    changed_to_correct = 0
    changed_to_wrong = 0

    for cand in _non_probe_candidates(data):
        cid = cand["id"]
        current_correct = _panel_truth_state(current[cid], truth[cid])
        augmented_correct = _panel_truth_state(augmented[cid], truth[cid])
        candidate_correct = verifier["verdicts"][cid] == truth[cid]

        if not current_correct and candidate_correct:
            unique_correct += 1
        if current_correct and not candidate_correct:
            unique_error += 1
        if current[cid] != augmented[cid]:
            changed += 1
            if augmented_correct:
                changed_to_correct += 1
            else:
                changed_to_wrong += 1

    return {
        "candidate_correct_on_current_panel_errors": unique_correct,
        "candidate_wrong_on_current_panel_correct_rows": unique_error,
        "panel_decisions_changed": changed,
        "panel_decisions_changed_to_correct": changed_to_correct,
        "panel_decisions_changed_to_wrong": changed_to_wrong,
    }


def _probe_effect(
    current_report: dict[str, Any], augmented_report: dict[str, Any]
) -> dict[str, Any] | None:
    current = current_report["probes"]
    augmented = augmented_report["probes"]
    if current is None and augmented is None:
        return None
    if current is None or augmented is None:
        raise RuntimeError("probe population changed between panel calculations")
    return {
        "total": current["total"],
        "current_breached": current["breached"],
        "augmented_breached": augmented["breached"],
        "breaches_prevented": current["breached"] - augmented["breached"],
        "current_breach_rate": current["breach_rate"],
        "augmented_breach_rate": augmented["breach_rate"],
    }


def _point_delta_effective_votes(
    current_effective: float | None,
    augmented_effective: float | None,
) -> tuple[float | None, list[str]]:
    reasons: list[str] = []
    if current_effective is None:
        reasons.append("current_effective_votes_undefined")
    elif gate_audit.is_saturated(current_effective):
        reasons.append("current_effective_votes_censored")

    if augmented_effective is None:
        reasons.append("augmented_effective_votes_undefined")
    elif gate_audit.is_saturated(augmented_effective):
        reasons.append("augmented_effective_votes_censored")

    if reasons:
        return None, reasons
    return augmented_effective - current_effective, reasons


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    frac = pos - lo
    return sorted_values[lo] + frac * (
        sorted_values[hi] - sorted_values[lo]
    )


def _interval(
    values: list[float], confidence_level: float
) -> tuple[float, float]:
    ordered = sorted(values)
    alpha = (1.0 - confidence_level) / 2.0
    return (
        _quantile(ordered, alpha),
        _quantile(ordered, 1.0 - alpha),
    )


def _metric_interval(
    point: float | None,
    values: list[float],
    replicates: int,
    confidence_level: float,
) -> dict[str, Any]:
    section = {
        "point": point,
        "ci_low": None,
        "ci_high": None,
        "replicates_used": len(values),
        "replicates_undefined": replicates - len(values),
    }
    if values:
        low, high = _interval(values, confidence_level)
        section["ci_low"] = low
        section["ci_high"] = high
    return section


def _precompute_panel_rows(
    data: dict[str, Any], verifier_ids: tuple[str, ...]
) -> tuple[list[list[int]], list[int]]:
    candidates = _non_probe_candidates(data)
    truth = _truth(data)
    by_id = _verifier_map(data)
    quorum = float(data.get("quorum", 0.5))

    error_bits: list[list[int]] = []
    for verifier_id in verifier_ids:
        verifier = by_id[verifier_id]
        error_bits.append(
            [
                0 if verifier["verdicts"][c["id"]] == truth[c["id"]] else 1
                for c in candidates
            ]
        )

    panel_wrong: list[int] = []
    for c in candidates:
        accepts = sum(
            1
            for verifier_id in verifier_ids
            if by_id[verifier_id]["verdicts"][c["id"]] == "accept"
        )
        accepted = _panel_accepts(accepts, len(verifier_ids), quorum)
        correct = _panel_truth_state(accepted, c["ground_truth"])
        panel_wrong.append(0 if correct else 1)
    return error_bits, panel_wrong


def _replicate_effective_votes(
    error_bits: list[list[int]],
    panel_wrong: list[int],
    draw: list[int],
    quorum: float,
) -> tuple[float, float | None]:
    n = len(draw)
    accuracies = []
    for bits in error_bits:
        errors = sum(bits[i] for i in draw)
        accuracies.append(1.0 - errors / n)
    mean_accuracy = math.fsum(accuracies) / len(accuracies)
    panel_error = sum(panel_wrong[i] for i in draw) / n

    if mean_accuracy <= 0.5:
        return panel_error, None
    effective = gate_audit.effective_n(panel_error, mean_accuracy, quorum)
    if not math.isfinite(effective) or gate_audit.is_saturated(effective):
        return panel_error, None
    return panel_error, effective


def _bootstrap_candidate(
    data: dict[str, Any],
    current_verifier_ids: tuple[str, ...],
    augmented_verifier_ids: tuple[str, ...],
    *,
    point_panel_error_delta: float,
    point_effective_votes_delta: float | None,
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    non_probe = _non_probe_candidates(data)
    n = len(non_probe)
    replicates = params["replicates"]
    confidence_level = params["confidence_level"]

    if n < MIN_CANDIDATES_FOR_INFERENCE:
        return {
            "method": BOOTSTRAP_METHOD,
            "sampling_unit": SAMPLING_UNIT,
            "confidence_level": confidence_level,
            "replicates": replicates,
            "seed": params["seed"],
            "non_probe_candidates": n,
            "min_candidates_for_inference": MIN_CANDIDATES_FOR_INFERENCE,
            "sufficient_for_inference": False,
            "panel_error_delta": None,
            "effective_votes_delta": None,
        }, [
            f"bootstrap skipped: {n} non-probe candidate(s) is below the "
            f"minimum of {MIN_CANDIDATES_FOR_INFERENCE}"
        ]

    current_bits, current_wrong = _precompute_panel_rows(
        data, current_verifier_ids
    )
    augmented_bits, augmented_wrong = _precompute_panel_rows(
        data, augmented_verifier_ids
    )
    quorum = float(data.get("quorum", 0.5))
    rng = random.Random(params["seed"])

    error_deltas: list[float] = []
    effective_deltas: list[float] = []

    for _ in range(replicates):
        draw = [rng.randrange(n) for _ in range(n)]
        current_error, current_effective = _replicate_effective_votes(
            current_bits, current_wrong, draw, quorum
        )
        augmented_error, augmented_effective = _replicate_effective_votes(
            augmented_bits, augmented_wrong, draw, quorum
        )
        error_deltas.append(current_error - augmented_error)
        if current_effective is not None and augmented_effective is not None:
            effective_deltas.append(augmented_effective - current_effective)

    warnings: list[str] = []
    effective_section = _metric_interval(
        point_effective_votes_delta,
        effective_deltas,
        replicates,
        confidence_level,
    )
    if not effective_deltas:
        warnings.append(
            "bootstrap effective-vote delta is undefined for every replicate "
            "(a panel mean accuracy failed the >0.5 screen, or an effective-"
            "vote estimate reached the table-resolution censoring boundary)"
        )

    return {
        "method": BOOTSTRAP_METHOD,
        "sampling_unit": SAMPLING_UNIT,
        "confidence_level": confidence_level,
        "replicates": replicates,
        "seed": params["seed"],
        "non_probe_candidates": n,
        "min_candidates_for_inference": MIN_CANDIDATES_FOR_INFERENCE,
        "sufficient_for_inference": True,
        "panel_error_delta": _metric_interval(
            point_panel_error_delta,
            error_deltas,
            replicates,
            confidence_level,
        ),
        "effective_votes_delta": effective_section,
    }, warnings


def _candidate_row(
    data: dict[str, Any],
    current_verifier_ids: tuple[str, ...],
    candidate_verifier_id: str,
    current_report: dict[str, Any],
    *,
    bootstrap: dict[str, Any] | None,
) -> dict[str, Any]:
    augmented_ids = current_verifier_ids + (candidate_verifier_id,)
    augmented_report = gate_audit.audit(_subset_data(data, augmented_ids))
    current_panel = current_report["panel"]
    augmented_panel = augmented_report["panel"]

    effective_delta, unresolved_reasons = _point_delta_effective_votes(
        current_panel["effective_votes"],
        augmented_panel["effective_votes"],
    )

    n_non_probe = len(_non_probe_candidates(data))
    if n_non_probe < MIN_CANDIDATES_FOR_INFERENCE:
        unresolved_reasons.append("insufficient_non_probe_candidates_for_inference")

    pairwise, mean_correlation = _pairwise_correlations(
        data, current_verifier_ids, candidate_verifier_id
    )
    measurable = sum(
        1 for row in pairwise if row["error_correlation"] is not None
    )
    if measurable == 0:
        unresolved_reasons.append("candidate_error_correlation_unmeasurable")

    candidate_errors = _candidate_error_vector(data, candidate_verifier_id)
    candidate_accuracy = 1.0 - sum(candidate_errors) / len(candidate_errors)
    panel_error_delta = current_panel["error"] - augmented_panel["error"]

    row: dict[str, Any] = {
        "id": candidate_verifier_id,
        "status": "unresolved" if unresolved_reasons else "measured",
        "unresolved_reasons": sorted(set(unresolved_reasons)),
        "standalone_accuracy": candidate_accuracy,
        "current_panel_error": current_panel["error"],
        "augmented_panel_error": augmented_panel["error"],
        "panel_error_delta": panel_error_delta,
        "current_effective_votes": current_panel["effective_votes"],
        "augmented_effective_votes": augmented_panel["effective_votes"],
        "delta_effective_votes": effective_delta,
        "current_effective_votes_censored": gate_audit.is_saturated(
            current_panel["effective_votes"]
        ),
        "augmented_effective_votes_censored": gate_audit.is_saturated(
            augmented_panel["effective_votes"]
        ),
        "mean_error_correlation_with_current_panel": mean_correlation,
        "pairwise_error_correlations": pairwise,
        "transition_counts": _candidate_transition_counts(
            data,
            current_verifier_ids,
            augmented_ids,
            candidate_verifier_id,
        ),
        "probe_effect": _probe_effect(current_report, augmented_report),
        "uncertainty": None,
        "warnings": [],
    }

    if panel_error_delta < 0:
        row["warnings"].append(
            "adding this verifier increased panel error on the audited "
            "non-probe candidate set under the declared quorum rule"
        )
    if row["transition_counts"]["panel_decisions_changed"] == 0:
        row["warnings"].append(
            "adding this verifier changed no panel decision on the audited "
            "non-probe candidate set"
        )
    if measurable == 0:
        row["warnings"].append(
            "candidate/current error dependence is unmeasurable on this "
            "candidate set because no pair had variance in both error vectors"
        )

    if bootstrap is not None:
        uncertainty, warnings = _bootstrap_candidate(
            data,
            current_verifier_ids,
            augmented_ids,
            point_panel_error_delta=panel_error_delta,
            point_effective_votes_delta=effective_delta,
            params=bootstrap,
        )
        row["uncertainty"] = uncertainty
        row["warnings"].extend(warnings)

    return row


def analyze(
    data: dict[str, Any],
    *,
    current_verifier_ids: Iterable[str],
    candidate_verifier_ids: Iterable[str] | None = None,
    bootstrap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure add-one verifier contribution against one fixed verdict matrix.

    The caller chooses the current panel. If candidate_verifier_ids is omitted,
    every verifier not already in the current panel is analyzed.

    Candidate rows are reported in source-matrix verifier order. No row is
    ranked or selected automatically.
    """
    try:
        gate_audit.validate_input(data)
    except gate_audit.GateAuditInputError as exc:
        raise MarginalEvidenceInputError(str(exc)) from exc

    current_ids = _normalize_ids("current_verifier_ids", current_verifier_ids)
    by_id = _verifier_map(data)
    known_ids = set(by_id)
    unknown_current = sorted(set(current_ids) - known_ids)
    if unknown_current:
        raise MarginalEvidenceInputError(
            "current_verifier_ids contains unknown verifier(s): "
            + ", ".join(unknown_current)
        )

    # Panel membership is a set for this diagnostic; canonicalize it to the
    # source-matrix order so equivalent CLI argument orderings produce the
    # same report and analysis provenance digest.
    requested_current = set(current_ids)
    current_ids = tuple(
        ver["id"] for ver in data["verifiers"] if ver["id"] in requested_current
    )

    if candidate_verifier_ids is None:
        current_set = set(current_ids)
        candidate_ids = tuple(
            ver["id"] for ver in data["verifiers"] if ver["id"] not in current_set
        )
        if not candidate_ids:
            raise MarginalEvidenceInputError(
                "no candidate verifiers remain outside the current panel"
            )
    else:
        requested_candidates = _normalize_ids(
            "candidate_verifier_ids", candidate_verifier_ids
        )
        unknown_candidates = sorted(set(requested_candidates) - known_ids)
        if unknown_candidates:
            raise MarginalEvidenceInputError(
                "candidate_verifier_ids contains unknown verifier(s): "
                + ", ".join(unknown_candidates)
            )
        overlap = sorted(set(current_ids) & set(requested_candidates))
        if overlap:
            raise MarginalEvidenceInputError(
                "a verifier cannot be both current and candidate: "
                + ", ".join(overlap)
            )
        requested = set(requested_candidates)
        candidate_ids = tuple(
            ver["id"] for ver in data["verifiers"] if ver["id"] in requested
        )

    bootstrap_params = _validate_bootstrap(bootstrap)
    current_data = _subset_data(data, current_ids)
    current_report = gate_audit.audit(current_data)

    rows = [
        _candidate_row(
            data,
            current_ids,
            candidate_id,
            current_report,
            bootstrap=bootstrap_params,
        )
        for candidate_id in candidate_ids
    ]

    non_probe = _non_probe_candidates(data)
    probes = [c for c in data["candidates"] if c.get("probe", False)]
    analysis_config = {
        "current_verifier_ids": list(current_ids),
        "candidate_verifier_ids": list(candidate_ids),
        "bootstrap": bootstrap_params,
    }

    warnings = list(current_report["warnings"])
    if len(non_probe) < MIN_CANDIDATES_FOR_INFERENCE:
        warnings.append(
            f"{len(non_probe)} non-probe candidate(s) is below the "
            f"{MIN_CANDIDATES_FOR_INFERENCE}-candidate inference floor; point "
            "comparisons are reported but should not be treated as stable"
        )

    return {
        "schema": SCHEMA_ID,
        "gate_id": data["gate_id"],
        "evidence_class": data["evidence_class"],
        "authority": AUTHORITY,
        "analysis": {
            **analysis_config,
            "quorum": float(data.get("quorum", 0.5)),
            "non_probe_candidates": len(non_probe),
            "probe_candidates": len(probes),
        },
        "current_panel": {
            "nominal_votes": current_report["panel"]["nominal_votes"],
            "error": current_report["panel"]["error"],
            "mean_verifier_accuracy": current_report["panel"][
                "mean_verifier_accuracy"
            ],
            "mean_pairwise_error_correlation": current_report["panel"][
                "mean_pairwise_error_correlation"
            ],
            "effective_votes": current_report["panel"]["effective_votes"],
            "effective_votes_censored": gate_audit.is_saturated(
                current_report["panel"]["effective_votes"]
            ),
        },
        "candidates": rows,
        "warnings": warnings,
        "provenance": {
            "tool": "idkmesh marginal-evidence",
            "tool_version": _tool_version(),
            "input_digest_sha256": _canonical_digest(data),
            "analysis_digest_sha256": _canonical_digest(analysis_config),
        },
    }


def analyze_text(
    text: str,
    *,
    current_verifier_ids: Iterable[str],
    candidate_verifier_ids: Iterable[str] | None = None,
    bootstrap: dict[str, Any] | None = None,
    source: str = "input",
) -> dict[str, Any]:
    try:
        data = gate_audit.parse_input_text(text, source=source)
    except gate_audit.GateAuditInputError as exc:
        raise MarginalEvidenceInputError(str(exc)) from exc
    return analyze(
        data,
        current_verifier_ids=current_verifier_ids,
        candidate_verifier_ids=candidate_verifier_ids,
        bootstrap=bootstrap,
    )


def analyze_file(
    input_path: str | Path,
    *,
    current_verifier_ids: Iterable[str],
    candidate_verifier_ids: Iterable[str] | None = None,
    bootstrap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(input_path)
    try:
        data = gate_audit.load_input_file(path)
    except gate_audit.GateAuditInputError as exc:
        raise MarginalEvidenceInputError(str(exc)) from exc
    return analyze(
        data,
        current_verifier_ids=current_verifier_ids,
        candidate_verifier_ids=candidate_verifier_ids,
        bootstrap=bootstrap,
    )


def render_json(report: dict[str, Any], pretty: bool = False) -> str:
    return json.dumps(
        report,
        indent=2 if pretty else None,
        sort_keys=False,
        allow_nan=False,
    )


def _tool_version() -> str:
    from idkmesh import __version__

    return __version__
