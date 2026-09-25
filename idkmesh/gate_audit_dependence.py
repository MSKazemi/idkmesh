"""Gate-audit-dependence: measured pairwise verifier error-dependence (#654).

``gate-audit-report-v0.1`` intentionally exposes only the panel *mean*
pairwise error correlation, never each verifier pair's own correlation.
That is deliberate: a future AVE (Adaptive Verifier-allocation Evidence)
revision must not reconstruct or invent per-pair dependence from the panel
mean, and it must not treat provider/model/family identity as measured
independence.

This module is the separate, optional artifact issue #654 asked for instead:
``gate-audit-dependence-v0.1`` binds to the exact same canonical
verdict-matrix digest as ``gate-audit-report-v0.1`` and reports, for every
verifier pair, the same phi coefficient ``idkmesh.gate_audit.phi`` uses,
computed over the same non-probe candidates the headline report's statistics
use. A pair with zero error variance on either side is recorded as
unmeasurable, never silently treated as independent (correlation 0).

The report is diagnostic only: it carries no routing, acceptance,
EvaluatorPlan, or merge authority, and it never aggregates pairs into a
per-verifier reputation score.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

from idkmesh.gate_audit import (
    GateAuditInputError,
    load_input_file,
    parse_input_text,
    phi,
)

SCHEMA_ID = "gate-audit-dependence-v0.1"
AUTHORITY = "diagnostic_only"

# phi() ends in a math.sqrt() division; the trailing bits of that result are
# not reproducible across Python/libm builds (observed: Python 3.11 and 3.13
# disagree in the last 1-2 bits of a phi_error value for the committed
# example, on the exact same input). A committed, byte-compared artifact
# cannot carry noise the statistic itself does not claim, so every phi_error
# is rounded to this many decimal digits - far beyond what a Pearson
# correlation over a handful of candidates means, but exactly enough to make
# the report reproducible across interpreters.
_PHI_ERROR_DECIMALS = 12

__all__ = [
    "GateAuditInputError",
    "SCHEMA_ID",
    "AUTHORITY",
    "compute",
    "render_json",
    "dependence_text",
    "dependence_file",
]


def _tool_version() -> str:
    from idkmesh import __version__

    return __version__


def compute(data: dict[str, Any]) -> dict[str, Any]:
    """Compute a gate-audit-dependence report from a validated verdict matrix.

    ``data`` must already have passed ``idkmesh.gate_audit.validate_input()``;
    ``dependence_text``/``dependence_file`` do this for callers holding raw
    text or a file path. Non-probe candidate selection and the phi
    implementation mirror ``idkmesh.gate_audit.audit()`` exactly, so the two
    artifacts describe the same audited population and cannot silently
    diverge in what they call "the panel".
    """
    candidates = data["candidates"]
    verifiers = data["verifiers"]
    non_probe = [c for c in candidates if not c.get("probe", False)]
    truth = {c["id"]: c["ground_truth"] for c in candidates}

    error_vectors: dict[str, list[int]] = {}
    for ver in verifiers:
        error_vectors[ver["id"]] = [
            0 if ver["verdicts"][c["id"]] == truth[c["id"]] else 1
            for c in non_probe
        ]

    # Sorted independent of input order: this artifact's own acceptance
    # criteria call for deterministic ordering, so pair order must not be a
    # silent function of verifier list order in the input document.
    verifier_ids = sorted(error_vectors)

    pairs: list[dict[str, Any]] = []
    unmeasurable = 0
    for a, b in itertools.combinations(verifier_ids, 2):
        error_a, error_b = error_vectors[a], error_vectors[b]
        value = phi(error_a, error_b)
        measurable = not math.isnan(value)
        if not measurable:
            unmeasurable += 1
        pairs.append({
            "verifier_a": a,
            "verifier_b": b,
            "phi_error": (
                round(value, _PHI_ERROR_DECIMALS) if measurable else None),
            "measurable": measurable,
            "joint_error_count": sum(
                1 for x, y in zip(error_a, error_b) if x == 1 and y == 1),
            "a_error_count": sum(error_a),
            "b_error_count": sum(error_b),
        })

    warnings: list[str] = []
    if len(verifier_ids) < 2:
        warnings.append(
            "fewer than two verifiers; there are no pairs to report")
    elif unmeasurable:
        warnings.append(
            f"{unmeasurable}/{len(pairs)} verifier pair(s) have zero error "
            "variance on at least one side on this candidate set; they are "
            "recorded as unmeasurable, not as independent (phi_error = 0)")

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return {
        "schema": SCHEMA_ID,
        "gate_id": data["gate_id"],
        "evidence_class": data["evidence_class"],
        "authority": AUTHORITY,
        "non_probe_candidate_count": len(non_probe),
        "verifier_ids": verifier_ids,
        "pairs": pairs,
        "warnings": warnings,
        "provenance": {
            "tool": "idkmesh gate-audit-dependence",
            "tool_version": _tool_version(),
            "input_digest_sha256": hashlib.sha256(
                canonical.encode("utf-8")).hexdigest(),
        },
    }


def render_json(report: dict[str, Any], pretty: bool = False) -> str:
    """Serialize a report as strict JSON (no bare NaN/Infinity tokens)."""
    return json.dumps(
        report, indent=2 if pretty else None, sort_keys=False,
        allow_nan=False)


def dependence_text(text: str, *, source: str = "input") -> dict[str, Any]:
    """Parse, validate, and compute one gate-audit-dependence report."""
    data = parse_input_text(text, source=source)
    return compute(data)


def dependence_file(input_path: str | Path) -> dict[str, Any]:
    """Load, validate, and compute one gate-audit-dependence report."""
    data = load_input_file(input_path)
    return compute(data)
