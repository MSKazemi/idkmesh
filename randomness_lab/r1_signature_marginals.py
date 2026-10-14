"""Per-signature marginal success summary for an R1 replay report.

The R1 real-corpus preregistration requires per-signature marginal success to be
reported alongside pairwise failure correlation. :mod:`randomness_lab.r1_replay`
emits the correlations and arm-level rates but no per-signature figure.

This module is a read-only post-processor. It deliberately does not import,
call, or change :mod:`randomness_lab.r1_replay`, so the replay keeps running
unchanged. It reads one replay report JSON and writes a separate summary bound
to the exact bytes of that report by a SHA-256 digest.

It does not classify ``helps`` / ``hurts`` / ``uncertain``, does not verify
anything, and carries no acceptance authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Sequence

SCHEMA_VERSION = 1
EXPERIMENT = "R1-signature-marginals"
SYNTHETIC_EVIDENCE_CLASS = "synthetic_fixture"
DERIVED_EVIDENCE_CLASS = "replay_report_derivative_provenance_unchecked"
WILSON_Z_95 = 1.959963984540054

GUARDRAIL = (
    "Observational summary of one replay report. Counts are conclusive, independently "
    "verified candidates only; inconclusive candidates are reported as a count and are "
    "neither successes nor failures. Candidates are clustered by work unit and attempt, "
    "so the Wilson interval treats them as independent and is narrower than the true "
    "uncertainty. Marginal success does not separate structural quality from structural "
    "diversity, and this summary classifies nothing as helps, hurts or uncertain. The "
    "provenance of the input report is not checked."
)


class MarginalsError(ValueError):
    """The input report is malformed or inconclusive; no summary is produced."""


class SyntheticInputRefused(MarginalsError):
    """The input is flagged synthetic and the caller did not opt in."""


def wilson_interval(
    successes: int, trials: int, z: float = WILSON_Z_95
) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion; ``None`` when no trials."""
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if trials == 0:
        return None
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _synthetic_flag(report: dict[str, object]) -> bool:
    evidence_class = report.get("evidence_class")
    if evidence_class is not None and not isinstance(evidence_class, str):
        raise MarginalsError("evidence_class must be a string when present")
    synthetic = report.get("synthetic")
    if synthetic is not None and not isinstance(synthetic, bool):
        raise MarginalsError("synthetic must be a boolean when present")
    return bool(synthetic) or (
        isinstance(evidence_class, str) and "synthetic" in evidence_class.lower()
    )


def _excluded_counts(report: dict[str, object]) -> dict[str, int]:
    normalization = report.get("normalization")
    if not isinstance(normalization, dict):
        raise MarginalsError("normalization must be an object")
    excluded = normalization.get("excluded")
    if not isinstance(excluded, dict):
        raise MarginalsError("normalization.excluded must be an object")
    for reason, count in excluded.items():
        if not _is_count(count):
            raise MarginalsError(f"normalization.excluded[{reason!r}] must be a count")
    return {str(reason): int(count) for reason, count in excluded.items()}


