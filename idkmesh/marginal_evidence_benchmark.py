"""Held-out benchmark for marginal verifier selection (issue #693).

The benchmark is intentionally diagnostic. It compares one preregistered
marginal-evidence selector with four simpler baselines, while keeping selection
and evaluation on disjoint candidate rows.

Selection is computed from the design matrix only. The holdout matrix is not
passed to any selector. The report contains no winner, routing decision,
EvaluatorPlan, acceptance verdict, or merge authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from idkmesh import gate_audit, marginal_evidence

CONFIG_SCHEMA_ID = "marginal-evidence-benchmark-config-v0.1"
REPORT_SCHEMA_ID = "marginal-evidence-benchmark-report-v0.1"
AUTHORITY = "diagnostic_only"
SELECTION_RULE_VERSION = "marginal-selection-interval-dominance-v0.1"

STRATEGY_MARGINAL = "marginal_effective_votes"
STRATEGY_RANDOM = "random_eligible"
STRATEGY_ACCURACY = "highest_standalone_accuracy"
STRATEGY_FAMILY = "different_family_first"
STRATEGY_CORRELATION = "minimum_mean_pairwise_error_correlation"
STRATEGIES = (
    STRATEGY_MARGINAL,
    STRATEGY_RANDOM,
    STRATEGY_ACCURACY,
    STRATEGY_FAMILY,
    STRATEGY_CORRELATION,
)

_REQUIRED_CONFIG_KEYS = {
    "schema",
    "benchmark_id",
    "design_matrix",
    "holdout_matrix",
    "current_verifier_ids",
    "candidate_verifier_ids",
    "verifier_families",
    "random_seed",
    "bootstrap",
}
_ALLOWED_CONFIG_KEYS = set(_REQUIRED_CONFIG_KEYS)


class MarginalEvidenceBenchmarkInputError(ValueError):
    """The benchmark input violates its explicit contract."""


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_json_constant(token: str) -> Any:
    raise MarginalEvidenceBenchmarkInputError(
        f"non-standard JSON constant {token!r} is not allowed"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MarginalEvidenceBenchmarkInputError(
                f"duplicate JSON key {key!r} is not allowed"
            )
        result[key] = value
    return result


def _parse_json_text(text: str, *, source: str) -> Any:
    text = text.removeprefix("\ufeff")
    try:
        return json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise MarginalEvidenceBenchmarkInputError(
            f"{source}: not valid JSON ({exc})"
        ) from exc
    except MarginalEvidenceBenchmarkInputError as exc:
        raise MarginalEvidenceBenchmarkInputError(f"{source}: {exc}") from exc


def _read_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarginalEvidenceBenchmarkInputError(
            f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})"
        ) from exc
    return _parse_json_text(text, source=str(path))


def _non_empty_string(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarginalEvidenceBenchmarkInputError(
            f"{path} must be a non-empty string"
        )
    return value


def _id_list(value: Any, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise MarginalEvidenceBenchmarkInputError(
            f"{path} must be a non-empty array"
        )
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        verifier_id = _non_empty_string(item, path=f"{path}[{index}]")
        if verifier_id in seen:
            raise MarginalEvidenceBenchmarkInputError(
                f"{path} contains duplicate verifier id {verifier_id!r}"
            )
        seen.add(verifier_id)
        result.append(verifier_id)
    return tuple(result)


def _bootstrap_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap must be an object"
        )
    unknown = sorted(set(value) - {"replicates", "seed", "confidence_level"})
    missing = sorted({"replicates", "seed", "confidence_level"} - set(value))
    if unknown:
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap contains unsupported key(s): " + ", ".join(unknown)
        )
    if missing:
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap is missing required key(s): " + ", ".join(missing)
        )

    replicates = value["replicates"]
    seed = value["seed"]
    confidence_level = value["confidence_level"]
    if (
        isinstance(replicates, bool)
        or not isinstance(replicates, int)
        or replicates < marginal_evidence.MIN_REPLICATES
    ):
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap.replicates must be an integer >= "
            f"{marginal_evidence.MIN_REPLICATES}"
        )
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap.seed must be an integer"
        )
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not (0.0 < confidence_level < 1.0)
    ):
        raise MarginalEvidenceBenchmarkInputError(
            "$.bootstrap.confidence_level must be a finite number in (0, 1)"
        )
    return {
        "replicates": replicates,
        "seed": seed,
        "confidence_level": float(confidence_level),
    }


def validate_config(value: Any) -> dict[str, Any]:
    """Validate and normalize the benchmark configuration."""
    if not isinstance(value, dict):
        raise MarginalEvidenceBenchmarkInputError(
            "benchmark config root must be an object"
        )
    unknown = sorted(set(value) - _ALLOWED_CONFIG_KEYS)
    missing = sorted(_REQUIRED_CONFIG_KEYS - set(value))
    if unknown:
        raise MarginalEvidenceBenchmarkInputError(
            "benchmark config contains unsupported key(s): "
            + ", ".join(unknown)
        )
    if missing:
        raise MarginalEvidenceBenchmarkInputError(
            "benchmark config is missing required key(s): " + ", ".join(missing)
        )
    if value["schema"] != CONFIG_SCHEMA_ID:
        raise MarginalEvidenceBenchmarkInputError(
            f"$.schema must be {CONFIG_SCHEMA_ID!r}"
        )

    benchmark_id = _non_empty_string(
        value["benchmark_id"], path="$.benchmark_id"
    )
    design_matrix = _non_empty_string(
        value["design_matrix"], path="$.design_matrix"
    )
    holdout_matrix = _non_empty_string(
        value["holdout_matrix"], path="$.holdout_matrix"
    )
    current_ids = _id_list(
        value["current_verifier_ids"], path="$.current_verifier_ids"
    )
    candidate_ids = _id_list(
        value["candidate_verifier_ids"], path="$.candidate_verifier_ids"
    )
    overlap = sorted(set(current_ids) & set(candidate_ids))
    if overlap:
        raise MarginalEvidenceBenchmarkInputError(
            "current_verifier_ids and candidate_verifier_ids overlap: "
            + ", ".join(overlap)
        )

    families = value["verifier_families"]
    if not isinstance(families, dict):
        raise MarginalEvidenceBenchmarkInputError(
            "$.verifier_families must be an object"
        )
    expected_family_ids = set(current_ids) | set(candidate_ids)
    if set(families) != expected_family_ids:
        missing_families = sorted(expected_family_ids - set(families))
        extra_families = sorted(set(families) - expected_family_ids)
        details: list[str] = []
        if missing_families:
            details.append("missing " + ", ".join(missing_families))
        if extra_families:
            details.append("unexpected " + ", ".join(extra_families))
        raise MarginalEvidenceBenchmarkInputError(
            "$.verifier_families must exactly cover current and candidate "
            "verifiers (" + "; ".join(details) + ")"
        )
    normalized_families: dict[str, str] = {}
    for verifier_id in sorted(families):
        normalized_families[verifier_id] = _non_empty_string(
            families[verifier_id],
            path=f"$.verifier_families[{verifier_id!r}]",
        )

    random_seed = value["random_seed"]
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise MarginalEvidenceBenchmarkInputError(
            "$.random_seed must be an integer"
        )

    return {
        "schema": CONFIG_SCHEMA_ID,
        "benchmark_id": benchmark_id,
        "design_matrix": design_matrix,
        "holdout_matrix": holdout_matrix,
        "current_verifier_ids": list(current_ids),
        "candidate_verifier_ids": list(candidate_ids),
        "verifier_families": normalized_families,
        "random_seed": random_seed,
        "bootstrap": _bootstrap_config(value["bootstrap"]),
    }


def load_config_file(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    return validate_config(_read_json_file(config_path))


def _resolve_child_path(config_path: Path, relative_value: str) -> Path:
    raw = Path(relative_value)
    if raw.is_absolute():
        raise MarginalEvidenceBenchmarkInputError(
            f"{config_path}: matrix paths must be relative to the config file"
        )
    base = config_path.resolve().parent
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise MarginalEvidenceBenchmarkInputError(
            f"{config_path}: matrix path {relative_value!r} escapes the "
            "configuration directory"
        ) from exc
    return resolved


def referenced_paths(config_path: str | Path) -> tuple[Path, Path, Path]:
    """Return config, design, and holdout paths after strict config validation."""
    path = Path(config_path)
    config = load_config_file(path)
    design_path = _resolve_child_path(path, config["design_matrix"])
    holdout_path = _resolve_child_path(path, config["holdout_matrix"])
    if design_path == holdout_path:
        raise MarginalEvidenceBenchmarkInputError(
            "design_matrix and holdout_matrix resolve to the same file"
        )
    return path.resolve(), design_path, holdout_path


def _load_matrix(path: Path) -> dict[str, Any]:
    try:
        return gate_audit.load_input_file(path)
    except gate_audit.GateAuditInputError as exc:
        raise MarginalEvidenceBenchmarkInputError(str(exc)) from exc


def _matrix_candidate_ids(data: dict[str, Any]) -> set[str]:
    return {candidate["id"] for candidate in data["candidates"]}


def _matrix_verifier_ids(data: dict[str, Any]) -> set[str]:
    return {verifier["id"] for verifier in data["verifiers"]}


def _validate_split_compatibility(
    design: dict[str, Any],
    holdout: dict[str, Any],
    config: dict[str, Any],
) -> None:
    if design["gate_id"] != holdout["gate_id"]:
        raise MarginalEvidenceBenchmarkInputError(
            "design and holdout matrices must use the same gate_id"
        )
    if design["evidence_class"] != holdout["evidence_class"]:
        raise MarginalEvidenceBenchmarkInputError(
            "design and holdout matrices must use the same evidence_class"
        )
    design_quorum = float(design.get("quorum", 0.5))
    holdout_quorum = float(holdout.get("quorum", 0.5))
    if design_quorum != holdout_quorum:
        raise MarginalEvidenceBenchmarkInputError(
            "design and holdout matrices must use the same quorum"
        )

    requested = set(config["current_verifier_ids"]) | set(
        config["candidate_verifier_ids"]
    )
    for name, data in (("design", design), ("holdout", holdout)):
        missing = sorted(requested - _matrix_verifier_ids(data))
        if missing:
            raise MarginalEvidenceBenchmarkInputError(
                f"{name} matrix is missing requested verifier(s): "
                + ", ".join(missing)
            )

    overlap = sorted(
        _matrix_candidate_ids(design) & _matrix_candidate_ids(holdout)
    )
    if overlap:
        preview = ", ".join(overlap[:5])
        suffix = "" if len(overlap) <= 5 else f" (+{len(overlap) - 5} more)"
        raise MarginalEvidenceBenchmarkInputError(
            "design and holdout candidate IDs must be disjoint; overlap: "
            + preview
            + suffix
        )


def _candidate_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return report["candidates"]


def _selector_result(
    strategy: str,
    *,
    selected_verifier_id: str | None,
    reason_code: str,
    design_score: float | None,
) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "status": "selected" if selected_verifier_id is not None else "unresolved",
        "selected_verifier_id": selected_verifier_id,
        "reason_code": reason_code,
        "design_score": design_score,
    }


def _select_random(
    rows: list[dict[str, Any]], random_seed: int
) -> dict[str, Any]:
    rng = random.Random(random_seed)
    selected = rows[rng.randrange(len(rows))]
    return _selector_result(
        STRATEGY_RANDOM,
        selected_verifier_id=selected["id"],
        reason_code="seeded_uniform_choice_over_canonical_candidate_order",
        design_score=None,
    )


def _select_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best = rows[0]
    for row in rows[1:]:
        if row["standalone_accuracy"] > best["standalone_accuracy"]:
            best = row
    return _selector_result(
        STRATEGY_ACCURACY,
        selected_verifier_id=best["id"],
        reason_code="highest_design_standalone_accuracy_then_source_order",
        design_score=best["standalone_accuracy"],
    )


def _select_family(
    rows: list[dict[str, Any]],
    *,
    current_ids: list[str],
    families: dict[str, str],
) -> dict[str, Any]:
    represented = {families[verifier_id] for verifier_id in current_ids}
    novel = [row for row in rows if families[row["id"]] not in represented]
    pool = novel if novel else rows

    best = pool[0]
    for row in pool[1:]:
        if row["standalone_accuracy"] > best["standalone_accuracy"]:
            best = row

    reason = (
        "unrepresented_family_then_design_accuracy_then_source_order"
        if novel
        else "no_unrepresented_family_design_accuracy_then_source_order"
    )
    return _selector_result(
        STRATEGY_FAMILY,
        selected_verifier_id=best["id"],
        reason_code=reason,
        design_score=best["standalone_accuracy"],
    )


def _select_correlation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(
        row["mean_error_correlation_with_current_panel"] is None
        for row in rows
    ):
        return _selector_result(
            STRATEGY_CORRELATION,
            selected_verifier_id=None,
            reason_code="candidate_error_correlation_unmeasurable",
            design_score=None,
        )

    best = rows[0]
    for row in rows[1:]:
        row_corr = row["mean_error_correlation_with_current_panel"]
        best_corr = best["mean_error_correlation_with_current_panel"]
        if row_corr < best_corr:
            best = row
        elif (
            row_corr == best_corr
            and row["standalone_accuracy"] > best["standalone_accuracy"]
        ):
            best = row

    return _selector_result(
        STRATEGY_CORRELATION,
        selected_verifier_id=best["id"],
        reason_code=(
            "minimum_design_mean_error_correlation_then_accuracy_then_source_order"
        ),
        design_score=best["mean_error_correlation_with_current_panel"],
    )


def _marginal_interval(row: dict[str, Any]) -> tuple[float, float] | None:
    uncertainty = row.get("uncertainty")
    if not isinstance(uncertainty, dict):
        return None
    if not uncertainty.get("sufficient_for_inference", False):
        return None
    section = uncertainty.get("effective_votes_delta")
    if not isinstance(section, dict):
        return None
    low = section.get("ci_low")
    high = section.get("ci_high")
    if not isinstance(low, (int, float)) or isinstance(low, bool):
        return None
    if not isinstance(high, (int, float)) or isinstance(high, bool):
        return None
    if not math.isfinite(float(low)) or not math.isfinite(float(high)):
        return None
    return float(low), float(high)


def _select_marginal(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unresolved = [
        row["id"]
        for row in rows
        if (
            row["status"] != "measured"
            or row["delta_effective_votes"] is None
            or _marginal_interval(row) is None
        )
    ]
    if unresolved:
        return _selector_result(
            STRATEGY_MARGINAL,
            selected_verifier_id=None,
            reason_code="unresolved_design_candidate_metrics",
            design_score=None,
        )

    top = rows[0]
    tied = False
    for row in rows[1:]:
        if row["delta_effective_votes"] > top["delta_effective_votes"]:
            top = row
            tied = False
        elif row["delta_effective_votes"] == top["delta_effective_votes"]:
            tied = True

    if tied:
        return _selector_result(
            STRATEGY_MARGINAL,
            selected_verifier_id=None,
            reason_code="marginal_point_estimate_tie",
            design_score=None,
        )

    if len(rows) > 1:
        top_interval = _marginal_interval(top)
        assert top_interval is not None
        other_highs = []
        for row in rows:
            if row["id"] == top["id"]:
                continue
            interval = _marginal_interval(row)
            assert interval is not None
            other_highs.append(interval[1])
        if top_interval[0] <= max(other_highs):
            return _selector_result(
                STRATEGY_MARGINAL,
                selected_verifier_id=None,
                reason_code="marginal_ordering_not_interval_separated",
                design_score=top["delta_effective_votes"],
            )

    return _selector_result(
        STRATEGY_MARGINAL,
        selected_verifier_id=top["id"],
        reason_code="largest_interval_separated_design_delta_effective_votes",
        design_score=top["delta_effective_votes"],
    )


def build_selection_plan(
    design: dict[str, Any],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build a selector plan from design evidence only.

    No holdout object is accepted by this function. That boundary is
    intentional and tested: holdout verdicts cannot influence selection.
    """
    normalized = validate_config(config)
    try:
        design_report = marginal_evidence.analyze(
            design,
            current_verifier_ids=normalized["current_verifier_ids"],
            candidate_verifier_ids=normalized["candidate_verifier_ids"],
            bootstrap=normalized["bootstrap"],
        )
    except marginal_evidence.MarginalEvidenceInputError as exc:
        raise MarginalEvidenceBenchmarkInputError(str(exc)) from exc

    rows = _candidate_rows(design_report)
    current_ids = design_report["analysis"]["current_verifier_ids"]
    canonical_candidate_ids = design_report["analysis"]["candidate_verifier_ids"]

    selectors = [
        _select_marginal(rows),
        _select_random(rows, normalized["random_seed"]),
        _select_accuracy(rows),
        _select_family(
            rows,
            current_ids=current_ids,
            families=normalized["verifier_families"],
        ),
        _select_correlation(rows),
    ]
    plan_core = {
        "rule_version": SELECTION_RULE_VERSION,
        "source": "design_only",
        "current_verifier_ids": current_ids,
        "candidate_verifier_ids": canonical_candidate_ids,
        "selectors": selectors,
    }
    return {
        **plan_core,
        "digest_sha256": _canonical_digest(plan_core),
        "design_report": design_report,
    }


