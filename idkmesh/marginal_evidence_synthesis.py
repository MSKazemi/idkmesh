"""Descriptive cross-cohort synthesis for marginal verifier benchmarks (#693).

This module combines already-frozen held-out benchmark reports produced by
:mod:`idkmesh.marginal_evidence_benchmark`. It does not rerun selection, inspect
raw verdict rows, tune thresholds, rank strategies, or create routing authority.

A synthesis manifest names the exact benchmark reports to include. Reports must
share the same evidence class and selection-rule version. Exact duplicate report,
design-split, or holdout-split digests are rejected so one cohort cannot be
silently counted twice. Cross-report row overlap cannot be proven from summary
reports alone and is therefore stated as a limitation rather than guessed away.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from idkmesh import marginal_evidence_benchmark as benchmark

CONFIG_SCHEMA_ID = "marginal-evidence-synthesis-config-v0.1"
REPORT_SCHEMA_ID = "marginal-evidence-synthesis-report-v0.1"
AUTHORITY = "diagnostic_only"
ANALYSIS_MODE = "descriptive-cross-cohort-v0.1"

_REQUIRED_CONFIG_KEYS = {
    "schema",
    "synthesis_id",
    "evidence_class",
    "selection_rule_version",
    "benchmark_reports",
}


class MarginalEvidenceSynthesisInputError(ValueError):
    """The synthesis manifest or a referenced benchmark report is invalid."""


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
    raise MarginalEvidenceSynthesisInputError(
        f"non-standard JSON constant {token!r} is not allowed"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MarginalEvidenceSynthesisInputError(
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
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: not valid JSON ({exc})"
        ) from exc
    except MarginalEvidenceSynthesisInputError as exc:
        raise MarginalEvidenceSynthesisInputError(f"{source}: {exc}") from exc


def _read_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarginalEvidenceSynthesisInputError(
            f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})"
        ) from exc
    return _parse_json_text(text, source=str(path))


def _non_empty_string(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarginalEvidenceSynthesisInputError(
            f"{path} must be a non-empty string"
        )
    return value


def validate_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MarginalEvidenceSynthesisInputError(
            "synthesis config root must be an object"
        )
    unknown = sorted(set(value) - _REQUIRED_CONFIG_KEYS)
    missing = sorted(_REQUIRED_CONFIG_KEYS - set(value))
    if unknown:
        raise MarginalEvidenceSynthesisInputError(
            "synthesis config contains unsupported key(s): " + ", ".join(unknown)
        )
    if missing:
        raise MarginalEvidenceSynthesisInputError(
            "synthesis config is missing required key(s): " + ", ".join(missing)
        )
    if value["schema"] != CONFIG_SCHEMA_ID:
        raise MarginalEvidenceSynthesisInputError(
            f"$.schema must be {CONFIG_SCHEMA_ID!r}"
        )

    reports = value["benchmark_reports"]
    if not isinstance(reports, list) or len(reports) < 2:
        raise MarginalEvidenceSynthesisInputError(
            "$.benchmark_reports must contain at least two report paths"
        )
    normalized_reports: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(reports):
        path = _non_empty_string(item, path=f"$.benchmark_reports[{index}]")
        raw = Path(path)
        if raw.is_absolute():
            raise MarginalEvidenceSynthesisInputError(
                "benchmark report paths must be relative to the synthesis config"
            )
        if path in seen:
            raise MarginalEvidenceSynthesisInputError(
                f"duplicate benchmark report path {path!r}"
            )
        seen.add(path)
        normalized_reports.append(path)

    normalized = {
        "schema": CONFIG_SCHEMA_ID,
        "synthesis_id": _non_empty_string(
            value["synthesis_id"], path="$.synthesis_id"
        ),
        "evidence_class": _non_empty_string(
            value["evidence_class"], path="$.evidence_class"
        ),
        "selection_rule_version": _non_empty_string(
            value["selection_rule_version"], path="$.selection_rule_version"
        ),
        "benchmark_reports": sorted(normalized_reports),
    }
    if normalized["selection_rule_version"] != benchmark.SELECTION_RULE_VERSION:
        raise MarginalEvidenceSynthesisInputError(
            "$.selection_rule_version must match the frozen v0.1 benchmark rule "
            f"{benchmark.SELECTION_RULE_VERSION!r}"
        )
    return normalized


def load_config_file(path: str | Path) -> dict[str, Any]:
    return validate_config(_read_json_file(Path(path)))


def referenced_paths(config_path: str | Path) -> tuple[Path, ...]:
    path = Path(config_path).resolve()
    config = load_config_file(path)
    base = path.parent
    resolved = [path]
    for raw_value in config["benchmark_reports"]:
        candidate = (base / raw_value).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise MarginalEvidenceSynthesisInputError(
                f"benchmark report path {raw_value!r} escapes the config directory"
            ) from exc
        resolved.append(candidate)
    if len(set(resolved[1:])) != len(resolved[1:]):
        raise MarginalEvidenceSynthesisInputError(
            "benchmark report paths must resolve to distinct files"
        )
    return tuple(resolved)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _sha256_text(value: Any, *, path: str) -> str:
    text = _non_empty_string(value, path=path)
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise MarginalEvidenceSynthesisInputError(
            f"{path} must be 64 lowercase hexadecimal characters"
        )
    return text


def _validate_benchmark_report(
    value: Any,
    *,
    expected_evidence_class: str,
    expected_rule_version: str,
    source: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: benchmark report root must be an object"
        )
    if value.get("schema") != benchmark.REPORT_SCHEMA_ID:
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: unsupported benchmark report schema"
        )
    if value.get("authority") != benchmark.AUTHORITY:
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: benchmark report must remain diagnostic_only"
        )
    if value.get("evidence_class") != expected_evidence_class:
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: evidence_class does not match the synthesis manifest"
        )

    analysis = value.get("analysis")
    plan = value.get("selection_plan")
    splits = value.get("splits")
    if not isinstance(analysis, dict) or not isinstance(plan, dict):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: analysis and selection_plan must be objects"
        )
    if analysis.get("selection_rule_version") != expected_rule_version:
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: selection rule version does not match the manifest"
        )
    if plan.get("rule_version") != expected_rule_version:
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: selection plan rule version does not match the manifest"
        )
    if (
        not isinstance(splits, dict)
        or not isinstance(splits.get("design"), dict)
        or not isinstance(splits.get("holdout"), dict)
    ):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: benchmark split metadata is missing"
        )

    design_digest = _sha256_text(
        splits["design"].get("input_digest_sha256"),
        path=f"{source}.splits.design.input_digest_sha256",
    )
    holdout_digest = _sha256_text(
        splits["holdout"].get("input_digest_sha256"),
        path=f"{source}.splits.holdout.input_digest_sha256",
    )
    holdout_rows = splits["holdout"].get("non_probe_candidates")
    if (
        isinstance(holdout_rows, bool)
        or not isinstance(holdout_rows, int)
        or holdout_rows < 1
    ):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: holdout non_probe_candidates must be an integer >= 1"
        )

    results = value.get("holdout_results")
    if not isinstance(results, list) or len(results) != len(benchmark.STRATEGIES):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: holdout_results must contain exactly the five strategies"
        )
    observed_order = [
        row.get("strategy") if isinstance(row, dict) else None for row in results
    ]
    if observed_order != list(benchmark.STRATEGIES):
        raise MarginalEvidenceSynthesisInputError(
            f"{source}: holdout_results strategy order does not match v0.1"
        )

    normalized_rows: list[dict[str, Any]] = []
    for row in results:
        selection_status = row.get("selection_status")
        status = row.get("status")
        if selection_status not in {"selected", "unresolved"}:
            raise MarginalEvidenceSynthesisInputError(
                f"{source}: invalid selection_status for {row.get('strategy')!r}"
            )
        if status not in {
            "not_evaluated",
            "evaluated",
            "evaluated_with_unresolved_metrics",
        }:
            raise MarginalEvidenceSynthesisInputError(
                f"{source}: invalid holdout status for {row.get('strategy')!r}"
            )
        selected = row.get("selected_verifier_id")
        if status == "not_evaluated":
            if selection_status != "unresolved" or selected is not None:
                raise MarginalEvidenceSynthesisInputError(
                    f"{source}: unresolved strategy cannot claim a selected verifier"
                )
        elif (
            selection_status != "selected"
            or not isinstance(selected, str)
            or not selected
        ):
            raise MarginalEvidenceSynthesisInputError(
                f"{source}: evaluated strategy requires a selected verifier"
            )

        normalized_rows.append(
            {
                "strategy": row["strategy"],
                "selection_status": selection_status,
                "selected_verifier_id": selected,
                "status": status,
                "panel_error_delta": _finite_number(row.get("panel_error_delta")),
                "delta_effective_votes": _finite_number(
                    row.get("delta_effective_votes")
                ),
            }
        )

    return {
        "benchmark_id": _non_empty_string(
            value.get("benchmark_id"), path=f"{source}.benchmark_id"
        ),
        "gate_id": _non_empty_string(
            value.get("gate_id"), path=f"{source}.gate_id"
        ),
        "design_digest": design_digest,
        "holdout_digest": holdout_digest,
        "holdout_rows": holdout_rows,
        "results": normalized_rows,
    }


def _metric_summary(
    outcomes: list[dict[str, Any]],
    *,
    key: str,
    positive_label: str,
    negative_label: str,
    weighted: bool,
) -> dict[str, Any]:
    values: list[tuple[float, int]] = []
    positive = zero = negative = 0
    for outcome in outcomes:
        value = outcome[key]
        if value is None:
            continue
        values.append((value, outcome["holdout_non_probe_candidates"]))
        if value > 0:
            positive += 1
        elif value < 0:
            negative += 1
        else:
            zero += 1

    result: dict[str, Any] = {
        "measured": len(values),
        "unresolved": len(outcomes) - len(values),
        positive_label: positive,
        "unchanged": zero,
        negative_label: negative,
        "macro_mean": (
            math.fsum(value for value, _ in values) / len(values)
            if values
            else None
        ),
    }
    if weighted:
        denominator = sum(weight for _, weight in values)
        result["holdout_row_weighted_mean"] = (
            math.fsum(value * weight for value, weight in values) / denominator
            if denominator
            else None
        )
    return result


def synthesize(
    reports: list[tuple[str, dict[str, Any]]],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    if len(reports) != len(normalized["benchmark_reports"]):
        raise MarginalEvidenceSynthesisInputError(
            "loaded benchmark report count does not match the synthesis manifest"
        )

    cohorts: list[dict[str, Any]] = []
    benchmark_ids: set[str] = set()
    report_digests: set[str] = set()
    design_digests: set[str] = set()
    holdout_digests: set[str] = set()

    for report_path, raw in reports:
        parsed = _validate_benchmark_report(
            raw,
            expected_evidence_class=normalized["evidence_class"],
            expected_rule_version=normalized["selection_rule_version"],
            source=report_path,
        )
        report_digest = _canonical_digest(raw)
        duplicate_checks = (
            (parsed["benchmark_id"], benchmark_ids, "benchmark_id"),
            (report_digest, report_digests, "benchmark report digest"),
            (parsed["design_digest"], design_digests, "design split digest"),
            (parsed["holdout_digest"], holdout_digests, "holdout split digest"),
        )
        for value, seen, label in duplicate_checks:
            if value in seen:
                raise MarginalEvidenceSynthesisInputError(
                    f"duplicate {label} {value!r}; a cohort cannot be counted twice"
                )
            seen.add(value)

        cohorts.append(
            {
                "benchmark_id": parsed["benchmark_id"],
                "gate_id": parsed["gate_id"],
                "report": report_path,
                "report_digest_sha256": report_digest,
                "design_input_digest_sha256": parsed["design_digest"],
                "holdout_input_digest_sha256": parsed["holdout_digest"],
                "holdout_non_probe_candidates": parsed["holdout_rows"],
                "results": parsed["results"],
            }
        )

    cohorts.sort(key=lambda row: row["benchmark_id"])
    strategy_summaries: list[dict[str, Any]] = []
    for strategy in benchmark.STRATEGIES:
        outcomes: list[dict[str, Any]] = []
        for cohort in cohorts:
            row = next(
                item
                for item in cohort["results"]
                if item["strategy"] == strategy
            )
            outcomes.append(
                {
                    "benchmark_id": cohort["benchmark_id"],
                    "holdout_non_probe_candidates": cohort[
                        "holdout_non_probe_candidates"
                    ],
                    **row,
                }
            )

        strategy_summaries.append(
            {
                "strategy": strategy,
                "cohorts_total": len(outcomes),
                "selection_resolved": sum(
                    row["selection_status"] == "selected" for row in outcomes
                ),
                "selection_unresolved": sum(
                    row["selection_status"] == "unresolved" for row in outcomes
                ),
                "holdout_evaluated": sum(
                    row["status"] != "not_evaluated" for row in outcomes
                ),
                "holdout_not_evaluated": sum(
                    row["status"] == "not_evaluated" for row in outcomes
                ),
                "panel_error_delta": _metric_summary(
                    outcomes,
                    key="panel_error_delta",
                    positive_label="improved",
                    negative_label="worsened",
                    weighted=True,
                ),
                "effective_votes_delta": _metric_summary(
                    outcomes,
                    key="delta_effective_votes",
                    positive_label="positive",
                    negative_label="negative",
                    weighted=False,
                ),
                "cohort_outcomes": outcomes,
            }
        )

    public_cohorts = [
        {key: value for key, value in cohort.items() if key != "results"}
        for cohort in cohorts
    ]
    provenance_input = {
        "config": normalized,
        "benchmark_reports": [
            {
                "benchmark_id": cohort["benchmark_id"],
                "digest_sha256": cohort["report_digest_sha256"],
            }
            for cohort in cohorts
        ],
    }
    return {
        "schema": REPORT_SCHEMA_ID,
        "synthesis_id": normalized["synthesis_id"],
        "evidence_class": normalized["evidence_class"],
        "authority": AUTHORITY,
        "analysis": {
            "mode": ANALYSIS_MODE,
            "selection_rule_version": normalized["selection_rule_version"],
            "benchmark_count": len(cohorts),
            "total_holdout_non_probe_candidates": sum(
                cohort["holdout_non_probe_candidates"] for cohort in cohorts
            ),
        },
        "cohorts": public_cohorts,
        "strategies": strategy_summaries,
        "warnings": [
            "cross-cohort synthesis is descriptive only; it performs no strategy ranking, significance test, threshold tuning, or routing recommendation",
            "exact duplicate split digests are rejected, but benchmark summaries do not expose row identities, so this layer cannot prove that different reports have zero row overlap",
            "macro and holdout-row-weighted panel-error deltas are descriptive summaries, not causal estimates of intrinsic verifier value",
        ],
        "provenance": {
            "tool": "idkmesh marginal-evidence-synthesis",
            "tool_version": _tool_version(),
            "config_digest_sha256": _canonical_digest(normalized),
            "synthesis_input_digest_sha256": _canonical_digest(provenance_input),
        },
    }


def synthesis_file(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    config = load_config_file(path)
    resolved = referenced_paths(path)
    report_paths = resolved[1:]
    reports = [
        (relative, _read_json_file(report_path))
        for relative, report_path in zip(
            config["benchmark_reports"], report_paths
        )
    ]
    return synthesize(reports, config=config)


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