def summarize_report(
    report: object,
    input_digest: str,
    *,
    allow_synthetic_fixture: bool = False,
) -> dict[str, object]:
    """Summarize a parsed replay report into per-signature marginal success."""
    if not isinstance(report, dict):
        raise MarginalsError("replay report must be a JSON object")
    synthetic = _synthetic_flag(report)
    if synthetic and not allow_synthetic_fixture:
        raise SyntheticInputRefused(
            "input is flagged synthetic; pass allow_synthetic_fixture to emit a "
            "summary marked evidence_class synthetic_fixture"
        )
    if report.get("experiment") != "R1-real-result-replay":
        raise MarginalsError("input is not an R1-real-result-replay report")
    if report.get("status") != "ok":
        raise MarginalsError(
            f"replay report status is {report.get('status')!r}, not 'ok'; "
            "an insufficient-data report carries no candidate_index"
        )
    candidates = report.get("candidate_index")
    if not isinstance(candidates, list):
        raise MarginalsError("candidate_index must be an array")
    correlations = report.get("signature_failure_correlations")
    if not isinstance(correlations, list) or not all(
        isinstance(row, dict) for row in correlations
    ):
        raise MarginalsError("signature_failure_correlations must be an array of objects")
    excluded = _excluded_counts(report)

    normalization = report["normalization"]
    assert isinstance(normalization, dict)
    conclusive = normalization.get("conclusive_candidates")
    if not _is_count(conclusive) or conclusive != len(candidates):
        raise MarginalsError(
            "normalization.conclusive_candidates does not match candidate_index length"
        )

    per_signature: dict[str, dict[str, object]] = {}
    seen_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise MarginalsError(f"candidate_index[{index}] must be an object")
        result_id = candidate.get("result_manifest_id")
        signature = candidate.get("structural_signature")
        work_unit = candidate.get("work_unit_id")
        verified = candidate.get("verified_good")
        if not isinstance(result_id, str) or not result_id:
            raise MarginalsError(f"candidate_index[{index}] needs result_manifest_id")
        if result_id in seen_ids:
            raise MarginalsError(f"duplicate result_manifest_id: {result_id}")
        seen_ids.add(result_id)
        if not isinstance(signature, str) or not signature:
            raise MarginalsError(f"candidate_index[{index}] needs structural_signature")
        if not isinstance(work_unit, str) or not work_unit:
            raise MarginalsError(f"candidate_index[{index}] needs work_unit_id")
        if not isinstance(verified, bool):
            raise MarginalsError(
                f"candidate_index[{index}].verified_good must be true or false; "
                "an inconclusive candidate is not a success or a failure"
            )
        row = per_signature.setdefault(
            signature, {"successes": 0, "candidates": 0, "work_units": set()}
        )
        row["candidates"] = int(row["candidates"]) + 1
        row["successes"] = int(row["successes"]) + int(verified)
        work_units = row["work_units"]
        assert isinstance(work_units, set)
        work_units.add(work_unit)

    signatures = []
    for signature in sorted(per_signature):
        row = per_signature[signature]
        n = int(row["candidates"])
        k = int(row["successes"])
        interval = wilson_interval(k, n)
        work_units = row["work_units"]
        assert isinstance(work_units, set)
        signatures.append(
            {
                "structural_signature": signature,
                "candidates_analysed": n,
                "independently_verified_successes": k,
                "independently_verified_failures": n - k,
                "success_rate": k / n,
                "wilson_95_interval": list(interval) if interval is not None else None,
                "work_units_covered": len(work_units),
            }
        )

    replay_config = report.get("config")
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": EXPERIMENT,
        "evidence_class": (
            SYNTHETIC_EVIDENCE_CLASS if synthetic else DERIVED_EVIDENCE_CLASS
        ),
        "input_report": {
            "sha256": input_digest,
            "experiment": report["experiment"],
            "status": report["status"],
        },
        "interval_method": {"name": "wilson_score", "confidence": 0.95, "z": WILSON_Z_95},
        "candidates_analysed_total": len(candidates),
        "inconclusive_excluded": {
            "total": sum(excluded.values()),
            "by_reason": {reason: excluded[reason] for reason in sorted(excluded)},
        },
        "signatures": signatures,
        "replay_config": replay_config if isinstance(replay_config, dict) else None,
        "signature_failure_correlations": correlations,
        "interpretation_guardrail": GUARDRAIL,
    }


def summarize_file(
    path: Path, *, allow_synthetic_fixture: bool = False
) -> dict[str, object]:
    """Read ``path`` once, digest its exact bytes, and summarize it."""
    raw = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarginalsError(f"{path.name} is not valid UTF-8 JSON: {error}") from error
    return summarize_report(
        report, digest, allow_synthetic_fixture=allow_synthetic_fixture
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_signature_marginals",
        description=(
            "Read an R1 replay report JSON and emit per-signature marginal success "
            "with Wilson 95% intervals, the unchanged pairwise failure correlations, "
            "and a digest binding the summary to that exact report."
        ),
    )
    parser.add_argument("report", type=Path, help="replay report JSON (read only)")
    parser.add_argument("--output", type=Path, help="write the summary here, not to stdout")
    parser.add_argument(
        "--allow-synthetic-fixture",
        action="store_true",
        help="accept an input flagged synthetic; the output is marked synthetic_fixture",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.output is not None and args.output.resolve() == args.report.resolve():
            raise MarginalsError("--output must not be the input report")
        summary = summarize_file(
            args.report, allow_synthetic_fixture=args.allow_synthetic_fixture
        )
    except (MarginalsError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