def _holdout_result(
    strategy: dict[str, Any],
    *,
    holdout: dict[str, Any],
    current_ids: list[str],
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    selected_id = strategy["selected_verifier_id"]
    if selected_id is None:
        return {
            "strategy": strategy["strategy"],
            "selection_status": strategy["status"],
            "selected_verifier_id": None,
            "status": "not_evaluated",
            "holdout_candidate_status": None,
            "panel_error_delta": None,
            "delta_effective_votes": None,
            "standalone_accuracy": None,
            "mean_error_correlation_with_current_panel": None,
            "uncertainty": None,
            "probe_effect": None,
            "warnings": [
                "strategy was unresolved on design evidence; holdout was not "
                "used to choose a fallback candidate"
            ],
        }

    try:
        report = marginal_evidence.analyze(
            holdout,
            current_verifier_ids=current_ids,
            candidate_verifier_ids=[selected_id],
            bootstrap=bootstrap,
        )
    except marginal_evidence.MarginalEvidenceInputError as exc:
        raise MarginalEvidenceBenchmarkInputError(str(exc)) from exc
    row = report["candidates"][0]
    status = (
        "evaluated"
        if row["status"] == "measured"
        else "evaluated_with_unresolved_metrics"
    )
    return {
        "strategy": strategy["strategy"],
        "selection_status": strategy["status"],
        "selected_verifier_id": selected_id,
        "status": status,
        "holdout_candidate_status": row["status"],
        "panel_error_delta": row["panel_error_delta"],
        "delta_effective_votes": row["delta_effective_votes"],
        "standalone_accuracy": row["standalone_accuracy"],
        "mean_error_correlation_with_current_panel": row[
            "mean_error_correlation_with_current_panel"
        ],
        "uncertainty": row["uncertainty"],
        "probe_effect": row["probe_effect"],
        "warnings": row["warnings"],
    }


def benchmark(
    design: dict[str, Any],
    holdout: dict[str, Any],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Compare preregistered design-only selectors on held-out rows."""
    normalized = validate_config(config)
    try:
        gate_audit.validate_input(design)
        gate_audit.validate_input(holdout)
    except gate_audit.GateAuditInputError as exc:
        raise MarginalEvidenceBenchmarkInputError(str(exc)) from exc

    _validate_split_compatibility(design, holdout, normalized)
    plan = build_selection_plan(design, config=normalized)
    design_report = plan["design_report"]
    selectors = plan["selectors"]

    current_ids = design_report["analysis"]["current_verifier_ids"]
    holdout_results = [
        _holdout_result(
            selector,
            holdout=holdout,
            current_ids=current_ids,
            bootstrap=normalized["bootstrap"],
        )
        for selector in selectors
    ]

    plan_public = {
        key: value for key, value in plan.items() if key != "design_report"
    }
    analysis_config = {
        "current_verifier_ids": current_ids,
        "candidate_verifier_ids": design_report["analysis"][
            "candidate_verifier_ids"
        ],
        "verifier_families": {
            verifier_id: normalized["verifier_families"][verifier_id]
            for verifier_id in current_ids
            + design_report["analysis"]["candidate_verifier_ids"]
        },
        "random_seed": normalized["random_seed"],
        "bootstrap": normalized["bootstrap"],
        "selection_rule_version": SELECTION_RULE_VERSION,
    }

    return {
        "schema": REPORT_SCHEMA_ID,
        "benchmark_id": normalized["benchmark_id"],
        "gate_id": design["gate_id"],
        "evidence_class": design["evidence_class"],
        "authority": AUTHORITY,
        "analysis": analysis_config,
        "splits": {
            "design": {
                "matrix": normalized["design_matrix"],
                "input_digest_sha256": _canonical_digest(design),
                "non_probe_candidates": design_report["analysis"][
                    "non_probe_candidates"
                ],
                "probe_candidates": design_report["analysis"][
                    "probe_candidates"
                ],
            },
            "holdout": {
                "matrix": normalized["holdout_matrix"],
                "input_digest_sha256": _canonical_digest(holdout),
                "non_probe_candidates": len(
                    [
                        candidate
                        for candidate in holdout["candidates"]
                        if not candidate.get("probe", False)
                    ]
                ),
                "probe_candidates": len(
                    [
                        candidate
                        for candidate in holdout["candidates"]
                        if candidate.get("probe", False)
                    ]
                ),
            },
        },
        "selection_plan": plan_public,
        "holdout_results": holdout_results,
        "warnings": (
            list(design_report["warnings"])
            + [
                "holdout outcomes are evaluation evidence only; they did not "
                "participate in selector construction or fallback selection"
            ]
        ),
        "provenance": {
            "tool": "idkmesh marginal-evidence-benchmark",
            "tool_version": _tool_version(),
            "config_digest_sha256": _canonical_digest(normalized),
            "selection_plan_digest_sha256": plan_public["digest_sha256"],
        },
    }


def benchmark_file(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    config = load_config_file(path)
    _, design_path, holdout_path = referenced_paths(path)
    design = _load_matrix(design_path)
    holdout = _load_matrix(holdout_path)
    return benchmark(design, holdout, config=config)


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
